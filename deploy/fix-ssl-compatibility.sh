#!/bin/bash

# ============================================
# 修复 SSL 兼容性配置
# ============================================

set -e

echo "🔧 修复 SSL 兼容性配置..."
echo ""

# 备份配置
echo "💾 备份配置..."
sudo cp /etc/nginx/sites-available/agent.upwaveai.com \
       /etc/nginx/sites-available/agent.upwaveai.com.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ 备份完成"
echo ""

# 修改 SSL 配置为更兼容的设置
echo "📝 更新 SSL 配置..."

sudo sed -i "s/ssl_prefer_server_ciphers off;/ssl_prefer_server_ciphers on;/" \
    /etc/nginx/sites-available/agent.upwaveai.com

echo "✅ 配置已更新"
echo ""

# 测试配置
echo "✅ 测试 Nginx 配置..."
sudo nginx -t
echo ""

# 重载 Nginx
echo "🔄 重载 Nginx..."
sudo systemctl reload nginx
echo "✅ Nginx 已重载"
echo ""

echo "======================================"
echo "🎉 SSL 兼容性修复完成！"
echo "======================================"
echo ""
echo "请从外部浏览器重新访问："
echo "https://agent.upwaveai.com"
echo ""
