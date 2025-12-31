#!/bin/bash

# ============================================
# 一键启动所有服务（使用 Screen）
# ============================================

PROJECT_DIR="/root/UpwaveAI-TikTok-Agent"

echo "🚀 启动 UpwaveAI-TikTok-Agent 服务..."
echo ""

# 检查是否安装了 screen
if ! command -v screen &> /dev/null; then
    echo "📦 安装 screen..."
    sudo apt update && sudo apt install screen -y
fi

# 停止已有的 screen 会话
echo "🧹 清理旧的 screen 会话..."
screen -S playwright -X quit 2>/dev/null || true
screen -S chatbot -X quit 2>/dev/null || true
sleep 2

# 启动 Playwright API
echo "1️⃣ 启动 Playwright API..."
screen -dmS playwright bash -c "
    cd $PROJECT_DIR
    source .venv/bin/activate
    python playwright_api.py
"
sleep 3

# 检查 Playwright API 是否启动成功
if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "✅ Playwright API 启动成功 (端口 8000)"
else
    echo "⚠️  Playwright API 可能需要更多时间启动..."
fi
echo ""

# 启动 Chatbot API
echo "2️⃣ 启动 Chatbot API..."
screen -dmS chatbot bash -c "
    cd $PROJECT_DIR
    source .venv/bin/activate
    python start_chatbot.py
"
sleep 5

# 检查 Chatbot API 是否启动成功
if curl -s http://127.0.0.1:8001/api/health > /dev/null 2>&1; then
    echo "✅ Chatbot API 启动成功 (端口 8001)"
else
    echo "⚠️  Chatbot API 可能需要更多时间启动..."
fi
echo ""

# 显示运行中的服务
echo "======================================"
echo "📊 运行中的服务"
echo "======================================"
screen -ls
echo ""

echo "======================================"
echo "💡 常用命令"
echo "======================================"
echo ""
echo "查看所有 screen 会话:"
echo "  screen -ls"
echo ""
echo "进入 Playwright API 控制台:"
echo "  screen -r playwright"
echo ""
echo "进入 Chatbot API 控制台:"
echo "  screen -r chatbot"
echo ""
echo "退出 screen (服务继续运行):"
echo "  按 Ctrl+A 然后按 D"
echo ""
echo "停止所有服务:"
echo "  bash stop_all_services.sh"
echo ""
echo "🎉 所有服务已启动！"
echo ""
