#!/bin/bash

# 更新现有 Nginx 配置添加 HTTPS 支持
# 适用于已有 HTTP 配置的情况

set -e

DOMAIN="agent.upwaveai.com"
NGINX_CONF="/etc/nginx/sites-available/$DOMAIN"
SSL_CERT="/etc/nginx/ssl/agent.upwaveai.com.pem"
SSL_KEY="/etc/nginx/ssl/agent.upwaveai.com.key"

echo "🔄 更新 Nginx 配置添加 HTTPS 支持..."

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    exit 1
fi

# 检查证书文件是否存在
if [ ! -f "$SSL_CERT" ]; then
    echo "❌ 证书文件不存在: $SSL_CERT"
    echo "请先运行: sudo bash deploy/manual-ssl-setup.sh"
    exit 1
fi

if [ ! -f "$SSL_KEY" ]; then
    echo "❌ 私钥文件不存在: $SSL_KEY"
    echo "请先运行: sudo bash deploy/manual-ssl-setup.sh"
    exit 1
fi

# 备份原配置
echo "💾 备份原配置..."
cp $NGINX_CONF ${NGINX_CONF}.backup.$(date +%Y%m%d_%H%M%S)

# 替换配置文件
echo "📝 更新配置文件..."
cat > $NGINX_CONF <<'NGINXCONF'
# HTTP 自动跳转到 HTTPS
server {
    listen 80;
    server_name agent.upwaveai.com;

    # 重定向所有 HTTP 请求到 HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS 主配置
server {
    listen 443 ssl http2;
    server_name agent.upwaveai.com;

    # SSL 证书配置
    ssl_certificate /etc/nginx/ssl/agent.upwaveai.com.pem;
    ssl_certificate_key /etc/nginx/ssl/agent.upwaveai.com.key;

    # SSL 协议配置
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
    access_log /var/log/nginx/agent.upwaveai.com.access.log;
    error_log /var/log/nginx/agent.upwaveai.com.error.log;

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

# 测试配置
echo "✅ 测试 Nginx 配置..."
nginx -t

if [ $? -ne 0 ]; then
    echo "❌ Nginx 配置测试失败！"
    echo "正在恢复备份..."
    mv ${NGINX_CONF}.backup.* $NGINX_CONF
    exit 1
fi

# 重启 Nginx
echo "🔄 重启 Nginx..."
systemctl restart nginx

# 测试 HTTPS
echo "🌐 测试 HTTPS 访问..."
sleep 2
HTTP_CODE=$(curl -k -s -o /dev/null -w "%{http_code}" https://agent.upwaveai.com/api/health)

if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ HTTPS 配置成功！"
else
    echo "⚠️  HTTPS 访问返回: $HTTP_CODE"
fi

echo ""
echo "🎉 配置更新完成！"
echo ""
echo "📋 更改内容:"
echo "  ✅ HTTP (80端口) → 自动跳转到 HTTPS"
echo "  ✅ HTTPS (443端口) → 主服务"
echo "  ✅ SSL 证书: $SSL_CERT"
echo ""
echo "🌐 访问地址: https://agent.upwaveai.com"
echo ""
echo "💡 备份文件: ${NGINX_CONF}.backup.*"
echo "   如需回滚: mv ${NGINX_CONF}.backup.* $NGINX_CONF && nginx -t && systemctl restart nginx"
