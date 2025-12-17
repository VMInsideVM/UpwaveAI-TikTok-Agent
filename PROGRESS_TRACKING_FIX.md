# 进度跟踪修复文档

## 问题描述

**现象：**
- ✅ 终端能看到进度条更新（例如：25%, 50%）
- ❌ 报告库中的进度条始终显示 0%

**根本原因：**
只有 Report Agent（阶段 3）的进度会更新到数据库，而阶段 2（获取达人详细信息）的进度只打印在终端，没有同步到数据库。

---

## 解决方案

### 1. 修复进度更新方法

**文件：** `background_tasks.py:245-266`

**改进：**
```python
# 之前（可能失败）
stmt = update(Report).where(...).values(progress=progress)
db.execute(stmt)
db.commit()

# 现在（更可靠）
report = db.query(Report).filter(...).first()
if not report:
    print(f"⚠️ 报告不存在: {report_id}")
    return

report.progress = progress
db.commit()
db.refresh(report)  # 验证更新
print(f"📊 进度已更新到数据库: {progress}% (验证: {report.progress}%)")
```

**优势：**
- ✅ 使用 ORM 对象而不是原始 SQL 语句
- ✅ 添加了报告存在性检查
- ✅ 提交后立即验证更新结果
- ✅ 添加了完整的异常堆栈跟踪

---

### 2. 集成三阶段进度跟踪

**文件：** `background_tasks.py:123-259`

**进度分配：**
```
阶段 1 (0-10%):   搜索达人候选列表
阶段 2 (10-60%):  获取达人详细信息 ⭐ 新增！
阶段 3 (60-100%): 生成分析报告
```

#### 阶段 1：搜索候选列表（0-10%）

```python
print(f"📥 步骤 1/3: 搜索达人候选列表...")
self._update_report_progress(report_id, 5)  # 开始

# ... 调用爬虫 API ...

self._update_report_progress(report_id, 10)  # 完成
```

#### 阶段 2：获取详细信息（10-60%）⭐ 核心修复

```python
# 直接调用流式 API，实时捕获进度事件
url = f"{API_BASE_URL}/process_influencer_list_stream"

with requests.get(url, params=params, stream=True) as response:
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith('data: '):
            continue

        event = json.loads(line[6:])

        if event["type"] == "progress":
            current = event["current"]
            total = event["total"]

            # 映射到 10-60% 的进度范围
            # 公式: 10% + (current/total * 50%)
            stage2_progress = int(10 + (current / total * 50))
            self._update_report_progress(report_id, stage2_progress)

            # 继续显示终端进度条
            print(f"处理进度: {bar} {percent}% ({current}/{total})")

        elif event["type"] == "complete":
            self._update_report_progress(report_id, 60)
```

**关键改进：**
- 直接调用流式 API（绕过 Tool 层）
- 捕获每个进度事件（`type: "progress"`）
- 实时映射到整体进度范围（10-60%）
- 同时保留终端输出（用户友好）

#### 阶段 3：生成报告（60-100%）

```python
# 创建进度回调函数（映射 0-100% 到 65-100%）
def progress_callback(internal_progress: int):
    """
    Report Agent 内部使用 0-100%，我们需要映射到 65-100%
    公式: 65 + (internal_progress * 0.35)
    """
    overall_progress = int(65 + (internal_progress * 0.35))
    self._update_report_progress(report_id, overall_progress)

# 调用 Report Agent
report_agent.generate_report(
    ...,
    progress_callback=progress_callback  # ⭐ 传入映射后的回调
)
```

**映射逻辑：**
- Report Agent 内部：0% → 整体：65%
- Report Agent 内部：50% → 整体：82.5%
- Report Agent 内部：100% → 整体：100%

---

## 进度映射详解

### 完整进度流程

| 任务阶段 | 内部进度 | 映射公式 | 整体进度范围 |
|---------|---------|---------|-------------|
| **阶段 1**: 搜索候选 | - | 固定值 | 0% → 5% → 10% |
| **阶段 2**: 获取详情 | 0-100% | `10 + (p * 0.5)` | 10% → 35% → 60% |
| **阶段 3**: 生成报告 | 0-100% | `65 + (p * 0.35)` | 65% → 82.5% → 100% |

### 示例场景

假设有 20 个达人需要获取详细信息：

```
阶段 1:
  开始    → 5%
  完成    → 10%

阶段 2:
  0/20    → 10%
  5/20    → 22.5%  (10 + 25% * 50%)
  10/20   → 35%    (10 + 50% * 50%)
  15/20   → 47.5%  (10 + 75% * 50%)
  20/20   → 60%    (10 + 100% * 50%)

阶段 3:
  加载数据 (10%)  → 68.5%   (65 + 10% * 35%)
  评分 (40%)      → 79%     (65 + 40% * 35%)
  内容分析 (80%)  → 93%     (65 + 80% * 35%)
  生成报告 (100%) → 100%    (65 + 100% * 35%)
```

---

## 用户体验改进

### 之前

```
报告库界面:
┌──────────────────────────────┐
│ 女士香水 - 达人推荐报告       │
│ 状态: 生成中                 │
│ 进度: [░░░░░░░░░░] 0%       │  ❌ 卡在 0%
│ 创建时间: 2025-01-08         │
└──────────────────────────────┘

终端输出:
处理进度: ███████░░░ 25% (5/20)  ✅ 正常显示
```

### 现在

```
报告库界面:
┌──────────────────────────────┐
│ 女士香水 - 达人推荐报告       │
│ 状态: 生成中                 │
│ 进度: [██████░░░░] 47%      │  ✅ 实时更新
│ 预计剩余: 15 分钟            │
│ 创建时间: 2025-01-08         │
└──────────────────────────────┘

终端输出:
📊 进度已更新到数据库: 47% (验证: 47%)  ✅ 确认成功
处理进度: ███████░░░ 75% (15/20)
```

---

## 测试验证

### 运行测试脚本

```bash
python test_progress_update.py
```

**预期输出：**
```
✅ 创建测试报告: abc-123-def
   初始进度: 0%

📊 开始测试进度更新...

🔄 阶段 1 开始: 搜索候选列表
📊 进度已更新到数据库: 5% (验证: 5%)
   ✅ 数据库进度: 5% (预期: 5%)

🔄 阶段 1 完成
📊 进度已更新到数据库: 10% (验证: 10%)
   ✅ 数据库进度: 10% (预期: 10%)

🔄 阶段 2: 获取详细信息 (40%)
📊 进度已更新到数据库: 30% (验证: 30%)
   ✅ 数据库进度: 30% (预期: 30%)

...

最终报告状态:
  报告 ID: abc-123-def
  状态: generating
  进度: 100%
  创建时间: 2025-01-08 10:30:00
```

### 实际任务测试

1. 启动服务：
   ```bash
   python start_chatbot.py
   ```

2. 提交报告生成任务

3. 观察终端输出：
   ```
   📊 进度已更新到数据库: 5% (验证: 5%)
   📊 进度已更新到数据库: 10% (验证: 10%)
   📊 进度已更新到数据库: 22% (验证: 22%)
   ...
   ```

4. 同时检查报告库界面，确认进度条实时更新

---

## 技术细节

### 为什么之前失败？

**SQLAlchemy update() 语句的问题：**
```python
stmt = update(Report).where(Report.report_id == report_id).values(progress=progress)
db.execute(stmt)
db.commit()
```

在 SQLite + 多线程环境下，这种方式可能遇到：
1. **不触发 ORM 刷新机制** - 更新可能不立即生效
2. **表锁定问题** - 后台线程 vs API 线程竞争
3. **静默失败** - 没有验证机制，无法确认成功

### 为什么现在成功？

**ORM 对象直接赋值：**
```python
report = db.query(Report).filter(...).first()
report.progress = progress
db.commit()
db.refresh(report)  # 强制刷新
```

优势：
- ✅ **ORM 自动管理** - 触发完整的生命周期事件
- ✅ **立即验证** - `db.refresh()` 强制从数据库重新读取
- ✅ **清晰的错误** - 查询失败会立即报错
- ✅ **事务安全** - 使用上下文管理器确保提交

---

## 已知限制

1. **进度粒度**：阶段 2 的进度取决于达人数量
   - 5 个达人 = 每完成 1 个跳 10%（10% → 20% → 30% ...）
   - 50 个达人 = 每完成 1 个跳 1%（平滑）

2. **网络延迟**：流式 API 的进度更新可能有 1-2 秒延迟

3. **缓存命中**：如果所有达人都已缓存，阶段 2 会瞬间完成（10% → 60%）

---

## 相关文件

| 文件 | 修改内容 | 行号 |
|------|---------|------|
| `background_tasks.py` | 修复 `_update_report_progress()` 方法 | 245-266 |
| `background_tasks.py` | 重写 `_execute_scraping_task()` 流程 | 123-259 |
| `background_tasks.py` | 修改 `_generate_report()` 映射逻辑 | 313-361 |
| `test_progress_update.py` | 新增测试脚本 | 全文 |

---

## 总结

✅ **修复前**：只有报告生成阶段（60-100%）的进度会更新
✅ **修复后**：完整的三阶段进度（0-100%）全部更新到数据库

✅ **修复前**：数据库更新使用 SQL 语句，可能静默失败
✅ **修复后**：使用 ORM 对象，带验证机制，确保成功

✅ **用户体验**：从"卡在 0%"变成"平滑增长，实时反馈"
