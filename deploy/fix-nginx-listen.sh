#!/bin/bash

# ============================================
# 修复 Nginx 监听地址配置
# ============================================

set -e

echo "🔧 检查并修复 Nginx 监听地址配置..."
echo ""

# 检查当前监听状态
echo "======================================"
echo "1️⃣  当前 Nginx 监听状态"
echo "======================================"
sudo netstat -tlnp | grep nginx
echo ""

# 检查配置文件中的 listen 指令
echo "======================================"
echo "2️⃣  当前配置文件中的 listen 指令"
echo "======================================"
grep -n "listen" /etc/nginx/sites-available/agent.upwaveai.com || echo "未找到 listen 指令"
echo ""

# 备份配置
echo "======================================"
echo "3️⃣  备份当前配置"
echo "======================================"
sudo cp /etc/nginx/sites-available/agent.upwaveai.com \
       /etc/nginx/sites-available/agent.upwaveai.com.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ 备份完成"
echo ""

# 修复配置（确保监听所有接口）
echo "======================================"
echo "4️⃣  更新 Nginx 配置"
echo "======================================"

cat > /etc/nginx/sites-available/agent.upwaveai.com <<'NGINXCONF'
# HTTP 自动跳转到 HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name agent.upwaveai.com;

    # 重定向所有 HTTP 请求到 HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS 主配置
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
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
        alias /root/UpwaveAI-TikTok-Agent/output/;
        autoindex off;
        expires 1h;
    }
}
NGINXCONF

echo "✅ 配置已更新"
echo ""

# 测试配置
echo "======================================"
echo "5️⃣  测试 Nginx 配置"
echo "======================================"
sudo nginx -t
echo ""

# 重启 Nginx
echo "======================================"
echo "6️⃣  重启 Nginx"
echo "======================================"
sudo systemctl restart nginx
echo "✅ Nginx 已重启"
echo ""

# 检查新的监听状态
echo "======================================"
echo "7️⃣  检查新的监听状态"
echo "======================================"
sudo netstat -tlnp | grep nginx
echo ""

# 测试访问
echo "======================================"
echo "8️⃣  测试访问"
echo "======================================"
echo ""
echo "【测试 HTTP】"
curl -I http://localhost
echo ""
echo "【测试 HTTPS】"
curl -k -I https://localhost
echo ""

echo "======================================"
echo "✅ 修复完成！"
echo "======================================"
echo ""
echo "📋 现在应该监听在："
echo "   - 0.0.0.0:80  (所有 IPv4 接口)"
echo "   - [::]:80     (所有 IPv6 接口)"
echo "   - 0.0.0.0:443 (所有 IPv4 接口)"
echo "   - [::]:443    (所有 IPv6 接口)"
echo ""
echo "🌐 请从外部测试访问："
echo "   https://agent.upwaveai.com"
echo ""
