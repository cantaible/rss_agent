# 🤖 RSS Agent - 智能新闻订阅机器人

基于 LangGraph 和飞书的智能新闻订阅助手，每天为你生成专属的行业情报速递。

## ✨ 功能特性

- 🎯 **智能订阅**: 订阅你关心的领域（AI、GAMES、MUSIC 等）
- 📰 **每日早报**: 自动抓取最新新闻并生成精美的 Markdown 日报
- 🧠 **LangGraph Agent**: 基于状态机的对话流程，智能判断用户意图
- 💾 **记忆系统**: SQLite 持久化存储用户偏好
- 🚀 **飞书集成**: 通过飞书机器人随时随地获取资讯

## 🏗️ 架构设计

```
用户消息 → Lark Service → LangGraph Router → Fetcher → Writer → 回复用户
                                    ↓
                                  Saver
                                    ↓
                                 Database
```

### 核心模块

- `lark_service.py`: FastAPI 服务，处理飞书事件回调
- `agent_graph.py`: LangGraph 状态机，实现业务逻辑
- `database.py`: SQLite 数据库操作
- `tools.py`: 外部 API 调用工具（新闻抓取）
- `simple_bot.py`: LLM 客户端封装

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```ini
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL_NAME=deepseek/deepseek-r1
LARK_APP_ID=cli_xxx
LARK_APP_SECRET=xxx
```

### 3. 启动服务

```bash
python lark_service.py
```

### 4. 配置内网穿透

```bash
cpolar http 36000
# 或使用 ngrok
ngrok http 36000
```

将获得的 HTTPS 地址配置到飞书开放平台的事件订阅中。

## 📖 使用指南

1. **订阅领域**：发送 `订阅 AI`
2. **获取早报**：发送 `我的早报` 或 `看看新闻`
3. **闲聊**：发送任意其他内容

## 🔧 技术栈

- **Web 框架**: FastAPI
- **Agent 框架**: LangGraph
- **LLM**: OpenAI API / OpenRouter
- **数据库**: SQLite
- **即时通讯**: 飞书开放平台

## 📝 开发日志

查看 [mvp_plan.md](mvp_plan.md) 和 [agent_design_spec.md](agent_design_spec.md) 了解详细的开发过程。

## 📄 License

MIT

## 🙏 致谢

感谢 LangGraph 和飞书开放平台提供的强大能力。
