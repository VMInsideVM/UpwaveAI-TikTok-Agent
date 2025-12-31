# 🎯 最终修复汇总

## 问题1: 静态资源404 - Nginx优先级问题 ✅

### 根因
错误日志显示Nginx在本地文件系统查找:
```
open() "/var/www/Upwave-website/dist/agent/static/logo.png" failed
```

这是因为正则匹配规则 `location ~* \.png$` 的优先级高于普通前缀匹配 `location /agent/static/`。

### 修复
使用 `^~` 修饰符阻止正则匹配:

**修改前:**
```nginx
location /agent/static/ {
    proxy_pass http://111.228.61.201:8001/static/;
}
```

**修改后:**
```nginx
location ^~ /agent/static/ {  # 添加 ^~
    proxy_pass http://111.228.61.201:8001/static/;
}
```

同样修改主应用路由:
```nginx
location ^~ /agent/ {  # 添加 ^~
    proxy_pass http://111.228.61.201:8001/;
}
```

### 部署命令 (在主服务器执行)
```bash
# 备份配置
cp /etc/nginx/sites-enabled/upwaveai.com /etc/nginx/sites-enabled/upwaveai.com.backup

# 修改配置 (添加 ^~)
sed -i 's|location /agent/static/|location ^~ /agent/static/|' /etc/nginx/sites-enabled/upwaveai.com
sed -i 's|    location /agent/ {|    location ^~ /agent/ {|' /etc/nginx/sites-enabled/upwaveai.com

# 测试配置
nginx -t

# 重载 Nginx
systemctl reload nginx

# 验证修复
curl -I https://upwaveai.com/agent/static/logo.png
# 应该返回 HTTP/2 200
```

---

## 问题2: "返回主页"按钮跳转到主域名 ✅

### 根因
[settings.html:386](static/settings.html#L386) 使用了硬编码的 `<a href="/">`

### 修复

**修改文件:**
1. `static/settings.html` - "返回主页"按钮
2. `static/register.html` - 已登录时的跳转逻辑

**settings.html 修改前:**
```html
<a href="/" class="btn-back">返回主页</a>
```

**settings.html 修改后:**
```html
<a href="#" onclick="event.preventDefault(); navigateTo('/');" class="btn-back">返回主页</a>
```

**register.html 修改前:**
```javascript
window.location.href = isAdmin ? '/admin.html' : '/';
```

**register.html 修改后:**
```javascript
navigateTo(isAdmin ? '/admin.html' : '/');
```

### 部署命令 (在 Agent 服务器执行)
```bash
# 确保最新代码已提交到 Git
cd /root/UpwaveAI-TikTok-Agent

# 拉取最新代码
git pull origin main

# 或者手动上传修改后的文件到服务器
# scp static/settings.html root@111.228.61.201:/root/UpwaveAI-TikTok-Agent/static/
# scp static/register.html root@111.228.61.201:/root/UpwaveAI-TikTok-Agent/static/
```

---

## 完整部署步骤

### 步骤1: 更新主服务器 Nginx 配置

**在主服务器 (upwaveai.com所在的VPS) 执行:**

```bash
# 1. 备份配置
cp /etc/nginx/sites-enabled/upwaveai.com /etc/nginx/sites-enabled/upwaveai.com.backup.$(date +%Y%m%d_%H%M%S)

# 2. 修改配置
sed -i 's|location /agent/static/|location ^~ /agent/static/|' /etc/nginx/sites-enabled/upwaveai.com
sed -i 's|    location /agent/ {|    location ^~ /agent/ {|' /etc/nginx/sites-enabled/upwaveai.com

# 3. 验证修改
grep "location.*agent" /etc/nginx/sites-enabled/upwaveai.com

# 4. 测试配置
nginx -t

# 5. 重载 Nginx
systemctl reload nginx

# 6. 验证静态资源
curl -I https://upwaveai.com/agent/static/logo.png
# 预期: HTTP/2 200

curl -I https://upwaveai.com/agent/static/alipay_payment.png
# 预期: HTTP/2 200
```

### 步骤2: 更新 Agent 服务器前端代码

**在 Agent 服务器 (111.228.61.201) 执行:**

```bash
# 方式1: 如果代码已提交到 Git
cd /root/UpwaveAI-TikTok-Agent
git pull origin main

# 方式2: 手动上传文件
# 在本地执行:
# scp static/settings.html root@111.228.61.201:/root/UpwaveAI-TikTok-Agent/static/
# scp static/register.html root@111.228.61.201:/root/UpwaveAI-TikTok-Agent/static/

# 无需重启服务 (静态文件直接生效)
```

### 步骤3: 验证修复

**浏览器验证:**

1. **清除浏览器缓存** (非常重要!)
   - Chrome: Ctrl+Shift+Delete → 选择"缓存的图片和文件"
   - 或使用无痕模式: Ctrl+Shift+N

2. 访问 https://upwaveai.com/agent/

3. 检查静态资源:
   - ✅ 左上角 logo 图标显示
   - ✅ 充值弹窗中支付宝图标显示
   - ✅ 充值弹窗中微信支付图标显示

4. 测试"返回主页"按钮:
   - 进入设置页面: 点击用户头像 → 个人设置
   - 点击"返回主页"按钮
   - ✅ 应该跳转到 `https://upwaveai.com/agent/` (而不是 `https://upwaveai.com/`)

5. 按 F12 → Network 标签:
   - 刷新页面
   - 筛选 `.png` 文件
   - ✅ 所有静态资源请求状态码应为 200

---

## 修复后的文件清单

### 本地已修改的文件:
1. ✅ `deploy/nginx-main-server-agent-proxy.conf` - 添加 `^~` 修饰符
2. ✅ `static/settings.html` - 修复"返回主页"按钮
3. ✅ `static/register.html` - 修复已登录跳转

### 服务器需要更新:
1. **主服务器**: `/etc/nginx/sites-enabled/upwaveai.com` - Nginx配置
2. **Agent服务器**: `static/settings.html` 和 `static/register.html` - 前端文件

---

## 技术要点总结

### Nginx Location 优先级
1. 精确匹配 `= /path` (最高)
2. **前缀匹配(跳过正则) `^~ /path`** ← 我们使用这个
3. 正则匹配 `~* pattern`
4. 普通前缀匹配 `/path` (最低)

### 为什么 `^~` 有效?
- 告诉 Nginx: "匹配后不再检查正则规则"
- 避免被 `location ~* \.(png|jpg|...)$` 拦截
- 确保 `/agent/` 路径下的请求正确转发到后端

### Base Path 自动检测
前端使用以下代码自动适配部署路径:

```javascript
const BASE_PATH = (() => {
    const path = window.location.pathname;
    if (path.startsWith('/agent/')) return '/agent';
    return '';
})();

const navigateTo = (p) => {
    window.location.href = BASE_PATH + (p.startsWith('/') ? p : '/' + p);
};
```

这样无论部署在根路径还是子路径都能正常工作!

---

## 完成！ 🎉

部署完成后,所有功能应该正常工作:
- ✅ 静态资源正常加载
- ✅ 页面导航使用正确的路径
- ✅ API 请求正常
- ✅ WebSocket 连接正常

如有问题,查看:
- 主服务器错误日志: `tail -50 /var/log/nginx/error.log`
- Agent服务器日志: `supervisorctl tail -f chatbot-api stderr`
