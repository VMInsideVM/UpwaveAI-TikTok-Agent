# 删除会话时的报告警告功能实现

## 功能概述

当用户删除聊天会话时，系统会自动检测该会话关联的报告数量，并在确认弹窗中明确提示用户：
- 对话历史将被永久删除
- 关联的报告（如果有）也将被一并删除
- 此操作无法撤销

## 实现细节

### 1. 后端 API 端点

**文件**: `chatbot_api.py`

**新增端点**: `GET /api/sessions/{session_id}/reports`

```python
@app.get("/api/sessions/{session_id}/reports")
async def get_session_reports(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取指定会话关联的所有报告（需要认证和权限验证）"""
    # 验证权限
    if not session_manager.verify_session_access(session_id, current_user.user_id):
        raise HTTPException(status_code=403, detail="无权访问此会话")

    # 查询关联报告
    with get_db_context() as db:
        reports = db.query(Report).filter(
            Report.session_id == session_id
        ).all()

        # 返回报告列表
        return JSONResponse({
            "session_id": session_id,
            "total": len(reports),
            "reports": [...]  # 报告详情
        })
```

**返回数据结构**:
```json
{
  "session_id": "xxx",
  "total": 3,
  "reports": [
    {
      "report_id": "yyy",
      "title": "女士香水推荐报告",
      "status": "completed",
      "report_type": "influencer_recommendation",
      "created_at": "2025-01-15T10:30:00"
    },
    ...
  ]
}
```

### 2. 前端交互流程

**文件**: `static/index.html`

**修改的函数**: `deleteSession(sid)`

#### 流程说明

**步骤 1: 获取关联报告数量**
```javascript
let relatedReportsCount = 0;
try {
    const reportsResponse = await fetch(`${API_BASE_URL}/api/sessions/${sid}/reports`, {
        headers: {
            'Authorization': `Bearer ${accessToken}`
        }
    });

    if (reportsResponse.ok) {
        const reportsData = await reportsResponse.json();
        relatedReportsCount = reportsData.total || 0;
    }
} catch (error) {
    console.warn('⚠️ 无法获取关联报告数量:', error);
    // 即使失败也继续执行删除流程
}
```

**步骤 2: 构建警告消息**
```javascript
let confirmMessage = '确定要删除这个对话吗？\n\n';
confirmMessage += '⚠️ 警告：\n';
confirmMessage += '• 对话历史将被永久删除\n';

if (relatedReportsCount > 0) {
    confirmMessage += `• 关联的 ${relatedReportsCount} 个报告也将被删除\n`;
} else {
    confirmMessage += '• 该对话暂无关联报告\n';
}

confirmMessage += '\n此操作无法撤销，请谨慎操作！';
```

**步骤 3: 显示确认弹窗**
```javascript
if (!confirm(confirmMessage)) {
    return;  // 用户取消删除
}
```

**步骤 4: 执行删除**
```javascript
const response = await fetch(`${API_BASE_URL}/api/sessions/${sid}`, {
    method: 'DELETE',
    headers: {
        'Authorization': `Bearer ${accessToken}`
    }
});
```

## 用户体验

### 场景 1：删除有报告的会话

用户点击会话的"删除"按钮 → 系统弹窗：

```
确定要删除这个对话吗？

⚠️ 警告：
• 对话历史将被永久删除
• 关联的 3 个报告也将被删除

此操作无法撤销，请谨慎操作！

[取消] [确定]
```

### 场景 2：删除无报告的会话

用户点击会话的"删除"按钮 → 系统弹窗：

```
确定要删除这个对话吗？

⚠️ 警告：
• 对话历史将被永久删除
• 该对话暂无关联报告

此操作无法撤销，请谨慎操作！

[取消] [确定]
```

### 场景 3：无法获取报告信息（网络错误）

即使无法获取报告数量，删除流程仍然继续：

```
确定要删除这个对话吗？

⚠️ 警告：
• 对话历史将被永久删除
• 该对话暂无关联报告

此操作无法撤销，请谨慎操作！

[取消] [确定]
```

控制台输出：
```
⚠️ 无法获取关联报告数量: NetworkError
```

## 安全性和权限

### 1. API 权限验证

```python
# 验证用户是否有权访问此会话
if not session_manager.verify_session_access(session_id, current_user.user_id):
    raise HTTPException(status_code=403, detail="无权访问此会话")
```

**规则**:
- 只有会话所有者可以查看关联报告
- 管理员可以查看所有会话的报告

### 2. 错误处理

**前端**:
- 如果获取报告数量失败，不阻止删除流程
- 在控制台输出警告，方便调试
- 默认显示"暂无关联报告"

**后端**:
- 捕获数据库查询异常
- 返回友好的错误消息
- 记录详细的错误堆栈（用于调试）

## 数据库级联删除

**注意**: 实际的报告删除由数据库外键级联删除规则处理。

在 `database/models.py` 中：

```python
class Report(Base):
    __tablename__ = 'reports'

    session_id = Column(String(36), ForeignKey('chat_sessions.session_id', ondelete='CASCADE'))
```

**`ondelete='CASCADE'`** 的作用：
- 当会话被删除时，数据库自动删除关联的所有报告
- 前端弹窗仅用于**警告用户**，实际删除由数据库处理

## 测试场景

### 测试 1：有报告的会话

**准备**:
1. 创建一个会话
2. 生成 2-3 个报告
3. 点击删除按钮

**预期**:
- 弹窗显示："关联的 3 个报告也将被删除"
- 确认后，会话和报告都被删除
- 刷新报告库，不再显示这些报告

### 测试 2：无报告的会话

**准备**:
1. 创建一个新会话
2. 只发送几条消息，不生成报告
3. 点击删除按钮

**预期**:
- 弹窗显示："该对话暂无关联报告"
- 确认后，会话被删除

### 测试 3：网络错误

**准备**:
1. 在开发者工具中，将网络调节为"Offline"
2. 尝试删除会话

**预期**:
- 控制台输出警告："⚠️ 无法获取关联报告数量"
- 仍然显示确认弹窗（默认"暂无关联报告"）
- 如果网络恢复，删除请求正常执行

### 测试 4：权限验证

**准备**:
1. 用户 A 创建会话
2. 用户 B 尝试访问 `/api/sessions/{A的会话ID}/reports`

**预期**:
- 返回 403 Forbidden
- 错误消息："无权访问此会话"

## 与响应验证器的集成

这两个功能（删除警告和响应验证器）是独立的：

| 功能 | 触发时机 | 作用 |
|------|---------|------|
| **删除警告** | 用户点击删除会话按钮 | 警告用户关联报告也会被删除 |
| **响应验证器** | Agent 返回响应时 | 检测 Agent 是否正确展示参数 |

它们可以同时工作，互不干扰。

## 未来改进

### 1. 更美观的弹窗

使用自定义模态框代替原生 `confirm()`:

```javascript
// 创建自定义弹窗组件
function showDeleteConfirmModal(sessionId, reportsCount) {
    return new Promise((resolve) => {
        // 显示模态框
        const modal = createModal({
            title: '⚠️ 确认删除',
            content: `
                <p>确定要删除这个对话吗？</p>
                <ul>
                    <li>对话历史将被永久删除</li>
                    ${reportsCount > 0
                        ? `<li class="warning">关联的 ${reportsCount} 个报告也将被删除</li>`
                        : '<li>该对话暂无关联报告</li>'
                    }
                </ul>
                <p class="danger">此操作无法撤销，请谨慎操作！</p>
            `,
            buttons: [
                { text: '取消', onClick: () => resolve(false) },
                { text: '确认删除', class: 'danger', onClick: () => resolve(true) }
            ]
        });
    });
}
```

### 2. 显示报告详情

在确认弹窗中列出报告标题：

```
确定要删除这个对话吗？

⚠️ 警告：
• 对话历史将被永久删除
• 以下 3 个报告也将被删除：
  - 女士香水推荐报告 (已完成)
  - 运动鞋达人分析 (已完成)
  - 瑜伽垫推荐 (处理中)

此操作无法撤销，请谨慎操作！
```

### 3. 软删除

不立即删除数据，而是标记为"已删除"：

```python
# database/models.py
class ChatSession(Base):
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

# 删除时
session.is_deleted = True
session.deleted_at = datetime.now()
```

**优点**:
- 可以恢复误删的数据
- 保留审计日志

**缺点**:
- 占用存储空间
- 需要定期清理

## 总结

✅ **已实现**:
1. 后端 API 端点：`GET /api/sessions/{session_id}/reports`
2. 前端获取关联报告数量
3. 构建详细的警告消息
4. 显示确认弹窗
5. 权限验证和错误处理

✅ **用户体验**:
- 清晰的警告信息
- 明确告知关联报告数量
- 强调操作不可撤销

✅ **安全性**:
- 只有会话所有者可以查看关联报告
- 即使 API 失败也不影响删除流程
- 数据库级联删除确保数据一致性

这个功能大大提高了用户体验，防止用户误删重要数据！
