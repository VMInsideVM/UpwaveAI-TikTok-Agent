#!/bin/bash

echo "=========================================="
echo "🔧 更新主服务器 Nginx 配置"
echo "=========================================="
echo ""

echo "📝 修复内容："
echo "  - 移除 rewrite + break 组合"
echo "  - 使用 proxy_pass 直接指定目标路径"
echo "  - 添加完整的 proxy headers"
echo ""

echo "1️⃣ 备份当前配置..."
cp /etc/nginx/sites-enabled/upwaveai.com /etc/nginx/sites-enabled/upwaveai.com.backup.$(date +%Y%m%d_%H%M%S)
echo "   ✅ 备份完成"
echo ""

echo "2️⃣ 更新配置文件..."
cat > /etc/nginx/sites-enabled/upwaveai.com << 'EOF'
# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name upwaveai.com www.upwaveai.com;

    # 重定向所有 HTTP 请求到 HTTPS
    return 301 https://$host$request_uri;
}

# HTTPS 配置
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name upwaveai.com www.upwaveai.com;

    # SSL 证书配置
    ssl_certificate /etc/nginx/ssl/upwaveai.com.pem;
    ssl_certificate_key /etc/nginx/ssl/upwaveai.com.key;

    # SSL 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # 安全头
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Gzip 压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss application/json application/javascript;

    # ==================== TikTok Agent 反向代理 ====================
    # 静态资源（优先级最高）
    location /agent/static/ {
        proxy_pass http://111.228.61.201:8001/static/;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 静态资源缓存
        expires 1h;
        add_header Cache-Control "public";
    }

    # WebSocket 连接（必须在其他 location 之前）
    location /agent/ws/ {
        proxy_pass http://111.228.61.201:8001/ws/;

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

        # 禁用缓冲
        proxy_buffering off;
    }

    # API 端点
    location /agent/api/ {
        proxy_pass http://111.228.61.201:8001/api/;

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

    # 输出文件访问
    location /agent/output/ {
        proxy_pass http://111.228.61.201:8001/output/;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }


    # Agent 主应用（前端页面）
    location /agent/ {
        proxy_pass http://111.228.61.201:8001/;

        proxy_http_version 1.1;

        # WebSocket 支持
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 600s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;

        # 禁用缓冲（流式响应）
        proxy_buffering off;
    }

    # Agent 精确匹配（处理 /agent 不带斜杠的情况）
    location = /agent {
        return 301 /agent/;
    }
    # ==================== Agent 反向代理结束 ====================

    # 网站根目录
    root /var/www/Upwave-website/dist;
    index index.html;

    # SPA 路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # 原有 API 代理（保持不变）
    location /api {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF
echo "   ✅ 配置文件已更新"
echo ""

echo "3️⃣ 测试 Nginx 配置..."
nginx -t
if [ $? -eq 0 ]; then
    echo "   ✅ 配置测试通过"
    echo ""

    echo "4️⃣ 重载 Nginx..."
    systemctl reload nginx
    echo "   ✅ Nginx 已重载"
    echo ""

    echo "5️⃣ 测试静态资源访问..."
    echo ""

    echo "   测试 logo.png..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://upwaveai.com/agent/static/logo.png)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "   ✅ logo.png - HTTP $HTTP_CODE"
    else
        echo "   ❌ logo.png - HTTP $HTTP_CODE"
    fi

    echo "   测试 alipay_payment.png..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://upwaveai.com/agent/static/alipay_payment.png)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "   ✅ alipay_payment.png - HTTP $HTTP_CODE"
    else
        echo "   ❌ alipay_payment.png - HTTP $HTTP_CODE"
    fi

    echo "   测试 wechat_payment.png..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://upwaveai.com/agent/static/wechat_payment.png)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "   ✅ wechat_payment.png - HTTP $HTTP_CODE"
    else
        echo "   ❌ wechat_payment.png - HTTP $HTTP_CODE"
    fi

    echo ""
    echo "=========================================="
    echo "✅ 更新完成！"
    echo "=========================================="
    echo ""
    echo "💡 下一步："
    echo "   1. 清除浏览器缓存"
    echo "   2. 访问 https://upwaveai.com/agent/"
    echo "   3. 检查图片是否正常显示"
    echo ""
else
    echo "   ❌ 配置测试失败，请检查错误信息"
    echo ""
    echo "恢复备份："
    echo "   cp /etc/nginx/sites-enabled/upwaveai.com.backup.* /etc/nginx/sites-enabled/upwaveai.com"
    exit 1
fi
