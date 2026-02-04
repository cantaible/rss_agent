# 多轮交互式智能早报设计方案 (Interactive News Feed PRD)

## 1. 核心目标
将传统的“一次性长文本推送”升级为“**总分结构 + 按需展开**”的沉浸式阅读体验。
解决海量新闻（50+条）带来的信息过载问题，同时通过多轮对话增强用户的控制感。

## 2. 用户体验流程 (UX Flow)

### Phase 1: 每日早报推送 (Cover Card)
**触发**：早晨定时或用户发送“看新闻”。
**Bot 响应**：发送一张精美的**飞书消息卡片 (Interactive Card)**。

**卡片内容设计**：
*   **Header**: ☕️ **AI 行业早报** | 2026-02-04
*   **KPI 区**: 📅 今日监控资讯 **48** 条 | 🔥 重点 **5** 条
*   **Global Summary**: (LLM 生成的一句话综述，如“今日 ToB 赛道动作频繁，巨头安全合规压力增大...”)
*   **🔥 Top 5 必读**:
    1.  [链接] **英特尔宣战 GPU 制造** - *摘要...*
    2.  [链接] **蚂蚁数科成立大模型部** - *摘要...*
    ...
*   **👇 深度专题 (点击展开)**：
    *   [ 🛠️ 硬件与算力 (12条) ]  (按钮 A)
    *   [ ⚖️ 安全与合规 (8条) ]   (按钮 B)
    *   [ 💰 投融资动态 (5条) ]   (按钮 C)

### Phase 2: 专题详情展开 (Detail View)
**触发**：用户点击卡片上的 [ 🛠️ 硬件与算力 ] 按钮。
**交互机制**：
*   按钮背面实际上是发送了一条文本消息：“**展开：硬件与算力**”。
*   (这种机制兼容性最好，不需要配置飞书复杂的 Webhook 回调)

**Bot 响应**：
*   User: "展开：硬件与算力"
*   Bot (识别到多轮意图):
    *   *“收到，正在为您解析【硬件与算力】板块的详细情报...”*
    *   (调用 LLM 或直接读取缓存)
    *   发送该板块的详细新闻列表卡片（或 Markdown 文本）。

### Phase 3: 追问与对话 (Conversation)
**触发**：用户在看完详情后继续提问。
**Bot 响应**：
*   User: "这里面提到的摩尔线程是什么公司？"
*   Bot: 基于刚才的新闻上下文（Context）进行回答。

---

## 3. 技术架构设计

### 3.1 状态管理 (AgentState)
需要在 `agent_graph.py` 中扩展 State，使其具备“短期记忆”能力。

```python
class AgentState(TypedDict):
    # ...原有字段...
    
    # [新增] 结构化简报数据 (用于多轮回忆)
    briefing_data: Optional[NewsBriefing] 
    
    # [新增] 对话阶段
    # "idle": 空闲
    # "briefing_sent": 已发送简报，等待用户选板块
    # "detail_sent": 已发送详情，等待用户追问
    stage: str 
```

### 3.2 数据结构 (Pydantic Models)
用于约束 Writer LLM (DeepSeek R1T2) 的输出。

```python
class NewsItem(BaseModel):
    title: str
    summary: str
    url: str
    score: int # 重要性打分

class NewsCluster(BaseModel):
    name: str # 板块名，如 "硬件与算力"
    description: str # 板块综述
    items: List[NewsItem] # 该板块下的新闻

class NewsBriefing(BaseModel):
    global_summary: str
    top_story_indices: List[int] # 指向 clusters 中具体新闻的坐标，或者直接存 Top items
    clusters: List[NewsCluster]
```

### 3.3 节点逻辑变更

#### A. Writer Node (重构)
*   **旧逻辑**：Input -> LLM -> Markdown String
*   **新逻辑**：Input -> LLM -> `NewsBriefing` (JSON) -> Save to State -> **Render Cover Card** -> Output

#### B. Router Node (升级)
*   需要支持识别“菜单指令”。
*   当 `last_message` 匹配 `r"^展开：(.+)$"` 正则时，且 `state["briefing_data"]` 不为空：
    *   -> 路由到新的 `Detail Node`。
    *   -> 提取实体 "硬件与算力"。

#### C. Detail Node (新增)
*   **输入**：板块名 (Category Name)
*   **逻辑**：
    1.  从 `state["briefing_data"].clusters` 中找到对应板块。
    2.  格式化输出该板块下的所有 `items`。
    3.  (可选) 调用 LLM 针对该板块写更深度的点评。

---

## 4. 实施步骤

1.  **Step 1: Pydantic 定义**
    在 `agent_graph.py` 中添加 `NewsBriefing` 等结构定义。

2.  **Step 2: Writer 改造**
    修改 `writer_node`，使用 Prompt 要求 LLM 输出符合结构的 JSON 数据。
    *注：DeepSeek R1T2 在这里需要很强的 Prompt 约束。*

3.  **Step 3: 卡片渲染器**
    新建 `lark_card_builder.py`，编写 `build_cover_card(data)` 函数，返回飞书 JSON。

4.  **Step 4: 路由与新的节点**
    在 `router_node` 增加对 "展开：..." 指令的拦截。
    新增 `detail_node` 处理展开后的逻辑。

5.  **Step 5: 联调**
    测试“生成 -> 点击 -> 展开”的全链路。
