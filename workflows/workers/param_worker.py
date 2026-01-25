"""
Param Worker - 提取和验证参数

从用户输入中提取结构化参数值，如排序选择、数量、国家等。
"""

import re
from typing import Dict, List, Optional, Tuple

from ..states import UserInputState


# 排序选项映射
SORTING_OPTIONS = {
    1: "粉丝数",
    2: "近28天涨粉数",
    3: "互动率",
    4: "赞粉比",
    5: "近28天视频平均播放量",
    6: "近28天总销量",
}

# 排序名称到序号的映射
SORTING_NAME_TO_INDEX = {
    "粉丝数": 1,
    "粉丝": 1,
    "涨粉数": 2,
    "涨粉": 2,
    "近28天涨粉数": 2,
    "互动率": 3,
    "互动": 3,
    "赞粉比": 4,
    "播放量": 5,
    "视频播放量": 5,
    "近28天视频平均播放量": 5,
    "销量": 6,
    "总销量": 6,
    "近28天总销量": 6,
    "带货": 6,
}

# 确认词列表
CONFIRMATION_WORDS = [
    "好的", "好", "可以", "没问题", "确认", "开始", "行", "就这样",
    "ok", "yes", "yeah", "sure", "proceed", "go", "confirm",
    "嗯", "对", "是", "是的", "没错",
]

# 支持的国家
SUPPORTED_COUNTRIES = [
    "全部", "美国", "印度尼西亚", "英国", "越南", "泰国", "马来西亚", "菲律宾",
    "西班牙", "墨西哥", "德国", "法国", "意大利", "巴西", "日本"
]


def parse_sorting_selection(user_input: str) -> Tuple[bool, List[int], List[str]]:
    """
    解析排序选择

    Args:
        user_input: 用户输入

    Returns:
        (is_valid, indices, names)
    """
    indices = []
    names = []

    # 方式1: 解析数字 (如 "1", "1,3", "1 3", "1、2、3")
    # 匹配 1-6 的数字
    numbers = re.findall(r'[1-6]', user_input)
    if numbers:
        for num_str in numbers:
            num = int(num_str)
            if num in SORTING_OPTIONS and num not in indices:
                indices.append(num)
                names.append(SORTING_OPTIONS[num])

    # 方式2: 解析中文名称 (如 "粉丝数", "用销量排序")
    if not indices:
        for name, idx in SORTING_NAME_TO_INDEX.items():
            if name in user_input:
                if idx not in indices:
                    indices.append(idx)
                    names.append(SORTING_OPTIONS[idx])

    is_valid = len(indices) > 0
    return is_valid, indices, names


def parse_count(user_input: str) -> Optional[int]:
    """解析数量"""
    # 匹配 "50个"、"100人"、"50" 等
    match = re.search(r'(\d+)\s*[个人位条]?', user_input)
    if match:
        return int(match.group(1))
    return None


def parse_country(user_input: str) -> Optional[str]:
    """解析国家"""
    for country in SUPPORTED_COUNTRIES:
        if country in user_input:
            return country
    return None


def is_confirmation(user_input: str) -> bool:
    """检查是否是确认词"""
    user_input_lower = user_input.lower().strip()
    for word in CONFIRMATION_WORDS:
        if word.lower() == user_input_lower or word.lower() in user_input_lower:
            return True
    return False


def param_worker_node(state: UserInputState) -> Dict:
    """
    Param Worker 节点

    根据当前阶段，从用户输入中提取对应的参数。
    """
    user_input = state["raw_input"]
    current_stage = state["current_stage"]
    context = state.get("context", {})

    # 根据阶段处理不同类型的参数
    if current_stage == "sorting_selection":
        return extract_sorting_params(user_input, context)

    elif current_stage == "param_confirmation":
        return extract_confirmation(user_input, context)

    elif current_stage == "scraping_confirmation":
        return extract_confirmation(user_input, context)

    elif current_stage == "collect_requirements":
        return extract_requirements(user_input, context)

    elif current_stage == "quantity_adjustment":
        return extract_adjustment_choice(user_input, context)

    else:
        # 通用提取
        return extract_general(user_input, context)


def extract_sorting_params(user_input: str, context: Dict) -> Dict:
    """提取排序选择参数"""
    is_valid, indices, names = parse_sorting_selection(user_input)

    if is_valid:
        response = f"已选择: {', '.join(names)}"
        return {
            "worker_response": response,
            "should_continue": True,
            "extracted_params": {
                "sorting_indices": indices,
                "sorting_names": names,
            },
        }
    else:
        return {
            "worker_response": "无法识别您的选择，请输入 1-6 的数字（可多选，如 1,3）来选择排序方式。",
            "should_continue": False,
            "extracted_params": {},
        }


def extract_confirmation(user_input: str, context: Dict) -> Dict:
    """提取确认信号"""
    if is_confirmation(user_input):
        return {
            "worker_response": "",
            "should_continue": True,
            "extracted_params": {"confirmed": True},
        }
    else:
        return {
            "worker_response": "",
            "should_continue": False,
            "extracted_params": {"confirmed": False},
        }


def extract_requirements(user_input: str, context: Dict) -> Dict:
    """提取需求信息（商品、国家、数量）"""
    extracted = {}
    response_parts = []

    # 提取数量
    count = parse_count(user_input)
    if count:
        extracted["target_count"] = count
        response_parts.append(f"达人数量: {count}")

    # 提取国家
    country = parse_country(user_input)
    if country:
        extracted["country_name"] = country
        response_parts.append(f"国家: {country}")

    # 商品名需要更复杂的提取，这里简单处理
    # 假设剩余部分是商品名
    remaining = user_input
    if count:
        remaining = re.sub(r'\d+\s*[个人位条]?', '', remaining)
    if country:
        remaining = remaining.replace(country, '')
    remaining = remaining.strip("，。,. ")

    if remaining and len(remaining) >= 2:
        extracted["product_name"] = remaining
        response_parts.append(f"商品: {remaining}")

    if extracted:
        return {
            "worker_response": "\n".join(response_parts) if response_parts else "",
            "should_continue": True,
            "extracted_params": extracted,
        }
    else:
        return {
            "worker_response": "请告诉我您想推广什么商品，目标国家是哪里，需要多少达人。",
            "should_continue": False,
            "extracted_params": {},
        }


def extract_adjustment_choice(user_input: str, context: Dict) -> Dict:
    """提取调整方案选择"""
    # 匹配数字序号
    match = re.search(r'[1-6]', user_input)
    if match:
        choice = int(match.group())
        return {
            "worker_response": f"已选择方案 {choice}",
            "should_continue": True,
            "extracted_params": {"adjustment_choice": choice},
        }

    # 检查是否是确认接受当前数量
    if is_confirmation(user_input) or "接受" in user_input or "可以" in user_input:
        return {
            "worker_response": "",
            "should_continue": True,
            "extracted_params": {"accept_current": True},
        }

    return {
        "worker_response": "请选择一个调整方案（输入序号 1-6），或输入 '接受' 使用当前数量。",
        "should_continue": False,
        "extracted_params": {},
    }


def extract_general(user_input: str, context: Dict) -> Dict:
    """通用参数提取"""
    # 检查确认
    if is_confirmation(user_input):
        return {
            "worker_response": "",
            "should_continue": True,
            "extracted_params": {"confirmed": True},
        }

    # 其他情况，将原始输入作为值
    return {
        "worker_response": "",
        "should_continue": True,
        "extracted_params": {"raw_value": user_input},
    }
