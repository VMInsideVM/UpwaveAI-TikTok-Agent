# Target Count 硬编码修复文档

## 问题描述

**现象：**
- ✅ 用户请求：需要 2 个达人
- ❌ 实际生成：报告显示 40 个达人（Tier 1）
- ❌ 原因：`target_count` 硬编码为 10

**用户反馈：**
> "为什么我要找2个达人，生成的报告只有Tier1的40个达人"
> "target_count是不是硬编码成10了，而不是用户需要的达人数量"

**错误影响：**
1. Tier 计算错误：10×4=40（Tier 1）, 10×3=30（Tier 2）, 10×2=20（Tier 3）
2. 应该是：2×4=8, 2×3=6, 2×2=4，总共 18 个达人
3. 比较表只显示前 10 个，而不是所有达人

---

## 问题根因

### 硬编码位置

**文件：** [agent_tools.py:1094](agent_tools.py#L1094)

```python
def _collect_report_parameters(self, product_name: str) -> dict:
    # ...
    # 2. 固定 target_count = 10（每层 10 个达人）
    target_count = 10  # ❌ 硬编码！

    return {
        'user_query': user_query,
        'target_count': target_count,  # 总是 10
        'product_info': product_info
    }
```

### 为什么会有这个问题？

1. **Agent 有 `target_influencer_count` 属性但从未设置**
   - [agent.py:55](agent.py#L55) 定义了：`self.target_influencer_count = None`
   - 但在整个流程中没有任何地方给它赋值

2. **工作流程中缺少捕获步骤**
   - 步骤 1 要求"提取用户需要的达人数量并记录"
   - 但没有工具负责捕获并存储这个值

3. **报告生成时无法获取用户实际需求**
   - `SubmitSearchTaskTool._collect_report_parameters()` 无法访问用户请求的数量
   - 只能使用硬编码的默认值 10

---

## 解决方案

### 整体策略

采用**参数传递链**策略，确保用户请求的达人数量从输入到报告生成全程可追踪：

```
用户输入 → BuildURLTool → Agent.target_influencer_count → _collect_report_parameters → ReportAgent
```

### 修改 1: 添加 target_count 参数到 BuildURLInput

**文件：** [agent_tools.py:153-167](agent_tools.py#L153-L167)

**改动：**
```python
class BuildURLInput(BaseModel):
    """构建 URL 的输入参数"""
    # ... 现有参数 ...
    target_influencer_count: Optional[int] = Field(
        default=None,
        description="用户需要的达人数量（用于后续报告生成）"
    )  # ⭐ 新增
```

**原因：**
- BuildURLTool 是 Agent 收集参数的核心工具
- 在这里捕获 target_count 可以确保它被存储到 Agent 实例

---

### 修改 2: BuildURLTool 存储目标数量

**文件：** [agent_tools.py:225-248](agent_tools.py#L225-L248)

**改动：**
```python
def _run(
    self,
    # ... 现有参数 ...
    target_influencer_count: Optional[int] = None  # ⭐ 新增参数
) -> str:
    """执行 URL 构建"""
    try:
        agent = get_agent_instance()
        if agent:
            # ... 存储现有参数 ...

            # ⭐ 存储目标达人数量
            if target_influencer_count is not None:
                agent.target_influencer_count = target_influencer_count
                agent.current_params['target_count'] = target_influencer_count
```

**关键点：**
1. 同时存储到两个地方：
   - `agent.target_influencer_count` - Agent 实例属性
   - `agent.current_params['target_count']` - 参数字典（用于 review_parameters）

2. 只在用户明确提供时存储（`is not None`）

---

### 修改 3: 更新工具描述

**文件：** [agent_tools.py:197-207](agent_tools.py#L197-L207)

**改动：**
```python
class BuildURLTool(BaseTool):
    description: str = """
    ...
    参数说明:
    - country_name: 国家名称,如"美国"、"全部"
    - promotion_channel: "all"(全部)/"video"(短视频)/"live"(直播)
    - affiliate_check: True=只显示联盟达人, False=不限制
    - followers_min/max: 粉丝数范围,如 100000, 500000
    - target_influencer_count: 用户需要的达人数量（必须传入！用于后续报告生成）  # ⭐ 新增
    """
```

**原因：**
- LLM 需要知道这个参数的存在
- 强调"必须传入"提高 Agent 使用概率

---

### 修改 4: 更新 _collect_report_parameters 逻辑

**文件：** [agent_tools.py:1101-1103](agent_tools.py#L1101-L1103)

**修改前：**
```python
# 2. 固定 target_count = 10（每层 10 个达人）
target_count = 10
```

**修改后：**
```python
# 2. ⭐ 从 Agent 获取用户请求的达人数量（不再硬编码！）
target_count = agent.target_influencer_count if agent.target_influencer_count else 10
print(f"📊 报告生成使用的目标达人数: {target_count} (来源: {'用户指定' if agent.target_influencer_count else '默认值'})")
```

**优势：**
1. ✅ 优先使用用户指定的数量
2. ✅ 提供默认值 10（兜底）
3. ✅ 打印日志便于调试

---

### 修改 5: 更新 Agent 工作流程提示

**文件：** [agent.py:113-117](agent.py#L113-L117)

**改动：**
```python
3. **构建搜索 URL**: 使用 build_search_url 工具构建 URL
   - 传入所有收集到的筛选参数
   - ⚠️ **必须传入 target_influencer_count 参数**（用户需要的达人数量）  # ⭐ 新增
   - 工具会自动将参数存储起来
   - ✅ 完成后立即进入步骤4
```

**文件：** [agent.py:119-121](agent.py#L119-L121)

**改动：**
```python
4. **【关键步骤】参数确认循环 - 必须执行，严禁跳过！**:
   - ⚠️ **完成步骤3后，你必须立即调用 review_parameters 工具**，这是强制性步骤！
   - **调用时必须传入**: current_params（已存储的参数）, product_name,
     target_count（从 current_params['target_count'] 获取）, category_info  # ⭐ 新增
```

**原因：**
- 明确告诉 Agent 必须传递这个参数
- 指明如何获取参数值（从 current_params）

---

## 完整数据流

### 修复后的完整流程

```
┌──────────────────────────────────────────────────────────────┐
│ 步骤 1: 用户输入                                              │
│ "我要推广女士香水，需要 2 个达人"                              │
└─────────────────┬────────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────────────────────┐
│ 步骤 2: Agent 解析需求                                        │
│ - 提取商品名：女士香水                                        │
│ - 提取数量：2                                                 │
└─────────────────┬────────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────────────────────┐
│ 步骤 3: 调用 build_search_url 工具                            │
│ BuildURLTool._run(                                           │
│     country_name="美国",                                      │
│     followers_min=100000,                                    │
│     followers_max=250000,                                    │
│     target_influencer_count=2  ⭐ 传入用户需求                │
│ )                                                            │
└─────────────────┬────────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────────────────────┐
│ 步骤 4: BuildURLTool 存储参数                                 │
│ agent.target_influencer_count = 2                            │
│ agent.current_params['target_count'] = 2                     │
└─────────────────┬────────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────────────────────┐
│ 步骤 5: 调用 review_parameters 工具                           │
│ ReviewParametersTool._run(                                   │
│     current_params=agent.current_params,                     │
│     product_name="女士香水",                                  │
│     target_count=agent.current_params['target_count'],  # 2  │
│     category_info={...}                                      │
│ )                                                            │
└─────────────────┬────────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────────────────────┐
│ 步骤 6: 用户确认，提交搜索任务                                 │
│ SubmitSearchTaskTool._run(...)                               │
└─────────────────┬────────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────────────────────┐
│ 步骤 7: 收集报告参数                                          │
│ _collect_report_parameters():                                │
│   target_count = agent.target_influencer_count  # ✅ 读取 2   │
│   打印: "📊 报告生成使用的目标达人数: 2 (来源: 用户指定)"      │
└─────────────────┬────────────────────────────────────────────┘
                  ▼
┌──────────────────────────────────────────────────────────────┐
│ 步骤 8: 报告生成（ReportAgent）                               │
│ - Tier 1: 2 × 4 = 8 个达人                                   │
│ - Tier 2: 2 × 3 = 6 个达人                                   │
│ - Tier 3: 2 × 2 = 4 个达人                                   │
│ - 总计: 18 个达人 ✅ 正确！                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 测试验证

### 测试用例 1: 用户请求 2 个达人

**输入：**
```
用户: 我要推广女士香水，目标美国市场，需要 2 个达人
```

**期望 Agent 行为：**
```python
# Agent 调用 build_search_url
build_search_url(
    country_name="美国",
    followers_min=100000,
    followers_max=250000,
    target_influencer_count=2  # ⭐ 必须传入
)

# Agent 调用 review_parameters
review_parameters(
    current_params={...},
    product_name="女士香水",
    target_count=2,  # ⭐ 从 current_params 获取
    category_info={...}
)
```

**期望输出：**
```
📋 **当前筛选参数摘要**

🎯 **商品信息**
   • 商品名称: 女士香水
   • 商品分类: 美妆个护 > 香水彩妆 > 女士香水
   • 目标数量: 2 个达人  ✅ 显示正确
```

**期望报告结果：**
```
生成时间: 2025-12-17 18:00:00
分析达人数: 40
推荐达人数: 18  ✅ 正确（2×4 + 2×3 + 2×2）

推荐层级:
- Tier 1 (深度分析): 8 个达人  ✅ 2×4
- Tier 2 (标准分析): 6 个达人  ✅ 2×3
- Tier 3 (基础分析): 4 个达人  ✅ 2×2
```

---

### 测试用例 2: 用户未指定数量（使用默认值）

**输入：**
```
用户: 我要推广女士香水，目标美国市场
```

**期望行为：**
```python
# Agent 可能不传 target_influencer_count（或传 None）
build_search_url(
    country_name="美国",
    followers_min=100000,
    followers_max=250000
    # target_influencer_count 未传或为 None
)

# _collect_report_parameters 使用默认值
target_count = agent.target_influencer_count or 10  # → 10
```

**期望日志：**
```
📊 报告生成使用的目标达人数: 10 (来源: 默认值)
```

**期望报告结果：**
```
推荐达人数: 90  ✅ 使用默认值（10×4 + 10×3 + 10×2）
```

---

### 测试用例 3: 用户请求大量达人

**输入：**
```
用户: 我要推广女士香水，需要 50 个达人
```

**期望报告结果：**
```
推荐层级:
- Tier 1 (深度分析): 40 个达人（受限于实际可用数量）
- Tier 2 (标准分析): 30 个达人（如果有足够达人）
- Tier 3 (基础分析): 20 个达人（如果有足够达人）

⚠️ 注意：如果实际可用达人不足 50×9=450 个，报告会根据实际情况调整
```

---

## 调试方法

### 1. 验证参数是否传递

在聊天界面观察 Agent 的工具调用：

```
Agent: [调用工具] build_search_url
参数:
  country_name: "美国"
  followers_min: 100000
  followers_max: 250000
  target_influencer_count: 2  ⭐ 检查是否存在

Agent: [调用工具] review_parameters
参数:
  current_params: {...}
  product_name: "女士香水"
  target_count: 2  ⭐ 检查是否正确
```

### 2. 查看终端日志

启动聊天机器人后，提交任务时观察终端输出：

```bash
📊 报告生成使用的目标达人数: 2 (来源: 用户指定)  ✅ 正确
```

或：

```bash
📊 报告生成使用的目标达人数: 10 (来源: 默认值)  ⚠️ Agent 未传递 target_count
```

### 3. 检查生成的报告

打开生成的 HTML 报告，查看头部信息：

```html
<div class="report-header">
    <h1>TikTok 达人推荐报告</h1>
    <p>生成时间: 2025-12-17 18:00:00 | 分析达人数: 40 | 推荐达人数: 18</p>
    <!--                                                            ^^
         应该是 target_count × 9，例如 2×9=18 -->
</div>
```

---

## 已知限制

### 1. Agent 可能忘记传递参数

**问题：**
- LLM 可能忽略 `target_influencer_count` 参数
- 即使提示词中强调"必须传入"

**缓解措施：**
- 已在工具描述、工作流程、重要规则三处强调
- 提供默认值 10 作为兜底

**未来改进：**
- 可以在 BuildURLTool 中强制提示 Agent：
  ```python
  if target_influencer_count is None:
      return "⚠️ 警告：你没有传入 target_influencer_count，请先询问用户需要多少个达人！"
  ```

### 2. 用户模糊表达数量

**问题：**
- 用户说"一些达人"、"几个达人"
- Agent 难以提取具体数字

**缓解措施：**
- Agent 会使用默认值 10
- 或者 Agent 会反问用户："您需要多少个达人？"

### 3. 实际可用达人不足

**问题：**
- 用户请求 50 个达人
- 但筛选后只有 20 个符合条件

**处理逻辑（report_agent.py）：**
```python
# 如果可用达人不足，会自动调整 tier 分配
available = len(influencers)  # 例如 20
needed = target_count * 9     # 50 * 9 = 450

if available < needed:
    # 优先分配 Tier 1，然后 Tier 2，最后 Tier 3
    tier1_count = min(available, target_count * 4)
    remaining = available - tier1_count
    tier2_count = min(remaining, target_count * 3)
    tier3_count = available - tier1_count - tier2_count
```

**结果示例：**
```
可用达人: 20 个
请求: 50 个

实际分配:
- Tier 1: 20 个（全部）
- Tier 2: 0 个
- Tier 3: 0 个
```

---

## 相关文件

| 文件 | 修改内容 | 行号 |
|------|---------|------|
| [agent_tools.py](agent_tools.py) | BuildURLInput 添加 target_influencer_count 字段 | 167 |
| [agent_tools.py](agent_tools.py) | BuildURLTool 描述添加参数说明 | 207 |
| [agent_tools.py](agent_tools.py) | BuildURLTool._run() 添加参数并存储到 Agent | 225, 245-248 |
| [agent_tools.py](agent_tools.py) | _collect_report_parameters 使用动态 target_count | 1101-1103 |
| [agent.py](agent.py) | 工作流程步骤 3 添加参数传递提示 | 115 |
| [agent.py](agent.py) | 工作流程步骤 4 添加调用说明 | 121 |

---

## 总结

✅ **修复前**：
- target_count 硬编码为 10
- 用户请求 2 个达人 → 生成 90 个推荐（10×9）
- 无法满足用户实际需求

✅ **修复后**：
- target_count 从用户输入提取
- 用户请求 2 个达人 → 生成 18 个推荐（2×9）
- 符合用户期望

✅ **核心思路**：
- 在 BuildURLTool 捕获用户需求
- 存储到 Agent.target_influencer_count
- 报告生成时读取并使用

✅ **兜底机制**：
- 如果 Agent 未传递参数 → 使用默认值 10
- 打印日志便于调试："📊 报告生成使用的目标达人数: X (来源: ...)"
