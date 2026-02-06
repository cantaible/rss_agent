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
cpolar http 8000
# 或使用 ngrok
ngrok http 8000
```

将获得的 HTTPS 地址配置到飞书开放平台的事件订阅中。

### 5. 长期运行 (防休眠+后台)

如果希望在 Mac 锁屏或后台运行时服务不中断，请使用我们提供的脚本：

```bash
# 1. 赋予执行权限
chmod +x start_services.sh

# 2. 启动服务 (同时启动 RSS Agent 和 cpolar)
./start_services.sh
```

- 该脚本会自动使用 `caffeinate` 防止休眠
- 日志输出到 `service.log` 和 `cpolar.log`
- 停止服务：`pkill -f "python lark_service.py"; pkill -f "cpolar http"`
- **👀 实时查看日志**：
  ```bash
  tail -f service.log
  ```

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

## 🛠️ 常见问题 (FAQ)

### 🔌 cpolar 挂了怎么办？

如果内网穿透服务中断或过期，请按以下步骤重启：

1. **重启 cpolar**：
   在终端运行命令（确保端口与服务一致，默认 8000）：
   ```bash
   cpolar http 8000
   ```
2. **获取新地址**：
   复制终端输出的 HTTPS 地址，例如 `https://1a2b3c4d.r8.cpolar.cn`。

3. **更新飞书配置**：
   - 登录 [飞书开放平台](https://open.feishu.cn/)。
   - 进入你的应用 -> **事件订阅**。
   - 将 **请求地址 URL** 修改为新的地址（注意保留路径 `/`）。
   - 点击 **保存**，飞书会发送 Challenge 验证，服务必须处于运行状态才能通过。

### 🔒 如何固定 cpolar 域名（避免每次重启变动）？

如果你希望拥有一个固定的域名（例如 `my-bot.cpolar.cn`），需要使用 cpolar 的**保留二级子域名**功能：

1. **保留域名**：
   - 登录 [cpolar 官网后台](https://dashboard.cpolar.com/reserved)。
   - 找到 **保留** -> **保留二级子域名**。
   - 选择地区（如 `China VIP` 或 `United States`）。
   - 输入你想要的名称（例如 `rss-agent`），点击保留。

2. **使用固定域名启动**：
   在终端运行（替换 `<你的子域名>` 为你刚才保留的名称）：
   ```bash
   cpolar http -subdomain=<你的子域名> 8000
   ```
   例如：`cpolar http -subdomain=rss-agent 8000`

3. **更新配置文件**：
   如果这是一个长期使用的域名，建议更新飞书后台的事件订阅 URL，就不用每次都改了。
