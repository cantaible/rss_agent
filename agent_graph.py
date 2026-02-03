from typing import TypedDict, List, Optional
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # 消息历史 (Chat History)
    messages: List[BaseMessage]
    
    # 上下文信息
    user_id: str
    user_preference: Optional[str]
    news_content: Optional[str] # 抓取到的新闻数据

    
    # 控制流标志
    intent: Optional[str] # write / read / chat

def router_node(state: AgentState):
    """简单的意图识别节点，现在只能识别一些关键词"""
    last_message = state["messages"][-1].content
    
    if "订阅" in last_message or "关注" in last_message:
        return {"intent": "write"}
    elif "新闻" in last_message or "早报" in last_message:
        return {"intent": "read"}
    else:
        return {"intent": "chat"}

from database import upsert_preference, get_preference
from langchain_core.messages import AIMessage

def saver_node(state: AgentState):
    msg = state["messages"][-1].content
    category = "AI" # Default
    if "GAMES" in msg: category = "GAMES"
    elif "MUSIC" in msg: category = "MUSIC"
    
    res = upsert_preference(state["user_id"], category)
    return {"messages": [AIMessage(content=res)]}

from tools import fetch_news
from simple_bot import llm
import json

def fetcher_node(state: AgentState):
    """读取偏好 -> 抓取新闻"""
    print("🕵️ [Fetcher] Node started")
    pref = get_preference(state["user_id"])
    if not pref:
        print("⚠️ [Fetcher] No preference found")
        return {
            "user_preference": None, 
            "messages": [AIMessage(content="您还没有订阅任何内容，请发送 '订阅 AI'")]
        }
    
    print(f"🌍 [Fetcher] Fetching news for: {pref}")
    news_data = fetch_news(pref)
    print(f"✅ [Fetcher] Got data (length: {len(str(news_data))})")
    return {"user_preference": pref, "news_content": json.dumps(news_data, ensure_ascii=False)}

def writer_node(state: AgentState):
    """新闻数据 -> LLM 撰写日报"""
    print("✍️ [Writer] Node started")
    news_json = state.get("news_content")
    category = state.get("user_preference", "未知领域")
    
    if not news_json:
        print("❌ [Writer] No news content")
        return {"messages": [AIMessage(content="未获取到新闻数据。")]}
        
    prompt = f"""# 角色
你是一个资深的行业情报分析师。用户的订阅偏好是：{category}。

# 任务
请阅读以下原始新闻数据：
{news_json}

# 输出要求
请根据上述数据，生成一份结构清晰、排版精美的《每日情报速递》。格式如下：

---
### ☕️ 每日早报 | {category} 版
*(这里写一句关于今天新闻整体气氛的开场白)*

#### 🔥 今日头条
*(从新闻中挑选最重要的一条，写一段 80 字左右的深度摘要)*

#### 📰 行业快讯 （Top 10）
*(请遍历**所有**新闻数据，按照重要程度挑选前十条：)*

* [**{{新闻标题}}**]({{sourceURL}}) 
* [**{{新闻标题}}**]({{sourceURL}}) 
*(...请列出剩余所有新闻)*

#### 💡 独家点评
*(用一句金句总结今天的行业趋势或给出投资/关注建议)*
---

# 注意事项
- 必须使用 Markdown 格式。
- 适当使用 Emoji (🚀, 💡, 📢) 增加可读性。
- 如果新闻数据为空，请输出：“今日该板块暂无重大新闻，请稍后再试。”
"""
    print("🧠 [Writer] Invoking LLM...")
    response = llm.invoke(prompt)
    print("✅ [Writer] LLM response received")
    return {"messages": [response]}


# --- 组装图谱 (The Map) ---
from langgraph.graph import StateGraph, END

# 1. 拿出一张空白地图
workflow = StateGraph(AgentState)

# 2. 在地图上画站点 (Nodes)
workflow.add_node("router", router_node)
workflow.add_node("saver", saver_node)
workflow.add_node("fetcher", fetcher_node) # 改名
workflow.add_node("writer", writer_node)   # 新增
workflow.add_node("chat", lambda x: {"messages": [AIMessage(content="我是聊天模式(暂未接入LLM)")]})

# 3. 设置起点
workflow.set_entry_point("router")

# 4. 设置分岔路口
workflow.add_conditional_edges(
    "router",
    lambda x: x["intent"],
    {
        "write": "saver",
        "read": "fetcher", # 指向 fetcher
        "chat": "chat"
    }
)

# 5. 设置终点
workflow.add_edge("saver", END)
workflow.add_edge("chat", END)
workflow.add_edge("fetcher", "writer") # Fetcher -> Writer
workflow.add_edge("writer", END)       # Writer -> END

# 6. 编译
graph = workflow.compile()




