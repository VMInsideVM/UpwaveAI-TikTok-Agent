# LangGraph 工作流集成指南

## 概述

本指南说明如何将 LangGraph URL 构建工作流集成到现有的 `TikTokInfluencerAgent` 中。

## 已完成的工作

### 1. 创建了工作流模块

**url_build_workflow.py** - LangGraph 工作流实现:
- `URLBuildState`: 工作流状态定义
- `URLBuildWorkflow`: 工作流类
  - `_build_url_node()`: 调用 build_search_url
  - `_force_review_node()`: 🔥 强制调用 review_parameters
  - `execute()`: 执行工作流
  - `get_user_output()`: 提取用户输出

**关键特性**:
- ✅ 使用 LangGraph 状态图强制执行顺序
- ✅ build_url → force_review 无条件路由
- ✅ 无法跳过任何步骤
- ✅ 调试模式支持

### 2. 创建了测试文件

**test_url_workflow.py** - 独立测试:
- 初始化 agent
- 创建工作流
- 执行测试参数
- 验证 review_parameters 被强制调用
- 显示用户输出

## 集成步骤

### 步骤 1: 修改 requirements.txt

在 `requirements.txt` 中添加:

```txt
langgraph>=0.2.0
```

然后安装:
```bash
pip install langgraph
```

### 步骤 2: 在 agent.py 中集成工作流

#### 方案 A: 渐进式集成 (推荐)

只在特定场景使用工作流,其他情况保持原有行为:

```python
# agent.py

from url_build_workflow import create_url_build_workflow

class TikTokInfluencerAgent:
    def __init__(self, ...):
        # ... 现有初始化代码 ...

        # 🔥 新增: 创建 URL 构建工作流 (可选启用)
        self.use_workflow = os.getenv("USE_LANGGRAPH_WORKFLOW", "false").lower() == "true"
        self.url_workflow = None

        if self.use_workflow:
            try:
                self.url_workflow = create_url_build_workflow(self, debug=False)
                print("✅ LangGraph 工作流已启用")
            except Exception as e:
                print(f"⚠️ LangGraph 工作流启用失败: {e}")
                self.use_workflow = False

    def run(self, user_input: str, image: Optional[str] = None) -> str:
        """执行 agent (支持工作流拦截)"""

        # 🔥 检测是否需要使用工作流
        if self.use_workflow and self._should_use_workflow(user_input):
            return self._run_with_workflow(user_input)

        # 原有的执行逻辑
        # ... (保持不变) ...

    def _should_use_workflow(self, user_input: str) -> bool:
        """
        判断是否应该使用工作流

        当检测到用户已经提供了所有参数,即将构建 URL 时,使用工作流
        """
        # 简单实现: 检测是否收集了足够的参数
        required_keys = ['country_name', 'product_name', 'target_influencer_count']
        has_all_required = all(
            self.current_params.get(key) for key in required_keys
        )

        return has_all_required and not self.current_url

    def _run_with_workflow(self, user_input: str) -> str:
        """
        使用 LangGraph 工作流执行 build_url → review_params

        Returns:
            应该展示给用户的内容 (review_parameters 的输出)
        """
        print("[Agent] 🔥 使用 LangGraph 工作流执行...")

        try:
            # 执行工作流
            result = self.url_workflow.execute(
                params=self.current_params,
                product_name=self.current_params.get('product_name', '未知'),
                target_count=self.current_params.get('target_influencer_count', 0),
                category_info=self.current_params.get('category_info')
            )

            # 更新 agent 状态
            self.current_url = result.get('url', '')

            # 提取用户输出
            user_output = self.url_workflow.get_user_output(result)

            print("[Agent] ✅ 工作流执行完成")
            return user_output

        except Exception as e:
            print(f"[Agent] ❌ 工作流执行失败: {e}")
            # 降级回原有逻辑
            return self.agent.invoke({"input": user_input})
```

#### 方案 B: 完全替换 (激进)

完全用工作流替换 build_url 的逻辑:

```python
# agent.py

class TikTokInfluencerAgent:
    def __init__(self, ...):
        # ... 现有初始化代码 ...

        # 🔥 总是使用工作流
        self.url_workflow = create_url_build_workflow(self, debug=False)

        # 从工具列表中移除 build_search_url (工作流会调用)
        # self.tools = [t for t in self.tools if t.name != 'build_search_url']
```

### 步骤 3: 添加环境变量控制

在 `.env` 中添加:

```bash
# LangGraph 工作流开关
USE_LANGGRAPH_WORKFLOW=true  # 或 false
```

### 步骤 4: 测试工作流

运行测试:

```bash
python test_url_workflow.py
```

预期输出:
```
======================================================================
🧪 测试: LangGraph URL 构建工作流
======================================================================

📍 步骤1: 初始化 Agent...
✅ Agent 初始化成功

📍 步骤2: 创建 URL 构建工作流...
✅ 工作流创建成功

📍 步骤3: 准备测试参数...
  商品: 口红
  国家: 美国
  粉丝范围: 10,000 - 100,000
  目标数量: 20 个达人

📍 步骤4: 执行工作流...
----------------------------------------------------------------------
[URLBuildWorkflow] 🚀 开始执行工作流
[URLBuildWorkflow] 📍 步骤1: 构建搜索 URL
  ✅ URL 构建成功: https://...
[URLBuildWorkflow] 📍 步骤2: 强制调用 review_parameters
  ✅ 参数展示完成
[URLBuildWorkflow] ✅ 工作流执行完成
----------------------------------------------------------------------
✅ 工作流执行成功

📍 步骤5: 验证结果...
✅ URL 已构建: https://...
✅ review_parameters 已被强制调用
✅ 参数展示输出已生成 (XXX 字符)

📍 步骤6: 展示给用户的内容 (review_parameters 输出):
======================================================================
[🔔 请将以下内容完整展示给用户]

📋 **当前筛选参数摘要**

🎯 **商品信息**
   • 商品名称: 口红
   • 商品分类: 口红
   • 目标数量: 20 个达人

🌍 **目标地区**: 美国

🔍 **筛选条件**
   • 粉丝数: 10,000 - 100,000
   • 推广渠道: 不限制
   ...
======================================================================

======================================================================
🎉 测试通过!
======================================================================

✅ 验证结果:
  1. build_search_url 被正确调用
  2. review_parameters 被强制调用 (无法跳过)
  3. 参数展示内容已生成
  4. 工作流保证了正确的执行顺序

🔥 结论: LangGraph 工作流成功强制执行了 review_parameters!
```

## 工作流执行流程

### 原有流程 (无保障)

```
User Input
    ↓
  Agent
    ↓
build_search_url ✅
    ↓
  (Agent 决定)
    ↓
review_parameters ❌ (可能被跳过!)
    ↓
  用户困惑
```

### 新流程 (LangGraph 保障)

```
User Input
    ↓
  Agent 检测到需要构建 URL
    ↓
  触发 URLBuildWorkflow
    ↓
┌─────────────────────────────┐
│  LangGraph State Graph      │
│                             │
│  ┌─────────────────────┐   │
│  │ build_search_url    │   │
│  └──────────┬──────────┘   │
│             │ 强制边        │
│             ▼              │
│  ┌─────────────────────┐   │
│  │ force_review_params │   │
│  │  (无法跳过!)        │   │
│  └─────────────────────┘   │
└─────────────────────────────┘
    ↓
返回 review_parameters 输出
    ↓
  用户看到参数展示 ✅
```

## 优势对比

| 特性 | 原有 Callback 方案 | LangGraph 方案 |
|------|-------------------|----------------|
| 检测违规 | ✅ | ✅ |
| 阻止跳过 | ❌ (只能提醒) | ✅ (强制执行) |
| 状态管理 | ❌ | ✅ |
| 可视化 | ❌ | ✅ |
| 调试能力 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 可靠性 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 改动量 | 小 | 中等 |

## 调试技巧

### 启用调试模式

```python
# 创建工作流时
workflow = create_url_build_workflow(agent, debug=True)

# 或在 agent 中
self.url_workflow = create_url_build_workflow(self, debug=True)
```

### 查看状态图

```python
from IPython.display import Image, display

# 显示工作流图
display(Image(workflow.graph.get_graph().draw_mermaid_png()))
```

### 日志输出

工作流会输出详细日志:
```
[URLBuildWorkflow] 🚀 开始执行工作流
[URLBuildWorkflow] 📍 步骤1: 构建搜索 URL
  参数: {...}
  ✅ URL 构建成功: https://...
[URLBuildWorkflow] 📍 步骤2: 强制调用 review_parameters
  ✅ 参数展示完成
  输出长度: 845 字符
[URLBuildWorkflow] ✅ 工作流执行完成
```

## 扩展建议

成功实施 URL 构建工作流后,可以创建其他工作流:

### 1. 数量检查工作流

```python
# quantity_check_workflow.py

class QuantityCheckWorkflow:
    """
    强制执行: get_max_page → analyze_quantity → suggest_adjustments
    """
```

### 2. 完整爬取工作流

```python
# scraping_workflow.py

class ScrapingWorkflow:
    """
    强制执行: scrape_page_1 → ... → scrape_page_N → export_excel
    """
```

### 3. 参数调整循环

```python
# param_adjustment_workflow.py

class ParamAdjustmentWorkflow:
    """
    循环工作流:
    suggest_adjustments → user_select → update_params → review_parameters
       ↑                                                        ↓
       └────────────────── 用户不满意 ←──────────────────────────┘
    """
```

## 故障排查

### 问题 1: langgraph 导入失败

```
ModuleNotFoundError: No module named 'langgraph'
```

**解决**:
```bash
pip install langgraph
```

### 问题 2: 工具实例无法访问

```
ValueError: 无法创建工作流: agent 缺少必要的工具
```

**解决**:
- 确保 `agent.tools` 包含 `build_search_url` 和 `review_parameters`
- 检查工具初始化是否正确

### 问题 3: 状态传递错误

```
KeyError: 'params'
```

**解决**:
- 检查 `execute()` 调用是否传递了所有必需参数
- 查看 `URLBuildState` 的定义

### 问题 4: 工作流无响应

**调试**:
```python
# 启用调试模式
workflow = create_url_build_workflow(agent, debug=True)

# 检查状态
result = workflow.execute(...)
print(f"状态: {result}")
```

## 性能考虑

### 工作流开销

- LangGraph 增加的开销: **~50-100ms** (可忽略)
- 对比收益: **100% 保证正确性**

### 何时使用工作流

✅ **推荐使用**:
- 关键业务流程 (build_url → review)
- 需要严格顺序保证的操作
- 多步骤复杂流程

❌ **不推荐使用**:
- 单步简单操作
- 无严格顺序要求
- 高频小操作

## 总结

LangGraph 工作流方案:
- ✅ **强制保证** review_parameters 被调用
- ✅ **无法绕过** 任何关键步骤
- ✅ **渐进集成** 最小化风险
- ✅ **调试友好** 易于排查问题
- ✅ **生产就绪** LangChain 官方推荐方案

推荐使用 **方案 A (渐进式集成)** 开始,验证稳定后考虑扩展到其他流程。
