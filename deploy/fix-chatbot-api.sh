#!/bin/bash

# ============================================
# 修复 Chatbot API 启动问题
# ============================================

set -e

echo "🔧 修复 Chatbot API 启动问题..."
echo ""

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    exit 1
fi

DEPLOY_DIR="/root/UpwaveAI-TikTok-Agent"

# 1. 停止 chatbot-api
echo "1️⃣  停止 chatbot-api 服务..."
supervisorctl stop chatbot-api
sleep 3
echo "✅ 已停止"
echo ""

# 2. 清理端口 8001
echo "2️⃣  清理端口 8001..."
if sudo lsof -i :8001 > /dev/null 2>&1; then
    echo "   发现端口 8001 被占用，强制释放..."
    sudo fuser -k 8001/tcp || true
    sleep 2
    echo "✅ 端口 8001 已释放"
else
    echo "✅ 端口 8001 未被占用"
fi
echo ""

# 3. 清理可能的 gunicorn 进程
echo "3️⃣  清理可能的僵尸 Gunicorn 进程..."
if pgrep -f "gunicorn.*chatbot_api" > /dev/null; then
    echo "   发现 Gunicorn 进程，正在终止..."
    pkill -9 -f "gunicorn.*chatbot_api" || true
    sleep 1
    echo "✅ 已清理"
else
    echo "✅ 无僵尸进程"
fi
echo ""

# 4. 更新 Supervisor 配置（减少 workers，避免并发问题）
echo "4️⃣  更新 Chatbot API Supervisor 配置..."
cat > /etc/supervisor/conf.d/chatbot-api.conf <<EOF
[program:chatbot-api]
command=$DEPLOY_DIR/.venv/bin/gunicorn chatbot_api:app --bind 127.0.0.1:8001 --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 600 --graceful-timeout 30 --keep-alive 5 --max-requests 1000 --max-requests-jitter 100 --access-logfile /var/log/supervisor/chatbot-api.access.log --error-logfile /var/log/supervisor/chatbot-api.error.log --log-level info
directory=$DEPLOY_DIR
user=root
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/chatbot-api.err.log
stdout_logfile=/var/log/supervisor/chatbot-api.out.log
environment=PATH="$DEPLOY_DIR/.venv/bin"
stopwaitsecs=10
EOF

echo "✅ 配置已更新（workers: 4 → 2）"
echo ""

# 5. 重新加载 Supervisor 配置
echo "5️⃣  重新加载 Supervisor 配置..."
supervisorctl reread
supervisorctl update
echo "✅ 配置已重新加载"
echo ""

# 6. 启动 chatbot-api
echo "6️⃣  启动 chatbot-api 服务..."
supervisorctl start chatbot-api
echo "✅ 服务已启动"
echo ""

# 7. 等待服务启动
echo "7️⃣  等待服务完全启动（15秒）..."
for i in {1..15}; do
    echo -n "."
    sleep 1
done
echo ""
echo ""

# 8. 检查服务状态
echo "8️⃣  检查服务状态..."
echo ""
supervisorctl status chatbot-api
echo ""

# 9. 检查端口监听
echo "9️⃣  检查端口 8001 监听状态..."
if sudo netstat -tlnp | grep 8001 > /dev/null; then
    echo "✅ 端口 8001 正常监听"
    sudo netstat -tlnp | grep 8001
else
    echo "❌ 端口 8001 未监听"
    echo ""
    echo "📋 查看错误日志："
    echo "   sudo tail -30 /var/log/supervisor/chatbot-api.err.log"
fi
echo ""

# 10. 测试健康检查
echo "🔟 测试 Chatbot API 健康检查..."
sleep 2

HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/health 2>/dev/null || echo "000")

if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo "✅ Chatbot API 健康检查通过！"
    echo ""
    curl -s http://127.0.0.1:8001/api/health | python3 -m json.tool 2>/dev/null || echo ""
else
    echo "❌ Chatbot API 健康检查失败（HTTP $HEALTH_RESPONSE）"
    echo ""
    echo "📋 最近的错误日志："
    sudo tail -20 /var/log/supervisor/chatbot-api.err.log
fi
echo ""

# 11. 测试 HTTPS 访问
echo "1️⃣1️⃣  测试 HTTPS 访问..."
HTTPS_RESPONSE=$(curl -k -s -o /dev/null -w "%{http_code}" https://agent.upwaveai.com/api/health 2>/dev/null || echo "000")

if [ "$HTTPS_RESPONSE" == "200" ]; then
    echo "✅ HTTPS 访问正常！"
    echo ""
    echo "🎉 所有服务部署成功！"
    echo ""
    echo "🌐 访问地址:"
    echo "   - HTTPS: https://agent.upwaveai.com"
    echo "   - 本地: http://127.0.0.1:8001"
else
    echo "⚠️  HTTPS 访问返回: $HTTPS_RESPONSE"
    if [ "$HEALTH_RESPONSE" == "200" ]; then
        echo ""
        echo "💡 本地服务正常，可能是 Nginx 配置问题"
        echo "   检查 Nginx 配置: sudo nginx -t"
        echo "   查看 Nginx 日志: sudo tail /var/log/nginx/error.log"
    fi
fi
echo ""

# 12. 最终状态总结
echo "======================================"
echo "📊 最终状态总结"
echo "======================================"
echo ""
supervisorctl status
echo ""

if [ "$HEALTH_RESPONSE" == "200" ]; then
    echo "🎉 Chatbot API 运行正常！"
    echo ""
    echo "✅ 下一步:"
    echo "   1. 上传 SSL 证书到 /tmp/ (如果还没上传)"
    echo "   2. 配置 SSL: sudo bash deploy/manual-ssl-setup.sh"
    echo "   3. 或者使用已有配置: sudo bash deploy/update-nginx-ssl.sh"
else
    echo "⚠️  Chatbot API 仍有问题"
    echo ""
    echo "🔍 调试建议:"
    echo "   1. 查看完整错误日志:"
    echo "      sudo tail -50 /var/log/supervisor/chatbot-api.err.log"
    echo ""
    echo "   2. 手动启动测试:"
    echo "      sudo supervisorctl stop chatbot-api"
    echo "      cd $DEPLOY_DIR"
    echo "      source .venv/bin/activate"
    echo "      gunicorn chatbot_api:app --bind 127.0.0.1:8001 --workers 1 --worker-class uvicorn.workers.UvicornWorker"
fi
echo ""
