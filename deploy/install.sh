#!/bin/bash

# UpwaveAI TikTok Agent - 自动部署脚本
# 适用于 Ubuntu 24.04 64位 UEFI版

set -e  # 遇到错误立即退出

echo "🚀 开始部署 UpwaveAI TikTok Agent..."

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    echo "使用命令: sudo bash install.sh"
    exit 1
fi

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量
DOMAIN="agent.upwaveai.com"
DEPLOY_USER="upwaveai"
DEPLOY_DIR="/home/$DEPLOY_USER/UpwaveAI-TikTok-Agent"
EMAIL="admin@upwaveai.com"  # 用于 Let's Encrypt

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  UpwaveAI TikTok Agent 部署脚本  ${NC}"
echo -e "${GREEN}====================================${NC}"
echo ""
echo "域名: $DOMAIN"
echo "部署用户: $DEPLOY_USER"
echo "部署目录: $DEPLOY_DIR"
echo ""
read -p "是否继续部署？(y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 部署已取消"
    exit 1
fi

# 1. 更新系统
echo -e "${YELLOW}[1/10] 更新系统...${NC}"
apt update && apt upgrade -y

# 2. 安装基础依赖
echo -e "${YELLOW}[2/10] 安装基础依赖...${NC}"
apt install -y git curl wget vim htop ufw \
    python3 python3-pip python3-venv \
    nginx supervisor \
    chromium-browser xvfb \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libatspi2.0-0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2

# 3. 创建部署用户
echo -e "${YELLOW}[3/10] 创建部署用户 $DEPLOY_USER...${NC}"
if id "$DEPLOY_USER" &>/dev/null; then
    echo "用户 $DEPLOY_USER 已存在，跳过创建"
else
    adduser --disabled-password --gecos "" $DEPLOY_USER
    echo "✅ 用户 $DEPLOY_USER 创建成功"
fi

# 4. 克隆或更新项目代码
echo -e "${YELLOW}[4/10] 准备项目代码...${NC}"
if [ -d "$DEPLOY_DIR" ]; then
    echo "项目目录已存在，跳过克隆"
else
    echo "请手动上传项目代码到 $DEPLOY_DIR"
    echo "或提供 Git 仓库地址（留空跳过）:"
    read -r GIT_REPO
    if [ -n "$GIT_REPO" ]; then
        su - $DEPLOY_USER -c "git clone $GIT_REPO $DEPLOY_DIR"
    else
        echo "⚠️  请手动上传代码后继续"
        read -p "代码已上传，按回车继续..."
    fi
fi

# 5. 设置 Python 环境
echo -e "${YELLOW}[5/10] 配置 Python 虚拟环境...${NC}"
su - $DEPLOY_USER -c "cd $DEPLOY_DIR && python3 -m venv .venv"
su - $DEPLOY_USER -c "cd $DEPLOY_DIR && source .venv/bin/activate && pip install --upgrade pip"
su - $DEPLOY_USER -c "cd $DEPLOY_DIR && source .venv/bin/activate && pip install -r requirements.txt"
su - $DEPLOY_USER -c "cd $DEPLOY_DIR && source .venv/bin/activate && pip install gunicorn uvicorn[standard]"
su - $DEPLOY_USER -c "cd $DEPLOY_DIR && source .venv/bin/activate && playwright install chromium"

# 6. 配置环境变量
echo -e "${YELLOW}[6/10] 配置环境变量...${NC}"
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    echo "请输入以下配置信息："
    read -p "OpenAI API Key: " OPENAI_KEY
    read -p "Admin Password: " -s ADMIN_PASS
    echo

    # 生成随机 SECRET_KEY
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")

    cat > $DEPLOY_DIR/.env <<EOF
# LLM API 配置
OPENAI_API_KEY="$OPENAI_KEY"
OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
OPENAI_MODEL="Qwen/Qwen3-VL-30B-A3B-Instruct"

# JWT 密钥
SECRET_KEY="$SECRET_KEY"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# 数据库配置
DATABASE_URL="sqlite:///./chatbot.db"

# 管理员账户
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="$ADMIN_PASS"
ADMIN_EMAIL="$EMAIL"

# 服务端口
CHATBOT_PORT=8001
PLAYWRIGHT_PORT=8000
CHROME_CDP_PORT=9224

# 生产环境
ENVIRONMENT="production"
EOF
    chown $DEPLOY_USER:$DEPLOY_USER $DEPLOY_DIR/.env
    chmod 600 $DEPLOY_DIR/.env
    echo "✅ 环境变量配置完成"
else
    echo "⚠️  .env 文件已存在，跳过创建"
fi

# 7. 配置 Supervisor
echo -e "${YELLOW}[7/10] 配置 Supervisor 进程管理...${NC}"

# Xvfb 服务
cat > /etc/supervisor/conf.d/xvfb.conf <<EOF
[program:xvfb]
command=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
autostart=true
autorestart=true
user=$DEPLOY_USER
stderr_logfile=/var/log/supervisor/xvfb.err.log
stdout_logfile=/var/log/supervisor/xvfb.out.log
EOF

# Chrome CDP 服务
cat > /etc/supervisor/conf.d/chrome-cdp.conf <<EOF
[program:chrome-cdp]
command=/usr/bin/chromium-browser --headless --no-sandbox --disable-gpu --remote-debugging-port=9224 --disable-dev-shm-usage --disable-setuid-sandbox
directory=$DEPLOY_DIR
user=$DEPLOY_USER
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/chrome-cdp.err.log
stdout_logfile=/var/log/supervisor/chrome-cdp.out.log
environment=DISPLAY=":99"
EOF

# Playwright API 服务
cat > /etc/supervisor/conf.d/playwright-api.conf <<EOF
[program:playwright-api]
command=$DEPLOY_DIR/.venv/bin/python playwright_api.py
directory=$DEPLOY_DIR
user=$DEPLOY_USER
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/playwright-api.err.log
stdout_logfile=/var/log/supervisor/playwright-api.out.log
environment=PATH="$DEPLOY_DIR/.venv/bin"
EOF

# Chatbot API 服务
cat > /etc/supervisor/conf.d/chatbot-api.conf <<EOF
[program:chatbot-api]
command=$DEPLOY_DIR/.venv/bin/gunicorn chatbot_api:app --bind 127.0.0.1:8001 --workers 4 --worker-class uvicorn.workers.UvicornWorker --timeout 600 --access-logfile /var/log/supervisor/chatbot-api.access.log --error-logfile /var/log/supervisor/chatbot-api.error.log --log-level info
directory=$DEPLOY_DIR
user=$DEPLOY_USER
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/chatbot-api.err.log
stdout_logfile=/var/log/supervisor/chatbot-api.out.log
environment=PATH="$DEPLOY_DIR/.venv/bin"
EOF

# 重载 Supervisor
supervisorctl reread
supervisorctl update

# 8. 配置 Nginx
echo -e "${YELLOW}[8/10] 配置 Nginx 反向代理...${NC}"
cat > /etc/nginx/sites-available/$DOMAIN <<'NGINXCONF'
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    client_max_body_size 100M;

    access_log /var/log/nginx/DOMAIN_PLACEHOLDER.access.log;
    error_log /var/log/nginx/DOMAIN_PLACEHOLDER.error.log;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    location /output/ {
        alias DEPLOY_DIR_PLACEHOLDER/output/;
        autoindex off;
        expires 1h;
    }
}
NGINXCONF

# 替换占位符
sed -i "s|DOMAIN_PLACEHOLDER|$DOMAIN|g" /etc/nginx/sites-available/$DOMAIN
sed -i "s|DEPLOY_DIR_PLACEHOLDER|$DEPLOY_DIR|g" /etc/nginx/sites-available/$DOMAIN

# 启用站点
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 测试 Nginx 配置
nginx -t

# 重启 Nginx
systemctl restart nginx

# 9. 配置防火墙
echo -e "${YELLOW}[9/10] 配置防火墙...${NC}"
ufw --force enable
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw status

# 10. 初始化数据库
echo -e "${YELLOW}[10/10] 初始化数据库...${NC}"
su - $DEPLOY_USER -c "cd $DEPLOY_DIR && source .venv/bin/activate && python -c \"
from database.connection import init_db, create_admin_user
init_db()
create_admin_user()
print('✅ 数据库初始化完成')
\""

# 启动所有服务
echo -e "${YELLOW}启动所有服务...${NC}"
supervisorctl start all

# 显示服务状态
echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}  部署完成！  ${NC}"
echo -e "${GREEN}====================================${NC}"
echo ""
echo "📊 服务状态:"
supervisorctl status
echo ""
echo "🌐 访问地址: http://$DOMAIN"
echo ""
echo "⚠️  下一步操作:"
echo "1. 安装 SSL 证书："
echo "   sudo apt install certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d $DOMAIN"
echo ""
echo "2. 测试服务："
echo "   curl http://$DOMAIN/api/health"
echo ""
echo "3. 查看日志："
echo "   sudo tail -f /var/log/supervisor/chatbot-api.out.log"
echo ""
echo -e "${GREEN}祝使用愉快！🎉${NC}"
