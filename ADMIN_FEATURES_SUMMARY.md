# 管理员功能新增总结

## 更新日期
2025-12-19

## 概述

本次更新为后台管理系统新增了两个重要功能：
1. **修改用户信息**：管理员可以修改任何用户的用户名、邮箱、手机号和密码
2. **查看报告详情**：管理员可以查看任何用户报告的完整内容

---

## 新增功能详情

### 1. 修改用户信息 API

**端点**: `PUT /api/admin/users/{user_id}`

**功能**:
- 管理员可以修改用户的用户名
- 管理员可以修改用户的邮箱
- 管理员可以修改用户的手机号
- 管理员可以重置用户的密码

**特性**:
- ✅ 所有字段都是可选的，只需传递要修改的字段
- ✅ 自动检查用户名、邮箱、手机号的唯一性
- ✅ 密码自动使用 bcrypt 加密
- ✅ 返回修改前后的信息对比

**请求示例**:
```json
{
  "username": "new_username",
  "email": "new@example.com",
  "phone_number": "13900139000",
  "password": "new_password"
}
```

**响应示例**:
```json
{
  "message": "用户信息更新成功",
  "user_id": "uuid",
  "old_info": {
    "username": "old_username",
    "email": "old@example.com",
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

**错误处理**:
- 用户不存在 → 404
- 用户名已被使用 → 400
- 邮箱已被使用 → 400
- 手机号已被使用 → 400

### 2. 查看报告详情 API

**端点**: `GET /api/admin/reports/{report_id}`

**功能**:
- 管理员可以查看任何用户的报告详情
- 自动读取报告文件内容（HTML或JSON）
- 返回报告的所有元信息

**返回数据**:
- 报告基本信息（ID、标题、状态）
- 用户信息（用户名、邮箱）
- 会话信息（session_id）
- 时间信息（创建时间、完成时间）
- 报告内容（HTML内容或JSON数据）
- 错误信息（如果失败）

**响应示例**:
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

**特殊处理**:
- HTML报告：返回完整的HTML内容
- JSON报告：返回JSON数据数组 + 描述信息
- 文件不存在：返回错误信息

---

## 修改的文件

### 1. api/admin.py

**新增内容**:
```python
# 1. 新增 Pydantic 模型
class UpdateUserInfoRequest(BaseModel):
    """更新用户信息请求"""
    username: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    password: Optional[str] = None

# 2. 新增修改用户信息端点
@router.put("/users/{user_id}")
async def update_user_info(...)

# 3. 新增查看报告详情端点
@router.get("/reports/{report_id}")
async def get_report_detail(...)
```

**代码行数**:
- `UpdateUserInfoRequest`: 第42-47行
- `update_user_info`: 第190-279行（90行）
- `get_report_detail`: 第361-417行（57行）

---

## 使用场景

### 场景 1: 用户忘记密码

**问题**: 用户忘记密码无法登录

**解决方案**:
```bash
# 管理员重置密码
curl -X PUT http://127.0.0.1:8001/api/admin/users/{user_id} \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{"password": "temporary_password_123"}'

# 通知用户新密码
```

### 场景 2: 用户信息错误

**问题**: 用户注册时填写了错误的邮箱或手机号

**解决方案**:
```bash
# 管理员修正信息
curl -X PUT http://127.0.0.1:8001/api/admin/users/{user_id} \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "correct@example.com",
    "phone_number": "13900000000"
  }'
```

### 场景 3: 查看用户报告内容

**问题**: 用户报告出现错误，管理员需要查看详情

**解决方案**:
```bash
# 1. 获取报告列表
curl http://127.0.0.1:8001/api/admin/reports \
  -H "Authorization: Bearer {admin_token}"

# 2. 查看具体报告
curl http://127.0.0.1:8001/api/admin/reports/{report_id} \
  -H "Authorization: Bearer {admin_token}"

# 3. 查看报告内容和错误信息
```

### 场景 4: 批量修改用户信息

**问题**: 需要批量更新多个用户的信息

**解决方案**:
```python
import requests

admin_token = "..."
headers = {"Authorization": f"Bearer {admin_token}"}

# 获取所有用户
users = requests.get(
    "http://127.0.0.1:8001/api/admin/users",
    headers=headers
).json()

# 批量修改
for user in users:
    if user['username'].startswith('test_'):
        # 给测试用户统一重置密码
        requests.put(
            f"http://127.0.0.1:8001/api/admin/users/{user['user_id']}",
            headers=headers,
            json={"password": "test123"}
        )
```

---

## 安全考虑

### 1. 权限控制

✅ **已实现**:
- 所有管理员API都需要管理员Token
- 使用 `get_current_admin_user` 依赖验证权限
- 非管理员无法访问这些端点

### 2. 数据验证

✅ **已实现**:
- 用户名、邮箱、手机号唯一性检查
- 防止修改为已存在的值
- 密码使用bcrypt加密存储

### 3. 操作日志

⚠️ **建议实现**:
```python
# 记录管理员操作
@router.put("/users/{user_id}")
async def update_user_info(...):
    # 修改前记录日志
    log_admin_action(
        admin_id=admin_user.user_id,
        action="update_user_info",
        target_user_id=user_id,
        changes=request.dict()
    )

    # 执行修改...
```

### 4. 敏感信息保护

✅ **已实现**:
- 密码以明文传输但立即加密
- 建议使用HTTPS加密传输
- 返回结果不包含密码哈希

---

## 测试方法

### 自动化测试

运行测试脚本:
```bash
python test_admin_api.py
```

测试内容:
- ✅ 管理员登录
- ✅ 修改用户名
- ✅ 修改邮箱
- ✅ 修改手机号
- ✅ 修改密码
- ✅ 一次性修改多个字段
- ✅ 唯一性检查
- ✅ 查看报告详情

### 手动测试

使用API文档:
1. 访问 http://127.0.0.1:8001/docs
2. 点击 "Authorize" 输入管理员Token
3. 测试 `PUT /api/admin/users/{user_id}`
4. 测试 `GET /api/admin/reports/{report_id}`

---

## API完整列表

### 用户管理
| 方法 | 端点 | 功能 | 状态 |
|------|------|------|------|
| GET | /api/admin/users | 获取所有用户 | ✅ 已有 |
| PUT | /api/admin/users/{user_id}/credits | 修改用户积分 | ✅ 已有 |
| PUT | /api/admin/users/{user_id} | 修改用户信息 | 🆕 新增 |
| POST | /api/admin/users/{user_id}/toggle-active | 激活/停用用户 | ✅ 已有 |
| DELETE | /api/admin/users/{user_id} | 删除用户 | ✅ 已有 |

### 报告管理
| 方法 | 端点 | 功能 | 状态 |
|------|------|------|------|
| GET | /api/admin/reports | 获取所有报告列表 | ✅ 已有 |
| GET | /api/admin/reports/{report_id} | 查看报告详情 | 🆕 新增 |

### 其他功能
| 方法 | 端点 | 功能 | 状态 |
|------|------|------|------|
| GET | /api/admin/sessions | 获取所有会话 | ✅ 已有 |
| GET | /api/admin/sessions/{session_id}/messages | 查看会话消息 | ✅ 已有 |
| GET | /api/admin/tasks | 查看任务队列 | ✅ 已有 |
| POST | /api/admin/invitation-codes | 生成邀请码 | ✅ 已有 |
| GET | /api/admin/invitation-codes | 查看邀请码列表 | ✅ 已有 |
| GET | /api/admin/statistics | 获取系统统计 | ✅ 已有 |

---

## 与之前功能的对比

### 用户管理增强

**之前**:
- 只能修改积分
- 只能激活/停用账户
- 只能删除用户

**现在**:
- ✅ 可以修改用户名
- ✅ 可以修改邮箱
- ✅ 可以修改手机号
- ✅ 可以重置密码
- ✅ 可以一次性修改多个字段
- ✅ 修改前后信息对比

### 报告管理增强

**之前**:
- 只能看报告列表
- 只能看基本信息（标题、状态、用户）
- 无法查看报告内容

**现在**:
- ✅ 可以查看报告详情
- ✅ 可以读取HTML报告内容
- ✅ 可以读取JSON报告数据
- ✅ 可以看到用户邮箱
- ✅ 可以看到会话ID
- ✅ 可以看到错误信息

---

## 常见问题

### Q1: 如何修改管理员自己的密码？

**A**: 有两种方式：

方式1 - 使用修改用户信息API:
```bash
curl -X PUT http://127.0.0.1:8001/api/admin/users/{admin_user_id} \
  -H "Authorization: Bearer {admin_token}" \
  -d '{"password": "new_admin_password"}'
```

方式2 - 使用普通用户的修改密码功能（如果已实现）

### Q2: 修改用户信息后，用户是否需要重新登录？

**A**:
- 修改用户名/邮箱/手机号：不需要重新登录（Token仍然有效）
- 修改密码：下次登录时使用新密码

### Q3: 如何查看JSON格式的报告数据？

**A**: 使用报告详情API，如果报告是JSON格式，会在 `report_data` 字段返回实际数据：
```python
response = requests.get(
    f"http://127.0.0.1:8001/api/admin/reports/{report_id}",
    headers={"Authorization": f"Bearer {token}"}
)
data = response.json()

if data['report_data']:
    influencers = data['report_data']  # JSON数组
    print(f"包含 {len(influencers)} 个达人")
```

### Q4: 批量修改用户信息的最佳实践？

**A**:
```python
import requests
import time

def batch_update_users(admin_token, updates):
    """批量更新用户信息

    Args:
        admin_token: 管理员Token
        updates: [{"user_id": "xxx", "changes": {...}}, ...]
    """
    headers = {"Authorization": f"Bearer {admin_token}"}
    results = []

    for item in updates:
        try:
            response = requests.put(
                f"http://127.0.0.1:8001/api/admin/users/{item['user_id']}",
                headers=headers,
                json=item['changes']
            )
            results.append({
                "user_id": item['user_id'],
                "success": response.status_code == 200,
                "result": response.json()
            })
            time.sleep(0.1)  # 避免过于频繁的请求
        except Exception as e:
            results.append({
                "user_id": item['user_id'],
                "success": False,
                "error": str(e)
            })

    return results

# 使用示例
updates = [
    {"user_id": "user1", "changes": {"password": "newpass123"}},
    {"user_id": "user2", "changes": {"email": "new@example.com"}},
]
results = batch_update_users(admin_token, updates)
```

### Q5: 如何导出所有报告的数据？

**A**:
```python
import requests
import json

admin_token = "..."
headers = {"Authorization": f"Bearer {admin_token}"}

# 1. 获取所有报告
reports = requests.get(
    "http://127.0.0.1:8001/api/admin/reports?limit=1000",
    headers=headers
).json()

# 2. 逐个获取详情并导出
all_reports_data = []

for report in reports:
    detail = requests.get(
        f"http://127.0.0.1:8001/api/admin/reports/{report['report_id']}",
        headers=headers
    ).json()

    all_reports_data.append(detail)

# 3. 保存为JSON
with open('all_reports.json', 'w', encoding='utf-8') as f:
    json.dump(all_reports_data, f, ensure_ascii=False, indent=2)

print(f"已导出 {len(all_reports_data)} 个报告")
```

---

## 文档清单

本次更新创建的文档:
1. ✅ [ADMIN_API_GUIDE.md](ADMIN_API_GUIDE.md) - 详细的API使用指南
2. ✅ [ADMIN_FEATURES_SUMMARY.md](ADMIN_FEATURES_SUMMARY.md) - 本文档
3. ✅ [test_admin_api.py](test_admin_api.py) - 自动化测试脚本

相关已有文档:
- [api/admin.py](api/admin.py) - 管理员API实现代码

---

## 总结

### 新增功能

✅ **修改用户信息**:
- 支持修改用户名、邮箱、手机号、密码
- 自动唯一性检查
- 密码自动加密
- 返回修改前后对比

✅ **查看报告详情**:
- 支持查看任何用户的报告
- 自动读取HTML/JSON内容
- 返回完整的元信息
- 包含用户和会话信息

### 技术亮点

- 🔒 **安全**: 管理员权限验证、唯一性检查、密码加密
- 🎯 **灵活**: 字段可选、批量操作、多格式支持
- 📝 **完善**: 详细文档、自动化测试、错误处理
- 🚀 **高效**: RESTful设计、JSON响应、易于集成

### 使用建议

1. **定期备份数据库**（修改用户信息前）
2. **记录管理员操作**（便于审计）
3. **使用HTTPS传输**（保护敏感数据）
4. **设置操作限制**（防止误操作）
5. **测试后再部署**（运行test_admin_api.py）
