"""
Redirect Worker - 处理修改请求

识别用户想要修改的参数，并确定重定向目标节点。
"""

import os
from typing import Dict
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import Literal, Optional

from ..states import UserInputState

load_dotenv()


class RedirectDecision(BaseModel):
    """重定向决策"""
    wants_to_modify: bool = Field(description="用户是否想要修改参数")
    target_param: Optional[str] = Field(
        default=None,
        description="要修改的参数名 (product_name, country_name, target_count, followers, sorting, etc.)"
    )
    redirect_to: Optional[str] = Field(
        default=None,
        description="重定向到的节点名"
    )
    response: str = Field(description="给用户的回复")


def get_llm() -> ChatOpenAI:
    """获取 LLM 实例"""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL"),
        temperature=0.3,
        max_tokens=512
    )


# 参数到节点的映射
PARAM_TO_NODE = {
    "product_name": "collect_requirements",
    "商品": "collect_requirements",
    "商品名": "collect_requirements",
    "country_name": "collect_requirements",
    "国家": "collect_requirements",
    "地区": "collect_requirements",
    "target_count": "collect_requirements",
    "数量": "collect_requirements",
    "达人数": "collect_requirements",
    "followers": "param_optimizer",
    "粉丝": "param_optimizer",
    "粉丝数": "param_optimizer",
    "channel": "param_optimizer",
    "渠道": "param_optimizer",
    "推广渠道": "param_optimizer",
    "sorting": "sorting_selection",
    "排序": "sorting_selection",
    "排序方式": "sorting_selection",
    "category": "category_matching",
    "分类": "category_matching",
}


def simple_redirect_detection(user_input: str, context: Dict) -> Dict:
    """简单的重定向检测（不使用 LLM）"""
    user_input_lower = user_input.lower()

    # 检测是否包含修改意图的关键词
    modify_keywords = ["改", "修改", "换", "重新", "调整", "变更", "不对", "错了"]
    wants_to_modify = any(k in user_input_lower for k in modify_keywords)

    if not wants_to_modify:
        return {
            "worker_response": "",
            "should_continue": False,
            "extracted_params": {},
            "redirect_to": None,
        }

    # 尝试识别要修改的参数
    target_param = None
    redirect_to = None

    for param, node in PARAM_TO_NODE.items():
        if param in user_input or param.lower() in user_input_lower:
            target_param = param
            redirect_to = node
            break

    if redirect_to:
        param_display = {
            "collect_requirements": "基本需求（商品、国家、数量）",
            "param_optimizer": "筛选参数",
            "sorting_selection": "排序方式",
            "category_matching": "商品分类",
        }
        response = f"好的，让我们重新设置{param_display.get(redirect_to, '参数')}。请告诉我新的设置。"

        return {
            "worker_response": response,
            "should_continue": False,
            "extracted_params": {"wants_to_modify": True, "target_param": target_param},
            "redirect_to": redirect_to,
        }
    else:
        # 无法确定要修改什么，询问用户
        return {
            "worker_response": "好的，您想修改哪个参数？可以修改：商品名称、国家、达人数量、粉丝范围、排序方式等。",
            "should_continue": False,
            "extracted_params": {"wants_to_modify": True},
            "redirect_to": None,
        }


def redirect_worker_node(state: UserInputState) -> Dict:
    """
    Redirect Worker 节点

    识别用户想要修改的参数，确定重定向目标。
    """
    user_input = state["raw_input"]
    context = state.get("context", {})

    # 首先尝试简单检测
    result = simple_redirect_detection(user_input, context)

    if result.get("redirect_to") or not result.get("extracted_params", {}).get("wants_to_modify"):
        return result

    # 如果简单检测无法确定，使用 LLM
    try:
        llm = get_llm()
        classifier = llm.with_structured_output(RedirectDecision)

        prompt = f"""用户输入: "{user_input}"

当前上下文:
- 商品名: {context.get('product_name', '未设置')}
- 国家: {context.get('country_name', '未设置')}
- 数量: {context.get('target_count', '未设置')}

用户似乎想要修改某些参数。请判断:
1. 用户是否确实想修改参数？
2. 想修改哪个参数？
3. 应该重定向到哪个节点？

可选的重定向目标:
- collect_requirements: 修改商品、国家、数量
- param_optimizer: 修改粉丝范围、推广渠道等筛选条件
- sorting_selection: 修改排序方式
- category_matching: 修改商品分类

请给出判断和友好的回复。
"""

        decision = classifier.invoke(prompt)

        return {
            "worker_response": decision.response,
            "should_continue": False,
            "extracted_params": {
                "wants_to_modify": decision.wants_to_modify,
                "target_param": decision.target_param,
            },
            "redirect_to": decision.redirect_to,
        }

    except Exception as e:
        print(f"[Redirect Worker] LLM 调用失败: {e}")

        # 回退到询问用户
        return {
            "worker_response": "好的，您想修改哪个参数？请告诉我具体想改什么。",
            "should_continue": False,
            "extracted_params": {"wants_to_modify": True},
            "redirect_to": None,
        }
