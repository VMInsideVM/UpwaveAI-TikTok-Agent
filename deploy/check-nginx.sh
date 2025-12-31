#!/bin/bash

# ============================================
# 检查 Nginx 配置和状态
# ============================================

echo "🔍 检查 Nginx 配置和状态..."
echo ""

# 1. 检查 Nginx 服务状态
echo "======================================"
echo "1️⃣  Nginx 服务状态"
echo "======================================"
systemctl status nginx --no-pager -l
echo ""

# 2. 检查 Nginx 配置文件
echo "======================================"
echo "2️⃣  检查 Nginx 配置文件"
echo "======================================"
echo ""
echo "【sites-available 目录】"
ls -la /etc/nginx/sites-available/
echo ""
echo "【sites-enabled 目录】"
ls -la /etc/nginx/sites-enabled/
echo ""

# 3. 测试 Nginx 配置
echo "======================================"
echo "3️⃣  测试 Nginx 配置语法"
echo "======================================"
nginx -t
echo ""

# 4. 查看当前生效的配置
echo "======================================"
echo "4️⃣  查看 agent.upwaveai.com 配置"
echo "======================================"
if [ -f "/etc/nginx/sites-available/agent.upwaveai.com" ]; then
    echo "✅ 配置文件存在"
    echo ""
    cat /etc/nginx/sites-available/agent.upwaveai.com
else
    echo "❌ 配置文件不存在: /etc/nginx/sites-available/agent.upwaveai.com"
fi
echo ""

# 5. 检查符号链接
echo "======================================"
echo "5️⃣  检查配置文件是否已启用"
echo "======================================"
if [ -L "/etc/nginx/sites-enabled/agent.upwaveai.com" ]; then
    echo "✅ 配置已启用（符号链接存在）"
    ls -la /etc/nginx/sites-enabled/agent.upwaveai.com
else
    echo "❌ 配置未启用（符号链接不存在）"
    echo ""
    echo "💡 需要创建符号链接："
    echo "   sudo ln -s /etc/nginx/sites-available/agent.upwaveai.com /etc/nginx/sites-enabled/"
fi
echo ""

# 6. 检查端口监听
echo "======================================"
echo "6️⃣  检查 Nginx 端口监听"
echo "======================================"
echo ""
echo "【端口 80 - HTTP】"
sudo netstat -tlnp | grep :80 || echo "❌ 未监听"
echo ""
echo "【端口 443 - HTTPS】"
sudo netstat -tlnp | grep :443 || echo "❌ 未监听"
echo ""

# 7. 检查 SSL 证书
echo "======================================"
echo "7️⃣  检查 SSL 证书文件"
echo "======================================"
if [ -f "/etc/nginx/ssl/agent.upwaveai.com.pem" ]; then
    echo "✅ 证书文件存在: /etc/nginx/ssl/agent.upwaveai.com.pem"
    openssl x509 -in /etc/nginx/ssl/agent.upwaveai.com.pem -noout -dates
else
    echo "❌ 证书文件不存在: /etc/nginx/ssl/agent.upwaveai.com.pem"
fi
echo ""
if [ -f "/etc/nginx/ssl/agent.upwaveai.com.key" ]; then
    echo "✅ 私钥文件存在: /etc/nginx/ssl/agent.upwaveai.com.key"
else
    echo "❌ 私钥文件不存在: /etc/nginx/ssl/agent.upwaveai.com.key"
fi
echo ""

# 8. 查看 Nginx 错误日志
echo "======================================"
echo "8️⃣  Nginx 错误日志（最近 30 行）"
echo "======================================"
sudo tail -30 /var/log/nginx/error.log
echo ""

# 9. 查看 Nginx 访问日志
echo "======================================"
echo "9️⃣  Nginx 访问日志（最近 20 行）"
echo "======================================"
sudo tail -20 /var/log/nginx/access.log
echo ""

# 10. 测试各种访问方式
echo "======================================"
echo "🔟 测试各种访问方式"
echo "======================================"
echo ""

echo "【测试 HTTP】"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://agent.upwaveai.com 2>/dev/null || echo "000")
echo "HTTP 状态码: $HTTP_CODE"
if [ "$HTTP_CODE" == "301" ] || [ "$HTTP_CODE" == "302" ]; then
    echo "✅ HTTP 正确重定向到 HTTPS"
elif [ "$HTTP_CODE" == "200" ]; then
    echo "⚠️  HTTP 返回 200（应该重定向到 HTTPS）"
else
    echo "❌ HTTP 访问失败"
fi
echo ""

echo "【测试 HTTPS】"
HTTPS_CODE=$(curl -k -s -o /dev/null -w "%{http_code}" https://agent.upwaveai.com 2>/dev/null || echo "000")
echo "HTTPS 状态码: $HTTPS_CODE"
if [ "$HTTPS_CODE" == "200" ]; then
    echo "✅ HTTPS 访问正常"
elif [ "$HTTPS_CODE" == "502" ]; then
    echo "❌ 502 Bad Gateway（后端服务问题）"
elif [ "$HTTPS_CODE" == "000" ]; then
    echo "❌ 无法连接（Nginx 未运行或端口未开放）"
else
    echo "⚠️  状态码: $HTTPS_CODE"
fi
echo ""

echo "【测试 HTTPS API 健康检查】"
API_CODE=$(curl -k -s -o /dev/null -w "%{http_code}" https://agent.upwaveai.com/api/health 2>/dev/null || echo "000")
echo "API 健康检查状态码: $API_CODE"
if [ "$API_CODE" == "200" ]; then
    echo "✅ API 访问正常"
    curl -k -s https://agent.upwaveai.com/api/health | python3 -m json.tool 2>/dev/null || echo ""
else
    echo "❌ API 访问失败"
fi
echo ""

# 11. 检查防火墙
echo "======================================"
echo "1️⃣1️⃣  检查防火墙规则"
echo "======================================"
if command -v ufw &> /dev/null; then
    echo "【UFW 防火墙状态】"
    sudo ufw status
else
    echo "ℹ️  UFW 未安装"
fi
echo ""

# 12. 总结和建议
echo "======================================"
echo "📋 诊断总结"
echo "======================================"
echo ""

if [ "$HTTPS_CODE" == "200" ]; then
    echo "🎉 Nginx 配置正常，HTTPS 访问成功！"
    echo ""
    echo "✅ 网站地址: https://agent.upwaveai.com"
elif [ "$HTTPS_CODE" == "502" ]; then
    echo "⚠️  Nginx 配置正常，但后端服务有问题"
    echo ""
    echo "🔍 检查建议："
    echo "   1. 确认 chatbot-api 正在运行："
    echo "      supervisorctl status chatbot-api"
    echo "   2. 确认端口 8001 正在监听："
    echo "      netstat -tlnp | grep 8001"
    echo "   3. 测试本地访问："
    echo "      curl http://127.0.0.1:8001/api/health"
elif [ "$HTTPS_CODE" == "000" ]; then
    echo "❌ 无法连接到 Nginx"
    echo ""
    echo "🔍 可能的原因："
    echo "   1. Nginx 未运行"
    echo "   2. 端口 443 未开放（防火墙/安全组）"
    echo "   3. DNS 未正确解析"
    echo ""
    echo "🔧 修复建议："
    echo "   1. 启动 Nginx: sudo systemctl start nginx"
    echo "   2. 检查防火墙: sudo ufw allow 80,443/tcp"
    echo "   3. 检查 DNS: nslookup agent.upwaveai.com"
else
    echo "⚠️  Nginx 返回状态码: $HTTPS_CODE"
    echo ""
    echo "查看错误日志获取更多信息："
    echo "   sudo tail -50 /var/log/nginx/error.log"
fi
echo ""
