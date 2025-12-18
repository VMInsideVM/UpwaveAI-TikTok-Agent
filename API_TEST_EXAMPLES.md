# 手机号认证 API 测试示例

## 📌 前提条件

1. 启动服务：`python chatbot_api.py` 或 `python start_chatbot.py`
2. 服务地址：`http://127.0.0.1:8001`
3. 确保有可用的邀请码（通过管理员生成）

---

## 🧪 API 端点测试

### 1️⃣ 发送短信验证码

**端点**: `POST /api/auth/send-sms-code`

**请求示例 (注册验证码)**:
```bash
curl -X POST http://127.0.0.1:8001/api/auth/send-sms-code \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "13800138000",
    "code_type": "register"
  }'
```

**请求示例 (重置密码验证码)**:
```bash
curl -X POST http://127.0.0.1:8001/api/auth/send-sms-code \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "13800138000",
    "code_type": "reset_password"
  }'
```

**成功响应** (200):
```json
{
  "message": "验证码已发送至 13800138000，5 分钟内有效",
  "phone_number": "13800138000",
  "expires_in_minutes": 5
}
```

**错误响应** (400 - 手机号已注册):
```json
{
  "detail": "该手机号已被注册"
}
```

**错误响应** (429 - 频率限制):
```json
{
  "detail": "该手机号每小时最多发送 5 次验证码，请稍后再试"
}
```

---

### 2️⃣ 手机号注册

**端点**: `POST /api/auth/register-phone`

**请求示例**:
```bash
curl -X POST http://127.0.0.1:8001/api/auth/register-phone \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "13800138000",
    "password": "Test123456",
    "sms_code": "123456",
    "invitation_code": "YOUR_INVITE_CODE",
    "username": "testuser",
    "email": "test@example.com"
  }'
```

**最小请求示例** (用户名和邮箱可选):
```bash
curl -X POST http://127.0.0.1:8001/api/auth/register-phone \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "13800138000",
    "password": "Test123456",
    "sms_code": "123456",
    "invitation_code": "YOUR_INVITE_CODE"
  }'
```

**成功响应** (201):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "bc5b6604-534b-4789-b8fc-4b72851a3ed0",
  "username": "testuser",
  "is_admin": false
}
```

**错误响应** (400 - 验证码错误):
```json
{
  "detail": "验证码错误，还剩 2 次尝试机会"
}
```

---

### 3️⃣ 手机号/用户名登录

**端点**: `POST /api/auth/login-phone`

**请求示例 (手机号登录)**:
```bash
curl -X POST http://127.0.0.1:8001/api/auth/login-phone \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "13800138000",
    "password": "Test123456"
  }'
```

**请求示例 (用户名登录)**:
```bash
curl -X POST http://127.0.0.1:8001/api/auth/login-phone \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "testuser",
    "password": "Test123456"
  }'
```

**成功响应** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": "bc5b6604-534b-4789-b8fc-4b72851a3ed0",
  "username": "testuser",
  "is_admin": false
}
```

**错误响应** (401):
```json
{
  "detail": "手机号/用户名或密码错误"
}
```

---

### 4️⃣ 重置密码

**端点**: `POST /api/auth/reset-password`

**请求示例**:
```bash
curl -X POST http://127.0.0.1:8001/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "13800138000",
    "sms_code": "123456",
    "new_password": "NewPass123"
  }'
```

**成功响应** (200):
```json
{
  "message": "密码重置成功",
  "phone_number": "13800138000"
}
```

**错误响应** (400 - 验证码错误):
```json
{
  "detail": "验证码错误，还剩 1 次尝试机会"
}
```

**错误响应** (404 - 手机号未注册):
```json
{
  "detail": "该手机号未注册"
}
```

---

### 5️⃣ 修改手机号 (需要登录)

**端点**: `POST /api/auth/change-phone`

**请求示例**:
```bash
curl -X POST http://127.0.0.1:8001/api/auth/change-phone \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "new_phone_number": "13900139000",
    "sms_code": "123456"
  }'
```

**成功响应** (200):
```json
{
  "message": "手机号修改成功",
  "old_phone": "13800138000",
  "new_phone": "13900139000"
}
```

**错误响应** (400 - 手机号已被使用):
```json
{
  "detail": "该手机号已被其他用户使用"
}
```

---

## 📊 完整测试流程示例

### 步骤 1: 发送注册验证码
```bash
curl -X POST http://127.0.0.1:8001/api/auth/send-sms-code \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "13800138000", "code_type": "register"}'
```

### 步骤 2: 使用验证码注册
```bash
curl -X POST http://127.0.0.1:8001/api/auth/register-phone \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "13800138000",
    "password": "Test123456",
    "sms_code": "从手机收到的验证码",
    "invitation_code": "从管理员获取的邀请码"
  }'
```

### 步骤 3: 使用手机号登录
```bash
curl -X POST http://127.0.0.1:8001/api/auth/login-phone \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "13800138000",
    "password": "Test123456"
  }'
```

### 步骤 4: 测试密码重置
```bash
# 4.1 发送重置密码验证码
curl -X POST http://127.0.0.1:8001/api/auth/send-sms-code \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "13800138000", "code_type": "reset_password"}'

# 4.2 重置密码
curl -X POST http://127.0.0.1:8001/api/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "13800138000",
    "sms_code": "从手机收到的验证码",
    "new_password": "NewPass123"
  }'
```

---

## 🔍 Postman 测试集合

如果使用 Postman，可以导入以下配置：

**环境变量**:
- `base_url`: `http://127.0.0.1:8001`
- `access_token`: (从登录响应中获取)
- `phone_number`: `13800138000`

**Collection 结构**:
```
FastMoss Phone Auth
├── 1. Send SMS Code (Register)
├── 2. Register with Phone
├── 3. Login with Phone
├── 4. Send SMS Code (Reset Password)
├── 5. Reset Password
└── 6. Change Phone (Requires Auth)
```

---

## ⚠️ 注意事项

1. **验证码有效期**: 5分钟
2. **验证码尝试次数**: 最多3次
3. **手机号频率限制**: 每小时最多发送5次
4. **IP频率限制**: 每小时最多发送20次
5. **密码要求**: 至少8位，包含字母和数字
6. **手机号格式**: 11位中国大陆手机号 (1[3-9]xxxxxxxxx)

---

## 🐛 常见错误排查

### 错误: "该手机号每小时最多发送 5 次验证码"
**原因**: 触发频率限制
**解决**: 等待1小时后重试，或清理数据库中的 `sms_verifications` 表

### 错误: "验证码不存在或已使用"
**原因**: 验证码已过期或已被验证
**解决**: 重新获取验证码

### 错误: "邀请码无效或已被使用"
**原因**: 邀请码不正确或已被使用
**解决**: 联系管理员获取新的邀请码

### 错误: "短信发送失败"
**原因**: 阿里云API调用失败
**解决**:
1. 检查 .env 中的阿里云配置
2. 确认阿里云短信服务已开通
3. 确认账户余额充足
4. 查看服务器日志获取详细错误信息

---

## 📖 API 文档

启动服务后，访问以下地址查看完整API文档：
- Swagger UI: `http://127.0.0.1:8001/docs`
- ReDoc: `http://127.0.0.1:8001/redoc`
