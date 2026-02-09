#!/bin/bash
# RSS Agent 快速测试命令

echo "========================================="
echo "🚀 RSS Agent 快速测试"
echo "========================================="
echo ""

# 1. 测试本地服务
echo "1️⃣ 测试本地服务 (36000)..."
curl -s http://localhost:36000/ && echo " ✅" || echo " ❌"
echo ""

# 2. 测试公网访问
echo "2️⃣ 测试公网访问..."
curl -s https://ttrssbot.cpolar.cn/ && echo " ✅" || echo " ❌"
echo ""

# 3. 测试 Webhook
echo "3️⃣ 测试 Webhook URL 验证..."
curl -s -X POST https://ttrssbot.cpolar.cn/api/lark/event \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test_123"}' && echo " ✅" || echo " ❌"
echo ""

echo "========================================="
echo "📋 配置信息"
echo "========================================="
echo "本地服务: http://localhost:36000"
echo "公网 URL: https://ttrssbot.cpolar.cn"
echo "Webhook: https://ttrssbot.cpolar.cn/api/lark/event"
echo ""
echo "详细测试请运行: ./diagnostic_test.sh"
echo "========================================="
