#!/bin/bash

# ============================================
# Playwright API 端口 8000 冲突一键修复脚本
# ============================================

set -e

echo "🔧 开始修复 Playwright API 端口 8000 冲突问题..."
echo ""

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    echo "   sudo bash deploy/fix-port-8000.sh"
    exit 1
fi

# 1. 停止所有 Supervisor 服务
echo "1️⃣  停止所有 Supervisor 服务..."
supervisorctl stop all
echo "✅ 已停止所有服务"
echo ""

# 2. 等待进程完全停止
echo "2️⃣  等待进程完全停止（5秒）..."
sleep 5
echo ""

# 3. 强制释放端口 8000
echo "3️⃣  强制释放端口 8000..."
if sudo lsof -i :8000 > /dev/null 2>&1; then
    echo "   发现端口 8000 被占用，强制释放..."
    sudo fuser -k 8000/tcp || true
    sleep 2
    echo "✅ 端口 8000 已释放"
else
    echo "✅ 端口 8000 未被占用"
fi
echo ""

# 4. 检查并清理僵尸进程
echo "4️⃣  清理可能的僵尸进程..."
if pgrep -f "playwright_api.py" > /dev/null; then
    echo "   发现 playwright_api 进程，正在终止..."
    pkill -9 -f "playwright_api.py" || true
    sleep 1
    echo "✅ 已清理"
else
    echo "✅ 无僵尸进程"
fi
echo ""

# 5. 检查 Chrome CDP 状态
echo "5️⃣  检查 Chrome CDP (端口 9224)..."
if sudo netstat -tlnp | grep 9224 > /dev/null; then
    echo "✅ Chrome CDP 正常运行"
else
    echo "⚠️  Chrome CDP 未运行，将在 Supervisor 启动时自动启动"
fi
echo ""

# 6. 检查 Xvfb 状态
echo "6️⃣  检查 Xvfb (虚拟显示)..."
if pgrep Xvfb > /dev/null; then
    echo "✅ Xvfb 正常运行"
else
    echo "⚠️  Xvfb 未运行，将在 Supervisor 启动时自动启动"
fi
echo ""

# 7. 重新加载 Supervisor 配置
echo "7️⃣  重新加载 Supervisor 配置..."
supervisorctl reread
supervisorctl update
echo "✅ 配置已重新加载"
echo ""

# 8. 按顺序启动服务
echo "8️⃣  按顺序启动服务..."
echo ""

echo "   启动 Xvfb..."
supervisorctl start xvfb
sleep 2

echo "   启动 Chrome CDP..."
supervisorctl start chrome-cdp
sleep 3

echo "   启动 Playwright API..."
supervisorctl start playwright-api
sleep 5

echo "   启动 Chatbot API..."
supervisorctl start chatbot-api
sleep 2

echo "✅ 所有服务已启动"
echo ""

# 9. 检查服务状态
echo "9️⃣  检查服务状态..."
echo ""
supervisorctl status
echo ""

# 10. 验证端口监听
echo "🔟 验证端口监听..."
echo ""

echo "【检查端口 8000 - Playwright API】"
if sudo netstat -tlnp | grep 8000 > /dev/null; then
    echo "✅ 端口 8000 正常监听"
    sudo netstat -tlnp | grep 8000
else
    echo "❌ 端口 8000 未监听"
fi
echo ""

echo "【检查端口 8001 - Chatbot API】"
if sudo netstat -tlnp | grep 8001 > /dev/null; then
    echo "✅ 端口 8001 正常监听"
    sudo netstat -tlnp | grep 8001
else
    echo "❌ 端口 8001 未监听"
fi
echo ""

echo "【检查端口 9224 - Chrome CDP】"
if sudo netstat -tlnp | grep 9224 > /dev/null; then
    echo "✅ 端口 9224 正常监听"
    sudo netstat -tlnp | grep 9224
else
    echo "❌ 端口 9224 未监听"
fi
echo ""

# 11. 测试 Playwright API 健康检查
echo "1️⃣1️⃣  测试 Playwright API 健康检查..."
sleep 3  # 等待服务完全启动

HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health || echo "000")

if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo "✅ Playwright API 健康检查通过！"
    curl -s http://127.0.0.1:8000/health | python3 -m json.tool || echo ""
else
    echo "❌ Playwright API 健康检查失败（HTTP $HEALTH_RESPONSE）"
    echo ""
    echo "📋 查看错误日志："
    echo "   sudo tail -20 /var/log/supervisor/playwright-api.err.log"
fi
echo ""

# 12. 最终状态总结
echo "======================================"
echo "📊 修复完成！最终状态："
echo "======================================"
echo ""
supervisorctl status
echo ""

if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo "🎉 所有服务运行正常！"
    echo ""
    echo "✅ 下一步："
    echo "   1. 运行数据库初始化: python start_chatbot.py --init-only"
    echo "   2. 上传 SSL 证书到 /tmp/"
    echo "   3. 运行 SSL 配置: sudo bash deploy/manual-ssl-setup.sh"
else
    echo "⚠️  Playwright API 仍有问题"
    echo ""
    echo "🔍 调试建议："
    echo "   1. 查看完整错误日志："
    echo "      sudo tail -50 /var/log/supervisor/playwright-api.err.log"
    echo ""
    echo "   2. 手动启动测试："
    echo "      sudo supervisorctl stop playwright-api"
    echo "      cd /root/UpwaveAI-TikTok-Agent"
    echo "      source .venv/bin/activate"
    echo "      python playwright_api.py"
    echo ""
    echo "   3. 检查 Chrome CDP 是否正常："
    echo "      curl http://127.0.0.1:9224/json/version"
fi
echo ""
