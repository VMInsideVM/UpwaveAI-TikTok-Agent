#!/bin/bash

echo "=========================================="
echo "🔧 修复 Nginx location 优先级问题"
echo "=========================================="
echo ""

echo "问题诊断:"
echo "  错误日志显示 Nginx 在本地文件系统查找:"
echo "  /var/www/Upwave-website/dist/agent/static/logo.png"
echo ""
echo "  这说明请求被以下规则拦截了:"
echo "  location ~* \.(png|jpg|...)$ { ... }"
echo ""
echo "  正则匹配优先级 > 普通前缀匹配"
echo ""
echo "解决方案:"
echo "  使用 ^~ 修饰符,阻止正则匹配"
echo "  location ^~ /agent/static/ { ... }"
echo ""

read -p "是否继续修复? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 1
fi

echo "1️⃣ 备份当前配置..."
cp /etc/nginx/sites-enabled/upwaveai.com /etc/nginx/sites-enabled/upwaveai.com.backup.$(date +%Y%m%d_%H%M%S)
echo "   ✅ 备份完成"
echo ""

echo "2️⃣ 修改配置..."
# 修改 /agent/static/ location
sed -i 's|location /agent/static/|location ^~ /agent/static/|' /etc/nginx/sites-enabled/upwaveai.com

# 修改 /agent/ location (主应用)
sed -i 's|# Agent 主应用（前端页面）$|# Agent 主应用（前端页面 - 使用 ^~ 阻止正则匹配）|' /etc/nginx/sites-enabled/upwaveai.com
sed -i 's|location /agent/ {|location ^~ /agent/ {|' /etc/nginx/sites-enabled/upwaveai.com

echo "   ✅ 配置已修改"
echo ""

echo "3️⃣ 验证修改..."
grep -n "location.*/agent" /etc/nginx/sites-enabled/upwaveai.com | head -10
echo ""

echo "4️⃣ 测试 Nginx 配置..."
nginx -t
if [ $? -eq 0 ]; then
    echo "   ✅ 配置测试通过"
    echo ""

    echo "5️⃣ 重载 Nginx..."
    systemctl reload nginx
    echo "   ✅ Nginx 已重载"
    echo ""

    echo "6️⃣ 等待3秒后测试..."
    sleep 3

    echo "7️⃣ 测试静态资源访问..."
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://upwaveai.com/agent/static/logo.png)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "   ✅ logo.png - HTTP $HTTP_CODE"
        echo ""
        echo "=========================================="
        echo "✅ 修复成功！"
        echo "=========================================="
        echo ""
        echo "💡 下一步:"
        echo "   1. 清除浏览器缓存 (Ctrl+Shift+Delete)"
        echo "   2. 访问 https://upwaveai.com/agent/"
        echo "   3. 图片应该能正常显示了"
        echo ""
    else
        echo "   ❌ logo.png - HTTP $HTTP_CODE"
        echo ""
        echo "仍然失败,查看错误日志:"
        tail -5 /var/log/nginx/error.log
    fi
else
    echo "   ❌ 配置测试失败"
    echo ""
    echo "恢复备份:"
    echo "   cp /etc/nginx/sites-enabled/upwaveai.com.backup.* /etc/nginx/sites-enabled/upwaveai.com"
    exit 1
fi
