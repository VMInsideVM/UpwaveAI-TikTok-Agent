#!/bin/bash

# ============================================
# 一键停止所有服务
# ============================================

echo "🛑 停止所有服务..."
echo ""

# 停止 screen 会话
echo "停止 Playwright API..."
screen -S playwright -X quit 2>/dev/null && echo "✅ Playwright API 已停止" || echo "ℹ️  Playwright API 未运行"

echo "停止 Chatbot API..."
screen -S chatbot -X quit 2>/dev/null && echo "✅ Chatbot API 已停止" || echo "ℹ️  Chatbot API 未运行"

# 清理可能残留的进程
echo ""
echo "🧹 清理残留进程..."
pkill -f "playwright_api.py" 2>/dev/null && echo "✅ 清理了 playwright_api 进程" || true
pkill -f "start_chatbot.py" 2>/dev/null && echo "✅ 清理了 chatbot 进程" || true
pkill -f "chatbot_api.py" 2>/dev/null && echo "✅ 清理了 chatbot_api 进程" || true

# 等待进程完全停止
sleep 2

# 检查端口是否已释放
echo ""
echo "======================================"
echo "📊 端口状态检查"
echo "======================================"
echo ""
echo "端口 8000 (Playwright API):"
if netstat -tlnp 2>/dev/null | grep :8000 > /dev/null; then
    echo "⚠️  仍在使用"
    netstat -tlnp | grep :8000
else
    echo "✅ 已释放"
fi

echo ""
echo "端口 8001 (Chatbot API):"
if netstat -tlnp 2>/dev/null | grep :8001 > /dev/null; then
    echo "⚠️  仍在使用"
    netstat -tlnp | grep :8001
else
    echo "✅ 已释放"
fi

echo ""
echo "🎉 所有服务已停止！"
echo ""
