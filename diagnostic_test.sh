#!/bin/bash

echo "========================================="
echo "🔍 RSS Agent 服务诊断工具"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查 Docker 容器状态
echo "1️⃣ 检查 Docker 容器状态..."
echo "---"
if docker ps | grep -q "rss-agent"; then
    echo -e "${GREEN}✅ rss-agent 容器正在运行${NC}"
    CONTAINER_STATUS=$(docker inspect rss-agent --format='{{.State.Health.Status}}' 2>/dev/null)
    if [ "$CONTAINER_STATUS" = "healthy" ]; then
        echo -e "${GREEN}   健康状态: healthy${NC}"
    elif [ "$CONTAINER_STATUS" = "unhealthy" ]; then
        echo -e "${RED}   健康状态: unhealthy${NC}"
        echo -e "${YELLOW}   建议: 检查容器日志 'docker logs rss-agent'${NC}"
    else
        echo -e "${YELLOW}   健康状态: $CONTAINER_STATUS${NC}"
    fi
else
    echo -e "${RED}❌ rss-agent 容器未运行${NC}"
    echo -e "${YELLOW}   建议: 运行 'docker-compose up -d' 启动服务${NC}"
fi
echo ""

# 2. 检查 Lark Service (端口 36000)
echo "2️⃣ 检查 Lark Service (端口 36000)..."
echo "---"
LARK_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:36000/ 2>/dev/null)
if [ "$LARK_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ Lark Service 正常响应${NC}"
    curl -s http://localhost:36000/ | jq . 2>/dev/null || curl -s http://localhost:36000/
else
    echo -e "${RED}❌ Lark Service 无响应 (HTTP $LARK_RESPONSE)${NC}"
    echo -e "${YELLOW}   建议: 检查服务是否启动，端口是否被占用${NC}"
fi
echo ""

# 3. 检查 cpolar 进程
echo "3️⃣ 检查 cpolar 进程..."
echo "---"
if pgrep -f "cpolar" > /dev/null; then
    echo -e "${GREEN}✅ cpolar 进程正在运行${NC}"
    ps aux | grep cpolar | grep -v grep
else
    echo -e "${RED}❌ cpolar 进程未运行${NC}"
    echo -e "${YELLOW}   建议: 运行 './start_services.sh' 或手动启动 cpolar${NC}"
fi
echo ""

# 4. 检查 cpolar Dashboard (端口 4040)
echo "4️⃣ 检查 cpolar Dashboard (端口 4040)..."
echo "---"
CPOLAR_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:4040/api/tunnels 2>/dev/null)
if [ "$CPOLAR_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✅ cpolar Dashboard API 正常${NC}"
    echo "   获取隧道信息:"
    curl -s http://127.0.0.1:4040/api/tunnels | jq '.tunnels[] | {name, public_url, config}' 2>/dev/null || \
    curl -s http://127.0.0.1:4040/api/tunnels
else
    echo -e "${RED}❌ cpolar Dashboard API 无响应 (HTTP $CPOLAR_RESPONSE)${NC}"
    echo -e "${YELLOW}   建议: cpolar 可能未启动 Dashboard，检查启动参数${NC}"
    echo -e "${YELLOW}   尝试重启: pkill -f 'cpolar http'; cpolar http 36000 -subdomain=ttrssbot -dashboard=on -inspect-addr=127.0.0.1:4040${NC}"
fi
echo ""

# 5. 检查端口占用
echo "5️⃣ 检查端口占用情况..."
echo "---"
echo "端口 36000:"
if lsof -i :36000 > /dev/null 2>&1; then
    lsof -i :36000 | grep -v COMMAND
else
    echo -e "${YELLOW}   端口未被占用${NC}"
fi
echo ""
echo "端口 4040:"
if lsof -i :4040 > /dev/null 2>&1; then
    lsof -i :4040 | grep -v COMMAND
else
    echo -e "${YELLOW}   端口未被占用${NC}"
fi
echo ""

# 6. 测试外网访问（如果 cpolar 正常）
echo "6️⃣ 测试 cpolar 公网 URL..."
echo "---"
TUNNEL_INFO=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null)
if [ ! -z "$TUNNEL_INFO" ]; then
    PUBLIC_URL=$(echo "$TUNNEL_INFO" | jq -r '.tunnels[0].public_url' 2>/dev/null)
    if [ ! -z "$PUBLIC_URL" ] && [ "$PUBLIC_URL" != "null" ]; then
        echo "   公网 URL: $PUBLIC_URL"
        echo "   测试健康检查..."
        EXTERNAL_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$PUBLIC_URL/" 2>/dev/null)
        if [ "$EXTERNAL_RESPONSE" = "200" ]; then
            echo -e "${GREEN}✅ 外网访问正常${NC}"
            echo "   飞书配置 URL: $PUBLIC_URL/api/lark/event"
        else
            echo -e "${RED}❌ 外网访问失败 (HTTP $EXTERNAL_RESPONSE)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  无法获取公网 URL${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  cpolar API 无响应，跳过外网测试${NC}"
fi
echo ""

# 7. 查看最新日志
echo "7️⃣ 最新服务日志 (最后 10 行)..."
echo "---"
echo "📋 Docker 容器日志:"
docker logs rss-agent --tail 10 2>/dev/null || echo -e "${YELLOW}   容器日志不可用${NC}"
echo ""
echo "📋 cpolar 日志 (cpolar.log):"
if [ -f "cpolar.log" ]; then
    tail -n 10 cpolar.log
else
    echo -e "${YELLOW}   cpolar.log 文件不存在${NC}"
fi
echo ""

echo "========================================="
echo "✅ 诊断完成"
echo "========================================="
