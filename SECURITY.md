# 安全功能文档

## 已实现的安全功能

### 1. IP注册频率限制 ✅
**位置**: `api/auth.py` - `register_with_phone` 函数

**限制规则**:
- 同一IP每小时最多注册3次
- 同一IP每天最多注册5次
- 同一设备每天最多注册2次

**实现方式**:
- 使用内存限流器 `RateLimiter`
- 违规时记录安全日志
- 返回 HTTP 429 状态码

### 2. 强制手机验证码验证 ✅
**位置**: `api/auth.py` - `register_with_phone` 函数

**验证流程**:
1. 用户请求短信验证码
2. 验证码发送到用户手机
3. 注册时必须提供正确的验证码
4. 验证码错误会记录安全日志

**已有限制**:
- 同一手机号5分钟内只能发送1次验证码
- 同一IP每小时最多发送5次验证码
- 验证码有效期5分钟
- 最多尝试3次

### 3. 防止恶意订单创建 ✅
**位置**: `api/payment.py` - `create_order` 函数

**已有限制**:
- 每用户最多3个未支付订单
- 每用户每小时最多创建5个订单（已从10调整为5）
- 订单15分钟后自动过期

**需要添加** (代码已准备但未完全集成):
- IP级别的订单创建限流
- 新用户首次充值金额限制
- 异常支付模式检测

### 4. 退款频率限制 ⚠️ 待实现
**需要在**: `api/user_orders.py` - `request_refund` 函数

**建议规则**:
- 每用户每月最多申请3次退款
- 退款后72小时内禁止再次充值
- 退款率过高的用户标记风险

### 5. 对话频率限制 ✅
**位置**: `chatbot_api.py` - WebSocket消息处理

**已实现规则**:
- 每用户每分钟最多5条消息
- 单个会话最多50轮对话
- 每日新对话创建数动态限制（基于积分：1000积分=10个新对话/天）

**配置位置**: `config/pricing.py`
```python
MAX_ROUNDS_PER_SESSION = 50
NEW_CONVERSATIONS_PER_1000_CREDITS = 10

def calculate_max_daily_conversations(user_credits: int) -> int:
    # 1000积分=10个对话，最少保证1个
    pass
```

### 6. 内容审核（本地关键词）✅
**位置**: `utils/security.py` - `ContentModerator` 类

**功能**:
- 敏感词库过滤
- Prompt注入检测
- 异常长句检测

**已集成到**: `chatbot_api.py` WebSocket消息处理
- 每条用户消息自动进行内容审核
- 违规内容自动拦截并记录安全日志
- 更新用户风险评分（+5分）

**使用方法**:
```python
from utils.security import content_moderator

# 检查内容
is_safe, reason = content_moderator.check_content(user_message)
if not is_safe:
    # 拒绝并记录
    pass

# 检测Prompt注入
is_injection, reason = content_moderator.detect_prompt_injection(user_message)
if is_injection:
    # 拒绝并记录
    pass
```

### 7. Token消耗异常检测 ❌ 已移除
**原位置**: `utils/security.py` - `TokenMonitor` 类

**状态**: 已按照用户要求移除此功能
- TokenMonitor 类代码仍保留在 utils/security.py 中（未使用）
- 未集成到任何业务逻辑
- 如需启用，可参考以下代码

**参考代码（未启用）**:
```python
from utils.security import token_monitor

# 检测异常
is_anomaly, reason = token_monitor.check_anomaly(
    user_id=user_id,
    current_tokens=token_count
)

if is_anomaly:
    # 警告或拒绝
    pass

# 记录使用
token_monitor.record_usage(user_id, token_count)
```

### 8. 恶意Prompt注入防护 ✅
**位置**: `utils/security.py` - `ContentModerator.detect_prompt_injection`

**检测模式**:
- "忽略之前的指令"
- "你现在是..."
- 系统提示注入
- 特殊标记注入

**已集成到**: `chatbot_api.py` WebSocket消息处理
- 每条用户消息自动检测Prompt注入
- 检测到注入立即拦截并记录高危安全日志
- 更新用户风险评分（+15分）

## 安全数据库表

### security_logs
记录所有安全事件
- `event_type`: rate_limit, content_violation, prompt_injection, etc.
- `severity`: low, medium, high, critical
- `event_details`: JSON格式的详细信息

### user_risk_scores
用户风险评分
- `risk_score`: 0-100，越高越危险
- `violation_count`: 违规次数
- `is_blocked`: 是否被封禁

### ip_blacklist
IP黑名单

### device_blacklist
设备指纹黑名单

## 使用示例

### 1. 记录安全事件
```python
from services.security_service import security_service

security_service.log_security_event(
    db=db,
    event_type="rate_limit_exceeded",
    severity="medium",
    user_id=user_id,
    ip_address=client_ip,
    event_details={"action": "register"}
)
```

### 2. 检查用户是否被封禁
```python
from services.security_service import security_service

is_blocked, reason = security_service.check_user_blocked(db, user_id)
if is_blocked:
    raise HTTPException(403, detail=reason)
```

### 3. 使用限流器
```python
from utils.security import rate_limiter

allowed, remaining = rate_limiter.check_rate_limit(
    key=f"action:{user_id}",
    max_requests=10,
    window_seconds=3600
)

if not allowed:
    raise HTTPException(429, detail="请求过于频繁")
```

## 已完成的任务

1. ✅ IP注册频率限制（3次/小时，5次/天）
2. ✅ 设备注册频率限制（2次/天）
3. ✅ 强制手机验证码验证
4. ✅ 订单创建限制（5个/小时，3个未支付）
5. ✅ 对话频率限制（5条/分钟，50轮/会话）
6. ✅ 每日新对话动态限制（基于积分）
7. ✅ 内容审核（已集成到WebSocket）
8. ✅ Prompt注入防护（已集成到WebSocket）
9. ❌ Token异常检测（已按用户要求移除）

## 待完成的任务

1. ⚠️ 退款频率限制（需要在user_orders.py中实现）
2. ⚠️ 完善订单创建安全检查（IP级别限流、新用户金额限制）
3. ⚠️ 退款后冷却期（72小时禁止充值）

## 集成清单

### ✅ 已集成到chatbot_api.py的功能：
1. ✅ 对话频率限制（每分钟5条消息）
2. ✅ 会话轮次限制（最多50轮）
3. ✅ 每日新对话限制（基于积分动态计算）
4. ✅ 内容审核（用户消息自动检测）
5. ✅ Prompt注入防护（用户消息自动拦截）
6. ❌ Token异常检测（已移除）

### ⚠️ 待集成到api/user_orders.py的功能：
1. ❌ 退款频率限制（每月3次）
2. ❌ 退款后冷却期（72小时禁止充值）

### ⚠️ 待完善api/payment.py的功能：
1. ❌ IP级别的订单创建限流
2. ❌ 新用户充值金额限制
3. ❌ 异常支付模式检测

## 安全配置建议

### 生产环境优化：
1. 将 `RateLimiter` 改为使用 Redis（支持分布式）
2. 定期清理安全日志（保留30天）
3. 设置自动封禁规则（风险评分>80）
4. 配置告警通知（高危事件）

### 敏感词库优化：
1. 从文件加载敏感词库
2. 支持正则表达式匹配
3. 分级处理（警告 vs 拒绝）
4. 定期更新词库

### 监控建议：
1. 实时监控安全日志
2. 统计每日违规趋势
3. 分析高风险用户行为
4. 生成安全报告
