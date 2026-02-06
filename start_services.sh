#!/bin/bash

# 端口配置
PORT=36000

echo "🛑 Stopping existing services..."
pkill -f "python lark_service.py"
pkill -f "cpolar http"

echo "🚀 Starting RSS Agent Services on port $PORT..."

# 1. 启动 Lark Service (Python)
# caffeinate -i: 防止 Mac 休眠
# nohup: 防止关闭终端后退出
nohup caffeinate -i python lark_service.py > service.log 2>&1 &
PID_PY=$!
echo "✅ Lark Service started (PID: $PID_PY). Logs: service.log"

# 2. 启动 cpolar (内网穿透)
# 飞书开放平台配置：https://ttrssbot.ap.cpolar.io/api/lark/event
# 使用固定子域名 ttrssbot (https://ttrssbot.ap.cpolar.io)
# 开启 Dashboard: http://127.0.0.1:4040
nohup caffeinate -i cpolar http $PORT -subdomain=ttrssbot -dashboard=on -inspect-addr=127.0.0.1:4040 > cpolar.log 2>&1 &
PID_CP=$!
echo "✅ Cpolar started (PID: $PID_CP). Dashboard: http://127.0.0.1:4040"

echo ""
echo "🎉 Services are running in background!"
echo "---------------------------------------"
echo "To follow logs run:"
echo "tail -f service.log cpolar.log"
echo "---------------------------------------"
echo "To stop services run:"
echo "pkill -f 'python lark_service.py'; pkill -f 'cpolar http'"
