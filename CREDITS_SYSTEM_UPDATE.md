# 积分系统更新文档

## 更新概述

本次更新将积分系统从每个达人30积分调整为100积分，并增加了积分不足时的使用限制。

### 更新日期
2025-12-19

### 更新内容
1. **积分消耗标准变更**: 每个达人从30积分 → 100积分
2. **最低使用门槛**: 用户剩余积分 < 100时无法使用Agent聊天功能
3. **前端积分检查**: 实时检查用户积分，不足时禁用输入框并显示警告
4. **文档和注释更新**: 同步更新所有相关文档和代码注释

---

## 修改详情

### 1. 前端确认弹窗 (static/index.html)

#### 修改位置 1: 积分计算公式
**文件**: [static/index.html:1865](static/index.html#L1865)

**修改前**:
```javascript
const creditsPerInfluencer = 30;
```

**修改后**:
```javascript
const creditsPerInfluencer = 100;
```

#### 修改位置 2: 弹窗提示文字
**文件**: [static/index.html:1040](static/index.html#L1040)

**修改前**:
```html
此操作将消耗 <strong style="color: #d9534f;"><span id="creditsToDeduct">-</span> 积分</strong>（<span id="influencerCount">-</span> 个达人 × 30 积分/个）
```

**修改后**:
```html
此操作将消耗 <strong style="color: #d9534f;"><span id="creditsToDeduct">-</span> 积分</strong>（<span id="influencerCount">-</span> 个达人 × 100 积分/个）
```

#### 修改位置 3: 积分不足检查和输入禁用
**文件**: [static/index.html:1166-1208](static/index.html#L1166-L1208)

**新增功能**:
```javascript
// ⭐ 检查积分是否足够（至少需要100积分才能使用）
const MIN_CREDITS_REQUIRED = 100;
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');

if (user.remaining_credits < MIN_CREDITS_REQUIRED) {
    // 积分不足，禁用输入
    chatInput.disabled = true;
    sendBtn.disabled = true;
    chatInput.placeholder = `积分不足（剩余${user.remaining_credits}），至少需要${MIN_CREDITS_REQUIRED}积分才能使用`;
    console.warn(`⚠️ 积分不足: ${user.remaining_credits} < ${MIN_CREDITS_REQUIRED}`);

    // 在聊天区域显示警告消息
    const messagesDiv = document.getElementById('chatMessages');
    const existingWarning = document.getElementById('low-credits-warning');

    if (!existingWarning) {
        const warningDiv = document.createElement('div');
        warningDiv.id = 'low-credits-warning';
        warningDiv.style.cssText = 'padding: 16px; margin: 16px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; text-align: center;';
        warningDiv.innerHTML = `
            <p style="margin: 0; color: #856404; font-size: 16px;">
                <strong>⚠️ 积分不足</strong><br>
                您当前剩余 <strong>${user.remaining_credits}</strong> 积分，至少需要 <strong>${MIN_CREDITS_REQUIRED}</strong> 积分才能使用达人推荐服务。<br>
                <span style="font-size: 14px;">每个达人消耗100积分</span>
            </p>
        `;
        messagesDiv.appendChild(warningDiv);
    }
} else {
    // 积分充足，启用输入（如果WebSocket已连接）
    if (isConnected) {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.placeholder = '请告诉我您的需求...';
    }

    // 移除警告消息（如果存在）
    const existingWarning = document.getElementById('low-credits-warning');
    if (existingWarning) {
        existingWarning.remove();
    }
}
```

**功能说明**:
- 加载用户信息时自动检查积分
- 积分 < 100 时：
  - 禁用聊天输入框和发送按钮
  - 修改输入框占位符显示积分不足提示
  - 在聊天区域显示醒目的黄色警告框
- 积分 ≥ 100 时：
  - 启用输入框（如果已连接WebSocket）
  - 移除警告框（如果存在）

---

### 2. 后端报告生成 (api/reports.py)

#### 修改位置 1: 积分常量定义
**文件**: [api/reports.py:155](api/reports.py#L155)

**修改前**:
```python
CREDITS_PER_INFLUENCER = 30
```

**修改后**:
```python
CREDITS_PER_INFLUENCER = 100
```

#### 修改位置 2: 错误提示信息
**文件**: [api/reports.py:189](api/reports.py#L189)

**修改前**:
```python
error_detail = f"积分不足：需要 {required_credits} 积分（{influencer_count} 个达人 × 30），当前剩余 {usage.remaining_credits} 积分"
```

**修改后**:
```python
error_detail = f"积分不足：需要 {required_credits} 积分（{influencer_count} 个达人 × 100），当前剩余 {usage.remaining_credits} 积分"
```

---

### 3. 后台任务队列 (background_tasks.py)

#### 修改位置 1: 积分常量定义
**文件**: [background_tasks.py:610-611](background_tasks.py#L610-L611)

**修改前**:
```python
# ⭐ 计算所需积分（30积分/达人）
CREDITS_PER_INFLUENCER = 30
```

**修改后**:
```python
# ⭐ 计算所需积分（100积分/达人）
CREDITS_PER_INFLUENCER = 100
```

#### 修改位置 2: 错误提示信息
**文件**: [background_tasks.py:627](background_tasks.py#L627)

**修改前**:
```python
error_msg = f"积分不足：需要 {required_credits} 积分（{target_influencer_count} 个达人 × 30），当前剩余 {usage.remaining_credits} 积分"
```

**修改后**:
```python
error_msg = f"积分不足：需要 {required_credits} 积分（{target_influencer_count} 个达人 × 100），当前剩余 {usage.remaining_credits} 积分"
```

---

### 4. 数据库模型 (database/models.py)

#### 修改位置: 注释更新
**文件**: [database/models.py:183](database/models.py#L183)

**修改前**:
```python
total_credits = Column(Integer, default=300, nullable=False)  # 总积分（默认300积分，可查询10个达人）
```

**修改后**:
```python
total_credits = Column(Integer, default=300, nullable=False)  # 总积分（默认300积分，可查询3个达人，每个达人100积分）
```

---

### 5. 数据库迁移脚本 (migrations/001_quota_to_credits.sql)

#### 修改位置 1: 表结构注释
**文件**: [migrations/001_quota_to_credits.sql:16](migrations/001_quota_to_credits.sql#L16)

**修改前**:
```sql
total_credits INTEGER NOT NULL DEFAULT 300,  -- 总积分（从 total_quota 改名）
```

**修改后**:
```sql
total_credits INTEGER NOT NULL DEFAULT 300,  -- 总积分（从 total_quota 改名，每个达人100积分）
```

#### 修改位置 2: 数据迁移注释
**文件**: [migrations/001_quota_to_credits.sql:25-26](migrations/001_quota_to_credits.sql#L25-L26)

**修改前**:
```sql
-- 2. 迁移数据（将旧的配额数据转换为积分）
-- 策略：1次配额 = 300积分（可查询10个达人）
```

**修改后**:
```sql
-- 2. 迁移数据（将旧的配额数据转换为积分）
-- 策略：1次配额 = 300积分（可查询3个达人，每个达人100积分）
```

---

## 功能对比表

| 项目 | 修改前 | 修改后 | 说明 |
|------|--------|--------|------|
| 每个达人积分消耗 | 30积分 | 100积分 | 增加3.33倍 |
| 默认300积分可查询数量 | 10个达人 | 3个达人 | 减少70% |
| 最低使用门槛 | 无限制 | 100积分 | 新增限制 |
| 积分不足时聊天 | 可以聊天 | 禁用输入 | 新增保护 |
| 积分不足提示 | 仅在提交时 | 登录时+提交时 | 双重提示 |

---

## 用户体验流程

### 场景 1: 积分充足（≥100积分）

```
用户登录
    ↓
加载用户信息（积分: 300）
    ↓
✅ 积分检查通过
    ↓
启用聊天输入框
    ↓
用户输入: "美国的口红，2个达人"
    ↓
Agent收集参数
    ↓
显示确认弹窗:
  - 达人数量: 2个
  - 消耗积分: 200 (2 × 100)
  - 剩余积分: 100
    ↓
✅ 积分检查通过，启用确认按钮
    ↓
用户点击确认
    ↓
后台扣除200积分
    ↓
剩余积分: 100（刚好够最低门槛）
```

### 场景 2: 积分不足但能查看（50积分）

```
用户登录
    ↓
加载用户信息（积分: 50）
    ↓
❌ 积分检查失败 (50 < 100)
    ↓
禁用聊天输入框
    ↓
显示警告框:
  "⚠️ 积分不足
   您当前剩余 50 积分，
   至少需要 100 积分才能使用达人推荐服务。
   每个达人消耗100积分"
    ↓
用户无法输入消息
    ↓
只能查看历史对话和报告
```

### 场景 3: 积分临界状态（110积分请求2个达人）

```
用户登录
    ↓
加载用户信息（积分: 110）
    ↓
✅ 积分检查通过 (110 ≥ 100)
    ↓
启用聊天输入框
    ↓
用户输入: "美国的口红，2个达人"
    ↓
Agent收集参数
    ↓
显示确认弹窗:
  - 达人数量: 2个
  - 消耗积分: 200 (2 × 100)
  - 剩余积分: -90 (不足)
    ↓
❌ 积分检查失败，禁用确认按钮
    ↓
按钮文字: "积分不足，需要 200 积分"
    ↓
用户无法提交
    ↓
建议: 调整为1个达人（需要100积分）
```

---

## 测试用例

### 测试 1: 前端积分检查

**测试步骤**:
1. 修改数据库中某用户的积分为50
2. 使用该用户登录
3. 观察聊天界面

**期望结果**:
- ✅ 输入框被禁用（灰色）
- ✅ 发送按钮被禁用
- ✅ 输入框占位符显示: "积分不足（剩余50），至少需要100积分才能使用"
- ✅ 聊天区域显示黄色警告框
- ✅ 控制台输出: `⚠️ 积分不足: 50 < 100`

**验证方式**:
```sql
-- 修改测试用户积分
UPDATE user_usage
SET total_credits = 50, used_credits = 0
WHERE user_id = 'test_user_id';
```

### 测试 2: 确认弹窗积分计算

**测试步骤**:
1. 使用积分充足的用户登录（如300积分）
2. 输入: "美国的口红，2个达人"
3. 等待确认弹窗出现

**期望结果**:
- ✅ 达人数量显示: 2
- ✅ 消耗积分显示: 200
- ✅ 当前积分显示: 300
- ✅ 确认后剩余: 100
- ✅ 确认按钮: 启用
- ✅ 控制台输出: `📊 确认弹窗 - 达人数量: 2, 扣除积分: 200`

### 测试 3: 实际扣除积分

**测试步骤**:
1. 使用积分300的用户
2. 请求2个达人并确认
3. 等待报告生成完成
4. 检查数据库积分变化

**期望结果**:
- ✅ 后端日志: `💰 使用目标达人数量计算积分: 2 个`
- ✅ 扣除积分: 200
- ✅ 数据库记录:
  ```
  total_credits: 300
  used_credits: 200
  remaining_credits: 100
  ```

**验证SQL**:
```sql
SELECT
    user_id,
    total_credits,
    used_credits,
    (total_credits - used_credits) as remaining_credits
FROM user_usage
WHERE user_id = 'test_user_id';
```

### 测试 4: 积分恢复后重新启用

**测试步骤**:
1. 用户当前积分50（输入已禁用）
2. 管理员充值到150积分
3. 用户刷新页面或等待自动刷新

**期望结果**:
- ✅ 输入框恢复启用
- ✅ 发送按钮恢复启用
- ✅ 占位符恢复为: "请告诉我您的需求..."
- ✅ 黄色警告框消失
- ✅ 用户可以正常聊天

### 测试 5: 边界情况 - 刚好100积分请求1个达人

**测试步骤**:
1. 用户积分: 100
2. 请求: 1个达人

**期望结果**:
- ✅ 聊天输入正常（100 ≥ 100）
- ✅ 确认弹窗显示消耗100积分
- ✅ 确认后剩余: 0积分
- ✅ 确认按钮启用（100 ≥ 100）
- ✅ 提交成功
- ✅ 扣除后积分为0，下次登录输入被禁用

---

## 后台日志示例

### 正常扣除积分

```
💰 使用目标达人数量计算积分: 2 个
📊 用户 user_123 扣除积分: 200 (剩余: 100)
✅ 积分扣除成功
```

### 积分不足拒绝

```
💰 使用目标达人数量计算积分: 2 个
❌ 积分不足：需要 200 积分（2 个达人 × 100），当前剩余 50 积分

💡 请充值积分后继续
```

### 积分临界建议

```
💰 使用目标达人数量计算积分: 3 个
❌ 积分不足：需要 300 积分（3 个达人 × 100），当前剩余 150 积分

💡 建议：您当前积分可以生成 1 个达人的报告。您可以：
   1. 调整达人数量为 1 个（需要 100 积分）
   2. 充值积分后继续生成 3 个达人的报告
```

---

## 前端控制台日志示例

### 积分充足

```
📊 确认弹窗 - 达人数量: 2, 扣除积分: 200
🔄 积分信息已刷新
📋 报告列表已刷新
```

### 积分不足（登录时）

```
⚠️ 积分不足: 50 < 100
```

### 积分不足（确认弹窗）

```
📊 确认弹窗 - 达人数量: 2, 扣除积分: 200
⚠️ 积分不足，禁用确认按钮
```

---

## 数据库影响分析

### 默认积分价值变化

**修改前**:
- 新用户默认: 300积分
- 可查询: 10个达人
- 平均每个达人: 30积分

**修改后**:
- 新用户默认: 300积分
- 可查询: 3个达人
- 平均每个达人: 100积分

### 已有用户影响

**场景**: 假设已有用户剩余180积分

**修改前**:
- 可查询: 6个达人 (180 ÷ 30 = 6)

**修改后**:
- 可查询: 1个达人 (180 ÷ 100 = 1)
- 剩余: 80积分
- ⚠️ 如果积分 < 100，将无法使用聊天功能

**建议**:
1. 在更新前通知所有用户
2. 考虑一次性补偿积分（如每用户+200积分）
3. 或提供积分充值优惠活动

---

## 回滚方案

如果需要回滚到30积分/达人的旧版本:

### 1. 代码回滚

```bash
# 回滚所有修改
git revert <commit_hash>
```

### 2. 手动修改

**前端** (static/index.html):
```javascript
const creditsPerInfluencer = 30;  // 改回30
const MIN_CREDITS_REQUIRED = 30;   // 最低门槛改为30
```

**后端** (api/reports.py, background_tasks.py):
```python
CREDITS_PER_INFLUENCER = 30  # 改回30
```

### 3. 数据库无需修改

- 积分记录保持不变
- 只是计算规则恢复

---

## 注意事项

### 1. 用户体验影响

- ⚠️ 积分价值缩水至原来的30%
- ⚠️ 部分用户可能因积分不足无法使用
- ✅ 建议配合积分充值或赠送活动

### 2. 系统稳定性

- ✅ 所有积分计算逻辑已统一更新
- ✅ 前后端积分检查一致
- ✅ 不影响已有数据

### 3. 后续优化建议

1. **积分充值功能**: 允许用户购买积分
2. **积分历史记录**: 显示积分消耗明细
3. **积分预警**: 积分低于200时发送提醒
4. **会员等级**: 不同等级用户享受不同折扣

---

## 文件清单

### 修改的文件（共5个）

1. ✅ [static/index.html](static/index.html) - 前端界面和逻辑
2. ✅ [api/reports.py](api/reports.py) - 报告生成积分扣除
3. ✅ [background_tasks.py](background_tasks.py) - 后台任务积分扣除
4. ✅ [database/models.py](database/models.py) - 数据库模型注释
5. ✅ [migrations/001_quota_to_credits.sql](migrations/001_quota_to_credits.sql) - 迁移脚本注释

### 新建的文件

6. ✅ [CREDITS_SYSTEM_UPDATE.md](CREDITS_SYSTEM_UPDATE.md) - 本文档

---

## 总结

本次更新完成了以下目标:

1. ✅ **统一积分标准**: 所有地方都使用100积分/达人
2. ✅ **增加使用门槛**: 积分 < 100 无法使用聊天功能
3. ✅ **完善前端保护**: 实时检查积分，禁用输入+显示警告
4. ✅ **更新所有文档**: 代码注释和迁移脚本同步更新
5. ✅ **保持数据一致**: 前后端积分计算逻辑完全一致

**测试建议**: 在生产环境部署前，使用测试账号验证所有场景。
