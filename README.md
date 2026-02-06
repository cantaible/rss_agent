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

## 🐳 Docker 部署指南

### 架构说明

采用**分离部署**策略，简化配置：
- **Docker 容器**：运行 RSS Agent 服务（端口 36000）
- **cpolar**：在宿主机运行，将服务暴露到公网

```
飞书服务器 → cpolar (宿主机) → Docker容器 (RSS Agent)
```

### 本地测试部署

1. **准备环境变量**

   ```bash
   cp .env.example .env
   # 编辑 .env 填入你的 API Key 和飞书应用凭证
   nano .env
   ```

2. **启动 Docker 服务**

   ```bash
   docker-compose up -d --build
   ```

3. **验证服务运行**

   ```bash
   curl http://localhost:36000/
   # 应返回: {"status":"ok","message":"Bot is running!"}
   ```

4. **启动 cpolar（另一个终端）**

   ```bash
   cpolar http 36000 -subdomain=ttrssbot
   ```

5. **测试公网访问**

   ```bash
   curl https://ttrssbot.cpolar.top/
   ```

6. **配置飞书事件订阅**

   - 进入飞书开放平台 -> 你的应用 -> 事件订阅
   - 请求地址 URL：`https://ttrssbot.cpolar.top/api/lark/event`

### 云服务器部署

1. **安装 Docker**

   ```bash
   # Ubuntu/Debian
   curl -fsSL https://get.docker.com | bash
   
   # 启动 Docker 服务
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

2. **上传代码**

   ```bash
   # 方式一：使用 git clone
   git clone <你的仓库地址>
   cd rss_agent
   
   # 方式二：使用 scp 上传
   scp -r /local/path/rss_agent root@server:/root/
   ```

3. **配置环境变量**

   ```bash
   cp .env.example .env
   nano .env  # 填入真实配置
   ```

   **必填配置**：
   - `LARK_APP_ID` 和 `LARK_APP_SECRET`
   - `OPENAI_API_KEY`
   - `LLM_FAST_MODEL` 和 `LLM_REASONING_MODEL`

4. **启动 Docker 服务**

   ```bash
   docker-compose up -d --build
   
   # 查看日志确认启动成功
   docker-compose logs -f
   ```

5. **启动 cpolar**

   ```bash
   # 后台运行
   nohup cpolar http 36000 -subdomain=ttrssbot -authtoken=你的token > cpolar.log 2>&1 &
   
   # 查看 cpolar 日志
   tail -f cpolar.log
   ```

   获取 authtoken：访问 [cpolar 官网](https://dashboard.cpolar.com/get-started) 注册并复制 token

6. **配置飞书事件订阅**

   - 访问飞书开放平台，进入你的应用
   - 在 **事件订阅** 中填入：`https://ttrssbot.cpolar.top/api/lark/event`
   
   或使用其他方式：
   - **直接访问**：`http://服务器IP:36000/api/lark/event`（需开放端口）
   - **Nginx 反向代理**：`https://你的域名/api/lark/event`（见下方配置）

### 使用 Nginx 反向代理（生产环境推荐）

1. **安装 Nginx**

   ```bash
   sudo apt install nginx
   ```

2. **配置反向代理**

   创建配置文件 `/etc/nginx/sites-available/rss-agent`：
   ```nginx
   server {
       listen 80;
       server_name 你的域名或IP;
       
       location / {
           proxy_pass http://localhost:36000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
   }
   ```

3. **启用配置**

   ```bash
   sudo ln -s /etc/nginx/sites-available/rss-agent /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

4. **配置 HTTPS（可选但推荐）**

   ```bash
   # 安装 certbot
   sudo apt install certbot python3-certbot-nginx
   
   # 获取证书
   sudo certbot --nginx -d 你的域名
   ```

### 管理命令

**Docker 服务：**

```bash
# 查看运行状态
docker-compose ps

# 重启服务
docker-compose restart

# 查看所有日志（lark_service + cpolar）
docker-compose logs -f

# 只查看最近 100 行日志
docker-compose logs --tail=100

# 只查看 lark_service 日志（过滤掉 cpolar）
docker-compose logs -f | grep -v "cpolar"

# 按类型过滤日志
docker-compose logs -f | grep "📧\|🚦\|📤"  # 消息处理
docker-compose logs -f | grep "❌\|ERROR"   # 错误日志
docker-compose logs -f | grep "👨‍🍳\|🛵"      # 调度任务

# 进入容器内部查看日志
docker-compose exec rss-agent bash
supervisorctl status                          # 查看进程状态
supervisorctl tail -f lark_service           # 实时查看 lark_service 日志
supervisorctl tail -f cpolar                 # 实时查看 cpolar 日志

# 进入容器调试
docker-compose exec rss-agent bash

# 更新代码后重新部署
git pull
docker-compose down
docker-compose up -d --build
```

**Cpolar 管理：**

```bash
# 查看 cpolar 进程
ps aux | grep cpolar

# 查看日志
tail -f cpolar.log

# 停止 cpolar
pkill cpolar

# 重启 cpolar
nohup cpolar http 36000 -subdomain=ttrssbot -authtoken=你的token > cpolar.log 2>&1 &
```

### cpolar 替代方案

如果 cpolar 不稳定，可考虑：

| 工具 | 特点 | 使用方式 |
|------|------|----------|
| **frp** | 开源、可自建 | 需要有公网服务器 |
| **ngrok** | 稳定、商业 | `ngrok http 36000` |
| **Cloudflare Tunnel** | 免费、无限流量 | `cloudflared tunnel` |
| **localhost.run** | 零配置 | `ssh -R 80:localhost:36000 localhost.run` |

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

### 🐳 Docker 容器无法启动怎么办？

1. **查看日志**：
   ```bash
   docker-compose logs rss-agent
   ```

2. **检查环境变量**：
   确保 `.env` 文件存在且配置正确

3. **检查端口占用**：
   ```bash
   sudo lsof -i :36000
   # 如果端口被占用，修改 docker-compose.yml 中的端口映射
   ```

### 📊 如何监控服务运行状态？

可以使用以下工具：

- **Docker 原生**：`docker stats rss-agent`
- **Portainer**：可视化 Docker 管理界面
- **健康检查**：docker-compose.yml 已配置健康检查，使用 `docker-compose ps` 查看

