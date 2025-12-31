# ⚡ SSL 证书快速配置指南

如果您已有 `agent.upwaveai.com.key` 和 `agent.upwaveai.com.pem` 文件，按以下步骤操作。

---

## 🚀 三步配置

### 步骤 1: 上传证书文件

**在本地电脑运行**:

```bash
# 上传证书文件到 VPS
scp agent.upwaveai.com.pem root@your_vps_ip:/tmp/
scp agent.upwaveai.com.key root@your_vps_ip:/tmp/

# 或一起上传
scp agent.upwaveai.com.{pem,key} root@your_vps_ip:/tmp/
```

### 步骤 2: SSH 连接并运行配置脚本

```bash
# 连接到 VPS
ssh root@your_vps_ip

# 进入项目目录
cd /root/UpwaveAI-TikTok-Agent

# 运行 SSL 配置脚本
chmod +x deploy/manual-ssl-setup.sh
sudo bash deploy/manual-ssl-setup.sh
```

### 步骤 3: 验证配置

```bash
# 测试 HTTPS 访问
curl -I https://agent.upwaveai.com

# 应该返回 200 OK 或 502（如果后端未启动）

# 查看证书有效期
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -noout -dates
```

---

## ✅ 完成！

现在您的网站可以通过 HTTPS 访问了： `https://agent.upwaveai.com`

---

## 📝 证书文件说明

- **agent.upwaveai.com.pem** - SSL 证书文件（包含服务器证书和中间证书链）
- **agent.upwaveai.com.key** - SSL 私钥文件（需要严格保密）

---

## 🔧 如果遇到问题

### 问题 1: 脚本提示找不到证书文件

**原因**: 证书文件未上传到 `/tmp/` 目录

**解决**: 重新检查文件名和上传路径
```bash
# 检查文件是否存在
ls -l /tmp/agent.upwaveai.com.*
```

### 问题 2: Nginx 测试失败

**原因**: 证书和私钥不匹配

**解决**: 验证证书和私钥
```bash
# 证书的模数
openssl x509 -noout -modulus -in /tmp/agent.upwaveai.com.pem | openssl md5

# 私钥的模数
openssl rsa -noout -modulus -in /tmp/agent.upwaveai.com.key | openssl md5

# 两个输出应该相同
```

### 问题 3: 浏览器显示证书错误

**原因**: 证书链不完整

**解决**: 确保 `.pem` 文件包含完整证书链（服务器证书 + 中间证书）

---

## 📚 详细文档

- **完整手动 SSL 指南**: [deploy/MANUAL_SSL_GUIDE.md](deploy/MANUAL_SSL_GUIDE.md)
- **部署指南**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **快速部署**: [QUICK_DEPLOY.md](QUICK_DEPLOY.md)

---

**祝配置顺利！** 🎉
