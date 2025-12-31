#!/bin/bash

# SSL 证书配置脚本（使用 Let's Encrypt）
# 适用于 Ubuntu 24.04

set -e

# 配置变量
DOMAIN="agent.upwaveai.com"
EMAIL="admin@upwaveai.com"

echo "🔒 开始配置 SSL 证书..."

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    echo "使用命令: sudo bash ssl-setup.sh"
    exit 1
fi

# 1. 检查域名解析
echo "📡 检查域名解析..."
DOMAIN_IP=$(dig +short $DOMAIN | tail -n1)
SERVER_IP=$(curl -s ifconfig.me)

echo "域名 IP: $DOMAIN_IP"
echo "服务器 IP: $SERVER_IP"

if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
    echo "⚠️  警告: 域名 IP 与服务器 IP 不匹配！"
    echo "请确保域名已正确指向服务器 IP: $SERVER_IP"
    read -p "是否继续？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 已取消"
        exit 1
    fi
fi

# 2. 安装 Certbot
echo "📦 安装 Certbot..."
apt update
apt install -y certbot python3-certbot-nginx

# 3. 申请证书
echo "🔐 申请 SSL 证书..."
echo "邮箱: $EMAIL"
echo "域名: $DOMAIN"

certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL --redirect

# 4. 测试证书
echo "✅ 测试证书配置..."
nginx -t

# 5. 重启 Nginx
echo "🔄 重启 Nginx..."
systemctl restart nginx

# 6. 测试 HTTPS 访问
echo "🌐 测试 HTTPS 访问..."
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/api/health)

if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ HTTPS 配置成功！"
else
    echo "⚠️  HTTPS 访问返回: $HTTP_CODE"
    echo "请检查服务是否正常运行"
fi

# 7. 设置自动续期
echo "⏰ 配置证书自动续期..."
systemctl enable certbot.timer
systemctl start certbot.timer

# 测试续期
certbot renew --dry-run

echo ""
echo "🎉 SSL 证书配置完成！"
echo ""
echo "📋 证书信息:"
certbot certificates
echo ""
echo "🌐 访问地址: https://$DOMAIN"
echo "📅 证书有效期: 90 天（自动续期）"
echo ""
echo "💡 提示:"
echo "  - 查看证书状态: sudo certbot certificates"
echo "  - 手动续期: sudo certbot renew"
echo "  - 查看续期日志: sudo journalctl -u certbot.timer"
