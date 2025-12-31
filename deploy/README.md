# 🚀 部署脚本说明

本目录包含自动化部署和维护脚本，用于在 Ubuntu 24.04 VPS 上快速部署 UpwaveAI TikTok Agent。

## 📋 脚本列表

### 1. install.sh - 自动部署脚本

**功能**: 一键安装所有依赖和配置服务

**使用方法**:

```bash
# 1. 上传脚本到服务器
scp deploy/install.sh root@your_vps_ip:/root/

# 2. 连接到服务器
ssh root@your_vps_ip

# 3. 运行安装脚本
chmod +x install.sh
sudo bash install.sh
```

**脚本执行内容**:
- ✅ 更新系统
- ✅ 安装所有依赖（Python, Nginx, Chromium 等）
- ✅ 创建部署用户
- ✅ 配置 Python 虚拟环境
- ✅ 生成 .env 配置文件
- ✅ 配置 Supervisor 进程管理
- ✅ 配置 Nginx 反向代理
- ✅ 配置防火墙
- ✅ 初始化数据库

---

### 2. ssl-setup.sh - SSL 证书配置脚本

**功能**: 自动申请 Let's Encrypt SSL 证书并配置 HTTPS

**使用方法**:

```bash
# 前提: install.sh 已执行完成

# 1. 确保域名已指向服务器 IP
dig agent.upwaveai.com

# 2. 运行 SSL 配置脚本
chmod +x deploy/ssl-setup.sh
sudo bash deploy/ssl-setup.sh
```

**脚本执行内容**:
- ✅ 检查域名解析
- ✅ 安装 Certbot
- ✅ 申请 SSL 证书
- ✅ 配置 Nginx HTTPS
- ✅ 配置证书自动续期
- ✅ 测试 HTTPS 访问

---

### 3. update.sh - 项目更新脚本

**功能**: 更新代码并重启服务

**使用方法**:

```bash
# 当需要更新代码时运行
sudo bash deploy/update.sh
```

**脚本执行内容**:
- ✅ 停止服务
- ✅ 备份数据库
- ✅ 更新代码（从 Git 拉取）
- ✅ 更新 Python 依赖
- ✅ 清理缓存
- ✅ 数据库迁移（如果有）
- ✅ 重启服务
- ✅ 测试服务状态

---

### 4. monitor.sh - 服务监控脚本

**功能**: 显示服务状态、系统资源和日志

**使用方法**:

```bash
# 查看服务监控面板
sudo bash deploy/monitor.sh
```

**显示内容**:
- 📊 服务状态（Supervisor）
- 💻 系统资源（CPU、内存、磁盘）
- 💾 数据库信息（大小、统计）
- 🌐 Nginx 状态
- 📝 最近错误日志
- 🔍 最近访问日志

---

## 🎯 快速部署流程

### 方式 A: 使用自动脚本（推荐）

```bash
# 1. 将整个项目上传到服务器
scp -r UpwaveAI-TikTok-Agent root@your_vps_ip:/tmp/

# 2. 连接到服务器
ssh root@your_vps_ip

# 3. 移动项目到正确位置
mv /tmp/UpwaveAI-TikTok-Agent /root/

# 4. 运行安装脚本
cd /root/UpwaveAI-TikTok-Agent
chmod +x deploy/*.sh
sudo bash deploy/install.sh

# 5. 配置 SSL 证书
sudo bash deploy/ssl-setup.sh

# 6. 访问网站
# https://agent.upwaveai.com
```

### 方式 B: 手动部署

参考 `DEPLOYMENT_GUIDE.md` 详细步骤。

---

## 📝 常用命令

### 服务管理

```bash
# 查看所有服务状态
sudo supervisorctl status

# 重启单个服务
sudo supervisorctl restart chatbot-api

# 重启所有服务
sudo supervisorctl restart all

# 查看服务日志
sudo tail -f /var/log/supervisor/chatbot-api.out.log
```

### Nginx 管理

```bash
# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx

# 查看访问日志
sudo tail -f /var/log/nginx/agent.upwaveai.com.access.log

# 查看错误日志
sudo tail -f /var/log/nginx/agent.upwaveai.com.error.log
```

### 数据库管理

```bash
# 进入项目目录
cd /home/upwaveai/UpwaveAI-TikTok-Agent

# 备份数据库
cp chatbot.db backups/chatbot_backup_$(date +%Y%m%d_%H%M%S).db

# 查看数据库
sqlite3 chatbot.db

# 查看表
.tables

# 查看用户
SELECT * FROM users;
```

### 证书管理

```bash
# 查看证书状态
sudo certbot certificates

# 手动续期证书
sudo certbot renew

# 测试续期
sudo certbot renew --dry-run
```

---

## 🐛 故障排查

### 问题 1: 服务无法启动

```bash
# 查看错误日志
sudo tail -100 /var/log/supervisor/chatbot-api.err.log

# 检查端口占用
sudo netstat -tlnp | grep 8001

# 手动启动测试
cd /home/upwaveai/UpwaveAI-TikTok-Agent
source .venv/bin/activate
python chatbot_api.py
```

### 问题 2: SSL 证书申请失败

```bash
# 检查域名解析
dig agent.upwaveai.com

# 检查防火墙
sudo ufw status

# 查看 Certbot 日志
sudo tail -100 /var/log/letsencrypt/letsencrypt.log
```

### 问题 3: 数据库锁定

```bash
# 检查数据库进程
sudo lsof chatbot.db

# 重启服务
sudo supervisorctl restart chatbot-api
```

---

## 📊 性能优化建议

### 1. 使用 PostgreSQL 替代 SQLite

```bash
# 安装 PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# 创建数据库
sudo -u postgres psql
CREATE DATABASE upwaveai_db;
CREATE USER upwaveai_user WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE upwaveai_db TO upwaveai_user;

# 修改 .env
DATABASE_URL="postgresql://upwaveai_user:your-password@localhost/upwaveai_db"
```

### 2. 增加 Gunicorn Workers

```bash
# 编辑 Supervisor 配置
sudo nano /etc/supervisor/conf.d/chatbot-api.conf

# 修改 workers 参数（建议设置为 CPU 核心数 * 2 + 1）
--workers 8
```

### 3. 配置 Redis 缓存

```bash
# 安装 Redis
sudo apt install -y redis-server

# 修改代码使用 Redis 缓存会话
```

---

## 🔒 安全建议

1. **修改默认端口**: SSH 端口从 22 改为其他端口
2. **使用 SSH 密钥**: 禁用密码登录
3. **配置 Fail2Ban**: 防止暴力破解
4. **定期更新系统**: `sudo apt update && sudo apt upgrade`
5. **监控日志**: 定期检查异常访问
6. **数据库备份**: 每天自动备份

---

## 📞 技术支持

如遇到问题，请：

1. 查看服务日志
2. 运行 `monitor.sh` 检查状态
3. 参考 `DEPLOYMENT_GUIDE.md` 详细文档
4. 提交 GitHub Issue

---

**祝部署顺利！** 🎉
