# LangGraph Evaluator 模式改进方案

## 背景

当前使用 LangChain Callback (`WorkflowEnforcer`) 监督 agent 行为:
- **问题**: Agent 调用 `build_search_url` 后经常忘记调用 `review_parameters`
- **现状**: Callback 只能检测违规并注入提醒,但无法强制执行

## LangGraph Evaluator/Optimizer 模式

根据 [LangGraph workflows-agents 文档](https://docs.langchain.com/oss/python/langgraph/workflows-agents),Evaluator 模式提供:

1. **主动质量检查**: Evaluator 作为独立节点,检查输出的准确性和一致性
2. **条件路由**: 检测到问题时,自动路由回 Planner 或其他节点重试
3. **显式状态管理**: 使用状态机管理工作流,便于调试和回滚

## 架构设计

### 当前架构 (LangChain ReAct)

```
┌───────────────────────────────────────────────┐
│            LangChain ReAct Agent             │
│  ┌─────────────────────────────────────────┐ │
│  │  Tools: build_search_url, ...           │ │
│  │  WorkflowEnforcer (Callback) 监督       │ │
│  └─────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
         │
         │ 违规检测 (被动)
         ▼
    ⚠️ 注入提醒消息 (可能被忽略)
```

### 改进架构 (LangGraph + Evaluator)

```
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph State Graph                     │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌───────────────┐      │
│  │  START   │──▶│ build_search │──▶│   Evaluator   │      │
│  └──────────┘   │     _url     │   │  (检查是否调用 │      │
│                 └──────────────┘   │  review_params)│      │
│                                    └───────┬───────┘       │
│                                            │               │
│                       ┌────────────────────┴────────┐      │
│                       │                             │      │
│                       ▼                             ▼      │
│              ┌────────────────┐          ┌──────────────┐ │
│              │ review_params  │          │   继续执行    │ │
│              │  (强制调用)    │          │              │ │
│              └────────┬───────┘          └──────────────┘ │
│                       │                                    │
│                       ▼                                    │
│                  ✅ 继续流程                                │
└─────────────────────────────────────────────────────────────┘
```

## 实现方案

### 方案 1: 完全重构为 LangGraph (推荐,但工作量大)

**优点**:
- ✅ 完全控制工作流
- ✅ 状态持久化和回滚
- ✅ 条件路由保证正确性
- ✅ 更好的调试和可视化

**缺点**:
- ❌ 需要重写整个 agent.py
- ❌ 迁移成本高
- ❌ 学习曲线陡峭

**代码示例**:

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage

# 定义状态
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "聊天消息历史"]
    search_url: str  # build_search_url 的输出
    parameters_reviewed: bool  # 是否已调用 review_parameters
    user_confirmed: bool  # 用户是否确认

# 定义节点
def build_url_node(state: AgentState):
    """调用 build_search_url 工具"""
    # ... 调用工具逻辑
    return {"search_url": url, "parameters_reviewed": False}

def evaluator_node(state: AgentState):
    """评估是否需要调用 review_parameters"""
    if state["search_url"] and not state["parameters_reviewed"]:
        return {"next": "review_parameters"}  # 强制路由到 review_parameters
    return {"next": "continue"}

def review_params_node(state: AgentState):
    """调用 review_parameters 工具"""
    # ... 调用工具逻辑
    return {"parameters_reviewed": True}

# 构建图
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("build_url", build_url_node)
workflow.add_node("evaluator", evaluator_node)
workflow.add_node("review_params", review_params_node)

# 添加边
workflow.set_entry_point("build_url")
workflow.add_edge("build_url", "evaluator")

# 条件路由
workflow.add_conditional_edges(
    "evaluator",
    lambda x: x["next"],
    {
        "review_parameters": "review_params",
        "continue": END
    }
)

workflow.add_edge("review_params", END)

# 编译
app = workflow.compile()
```

### 方案 2: 混合方案 - 在关键节点使用 LangGraph (推荐 ✅)

**思路**:
- 保留现有的 LangChain ReAct agent
- 对于关键工作流 (build_url → review_params),用 LangGraph 包装
- 最小化改动,渐进式迁移

**优点**:
- ✅ 改动量小,风险低
- ✅ 关键流程得到强制保障
- ✅ 可以逐步迁移其他流程
- ✅ 保留现有工具定义

**缺点**:
- ⚠️ 架构混合,略微复杂

**实现思路**:

```python
from langgraph.graph import StateGraph
from agent import TikTokInfluencerAgent

class URLBuildWorkflow:
    """
    使用 LangGraph 强制执行 build_url → review_params 工作流
    """
    def __init__(self, agent: TikTokInfluencerAgent):
        self.agent = agent
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(dict)

        # 节点1: build_search_url
        workflow.add_node("build_url", self._build_url_step)

        # 节点2: review_parameters (强制调用)
        workflow.add_node("review_params", self._review_params_step)

        # 节点3: 等待用户确认
        workflow.add_node("wait_confirm", self._wait_confirm_step)

        # 边
        workflow.set_entry_point("build_url")
        workflow.add_edge("build_url", "review_params")  # 强制路由
        workflow.add_edge("review_params", "wait_confirm")

        # 条件路由: 用户确认后继续或返回修改
        workflow.add_conditional_edges(
            "wait_confirm",
            lambda x: x.get("user_action"),
            {
                "confirmed": END,
                "modify": "build_url"  # 循环回去
            }
        )

        return workflow.compile()

    def _build_url_step(self, state):
        """调用 build_search_url 工具"""
        # 调用现有工具
        result = self.agent.tools['build_search_url'].invoke(state['params'])
        return {"url": result, "step": "review_params"}

    def _review_params_step(self, state):
        """强制调用 review_parameters"""
        result = self.agent.tools['review_parameters'].invoke({})
        # 必须将结果展示给用户
        print(result)  # 或通过回调发送给用户
        return {"reviewed": True, "step": "wait_confirm"}

    def _wait_confirm_step(self, state):
        """等待用户确认"""
        # 这里需要与主 agent 交互,获取用户输入
        user_input = self.agent.get_user_input()
        if "确认" in user_input or "可以" in user_input:
            return {"user_action": "confirmed"}
        else:
            return {"user_action": "modify"}

    def execute(self, params):
        """执行工作流"""
        return self.graph.invoke({"params": params})

# 在 agent.py 中集成:
class TikTokInfluencerAgent:
    def __init__(self):
        # ... 现有初始化
        self.url_workflow = URLBuildWorkflow(self)  # 添加工作流

    def run(self, user_input):
        # 检测是否需要使用工作流
        if self._should_use_url_workflow(user_input):
            return self.url_workflow.execute(user_input)
        else:
            # 使用现有的 ReAct agent
            return self.agent_executor.invoke(...)
```

### 方案 3: 增强现有 WorkflowEnforcer (最简单 ✅✅)

**思路**:
- 不改架构,增强现有的 `WorkflowEnforcer`
- 让 enforcer 直接拦截并强制调用 `review_parameters`
- 使用 LangChain 的 `AgentExecutor.step()` 方法注入强制工具调用

**优点**:
- ✅ 改动最小
- ✅ 无需学习 LangGraph
- ✅ 快速实施

**缺点**:
- ⚠️ 仍然是被动监督,不如 LangGraph 优雅

**实现代码**:

```python
# workflow_enforcer.py

from langchain_core.agents import AgentAction

class EnhancedWorkflowEnforcer(BaseCallbackHandler):
    """增强版工作流强制执行器"""

    def __init__(self, agent_executor, debug: bool = False):
        super().__init__()
        self.agent_executor = agent_executor
        self.debug = debug
        self.expect_review_parameters = False
        self.pending_action = None  # 待注入的强制动作

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """工具执行完成时的回调"""
        tool_name = self.tool_call_history[-1]['name']

        if tool_name == 'build_search_url':
            self.expect_review_parameters = True
            # 🔥 关键: 准备强制动作
            self.pending_action = AgentAction(
                tool='review_parameters',
                tool_input={},
                log='[系统强制调用] review_parameters'
            )
            if self.debug:
                print("[Enforcer] ⚠️ 准备强制调用 review_parameters")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """LLM 生成完成时的回调"""
        # 检查是否违反工作流
        if self.expect_review_parameters:
            has_review_call = self._check_review_call(response)

            if not has_review_call:
                if self.debug:
                    print("[Enforcer] ❌ 检测到违规! 强制注入 review_parameters")

                # 🔥 强制注入工具调用
                self._inject_forced_action()

    def _inject_forced_action(self):
        """注入强制工具调用"""
        if self.pending_action:
            # 使用 agent_executor 的内部方法执行强制动作
            # 这需要访问 agent_executor 的私有方法
            result = self.agent_executor.agent.run_tool(
                self.pending_action.tool,
                self.pending_action.tool_input
            )

            # 将结果添加到对话历史
            self.agent_executor.memory.chat_memory.add_message(
                AIMessage(content=result)
            )

            self.expect_review_parameters = False
            self.pending_action = None

# 在 agent.py 中使用:
enforcer = EnhancedWorkflowEnforcer(self.agent_executor, debug=True)
self.agent_executor = AgentExecutor(
    agent=self.agent,
    tools=tools,
    callbacks=[enforcer],  # 注入增强版 enforcer
    # ...
)
```

## 推荐方案对比

| 方案 | 改动量 | 有效性 | 学习成本 | 推荐度 |
|------|--------|--------|----------|--------|
| 方案1: 完全 LangGraph | 大 (重写) | ⭐⭐⭐⭐⭐ | 高 | ⭐⭐⭐ |
| 方案2: 混合 LangGraph | 中等 | ⭐⭐⭐⭐⭐ | 中 | ⭐⭐⭐⭐⭐ |
| 方案3: 增强 Enforcer | 小 | ⭐⭐⭐ | 低 | ⭐⭐⭐⭐ |

## 最终推荐: 方案 2 (混合 LangGraph)

### 实施步骤

#### 第1步: 安装 LangGraph

```bash
pip install langgraph
```

#### 第2步: 创建 URL 构建工作流

创建新文件 `url_build_workflow.py`:

```python
"""
使用 LangGraph 强制执行 build_url → review_params 工作流
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Literal
from langchain_core.messages import HumanMessage, AIMessage

class URLBuildState(TypedDict):
    """URL 构建工作流状态"""
    params: dict  # 用户参数
    url: str  # 构建的 URL
    parameters_reviewed: bool  # 是否已展示参数
    user_confirmed: bool  # 用户是否确认
    messages: list  # 消息历史

class URLBuildWorkflow:
    """强制执行 build_url → review_params 的工作流"""

    def __init__(self, build_url_tool, review_params_tool, debug=False):
        self.build_url_tool = build_url_tool
        self.review_params_tool = review_params_tool
        self.debug = debug
        self.graph = self._build_graph()

    def _build_graph(self):
        """构建状态图"""
        workflow = StateGraph(URLBuildState)

        # 添加节点
        workflow.add_node("build_url", self._build_url_node)
        workflow.add_node("force_review", self._force_review_node)  # 🔥 强制节点

        # 设置入口
        workflow.set_entry_point("build_url")

        # 强制路由: build_url → force_review (无条件)
        workflow.add_edge("build_url", "force_review")

        # 强制 review 后结束
        workflow.add_edge("force_review", END)

        return workflow.compile()

    def _build_url_node(self, state: URLBuildState):
        """调用 build_search_url 工具"""
        if self.debug:
            print("[URLBuildWorkflow] 步骤1: 构建搜索 URL")

        result = self.build_url_tool.invoke(state['params'])

        return {
            "url": result,
            "parameters_reviewed": False,
            "messages": state.get("messages", []) + [
                AIMessage(content=f"✅ URL 构建完成: {result}")
            ]
        }

    def _force_review_node(self, state: URLBuildState):
        """🔥 强制调用 review_parameters 工具"""
        if self.debug:
            print("[URLBuildWorkflow] 步骤2: 强制调用 review_parameters")

        # 无条件调用 review_parameters
        result = self.review_params_tool.invoke({})

        return {
            "parameters_reviewed": True,
            "messages": state.get("messages", []) + [
                AIMessage(content=result)  # 将参数展示添加到消息
            ]
        }

    def execute(self, params: dict) -> dict:
        """
        执行工作流

        Args:
            params: 用户参数 (传递给 build_url_tool)

        Returns:
            执行结果,包含 url 和展示的参数
        """
        initial_state = {
            "params": params,
            "url": "",
            "parameters_reviewed": False,
            "user_confirmed": False,
            "messages": []
        }

        result = self.graph.invoke(initial_state)

        if self.debug:
            print(f"[URLBuildWorkflow] ✅ 工作流完成")
            print(f"  - URL: {result['url']}")
            print(f"  - 参数已展示: {result['parameters_reviewed']}")

        return result
```

#### 第3步: 在 agent.py 中集成

修改 `agent.py`:

```python
# agent.py

from url_build_workflow import URLBuildWorkflow

class TikTokInfluencerAgent:
    def __init__(self, ...):
        # ... 现有初始化代码

        # 🔥 新增: 创建 URL 构建工作流
        from agent_tools import BuildURLTool, ReviewParametersTool

        build_url_tool = BuildURLTool()
        review_params_tool = ReviewParametersTool(self.current_params)

        self.url_workflow = URLBuildWorkflow(
            build_url_tool=build_url_tool,
            review_params_tool=review_params_tool,
            debug=self.debug
        )

    def _should_use_workflow(self, tool_name: str) -> bool:
        """判断是否应该使用工作流"""
        return tool_name == 'build_search_url'

    def run_with_workflow(self, user_input: str):
        """
        使用工作流执行 (当检测到需要 build_url 时)
        """
        # 1. 先让 agent 解析用户输入,提取参数
        # (这部分可以用现有的 agent 或单独的 LLM 调用)

        # 2. 使用工作流强制执行 build_url → review_params
        result = self.url_workflow.execute(self.current_params)

        # 3. 将工作流的输出 (参数展示) 返回给用户
        return result['messages'][-1].content  # 返回 review_parameters 的输出
```

#### 第4步: 测试工作流

创建测试文件 `test_url_workflow.py`:

```python
"""测试 URL 构建工作流"""

from url_build_workflow import URLBuildWorkflow
from agent_tools import BuildURLTool, ReviewParametersTool

# 模拟参数
test_params = {
    "country_name": "美国",
    "product_name": "口红",
    "follower_min": 10000,
    "follower_max": 100000
}

# 创建工具实例
build_tool = BuildURLTool()
review_tool = ReviewParametersTool(test_params)

# 创建工作流
workflow = URLBuildWorkflow(
    build_url_tool=build_tool,
    review_params_tool=review_tool,
    debug=True
)

# 执行工作流
print("=" * 60)
print("测试: 强制执行 build_url → review_params 工作流")
print("=" * 60)

result = workflow.execute(test_params)

print("\n工作流执行结果:")
print(f"✅ URL: {result['url']}")
print(f"✅ 参数已展示: {result['parameters_reviewed']}")
print(f"\n展示给用户的内容:")
for msg in result['messages']:
    print(f"  {msg.content}")

print("\n✅ 测试通过: review_parameters 被强制调用!")
```

运行测试:
```bash
python test_url_workflow.py
```

预期输出:
```
============================================================
测试: 强制执行 build_url → review_params 工作流
============================================================
[URLBuildWorkflow] 步骤1: 构建搜索 URL
[URLBuildWorkflow] 步骤2: 强制调用 review_parameters
[URLBuildWorkflow] ✅ 工作流完成
  - URL: https://...
  - 参数已展示: True

展示给用户的内容:
  ✅ URL 构建完成: https://...

  📋 当前搜索参数:
  - 国家: 美国
  - 商品: 口红
  - 粉丝数: 10,000 - 100,000

  请确认参数是否正确？

✅ 测试通过: review_parameters 被强制调用!
```

## 优势总结

使用 LangGraph Evaluator 模式后:

1. **✅ 强制保证**: `build_search_url` 后**必定**调用 `review_parameters`
2. **✅ 无法绕过**: 使用图的边定义,agent 无法跳过步骤
3. **✅ 状态可见**: 明确知道当前处于哪个步骤
4. **✅ 易于调试**: 可视化工作流,快速定位问题
5. **✅ 渐进迁移**: 关键流程先用 LangGraph,其他保持不变
6. **✅ 生产就绪**: LangGraph 是 LangChain 官方推荐的生产级方案

## 后续扩展

成功实施 URL 构建工作流后,可以扩展到其他关键流程:

1. **数量检查工作流**: `get_max_page → analyze_quantity → suggest_adjustments`
2. **爬取工作流**: `scrape_page_1 → scrape_page_2 → ... → export_excel`
3. **参数调整工作流**: `suggest → user_select → update_params → review`

最终可以将整个 agent 迁移到 LangGraph,获得:
- 完整的状态管理
- 持久化和恢复
- 多 agent 协作
- Human-in-the-loop 支持

## 参考资料

- [LangGraph workflows-agents 文档](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph 示例: Trace and Evaluate Agents](https://langfuse.com/guides/cookbook/example_langgraph_agents)
- [GitHub: langchain-ai/agentevals](https://github.com/langchain-ai/agentevals)
- [Best AI Agent Frameworks 2025: LangGraph 分析](https://www.getmaxim.ai/articles/top-5-ai-agent-frameworks-in-2025-a-practical-guide-for-ai-builders/)

---

**结论**: 推荐使用 **方案2 (混合 LangGraph)** 来强制执行 `review_parameters` 调用,既保证了正确性,又最小化了改动风险。
