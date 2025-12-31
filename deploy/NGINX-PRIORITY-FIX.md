# 🔥 Nginx Location 优先级问题修复

## 问题根因

通过你提供的错误日志,我们发现了真正的问题:

```
2025/12/31 22:33:40 [error] 836223#836223: *44823
open() "/var/www/Upwave-website/dist/agent/static/logo.png" failed
(2: No such file or directory)
```

**Nginx 没有转发请求到后端服务器**,而是在本地文件系统查找文件!

这说明请求被主站的静态资源规则拦截了:

```nginx
# 这个正则匹配规则优先级更高!
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## Nginx Location 优先级规则

Nginx 按以下顺序匹配 location:

1. **精确匹配** `= /path`
2. **前缀匹配(不检查正则)** `^~ /path`  ← **我们需要这个!**
3. **正则匹配** `~* \.png$` 或 `~ \.png$`
4. **普通前缀匹配** `/path`

你的配置问题:
- `/agent/static/` 是普通前缀匹配(优先级4)
- `~* \.png$` 是正则匹配(优先级3)
- **正则优先级更高!** 所以 `.png` 请求被正则规则拦截

## 解决方案

使用 `^~` 修饰符,让 `/agent/` 路径**跳过正则匹配**:

### 修改前:
```nginx
location /agent/static/ {  # ❌ 会被正则拦截
    proxy_pass http://111.228.61.201:8001/static/;
}
```

### 修改后:
```nginx
location ^~ /agent/static/ {  # ✅ 跳过正则,直接匹配
    proxy_pass http://111.228.61.201:8001/static/;
}
```

## 快速修复(在主服务器上执行)

### 方式1:使用自动化脚本

```bash
# 下载并执行修复脚本
cd /root
chmod +x fix-nginx-priority.sh
./fix-nginx-priority.sh
```

### 方式2:手动修改

```bash
# 1. 备份配置
cp /etc/nginx/sites-enabled/upwaveai.com /etc/nginx/sites-enabled/upwaveai.com.backup

# 2. 编辑配置
nano /etc/nginx/sites-enabled/upwaveai.com

# 3. 找到这两行并添加 ^~ 修饰符:
#    location /agent/static/ {
#    改成:
#    location ^~ /agent/static/ {
#
#    location /agent/ {
#    改成:
#    location ^~ /agent/ {

# 4. 测试配置
nginx -t

# 5. 重载 Nginx
systemctl reload nginx

# 6. 测试静态资源
curl -I https://upwaveai.com/agent/static/logo.png
# 应该返回 HTTP/2 200
```

## 验证修复

### 1. 命令行测试

```bash
curl -I https://upwaveai.com/agent/static/logo.png
```

**修复前**:
```
HTTP/2 404
```

**修复后**:
```
HTTP/2 200
content-type: image/png
```

### 2. 检查错误日志

```bash
tail -5 /var/log/nginx/error.log
```

**修复后应该没有**类似这样的错误:
```
open() "/var/www/Upwave-website/dist/agent/static/..." failed
```

### 3. 浏览器测试

1. **清除浏览器缓存**(非常重要!)
   - Chrome: Ctrl+Shift+Delete
   - 选择"缓存的图片和文件"

2. 访问 https://upwaveai.com/agent/

3. 按 F12 → Network 标签

4. 刷新页面

5. 检查 `/agent/static/logo.png` 请求:
   - ✅ 状态码 200
   - ✅ Type 显示 `png`
   - ✅ 图片正常显示

## 完整配置示例

修复后的关键部分:

```nginx
server {
    # ... SSL 配置 ...

    # ==================== Agent 反向代理 ====================
    # 使用 ^~ 确保优先级高于正则匹配

    location ^~ /agent/static/ {
        proxy_pass http://111.228.61.201:8001/static/;
        proxy_set_header Host $host;
        # ... 其他配置 ...
    }

    location ^~ /agent/ws/ {
        proxy_pass http://111.228.61.201:8001/ws/;
        # ... WebSocket 配置 ...
    }

    location ^~ /agent/api/ {
        proxy_pass http://111.228.61.201:8001/api/;
        # ... API 配置 ...
    }

    location ^~ /agent/ {
        proxy_pass http://111.228.61.201:8001/;
        # ... 主应用配置 ...
    }
    # ==================== Agent 反向代理结束 ====================

    # 主站根目录
    root /var/www/Upwave-website/dist;

    # 这个正则匹配现在不会影响 /agent/ 路径了!
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## 为什么之前的修复没用?

之前我们修复了 `rewrite` 问题,但请求根本没到达那个 location 块!

执行流程:
1. 请求: `GET /agent/static/logo.png`
2. Nginx 匹配规则:
   - ❌ 跳过 `location /agent/static/` (普通前缀)
   - ✅ **匹配 `location ~* \.png$`** (正则,优先级更高!)
   - 在本地文件系统查找 `/var/www/Upwave-website/dist/agent/static/logo.png`
   - 404 Not Found

现在使用 `^~` 后:
1. 请求: `GET /agent/static/logo.png`
2. Nginx 匹配规则:
   - ✅ **匹配 `location ^~ /agent/static/`** (跳过正则检查!)
   - 转发到 `http://111.228.61.201:8001/static/logo.png`
   - 200 OK ✅

## 总结

- ❌ 之前的问题: 正则匹配规则优先级高,拦截了所有 `.png` 请求
- ✅ 修复方案: 使用 `^~` 修饰符,让 `/agent/` 路径跳过正则匹配
- 🔥 关键修改: `location /agent/xxx/` → `location ^~ /agent/xxx/`

修复后图片应该能正常显示了!
