# 积分历史查询功能
**Credit History Feature**

实现时间: 2025-12-27

---

## 功能描述

用户点击顶部的**"剩余积分"**徽章，可以查看自己的积分变动历史记录，包括充值、消费、退款等所有积分变动详情。

### 功能入口

**位置**: 页面顶部导航栏右侧
```
┌─────────────────────────────────────┐
│ 🤖 TikTok 达人推荐助手              │
│                                     │
│     [剩余积分: 1000] 💳 充值  👤    │
│          ↑                          │
│      点击这里查看历史                │
└─────────────────────────────────────┘
```

### 交互效果

1. **鼠标悬停**: 积分徽章放大并显示阴影，提示可点击
2. **点击**: 弹出积分历史模态框
3. **显示**: 最近50条积分变动记录

---

## 功能特性

### 1. 详细的记录信息

每条记录显示以下信息：

| 字段 | 说明 | 示例 |
|------|------|------|
| 时间 | 变动发生时间 | 2025-12-27 23:28:45 |
| 类型 | 变动类型（带emoji） | 💳 充值 / 📤 消费 |
| 变动 | 积分变动数量 | +1000 / -100 |
| 变动前 | 变动前的积分余额 | 0 |
| 变动后 | 变动后的积分余额 | 1000 |
| 说明 | 变动原因或关联信息 | 订单 ORD20251227... |

### 2. 类型分类

支持以下积分变动类型：

| 类型 | 显示 | 颜色 | 说明 |
|------|------|------|------|
| `recharge` | 💳 充值 | 绿色 | 用户充值获得积分 |
| `deduct` | 📤 消费 | 红色 | 使用服务消耗积分 |
| `refund` | 💰 退款 | 蓝色 | 退款返还积分 |
| `refund_deduct` | 📥 退款扣除 | 橙色 | 退款时扣除已使用积分 |
| `add` | ➕ 增加 | 绿色 | 管理员赠送积分 |
| `admin_adjust` | ⚙️ 调整 | 灰色 | 管理员调整积分 |

### 3. 颜色标识

- **正数变动**: 绿色 `+1000`
- **负数变动**: 红色 `-100`
- **当前余额**: 紫色粗体显示

### 4. 关联信息

- **充值记录**: 显示订单号（如 `订单 ORD20251227...`）
- **消费记录**: 显示报告标题（如 `达人推荐报告`）
- **退款记录**: 显示订单号

---

## 技术实现

### 后端 API

#### 端点
```
GET /api/payment/credit-history
```

#### 参数
- `limit`: 返回记录数量（默认50，最大100）
- `offset`: 跳过记录数量（用于分页）

#### 认证
需要用户登录（JWT Token）

#### 响应示例
```json
[
  {
    "history_id": "uuid",
    "change_type": "recharge",
    "amount": 1000,
    "before_credits": 0,
    "after_credits": 1000,
    "reason": "充值获得",
    "created_at": "2025-12-27T23:28:45",
    "order_no": "ORD20251227...",
    "report_title": null
  }
]
```

### 前端实现

#### HTML结构
```html
<!-- 积分历史模态框 -->
<div id="creditHistoryModal" class="modal">
    <div class="modal-content">
        <div class="modal-header">
            <h3>💰 积分变动历史</h3>
            <button onclick="closeCreditHistoryModal()">×</button>
        </div>
        <div class="modal-body">
            <table>
                <!-- 表格内容 -->
            </table>
        </div>
    </div>
</div>
```

#### JavaScript函数

**打开模态框**:
```javascript
function openCreditHistoryModal() {
    document.getElementById('creditHistoryModal').style.display = 'flex';
    loadCreditHistory();
}
```

**加载数据**:
```javascript
async function loadCreditHistory() {
    const response = await fetchWithAuth('/api/payment/credit-history?limit=50');
    const histories = await response.json();
    renderCreditHistoryTable(histories);
}
```

**渲染表格**:
```javascript
function renderCreditHistoryTable(histories) {
    // 遍历数据，生成表格行
    tbody.innerHTML = histories.map(history => `
        <tr>
            <td>${formatDate(history.created_at)}</td>
            <td>${getChangeTypeIcon(history.change_type)}</td>
            <td>${formatAmount(history.amount)}</td>
            ...
        </tr>
    `).join('');
}
```

---

## 文件修改

### 1. 后端 - api/payment.py

**位置**: 文件末尾（第525-594行）

**新增内容**:
- `CreditHistoryItem` Pydantic模型
- `get_credit_history` API端点
- 查询逻辑：从数据库获取积分历史并关联订单/报告信息

### 2. 前端 - static/index.html

#### 修改1: 积分徽章（第1199-1205行）
```html
<div class="quota-badge" id="quotaBadge"
     onclick="openCreditHistoryModal()"
     style="cursor: pointer;"
     title="点击查看积分变动历史">
    剩余积分: --
</div>
```

#### 修改2: 添加模态框HTML（第1540-1571行）
```html
<div id="creditHistoryModal" class="modal">
    <!-- 积分历史表格 -->
</div>
```

#### 修改3: JavaScript函数（第4031-4127行）
- `openCreditHistoryModal()` - 打开模态框
- `closeCreditHistoryModal()` - 关闭模态框
- `loadCreditHistory()` - 加载数据
- `renderCreditHistoryTable()` - 渲染表格

---

## 使用场景

### 场景1: 查看充值记录
1. 点击"剩余积分"徽章
2. 看到所有充值记录，包括：
   - 充值时间
   - 充值金额对应的积分
   - 订单号
   - 充值前后的积分余额

### 场景2: 查看消费记录
1. 打开积分历史
2. 看到所有消费记录，包括：
   - 消费时间
   - 消费的积分数量
   - 关联的报告标题
   - 消费前后的积分余额

### 场景3: 查看退款记录
1. 打开积分历史
2. 看到退款相关记录：
   - 退款返还的积分（绿色 +）
   - 退款扣除的已用积分（橙色 -）
   - 关联的订单号

---

## 界面展示

### 积分历史表格示例

```
╔══════════════════════════════════════════════════════════════╗
║              💰 积分变动历史                            ×    ║
╠══════════════════════════════════════════════════════════════╣
║ 时间              类型      变动    变动前   变动后   说明    ║
╟──────────────────────────────────────────────────────────────╢
║ 2025-12-27 23:28  💳 充值  +1000      0     1000   订单...  ║
║ 2025-12-27 23:30  📤 消费   -100   1000      900   达人推荐 ║
║ 2025-12-27 23:35  💰 退款   +100    900     1000   订单...  ║
╚══════════════════════════════════════════════════════════════╝
```

### 颜色方案

- **充值/增加**: 💚 绿色 (#10b981)
- **消费/扣除**: 💔 红色 (#ef4444)
- **退款**: 💙 蓝色 (#3b82f6)
- **退款扣除**: 🧡 橙色 (#f59e0b)
- **调整**: 💜 灰色 (#6b7280)

---

## 性能优化

### 1. 分页支持
- 默认查询50条记录
- 支持通过 `limit` 和 `offset` 参数分页
- 最大单次查询100条

### 2. 数据库优化
- `created_at` 字段建立索引
- `user_id` 字段建立索引
- 使用 `order_by` 按时间倒序排列

### 3. 前端优化
- 表格使用虚拟化渲染（未来可实现）
- 懒加载更多记录（未来可实现）

---

## 数据库表结构

### credit_history 表

| 字段 | 类型 | 说明 |
|------|------|------|
| history_id | VARCHAR(36) | 主键 |
| user_id | VARCHAR(36) | 用户ID（索引） |
| change_type | VARCHAR(20) | 变动类型（索引） |
| amount | INTEGER | 变动数量（正/负） |
| before_credits | INTEGER | 变动前积分 |
| after_credits | INTEGER | 变动后积分 |
| reason | VARCHAR(200) | 变动原因 |
| related_report_id | VARCHAR(36) | 关联报告ID |
| related_order_id | VARCHAR(36) | 关联订单ID |
| created_at | DATETIME | 创建时间（索引） |
| meta_data | JSON | 其他元数据 |

---

## 测试用例

### 测试1: 查看空历史
1. 新用户登录
2. 点击"剩余积分"
3. ✅ 预期：显示"暂无积分变动记录"

### 测试2: 查看充值记录
1. 用户完成一笔充值
2. 点击"剩余积分"
3. ✅ 预期：
   - 显示充值记录
   - 类型为"💳 充值"
   - 变动为正数（绿色）
   - 显示订单号

### 测试3: 查看消费记录
1. 用户生成一份报告
2. 点击"剩余积分"
3. ✅ 预期：
   - 显示消费记录
   - 类型为"📤 消费"
   - 变动为负数（红色）
   - 显示报告标题

### 测试4: 查看多条记录
1. 用户有多次充值和消费
2. 点击"剩余积分"
3. ✅ 预期：
   - 按时间倒序显示
   - 最新的记录在最上面
   - 每条记录都显示完整

---

## 未来改进

### 1. 筛选功能
```javascript
// 按类型筛选
<select onChange="filterByType(this.value)">
    <option value="all">全部</option>
    <option value="recharge">充值</option>
    <option value="deduct">消费</option>
    <option value="refund">退款</option>
</select>
```

### 2. 时间范围选择
```javascript
// 按时间筛选
<input type="date" onChange="filterByDate(this.value)">
```

### 3. 导出功能
```javascript
// 导出为Excel
<button onClick="exportToExcel()">📥 导出Excel</button>
```

### 4. 统计图表
```javascript
// 使用Chart.js显示积分变化趋势
<canvas id="creditChart"></canvas>
```

---

## 相关文档

- [api/payment.py](api/payment.py:525-594) - 积分历史API
- [static/index.html](static/index.html:1199-1205) - 积分徽章
- [static/index.html](static/index.html:1540-1571) - 积分历史模态框
- [static/index.html](static/index.html:4031-4127) - JavaScript函数
- [database/models.py](database/models.py:205-225) - CreditHistory模型

---

*本文档生成于 2025-12-27*
*积分历史查询功能已完成 ✅*
