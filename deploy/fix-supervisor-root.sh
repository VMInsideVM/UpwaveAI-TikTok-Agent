#!/bin/bash

# 修复 Supervisor 配置为 root 用户
# 适用于直接使用 root 部署的情况

set -e

echo "🔧 修复 Supervisor 配置（使用 root 用户）..."

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    exit 1
fi

# 修改项目路径为 root 用户目录
DEPLOY_DIR="/root/UpwaveAI-TikTok-Agent"

echo "📂 项目目录: $DEPLOY_DIR"

# 1. 修复 Xvfb 配置
echo "📝 修复 Xvfb 配置..."
cat > /etc/supervisor/conf.d/xvfb.conf <<EOF
[program:xvfb]
command=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
autostart=true
autorestart=true
user=root
stderr_logfile=/var/log/supervisor/xvfb.err.log
stdout_logfile=/var/log/supervisor/xvfb.out.log
EOF

# 2. 修复 Chrome CDP 配置
echo "📝 修复 Chrome CDP 配置..."
cat > /etc/supervisor/conf.d/chrome-cdp.conf <<EOF
[program:chrome-cdp]
command=/usr/bin/chromium-browser --headless --no-sandbox --disable-gpu --remote-debugging-port=9224 --disable-dev-shm-usage --disable-setuid-sandbox
directory=$DEPLOY_DIR
user=root
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/chrome-cdp.err.log
stdout_logfile=/var/log/supervisor/chrome-cdp.out.log
environment=DISPLAY=":99"
EOF

# 3. 修复 Playwright API 配置
echo "📝 修复 Playwright API 配置..."
cat > /etc/supervisor/conf.d/playwright-api.conf <<EOF
[program:playwright-api]
command=$DEPLOY_DIR/.venv/bin/python playwright_api.py
directory=$DEPLOY_DIR
user=root
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/playwright-api.err.log
stdout_logfile=/var/log/supervisor/playwright-api.out.log
environment=PATH="$DEPLOY_DIR/.venv/bin"
EOF

# 4. 修复 Chatbot API 配置
echo "📝 修复 Chatbot API 配置..."
cat > /etc/supervisor/conf.d/chatbot-api.conf <<EOF
[program:chatbot-api]
command=$DEPLOY_DIR/.venv/bin/gunicorn chatbot_api:app --bind 127.0.0.1:8001 --workers 4 --worker-class uvicorn.workers.UvicornWorker --timeout 600 --access-logfile /var/log/supervisor/chatbot-api.access.log --error-logfile /var/log/supervisor/chatbot-api.error.log --log-level info
directory=$DEPLOY_DIR
user=root
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/chatbot-api.err.log
stdout_logfile=/var/log/supervisor/chatbot-api.out.log
environment=PATH="$DEPLOY_DIR/.venv/bin"
EOF

# 5. 重新加载配置
echo "🔄 重新加载 Supervisor 配置..."
supervisorctl reread
supervisorctl update

# 6. 启动所有服务
echo "▶️  启动所有服务..."
supervisorctl start all

# 7. 查看状态
echo ""
echo "📊 服务状态:"
supervisorctl status

echo ""
echo "✅ 配置修复完成！"
echo ""
echo "💡 提示:"
echo "  - 所有服务现在以 root 用户运行"
echo "  - 项目目录: $DEPLOY_DIR"
echo "  - 查看日志: sudo tail -f /var/log/supervisor/chatbot-api.out.log"
