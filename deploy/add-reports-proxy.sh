#!/bin/bash

echo "=========================================="
echo "🔧 添加 /agent/reports/ 反向代理配置"
echo "=========================================="
echo ""

echo "问题: 报告 URL https://upwaveai.com/reports/xxx 显示主页内容"
echo "原因: 缺少 /agent/reports/ 的反向代理规则"
echo ""

read -p "是否继续? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 1
fi

echo "1️⃣ 备份当前配置..."
cp /etc/nginx/sites-enabled/upwaveai.com /etc/nginx/sites-enabled/upwaveai.com.backup.$(date +%Y%m%d_%H%M%S)
echo "   ✅ 备份完成"
echo ""

echo "2️⃣ 添加 /agent/reports/ location 块..."

# 在 /agent/output/ 后面添加 /agent/reports/ 配置
sed -i '/location \/agent\/output\//,/^    }$/a\
\
    # 报告文件访问（HTML报告和图表）\
    location ^~ /agent/reports/ {\
        proxy_pass http://111.228.61.201:8001/reports/;\
\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
\
        # 静态资源缓存\
        expires 1h;\
        add_header Cache-Control "public";\
    }' /etc/nginx/sites-enabled/upwaveai.com

echo "   ✅ 配置已添加"
echo ""

echo "3️⃣ 验证配置..."
grep -A 3 "location.*agent/reports" /etc/nginx/sites-enabled/upwaveai.com
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

    echo "=========================================="
    echo "✅ 配置已生效！"
    echo "=========================================="
    echo ""
    echo "💡 现在报告 URL 应该使用:"
    echo "   https://upwaveai.com/agent/reports/20260101_233824/report.html"
    echo ""
    echo "📝 注意: 如果后端生成的报告 URL 不包含 /agent/ 前缀,"
    echo "   需要在后端代码中修正 URL 生成逻辑。"
    echo ""
else
    echo "   ❌ 配置测试失败"
    echo ""
    echo "恢复备份:"
    echo "   cp /etc/nginx/sites-enabled/upwaveai.com.backup.* /etc/nginx/sites-enabled/upwaveai.com"
    exit 1
fi
