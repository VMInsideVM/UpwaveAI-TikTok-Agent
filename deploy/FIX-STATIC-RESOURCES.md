# 🔧 修复静态资源显示问题

## 问题原因

你说用 IP 访问（`http://111.228.61.201:8001`）可以正常加载图片，但通过域名（`https://upwaveai.com/agent/`）不行。

**根本原因**：Nginx 反向代理配置错误

之前使用的配置：
```nginx
location /agent/static/ {
    rewrite ^/agent/static/(.*) /static/$1 break;  # ❌ 错误
    proxy_pass http://111.228.61.201:8001;
}
```

这种 `rewrite` + `break` + `proxy_pass`（不带路径）的组合会导致路径处理失败。

## 正确配置

应该直接在 `proxy_pass` 后面指定完整的目标路径：

```nginx
location /agent/static/ {
    proxy_pass http://111.228.61.201:8001/static/;  # ✅ 正确
}
```

**工作原理**：
- 请求：`https://upwaveai.com/agent/static/logo.png`
- Nginx 自动替换：`/agent/static/` → `/static/`
- 转发到后端：`http://111.228.61.201:8001/static/logo.png` ✅

## 快速部署（推荐）

在**主服务器**上直接复制粘贴执行：

```bash
# 备份配置
cp /etc/nginx/sites-enabled/upwaveai.com /etc/nginx/sites-enabled/upwaveai.com.backup.$(date +%Y%m%d_%H%M%S)

# 直接更新配置（完整替换）
cat > /etc/nginx/sites-enabled/upwaveai.com << 'NGINX_CONFIG_EOF'
# 此处粘贴修复后的完整配置（见 nginx-main-server-agent-proxy.conf）
NGINX_CONFIG_EOF

# 测试配置
nginx -t

# 如果测试通过，重载 Nginx
systemctl reload nginx

# 验证静态资源
curl -I https://upwaveai.com/agent/static/logo.png
```

## 手动修改要点

如果你想手动修改，只需改5个 location 块：

```nginx
# 1. 静态资源 - 把 rewrite + proxy_pass 改成 proxy_pass 带路径
location /agent/static/ {
    proxy_pass http://111.228.61.201:8001/static/;  # 删除 rewrite 那行
}

# 2. WebSocket
location /agent/ws/ {
    proxy_pass http://111.228.61.201:8001/ws/;  # 删除 rewrite 那行
}

# 3. API
location /agent/api/ {
    proxy_pass http://111.228.61.201:8001/api/;  # 删除 rewrite 那行
}

# 4. 输出文件
location /agent/output/ {
    proxy_pass http://111.228.61.201:8001/output/;  # 删除 rewrite 那行
}

# 5. 主应用
location /agent/ {
    proxy_pass http://111.228.61.201:8001/;  # 删除 rewrite 那行
}
```

## 验证步骤

1. 测试静态资源：
```bash
curl -I https://upwaveai.com/agent/static/logo.png
# 应该返回 HTTP/2 200
```

2. 清除浏览器缓存后访问 https://upwaveai.com/agent/

3. 检查图片是否显示：
   - ✅ 左上角 logo
   - ✅ 充值弹窗的支付宝图标
   - ✅ 充值弹窗的微信支付图标

## 为什么这样修复？

Nginx `proxy_pass` 规则：
- **不带路径**：使用原始请求 URI（rewrite 无效）
- **带路径**：自动替换 location 前缀

示例：
```nginx
# ❌ 错误：rewrite 被忽略
location /agent/static/ {
    rewrite ^/agent/static/(.*) /static/$1 break;
    proxy_pass http://backend;  # 转发: /agent/static/logo.png
}

# ✅ 正确：自动替换前缀
location /agent/static/ {
    proxy_pass http://backend/static/;  # 转发: /static/logo.png
}
```

完成后图片应该能正常显示！
