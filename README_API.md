# Playwright API 服务使用指南

## 📖 概述

为了解决 LangChain 多线程调用 Playwright 时的 greenlet 线程切换错误，我们将 Playwright 操作封装成独立的 FastAPI 服务。

### 问题背景

**之前的错误**:
```
greenlet.error: Cannot switch to a different thread
        Current:  <greenlet.greenlet object at 0x00000227202B38C0>
        Expected: <greenlet.greenlet object at 0x000002271E35D500>
```

**根本原因**:
- Playwright 的 `sync_api` 使用 greenlet（绿色线程），greenlet 是**线程局部**的
- LangChain 的 `create_agent()` 会在**工作线程**中调用工具
- 工作线程尝试访问主线程创建的 Playwright 对象 → greenlet 无法跨线程切换 → 错误

**解决方案**:
- 将 Playwright 操作隔离到独立的 **FastAPI 服务**（独立进程）
- Agent 通过 **HTTP 请求**调用 API（跨进程通信，无线程问题）
- API 服务在自己的主线程中运行 Playwright（单线程，无冲突）

---

## 🚀 快速开始

### 1. 安装依赖

确保已安装新增的 API 依赖：

```bash
pip install -r requirements.txt
```

新增依赖：
- `fastapi>=0.100.0` - Web 框架
- `uvicorn>=0.23.0` - ASGI 服务器
- `requests>=2.31.0` - HTTP 客户端

### 2. 启动 Chrome 浏览器

```bash
# Windows
chrome.exe --remote-debugging-port=9224

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9224

# Linux
google-chrome --remote-debugging-port=9224
```

### 3. 启动 Playwright API 服务（终端 1）

```bash
# 方式 1: 使用启动脚本（推荐）
python start_api.py

# 方式 2: 直接运行
python playwright_api.py
```

启动成功后会看到：

```
╔═══════════════════════════════════════════════════════════════╗
║      🚀 Playwright Scraping API Service 🚀                   ║
╚═══════════════════════════════════════════════════════════════╝

🔧 正在初始化 Playwright API 服务...
  ✓ Playwright 实例已创建
  ✓ 已连接到 Chrome (CDP:9224)
  ✓ 已获取浏览器页面
✅ Playwright API 服务启动成功！
📡 API 文档: http://127.0.0.1:8000/docs

INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 4. 启动 Agent（终端 2 - 新窗口）

```bash
# 正常模式
python run_agent.py

# 测试模式
python run_agent.py --test
```

Agent 会自动检测 API 服务：

```
🔧 正在检查 Playwright API 服务...
✅ Playwright API 服务已就绪!
```

---

## 📡 API 端点说明

### 1. 健康检查

**GET** `/health`

检查 API 服务和 Playwright 是否正常运行。

```bash
curl http://127.0.0.1:8000/health
```

响应示例：
```json
{
  "status": "healthy",
  "playwright_initialized": true,
  "message": "服务正常"
}
```

---

### 2. 页面导航

**POST** `/navigate`

导航到指定 URL 并等待页面加载。

请求体：
```json
{
  "url": "https://www.fastmoss.com/zh/influencer/search?region=US",
  "wait_for_load": true
}
```

响应示例：
```json
{
  "success": true,
  "url": "https://www.fastmoss.com/zh/influencer/search?region=US",
  "message": "页面导航成功"
}
```

---

### 3. 获取最大页数

**GET** `/max_page`

从当前页面的分页控件中提取最大页码。

**注意**: 必须先调用 `/navigate` 导航到搜索页面。

```bash
curl http://127.0.0.1:8000/max_page
```

响应示例：
```json
{
  "success": true,
  "max_page": 45,
  "estimated_count": 450,
  "message": "最大页数: 45"
}
```

---

### 4. 爬取达人数据

**POST** `/scrape`

爬取多页达人数据并返回 JSON 格式。

请求体：
```json
{
  "url": "https://www.fastmoss.com/zh/influencer/search?region=US&follower=100000,500000",
  "max_pages": 5
}
```

响应示例：
```json
{
  "success": true,
  "data": [
    {
      "达人昵称": "John Doe",
      "粉丝数": 250000,
      "互动率": 0.0523,
      ...
    },
    ...
  ],
  "row_count": 50,
  "column_count": 12,
  "columns": ["达人昵称", "粉丝数", "互动率", ...],
  "message": "成功爬取 50 个达人"
}
```

---

### 5. 获取当前 URL

**GET** `/current_url`

获取浏览器当前页面的 URL。

```bash
curl http://127.0.0.1:8000/current_url
```

响应示例：
```json
{
  "success": true,
  "url": "https://www.fastmoss.com/zh/influencer/search?region=US",
  "message": "当前 URL"
}
```

---

## 🔧 Agent 工具如何调用 API

### 修改前（直接调用 Playwright）

```python
# agent_tools.py - 旧版本
from main import navigate_to_url, get_max_page_number

class GetMaxPageTool(BaseTool):
    def _run(self, url: str) -> str:
        # ❌ 在 LangChain 工作线程中调用，导致 greenlet 错误
        if not navigate_to_url(url):
            return "访问失败"
        max_page = get_max_page_number()
        return f"最大页数: {max_page}"
```

### 修改后（调用 API）

```python
# agent_tools.py - 新版本
import requests

API_BASE_URL = "http://127.0.0.1:8000"

class GetMaxPageTool(BaseTool):
    def _run(self, url: str) -> str:
        # ✅ 通过 HTTP 调用 API，无线程问题
        # 1. 导航到 URL
        nav_result = requests.post(
            f"{API_BASE_URL}/navigate",
            json={"url": url, "wait_for_load": True}
        ).json()

        # 2. 获取最大页数
        result = requests.get(f"{API_BASE_URL}/max_page").json()
        max_page = result.get("max_page", 0)

        return f"最大页数: {max_page}"
```

---

## 📊 架构对比

### 旧架构（单进程，有线程问题）

```
┌─────────────────────────────────────┐
│   主进程                             │
│                                     │
│   主线程: Playwright (greenlet A)   │
│      ↓                              │
│   工作线程: LangChain Tool          │
│      ↓                              │
│   ❌ 尝试访问 greenlet A            │
│   ❌ greenlet.error!                │
└─────────────────────────────────────┘
```

### 新架构（微服务，无线程问题）

```
┌────────────────────┐           ┌────────────────────┐
│  进程 1: Agent     │  HTTP     │  进程 2: API 服务  │
│                    │ ◄────────►│                    │
│  主线程            │           │  主线程            │
│  ├─ LangChain      │           │  └─ Playwright     │
│  └─ 工作线程       │           │     (greenlet)     │
│     └─ Tools       │           │                    │
│        └─ HTTP请求 │           │  ✅ 单线程运行     │
│                    │           │  ✅ 无冲突         │
└────────────────────┘           └────────────────────┘
```

---

## 🛠 开发和调试

### 查看 API 文档

启动 API 服务后，访问自动生成的交互式文档：

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

在 Swagger UI 中可以直接测试所有 API 端点。

### 手动测试 API

使用 `curl` 或 `Postman` 测试：

```bash
# 1. 检查健康状态
curl http://127.0.0.1:8000/health

# 2. 导航到页面
curl -X POST http://127.0.0.1:8000/navigate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.fastmoss.com/zh/influencer/search?region=US", "wait_for_load": true}'

# 3. 获取最大页数
curl http://127.0.0.1:8000/max_page

# 4. 爬取数据
curl -X POST http://127.0.0.1:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.fastmoss.com/zh/influencer/search?region=US", "max_pages": 2}'
```

### Python 代码测试

```python
import requests

API_BASE_URL = "http://127.0.0.1:8000"

# 检查健康状态
health = requests.get(f"{API_BASE_URL}/health").json()
print(health)

# 导航并爬取
requests.post(f"{API_BASE_URL}/navigate", json={
    "url": "https://www.fastmoss.com/zh/influencer/search?region=US",
    "wait_for_load": True
})

result = requests.get(f"{API_BASE_URL}/max_page").json()
print(f"最大页数: {result['max_page']}")
```

---

## ⚠️ 常见问题

### 1. Agent 提示 "无法连接到 Playwright API 服务"

**原因**: API 服务未启动

**解决**:
```bash
# 启动 API 服务
python start_api.py
```

---

### 2. API 服务提示 "Playwright 未初始化"

**原因**: Chrome 未运行或 CDP 端口不正确

**解决**:
```bash
# 确保 Chrome 运行在 9224 端口
chrome.exe --remote-debugging-port=9224
```

---

### 3. 端口 8000 被占用

**错误信息**: `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`

**解决**:
```bash
# 查找占用端口的进程
netstat -ano | findstr :8000

# 结束进程（Windows）
taskkill /PID <进程ID> /F

# 或修改 API 服务端口（playwright_api.py）
uvicorn.run(app, host="127.0.0.1", port=8001)  # 改为 8001
```

---

### 4. API 响应超时

**原因**: 爬取页数过多或网络慢

**解决**: 增加超时时间

```python
# agent_tools.py
result = call_api(
    "/scrape",
    method="POST",
    data={"url": url, "max_pages": 10},
    timeout=600  # 增加到 10 分钟
)
```

---

## 📈 性能和扩展

### 当前架构的性能

- **单线程爬取**: API 服务是单线程的，一次只能处理一个请求
- **适合场景**: 顺序爬取，单个 Agent 实例
- **延迟**: 本地 HTTP 调用延迟极低（< 1ms）

### 未来扩展方向

如果需要高并发，可以考虑：

1. **多实例部署**:
   ```bash
   # 启动多个 API 服务实例，使用不同端口
   python playwright_api.py --port 8000
   python playwright_api.py --port 8001
   python playwright_api.py --port 8002
   ```

2. **负载均衡**: 使用 Nginx 或其他负载均衡器分发请求

3. **Docker 部署**:
   ```dockerfile
   FROM python:3.12
   RUN playwright install chromium
   COPY . /app
   WORKDIR /app
   CMD ["python", "playwright_api.py"]
   ```

---

## 📝 总结

### 优势

✅ **彻底解决线程问题**: Playwright 在独立进程中运行，无 greenlet 冲突
✅ **关注点分离**: Agent 专注于决策，API 专注于爬虫
✅ **易于调试**: 可以独立测试 API 服务
✅ **可扩展**: 支持多实例部署、负载均衡
✅ **语言无关**: 任何语言都能调用 API

### 代价

⚠️ **需要两个进程**: 必须先启动 API 服务，再启动 Agent
⚠️ **轻微延迟**: HTTP 通信有极小的开销（可忽略）
⚠️ **多一层抽象**: 增加了系统复杂度

---

## 📚 相关文档

- [CLAUDE.md](CLAUDE.md) - 项目架构和开发指南
- [playwright_api.py](playwright_api.py) - API 服务源码
- [agent_tools.py](agent_tools.py) - Agent 工具实现
- FastAPI 文档: https://fastapi.tiangolo.com/
- Playwright 文档: https://playwright.dev/python/

---

**更新日期**: 2025-01-04
**版本**: v1.0（API 架构）
