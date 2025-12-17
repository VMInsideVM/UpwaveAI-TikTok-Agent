# 双进度条功能实现文档

## 概述

实现了报告生成过程中的两个独立进度条，分别显示：
1. **爬取达人数据进度**（蓝色）：0-100%，包含预计剩余时间
2. **生成报告进度**（绿色）：0-100%，包含预计剩余时间

## 实现细节

### 1. 数据库模型 ([database/models.py](database/models.py#L140-L169))

新增字段到 `Report` 表：
```python
scraping_progress = Column(Integer, default=0)  # 爬取达人数据的进度 (0-100)
scraping_eta = Column(Integer)  # 爬取阶段预计剩余时间（秒）
report_progress = Column(Integer, default=0)  # 报告生成的进度 (0-100)
report_eta = Column(Integer)  # 报告生成阶段预计剩余时间（秒）
```

### 2. 后端进度更新 ([background_tasks.py](background_tasks.py#L123-L260))

#### 进度分配策略
- **阶段 1**：搜索达人候选列表（scraping: 0-20%）
- **阶段 2**：获取达人详细信息（scraping: 20-100%）
- **阶段 3**：生成分析报告（report: 0-100%）

#### 新增方法

**`_update_scraping_progress(report_id, progress, eta)`**
- 更新爬取阶段的进度和预计剩余时间
- 同步更新总进度（scraping 占 60%）

**`_update_report_agent_progress(report_id, progress, eta)`**
- 更新报告生成阶段的进度和预计剩余时间
- 同步更新总进度（report 占 40%）

#### ETA 计算逻辑

**爬取阶段**：
```python
elapsed = time.time() - stage_start_time
if current > 0:
    avg_time_per_item = elapsed / current
    remaining_items = total - current
    eta_seconds = int(avg_time_per_item * remaining_items)
```

**报告生成阶段**：
```python
elapsed = time.time() - stage_start_time
if internal_progress > 0:
    estimated_total = (elapsed / internal_progress) * 100
    eta_seconds = int(estimated_total - elapsed)
```

### 3. API 端点更新 ([api/reports.py](api/reports.py#L29-L58))

#### ReportListItem 模型
新增字段：
```python
scraping_progress: Optional[int]
scraping_eta: Optional[int]
report_progress: Optional[int]
report_eta: Optional[int]
```

#### ReportStatusResponse 模型
新增字段（同上）

### 4. 前端显示 ([static/index.html](static/index.html#L647-L704))

#### CSS 样式
新增双进度条样式：
- `.dual-progress-container`: 双进度条容器
- `.progress-bar-wrapper`: 单个进度条包装器
- `.progress-label`: 进度标签（名称 + 百分比 + ETA）
- `.progress-bar-bg`: 进度条背景
- `.progress-bar-fill.scraping`: 爬取进度条填充（蓝色渐变）
- `.progress-bar-fill.report`: 报告进度条填充（绿色渐变）

#### JavaScript 渲染
```javascript
const formatETA = (seconds) => {
    if (!seconds || seconds <= 0) return '';
    if (seconds < 60) return `${seconds}秒`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs > 0 ? `${mins}分${secs}秒` : `${mins}分`;
};
```

HTML 结构：
```html
<div class="dual-progress-container">
    <!-- 爬取进度条 -->
    <div class="progress-bar-wrapper">
        <div class="progress-label">
            <span class="progress-name">📥 爬取数据</span>
            <span class="progress-stats">50% · 2分30秒</span>
        </div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill scraping" style="width: 50%"></div>
        </div>
    </div>
    <!-- 报告生成进度条 -->
    <div class="progress-bar-wrapper">
        <div class="progress-label">
            <span class="progress-name">📊 生成报告</span>
            <span class="progress-stats">25% · 1分15秒</span>
        </div>
        <div class="progress-bar-bg">
            <div class="progress-bar-fill report" style="width: 25%"></div>
        </div>
    </div>
</div>
```

## 数据库迁移

执行迁移脚本：
```bash
python migrate_add_dual_progress.py
```

迁移内容：
- 添加 `scraping_progress` 字段（默认值：0）
- 添加 `scraping_eta` 字段（可为空）
- 添加 `report_progress` 字段（默认值：0）
- 添加 `report_eta` 字段（可为空）

## 使用场景

1. **用户触发报告生成**
2. **后台任务开始执行**
   - 爬取阶段：显示蓝色进度条，实时更新进度和 ETA
   - 报告生成阶段：显示绿色进度条，实时更新进度和 ETA
3. **前端轮询**
   - 每 3 秒轮询一次报告状态
   - 实时更新两个进度条的百分比和 ETA
4. **完成后停止轮询**

## 优势

✅ **用户体验改善**：
- 清晰区分两个独立阶段
- 准确的预计剩余时间
- 视觉上更直观（不同颜色）

✅ **技术优势**：
- 独立的进度追踪
- 精确的时间估算
- 向后兼容（保留旧的 `progress` 字段）

## 文件修改清单

1. ✅ [database/models.py](database/models.py) - 添加新字段到 Report 模型
2. ✅ [background_tasks.py](background_tasks.py) - 实现双进度更新和 ETA 计算
3. ✅ [api/reports.py](api/reports.py) - API 端点返回新字段
4. ✅ [static/index.html](static/index.html) - 前端显示双进度条
5. ✅ [migrate_add_dual_progress.py](migrate_add_dual_progress.py) - 数据库迁移脚本
6. ✅ [report_agent.py](report_agent.py) - 横向对比显示所有达人（修复前只显示前10个）

## 测试建议

1. 创建新报告，观察双进度条是否正常显示
2. 验证 ETA 计算是否准确
3. 确认爬取完成后，报告进度条开始更新
4. 检查完成后两个进度条都显示 100%
