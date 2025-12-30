# 任务队列管理功能

## 功能概述

后台管理系统新增**任务队列管理**功能，管理员可以实时查看当前正在处理的用户任务，并且可以停止特定任务让API切换处理下一个用户的任务。

## 功能特性

✅ **实时任务监控**
- 显示当前正在处理的任务详情（用户名、用户ID、会话ID、任务类型、运行时间）
- 显示等待队列中的任务列表
- 自动计算任务运行时长和等待时长

✅ **任务控制**
- 管理员可以停止当前任务
- 任务在下一个检查点安全停止（不会强制中断）
- 停止后自动切换处理下一个任务

✅ **用户友好界面**
- 清晰的任务状态显示（🟢 处理中 / ⚪ 空闲）
- 彩色标记区分当前任务和等待队列
- 一键刷新任务状态

## 架构设计

### 后端架构

```
┌──────────────────────────────────────────────────────────┐
│   Playwright API (端口 8000)                              │
│   - 任务队列状态管理（全局变量）                            │
│   - 爬虫任务执行（检查停止请求）                            │
│   - 管理员API端点                                         │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────┐
│   任务队列状态全局变量                                      │
│   - current_task: 当前任务信息                             │
│   - is_processing: 是否正在处理                            │
│   - stop_requested: 停止请求标记                           │
│   - processing_lock: 并发控制锁                            │
└──────────────────────────────────────────────────────────┘
```

### 前端架构

```
┌──────────────────────────────────────────────────────────┐
│   后台管理页面 (admin.html)                                │
│   - 任务队列标签页                                         │
│   - loadTasks() - 获取任务状态                             │
│   - stopCurrentTask() - 停止任务                           │
└─────────────────┬────────────────────────────────────────┘
                  │ HTTP请求
                  ▼
┌──────────────────────────────────────────────────────────┐
│   Playwright API 管理员端点                                │
│   - GET /api/admin/tasks - 查看任务                        │
│   - POST /api/admin/tasks/stop - 停止任务                  │
└──────────────────────────────────────────────────────────┘
```

## 代码实现

### 1. 后端 - 任务队列状态管理

**文件**: [playwright_api.py:74-145](playwright_api.py#L74-L145)

**全局状态变量**:
```python
_task_queue_state = {
    "current_task": None,  # 当前正在处理的任务信息
    "queue": [],  # 等待队列
    "is_processing": False,  # 是否正在处理任务
    "processing_lock": None,  # 并发控制锁
    "stop_requested": False,  # 是否请求停止当前任务
}
```

**核心函数**:

#### `set_current_task(session_id, user_id, username, task_type)`
设置当前任务：
```python
def set_current_task(session_id: str, user_id: str = None, username: str = None, task_type: str = "scraping"):
    """设置当前任务"""
    global _task_queue_state
    _task_queue_state["current_task"] = {
        "session_id": session_id,
        "user_id": user_id or "未知",
        "username": username or "未知用户",
        "task_type": task_type,
        "start_time": datetime.now()
    }
    _task_queue_state["is_processing"] = True
    _task_queue_state["stop_requested"] = False
    print(f"[任务队列] 开始处理任务: 用户 {username} (会话 {session_id})")
```

#### `clear_current_task()`
清除当前任务：
```python
def clear_current_task():
    """清除当前任务"""
    global _task_queue_state
    if _task_queue_state["current_task"]:
        print(f"[任务队列] 完成任务: {_task_queue_state['current_task']['username']}")
    _task_queue_state["current_task"] = None
    _task_queue_state["is_processing"] = False
    _task_queue_state["stop_requested"] = False
```

#### `request_stop_current_task()`
请求停止当前任务：
```python
def request_stop_current_task() -> bool:
    """请求停止当前任务"""
    global _task_queue_state
    if _task_queue_state["is_processing"]:
        _task_queue_state["stop_requested"] = True
        print(f"[任务队列] 收到停止请求，将在下一个检查点停止当前任务")
        return True
    return False
```

#### `is_stop_requested()`
检查是否请求停止：
```python
def is_stop_requested() -> bool:
    """检查是否请求停止"""
    return _task_queue_state.get("stop_requested", False)
```

### 2. 后端 - 任务执行与停止检查

**文件**: [playwright_api.py:953-1052](playwright_api.py#L953-L1052)

**修改的爬取端点**:
```python
@app.post("/scrape")
async def scrape_pages(req: ScrapeRequest):
    """爬取达人数据（支持任务队列管理）"""
    check_initialized()

    # 设置当前任务
    set_current_task(
        session_id=req.session_id or "unknown",
        user_id=req.user_id,
        username=req.username,
        task_type="scraping"
    )

    try:
        # ... 爬取逻辑 ...

        # 依次爬取每个 URL
        for idx, url in enumerate(req.urls, 1):
            # ⭐ 检查是否请求停止
            if is_stop_requested():
                print(f"\n⚠️ 收到停止请求，中止爬取任务")
                clear_current_task()
                raise HTTPException(status_code=499, detail="任务已被管理员停止")

            # 继续爬取...
            row_keys = await get_data_row_keys(url=url, max_pages=req.max_pages)
            # ...

        # 清除当前任务
        clear_current_task()

        return {
            "success": True,
            # ...
        }

    except PlaywrightError as e:
        clear_current_task()  # 出错时也清除任务状态
        # ...

    except Exception as e:
        clear_current_task()  # 出错时也清除任务状态
        # ...
```

**关键改进**：
1. 任务开始时调用 `set_current_task()` 设置状态
2. 循环中检查 `is_stop_requested()` 判断是否停止
3. 任务完成或出错时调用 `clear_current_task()` 清除状态

### 3. 后端 - 管理员API端点

**文件**: [playwright_api.py:2120-2193](playwright_api.py#L2120-L2193)

#### GET /api/admin/tasks
获取任务队列状态：
```python
@app.get("/api/admin/tasks")
async def get_admin_tasks():
    """管理员API：获取任务队列状态"""
    try:
        status = get_task_queue_status()

        # 格式化当前任务信息
        current_task_info = None
        if status["current_task"]:
            task = status["current_task"]
            elapsed_time = (datetime.now() - task["start_time"]).total_seconds()
            current_task_info = {
                "session_id": task["session_id"],
                "user_id": task.get("user_id", "未知"),
                "username": task.get("username", "未知用户"),
                "task_type": task.get("task_type", "unknown"),
                "elapsed_time": int(elapsed_time),
                "elapsed_time_formatted": f"{int(elapsed_time // 60)}分{int(elapsed_time % 60)}秒"
            }

        return {
            "success": True,
            "is_processing": status["is_processing"],
            "current_task": current_task_info,
            "queue_length": status["queue_length"],
            "queued_tasks": status["queued_tasks"],
            "stop_requested": status["stop_requested"]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "is_processing": False,
            "current_task": None,
            "queue_length": 0,
            "queued_tasks": []
        }
```

#### POST /api/admin/tasks/stop
停止当前任务：
```python
@app.post("/api/admin/tasks/stop")
async def stop_current_task():
    """管理员API：停止当前任务"""
    try:
        stopped = request_stop_current_task()

        if stopped:
            return {
                "success": True,
                "message": "已发送停止信号，任务将在下一个检查点停止"
            }
        else:
            return {
                "success": False,
                "message": "当前没有正在处理的任务"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"停止任务失败: {str(e)}"
        }
```

### 4. 前端 - 任务队列页面

**文件**: [static/admin.html:1703-1827](static/admin.html#L1703-L1827)

#### 加载任务列表
```javascript
async function loadTasks() {
    try {
        const response = await fetch('http://127.0.0.1:8000/api/admin/tasks');
        const data = await response.json();

        if (!data.success) {
            throw new Error(data.error || '加载失败');
        }

        // 构建当前任务信息
        let currentTaskHtml = '<div style="color: #666; font-style: italic;">无任务运行</div>';
        if (data.current_task) {
            const task = data.current_task;
            currentTaskHtml = `
                <div style="background: #f0f9ff; padding: 15px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                    <div style="display: grid; grid-template-columns: 120px 1fr; gap: 10px; font-size: 15px;">
                        <div style="font-weight: 600; color: #1e40af;">用户名:</div>
                        <div>${task.username}</div>

                        <div style="font-weight: 600; color: #1e40af;">用户ID:</div>
                        <div>${task.user_id}</div>

                        <div style="font-weight: 600; color: #1e40af;">会话ID:</div>
                        <div style="font-family: monospace; font-size: 13px;">${task.session_id.substring(0, 12)}...</div>

                        <div style="font-weight: 600; color: #1e40af;">任务类型:</div>
                        <div>${task.task_type === 'scraping' ? '🕷️ 达人搜索' : task.task_type}</div>

                        <div style="font-weight: 600; color: #1e40af;">运行时间:</div>
                        <div>${task.elapsed_time_formatted}</div>

                        ${data.stop_requested ? `
                            <div style="grid-column: 1 / -1; margin-top: 10px;">
                                <span style="color: #dc2626; font-weight: 600;">⚠️ 已请求停止，等待任务响应...</span>
                            </div>
                        ` : ''}
                    </div>

                    <div style="margin-top: 15px; text-align: right;">
                        <button
                            class="btn btn-danger btn-sm"
                            onclick="stopCurrentTask()"
                            ${data.stop_requested ? 'disabled' : ''}
                        >
                            ${data.stop_requested ? '⏳ 停止中...' : '⏹️ 停止任务'}
                        </button>
                    </div>
                </div>
            `;
        }

        // 构建等待队列信息...
        // （显示等待中的任务列表）

        document.getElementById('tasksInfo').innerHTML = html;
    } catch (error) {
        console.error('Failed to load tasks:', error);
        document.getElementById('tasksInfo').innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">😕</div>
                <p>加载失败: ${error.message}</p>
                <p style="font-size: 13px; color: #666; margin-top: 10px;">
                    请确保 Playwright API 服务 (端口 8000) 正在运行
                </p>
            </div>
        `;
    }
}
```

#### 停止任务
```javascript
async function stopCurrentTask() {
    if (!confirm('确定要停止当前任务吗？\n\n任务会在下一个检查点停止，正在处理的数据可能会丢失。')) {
        return;
    }

    try {
        const response = await fetch('http://127.0.0.1:8000/api/admin/tasks/stop', {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            alert('✅ ' + data.message);
            // 刷新任务队列显示
            await loadTasks();
        } else {
            alert('❌ ' + data.message);
        }
    } catch (error) {
        console.error('Failed to stop task:', error);
        alert('停止任务失败: ' + error.message);
    }
}
```

### 5. Agent - 会话信息传递

**文件**: [agent.py:29-41](agent.py#L29-L41), [agent_tools.py:495-504](agent_tools.py#L495-L504), [session_manager_db.py:68-102](session_manager_db.py#L68-L102)

#### Agent接收username
```python
# agent.py
def __init__(self, user_id: Optional[str] = None, session_id: Optional[str] = None, username: Optional[str] = None, callbacks: Optional[list] = None):
    """初始化 Agent"""
    self.user_id = user_id  # 存储用户 ID
    self.session_id = session_id  # 存储会话 ID
    self.username = username  # 存储用户名
```

#### 工具传递会话信息
```python
# agent_tools.py - ScrapeInfluencersTool
# 获取会话信息
agent = get_agent_instance()
session_info = {}
if agent:
    if hasattr(agent, 'session_id') and agent.session_id:
        session_info['session_id'] = agent.session_id
    if hasattr(agent, 'user_id') and agent.user_id:
        session_info['user_id'] = agent.user_id
    if hasattr(agent, 'username') and agent.username:
        session_info['username'] = agent.username

# 调用 API 爬取数据并导出 JSON
result = call_api(
    "/scrape",
    method="POST",
    data={
        "urls": urls,
        "max_pages": max_pages,
        "product_name": product_name,
        **session_info  # 传递会话信息
    },
    timeout=len(urls) * max_pages * 30
)
```

#### Session Manager获取用户信息
```python
# session_manager_db.py
def get_agent(self, session_id: str) -> TikTokInfluencerAgent:
    """获取会话的 Agent 实例"""
    # 从缓存获取
    if session_id in self._agent_cache:
        return self._agent_cache[session_id]

    # 获取会话的 user_id 和 username
    user_info = self._get_session_user_info(session_id)
    user_id = user_info.get('user_id') if user_info else None
    username = user_info.get('username') if user_info else None

    # 创建新 Agent 实例，传递 user_id, session_id 和 username
    agent = TikTokInfluencerAgent(
        user_id=user_id,
        session_id=session_id,
        username=username
    )

    # 加载历史消息...
    # 缓存...
    return agent

def _get_session_user_info(self, session_id: str) -> Optional[Dict]:
    """获取会话对应的用户信息（user_id 和 username）"""
    try:
        with get_db_context() as db:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()

            if not session:
                return None

            # 获取用户信息
            user = db.query(User).filter(User.user_id == session.user_id).first()

            return {
                'user_id': session.user_id,
                'username': user.username if user else None
            }
    except Exception as e:
        print(f"❌ 获取会话用户信息失败: {e}")
        return None
```

## 使用指南

### 管理员操作

1. **打开后台管理**
   - 访问 http://127.0.0.1:8001/admin.html
   - 使用管理员账号登录

2. **查看任务队列**
   - 点击顶部导航栏的"⚙️ 任务队列"标签
   - 页面自动加载当前任务状态

3. **停止任务**
   - 当有任务正在运行时，点击"⏹️ 停止任务"按钮
   - 确认停止操作
   - 任务会在下一个检查点（每个URL爬取完成后）停止

4. **刷新任务状态**
   - 点击右上角的"🔄 刷新"按钮
   - 手动刷新任务队列状态

### 任务状态说明

**🟢 处理中**
- 当前有任务正在执行
- 显示任务详细信息：
  - 用户名
  - 用户ID
  - 会话ID（前12位）
  - 任务类型（🕷️ 达人搜索）
  - 运行时间（分秒）

**⚪ 空闲**
- 当前没有任务运行
- API可以接受新的任务请求

**⏳ 停止中**
- 管理员已请求停止
- 任务正在等待下一个检查点

### 停止机制

任务停止是**优雅停止**，不会强制中断：

1. **检查点位置**
   - 每个URL爬取完成后
   - 不会中断单个URL的爬取过程

2. **停止流程**
   ```
   管理员点击停止 → 设置停止标记
                    ↓
         任务循环检查停止标记
                    ↓
        到达检查点 → 清除任务状态 → 抛出HTTP 499异常
                    ↓
         前端收到停止响应 → 任务停止
   ```

3. **数据完整性**
   - 已爬取的数据会保留
   - 未完成的URL不会爬取
   - 不会产生不完整的文件

## 测试方法

### 测试场景 1：查看任务状态

1. 启动服务：
   ```bash
   # 终端 1: Playwright API
   python start_api.py

   # 终端 2: Chatbot API
   python start_chatbot.py
   ```

2. 创建测试任务：
   - 打开聊天界面 http://127.0.0.1:8001
   - 登录用户账号
   - 开始一个推荐流程（输入商品、国家等）
   - 点击"确认"开始搜索

3. 查看任务队列：
   - 打开后台管理 http://127.0.0.1:8001/admin.html
   - 登录管理员账号
   - 点击"任务队列"标签
   - **预期结果**：
     - ✅ 看到当前任务正在运行
     - ✅ 显示用户名、任务类型、运行时间
     - ✅ 运行时间实时更新（需手动刷新）

### 测试场景 2：停止任务

1. 执行测试场景1，确保有任务正在运行

2. 停止任务：
   - 在任务队列页面点击"⏹️ 停止任务"
   - 确认操作
   - **预期结果**：
     - ✅ 按钮变为"⏳ 停止中..."（禁用状态）
     - ✅ 显示"⚠️ 已请求停止，等待任务响应..."

3. 观察任务停止：
   - 等待几秒钟
   - 点击"刷新"按钮
   - **预期结果**：
     - ✅ 任务状态变为"⚪ 空闲"
     - ✅ 当前任务信息消失
     - ✅ 用户端聊天界面收到错误提示

### 测试场景 3：并发任务处理

1. 创建多个用户账号

2. 同时发起多个任务：
   - 用户A：开始推荐流程 → 点击确认
   - 用户B：开始推荐流程 → 点击确认（会排队）

3. 查看任务队列：
   - 打开后台管理
   - 查看任务队列
   - **预期结果**：
     - ✅ 当前任务显示用户A的任务
     - ✅ 等待队列显示用户B的任务
     - ✅ 等待时间实时更新

4. 停止用户A的任务：
   - 点击停止
   - **预期结果**：
     - ✅ 用户A的任务停止
     - ✅ 系统自动开始处理用户B的任务

## 数据流图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户操作                              │
│  浏览器访问聊天界面 → 输入推荐需求 → 点击"确认"开始搜索      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Chatbot API (端口 8001)                         │
│  收到用户消息 → 调用 Agent → Agent 调用 ScrapeInfluencersTool│
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP POST /scrape
                            │ (包含 session_id, user_id, username)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│          Playwright API (端口 8000)                          │
│                                                              │
│  1. set_current_task(session_id, user_id, username)         │
│     ↓                                                        │
│  2. 开始爬取循环                                              │
│     for url in urls:                                         │
│         检查 is_stop_requested()                             │
│         如果停止 → 清除任务 → 抛出异常                        │
│         否则 → 继续爬取                                       │
│     ↓                                                        │
│  3. clear_current_task()                                     │
│     ↓                                                        │
│  4. 返回结果                                                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────────┐  ┌────────────────┐
│  管理员查看   │  │  管理员停止任务   │  │  用户收到结果   │
│              │  │                  │  │                │
│ GET /api/    │  │ POST /api/       │  │  聊天界面显示   │
│ admin/tasks  │  │ admin/tasks/stop │  │  报告或错误     │
│              │  │                  │  │                │
│  返回任务状态 │  │  设置停止标记     │  │                │
└──────────────┘  └──────────────────┘  └────────────────┘
```

## 注意事项

### 1. 单浏览器实例限制

目前系统使用单个浏览器实例，因此：
- ⚠️ 同一时间只能处理一个用户的任务
- ⚠️ 后续任务会自动排队等待
- ⚠️ 管理员停止任务会影响当前用户的体验

**未来改进**：
- 使用任务队列系统（如 Celery）
- 支持多浏览器实例并发处理

### 2. 停止时机

停止任务是在**检查点**停止，不是立即停止：
- ✅ 优点：数据完整性得到保证
- ⚠️ 缺点：如果当前URL有很多页，可能需要等待较长时间

**建议**：
- 尽量在任务开始后不久停止
- 避免在大量数据爬取中途停止

### 3. 会话信息准确性

任务队列显示的用户信息依赖于：
- Agent创建时传递的 `user_id` 和 `username`
- Session Manager 从数据库获取用户信息

**确保准确性**：
- Session Manager 必须正确查询用户表
- Agent 必须在创建时接收这些参数

## 故障排查

### 问题 1：任务队列页面显示"加载失败"

**可能原因**：
- Playwright API 服务（端口 8000）未启动

**解决方法**：
```bash
python start_api.py
```

### 问题 2：停止任务无响应

**可能原因**：
- 任务正在执行长时间操作（等待页面加载等）
- 任务已经接近完成

**解决方法**：
- 等待当前URL爬取完成
- 检查 Playwright API 终端日志

### 问题 3：用户名显示为"未知用户"

**可能原因**：
- Agent 创建时未传递 username
- Session Manager 查询用户失败

**解决方法**：
- 检查 session_manager_db.py 的 `_get_session_user_info()` 方法
- 检查数据库连接是否正常

## 总结

### 实现的功能

✅ **任务队列状态管理**：全局变量跟踪当前任务和队列
✅ **实时任务监控**：后台管理页面显示任务详情
✅ **优雅停止机制**：检查点停止，保证数据完整性
✅ **用户信息传递**：从Agent → Tool → API的完整链路
✅ **管理员控制台**：查看和停止任务的友好界面

### 技术栈

- **后端**: FastAPI (Playwright API)
- **前端**: Vanilla JavaScript (后台管理页面)
- **状态管理**: 全局Python字典（内存存储）
- **并发控制**: asyncio.Lock（异步锁）

### 修改的文件

1. **playwright_api.py** - 添加任务队列管理逻辑
2. **static/admin.html** - 更新任务队列页面UI
3. **agent.py** - 添加username参数
4. **agent_tools.py** - 传递会话信息到API
5. **session_manager_db.py** - 获取用户username

---

**功能已完成！管理员现在可以实时查看和控制任务队列。** 🎉
