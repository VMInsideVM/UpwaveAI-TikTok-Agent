# ⚡ 快速部署指南

> 在 Ubuntu 24.04 VPS 上 5 分钟内完成部署

## 📋 前提条件

- ✅ Ubuntu 24.04 64位服务器
- ✅ Root 访问权限
- ✅ 域名 `agent.upwaveai.com` 已指向服务器 IP
- ✅ OpenAI API Key（SiliconFlow）

---

## 🚀 三步部署

### 步骤 1: 上传项目到服务器

**在本地电脑运行**:

```bash
# 压缩项目
tar -czf upwaveai.tar.gz UpwaveAI-TikTok-Agent/

# 上传到服务器
scp upwaveai.tar.gz root@your_vps_ip:/root/

# 或使用 rsync（更快）
rsync -avz --progress UpwaveAI-TikTok-Agent/ root@your_vps_ip:/root/UpwaveAI-TikTok-Agent/
```

### 步骤 2: 运行自动安装脚本

**连接到服务器**:

```bash
ssh root@your_vps_ip
```

**解压并安装**:

```bash
# 如果使用压缩包
tar -xzf upwaveai.tar.gz
cd UpwaveAI-TikTok-Agent

# 设置脚本执行权限
chmod +x deploy/*.sh

# 运行安装脚本（约 5-10 分钟）
sudo bash deploy/install.sh
```

**安装过程中会提示输入**:
- OpenAI API Key: `your-api-key`
- Admin Password: `设置管理员密码（至少8位）`

### 步骤 3: 配置 SSL 证书

```bash
# 确保域名已解析
dig agent.upwaveai.com

# 运行 SSL 配置脚本（约 1-2 分钟）
sudo bash deploy/ssl-setup.sh
```

---

## ✅ 验证部署

### 1. 检查服务状态

```bash
sudo supervisorctl status
```

**预期输出**:
```
chatbot-api      RUNNING   pid 12345, uptime 0:01:00
chrome-cdp       RUNNING   pid 12346, uptime 0:01:00
playwright-api   RUNNING   pid 12347, uptime 0:01:00
xvfb            RUNNING   pid 12348, uptime 0:01:00
```

### 2. 测试 API

```bash
# 健康检查
curl https://agent.upwaveai.com/api/health

# 预期输出: {"status":"healthy"}
```

### 3. 浏览器访问

打开 `https://agent.upwaveai.com`，应该看到聊天界面。

---

## 🎯 首次登录

1. 访问 `https://agent.upwaveai.com`
2. 使用管理员账户登录:
   - 用户名: `admin`
   - 密码: `安装时设置的密码`

3. 生成邀请码:
   - 进入管理后台
   - 点击"生成邀请码"
   - 复制邀请码给用户注册

---

## 📊 常用命令速查

### 服务管理

```bash
# 查看状态
sudo supervisorctl status

# 重启所有服务
sudo supervisorctl restart all

# 查看实时日志
sudo tail -f /var/log/supervisor/chatbot-api.out.log
```

### 更新代码

```bash
# 一键更新
sudo bash deploy/update.sh
```

### 监控面板

```bash
# 查看服务监控
sudo bash deploy/monitor.sh
```

### 数据库备份

```bash
# 手动备份
cp /home/upwaveai/UpwaveAI-TikTok-Agent/chatbot.db \
   /home/upwaveai/backups/chatbot_backup_$(date +%Y%m%d).db
```

---

## 🐛 常见问题

### 问题: 502 Bad Gateway

**解决**:
```bash
# 查看服务状态
sudo supervisorctl status

# 查看错误日志
sudo tail -100 /var/log/supervisor/chatbot-api.err.log

# 重启服务
sudo supervisorctl restart all
```

### 问题: SSL 证书申请失败

**解决**:
```bash
# 检查域名解析
dig agent.upwaveai.com

# 检查 80/443 端口开放
sudo ufw status

# 查看 Certbot 日志
sudo tail -100 /var/log/letsencrypt/letsencrypt.log
```

### 问题: WebSocket 连接失败

**解决**:
```bash
# 检查 Nginx 配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

---

## 🔒 安全提醒

部署完成后立即执行：

1. **修改管理员密码**（如果使用了简单密码）
2. **配置防火墙** - 只开放必要端口（22, 80, 443）
3. **启用 Fail2Ban** - 防止暴力破解
4. **设置数据库定时备份**
5. **禁用 Root SSH 登录**（可选）

---

## 📚 完整文档

- **详细部署指南**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **部署脚本说明**: [deploy/README.md](deploy/README.md)
- **项目使用文档**: [CLAUDE.md](CLAUDE.md)

---

## 🎉 部署完成检查清单

- [ ] 所有 Supervisor 服务状态为 RUNNING
- [ ] SSL 证书已配置，HTTPS 访问正常
- [ ] 浏览器可以访问聊天界面
- [ ] API 健康检查返回正常
- [ ] WebSocket 连接正常
- [ ] 管理员账户可以登录
- [ ] 防火墙已配置
- [ ] 数据库备份已设置

---

**总部署时间**: 约 10-15 分钟

**祝部署顺利！** 🚀

---

## 💡 下一步

部署完成后，您可以：

1. **创建测试用户**: 生成邀请码并注册
2. **测试对话流程**: 搜索 TikTok 达人
3. **生成分析报告**: 使用报告功能
4. **配置监控**: 设置 Prometheus + Grafana
5. **优化性能**: 迁移到 PostgreSQL

需要帮助？请参考 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 获取详细信息。
