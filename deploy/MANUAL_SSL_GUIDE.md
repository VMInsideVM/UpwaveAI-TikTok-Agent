# 📋 手动 SSL 证书配置指南

如果您已经有自己的 SSL 证书文件（非 Let's Encrypt），请按照以下步骤配置。

---

## 📦 前提条件

您需要准备以下文件：

- ✅ `agent.upwaveai.com.pem` - SSL 证书文件（或 `.crt` 格式）
- ✅ `agent.upwaveai.com.key` - SSL 私钥文件

**证书格式说明**:
- `.pem` - PEM 格式（推荐，文本格式）
- `.crt` - 证书格式（也可使用）
- `.key` - 私钥文件

**如果证书是其他格式**，请先转换为 PEM 格式：

```bash
# DER 转 PEM
openssl x509 -inform der -in certificate.cer -out certificate.pem

# PFX 转 PEM（需要密码）
openssl pkcs12 -in certificate.pfx -out certificate.pem -nodes
```

---

## 🚀 配置步骤

### 方式一：使用自动化脚本（推荐）

#### 步骤 1: 上传证书文件到 VPS

**在本地电脑运行**:

```bash
# 上传证书文件到 VPS 的 /tmp/ 目录
scp agent.upwaveai.com.pem root@your_vps_ip:/tmp/
scp agent.upwaveai.com.key root@your_vps_ip:/tmp/

# 或者一起上传
scp agent.upwaveai.com.{pem,key} root@your_vps_ip:/tmp/
```

#### 步骤 2: SSH 连接到 VPS

```bash
ssh root@your_vps_ip
```

#### 步骤 3: 运行配置脚本

```bash
# 进入项目目录
cd /root/UpwaveAI-TikTok-Agent

# 设置脚本执行权限
chmod +x deploy/manual-ssl-setup.sh

# 运行脚本
sudo bash deploy/manual-ssl-setup.sh
```

**脚本会自动执行以下操作**:
1. ✅ 创建 SSL 证书目录 `/etc/nginx/ssl/`
2. ✅ 复制证书文件到正确位置
3. ✅ 设置文件权限（私钥 600，证书 644）
4. ✅ 配置 Nginx HTTPS
5. ✅ 设置 HTTP 自动跳转 HTTPS
6. ✅ 重启 Nginx
7. ✅ 测试 HTTPS 访问

#### 步骤 4: 验证配置

```bash
# 测试 HTTPS 访问
curl -I https://agent.upwaveai.com

# 应该返回 200 OK 或 502（如果后端未启动）

# 查看证书详情
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -text -noout

# 检查证书有效期
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -noout -dates
```

---

### 方式二：手动配置

如果您想手动配置，请按照以下步骤：

#### 1. 上传证书文件

```bash
# 在本地运行
scp agent.upwaveai.com.pem root@your_vps_ip:/tmp/
scp agent.upwaveai.com.key root@your_vps_ip:/tmp/
```

#### 2. 移动证书到正确位置

```bash
# SSH 连接到 VPS
ssh root@your_vps_ip

# 创建 SSL 目录
mkdir -p /etc/nginx/ssl

# 移动证书文件
mv /tmp/agent.upwaveai.com.pem /etc/nginx/ssl/
mv /tmp/agent.upwaveai.com.key /etc/nginx/ssl/

# 设置权限
chmod 644 /etc/nginx/ssl/agent.upwaveai.com.pem
chmod 600 /etc/nginx/ssl/agent.upwaveai.com.key
chown root:root /etc/nginx/ssl/agent.upwaveai.com.{pem,key}
```

#### 3. 编辑 Nginx 配置

```bash
# 备份原配置
cp /etc/nginx/sites-available/agent.upwaveai.com \
   /etc/nginx/sites-available/agent.upwaveai.com.backup

# 编辑配置文件
nano /etc/nginx/sites-available/agent.upwaveai.com
```

**添加以下 HTTPS 配置**:

```nginx
# HTTP 自动跳转到 HTTPS
server {
    listen 80;
    server_name agent.upwaveai.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS 主配置
server {
    listen 443 ssl http2;
    server_name agent.upwaveai.com;

    # SSL 证书配置
    ssl_certificate /etc/nginx/ssl/agent.upwaveai.com.pem;
    ssl_certificate_key /etc/nginx/ssl/agent.upwaveai.com.key;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # 安全头
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 请求体大小限制
    client_max_body_size 100M;

    # 日志
    access_log /var/log/nginx/agent.upwaveai.com.access.log;
    error_log /var/log/nginx/agent.upwaveai.com.error.log;

    # 反向代理配置（与之前相同）
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
        alias /home/upwaveai/UpwaveAI-TikTok-Agent/output/;
        autoindex off;
        expires 1h;
    }
}
```

#### 4. 测试并重启 Nginx

```bash
# 测试配置
nginx -t

# 如果测试通过，重启 Nginx
systemctl restart nginx

# 查看 Nginx 状态
systemctl status nginx
```

---

## ✅ 验证配置

### 1. 测试 HTTP 跳转

```bash
# 应该返回 301 重定向
curl -I http://agent.upwaveai.com
```

### 2. 测试 HTTPS 访问

```bash
# 应该返回 200 OK
curl -I https://agent.upwaveai.com
```

### 3. 浏览器测试

访问 `https://agent.upwaveai.com`，检查：

- ✅ 地址栏显示锁图标
- ✅ 证书信息正确
- ✅ 页面正常加载

### 4. SSL 安全评级测试

访问 [SSL Labs](https://www.ssllabs.com/ssltest/analyze.html?d=agent.upwaveai.com) 检查 SSL 配置评分。

---

## 🔒 证书管理

### 查看证书信息

```bash
# 查看证书详情
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -text -noout

# 查看证书有效期
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -noout -dates

# 查看证书主题
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -noout -subject

# 查看证书指纹
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -noout -fingerprint
```

### 证书续期提醒

**手动证书不会自动续期**，请注意：

1. **设置提醒**: 在证书到期前 30 天提醒续期
2. **续期步骤**:
   - 获取新证书文件
   - 重复上述上传和配置步骤
   - 重启 Nginx

**可选：设置自动检查**

创建定时任务检查证书有效期：

```bash
# 创建检查脚本
cat > /usr/local/bin/check-ssl-expiry.sh <<'EOF'
#!/bin/bash
CERT_FILE="/etc/nginx/ssl/agent.upwaveai.com.pem"
DAYS_BEFORE_EXPIRY=30

# 获取证书到期日期
EXPIRY_DATE=$(openssl x509 -enddate -noout -in $CERT_FILE | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s)
CURRENT_EPOCH=$(date +%s)
DAYS_LEFT=$(( ($EXPIRY_EPOCH - $CURRENT_EPOCH) / 86400 ))

if [ $DAYS_LEFT -lt $DAYS_BEFORE_EXPIRY ]; then
    echo "⚠️  警告: SSL 证书将在 $DAYS_LEFT 天后过期！"
    echo "证书到期日期: $EXPIRY_DATE"
    # 这里可以发送邮件或其他通知
fi
EOF

chmod +x /usr/local/bin/check-ssl-expiry.sh

# 添加定时任务（每天检查）
crontab -e
# 添加以下行：
# 0 9 * * * /usr/local/bin/check-ssl-expiry.sh
```

---

## 🐛 故障排查

### 问题 1: Nginx 启动失败

```bash
# 查看错误日志
tail -50 /var/log/nginx/error.log

# 常见原因：
# - 证书文件路径错误
# - 私钥文件权限错误
# - 证书和私钥不匹配
```

### 问题 2: 证书不匹配

验证证书和私钥是否匹配：

```bash
# 证书的模数
openssl x509 -noout -modulus -in /etc/nginx/ssl/agent.upwaveai.com.pem | openssl md5

# 私钥的模数
openssl rsa -noout -modulus -in /etc/nginx/ssl/agent.upwaveai.com.key | openssl md5

# 两个输出应该相同
```

### 问题 3: 浏览器显示证书错误

**可能原因**:
- 证书链不完整（需要包含中间证书）
- 证书已过期
- 证书域名不匹配

**解决方案**: 确保 `.pem` 文件包含完整证书链：

```bash
# 证书文件应该包含：
# 1. 服务器证书
# 2. 中间证书
# 3. 根证书（可选）

# 合并证书链
cat server.crt intermediate.crt > agent.upwaveai.com.pem
```

---

## 📋 部署检查清单

- [ ] ✅ 证书文件已上传到 VPS
- [ ] ✅ 私钥文件已上传到 VPS
- [ ] ✅ 证书和私钥已移动到 `/etc/nginx/ssl/`
- [ ] ✅ 文件权限正确（证书 644，私钥 600）
- [ ] ✅ Nginx 配置已更新
- [ ] ✅ Nginx 配置测试通过
- [ ] ✅ Nginx 已重启
- [ ] ✅ HTTP 自动跳转 HTTPS
- [ ] ✅ HTTPS 访问正常
- [ ] ✅ 浏览器无证书警告
- [ ] ✅ SSL Labs 测试评分良好
- [ ] ✅ 证书到期提醒已设置

---

## 🎯 快速命令参考

```bash
# 上传证书
scp agent.upwaveai.com.{pem,key} root@your_vps_ip:/tmp/

# 运行配置脚本
sudo bash deploy/manual-ssl-setup.sh

# 测试 HTTPS
curl -I https://agent.upwaveai.com

# 查看证书有效期
openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -noout -dates

# 重启 Nginx
sudo systemctl restart nginx
```

---

**完成！** 🎉

您的网站现在应该可以通过 HTTPS 安全访问了。

如有问题，请参考 [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) 获取更多帮助。
