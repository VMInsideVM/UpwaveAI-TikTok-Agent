# ✅ 部署检查清单

使用此清单确保部署过程顺利完成，避免遗漏关键步骤。

---

## 📋 部署前准备

### VPS 环境检查

- [ ] 服务器系统: Ubuntu 24.04 64位 UEFI版
- [ ] Root 访问权限或 sudo 权限
- [ ] 至少 2GB RAM
- [ ] 至少 20GB 磁盘空间
- [ ] 稳定的网络连接

### 域名配置

- [ ] 域名已注册: `agent.upwaveai.com`
- [ ] DNS A 记录已设置指向服务器 IP
- [ ] DNS 解析已生效（使用 `dig` 验证）
- [ ] 邮箱地址用于 SSL 证书通知

### 准备资料

- [ ] OpenAI API Key（SiliconFlow 或其他）
- [ ] 管理员密码（至少8位，包含字母和数字）
- [ ] 项目代码已准备好上传

---

## 🚀 部署步骤检查

### 第一阶段: 代码上传（5分钟）

- [ ] 项目代码已压缩: `tar -czf upwaveai.tar.gz UpwaveAI-TikTok-Agent/`
- [ ] 代码已上传到服务器: `/root/UpwaveAI-TikTok-Agent/`
- [ ] 文件权限正确
- [ ] 脚本可执行: `chmod +x deploy/*.sh`

### 第二阶段: 自动安装（10分钟）

- [ ] 运行 `install.sh` 脚本
- [ ] 输入 OpenAI API Key
- [ ] 设置管理员密码
- [ ] 安装过程无错误
- [ ] 所有依赖已安装:
  - [ ] Python 3.12
  - [ ] Nginx
  - [ ] Chromium
  - [ ] Supervisor
  - [ ] Xvfb

### 第三阶段: 服务验证（5分钟）

- [ ] 检查 Supervisor 服务状态:
  ```bash
  sudo supervisorctl status
  ```
  - [ ] chatbot-api: RUNNING
  - [ ] playwright-api: RUNNING
  - [ ] chrome-cdp: RUNNING
  - [ ] xvfb: RUNNING

- [ ] 检查端口监听:
  ```bash
  sudo netstat -tlnp | grep -E '8000|8001|9224'
  ```
  - [ ] 8001 端口: chatbot-api
  - [ ] 8000 端口: playwright-api
  - [ ] 9224 端口: chrome-cdp

- [ ] 检查 Nginx 配置:
  ```bash
  sudo nginx -t
  ```
  - [ ] 配置测试成功
  - [ ] Nginx 服务运行中

### 第四阶段: SSL 证书配置（3分钟）

- [ ] 域名解析验证通过
- [ ] 运行 `ssl-setup.sh` 脚本
- [ ] SSL 证书申请成功
- [ ] HTTPS 访问正常
- [ ] 证书自动续期已配置

### 第五阶段: 功能测试（5分钟）

- [ ] API 健康检查:
  ```bash
  curl https://agent.upwaveai.com/api/health
  ```
  预期: `{"status":"healthy"}`

- [ ] 浏览器访问测试:
  - [ ] 打开 `https://agent.upwaveai.com`
  - [ ] 聊天界面正常显示
  - [ ] WebSocket 连接成功

- [ ] 管理员登录测试:
  - [ ] 使用 admin 账户登录成功
  - [ ] 可以访问管理后台
  - [ ] 可以生成邀请码

### 第六阶段: 数据库验证（2分钟）

- [ ] 数据库文件已创建: `chatbot.db`
- [ ] 所有表已创建:
  ```bash
  sqlite3 /home/upwaveai/UpwaveAI-TikTok-Agent/chatbot.db ".tables"
  ```
  预期: users, chat_sessions, messages, reports, tasks, invitation_codes, user_usage

- [ ] 管理员账户已创建:
  ```bash
  sqlite3 /home/upwaveai/UpwaveAI-TikTok-Agent/chatbot.db \
    "SELECT username, is_admin FROM users WHERE username='admin';"
  ```

---

## 🔒 安全配置检查

### 防火墙配置

- [ ] UFW 已启用
- [ ] SSH 端口已开放（22 或自定义端口）
- [ ] HTTP 端口已开放（80）
- [ ] HTTPS 端口已开放（443）
- [ ] 其他端口已关闭

### 访问控制

- [ ] 管理员密码已修改为强密码
- [ ] SSH 密钥登录已配置（推荐）
- [ ] Root 登录已禁用（推荐）
- [ ] Fail2Ban 已安装配置（可选）

### 文件权限

- [ ] 项目文件所有者: upwaveai 用户
- [ ] .env 文件权限: 600（仅所有者可读写）
- [ ] 数据库文件权限: 644 或 600
- [ ] 日志目录可写

---

## 📊 监控和日志检查

### 日志文件

- [ ] Supervisor 日志正常:
  - [ ] `/var/log/supervisor/chatbot-api.out.log`
  - [ ] `/var/log/supervisor/chatbot-api.err.log`
  - [ ] `/var/log/supervisor/playwright-api.out.log`
  - [ ] `/var/log/supervisor/playwright-api.err.log`

- [ ] Nginx 日志正常:
  - [ ] `/var/log/nginx/agent.upwaveai.com.access.log`
  - [ ] `/var/log/nginx/agent.upwaveai.com.error.log`

### 监控脚本

- [ ] monitor.sh 脚本可正常运行
- [ ] 系统资源使用率正常（CPU < 80%, 内存 < 80%）

---

## 💾 备份配置检查

### 数据库备份

- [ ] 备份目录已创建: `/home/upwaveai/backups/`
- [ ] 备份脚本已创建: `/home/upwaveai/backup_db.sh`
- [ ] 定时任务已配置:
  ```bash
  crontab -l -u upwaveai
  ```
  预期: `0 2 * * * /home/upwaveai/backup_db.sh`

### 配置文件备份

- [ ] .env 文件已备份到安全位置
- [ ] Nginx 配置已备份
- [ ] Supervisor 配置已备份

---

## 🧪 完整功能测试

### 用户注册流程

- [ ] 管理员生成邀请码成功
- [ ] 使用邀请码注册新用户成功
- [ ] 新用户登录成功
- [ ] 用户配额正确显示

### 聊天功能

- [ ] 发送消息成功
- [ ] Agent 响应正常
- [ ] WebSocket 实时更新
- [ ] 对话历史保存

### 爬虫功能

- [ ] Playwright API 响应正常
- [ ] Chrome CDP 连接成功
- [ ] 可以爬取 TikTok 达人数据
- [ ] 数据保存到 influencer/ 目录

### 报告生成

- [ ] 报告生成任务创建成功
- [ ] 报告队列正常工作
- [ ] 报告生成完成
- [ ] 报告可以下载查看

---

## 📈 性能优化检查（可选）

### 数据库优化

- [ ] 考虑迁移到 PostgreSQL（如果高并发）
- [ ] 数据库索引已优化
- [ ] 定期清理过期数据

### 缓存配置

- [ ] Redis 缓存已配置（可选）
- [ ] 静态文件缓存已启用
- [ ] Nginx 缓存已配置

### 服务配置

- [ ] Gunicorn workers 数量优化（CPU核心数 * 2 + 1）
- [ ] Nginx worker_processes 优化
- [ ] 系统 ulimit 已调整

---

## 📞 故障恢复准备

### 回滚方案

- [ ] 代码回滚方法已知
- [ ] 数据库备份可恢复
- [ ] 配置文件有备份

### 联系方式

- [ ] 技术支持联系方式已记录
- [ ] 紧急联系人已设置
- [ ] 监控告警已配置（可选）

---

## 🎯 部署完成最终确认

### 所有系统检查

- [ ] ✅ 所有服务正常运行
- [ ] ✅ SSL 证书有效
- [ ] ✅ 域名访问正常
- [ ] ✅ API 响应正常
- [ ] ✅ WebSocket 连接正常
- [ ] ✅ 数据库工作正常
- [ ] ✅ 日志输出正常
- [ ] ✅ 备份机制已配置
- [ ] ✅ 安全措施已实施
- [ ] ✅ 文档已更新

### 部署信息记录

```
部署日期: ______________
服务器 IP: ______________
域名: agent.upwaveai.com
管理员账户: admin
管理员密码: ______________ (请妥善保管)
OpenAI API Key: ______________ (请妥善保管)
SSL 证书有效期: ______________
数据库类型: SQLite / PostgreSQL
备份频率: 每天凌晨2点
```

---

## 📚 下一步行动

部署完成后，建议：

1. **测试所有功能** - 确保每个功能都正常工作
2. **设置监控** - 配置 Prometheus + Grafana（可选）
3. **优化性能** - 根据实际使用情况调整配置
4. **编写运维文档** - 记录常见操作和故障处理
5. **培训用户** - 指导用户如何使用系统

---

## ✅ 签署确认

我确认已完成以上所有检查项，系统已成功部署并可投入使用。

签署人: ______________
日期: ______________

---

**祝部署顺利！** 🎉

如有问题，请参考：
- [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - 详细部署指南
- [deploy/README.md](README.md) - 脚本使用说明
- [QUICK_DEPLOY.md](../QUICK_DEPLOY.md) - 快速部署指南
