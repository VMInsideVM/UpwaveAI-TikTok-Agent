"""
Suggest Worker - 提供个性化建议

根据用户的商品类型、目标人群等上下文，提供个性化的推荐建议。
"""

import os
from typing import Dict
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI

from ..states import UserInputState

load_dotenv()


def get_llm() -> ChatOpenAI:
    """获取 LLM 实例"""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL"),
        temperature=0.6,
        max_tokens=1024
    )


# 不同商品类型的排序建议
PRODUCT_SORTING_RECOMMENDATIONS = {
    "美妆": {
        "primary": ["互动率", "赞粉比"],
        "reason": "美妆产品重视内容质量和粉丝互动，高互动率的达人更容易带动购买决策。"
    },
    "服饰": {
        "primary": ["近28天视频平均播放量", "近28天总销量"],
        "reason": "服饰类需要高曝光和实际销量验证，播放量和销量都很重要。"
    },
    "食品": {
        "primary": ["近28天总销量", "互动率"],
        "reason": "食品类冲动消费较多，带货能力强的达人效果更好。"
    },
    "数码": {
        "primary": ["赞粉比", "互动率"],
        "reason": "数码产品需要专业的内容和高质量的粉丝群体。"
    },
    "家居": {
        "primary": ["近28天视频平均播放量", "粉丝数"],
        "reason": "家居产品需要大曝光来触达有需求的用户。"
    },
    "默认": {
        "primary": ["近28天总销量", "互动率"],
        "reason": "综合考虑带货能力和粉丝互动度，这两个维度通常最有效。"
    }
}


# 排序选项映射
SORTING_OPTIONS = {
    1: "粉丝数",
    2: "近28天涨粉数",
    3: "互动率",
    4: "赞粉比",
    5: "近28天视频平均播放量",
    6: "近28天总销量",
}

SORTING_OPTIONS_REVERSE = {v: k for k, v in SORTING_OPTIONS.items()}


def infer_product_category(product_name: str, category_info: Dict = None) -> str:
    """推断商品类别"""
    if category_info and category_info.get("category_name"):
        # 从分类信息推断
        cat_name = category_info["category_name"]
        if any(k in cat_name for k in ["美妆", "护肤", "彩妆", "化妆"]):
            return "美妆"
        if any(k in cat_name for k in ["服饰", "服装", "鞋", "包"]):
            return "服饰"
        if any(k in cat_name for k in ["食品", "零食", "饮料", "酒"]):
            return "食品"
        if any(k in cat_name for k in ["数码", "电子", "手机", "电脑"]):
            return "数码"
        if any(k in cat_name for k in ["家居", "家具", "家电"]):
            return "家居"

    # 从商品名推断
    product_lower = product_name.lower() if product_name else ""
    if any(k in product_lower for k in ["口红", "眼影", "粉底", "护肤", "面膜"]):
        return "美妆"
    if any(k in product_lower for k in ["衣服", "裤子", "鞋子", "包包", "T恤"]):
        return "服饰"
    if any(k in product_lower for k in ["零食", "饮料", "咖啡", "巧克力"]):
        return "食品"
    if any(k in product_lower for k in ["手机", "耳机", "充电器", "电脑"]):
        return "数码"
    if any(k in product_lower for k in ["沙发", "桌子", "灯", "收纳"]):
        return "家居"

    return "默认"


def suggest_worker_node(state: UserInputState) -> Dict:
    """
    Suggest Worker 节点

    根据上下文提供个性化推荐建议。
    """
    current_stage = state["current_stage"]
    context = state.get("context", {})

    # 主要处理排序选择阶段的建议请求
    if current_stage == "sorting_selection":
        return suggest_sorting(state, context)

    # 其他阶段的建议请求，使用 LLM 生成
    return suggest_general(state, context)


def suggest_sorting(state: UserInputState, context: Dict) -> Dict:
    """为排序选择提供建议"""
    product_name = context.get("product_name", "")
    category_info = context.get("category_info", {})

    # 推断商品类别
    category = infer_product_category(product_name, category_info)

    # 获取推荐
    recommendation = PRODUCT_SORTING_RECOMMENDATIONS.get(
        category,
        PRODUCT_SORTING_RECOMMENDATIONS["默认"]
    )

    primary_sorts = recommendation["primary"]
    reason = recommendation["reason"]

    # 获取对应的序号
    indices = [SORTING_OPTIONS_REVERSE.get(s, 0) for s in primary_sorts]
    indices_str = ",".join(map(str, indices))

    # 构建响应
    if product_name:
        product_mention = f"针对「{product_name}」这类商品，"
    else:
        product_mention = ""

    response = f"""{product_mention}我推荐选择 **{primary_sorts[0]}** 和 **{primary_sorts[1]}** 排序。

**推荐理由**: {reason}

您可以输入 `{indices_str}` 来选择这两个排序维度，或者根据自己的需求选择其他选项。

排序选项:
1. 粉丝数 - 按粉丝数量排序
2. 近28天涨粉数 - 选择近期活跃的达人
3. 互动率 - 选择粉丝互动度高的达人
4. 赞粉比 - 选择内容质量高的达人
5. 近28天视频平均播放量 - 选择视频曝光度高的达人
6. 近28天总销量 - 选择带货能力强的达人
"""

    return {
        "worker_response": response,
        "should_continue": False,
        "extracted_params": {
            "suggested_sorting": primary_sorts,
            "suggested_indices": indices,
        },
    }


def suggest_general(state: UserInputState, context: Dict) -> Dict:
    """通用建议生成"""
    llm = get_llm()

    current_stage = state["current_stage"]
    user_input = state["raw_input"]

    prompt = f"""你是 TikTok 达人推荐系统的智能助手。用户在 {current_stage} 阶段请求建议。

用户输入: {user_input}
上下文: {context}

请根据上下文提供专业、简洁的建议，并引导用户继续完成当前步骤。

注意:
1. 建议要具体、可操作
2. 语气要友好专业
3. 回答后引导用户继续
"""

    try:
        response = llm.invoke(prompt)
        return {
            "worker_response": response.content,
            "should_continue": False,
            "extracted_params": {},
        }
    except Exception as e:
        print(f"[Suggest Worker] LLM 调用失败: {e}")
        return {
            "worker_response": "抱歉，我暂时无法提供建议。请直接输入您的选择。",
            "should_continue": False,
            "extracted_params": {},
        }
