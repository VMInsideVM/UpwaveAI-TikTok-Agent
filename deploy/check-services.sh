#!/bin/bash

# ============================================
# 检查所有服务状态
# ============================================

echo "🔍 检查所有服务状态..."
echo ""

# 1. Supervisor 状态
echo "======================================"
echo "1️⃣  Supervisor 服务状态"
echo "======================================"
supervisorctl status
echo ""

# 2. 端口监听情况
echo "======================================"
echo "2️⃣  端口监听情况"
echo "======================================"
echo ""
echo "【端口 8000 - Playwright API】"
sudo netstat -tlnp | grep 8000 || echo "❌ 未监听"
echo ""
echo "【端口 8001 - Chatbot API】"
sudo netstat -tlnp | grep 8001 || echo "❌ 未监听"
echo ""
echo "【端口 9224 - Chrome CDP】"
sudo netstat -tlnp | grep 9224 || echo "❌ 未监听"
echo ""

# 3. 检查 chatbot-api 日志（最近 30 行）
echo "======================================"
echo "3️⃣  Chatbot API 错误日志（最近 30 行）"
echo "======================================"
sudo tail -30 /var/log/supervisor/chatbot-api.err.log
echo ""

# 4. 检查 chatbot-api 输出日志（最近 30 行）
echo "======================================"
echo "4️⃣  Chatbot API 输出日志（最近 30 行）"
echo "======================================"
sudo tail -30 /var/log/supervisor/chatbot-api.out.log
echo ""

# 5. 测试本地端口
echo "======================================"
echo "5️⃣  测试本地服务健康检查"
echo "======================================"
echo ""
echo "【Playwright API (8000)】"
curl -s http://127.0.0.1:8000/health || echo "❌ 无法连接"
echo ""
echo ""
echo "【Chatbot API (8001)】"
curl -s http://127.0.0.1:8001/api/health || echo "❌ 无法连接"
echo ""
