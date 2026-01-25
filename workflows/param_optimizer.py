"""
Param Optimizer - Evaluator-Optimizer Workflow

使用 Evaluator-Optimizer 模式优化筛选参数：
1. Generator: 构建筛选参数
2. Evaluator: 评估参数质量
3. 循环: 如果评估失败，带反馈重新生成
"""

import os
from typing import Dict, Literal
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .states import ParamOptimizerState

load_dotenv()


def get_llm() -> ChatOpenAI:
    """获取 LLM 实例"""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL"),
        temperature=0.3,
        max_tokens=1024
    )


class ParamEvaluation(BaseModel):
    """参数评估结果"""
    is_complete: bool = Field(description="参数是否完整（必填项都有值）")
    is_reasonable: bool = Field(description="参数是否合理（数值在正常范围内）")
    matches_intent: bool = Field(description="是否匹配用户意图")
    quality_score: float = Field(description="质量评分 0-1")
    feedback: str = Field(description="改进建议（如果评估失败）")
    result: Literal["pass", "fail"] = Field(description="最终结果")


# ============================================================
# Generator Node: 构建筛选参数
# ============================================================

def build_params_node(state: ParamOptimizerState) -> Dict:
    """
    Generator 节点：构建筛选参数

    根据用户需求和（可能的）评估反馈，构建或优化筛选参数。
    """
    user_requirements = state["user_requirements"]
    current_params = state.get("current_params", {})
    feedback = state.get("feedback", "")
    iteration = state.get("iteration_count", 0)

    # 如果是首次构建（没有反馈），直接使用已有参数
    if not feedback or iteration == 0:
        # 确保必要的默认值
        if "followers_min" not in current_params:
            current_params["followers_min"] = 10000  # 默认最小粉丝数
        if "followers_max" not in current_params:
            current_params["followers_max"] = 10000000  # 默认最大粉丝数
        if "channel" not in current_params:
            current_params["channel"] = "video"  # 默认短视频带货

        return {
            "current_params": current_params,
            "iteration_count": iteration + 1,
        }

    # 如果有反馈，使用 LLM 优化参数
    llm = get_llm()

    prompt = f"""你是一个参数优化助手。根据用户需求和评估反馈，优化筛选参数。

用户原始需求: {user_requirements}

当前参数:
{current_params}

评估反馈:
{feedback}

请根据反馈优化参数。只返回需要修改的参数，格式为 JSON。

可调整的参数:
- followers_min: 最小粉丝数 (整数)
- followers_max: 最大粉丝数 (整数)
- channel: 推广渠道 ("video" 或 "live")
- affiliate_check: 是否只看联盟达人 (true/false)
- new_followers: 近期涨粉筛选 (true/false)
- auth_type: 认证类型 ("personal"/"enterprise"/null)
- account_type: 账号类型 ("creator"/"business"/null)

示例输出:
{{"followers_min": 50000, "followers_max": 500000}}
"""

    try:
        response = llm.invoke(prompt)
        content = response.content

        # 尝试解析 JSON
        import json
        import re

        # 提取 JSON 部分
        json_match = re.search(r'\{[^{}]*\}', content)
        if json_match:
            updates = json.loads(json_match.group())
            current_params.update(updates)
    except Exception as e:
        print(f"[Param Optimizer] 参数优化失败: {e}")

    return {
        "current_params": current_params,
        "iteration_count": iteration + 1,
    }


# ============================================================
# Review Node: 生成参数摘要
# ============================================================

def review_params_node(state: ParamOptimizerState) -> Dict:
    """
    Review 节点：生成参数摘要

    将当前参数转换为用户友好的摘要文本。
    """
    params = state.get("current_params", {})

    # 构建摘要
    summary_parts = []

    # 商品信息
    if params.get("product_name"):
        summary_parts.append(f"商品: {params['product_name']}")

    # 国家
    if params.get("country_name"):
        summary_parts.append(f"国家: {params['country_name']}")

    # 分类
    if params.get("category_name"):
        summary_parts.append(f"分类: {params['category_name']}")

    # 目标数量
    if params.get("target_count"):
        summary_parts.append(f"目标达人数: {params['target_count']}")

    # 粉丝范围
    followers_min = params.get("followers_min", 10000)
    followers_max = params.get("followers_max", 10000000)
    summary_parts.append(f"粉丝范围: {format_number(followers_min)} - {format_number(followers_max)}")

    # 推广渠道
    channel = params.get("channel", "video")
    channel_name = "短视频带货" if channel == "video" else "直播带货"
    summary_parts.append(f"推广渠道: {channel_name}")

    # 可选筛选
    optional_filters = []
    if params.get("affiliate_check"):
        optional_filters.append("联盟达人")
    if params.get("new_followers"):
        optional_filters.append("近期涨粉")
    if params.get("auth_type"):
        auth_name = "个人认证" if params["auth_type"] == "personal" else "企业认证"
        optional_filters.append(auth_name)
    if params.get("account_type"):
        account_name = "创作者账号" if params["account_type"] == "creator" else "企业账号"
        optional_filters.append(account_name)

    if optional_filters:
        summary_parts.append(f"筛选条件: {', '.join(optional_filters)}")
    else:
        summary_parts.append("筛选条件: 无额外限制")

    param_summary = "\n".join(summary_parts)

    return {
        "param_summary": param_summary,
    }


def format_number(num: int) -> str:
    """格式化数字为易读形式"""
    if num >= 10000000:
        return f"{num // 10000000}千万"
    elif num >= 10000:
        return f"{num // 10000}万"
    else:
        return str(num)


# ============================================================
# Evaluator Node: 评估参数质量
# ============================================================

def evaluate_params_node(state: ParamOptimizerState) -> Dict:
    """
    Evaluator 节点：评估参数质量

    使用 LLM 结构化输出评估当前参数是否满足用户需求。
    """
    user_requirements = state["user_requirements"]
    current_params = state.get("current_params", {})
    param_summary = state.get("param_summary", "")
    iteration = state.get("iteration_count", 0)

    # 如果已达最大迭代次数，强制通过
    if iteration >= 3:
        return {
            "evaluation_result": "pass",
            "feedback": "已达最大优化次数，使用当前参数。",
        }

    # 基本验证（不需要 LLM）
    basic_issues = []

    # 检查必填项
    if not current_params.get("product_name"):
        basic_issues.append("缺少商品名称")
    if not current_params.get("country_name"):
        basic_issues.append("缺少目标国家")
    if not current_params.get("target_count"):
        basic_issues.append("缺少目标达人数量")

    # 检查粉丝范围合理性
    followers_min = current_params.get("followers_min", 0)
    followers_max = current_params.get("followers_max", 0)
    if followers_min >= followers_max:
        basic_issues.append("粉丝范围不合理（最小值大于等于最大值）")
    if followers_min < 1000:
        basic_issues.append("最小粉丝数过低（建议至少 1000）")

    # 如果有基本问题，直接返回失败
    if basic_issues:
        return {
            "evaluation_result": "fail",
            "feedback": "参数存在问题: " + "; ".join(basic_issues),
        }

    # 使用 LLM 进行深度评估
    try:
        llm = get_llm()
        evaluator = llm.with_structured_output(ParamEvaluation)

        prompt = f"""评估以下 TikTok 达人筛选参数是否满足用户需求。

用户需求: {user_requirements}

当前参数:
{param_summary}

详细参数:
{current_params}

请评估:
1. 参数是否完整（商品、国家、数量等必填项）
2. 参数是否合理（粉丝范围、筛选条件等是否适合该商品）
3. 是否匹配用户意图（参数是否真正反映了用户想要的）

如果有问题，请在 feedback 中给出具体的改进建议。
质量评分标准:
- 0.9-1.0: 完美，无需修改
- 0.7-0.9: 良好，可以使用
- 0.5-0.7: 一般，建议优化
- 0-0.5: 较差，需要重新构建
"""

        evaluation = evaluator.invoke(prompt)

        # 判断是否通过（质量评分 >= 0.7 即可）
        result = "pass" if evaluation.quality_score >= 0.7 else "fail"

        return {
            "evaluation_result": result,
            "feedback": evaluation.feedback if result == "fail" else "",
        }

    except Exception as e:
        print(f"[Param Optimizer] 评估失败: {e}")
        # 如果 LLM 调用失败，基于基本检查通过
        return {
            "evaluation_result": "pass",
            "feedback": "",
        }


# ============================================================
# Routing Function
# ============================================================

def route_evaluation(state: ParamOptimizerState) -> str:
    """
    路由函数：根据评估结果决定下一步

    - pass: 结束优化循环
    - fail: 返回 build_params 重新构建
    """
    result = state.get("evaluation_result", "pass")
    iteration = state.get("iteration_count", 0)

    # 最大迭代次数保护
    if iteration >= 3:
        return "pass"

    return result


# ============================================================
# Create Workflow
# ============================================================

def create_param_optimizer():
    """
    创建参数优化器工作流

    流程:
    START → build_params → review_params → evaluate_params
                ↑                               │
                └───────────── fail ────────────┘
                                │
                              pass
                                │
                                ↓
                               END
    """
    builder = StateGraph(ParamOptimizerState)

    # 添加节点
    builder.add_node("build_params", build_params_node)
    builder.add_node("review_params", review_params_node)
    builder.add_node("evaluate_params", evaluate_params_node)

    # 添加边
    builder.add_edge(START, "build_params")
    builder.add_edge("build_params", "review_params")
    builder.add_edge("review_params", "evaluate_params")

    # 条件边：根据评估结果路由
    builder.add_conditional_edges(
        "evaluate_params",
        route_evaluation,
        {
            "pass": END,
            "fail": "build_params",  # 失败则带反馈重新构建
        }
    )

    return builder.compile()


# ============================================================
# Utility Functions
# ============================================================

def optimize_params(
    user_requirements: str,
    initial_params: Dict,
) -> Dict:
    """
    便捷函数：优化筛选参数

    Args:
        user_requirements: 用户原始需求描述
        initial_params: 初始参数（可能来自需求收集阶段）

    Returns:
        优化后的参数字典，包含:
        - current_params: 最终参数
        - param_summary: 参数摘要
        - iteration_count: 迭代次数
    """
    workflow = create_param_optimizer()

    initial_state = {
        "user_requirements": user_requirements,
        "current_params": initial_params,
        "param_summary": "",
        "evaluation_result": "",
        "feedback": "",
        "iteration_count": 0,
    }

    result = workflow.invoke(initial_state)

    return {
        "current_params": result.get("current_params", initial_params),
        "param_summary": result.get("param_summary", ""),
        "iteration_count": result.get("iteration_count", 0),
    }


if __name__ == "__main__":
    # 测试参数优化器
    test_requirements = "我想在美国推广口红，需要找30个达人，粉丝数在10万到100万之间"
    test_params = {
        "product_name": "口红",
        "country_name": "美国",
        "target_count": 30,
        "category_name": "唇部彩妆",
        "followers_min": 100000,
        "followers_max": 1000000,
    }

    print("=" * 50)
    print("测试参数优化器")
    print("=" * 50)
    print(f"\n用户需求: {test_requirements}")
    print(f"初始参数: {test_params}")

    result = optimize_params(test_requirements, test_params)

    print(f"\n优化后参数: {result['current_params']}")
    print(f"\n参数摘要:\n{result['param_summary']}")
    print(f"\n迭代次数: {result['iteration_count']}")
