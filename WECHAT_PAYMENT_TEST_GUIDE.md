# 微信支付测试指南
**WeChat Payment Test Guide**

生成时间: 2025-12-27

---

## ✅ 配置验证

### 当前配置状态

| 配置项 | 值 | 状态 |
|--------|-----|------|
| **商户号** | `<见.env配置>` | ✅ |
| **AppID** | `<见.env配置>` | ✅ |
| **APIv3密钥** | `<见.env配置>` | ✅ |
| **证书序列号** | `<见.env配置>` | ✅ |
| **商户私钥** | `certs/wechat/apiclient_key.pem` | ✅ (1704字节) |
| **平台证书** | `certs/wechat/pub_key.pem` | ✅ (451字节) |
| **回调URL** | `https://foreignly-harmonizable-hosea.ngrok-free.dev/api/payment/callback/wechat` | ✅ |

### 服务状态

✅ **聊天机器人服务已启动**
- **地址**: http://127.0.0.1:8001
- **进程ID**: 68416
- **健康检查**: ✅ 正常
- **微信支付配置**: ✅ 已加载

---

## 🧪 测试步骤

### 步骤1: 登录系统

1. 打开浏览器访问: http://127.0.0.1:8001
2. 使用您的账号登录
3. 确保账户有足够权限

### 步骤2: 发起充值

1. 点击顶部右侧的 **💳 充值** 按钮
2. 在充值弹窗中选择任意套餐
3. **重要**: 选择 **微信支付** 作为支付方式
4. 点击 **立即支付** 按钮

### 步骤3: 查看支付二维码

系统会：
1. 调用微信支付API创建订单
2. 生成支付二维码
3. 在弹窗中显示二维码

**预期结果**:
- ✅ 成功显示二维码
- ✅ 显示订单金额和订单号
- ✅ 显示倒计时（15分钟）

### 步骤4: 扫码支付

1. 使用**微信扫一扫**功能扫描二维码
2. 在微信中确认支付金额
3. 输入支付密码完成支付

**预期结果**:
- ✅ 微信提示支付成功
- ✅ 网页自动检测到支付成功
- ✅ 弹窗自动关闭
- ✅ 积分自动到账

### 步骤5: 验证结果

1. **查看积分余额**: 顶部应显示新增的积分
2. **查看订单记录**:
   - 点击用户头像 → 💳 我的订单
   - 应看到订单状态为"已支付"
3. **查看积分历史**:
   - 点击"剩余积分"徽章
   - 应看到充值记录

---

## 🔍 调试方法

### 查看后端日志

订单创建和支付过程中，后台会打印详细日志：

```bash
# 查看实时日志
tail -f C:\Users\Hank\AppData\Local\Temp\claude\...\tasks\b02634b.output
```

**关键日志**:
```
创建微信支付订单...
商户号: <YOUR_MCH_ID>
订单号: ORD20251227...
金额: 299 (分)
✅ 微信支付订单创建成功
二维码URL: weixin://wxpay/...
```

### 检查回调接收

支付成功后，微信会向以下URL发送回调：
```
https://foreignly-harmonizable-hosea.ngrok-free.dev/api/payment/callback/wechat
```

**回调日志示例**:
```
收到微信支付回调通知
订单号: ORD20251227...
交易号: 4200002468202512271234567890
✅ 回调验证成功
✅ 订单状态已更新为已支付
✅ 积分已发放
```

### 常见问题排查

#### 问题1: 二维码无法生成

**可能原因**:
- 证书文件路径错误
- 商户私钥不正确
- APIv3密钥配置错误

**解决方法**:
```bash
# 检查证书文件
ls -la certs/wechat/
# 应看到:
# apiclient_key.pem (1704字节)
# pub_key.pem (451字节)

# 验证配置加载
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('WECHAT_MCH_ID'))"
```

#### 问题2: 扫码后提示订单不存在

**可能原因**:
- 商户号配置错误
- AppID配置错误

**解决方法**:
检查 `.env` 文件中的配置是否与微信支付后台一致。

#### 问题3: 支付成功但积分未到账

**可能原因**:
- 回调URL无法访问
- 回调验证签名失败
- ngrok隧道中断

**解决方法**:
```bash
# 1. 确认ngrok隧道正常
curl https://foreignly-harmonizable-hosea.ngrok-free.dev/api/health

# 2. 手动触发回调（测试环境）
# 查看订单列表，找到待支付订单
# 点击"去付款"按钮，在开发者工具中查看网络请求

# 3. 检查回调日志
# 查看是否收到微信的回调请求
```

#### 问题4: 证书验证失败

**错误信息**: `证书序列号不匹配` 或 `签名验证失败`

**解决方法**:
```bash
# 1. 验证证书序列号
openssl x509 -in certs/wechat/pub_key.pem -noout -serial
# 输出应该包含你在 .env 中配置的证书序列号

# 2. 如果不匹配，需要重新下载平台证书
# 从微信支付商户平台下载最新的平台证书
```

---

## 📊 测试场景

### 场景1: 正常支付流程

1. ✅ 用户选择微信支付
2. ✅ 系统生成订单和二维码
3. ✅ 用户扫码支付成功
4. ✅ 微信发送回调通知
5. ✅ 系统验证回调签名
6. ✅ 更新订单状态为已支付
7. ✅ 发放积分到用户账户
8. ✅ 记录积分变动历史

### 场景2: 订单超时

1. 用户创建订单但不支付
2. 等待15分钟
3. ✅ 订单自动过期
4. ✅ 状态显示为"已过期"
5. ✅ 无法再次支付此订单

### 场景3: 重复支付

1. 用户完成支付
2. 微信发送回调通知
3. 系统更新订单状态
4. 微信再次发送回调（重试机制）
5. ✅ 系统检测到订单已支付
6. ✅ 不重复发放积分
7. ✅ 返回成功响应

---

## 🔐 安全检查

### 回调验证

微信支付回调会进行以下验证：

1. **签名验证**:
   - 使用微信平台证书验证签名
   - 确保请求来自微信服务器

2. **时间戳验证**:
   - 检查请求时间戳
   - 防止重放攻击

3. **订单状态验证**:
   - 检查订单是否已支付
   - 防止重复发放积分

### 证书安全

**重要提醒**:
- ⚠️ `apiclient_key.pem` 是商户私钥，务必妥善保管
- ⚠️ 不要将私钥提交到Git仓库
- ⚠️ 定期更换APIv3密钥
- ⚠️ 使用HTTPS传输支付信息

---

## 📝 API端点

### 1. 创建订单
```
POST /api/payment/orders
Content-Type: application/json
Authorization: Bearer <token>

{
  "tier_id": "tier_299",
  "payment_method": "wechat"
}
```

**响应**:
```json
{
  "order_id": "uuid",
  "order_no": "ORD20251227...",
  "payment_url": "weixin://wxpay/bizpayurl?pr=...",
  "qr_code_base64": "data:image/png;base64,...",
  "amount_yuan": 299,
  "credits": 1000,
  "expires_at": "2025-12-27T23:54:00"
}
```

### 2. 查询订单状态
```
GET /api/payment/orders/{order_id}/status
Authorization: Bearer <token>
```

**响应**:
```json
{
  "order_id": "uuid",
  "order_no": "ORD20251227...",
  "payment_status": "paid",
  "paid_at": "2025-12-27T23:40:00",
  "transaction_id": "4200002468202512271234567890"
}
```

### 3. 微信支付回调
```
POST /api/payment/callback/wechat
Content-Type: application/json
Wechatpay-Signature: ...
Wechatpay-Timestamp: ...
Wechatpay-Nonce: ...
Wechatpay-Serial: ...

{
  "id": "...",
  "create_time": "...",
  "resource_type": "encrypt-resource",
  "resource": {
    "algorithm": "AEAD_AES_256_GCM",
    "ciphertext": "...",
    "nonce": "...",
    "associated_data": "..."
  }
}
```

**响应**:
```json
{
  "code": "SUCCESS",
  "message": "成功"
}
```

---

## 🎯 测试清单

在生产环境上线前，请确保测试以下场景：

- [ ] 正常支付流程（小金额测试）
- [ ] 订单超时自动过期
- [ ] 重复回调不重复发放积分
- [ ] 不同套餐的支付测试
- [ ] 并发订单测试
- [ ] 网络异常情况（回调重试）
- [ ] 证书过期提醒
- [ ] 回调签名验证
- [ ] 订单状态查询
- [ ] 积分到账验证
- [ ] 积分历史记录

---

## 📞 技术支持

如果遇到问题，可以：

1. **查看日志**: 检查后台服务日志
2. **查看API文档**: http://127.0.0.1:8001/docs
3. **微信支付文档**: https://pay.weixin.qq.com/wiki/doc/apiv3/index.shtml
4. **商户平台**: https://pay.weixin.qq.com/

---

## 🚀 开始测试

现在您可以：

1. 打开浏览器访问 **http://127.0.0.1:8001**
2. 登录系统
3. 点击 **💳 充值** 按钮
4. 选择 **微信支付**
5. 扫码完成支付测试

**祝测试顺利！** 🎉

---

*文档生成于 2025-12-27*
*服务地址: http://127.0.0.1:8001*
