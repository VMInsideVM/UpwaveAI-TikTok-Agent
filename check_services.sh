#!/bin/bash

# ============================================
# 检查服务状态
# ============================================

echo "🔍 检查服务状态..."
echo ""

# 检查 screen 会话
echo "======================================"
echo "📺 Screen 会话"
echo "======================================"
screen -ls
echo ""

# 检查端口
echo "======================================"
echo "🔌 端口监听状态"
echo "======================================"
echo ""
echo "端口 8000 (Playwright API):"
if netstat -tlnp 2>/dev/null | grep :8000 > /dev/null; then
    echo "✅ 正在监听"
    netstat -tlnp | grep :8000
else
    echo "❌ 未监听"
fi

echo ""
echo "端口 8001 (Chatbot API):"
if netstat -tlnp 2>/dev/null | grep :8001 > /dev/null; then
    echo "✅ 正在监听"
    netstat -tlnp | grep :8001
else
    echo "❌ 未监听"
fi

echo ""
echo "端口 9224 (Chrome CDP):"
if netstat -tlnp 2>/dev/null | grep :9224 > /dev/null; then
    echo "✅ 正在监听"
    netstat -tlnp | grep :9224
else
    echo "❌ 未监听 (需要手动启动 Chrome)"
fi

# 健康检查
echo ""
echo "======================================"
echo "🏥 服务健康检查"
echo "======================================"
echo ""
echo "Playwright API:"
PLAYWRIGHT_STATUS=$(curl -s http://127.0.0.1:8000/health 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ 正常"
    echo "$PLAYWRIGHT_STATUS" | python3 -m json.tool 2>/dev/null || echo "$PLAYWRIGHT_STATUS"
else
    echo "❌ 无法访问"
fi

echo ""
echo "Chatbot API:"
CHATBOT_STATUS=$(curl -s http://127.0.0.1:8001/api/health 2>&1)
if [ $? -eq 0 ]; then
    echo "✅ 正常"
    echo "$CHATBOT_STATUS" | python3 -m json.tool 2>/dev/null || echo "$CHATBOT_STATUS"
else
    echo "❌ 无法访问"
fi

echo ""
echo "======================================"
echo "💡 提示"
echo "======================================"
echo ""
echo "查看 Playwright API 日志:"
echo "  screen -r playwright"
echo ""
echo "查看 Chatbot API 日志:"
echo "  screen -r chatbot"
echo ""
