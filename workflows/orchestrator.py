"""
Orchestrator-Worker 工作流

处理用户非预期输入（提问、请求建议、无关话题等），引导用户回到主流程。

使用 LLM 结构化输出进行意图分类，然后路由到对应的 Worker 处理。
"""

import os
from typing import Dict, Literal
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from .states import UserInputState, UserIntent, create_user_input_state

# 加载环境变量
load_dotenv()


def get_llm() -> ChatOpenAI:
    """获取 LLM 实例"""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL"),
        temperature=0.3,  # 低温度确保稳定的意图分类
        max_tokens=1024
    )


# ============================================================================
# 意图分类节点
# ============================================================================

def classify_intent_node(state: UserInputState) -> Dict:
    """
    意图分类节点

    使用 LLM 结构化输出判断用户输入的意图类型。
    """
    llm = get_llm()
    classifier = llm.with_structured_output(UserIntent)

    # 构建分类提示
    stage_context = {
        "collect_requirements": "收集商品、国家、达人数量等需求信息",
        "param_confirmation": "确认筛选参数是否正确",
        "sorting_selection": "选择排序方式 (1-6 的数字选项)",
        "quantity_adjustment": "选择参数调整方案",
        "scraping_confirmation": "确认是否开始搜索",
    }

    current_stage_desc = stage_context.get(
        state["current_stage"],
        "与用户进行对话"
    )

    # 上下文信息
    context_str = ""
    if state.get("context"):
        ctx = state["context"]
        if ctx.get("product_name"):
            context_str += f"商品名称: {ctx['product_name']}\n"
        if ctx.get("country_name"):
            context_str += f"国家: {ctx['country_name']}\n"
        if ctx.get("available_options"):
            context_str += f"可选项: {ctx['available_options']}\n"

    prompt = f"""请分析用户输入的意图类型。

当前阶段: {state['current_stage']}
阶段描述: {current_stage_desc}

上下文信息:
{context_str if context_str else "无"}

用户输入: "{state['raw_input']}"

请判断用户意图属于以下哪种类型:

1. **expected_param**: 用户提供了当前阶段期望的参数
   - 在 sorting_selection 阶段: "1", "2", "1,3", "粉丝数", "用销量排序" 等
   - 在 collect_requirements 阶段: "口红", "美国", "50个达人" 等
   - 在 param_confirmation 阶段: "好的", "没问题" 等确认词

2. **question**: 用户提出问题，希望了解某个概念或功能
   - "互动率是什么意思?"
   - "这些排序有什么区别?"
   - "怎么选比较好?"

3. **suggestion_request**: 用户请求推荐或建议
   - "你推荐哪个?"
   - "哪个排序效果好?"
   - "有什么建议吗?"

4. **adjustment**: 用户想修改之前设置的参数
   - "我想改一下国家"
   - "把粉丝数改成10万以上"
   - "等等，商品名不对"

5. **confirmation**: 用户确认继续
   - "好的", "可以", "确认", "开始", "没问题", "yes", "ok"

6. **off_topic**: 与当前任务无关的话题
   - "今天天气怎么样?"
   - "你是谁?"
   - 闲聊内容

请根据当前阶段和上下文，准确判断用户意图。
如果是 expected_param，请提取具体的值。
"""

    try:
        result = classifier.invoke(prompt)
        return {
            "intent": result.intent_type,
            "confidence": result.confidence,
            "extracted_value": result.extracted_value,
            "needs_clarification": result.needs_clarification,
        }
    except Exception as e:
        print(f"[Orchestrator] 意图分类失败: {e}")
        # 默认作为预期参数处理
        return {
            "intent": "expected_param",
            "confidence": 0.5,
            "extracted_value": state["raw_input"],
            "needs_clarification": True,
        }


# ============================================================================
# 路由函数
# ============================================================================

def route_to_worker(state: UserInputState) -> str:
    """根据意图路由到对应的 Worker"""
    intent = state.get("intent", "expected_param")

    routing = {
        "question": "qa_worker",
        "suggestion_request": "suggest_worker",
        "expected_param": "param_worker",
        "adjustment": "redirect_worker",
        "confirmation": "confirmation_handler",
        "off_topic": "polite_worker",
    }

    return routing.get(intent, "param_worker")


# ============================================================================
# Worker 节点
# ============================================================================

def qa_worker_node(state: UserInputState) -> Dict:
    """
    QA Worker - 回答用户问题

    使用知识库和 LLM 回答用户关于系统/参数的问题。
    """
    from .workers.qa_worker import qa_worker_node as qa_impl
    return qa_impl(state)


def suggest_worker_node(state: UserInputState) -> Dict:
    """
    Suggest Worker - 提供个性化建议

    根据上下文（商品类型、目标人群等）提供推荐。
    """
    from .workers.suggest_worker import suggest_worker_node as suggest_impl
    return suggest_impl(state)


def param_worker_node(state: UserInputState) -> Dict:
    """
    Param Worker - 提取/验证参数

    从用户输入中提取结构化参数值。
    """
    from .workers.param_worker import param_worker_node as param_impl
    return param_impl(state)


def redirect_worker_node(state: UserInputState) -> Dict:
    """
    Redirect Worker - 处理修改请求

    确定用户想要修改的参数，并设置重定向目标。
    """
    from .workers.redirect_worker import redirect_worker_node as redirect_impl
    return redirect_impl(state)


def polite_worker_node(state: UserInputState) -> Dict:
    """
    Polite Worker - 处理无关话题

    礼貌地拒绝无关话题，并引导用户回到主流程。
    """
    from .workers.polite_worker import polite_worker_node as polite_impl
    return polite_impl(state)


def confirmation_handler_node(state: UserInputState) -> Dict:
    """
    Confirmation Handler - 处理确认信号

    直接标记为可以继续主流程。
    """
    return {
        "worker_response": "",
        "should_continue": True,
        "extracted_params": {"confirmed": True},
    }


# ============================================================================
# 合并响应节点
# ============================================================================

def merge_response_node(state: UserInputState) -> Dict:
    """
    合并 Worker 响应

    根据 Worker 的处理结果，决定是继续主流程还是继续等待用户输入。
    """
    # 如果 Worker 已经设置了这些值，直接返回
    if state.get("should_continue") or state.get("worker_response"):
        return {}

    # 默认需要更多输入
    return {
        "should_continue": False,
        "worker_response": "请继续输入您的需求。",
    }


# ============================================================================
# 创建 Orchestrator 工作流
# ============================================================================

def create_orchestrator_workflow():
    """
    创建 Orchestrator-Worker 工作流

    流程:
    1. classify_intent: 分类用户意图
    2. 路由到对应 Worker
    3. merge_response: 合并响应
    """
    builder = StateGraph(UserInputState)

    # 添加节点
    builder.add_node("classify_intent", classify_intent_node)
    builder.add_node("qa_worker", qa_worker_node)
    builder.add_node("suggest_worker", suggest_worker_node)
    builder.add_node("param_worker", param_worker_node)
    builder.add_node("redirect_worker", redirect_worker_node)
    builder.add_node("polite_worker", polite_worker_node)
    builder.add_node("confirmation_handler", confirmation_handler_node)
    builder.add_node("merge_response", merge_response_node)

    # 添加边: START -> classify_intent
    builder.add_edge(START, "classify_intent")

    # 条件路由: classify_intent -> workers
    builder.add_conditional_edges(
        "classify_intent",
        route_to_worker,
        {
            "qa_worker": "qa_worker",
            "suggest_worker": "suggest_worker",
            "param_worker": "param_worker",
            "redirect_worker": "redirect_worker",
            "polite_worker": "polite_worker",
            "confirmation_handler": "confirmation_handler",
        }
    )

    # 所有 Worker 汇聚到 merge_response
    for worker in ["qa_worker", "suggest_worker", "param_worker",
                   "redirect_worker", "polite_worker", "confirmation_handler"]:
        builder.add_edge(worker, "merge_response")

    # merge_response -> END
    builder.add_edge("merge_response", END)

    return builder.compile()


# ============================================================================
# 便捷调用函数
# ============================================================================

def process_user_input(
    raw_input: str,
    current_stage: str,
    context: Dict
) -> UserInputState:
    """
    处理用户输入的便捷函数

    Args:
        raw_input: 用户原始输入
        current_stage: 当前工作流阶段
        context: 上下文信息

    Returns:
        处理后的 UserInputState，包含意图分类和 Worker 响应
    """
    # 创建初始状态
    state = create_user_input_state(raw_input, current_stage, context)

    # 执行工作流
    workflow = create_orchestrator_workflow()
    result = workflow.invoke(state)

    return result


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    # 测试意图分类
    test_cases = [
        ("1,3", "sorting_selection", {"available_options": ["粉丝数", "涨粉数", "互动率", "赞粉比", "播放量", "销量"]}),
        ("互动率是什么意思?", "sorting_selection", {}),
        ("你推荐哪个?", "sorting_selection", {"product_name": "口红"}),
        ("好的", "param_confirmation", {}),
        ("我想改一下国家", "param_confirmation", {"country_name": "美国"}),
        ("今天天气怎么样", "collect_requirements", {}),
    ]

    print("=" * 60)
    print("Orchestrator-Worker 工作流测试")
    print("=" * 60)

    for raw_input, stage, context in test_cases:
        print(f"\n输入: '{raw_input}'")
        print(f"阶段: {stage}")

        result = process_user_input(raw_input, stage, context)

        print(f"意图: {result.get('intent')}")
        print(f"置信度: {result.get('confidence')}")
        print(f"提取值: {result.get('extracted_value')}")
        print(f"可继续: {result.get('should_continue')}")
        print(f"响应: {result.get('worker_response', '')[:100]}...")
        print("-" * 40)
