from typing import TypedDict, List, Optional, Dict
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field
from typing import Literal

# --- Pydantic Data Models (用于 Writer 结构化输出) ---
class NewsItem(BaseModel):
    title: str = Field(..., description="新闻标题")
    summary: str = Field(..., description="新闻摘要")
    url: str = Field(..., description="原文链接")
    score: int = Field(..., description="重要性打分 1-100")

class NewsCluster(BaseModel):
    name: str = Field(..., description="板块名称，如'硬件与算力'")
    description: str = Field(..., description="板块综述")
    items: List[NewsItem] = Field(..., description="该板块下的新闻列表")

class NewsBriefing(BaseModel):
    global_summary: str = Field(..., description="全篇早报的开场综述")
    top_story_indices: List[int] = Field(None, description="今日头条新闻在 clusters 中的索引(暂不使用)")
    # 注意：为了简化，Top 5 可以在展示层逻辑处理，或者直接取 clusters 里 score 最高的
    clusters: List[NewsCluster] = Field(..., description="新闻分类板块")

# --- Agent State ---
class AgentState(TypedDict):
    # 消息历史
    messages: List[BaseMessage]
    user_id: str
    message_id: Optional[str]
    user_preference: Optional[str]
    news_content: Optional[str] 
    
    # [新增] 结构化简报数据 (用于多轮回忆)
    briefing_data: Optional[Dict] # 实际存的是 NewsBriefing.model_dump()
    
    # [新增] 当前选中的详情板块 (与 user_preference 长期偏好区分开)
    selected_cluster: Optional[str]

    # 控制流标志
    intent: Optional[str] # write / read / chat
    force_refresh: Optional[bool] # [新增] 是否强制刷新


class RouterDecision(BaseModel):
    """Router 对用户意图的分析结果"""
    intent: Literal["write", "read", "chat"] = Field(
        ..., description="用户的核心意图"
    )
    category: Optional[str] = Field(
        None, description="提取出的具体领域关键词，如 'AI', '科技'"
    )

from tools import fetch_news
from simple_bot import llm_fast, llm_reasoning # Import capability-based LLMs
import json

from langchain_core.prompts import ChatPromptTemplate

def router_node(state: AgentState):
    """进阶版意图识别：使用 LLM 结构化输出 + 容错兜底"""
    last_message = state["messages"][-1].content
    print(f"🚦 Router handling message: {last_message}")
    
    # --- 拦截器 1: 详情展开指令 (来自卡片按钮) ---
    # 匹配 "展开：XXX" 或 "👉 XXX"
    if "展开：" in last_message or "👉" in last_message:
        # 简单粗暴提取：取冒号或符号后的内容，去除括号里的数字
        # e.g. "👉 硬件与算力 (8)" -> "硬件与算力"
        import re
        # 匹配 "展开：(.+)" 或 "👉 (.+)"
        match = re.search(r"(?:展开：|👉\s*)([^\(\)]+)", last_message)
        if match:
            category = match.group(1).strip()
            print(f"🚀 [Router] Intercepted Detail Request: {category}")
            return {"intent": "detail", "selected_cluster": category}
    
    try:
        # 定义 System Prompt 强化指令 (适配 Reasoning 模型)
        system_prompt = """你是一个智能意图路由器。请分析用户的输入，提取核心意图和实体。
        
        规则：
        1. 如果用户想看新闻、日报、简报 -> intent: read
        2. 如果用户想订阅、关注、追踪某话题 -> intent: write, category: <话题>
        3. 其他情况（闲聊、问好、不想看了） -> intent: chat
        
        输出格式：必须是符合 RouterDecision 结构的 JSON。"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        # 绑定工具 (使用 Fast 模型 -> DeepSeek V3)
        print(f"🤖 User Input: {last_message}")
        structured_llm = llm_fast.with_structured_output(RouterDecision) 
        
        # 组合 chain
        # chain = prompt | structured_llm
        prompt_message = prompt.invoke({"input": last_message})
        decision = structured_llm.invoke(prompt_message)
        
        print(f"👉 LLM Decision: {decision.intent}, Category: {decision.category}")
        return {
            "intent": decision.intent, 
            "user_preference": decision.category
        }
    except Exception as e:
        print(f"⚠️ Router LLM Error: {e}")
        # 兜底策略：诚实报错，不进行猜测
        return {
            "intent": "error",
            "messages": [AIMessage(content=f"❌ 意图识别失败啦。\n错误详情: {str(e)}")]
        }


from database import upsert_preference, get_preference
from langchain_core.messages import AIMessage

def saver_node(state: AgentState):
    """保存用户偏好节点"""
    # 1. 优先使用 Router 提取的结构化数据
    extracted_category = state.get("user_preference")
    
    # 2. 如果 Router 没提出来，诚实地返回错误提示，而不是瞎猜
    if not extracted_category:
        print("⚠️ [Saver] Extraction failed")
        return {"messages": [AIMessage(content="🤔 我知道您想调整偏好，但我没能识别出具体的话题。\n\n请尝试更清晰的指令，例如：“订阅AI”、“关注游戏GAMES”、“关注音乐MUSIC”。")]}
    
    print(f"💾 [Saver] Saving preference: {extracted_category}")
    
    # 3. 存入数据库
    res = upsert_preference(state["user_id"], extracted_category)
    
    # 4. 返回动态消息
    return {"messages": [AIMessage(content=f"已关注：【{extracted_category}】板块，每日自动为您推送\n\n点击“当日{extracted_category}新闻”，即可获取今日动态。")]}



def fetcher_node(state: AgentState):
    """
    负责获取新闻数据：
    1. 先检查数据库缓存 (除非 force_refresh=True)
    2. 如果无缓存，调用 Tool 抓取 RSS
    """
    print("🕵️ [Fetcher] Node started")
    pref = get_preference(state["user_id"])
    if not pref:
        print("⚠️ [Fetcher] No preference found")
        return {
            "user_preference": None, 
            "messages": [AIMessage(content="您还没有订阅任何内容，请发送 '订阅 AI'，'订阅 MUSIC'，或者'订阅 GAMES")]
        }
    
    # 1. 尝试从数据库读取今日已生成的缓存
    today = date.today().isoformat()
    # 注意：get_cached_news 返回 {"content": str, "briefing_data": str/json, "generated_at": str}
    
    # 策略：如果有缓存且非强制刷新，我们直接返回缓存
    if not state.get("force_refresh"):
        cached = get_cached_news(pref, today)
        if cached and cached.get("briefing_data"):
            print(f"✅ [Fetcher] Found cached data for {pref}. generated_at={cached.get('generated_at')}")
            try:
                briefing_json = json.loads(cached["briefing_data"])
                return {
                    "user_preference": pref, 
                    "news_content": None, 
                    "briefing_data": briefing_json,
                    "generated_at": cached.get("generated_at")
                }
            except Exception as e:
                print(f"⚠️ [Fetcher] Cache parse failed: {e}")
                pass
    else:
        print(f"🔄 [Fetcher] Force refresh enabled. Skipping cache check.")

    # 2. 无缓存或强制刷新，执行实时抓取
    # 2. 无缓存或强制刷新，执行实时抓取
    print(f"🌍 [Fetcher] Fetching news for: {pref}")
    
    news_data = fetch_news(pref)
    
    print(f"✅ [Fetcher] Got data (length: {len(str(news_data))})")
    return {"user_preference": pref, "news_content": json.dumps(news_data, ensure_ascii=False)}

from messaging import reply_message

from lark_card_builder import build_cover_card

def writer_node(state: AgentState):
    """
    核心写作节点：
    1. 接收 Fetcher 抓取到的原始新闻数据
    2. 调用 Reasoning LLM (DeepSeek R1) 进行深度分析
    3. 生成结构化简报 (Summary + Clusters)
    4. 将结果存入 State，并渲染飞书卡片
    """
    print("✍️ [Writer] Node started")
    
    if state.get("message_id"):
        reply_message(state["message_id"], "✍️ AI 正在深度分析新闻数据，生成交互式早报...")
        
    news_json = state.get("news_content")
    category = state.get("user_preference", "未知领域")
    
    # 策略 0: 如果 State 中已有 briefing_data (来自 Cache)，直接使用
    if state.get("briefing_data"):
        try:
            print(f"⏩ [Writer] Using cached briefing data for {category}")
            # Pydantic 还原
            briefing = NewsBriefing(**state["briefing_data"])
            
            # 构建卡片 (传入 generated_at 和 category)
            card_content = build_cover_card(briefing, generated_at=state.get("generated_at"), category=category)
            
            return {
                "briefing_data": state["briefing_data"], 
                "messages": [AIMessage(content=card_content)]
            }
        except Exception as e:
            print(f"⚠️ [Writer] Failed to reuse cache: {e}, falling back to generation")
            # 失败了则继续往下执行生成逻辑
    
    # 策略 1: 如果没有 News Content (这不应该发生，Fetcher 应该处理了)，报错
    if not news_json:
        return {"messages": [AIMessage(content="未能获取新闻数据")]}
        
    system_prompt = f"""你是一个资深的行业情报分析师。用户的订阅偏好是：{category}。
    请阅读输入的新闻 JSON 数据，运用你的专业洞察力，进行以下处理：

    1. **去重与清洗**：合并雷同新闻，剔除无关噪音。
    2. **聚类**：将新闻归类为 3-5 个核心板块（Cluster）。
    3. **打分**：为每条新闻打分 (1-100)。
    4. **综述 (Global Summary)**：
       - **必需**：通读所有新闻，写一段 **犀利、具体、直击要害** 的情报综述，长度在200中文字符左右。
       - **禁止**：套话（如“行业稳步发展”）、废话（如“值得关注”）、笼统描述。
       - **要求**：必须提及具体的公司名、产品名、核心争端或关键数据。定性与定量结合，文字和数字结合，要点清晰，直接告诉用户“今天发生了什么大事，意味着什么”。
    
    请严格输出符合 NewsBriefing 结构的 JSON。
    **重要**：
    1. 直接输出 JSON 字符串，**不要**包含 ```json ... ``` 等 Markdown 格式。
    2. JSON 根对象直接包含 `global_summary` 和 `clusters` 字段，**不要**包裹在 `NewsBriefing` 等根键下。
    3. 不要包含任何推理过程文本。"""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{news_data}"),
    ])
    
    print("🧠 [Writer] Invoking LLM for Structured Output...")
    # 切换到 llm_reasoning (Claude 3.5 Sonnet / DeepSeek R1) 以获得最佳写作质量
    structured_llm = llm_reasoning.with_structured_output(NewsBriefing) 
    chain = prompt | structured_llm
    
    try:
        briefing: NewsBriefing = chain.invoke({"news_data": news_json})
        print(f"✅ [Writer] Briefing Generated. Clusters: {[c.name for c in briefing.clusters]}")
        
        # 1. 构建飞书交互卡片
        card_content = build_cover_card(briefing, category=category)
        
        # 2. 返回结果
        # 注意：我们需要标记这是一张卡片，而不是普通文本
        # 下游发送端 (lark_service 或 messaging) 需要识别这个标记
        # 这里我们将 content 设为 card json，开头加一个特殊标记？
        # 或者使用 additional_kwargs
        
        return {
            "briefing_data": briefing.model_dump(),
            "messages": [AIMessage(content=card_content)] 
        }
    except Exception as e:
        print(f"❌ [Writer] Analysis Failed: {e}")
        return {"messages": [AIMessage(content=f"生成早报失败，请稍后重试。\nError: {str(e)}")]}


# --- 详情展示节点 ---

from database import get_cached_news # Import at top or inside if circular
from datetime import date, timedelta # [新增] timedelta
from database import get_cached_news

# --- 详情展示节点 ---
def detail_node(state: AgentState):
    """
    接收用户选择的板块名 -> 从 State 缓存或数据库中查找新闻 -> 渲染详情
    """
    print("🔍 [Detail] Node started")
    selected_cluster = state.get("selected_cluster") # 使用专门的字段
    briefing_dump = state.get("briefing_data")
    
    # 策略 1: 尝试从 State 获取 (如果是同一会话)
    # 策略 2: 尝试从数据库获取 (如果是跨会话点击)
    if not briefing_dump:
        print(f"⚠️ [Detail] State missing briefing_data, searching DB for cluster: {selected_cluster}")
        today = date.today().isoformat()
        categories = ["AI", "GAMES", "MUSIC", "SHORT_DRAMA"] # 已知类别
        
        for cat in categories:
            cached = get_cached_news(cat, today)
            # get_cached_news 返回 {"content": str, "briefing_data": str}
            if cached and cached.get("briefing_data"):
                try:
                    data_json = json.loads(cached["briefing_data"])
                    # 检查 cluster 是否在这里
                    # 简单检查：直接看 briefing_data 字符串里有没有 cluster 名字？
                    # 或者解析后通过 Pydantic 检查
                    # 为求稳，我们先尝试解析
                    # 注意：NewsBriefing 结构是 global_summary, clusters
                    # 这里是一个 dict
                    clusters_data = data_json.get("clusters", [])
                    for c in clusters_data:
                        if c.get("name") and (selected_cluster in c["name"] or c["name"] in selected_cluster):
                            print(f"✅ [Detail] Found cluster in DB category: {cat}")
                            briefing_dump = data_json
                            break
                except Exception as e:
                    print(f"⚠️ [Detail] Parse DB cache failed for {cat}: {e}")
            
            if briefing_dump:
                break
    
    if not briefing_dump or not selected_cluster:
        return {"messages": [AIMessage(content=f"⚠️ 未找到板块：{selected_cluster}。\n\n数据可能已更新过期，请发送“生成日报”获取最新资讯。")]}
    
    # 恢复 Pydantic 对象
    try:
        briefing = NewsBriefing(**briefing_dump)
    except:
        return {"messages": [AIMessage(content="⚠️ 数据解析错误")]}
    
    # 查找对应板块
    found_cluster = None
    for cluster in briefing.clusters:
        if cluster.name in selected_cluster or selected_cluster in cluster.name:
            found_cluster = cluster
            break
            
    if not found_cluster:
        return {"messages": [AIMessage(content=f"⚠️ 未找到板块：{selected_cluster}")]}
        
    # 渲染详情 (这里简化为 Markdown 文本，也可以做成卡片)
    msg = f"## 📂 专题详情：{found_cluster.name}\n\n"
    msg += f"_{found_cluster.description}_\n\n"
    for item in found_cluster.items:
        msg += f"### [{item.title}]({item.url})\n"
        msg += f"{item.summary}\n\n"
    
    return {"messages": [AIMessage(content=msg)]}



# --- 组装图谱 (The Map) ---
from langgraph.graph import StateGraph, END

# 1. 拿出一张空白地图
workflow = StateGraph(AgentState)

# Chat Node: 使用 LLM 进行自然对话
def chat_node(state):
    """聊天模式节点 - 调用 LLM 进行多轮对话"""
    # state["messages"] 已包含历史上下文（由 run_agent 的滑动窗口提供）
    response = llm_fast.invoke(state["messages"])
    return {"messages": [response]}

# 2. 在地图上画站点 (Nodes)
workflow.add_node("router", router_node)
workflow.add_node("saver", saver_node)
workflow.add_node("fetcher", fetcher_node)
workflow.add_node("writer", writer_node)
workflow.add_node("detail", detail_node) # 新增 Detail 节点
workflow.add_node("chat", chat_node)

# 3. 设置起点
workflow.set_entry_point("router")

# 4. 设置分岔路口
workflow.add_conditional_edges(
    "router",
    lambda x: x["intent"],
    {
        "write": "saver",
        "read": "fetcher",
        "detail": "detail", 
        "chat": "chat",
        "error": END
    }
)

# 5. 设置终点
workflow.add_edge("saver", END)
workflow.add_edge("chat", END)
workflow.add_edge("fetcher", "writer")
workflow.add_edge("writer", END)
workflow.add_edge("detail", END) # Detail -> END

# 6. 编译（启用 Checkpointer 以持久化 State）
from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)
