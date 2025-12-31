#!/bin/bash

# 手动 SSL 证书配置脚本
# 适用于已有 SSL 证书文件的情况

set -e

# 配置变量
DOMAIN="agent.upwaveai.com"
SSL_DIR="/etc/nginx/ssl"
CERT_FILE="agent.upwaveai.com.pem"  # 证书文件
KEY_FILE="agent.upwaveai.com.key"   # 私钥文件

echo "🔒 开始配置手动上传的 SSL 证书..."

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    echo "使用命令: sudo bash manual-ssl-setup.sh"
    exit 1
fi

# 1. 创建 SSL 证书目录
echo "📁 创建 SSL 证书目录..."
mkdir -p $SSL_DIR
chmod 755 $SSL_DIR

# 2. 检查证书文件是否存在
echo "🔍 检查证书文件..."
if [ ! -f "/tmp/$CERT_FILE" ]; then
    echo "❌ 错误: 未找到证书文件 /tmp/$CERT_FILE"
    echo ""
    echo "请先上传证书文件到 /tmp/ 目录:"
    echo "  scp $CERT_FILE root@your_vps_ip:/tmp/"
    echo "  scp $KEY_FILE root@your_vps_ip:/tmp/"
    exit 1
fi

if [ ! -f "/tmp/$KEY_FILE" ]; then
    echo "❌ 错误: 未找到私钥文件 /tmp/$KEY_FILE"
    echo ""
    echo "请先上传私钥文件到 /tmp/ 目录:"
    echo "  scp $KEY_FILE root@your_vps_ip:/tmp/"
    exit 1
fi

# 3. 复制证书文件到正确位置
echo "📋 复制证书文件..."
cp /tmp/$CERT_FILE $SSL_DIR/$CERT_FILE
cp /tmp/$KEY_FILE $SSL_DIR/$KEY_FILE

# 4. 设置证书文件权限
echo "🔐 设置文件权限..."
chmod 644 $SSL_DIR/$CERT_FILE
chmod 600 $SSL_DIR/$KEY_FILE  # 私钥文件仅 root 可读
chown root:root $SSL_DIR/$CERT_FILE
chown root:root $SSL_DIR/$KEY_FILE

# 5. 备份原 Nginx 配置
echo "💾 备份 Nginx 配置..."
if [ -f "/etc/nginx/sites-available/$DOMAIN" ]; then
    cp /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-available/$DOMAIN.backup.$(date +%Y%m%d_%H%M%S)
fi

# 6. 创建 HTTPS Nginx 配置
echo "⚙️  配置 Nginx HTTPS..."
cat > /etc/nginx/sites-available/$DOMAIN <<'NGINXCONF'
# HTTP 自动跳转到 HTTPS
server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    # 重定向所有 HTTP 请求到 HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS 主配置
server {
    listen 443 ssl http2;
    server_name DOMAIN_PLACEHOLDER;

    # SSL 证书配置
    ssl_certificate SSL_DIR_PLACEHOLDER/CERT_FILE_PLACEHOLDER;
    ssl_certificate_key SSL_DIR_PLACEHOLDER/KEY_FILE_PLACEHOLDER;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
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
    access_log /var/log/nginx/DOMAIN_PLACEHOLDER.access.log;
    error_log /var/log/nginx/DOMAIN_PLACEHOLDER.error.log;

    # 主应用
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

        # 超时设置
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

        # WebSocket 超时
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # 输出文件访问
    location /output/ {
        alias /home/upwaveai/UpwaveAI-TikTok-Agent/output/;
        autoindex off;
        expires 1h;
    }
}
NGINXCONF

# 替换占位符
sed -i "s|DOMAIN_PLACEHOLDER|$DOMAIN|g" /etc/nginx/sites-available/$DOMAIN
sed -i "s|SSL_DIR_PLACEHOLDER|$SSL_DIR|g" /etc/nginx/sites-available/$DOMAIN
sed -i "s|CERT_FILE_PLACEHOLDER|$CERT_FILE|g" /etc/nginx/sites-available/$DOMAIN
sed -i "s|KEY_FILE_PLACEHOLDER|$KEY_FILE|g" /etc/nginx/sites-available/$DOMAIN

# 7. 启用站点配置
echo "🔗 启用站点配置..."
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 8. 测试 Nginx 配置
echo "✅ 测试 Nginx 配置..."
nginx -t

if [ $? -ne 0 ]; then
    echo "❌ Nginx 配置测试失败！"
    echo "请检查配置文件: /etc/nginx/sites-available/$DOMAIN"
    exit 1
fi

# 9. 重启 Nginx
echo "🔄 重启 Nginx..."
systemctl restart nginx

# 10. 测试 HTTPS 访问
echo "🌐 测试 HTTPS 访问..."
sleep 2
HTTP_CODE=$(curl -k -s -o /dev/null -w "%{http_code}" https://$DOMAIN/api/health)

if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ HTTPS 配置成功！"
else
    echo "⚠️  HTTPS 访问返回: $HTTP_CODE"
    echo "请检查后端服务是否正常运行"
fi

# 11. 清理临时文件
echo "🧹 清理临时文件..."
rm -f /tmp/$CERT_FILE
rm -f /tmp/$KEY_FILE

echo ""
echo "🎉 SSL 证书配置完成！"
echo ""
echo "📋 证书信息:"
echo "  证书位置: $SSL_DIR/$CERT_FILE"
echo "  私钥位置: $SSL_DIR/$KEY_FILE"
echo ""
echo "🌐 访问地址: https://$DOMAIN"
echo ""
echo "💡 提示:"
echo "  - 查看证书详情: openssl x509 -in $SSL_DIR/$CERT_FILE -text -noout"
echo "  - 检查证书有效期: openssl x509 -in $SSL_DIR/$CERT_FILE -noout -dates"
echo "  - 测试 SSL 配置: https://www.ssllabs.com/ssltest/analyze.html?d=$DOMAIN"
echo ""
echo "⚠️  证书到期提醒:"
echo "  - 请在证书到期前手动续期"
echo "  - 可设置提醒在到期前 30 天续期"
