#!/bin/bash

echo "=========================================="
echo "🔍 静态资源反向代理诊断工具"
echo "=========================================="
echo ""

echo "1️⃣ 检查静态文件是否存在..."
echo "---"
ls -lh /root/UpwaveAI-TikTok-Agent/static/*.png
echo ""

echo "2️⃣ 测试后端服务器直接访问静态文件..."
echo "---"
echo "测试: http://111.228.61.201:8001/static/logo.png"
curl -I http://111.228.61.201:8001/static/logo.png
echo ""

echo "测试: http://111.228.61.201:8001/static/alipay_payment.png"
curl -I http://111.228.61.201:8001/static/alipay_payment.png
echo ""

echo "测试: http://111.228.61.201:8001/static/wechat_payment.png"
curl -I http://111.228.61.201:8001/static/wechat_payment.png
echo ""

echo "3️⃣ 测试主服务器反向代理访问..."
echo "---"
echo "测试: https://upwaveai.com/agent/static/logo.png"
curl -I https://upwaveai.com/agent/static/logo.png
echo ""

echo "测试: https://upwaveai.com/agent/static/alipay_payment.png"
curl -I https://upwaveai.com/agent/static/alipay_payment.png
echo ""

echo "4️⃣ 检查 Nginx 配置是否有重复..."
echo "---"
grep -n "location /agent/static/" /etc/nginx/sites-enabled/*
echo ""

echo "5️⃣ 检查 Nginx 错误日志（最近10行）..."
echo "---"
tail -10 /var/log/nginx/error.log
echo ""

echo "=========================================="
echo "✅ 诊断完成！"
echo "=========================================="
