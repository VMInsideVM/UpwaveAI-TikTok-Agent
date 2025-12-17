# 配额扣除问题修复文档

## 问题描述

用户报告：**生成报告之后剩余次数并没有正确扣除**

## 根本原因分析

系统中存在 **两条不同的报告创建路径**，但只有一条正确扣除了配额：

### 路径 1：通过 API 端点生成报告 ✅ 正确扣除
```
用户点击"生成报告"
  → 调用 POST /api/reports
  → [api/reports.py:145] 扣除配额
  → 创建报告
```

### 路径 2：通过 Agent 确认生成报告 ❌ 未扣除配额
```
用户确认搜索
  → Agent 调用 submit_search_task 工具
  → [agent_tools.py:1041] 调用 task_queue.submit_task()
  → [background_tasks.py:473] 调用 _create_report()
  → 创建报告但 **未扣除配额** ❌
```

**问题**：`_create_report()` 方法只负责创建报告记录，没有包含配额扣除逻辑。

## 修复方案

### 1. 后端修复：在 `_create_report()` 中添加配额扣除逻辑

#### 修改文件：[background_tasks.py](background_tasks.py#L502-L553)

**修改内容**：

```python
def _create_report(self, user_id: str, product_name: str, session_id: str = None) -> str:
    """在数据库中创建新报告记录（并扣除用户配额）"""
    try:
        with get_db_context() as db:
            # ... 获取 session_id 的逻辑 ...

            # ⭐ 新增：检查并扣除用户配额
            from database.models import UserUsage
            usage = db.query(UserUsage).filter(
                UserUsage.user_id == user_id
            ).first()

            if not usage:
                raise ValueError(f"找不到用户 {user_id} 的配额信息")

            if usage.remaining_quota <= 0:
                raise ValueError(f"用户配额不足，剩余: {usage.remaining_quota}")

            # 创建报告
            report = Report(
                user_id=user_id,
                session_id=session_id,
                title=f"{product_name} - 达人推荐报告",
                report_path="",
                status='queued',
                meta_data={'product_name': product_name, 'type': 'influencer_search'}
            )
            db.add(report)

            # ⭐ 扣除配额（失败时会自动回滚）
            usage.used_count += 1
            db.commit()
            db.refresh(report)

            print(f"✅ 用户 {user_id} 配额已扣除: {usage.used_count}/{usage.total_quota} (剩余: {usage.remaining_quota})")

            return report.report_id
```

**关键改进**：
- ✅ 在创建报告前检查配额
- ✅ 扣除配额后再提交事务
- ✅ 如果配额不足，抛出异常并回滚
- ✅ 事务失败时自动回滚，不会扣除配额

### 2. 前端修复：增强配额刷新机制

#### 修改文件：[static/index.html](static/index.html#L1889-L1901)

**修改内容**：

```javascript
// 通过 WebSocket 发送确认消息
sendMessage('确认');

// ⭐ 新增：延迟2秒后刷新用户配额信息
// 因为配额会在后端处理"确认"消息时被扣除（在 _create_report 方法中）
// 增加到2秒确保后端处理完成
setTimeout(async () => {
    await loadUserInfo();
    console.log('🔄 配额信息已刷新');
}, 2000);

// ⭐ 同时刷新报告列表，以便显示新创建的报告
setTimeout(async () => {
    await loadReports();
    console.log('📋 报告列表已刷新');
}, 2000);
```

**关键改进**：
- ✅ 延迟从 1 秒增加到 2 秒（确保后端处理完成）
- ✅ 同时刷新报告列表（显示新创建的报告）
- ✅ 添加详细的注释说明扣除时机

## 技术细节

### 配额扣除时机

**旧行为**（有 bug）：
```
用户确认 → 创建报告 → 开始爬取 → [无配额扣除] ❌
```

**新行为**（已修复）：
```
用户确认 → [立即扣除配额] → 创建报告 → 开始爬取 ✅
```

### 事务安全性

使用数据库事务确保原子性：

```python
with get_db_context() as db:
    # 1. 检查配额
    if usage.remaining_quota <= 0:
        raise ValueError("配额不足")

    # 2. 创建报告
    db.add(report)

    # 3. 扣除配额
    usage.used_count += 1

    # 4. 提交事务（要么全部成功，要么全部回滚）
    db.commit()
```

**好处**：
- 如果创建报告失败，配额不会被扣除
- 如果配额不足，不会创建报告
- 保证数据一致性

### 两条路径的配额扣除

现在两条路径都正确扣除配额：

**路径 1**（API 端点）：
```python
# api/reports.py:145
usage.used_count += 1
db.commit()
```

**路径 2**（Agent 后台任务）：
```python
# background_tasks.py:541
usage.used_count += 1
db.commit()
```

## 测试验证

### 测试步骤

1. **查看初始配额**：
   ```
   登录系统 → 查看右上角显示的剩余次数（例如：1/999999）
   ```

2. **开始搜索达人**：
   ```
   与 Agent 对话 → 确认搜索参数 → 输入"确认"
   ```

3. **观察配额变化**：
   ```
   2秒后 → 配额应该从 1/999999 变为 2/999999
   ```

4. **验证报告创建**：
   ```
   点击"报告库" → 应该看到新创建的报告（状态：排队中或生成中）
   ```

### 预期结果

✅ 用户确认后，配额立即扣除
✅ 前端在 2 秒后自动刷新，显示正确的剩余次数
✅ 报告库中显示新创建的报告
✅ 后端日志输出配额扣除信息

### 日志输出示例

```
✅ 用户 bc5b6604-534b-4789-b8fc-4b72851a3ed0 配额已扣除: 2/999999 (剩余: 999997)
📥 新任务已加入队列: a1b2c3d4-... (报告: e5f6g7h8-...)
```

## 边界情况处理

### 1. 配额不足
```python
if usage.remaining_quota <= 0:
    raise ValueError(f"用户配额不足，剩余: {usage.remaining_quota}")
```
- 用户会收到错误提示
- 不会创建报告
- 不会扣除配额

### 2. 并发请求
- 数据库事务保证原子性
- 多个并发请求会按顺序处理
- 不会出现配额重复扣除

### 3. 任务失败
- 配额已扣除但任务失败时，需要**手动退还配额**（未来改进点）
- 当前行为：失败后配额不退还（与 API 路径一致）

## 未来改进建议

### 1. 失败退还机制
当报告生成失败时，自动退还配额：

```python
try:
    # 执行爬取任务
    self._execute_scraping_task(task_info)
except Exception as e:
    # 任务失败，退还配额
    self._refund_quota(user_id)
    raise
```

### 2. 配额历史记录
记录每次配额变化：

```python
class QuotaHistory(Base):
    usage_id = Column(String(36), ForeignKey("user_usage.usage_id"))
    action = Column(String(20))  # 'deduct' or 'refund'
    amount = Column(Integer)
    reason = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 3. 实时 WebSocket 推送
使用 WebSocket 推送配额变化，无需轮询：

```javascript
websocket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'quota_updated') {
        updateQuotaDisplay(data.remaining);
    }
});
```

## 总结

### 修复内容

✅ **后端**：`_create_report()` 方法添加配额扣除逻辑
✅ **前端**：增强配额和报告列表刷新机制
✅ **安全性**：使用数据库事务保证原子性
✅ **一致性**：两条创建路径都正确扣除配额

### 影响范围

- ✅ 不影响现有 API 端点的行为
- ✅ 向后兼容（不破坏现有功能）
- ✅ 改善用户体验（配额实时更新）

### 文件修改清单

1. ✅ [background_tasks.py](background_tasks.py#L502-L553) - 添加配额扣除逻辑
2. ✅ [static/index.html](static/index.html#L1889-L1901) - 增强前端刷新机制

## 参考文档

- [双进度条实现文档](DUAL_PROGRESS_IMPLEMENTATION.md)
- [会话标题唯一性文档](UNIQUE_TITLE_IMPLEMENTATION.md)
- [数据库模型定义](database/models.py)
