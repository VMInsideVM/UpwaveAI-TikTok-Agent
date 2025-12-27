# 订单倒计时实时更新功能
**Real-time Order Countdown Feature**

实现时间: 2025-12-27

---

## 功能描述

在"我的订单"页面中，待支付订单的剩余时间会**每秒自动更新**，用户无需刷新页面即可看到倒计时的实时变化。

### 效果演示

**修改前**:
```
订单状态: 待支付 (剩余 14:33)  ← 固定不变，需要刷新页面才更新
```

**修改后**:
```
订单状态: 待支付 (剩余 14:33)
          ↓ (1秒后)
订单状态: 待支付 (剩余 14:32)
          ↓ (1秒后)
订单状态: 待支付 (剩余 14:31)
          ↓ (持续更新...)
订单状态: 待支付 (剩余 0:00)
          ↓ (倒计时结束)
订单状态: 已过期  ← 自动更新为过期状态
操作按钮: -       ← 去付款按钮自动消失
```

---

## 实现原理

### 1. 定时器机制

```javascript
let orderCountdownInterval = null;

// 每秒执行一次倒计时更新
orderCountdownInterval = setInterval(() => {
    updateOrderCountdowns();
}, 1000);
```

### 2. 数据存储

在订单表格的每一行（`<tr>`）中添加 `data-` 属性存储关键信息：

```html
<tr data-expired-at="2025-12-27T23:11:45"
    data-payment-status="pending">
    <!-- 订单内容 -->
</tr>
```

### 3. 倒计时计算

```javascript
function updateOrderCountdowns() {
    const now = new Date();
    const expiredTime = new Date(row.dataset.expiredAt);
    const seconds = Math.floor((expiredTime - now) / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    const timeRemaining = `(剩余 ${minutes}:${secs.toString().padStart(2, '0')})`;
}
```

### 4. 状态自动更新

当倒计时结束时，自动更新订单状态：

```javascript
if (expired) {
    // 更新状态显示
    statusCell.innerHTML = '<span style="color: #9ca3af;">已过期</span>';
    // 移除"去付款"按钮
    actionCell.innerHTML = '-';
}
```

---

## 代码修改

### 文件: [static/index.html](static/index.html)

#### 1. 添加全局变量

**位置**: 第 3675 行

```javascript
let orderCountdownInterval = null; // 订单倒计时定时器
```

#### 2. 修改打开订单模态框函数

**位置**: 第 3677-3683 行

```javascript
function openOrdersModal() {
    document.getElementById('ordersModal').style.display = 'flex';
    currentTab = 'orders';
    switchOrderTab('orders');
    // 启动倒计时更新
    startOrderCountdown();
}
```

#### 3. 修改关闭订单模态框函数

**位置**: 第 3685-3689 行

```javascript
function closeOrdersModal() {
    document.getElementById('ordersModal').style.display = 'none';
    // 停止倒计时更新
    stopOrderCountdown();
}
```

#### 4. 新增启动倒计时函数

**位置**: 第 3691-3701 行

```javascript
function startOrderCountdown() {
    stopOrderCountdown();
    orderCountdownInterval = setInterval(() => {
        if (currentTab === 'orders') {
            updateOrderCountdowns();
        }
    }, 1000);
}
```

#### 5. 新增停止倒计时函数

**位置**: 第 3703-3709 行

```javascript
function stopOrderCountdown() {
    if (orderCountdownInterval) {
        clearInterval(orderCountdownInterval);
        orderCountdownInterval = null;
    }
}
```

#### 6. 新增更新倒计时函数

**位置**: 第 3711-3748 行

```javascript
function updateOrderCountdowns() {
    const now = new Date();
    const rows = document.querySelectorAll('#ordersTableBody tr');

    rows.forEach((row) => {
        const statusCell = row.querySelector('td:nth-child(5)');
        const expiredAt = row.dataset.expiredAt;
        const paymentStatus = row.dataset.paymentStatus;

        if (!expiredAt || paymentStatus !== 'pending') return;

        const expiredTime = new Date(expiredAt);
        const expired = expiredTime < now;

        if (expired) {
            // 订单已过期
            statusCell.innerHTML = '<span style="color: #9ca3af;">已过期</span>';
            const actionCell = row.querySelector('td:nth-child(7)');
            if (actionCell) actionCell.innerHTML = '-';
        } else {
            // 更新倒计时
            const seconds = Math.floor((expiredTime - now) / 1000);
            const minutes = Math.floor(seconds / 60);
            const secs = seconds % 60;
            const timeRemaining = `(剩余 ${minutes}:${secs.toString().padStart(2, '0')})`;
            statusCell.innerHTML = `<span style="color: #f59e0b;">待支付 ${timeRemaining}</span>`;
        }
    });
}
```

#### 7. 修改订单表格渲染函数

**位置**: 第 3864-3866 行

在 `<tr>` 标签中添加 `data-` 属性：

```html
<tr style="border-bottom: 1px solid var(--border-color);"
    data-expired-at="${order.expired_at || ''}"
    data-payment-status="${order.payment_status}">
```

#### 8. 修改标签切换函数

**位置**: 第 3768 和 3780 行

```javascript
if (tab === 'orders') {
    // ...
    loadUserOrders();
    startOrderCountdown(); // 启动倒计时
} else {
    // ...
    loadUserRefunds();
    stopOrderCountdown(); // 停止倒计时
}
```

---

## 性能优化

### 1. 条件执行

只在"订单"标签页激活时执行倒计时更新：

```javascript
orderCountdownInterval = setInterval(() => {
    if (currentTab === 'orders') {  // 仅在订单页更新
        updateOrderCountdowns();
    }
}, 1000);
```

### 2. 资源清理

关闭模态框或切换标签时自动停止定时器，避免内存泄漏：

```javascript
function stopOrderCountdown() {
    if (orderCountdownInterval) {
        clearInterval(orderCountdownInterval);
        orderCountdownInterval = null;
    }
}
```

### 3. DOM 查询优化

只更新待支付订单的倒计时，跳过已支付/已取消的订单：

```javascript
if (!expiredAt || paymentStatus !== 'pending') return;
```

---

## 用户体验提升

### 1. 实时反馈
- ✅ 用户可以清楚看到订单剩余时间的实时变化
- ✅ 无需刷新页面即可获取最新状态

### 2. 自动状态更新
- ✅ 倒计时结束后自动显示"已过期"
- ✅ "去付款"按钮自动消失
- ✅ 状态颜色自动变为灰色

### 3. 准确性
- ✅ 每秒精确更新，误差小于1秒
- ✅ 支持分:秒格式显示（如 14:33）
- ✅ 秒数自动补零（如 14:03）

---

## 测试场景

### 场景1: 打开订单列表

1. 点击"我的订单"
2. 观察待支付订单的倒计时
3. ✅ 预期：倒计时每秒减少1秒

### 场景2: 切换标签页

1. 在"我的订单"和"退款记录"之间切换
2. ✅ 预期：
   - 切换到"我的订单"时倒计时开始
   - 切换到"退款记录"时倒计时停止
   - 切换回"我的订单"时倒计时继续

### 场景3: 倒计时结束

1. 等待订单倒计时到 0:00
2. ✅ 预期：
   - 状态自动变为"已过期"
   - 颜色变为灰色
   - "去付款"按钮消失

### 场景4: 关闭模态框

1. 打开订单列表后关闭
2. 重新打开
3. ✅ 预期：倒计时正常工作，没有重复定时器

---

## 注意事项

### 1. 时区问题
- 倒计时使用客户端本地时间
- 确保 `order.expired_at` 使用东八区时间（已在后端修复）

### 2. 浏览器兼容性
- 使用标准 JavaScript API，兼容所有现代浏览器
- `setInterval`、`clearInterval` 支持 IE9+

### 3. 多订单场景
- 支持同时显示多个订单的倒计时
- 每个订单独立计算，互不影响

### 4. 内存管理
- 关闭模态框时自动清理定时器
- 切换标签时停止不必要的倒计时

---

## 未来改进建议

### 1. 倒计时即将结束提醒
```javascript
if (minutes === 0 && seconds <= 60) {
    // 最后1分钟显示红色警告
    statusCell.style.color = '#ef4444';
}
```

### 2. 倒计时结束音效提示
```javascript
if (expired) {
    playNotificationSound();
}
```

### 3. 浏览器通知
```javascript
if (minutes === 1 && seconds === 0) {
    new Notification('订单即将过期', {
        body: '您的订单还有1分钟即将过期，请尽快完成支付'
    });
}
```

---

## 相关文档

- [TIMEZONE_COMPLETE_FIX.md](TIMEZONE_COMPLETE_FIX.md) - 时区完整修复报告
- [static/index.html](static/index.html) - 前端主文件
- [config/pricing.py](config/pricing.py) - 订单过期时间配置

---

*本文档生成于 2025-12-27*
*订单倒计时功能已完成 ✅*
