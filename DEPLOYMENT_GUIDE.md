# Ubuntu 24.04 VPS 部署指南

## 📋 部署概览

- **服务器系统**: Ubuntu 24.04 64位 UEFI版
- **域名**: agent.upwaveai.com
- **SSL证书**: 手动配置（Let's Encrypt推荐）
- **架构**: Nginx反向代理 + Gunicorn + FastAPI

---

## 🎯 部署架构

```
外网请求 (https://agent.upwaveai.com)
    ↓
Nginx (443端口, SSL终止)
    ↓
Gunicorn (127.0.0.1:8001, chatbot_api.py)
    ↓
Playwright API (127.0.0.1:8000, playwright_api.py)
    ↓
Chrome/Chromium (CDP 端口 9224)
```

---

## 📦 第一步：准备 VPS 环境

### 1.1 连接到 VPS

```bash
ssh root@your_vps_ip
```

### 1.2 更新系统

```bash
apt update && apt upgrade -y
```

### 1.3 安装基础依赖

```bash
# 安装必要工具
apt install -y git curl wget vim nano htop ufw

# 安装 Python 3.12（Ubuntu 24.04 默认版本）
apt install -y python3 python3-pip python3-venv

# 安装 Nginx
apt install -y nginx

# 安装 Supervisor（进程管理）
apt install -y supervisor
```

### 1.4 安装 Chromium（用于 Playwright）

```bash
# 安装 Chromium 浏览器
apt install -y chromium-browser

# 验证安装
chromium-browser --version
# 应该输出: Chromium 130.x.x.x

# 安装 Playwright 系统依赖
apt install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2
```

---

## 🚀 第二步：部署项目代码

### 2.1 创建部署用户（推荐，安全性）

```bash
# 创建专用用户
adduser upwaveai
# 设置密码并填写信息

# 添加到 sudo 组（如果需要）
usermod -aG sudo upwaveai

# 切换到新用户
su - upwaveai
```

### 2.2 克隆项目到服务器

```bash
# 进入用户主目录
cd ~

# 克隆项目（使用 Git）
git clone https://github.com/yourusername/UpwaveAI-TikTok-Agent.git

# 如果是私有仓库，使用 SSH 密钥或 Personal Access Token
# git clone https://<token>@github.com/yourusername/UpwaveAI-TikTok-Agent.git

# 或者手动上传代码（使用 SCP）
# 在本地电脑运行：
# scp -r C:\Users\Hank\PycharmProjects\UpwaveAI-TikTok-Agent upwaveai@your_vps_ip:~/
```

### 2.3 进入项目目录

```bash
cd ~/UpwaveAI-TikTok-Agent
```

---

## 🐍 第三步：配置 Python 环境

### 3.1 创建虚拟环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境
deactivate


# 验证 Python 版本
python --version
# 应输出: Python 3.12.x
```

### 3.2 安装 Python 依赖

```bash
# 升级 pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 安装 Gunicorn（生产环境 WSGI 服务器）
pip install gunicorn uvicorn[standard]

# 安装 Playwright 浏览器
playwright install chromium
```

### 3.3 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env  # 如果有的话

# 或者创建新的 .env 文件
nano .env
```

**编辑 `.env` 文件内容**:

```env
# LLM API 配置
OPENAI_API_KEY="your-api-key"
OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
OPENAI_MODEL="Qwen/Qwen3-VL-30B-A3B-Instruct"

# JWT 密钥（生成随机字符串）
SECRET_KEY="your-very-long-random-secret-key-here-64-chars-min"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# 数据库配置
DATABASE_URL="sqlite:///./chatbot.db"

# 管理员账户（首次启动时创建）
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="ChangeThisPassword123!"
ADMIN_EMAIL="admin@upwaveai.com"

# 服务端口（内部使用）
CHATBOT_PORT=8001
PLAYWRIGHT_PORT=8000
CHROME_CDP_PORT=9224

# 生产环境标识
ENVIRONMENT="production"
```

**生成安全的 SECRET_KEY**:

```bash
# 在 Python 中生成随机密钥
python -c "import secrets; print(secrets.token_urlsafe(64))"
# 复制输出的字符串到 .env 文件的 SECRET_KEY
```

---

## 🌐 第四步：配置 Nginx 反向代理

### 4.1 创建 Nginx 配置文件

```bash
# 切换回 root 用户（或使用 sudo）
exit  # 如果在 upwaveai 用户下

# 创建配置文件
sudo nano /etc/nginx/sites-available/agent.upwaveai.com
```

**基础配置（HTTP，先测试再加 SSL）**:

```nginx
# HTTP 配置（临时用于测试）
server {
    listen 80;
    server_name agent.upwaveai.com;

    # 请求体大小限制（用于上传报告）
    client_max_body_size 100M;

    # 访问日志
    access_log /var/log/nginx/agent.upwaveai.com.access.log;
    error_log /var/log/nginx/agent.upwaveai.com.error.log;

    # 静态文件（前端页面）
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;

        # WebSocket 支持
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 代理头
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置（对话可能较长）
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }

    # API 端点
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # API 超时
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # WebSocket 连接
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;

        # WebSocket 必需
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 超时（保持连接）
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # 输出文件访问（报告、图表）
    location /output/ {
        alias /home/upwaveai/UpwaveAI-TikTok-Agent/output/;
        autoindex off;  # 禁止目录浏览
        expires 1h;     # 缓存 1 小时
    }
}
```

### 4.2 启用站点配置

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/agent.upwaveai.com /etc/nginx/sites-enabled/

# 删除默认配置（可选）
sudo rm /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 如果显示 "test is successful"，重启 Nginx
sudo systemctl restart nginx
```

### 4.3 配置防火墙

```bash
# 启用 UFW 防火墙
sudo ufw enable

# 允许 SSH（重要！否则会断开连接）
sudo ufw allow 22/tcp

# 允许 HTTP 和 HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 查看规则
sudo ufw status
```

---

## 🔒 第五步：配置 SSL 证书

您可以选择以下两种方式之一：

### 方式 A：使用 Let's Encrypt 自动申请（免费）

#### 5.1 安装 Certbot

```bash
# 安装 Certbot 和 Nginx 插件
sudo apt install -y certbot python3-certbot-nginx
```

### 5.2 获取 SSL 证书

```bash
# 确保域名已指向服务器 IP
# 使用 dig 或 nslookup 验证：
dig agent.upwaveai.com

# 申请证书
sudo certbot --nginx -d agent.upwaveai.com

# 按提示操作：
# 1. 输入邮箱（用于证书到期提醒）
# 2. 同意服务条款
# 3. 选择是否重定向 HTTP 到 HTTPS（推荐选择 2: Redirect）
```

**Certbot 会自动修改 Nginx 配置，添加以下内容**:

```nginx
server {
    listen 443 ssl http2;
    server_name agent.upwaveai.com;

    # SSL 证书路径（Certbot 自动添加）
    ssl_certificate /etc/letsencrypt/live/agent.upwaveai.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/agent.upwaveai.com/privkey.pem;

    # SSL 配置（Certbot 自动添加）
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # ... 其他配置保持不变 ...
}

# HTTP 自动跳转到 HTTPS
server {
    listen 80;
    server_name agent.upwaveai.com;

    return 301 https://$server_name$request_uri;
}
```

#### 5.3 测试 SSL 配置

```bash
# 重启 Nginx
sudo nginx -t && sudo systemctl restart nginx

# 访问测试
curl -I https://agent.upwaveai.com
# 应返回 200 OK 或 502（如果后端服务未启动）
```

#### 5.4 设置证书自动续期

```bash
# Certbot 会自动创建续期定时任务
# 验证定时任务
sudo systemctl status certbot.timer

# 手动测试续期（不会真正续期）
sudo certbot renew --dry-run
```

---

### 方式 B：使用自己的 SSL 证书（手动上传）

**如果您已经有自己的 SSL 证书文件**（如从阿里云、腾讯云购买的证书），请使用此方式。

#### 1. 上传证书文件到 VPS

**在本地电脑运行**:

```bash
# 上传证书文件到 VPS 的 /tmp/ 目录
scp agent.upwaveai.com.pem root@your_vps_ip:/tmp/
scp agent.upwaveai.com.key root@your_vps_ip:/tmp/
```

#### 2. 运行配置脚本

**SSH 连接到 VPS 后运行**:

```bash
# 进入项目目录
cd /root/UpwaveAI-TikTok-Agent

# 设置脚本执行权限
chmod +x deploy/manual-ssl-setup.sh

# 运行脚本
sudo bash deploy/manual-ssl-setup.sh
```

**脚本会自动**:
- ✅ 创建 SSL 证书目录 `/etc/nginx/ssl/`
- ✅ 复制证书文件到正确位置
- ✅ 设置文件权限（私钥 600，证书 644）
- ✅ 配置 Nginx HTTPS
- ✅ 设置 HTTP 自动跳转 HTTPS
- ✅ 重启 Nginx
- ✅ 测试 HTTPS 访问

#### 3. 验证配置

```bash
# 测试 HTTPS 访问
curl -I https://agent.upwaveai.com

# 查看证书有效期
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -noout -dates
```

**详细手动 SSL 配置说明**: 请参考 [deploy/MANUAL_SSL_GUIDE.md](deploy/MANUAL_SSL_GUIDE.md)

---

## 🔧 第六步：配置 Supervisor 进程管理

### 6.1 创建 Chrome CDP 服务配置

```bash
sudo nano /etc/supervisor/conf.d/chrome-cdp.conf
```

**内容**:

```ini
[program:chrome-cdp]
command=/usr/bin/chromium-browser --headless --no-sandbox --disable-gpu --remote-debugging-port=9224 --disable-dev-shm-usage --disable-setuid-sandbox
directory=/home/upwaveai/UpwaveAI-TikTok-Agent
user=upwaveai
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/chrome-cdp.err.log
stdout_logfile=/var/log/supervisor/chrome-cdp.out.log
environment=DISPLAY=":99"

[program:xvfb]
command=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
autostart=true
autorestart=true
user=upwaveai
stderr_logfile=/var/log/supervisor/xvfb.err.log
stdout_logfile=/var/log/supervisor/xvfb.out.log
```

**安装 Xvfb（虚拟显示）**:

```bash
sudo apt install -y xvfb
```

### 6.2 创建 Playwright API 服务配置

```bash
sudo nano /etc/supervisor/conf.d/playwright-api.conf
```

**内容**:

```ini
[program:playwright-api]
command=/home/upwaveai/UpwaveAI-TikTok-Agent/.venv/bin/python playwright_api.py
directory=/home/upwaveai/UpwaveAI-TikTok-Agent
user=upwaveai
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/playwright-api.err.log
stdout_logfile=/var/log/supervisor/playwright-api.out.log
environment=PATH="/home/upwaveai/UpwaveAI-TikTok-Agent/.venv/bin"
```

### 6.3 创建 Chatbot API 服务配置

```bash
sudo nano /etc/supervisor/conf.d/chatbot-api.conf
```

**内容**:

```ini
[program:chatbot-api]
command=/home/upwaveai/UpwaveAI-TikTok-Agent/.venv/bin/gunicorn chatbot_api:app \
    --bind 127.0.0.1:8001 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 600 \
    --access-logfile /var/log/supervisor/chatbot-api.access.log \
    --error-logfile /var/log/supervisor/chatbot-api.error.log \
    --log-level info
directory=/home/upwaveai/UpwaveAI-TikTok-Agent
user=upwaveai
autostart=true
autorestart=true
startretries=3
stderr_logfile=/var/log/supervisor/chatbot-api.err.log
stdout_logfile=/var/log/supervisor/chatbot-api.out.log
environment=PATH="/home/upwaveai/UpwaveAI-TikTok-Agent/.venv/bin"
```

### 6.4 重新加载 Supervisor 配置

```bash
# 创建日志目录（如果不存在）
sudo mkdir -p /var/log/supervisor

# 重新读取配置
sudo supervisorctl reread

# 更新进程
sudo supervisorctl update

# 启动所有服务
sudo supervisorctl start all

# 查看状态
sudo supervisorctl status
```

**预期输出**:

```
chatbot-api                      RUNNING   pid 12345, uptime 0:00:10
chrome-cdp                       RUNNING   pid 12346, uptime 0:00:10
playwright-api                   RUNNING   pid 12347, uptime 0:00:10
xvfb                            RUNNING   pid 12348, uptime 0:00:10
```

---

## ✅ 第七步：初始化数据库

### 7.1 切换到项目用户

```bash
su - upwaveai
cd ~/UpwaveAI-TikTok-Agent
source .venv/bin/activate
```

### 7.2 运行数据库初始化

```bash
# 运行启动脚本（会自动初始化数据库）
python start_chatbot.py --init-only

# 或者手动运行
python -c "
from database.connection import init_db, create_admin_user
init_db()
create_admin_user()
print('✅ 数据库初始化完成')
"
```

### 7.3 验证数据库

```bash
# 检查数据库文件
ls -lh chatbot.db

# 使用 sqlite3 查看表结构
sqlite3 chatbot.db ".tables"
# 应输出: chat_sessions  invitation_codes  messages  reports  tasks  user_usage  users
```

---

## 🧪 第八步：测试部署

### 8.1 检查服务状态

```bash
# 查看所有服务状态
sudo supervisorctl status

# 查看服务日志
sudo tail -f /var/log/supervisor/chatbot-api.out.log
sudo tail -f /var/log/supervisor/playwright-api.out.log
sudo tail -f /var/log/supervisor/chrome-cdp.out.log
```

### 8.2 测试 API 端点

```bash
# 健康检查
curl https://agent.upwaveai.com/api/health

# 预期输出: {"status":"healthy"}

# 测试登录
curl -X POST https://agent.upwaveai.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"ChangeThisPassword123!"}'

# 应返回 access_token 和用户信息
```

### 8.3 测试 WebSocket 连接

在浏览器中打开 Developer Tools Console:

```javascript
const ws = new WebSocket('wss://agent.upwaveai.com/ws/test-session');
ws.onopen = () => console.log('✅ WebSocket 连接成功');
ws.onerror = (error) => console.error('❌ WebSocket 错误:', error);
```

### 8.4 浏览器测试

访问 `https://agent.upwaveai.com`，应该看到聊天界面。

---

## 📊 第九步：监控和维护

### 9.1 查看日志

```bash
# Nginx 日志
sudo tail -f /var/log/nginx/agent.upwaveai.com.access.log
sudo tail -f /var/log/nginx/agent.upwaveai.com.error.log

# Supervisor 日志
sudo tail -f /var/log/supervisor/chatbot-api.out.log
sudo tail -f /var/log/supervisor/playwright-api.err.log

# 系统资源监控
htop
```

### 9.2 重启服务

```bash
# 重启单个服务
sudo supervisorctl restart chatbot-api

# 重启所有服务
sudo supervisorctl restart all

# 重启 Nginx
sudo systemctl restart nginx
```

### 9.3 更新代码

```bash
# 切换到项目用户
su - upwaveai
cd ~/UpwaveAI-TikTok-Agent

# 拉取最新代码
git pull origin main

# 激活虚拟环境
source .venv/bin/activate

# 更新依赖（如果有变化）
pip install -r requirements.txt

# 清理 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# 重启服务
exit  # 回到 root 用户
sudo supervisorctl restart chatbot-api
sudo supervisorctl restart playwright-api
```

### 9.4 数据库备份

```bash
# 创建备份脚本
sudo nano /home/upwaveai/backup_db.sh
```

**备份脚本内容**:

```bash
#!/bin/bash
BACKUP_DIR="/home/upwaveai/backups"
DB_PATH="/home/upwaveai/UpwaveAI-TikTok-Agent/chatbot.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cp $DB_PATH $BACKUP_DIR/chatbot_backup_$DATE.db

# 保留最近 30 天的备份
find $BACKUP_DIR -name "chatbot_backup_*.db" -mtime +30 -delete

echo "✅ 数据库备份完成: chatbot_backup_$DATE.db"
```

```bash
# 设置执行权限
chmod +x /home/upwaveai/backup_db.sh

# 添加定时任务（每天凌晨 2 点备份）
sudo crontab -e -u upwaveai
```

**添加以下行**:

```cron
0 2 * * * /home/upwaveai/backup_db.sh >> /var/log/backup.log 2>&1
```

---

## 🔐 第十步：安全加固

### 10.1 修改管理员密码

首次部署后立即修改：

```bash
curl -X POST https://agent.upwaveai.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"ChangeThisPassword123!"}'

# 获取 access_token 后，调用修改密码 API（需要自己实现）
# 或者直接在数据库中修改
```

### 10.2 配置 Fail2Ban（防止暴力破解）

```bash
# 安装 Fail2Ban
sudo apt install -y fail2ban

# 创建自定义规则
sudo nano /etc/fail2ban/filter.d/nginx-login.conf
```

**内容**:

```ini
[Definition]
failregex = ^<HOST> .* "POST /api/auth/login HTTP.*" 401
ignoreregex =
```

```bash
# 配置 Fail2Ban
sudo nano /etc/fail2ban/jail.local
```

**内容**:

```ini
[nginx-login]
enabled = true
port = http,https
filter = nginx-login
logpath = /var/log/nginx/agent.upwaveai.com.access.log
maxretry = 5
bantime = 3600
findtime = 600
```

```bash
# 重启 Fail2Ban
sudo systemctl restart fail2ban

# 查看状态
sudo fail2ban-client status nginx-login
```

### 10.3 限制 SSH 访问

```bash
# 编辑 SSH 配置
sudo nano /etc/ssh/sshd_config
```

**修改以下项**:

```
# 禁用 root 登录
PermitRootLogin no

# 禁用密码登录（推荐使用 SSH 密钥）
PasswordAuthentication no

# 修改默认端口（可选）
Port 2222
```

```bash
# 重启 SSH 服务
sudo systemctl restart sshd

# 如果修改了端口，记得更新防火墙规则
sudo ufw allow 2222/tcp
sudo ufw delete allow 22/tcp
```

---

## 📋 常见问题排查

### 问题 1: 502 Bad Gateway

**原因**: 后端服务未启动或崩溃

**解决**:

```bash
# 查看服务状态
sudo supervisorctl status

# 查看错误日志
sudo tail -100 /var/log/supervisor/chatbot-api.err.log

# 重启服务
sudo supervisorctl restart chatbot-api
```

### 问题 2: WebSocket 连接失败

**原因**: Nginx 配置缺少 WebSocket 支持

**解决**: 确保 Nginx 配置中包含:

```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

### 问题 3: Chrome CDP 连接失败

**原因**: Chrome 未启动或端口被占用

**解决**:

```bash
# 检查 Chrome 进程
ps aux | grep chromium

# 检查端口占用
netstat -tlnp | grep 9224

# 重启 Chrome 服务
sudo supervisorctl restart chrome-cdp
```

### 问题 4: 数据库锁定错误

**原因**: SQLite 不支持高并发写入

**解决**: 考虑迁移到 PostgreSQL:

```bash
# 安装 PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# 创建数据库
sudo -u postgres psql
CREATE DATABASE upwaveai_db;
CREATE USER upwaveai_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE upwaveai_db TO upwaveai_user;
\q

# 修改 .env
DATABASE_URL="postgresql://upwaveai_user:your-password@localhost/upwaveai_db"

# 重启服务
sudo supervisorctl restart chatbot-api
```

---

## 🎯 部署检查清单

部署完成后，请确认以下所有项：

- [ ] ✅ 域名 DNS 已正确指向服务器 IP
- [ ] ✅ SSL 证书已配置且有效
- [ ] ✅ 所有 Supervisor 服务状态为 RUNNING
- [ ] ✅ Nginx 配置测试通过 (`nginx -t`)
- [ ] ✅ 防火墙规则已配置（80, 443 开放）
- [ ] ✅ 数据库已初始化，管理员账户已创建
- [ ] ✅ 管理员密码已修改为强密码
- [ ] ✅ 浏览器可访问 `https://agent.upwaveai.com`
- [ ] ✅ WebSocket 连接正常
- [ ] ✅ API 健康检查返回正常
- [ ] ✅ 日志备份定时任务已设置
- [ ] ✅ SSL 证书自动续期已配置

---

## 📞 技术支持

如遇到问题，请检查：

1. **Nginx 错误日志**: `/var/log/nginx/agent.upwaveai.com.error.log`
2. **服务错误日志**: `/var/log/supervisor/*.err.log`
3. **系统日志**: `journalctl -xe`

---

## 🎉 部署完成！

现在您可以访问 `https://agent.upwaveai.com` 使用 TikTok 达人推荐系统了！

**下一步**:
1. 登录管理后台生成邀请码
2. 创建测试用户账户
3. 测试完整的对话流程
4. 配置监控告警（如 Prometheus + Grafana）
5. 设置定期数据库备份

---

**祝部署顺利！** 🚀
