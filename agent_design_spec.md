# 每日情报速递助手 (Daily News Agent) - 设计规格说明书

> 💡 **文档说明**：本文档旨在定义 Agent 的核心逻辑与架构设计，供开发前确认。请针对各个部分进行 Review。

## 1. 产品概述 (Overview)

**名称**：每日情报速递助手 (Daily News Agent)
**定位**：基于 LangGraph 构建的智能助理，具备长期记忆能力，能识别用户身份，并提供定制化的每日新闻简报。
**核心价值**：自动化识别用户、记住偏好、多步骤智能生成高质量日报。

---

## 2. 核心状态定义 (State Schema)

在 LangGraph 中流转的上下文对象（State）：

```python
class AgentState(TypedDict):
    # 核心字段
    user_id: str          # 用户唯一标识 (对应 Coze sys_uuid)
    messages: List[BaseMessage]  # 对话历史
    
    # 意图与控制
    intent: Literal["write", "read", "chat"]  # 意图分类
    category: Optional[str]  # 订阅分类 (如: "AI", "GAMES", "MUSIC")
    
    # 数据载体
    user_preference: Optional[str]  # 从数据库查到的偏好
    raw_news_data: Optional[List[Dict]]  # API 返回的原始数据
    cleaned_news_data: Optional[List[Dict]] # 模型 A 筛选后的数据
    final_report: Optional[str]  # 模型 B 生成的最终报告
```

---

## 3. 架构拓扑 (Graph Topology)

系统为一个有向图 (Graph)，核心流向如下：

1.  **START** -> `[Router Node]`
2.  `[Router Node]` -> **Conditional Edge**:
    *   If Write -> `[Memory Saver Node]` -> **END**
    *   If Chat -> `[Direct Reply Node]` -> **END**
    *   If Read -> `[Memory Loader Node]`
3.  `[Memory Loader Node]` -> **Conditional Edge (Guard)**:
    *   If No Preference -> `[Guide/Fallback Node]` -> **END**
    *   If Has Preference -> `[Content Gen Pipeline]`
4.  `[Content Gen Pipeline]` (Node E 分拆):
    *   `[API Fetcher]` -> `[Model A (Selector)]` -> `[Model B (Writer)]` -> **END**

---

## 4. 详细节点功能 (Node Specifications)

### 🟢 节点 A: 意图路由层 (Router)
*   **输入**: 用户最新消息 (Message)。
*   **逻辑**: 使用 LLM 或关键词分类。
    *   **写模式**: 用户说“订阅/关注/改看 [分类]”。(需提取参数)
    *   **读模式**: 用户说“日报/早报/新闻”。
    *   **其他**: 闲聊。
*   **白名单校验**: 仅允许 `AI`, `GAMES`, `MUSIC`。若不在范围内，视为无效或引导提示。

### 🔵 节点 B: 记忆写入 (Memory Saver)
*   **功能**: 数据库 Upsert 操作。
*   **逻辑**:
    *   连接数据库。
    *   Query `user_id`。
    *   If exist -> UPDATE category。
    *   If not exist -> INSERT user_id, category。
*   **输出回复**: "订阅成功！已为您记录 [分类] 偏好。"

### 🔵 节点 C: 记忆读取 (Memory Loader)
*   **功能**: 读取用户配置。
*   **逻辑**: SELECT category FROM users WHERE id = user_id。
*   **输出**: 更新 State 中的 `user_preference`。

### 🟡 节点 D: 兜底/安全阀 (Guard)
*   **类型**: 纯逻辑判断 (Conditional Edge)。
*   **逻辑**:
    *   检查 State.user_preference 是否为空。
    *   **空**: 转入引导节点，回复“我还没找到您的记录，请先订阅...”。
    *   **有值**: 转入内容生成流水线。

### 🔴 节点 E: 内容生成流水线 (Content Generation Pipeline)
*该模块包含三个连续子步骤，也就是您定制的“API -> A -> B”逻辑。*

#### 步骤 E1: API 数据请求 (Fetcher)
*   **类型**: Tool / Function
*   **动作**:
    *   构造 POST 请求：`http://150.158.113.98:9090/api/newsarticles/search`
    *   Payload: 
        ```json
        {
            "category": state.user_preference,
            "keyword": state.user_preference, 
            ... // 其他参数如 startDate, endDate 动态生成
        }
        ```
    *   **输出**: 这里的输出是海量的 Raw JSON 数据。

#### 步骤 E2: 清洗与去重 (Model A - The Selector)
*   **模型选型**: 成本较低、速度快、Context Window 大的模型 (e.g., GPT-3.5-Turbo / Haiku)。
*   **System Prompt**:
    > "你是一个严格的新闻编辑。接收原始 JSON 数据，请执行：1. 去除重复内容；2. 剔除广告或无关信息；3. 筛选出 Top 15 条最有价值的新闻。不要改写内容，直接输出清洗后的 JSON list。"
*   **输入**: Raw JSON。
*   **输出**: Cleaned List。

#### 步骤 E3: 深度加工 (Model B - The Writer)
*   **模型选型**: 写作能力强、逻辑优秀的模型 (e.g., GPT-4o / Sonnet / Gemini 1.5 Pro)。
*   **System Prompt**:
    > "你是一个资深主编。基于这份筛选后的新闻列表，写一份风格精美的日报。要求：Markdown 格式、使用 Emoji 分隔、每条新闻必须附带原文链接、保留核心数据。语气要专业且引人入胜。"
*   **输入**: Cleaned List。
*   **输出**: 最终 Markdown 文本，展示给用户。

---

### 6. 技术选型与细节确认 (Updated)

1.  **数据库**: **SQLite**。
    *   理由：开发阶段轻量便捷，本地文件存储。
    *   设计：表名 `user_preferences`，字段 `user_id` (PK, TEXT), `category` (TEXT), `updated_at` (DATETIME)。

2.  **API 接口**:
    *   **Method**: POST
    *   **URL**: `http://150.158.113.98:9090/api/newsarticles/search`
    *   **Payload 模板**:
        ```json
        {
          "keyword": "[CATEGORY_VALUE]",
          "category": "[CATEGORY_VALUE]",
          "sources": [],  
          "tags": [],
          "startDate": "...", 
          "endDate": "...",
          "sortOrder": "latest",
          "includeContent": false
        }
        ```
    *   **逻辑**: 主要使用 `category` 字段，其他字段目前保持默认或动态生成日期。

3.  **鉴权 (Auth)**:
    *   直接使用 `user_id` / `thread_id` 作为唯一凭证。

---

## 7. 飞书集成与定时任务 (Integrations)

### 🤖 飞书机器人接入 (Lark Bot)
为了让 Agent 真正触达用户，将通过 FastAPI 封装为 HTTP 服务，对接飞书开放平台。

*   **架构**: FastAPI Server + Lark OAPI SDK。
*   **交互模式**:
    *   **事件订阅 (Webhook)**: 监听 `im.message.receive_v1` 事件。收到用户消息 -> 触发 Agent -> 异步调用飞书 API 回复。
    *   **API 回复**: 使用 `client.im.v1.message.create` 接口发送 Markdown 消息。

### ⏰ 每日定时推送 (Daily Scheduler)
实现“主动找人”的功能。

*   **工具**: `APScheduler` (集成在本项目 FastAPI 进程中)。
*   **策略**: **按类聚合，生成一次，批量分发** (Group by Category)。
*   **流程**:
    1.  **Trigger**: 每天 08:30 触发。
    2.  **Query**: 从 SQLite 查出所有订阅，按 Category 分组。
        *   `AI`: [UserA, UserB, ...]
        *   `GAMES`: [UserC, ...]
    3.  **Generate**: 针对每个 Category，调用一次 Agent (Content Gen Pipeline) 生成日报文本。
    4.  **Broadcast**: 遍历该组用户列表，调用 Feishu API 逐个发送消息。
    *   *优势*: 极大降低 LLM Token 消耗和 API 请求次数。
