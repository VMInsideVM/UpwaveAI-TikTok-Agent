# 📊 报告URL修复 - 完整指南

## 问题描述

报告URL `https://upwaveai.com/reports/xxx/report.html` 显示主页内容,而不是实际报告。

## 修复内容

### ✅ 已修复的文件

1. **[.env](.env#L24-L26)** - 添加部署配置环境变量
2. **[api/reports.py](api/reports.py#L22)** - 使用BASE_PATH生成URL
3. **[background/report_queue.py](background/report_queue.py#L19-L20)** - 使用BASE_URL和BASE_PATH
4. **[background_tasks.py](background_tasks.py#L25-L26)** - 使用BASE_URL和BASE_PATH
5. **[deploy/nginx-main-server-agent-proxy.conf](deploy/nginx-main-server-agent-proxy.conf#L102-L114)** - 添加/agent/reports/反向代理

## 部署步骤

### 步骤1: 更新环境变量 (.env)

在 Agent 服务器上编辑 `.env` 文件,确保包含:

```bash
# 部署配置 (用于生成正确的URL)
BASE_URL="https://upwaveai.com"
BASE_PATH="/agent"
```

### 步骤2: 更新代码

```bash
# 在 Agent 服务器执行
cd /root/UpwaveAI-TikTok-Agent

# 拉取最新代码
git pull origin main

# 或者手动上传修改后的文件:
# - .env
# - api/reports.py
# - background/report_queue.py
# - background_tasks.py
```

### 步骤3: 重启服务

```bash
# 重启 Chatbot API 服务以加载新的环境变量
supervisorctl restart chatbot-api

# 查看日志确认启动成功
supervisorctl tail -f chatbot-api stderr
```

### 步骤4: 更新主服务器 Nginx 配置

在**主服务器** (upwaveai.com) 执行:

```bash
# 编辑 Nginx 配置
nano /etc/nginx/sites-enabled/upwaveai.com

# 在 Agent 反向代理部分,确保包含 /agent/reports/ location块:
```

添加以下内容(如果还没有):

```nginx
# 报告文件访问（HTML报告和图表）
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
```

然后:

```bash
# 测试配置
nginx -t

# 重载 Nginx
systemctl reload nginx
```

## 验证修复

### 1. 测试环境变量加载

在 Agent 服务器上:

```bash
# 进入 Python 环境测试
cd /root/UpwaveAI-TikTok-Agent
source .venv/bin/activate
python -c "import os; print('BASE_URL:', os.getenv('BASE_URL')); print('BASE_PATH:', os.getenv('BASE_PATH'))"

# 应该输出:
# BASE_URL: https://upwaveai.com
# BASE_PATH: /agent
```

### 2. 生成新报告测试

1. 访问 https://upwaveai.com/agent/
2. 登录并生成一个新报告
3. 点击报告链接

**预期结果:**
- ✅ URL应该是: `https://upwaveai.com/agent/reports/20260101_xxxxx/report.html`
- ✅ 正常显示报告内容(不是主页)
- ✅ 报告中的图表正常加载

### 3. 测试邮件/短信通知

生成报告后检查:
- ✅ 邮件中的报告链接包含完整域名和 `/agent/` 前缀
- ✅ 短信中的报告链接包含完整域名和 `/agent/` 前缀

### 4. 测试直接访问

```bash
# 在主服务器测试
curl -I https://upwaveai.com/agent/reports/
# 应该返回 HTTP/2 404 或转发到后端

# 如果有已生成的报告,测试完整路径
curl -I https://upwaveai.com/agent/reports/20260101_233824/report.html
# 应该返回 HTTP/2 200
```

## 代码修改详解

### 1. .env 环境变量

```bash
# 新增配置
BASE_URL="https://upwaveai.com"  # 实际域名(用于邮件/短信通知)
BASE_PATH="/agent"                # 部署路径前缀(用于生成正确的URL路径)
```

### 2. api/reports.py

**修改前:**
```python
static_url = f"/reports{relative_path}"
```

**修改后:**
```python
BASE_PATH = os.getenv("BASE_PATH", "")
static_url = f"{BASE_PATH}/reports{relative_path}"
```

生成的URL:
- 根路径部署: `/reports/20260101_233824/report.html`
- 子路径部署: `/agent/reports/20260101_233824/report.html` ✅

### 3. background/report_queue.py & background_tasks.py

**修改前:**
```python
report_url = f"http://127.0.0.1:8001/?session={session_id}#report-{report_id}"
```

**修改后:**
```python
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8001")
BASE_PATH = os.getenv("BASE_PATH", "")
report_url = f"{BASE_URL}{BASE_PATH}/?session={session_id}#report-{report_id}"
```

生成的URL:
- 本地开发: `http://127.0.0.1:8001/?session=xxx#report-yyy`
- 生产环境: `https://upwaveai.com/agent/?session=xxx#report-yyy` ✅

### 4. Nginx 配置

添加 `location ^~ /agent/reports/` 块,使用 `^~` 修饰符确保优先级高于正则匹配。

## 环境变量说明

### BASE_URL
- **用途**: 生成完整的URL(用于邮件/短信通知)
- **开发环境**: `http://127.0.0.1:8001` (默认值)
- **生产环境**: `https://upwaveai.com`

### BASE_PATH
- **用途**: URL路径前缀
- **根路径部署**: `` (空字符串,默认值)
- **子路径部署**: `/agent`

## 不同部署场景

### 场景1: 根路径部署 (agent.upwaveai.com)

```bash
# .env 配置
BASE_URL="https://agent.upwaveai.com"
BASE_PATH=""

# 生成的URL
https://agent.upwaveai.com/reports/20260101_233824/report.html
```

### 场景2: 子路径部署 (upwaveai.com/agent/)

```bash
# .env 配置
BASE_URL="https://upwaveai.com"
BASE_PATH="/agent"

# 生成的URL
https://upwaveai.com/agent/reports/20260101_233824/report.html
```

### 场景3: 本地开发

```bash
# .env 配置
BASE_URL="http://127.0.0.1:8001"
BASE_PATH=""

# 生成的URL
http://127.0.0.1:8001/reports/20260101_233824/report.html
```

## 故障排查

### 问题1: 报告URL仍然没有 /agent/ 前缀

**原因**: 环境变量未加载或服务未重启

**解决**:
```bash
# 检查环境变量
cat /root/UpwaveAI-TikTok-Agent/.env | grep BASE_

# 重启服务
supervisorctl restart chatbot-api

# 查看启动日志
supervisorctl tail chatbot-api stderr
```

### 问题2: 访问报告仍显示主页

**原因**: Nginx配置未更新或未重载

**解决**:
```bash
# 检查Nginx配置
grep -A 5 "location.*agent/reports" /etc/nginx/sites-enabled/upwaveai.com

# 测试配置
nginx -t

# 重载Nginx
systemctl reload nginx
```

### 问题3: 邮件中的链接仍是127.0.0.1

**原因**:
1. 环境变量未设置
2. 服务未重启
3. 代码未更新

**解决**:
```bash
# 确认代码已更新
grep "BASE_URL.*getenv" /root/UpwaveAI-TikTok-Agent/background/report_queue.py

# 确认.env配置正确
grep BASE_URL /root/UpwaveAI-TikTok-Agent/.env

# 重启服务
supervisorctl restart chatbot-api
```

## 总结

修复后的系统行为:

1. **前端显示的报告链接**: `/agent/reports/20260101_233824/report.html`
2. **邮件/短信中的链接**: `https://upwaveai.com/agent/reports/20260101_233824/report.html`
3. **Nginx反向代理**: 正确转发 `/agent/reports/` 到后端
4. **灵活部署**: 通过环境变量支持不同的部署场景

所有URL都包含正确的域名和路径前缀,报告可以正常访问! ✅
