# 修复后台管理系统任务队列加载失败问题

## 问题描述

后台管理系统中的"任务队列"标签页显示"加载失败"错误消息：
```
加载失败
请确保 Playwright API 服务 (端口 8000) 正在运行
```

但实际上 Playwright API 服务（端口 8000）正在正常运行，其他功能都正常。

## 根本原因

**文件**: `api/admin.py` (Lines 660-675)

**问题**: `/api/admin/tasks` 端点返回的 JSON 响应缺少 `success` 字段

**之前的响应格式**:
```json
{
  "current_task": "...",
  "queue_size": 0,
  "is_processing": false,
  "tasks": []
}
```

**前端期望的格式** (`static/admin.html` Line 1734):
```javascript
async function loadTasks() {
    const response = await fetch(`${API_BASE_URL}/api/admin/tasks`);
    const data = await response.json();

    if (!data.success) {  // ⚠️ 检查 success 字段
        throw new Error(data.error || '加载失败');
    }
    // ...
}
```

## 解决方案

### 修改 1: 添加 success 字段

**文件**: `api/admin.py` (Lines 660-686)

```python
@router.get("/tasks")
async def view_task_queue(
    admin_user: User = Depends(get_current_admin_user)
):
    """
    查看当前报告生成队列状态
    """
    try:
        queue_info = report_queue.get_all_tasks()

        return {
            "success": True,  # 🔥 添加 success 字段
            "current_task": queue_info["current_task"],
            "queue_size": queue_info["queue_size"],
            "is_processing": queue_info["is_processing"],
            "tasks": queue_info["all_statuses"]
        }
    except Exception as e:
        # 返回错误信息而不是抛出异常，避免前端显示混乱
        return {
            "success": False,
            "error": f"获取任务队列失败: {str(e)}",
            "current_task": None,
            "queue_size": 0,
            "is_processing": False,
            "tasks": []
        }
```

### 修改内容

1. ✅ 添加 `"success": True` 字段到成功响应
2. ✅ 添加 `try-except` 异常处理
3. ✅ 错误时返回 `"success": False` 和 `"error"` 消息
4. ✅ 提供默认值避免前端解析错误

## 修复后的效果

### 成功响应

```json
{
  "success": true,
  "current_task": "report_abc123",
  "queue_size": 2,
  "is_processing": true,
  "tasks": [
    {
      "report_id": "report_abc123",
      "status": "generating",
      "progress": 45,
      ...
    },
    {
      "report_id": "report_def456",
      "status": "queued",
      "queue_position": 1,
      ...
    }
  ]
}
```

### 错误响应

```json
{
  "success": false,
  "error": "获取任务队列失败: ...",
  "current_task": null,
  "queue_size": 0,
  "is_processing": false,
  "tasks": []
}
```

## 测试验证

### 1. 启动服务

```bash
# 确保主 API 服务运行
python main_api.py
```

### 2. 访问管理后台

```
http://127.0.0.1:8001/admin.html
```

### 3. 检查任务队列

1. 登录管理员账户
2. 点击"⚙️ 任务队列"标签
3. 应该显示：
   - ✅ 当前任务信息（如果有）
   - ✅ 队列大小
   - ✅ 处理状态
   - ✅ 任务列表

### 4. 预期结果

**之前**:
```
加载失败
请确保 Playwright API 服务 (端口 8000) 正在运行
```

**现在**:
```
任务队列状态

📊 当前任务
无任务运行

📦 队列信息
队列大小: 0
处理状态: 空闲

📋 任务列表
暂无任务
```

## API 端点说明

### GET /api/admin/tasks

**认证**: 需要管理员权限

**响应格式**:
```typescript
{
  success: boolean;
  current_task?: string;        // 当前处理的报告ID
  queue_size: number;            // 队列中等待的任务数量
  is_processing: boolean;        // 是否正在处理任务
  tasks: Array<{                 // 所有任务列表
    report_id: string;
    status: string;              // queued, generating, completed, failed
    progress?: number;           // 0-100
    queue_position?: number;     // 队列位置（仅queued状态）
    ...
  }>;
  error?: string;                // 错误信息（success=false时）
}
```

## 相关文件

- [api/admin.py](api/admin.py) - 管理员 API 端点
- [static/admin.html](static/admin.html) - 管理后台前端
- [background/report_queue.py](background/report_queue.py) - 报告队列管理

## 其他说明

这个问题与 Playwright API 服务（端口 8000）无关。任务队列是主 API 服务（端口 8001）的一部分，不依赖 Playwright API。错误消息"请确保 Playwright API 服务 (端口 8000) 正在运行"是误导性的，是前端的通用错误提示。

实际问题是 API 响应格式不匹配导致前端解析失败。

---

**修复日期**: 2025-01-11
**修复者**: Claude Code
**状态**: ✅ 已修复
