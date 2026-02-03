# MVP Implementation Plan: Simple Lark Chatbot

> 🎯 **目标**: 快速验证 "LangChain + FastAPI + Lark (飞书)" 的全链路连通性。暂不涉及复杂的 Agent 图和数据库，先跑通最简单的“一问一答”。

## 1. 环境准备 (Environment Setup)

### [NEW] `requirements.txt`
定义项目依赖。
*   `langchain`, `langchain-openai` (或者其他模型库)
*   `langgraph`
*   `fastapi`, `uvicorn` (Web 服务)
*   `lark-oapi` (飞书 SDK)
*   `python-dotenv` (环境变量管理)

### [NEW] `.env`
配置敏感信息 (用户需手动填写)。
*   `LARK_APP_ID`
*   `LARK_APP_SECRET`
*   `OPENAI_API_KEY` (或 DeepSeek 等 Key)

---

## 2. 核心模块开发

### [NEW] `simple_bot.py` (The Brain)
实现最简单的 LangChain 调用。
*   不使用复杂的 Graph，只写一个 `invoke_llm(user_input: str) -> str` 函数。
*   使用 `ChatOpenAI` 直接返回模型的回复。

### [NEW] `lark_service.py` (The Body)
FastAPI 服务端，处理飞书的回调。
*   **Endpoint**: `POST /api/lark/event`
*   **Event Handler**: 解析飞书 JSON，提取 `text`。
*   **Reply Logic**: 调用 `simple_bot` 得到回复，再调用 `lark-oapi` 发回给用户。

---

## 3. 验证步骤 (Verification)

1.  **本地启动**: `uvicorn lark_service:app --reload`.
2.  **内网穿透**: 使用 `ngrok` 或类似的工具，把本地 `8000` 端口暴露到公网 URL。
3.  **飞书配置**:
    *   在飞书开发者后台 -> 事件订阅 -> 填写公网 URL。
    *   发布版本。
4.  **最终测试**: 在飞书里给机器人发 "Hello"，看能不能收到回复。

---

## 下一步 (Next Steps)
MVP 跑通后，我们将按照 `agent_design_spec.md` 逐步引入：
1.  LangGraph 状态管理。
2.  SQLite 记忆存储。
3.  News API 和定时任务。
