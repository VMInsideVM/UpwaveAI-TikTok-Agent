# 后台管理系统 - 过期订单显示修复

## 问题描述

**原始问题**：
后台管理系统中，已经过期的订单仍然显示为"待支付"状态，而不是"已取消"。

## 问题场景

```
管理员登录后台 → 查看订单管理
                    ↓
看到一些订单：
- 订单 A：创建于 1小时前，状态：待支付 ❌（实际已超时15分钟）
- 订单 B：创建于 2小时前，状态：待支付 ❌（实际已超时）
- 订单 C：创建于 5分钟前，状态：待支付 ✅（未超时）
```

**问题**：订单 A 和 B 已经过期，但仍显示为"待支付"。

## 根本原因

后台管理系统的订单列表渲染逻辑只是简单显示数据库中的 `payment_status` 字段，没有检查订单是否已超过 `expired_at` 时间。

### 问题代码（修复前）

**位置**：[static/admin.html:2524-2532](static/admin.html#L2524-L2532)

```javascript
orders.forEach(order => {
    let statusBadge = '';
    switch (order.payment_status) {  // ❌ 直接使用数据库状态
        case 'pending': statusBadge = '<span>待支付</span>'; break;
        case 'paid': statusBadge = '<span>已支付</span>'; break;
        case 'cancelled': statusBadge = '<span>已取消</span>'; break;
        // ...
    }
    // 没有检查是否过期
});
```

## 解决方案

在渲染订单列表时，检查 `pending` 状态的订单是否已超过 `expired_at` 时间，如果已过期则显示为"已取消 (超时)"。

### 修复代码

**位置**：[static/admin.html:2525-2546](static/admin.html#L2525-L2546)

```javascript
orders.forEach(order => {
    // ⭐ 检查订单是否已过期（待支付状态且超过过期时间）
    const now = new Date();
    const isExpired = order.payment_status === 'pending' &&
                     order.expired_at &&
                     new Date(order.expired_at) < now;

    // 确定显示状态：如果是待支付但已过期，显示为"已取消"
    const displayStatus = isExpired ? 'cancelled' : order.payment_status;

    let statusBadge = '';
    switch (displayStatus) {
        case 'pending': statusBadge = '<span class="badge badge-warning">待支付</span>'; break;
        case 'paid': statusBadge = '<span class="badge badge-success">已支付</span>'; break;
        case 'cancelled': statusBadge = '<span class="badge" style="background: #9ca3af; color: white;">已取消</span>'; break;
        case 'refunded': statusBadge = '<span class="badge badge-danger">已退款</span>'; break;
        case 'partial_refunded': statusBadge = '<span class="badge" style="background: #f59e0b; color: white;">部分退款</span>'; break;
    }

    // 如果是过期订单，添加过期标记
    if (isExpired) {
        statusBadge = '<span class="badge" style="background: #9ca3af; color: white;">已取消 (超时)</span>';
    }

    // 继续渲染订单行...
});
```

## 修复要点

### 1. 过期检测逻辑

```javascript
const isExpired = order.payment_status === 'pending' &&  // 必须是待支付状态
                 order.expired_at &&                     // 有过期时间
                 new Date(order.expired_at) < now;       // 已超过过期时间
```

**检查三个条件**：
- ✅ 订单状态是 `pending`（待支付）
- ✅ 订单有 `expired_at` 字段
- ✅ 当前时间已超过过期时间

### 2. 显示状态映射

```javascript
const displayStatus = isExpired ? 'cancelled' : order.payment_status;
```

**逻辑**：
- 如果已过期 → 显示为 `cancelled`
- 否则 → 使用数据库的实际状态

### 3. 过期标记

```javascript
if (isExpired) {
    statusBadge = '<span class="badge" style="background: #9ca3af; color: white;">已取消 (超时)</span>';
}
```

**特殊标记**：过期订单显示"已取消 (超时)"，与手动取消区分。

## 修复效果

### 修复前 ❌

```
订单列表：
┌────────────┬──────┬────────┬──────────┐
│ 订单号      │ 用户 │ 金额   │ 状态      │
├────────────┼──────┼────────┼──────────┤
│ 202501xxx1 │ 张三 │ ¥50   │ 待支付    │  ← 实际已过期2小时
│ 202501xxx2 │ 李四 │ ¥100  │ 待支付    │  ← 实际已过期1小时
│ 202501xxx3 │ 王五 │ ¥200  │ 待支付    │  ← 未过期
│ 202501xxx4 │ 赵六 │ ¥50   │ 已支付    │
└────────────┴──────┴────────┴──────────┘
```

### 修复后 ✅

```
订单列表：
┌────────────┬──────┬────────┬──────────────┐
│ 订单号      │ 用户 │ 金额   │ 状态          │
├────────────┼──────┼────────┼──────────────┤
│ 202501xxx1 │ 张三 │ ¥50   │ 已取消 (超时) │  ← ✅ 正确显示
│ 202501xxx2 │ 李四 │ ¥100  │ 已取消 (超时) │  ← ✅ 正确显示
│ 202501xxx3 │ 王五 │ ¥200  │ 待支付        │  ← 未过期，正常显示
│ 202501xxx4 │ 赵六 │ ¥50   │ 已支付        │
└────────────┴──────┴────────┴──────────────┘
```

## 测试验证

### 测试步骤

1. **创建测试订单**：
   ```
   - 登录前端用户账号
   - 创建一个充值订单（例如 ¥50）
   - 不支付，等待15分钟让其超时
   ```

2. **查看后台管理**：
   ```
   - 登录后台管理账号
   - 进入"订单管理"页面
   - 查找刚才创建的订单
   ```

3. **验证显示**：
   ```
   预期结果：
   - ✅ 订单状态显示为"已取消 (超时)"
   - ✅ 状态徽章颜色为灰色（#9ca3af）
   - ✅ 与手动取消的订单有区分（有"超时"标记）
   ```

### 快速测试方法

如果不想等待15分钟，可以临时修改数据库：

```sql
-- 将某个待支付订单的过期时间设为过去
UPDATE payment_orders
SET expired_at = datetime('now', '-1 hour')
WHERE order_id = 'your_test_order_id'
  AND payment_status = 'pending';
```

然后刷新后台管理页面，应该看到订单显示为"已取消 (超时)"。

## 其他状态说明

### 订单状态类型

| 数据库状态 | 前端显示 | 颜色 | 说明 |
|-----------|---------|------|------|
| `pending` | 待支付 | 橙色 | 订单未支付且未过期 |
| `pending` (过期) | 已取消 (超时) | 灰色 | 订单未支付且已超时 |
| `paid` | 已支付 | 绿色 | 订单已支付 |
| `cancelled` | 已取消 | 灰色 | 用户手动取消 |
| `refunded` | 已退款 | 红色 | 订单已全额退款 |
| `partial_refunded` | 部分退款 | 橙色 | 订单已部分退款 |

### 区分"手动取消"和"超时取消"

```
手动取消：数据库 payment_status = 'cancelled'
         显示：已取消

超时取消：数据库 payment_status = 'pending' + expired_at < now
         显示：已取消 (超时)
```

## 用户端对比

**用户端**（index.html）已有类似逻辑：

```javascript
// 用户端的过期检测（index.html:4177-4179）
const expired = order.expired_at && new Date(order.expired_at) < now;
const isPending = order.payment_status === 'pending';
const displayStatus = (isPending && expired) ? 'expired' : order.payment_status;
```

**后台管理端**（admin.html）现在也有了：

```javascript
// 后台管理的过期检测（admin.html:2525-2532）
const isExpired = order.payment_status === 'pending' &&
                 order.expired_at &&
                 new Date(order.expired_at) < now;
const displayStatus = isExpired ? 'cancelled' : order.payment_status;
```

**差异**：
- 用户端：显示为"已过期"（expired）
- 后台管理：显示为"已取消 (超时)"（cancelled with timeout）

这是合理的，因为用户和管理员的关注点不同。

## 未来改进

### 1. 后台自动清理

可以添加定时任务，自动将过期的待支付订单更新为 `cancelled`：

```python
# 伪代码
@scheduler.scheduled_job('interval', minutes=5)
def auto_cancel_expired_orders():
    """自动取消过期订单"""
    expired_orders = db.query(PaymentOrder).filter(
        PaymentOrder.payment_status == 'pending',
        PaymentOrder.expired_at < datetime.now()
    ).all()

    for order in expired_orders:
        order.payment_status = 'cancelled'
        order.cancelled_at = datetime.now()

    db.commit()
```

### 2. 统计数据修正

确保统计数据也排除过期订单：

```javascript
// 统计"待支付"订单时，排除已过期的
const pendingOrders = orders.filter(order =>
    order.payment_status === 'pending' &&
    (!order.expired_at || new Date(order.expired_at) > new Date())
);
```

### 3. 订单搜索优化

在订单筛选中，"待支付"状态应该自动排除过期订单。

## 总结

### 修复内容

✅ **后台管理系统订单列表**：
- 检查 `pending` 订单是否已过期
- 已过期订单显示为"已取消 (超时)"
- 与手动取消订单区分

### 修复位置

- [static/admin.html:2525-2546](static/admin.html#L2525-L2546)

### 影响范围

- ✅ 后台管理员可以清楚看到哪些订单是超时未支付
- ✅ 避免混淆（不会把过期订单当作有效的待支付订单）
- ✅ 与用户端保持一致（都有过期检测）

---

**修复完成！现在后台管理系统会正确显示过期订单的状态。** 🎉
