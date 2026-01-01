# 📊 修复报告 URL 显示问题

## 问题描述

访问报告 URL `https://upwaveai.com/reports/20260101_233824/report.html` 时显示主页内容,而不是实际的报告。

## 问题原因

主服务器的 Nginx 配置缺少 `/agent/reports/` 的反向代理规则:

```
请求: https://upwaveai.com/reports/20260101_233824/report.html
     ↓
Nginx 没有匹配到 /agent/reports/ 规则
     ↓
落入 location / { try_files $uri $uri/ /index.html; }
     ↓
返回主站 SPA 应用 (Upwave-website)
     ↓
显示主页内容 ❌
```

## 解决方案

在主服务器 Nginx 配置中添加 `/agent/reports/` 反向代理规则。

### 修改后的配置

```nginx
# 输出文件访问
location /agent/output/ {
    proxy_pass http://111.228.61.201:8001/output/;
    # ... proxy headers ...
}

# 报告文件访问（HTML报告和图表）  ← 新增
location ^~ /agent/reports/ {
    proxy_pass http://111.228.61.201:8001/reports/;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # 静态资源缓存
    expires 1h;
    add_header Cache-Control "public";
}

# Agent 主应用
location ^~ /agent/ {
    proxy_pass http://111.228.61.201:8001/;
    # ...
}
```

## 部署步骤

### 在主服务器上执行:

```bash
# 1. 备份配置
cp /etc/nginx/sites-enabled/upwaveai.com /etc/nginx/sites-enabled/upwaveai.com.backup

# 2. 编辑配置
nano /etc/nginx/sites-enabled/upwaveai.com

# 3. 在 location /agent/output/ 块后面添加:
location ^~ /agent/reports/ {
    proxy_pass http://111.228.61.201:8001/reports/;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    expires 1h;
    add_header Cache-Control "public";
}

# 4. 测试配置
nginx -t

# 5. 重载 Nginx
systemctl reload nginx
```

### 或者使用自动化脚本:

```bash
# 从 Agent 服务器复制脚本到主服务器
# scp /root/UpwaveAI-TikTok-Agent/deploy/add-reports-proxy.sh root@主服务器IP:/root/

# 在主服务器执行
chmod +x /root/add-reports-proxy.sh
/root/add-reports-proxy.sh
```

## 重要提醒

### 报告 URL 必须包含 /agent/ 前缀!

修复后,报告 URL 应该是:
```
✅ 正确: https://upwaveai.com/agent/reports/20260101_233824/report.html
❌ 错误: https://upwaveai.com/reports/20260101_233824/report.html
```

### 如果后端生成的 URL 不正确

检查后端代码中生成报告 URL 的地方,确保包含 `BASE_PATH`:

**需要检查的文件:**
1. `api/reports.py` - 报告生成相关
2. 任何生成报告链接的地方

**应该使用:**
```python
# 示例 (需要根据实际代码调整)
report_url = f"{BASE_PATH}/reports/{report_id}/report.html"
# 而不是
report_url = f"/reports/{report_id}/report.html"  # ❌
```

## 验证修复

### 1. 测试反向代理

```bash
# 在主服务器上测试
curl -I https://upwaveai.com/agent/reports/
# 应该返回 HTTP/2 404 或者转发到后端
```

### 2. 生成新报告测试

1. 访问 https://upwaveai.com/agent/
2. 登录并生成一个新报告
3. 检查生成的报告 URL 是否包含 `/agent/` 前缀
4. 点击报告链接,应该能正常显示报告内容

### 3. 浏览器测试

打开浏览器访问:
```
https://upwaveai.com/agent/reports/20260101_233824/report.html
```

**预期结果:**
- ✅ 显示实际的报告内容 (HTML页面)
- ✅ 报告中的图表正常加载
- ❌ 不应该显示主站的主页

**如果仍然显示主页:**
- 清除浏览器缓存 (Ctrl+Shift+Delete)
- 检查 Nginx 配置是否正确生效: `nginx -t && systemctl reload nginx`
- 查看 Nginx 错误日志: `tail -20 /var/log/nginx/error.log`

## Nginx Location 优先级

为什么要使用 `^~` 修饰符?

```nginx
# 优先级从高到低:
1. location = /exact/path      # 精确匹配
2. location ^~ /prefix/        # 前缀匹配(跳过正则) ← 我们使用这个
3. location ~* \.png$          # 正则匹配
4. location /prefix/           # 普通前缀匹配
```

因为主站有:
```nginx
location ~* \.(html|css|js|png|...)$ {
    expires 1y;
    # ...
}
```

如果不用 `^~`,报告的 `.html` 文件会被这个正则规则拦截!

## 完成!

修复后,报告 URL 应该能正常访问了。

记住:**报告 URL 必须以 `/agent/reports/` 开头!**
