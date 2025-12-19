# 管理员API使用指南

## 概述

本文档介绍后台管理系统的所有API接口，包括用户管理、报告管理、会话管理等功能。

**基础URL**: `http://127.0.0.1:8001`

**认证方式**: Bearer Token（需要管理员权限）

---

## 认证

所有管理员API都需要在请求头中携带管理员的访问令牌：

```http
Authorization: Bearer <admin_access_token>
```

### 获取管理员Token

```bash
# 管理员登录
curl -X POST http://127.0.0.1:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin_password"
  }'
```

响应:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "user_id": "xxx",
    "username": "admin",
    "is_admin": true
  }
}
```

---

## 用户管理

### 1. 获取所有用户列表

**请求**:
```http
GET /api/admin/users?skip=0&limit=100
Authorization: Bearer <token>
```

**响应**:
```json
[
  {
    "user_id": "uuid",
    "username": "testuser",
    "email": "test@example.com",
    "phone_number": "13800138000",
    "is_active": true,
    "is_admin": false,
    "created_at": "2025-12-19T10:00:00",
    "last_login": "2025-12-19T12:00:00",
    "total_credits": 300,
    "used_credits": 200,
    "remaining_credits": 100
  }
]
```

### 2. 修改用户积分

**请求**:
```http
PUT /api/admin/users/{user_id}/credits
Authorization: Bearer <token>
Content-Type: application/json

{
  "new_credits": 500
}
```

**响应**:
```json
{
  "message": "积分更新成功",
  "user_id": "uuid",
  "username": "testuser",
  "new_credits": 500,
  "remaining": 300
}
```

**说明**:
- `new_credits` 是总积分（total_credits）
- `remaining` = `new_credits` - `used_credits`

### 3. 修改用户信息 🆕

**请求**:
```http
PUT /api/admin/users/{user_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "username": "new_username",
  "email": "new@example.com",
  "phone_number": "13900139000",
  "password": "new_password"
}
```

**参数说明**:
- 所有字段都是可选的，只传需要修改的字段
- `password`: 明文密码，后端会自动加密
- 用户名、邮箱、手机号会检查唯一性

**响应**:
```json
{
  "message": "用户信息更新成功",
  "user_id": "uuid",
  "old_info": {
    "username": "testuser",
    "email": "test@example.com",
    "phone_number": "13800138000"
  },
  "new_info": {
    "username": "new_username",
    "email": "new@example.com",
    "phone_number": "13900139000",
    "password_updated": true
  }
}
```

**错误响应**:
```json
{
  "detail": "用户名 'new_username' 已被使用"
}
```

### 4. 激活/停用用户

**请求**:
```http
POST /api/admin/users/{user_id}/toggle-active
Authorization: Bearer <token>
```

**响应**:
```json
{
  "message": "用户已停用",
  "user_id": "uuid",
  "username": "testuser",
  "is_active": false
}
```

**说明**:
- 停用的用户无法登录
- 不能停用自己的账户

### 5. 删除用户

**请求**:
```http
DELETE /api/admin/users/{user_id}
Authorization: Bearer <token>
```

**响应**:
```json
{
  "message": "用户 testuser 已被删除",
  "user_id": "uuid",
  "username": "testuser"
}
```

**说明**:
- 会级联删除用户的所有数据（积分、会话、消息、报告）
- 不能删除自己的账户

---

## 报告管理

### 1. 获取所有报告列表

**请求**:
```http
GET /api/admin/reports?skip=0&limit=100
Authorization: Bearer <token>
```

**响应**:
```json
[
  {
    "report_id": "uuid",
    "title": "美国市场口红达人推荐",
    "status": "completed",
    "user_id": "user_uuid",
    "username": "testuser",
    "created_at": "2025-12-19T10:00:00",
    "completed_at": "2025-12-19T10:05:00",
    "error_message": null
  }
]
```

**状态说明**:
- `pending`: 等待处理
- `processing`: 处理中
- `completed`: 已完成
- `failed`: 失败

### 2. 查看报告详情 🆕

**请求**:
```http
GET /api/admin/reports/{report_id}
Authorization: Bearer <token>
```

**响应**:
```json
{
  "report_id": "uuid",
  "title": "美国市场口红达人推荐",
  "status": "completed",
  "user_id": "user_uuid",
  "username": "testuser",
  "user_email": "test@example.com",
  "session_id": "session_uuid",
  "created_at": "2025-12-19T10:00:00",
  "completed_at": "2025-12-19T10:05:00",
  "report_path": "/path/to/report.html",
  "error_message": null,
  "report_content": "<html>...</html>",
  "report_data": null
}
```

**字段说明**:
- `report_content`:
  - 如果是HTML文件，返回完整的HTML内容
  - 如果是JSON文件，返回描述信息（如"JSON报告，包含10条数据"）
- `report_data`:
  - 如果是JSON文件，返回实际的JSON数据
  - 如果是HTML文件，为null

**用途**:
- 管理员可以查看任何用户的报告
- 可以直接在管理后台预览报告内容
- 可以导出报告数据

---

## 会话管理

### 1. 获取所有会话列表

**请求**:
```http
GET /api/admin/sessions?skip=0&limit=100
Authorization: Bearer <token>
```

**响应**:
```json
[
  {
    "session_id": "uuid",
    "user_id": "user_uuid",
    "username": "testuser",
    "title": "美国市场口红推荐",
    "created_at": "2025-12-19T10:00:00",
    "updated_at": "2025-12-19T10:30:00",
    "message_count": 15
  }
]
```

### 2. 查看会话消息

**请求**:
```http
GET /api/admin/sessions/{session_id}/messages
Authorization: Bearer <token>
```

**响应**:
```json
[
  {
    "message_id": "uuid",
    "role": "user",
    "content": "我需要推广口红，目标美国市场",
    "created_at": "2025-12-19T10:01:00"
  },
  {
    "message_id": "uuid",
    "role": "assistant",
    "content": "好的，我来帮您分析...",
    "created_at": "2025-12-19T10:01:05"
  }
]
```

**用途**:
- 监控用户对话内容
- 审计和质量检查
- 问题排查

---

## 任务队列管理

### 查看任务队列状态

**请求**:
```http
GET /api/admin/tasks
Authorization: Bearer <token>
```

**响应**:
```json
{
  "current_task": {
    "task_id": "uuid",
    "status": "processing",
    "user_id": "user_uuid",
    "created_at": "2025-12-19T10:00:00"
  },
  "queue_size": 3,
  "is_processing": true,
  "tasks": [
    {
      "task_id": "uuid",
      "status": "pending",
      "position": 1
    }
  ]
}
```

---

## 邀请码管理

### 1. 生成邀请码

**请求**:
```http
POST /api/admin/invitation-codes
Authorization: Bearer <token>
Content-Type: application/json

{
  "count": 10
}
```

**响应**:
```json
{
  "codes": [
    "ABCD1234EFGH5678",
    "IJKL9012MNOP3456"
  ],
  "count": 2,
  "message": "已生成 2 个永久有效的邀请码"
}
```

**说明**:
- 一次最多生成100个
- 邀请码永久有效
- 每个邀请码只能使用一次

### 2. 查看邀请码列表

**请求**:
```http
GET /api/admin/invitation-codes?skip=0&limit=100&show_used=true
Authorization: Bearer <token>
```

**参数**:
- `show_used`: 是否显示已使用的邀请码（默认true）

**响应**:
```json
[
  {
    "code_id": "uuid",
    "code": "ABCD1234EFGH5678",
    "is_used": false,
    "created_at": "2025-12-19T10:00:00",
    "used_at": null,
    "used_by_username": null
  },
  {
    "code_id": "uuid",
    "code": "IJKL9012MNOP3456",
    "is_used": true,
    "created_at": "2025-12-18T10:00:00",
    "used_at": "2025-12-18T15:00:00",
    "used_by_username": "testuser"
  }
]
```

---

## 统计信息

### 获取系统统计

**请求**:
```http
GET /api/admin/statistics
Authorization: Bearer <token>
```

**响应**:
```json
{
  "users": {
    "total": 50,
    "active": 45,
    "inactive": 5
  },
  "reports": {
    "total": 200,
    "completed": 180,
    "in_progress": 20
  },
  "sessions": {
    "total": 150,
    "avg_messages_per_session": 12.5
  },
  "invitation_codes": {
    "unused": 25
  }
}
```

---

## 使用示例

### Python 示例

```python
import requests

# 管理员登录
login_response = requests.post(
    "http://127.0.0.1:8001/api/auth/login",
    json={
        "email": "admin@example.com",
        "password": "admin_password"
    }
)
token = login_response.json()["access_token"]

# 设置请求头
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 1. 获取所有用户
users = requests.get(
    "http://127.0.0.1:8001/api/admin/users",
    headers=headers
).json()

print(f"总用户数: {len(users)}")

# 2. 修改用户信息
user_id = users[0]["user_id"]
update_response = requests.put(
    f"http://127.0.0.1:8001/api/admin/users/{user_id}",
    headers=headers,
    json={
        "username": "new_username",
        "email": "new@example.com",
        "password": "new_password"
    }
)
print(update_response.json())

# 3. 修改用户积分
credits_response = requests.put(
    f"http://127.0.0.1:8001/api/admin/users/{user_id}/credits",
    headers=headers,
    json={"new_credits": 1000}
)
print(credits_response.json())

# 4. 获取所有报告
reports = requests.get(
    "http://127.0.0.1:8001/api/admin/reports",
    headers=headers
).json()

# 5. 查看报告详情
if reports:
    report_id = reports[0]["report_id"]
    report_detail = requests.get(
        f"http://127.0.0.1:8001/api/admin/reports/{report_id}",
        headers=headers
    ).json()
    print(f"报告标题: {report_detail['title']}")
    print(f"报告用户: {report_detail['username']}")
    print(f"报告状态: {report_detail['status']}")

# 6. 生成邀请码
codes_response = requests.post(
    "http://127.0.0.1:8001/api/admin/invitation-codes",
    headers=headers,
    json={"count": 5}
)
codes = codes_response.json()["codes"]
print(f"生成的邀请码: {codes}")

# 7. 查看系统统计
stats = requests.get(
    "http://127.0.0.1:8001/api/admin/statistics",
    headers=headers
).json()
print(f"系统统计: {stats}")
```

### JavaScript 示例

```javascript
// 管理员登录
const loginResponse = await fetch('http://127.0.0.1:8001/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        email: 'admin@example.com',
        password: 'admin_password'
    })
});
const { access_token } = await loginResponse.json();

// 设置请求头
const headers = {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
};

// 1. 获取所有用户
const users = await fetch('http://127.0.0.1:8001/api/admin/users', {
    headers
}).then(r => r.json());

console.log(`总用户数: ${users.length}`);

// 2. 修改用户信息
const userId = users[0].user_id;
const updateResponse = await fetch(`http://127.0.0.1:8001/api/admin/users/${userId}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({
        username: 'new_username',
        email: 'new@example.com',
        password: 'new_password'
    })
});
console.log(await updateResponse.json());

// 3. 修改用户积分
const creditsResponse = await fetch(`http://127.0.0.1:8001/api/admin/users/${userId}/credits`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({ new_credits: 1000 })
});
console.log(await creditsResponse.json());

// 4. 获取所有报告
const reports = await fetch('http://127.0.0.1:8001/api/admin/reports', {
    headers
}).then(r => r.json());

// 5. 查看报告详情
if (reports.length > 0) {
    const reportId = reports[0].report_id;
    const reportDetail = await fetch(`http://127.0.0.1:8001/api/admin/reports/${reportId}`, {
        headers
    }).then(r => r.json());

    console.log('报告详情:', reportDetail);
}

// 6. 生成邀请码
const codesResponse = await fetch('http://127.0.0.1:8001/api/admin/invitation-codes', {
    method: 'POST',
    headers,
    body: JSON.stringify({ count: 5 })
});
const { codes } = await codesResponse.json();
console.log('生成的邀请码:', codes);

// 7. 查看系统统计
const stats = await fetch('http://127.0.0.1:8001/api/admin/statistics', {
    headers
}).then(r => r.json());
console.log('系统统计:', stats);
```

---

## API 完整清单

### 用户管理
- `GET /api/admin/users` - 获取所有用户
- `PUT /api/admin/users/{user_id}/credits` - 修改用户积分
- `PUT /api/admin/users/{user_id}` - 修改用户信息 🆕
- `POST /api/admin/users/{user_id}/toggle-active` - 激活/停用用户
- `DELETE /api/admin/users/{user_id}` - 删除用户

### 报告管理
- `GET /api/admin/reports` - 获取所有报告
- `GET /api/admin/reports/{report_id}` - 查看报告详情 🆕

### 会话管理
- `GET /api/admin/sessions` - 获取所有会话
- `GET /api/admin/sessions/{session_id}/messages` - 查看会话消息

### 任务队列
- `GET /api/admin/tasks` - 查看任务队列状态

### 邀请码管理
- `POST /api/admin/invitation-codes` - 生成邀请码
- `GET /api/admin/invitation-codes` - 查看邀请码列表

### 统计信息
- `GET /api/admin/statistics` - 获取系统统计

---

## 错误处理

### 常见错误码

| 状态码 | 说明 | 示例 |
|--------|------|------|
| 401 | 未授权 | 没有提供Token或Token无效 |
| 403 | 权限不足 | 非管理员用户访问管理员API |
| 404 | 资源不存在 | 用户ID或报告ID不存在 |
| 400 | 请求错误 | 参数格式错误、唯一性冲突 |
| 500 | 服务器错误 | 数据库错误、文件读取失败 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

### 示例

```json
// 401 未授权
{
  "detail": "Could not validate credentials"
}

// 403 权限不足
{
  "detail": "需要管理员权限"
}

// 404 资源不存在
{
  "detail": "用户不存在"
}

// 400 请求错误
{
  "detail": "用户名 'testuser' 已被使用"
}
```

---

## 安全建议

1. **Token安全**:
   - 不要在客户端代码中硬编码管理员Token
   - Token应该存储在安全的地方（如环境变量）
   - 定期轮换管理员密码

2. **API访问控制**:
   - 只有管理员用户可以访问这些API
   - 管理员不能删除或停用自己的账户
   - 所有敏感操作都会记录日志

3. **数据保护**:
   - 用户密码使用bcrypt加密存储
   - 删除用户会级联删除所有相关数据
   - 建议定期备份数据库

---

## 测试API

使用API文档界面测试（推荐）:

1. 启动服务后访问: http://127.0.0.1:8001/docs
2. 点击右上角"Authorize"按钮
3. 输入管理员的access_token
4. 点击各个API端点进行测试

使用curl测试:

```bash
# 1. 管理员登录获取Token
TOKEN=$(curl -s -X POST http://127.0.0.1:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin_password"}' \
  | jq -r '.access_token')

# 2. 获取所有用户
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8001/api/admin/users

# 3. 修改用户信息
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"new_name","email":"new@example.com"}' \
  http://127.0.0.1:8001/api/admin/users/{user_id}

# 4. 修改用户积分
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"new_credits":1000}' \
  http://127.0.0.1:8001/api/admin/users/{user_id}/credits

# 5. 获取所有报告
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8001/api/admin/reports

# 6. 查看报告详情
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8001/api/admin/reports/{report_id}

# 7. 生成邀请码
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"count":5}' \
  http://127.0.0.1:8001/api/admin/invitation-codes

# 8. 查看统计信息
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8001/api/admin/statistics
```

---

## 更新日志

### 2025-12-19
- 🆕 新增 `PUT /api/admin/users/{user_id}` - 修改用户信息（用户名、邮箱、手机号、密码）
- 🆕 新增 `GET /api/admin/reports/{report_id}` - 查看单个报告详情
- ✅ 管理员可以查看任何用户的报告内容
- ✅ 管理员可以修改用户的所有信息
- ✅ 所有修改操作都会进行唯一性检查
- ✅ 密码自动使用bcrypt加密
