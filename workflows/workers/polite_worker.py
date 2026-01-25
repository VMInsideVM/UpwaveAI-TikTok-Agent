"""
Polite Worker - 处理无关话题

礼貌地拒绝无关话题，并引导用户回到主流程。
"""

import random
from typing import Dict

from ..states import UserInputState


# 礼貌回复模板
POLITE_RESPONSES = [
    "感谢您的分享！不过我主要负责帮您找到合适的 TikTok 达人进行商品推广。",
    "这个问题超出了我的服务范围，我专注于帮您筛选和匹配 TikTok 达人。",
    "抱歉，我是 TikTok 达人推荐助手，主要帮您找到适合推广商品的达人。",
    "我理解您的好奇，但我的专长是帮您找到合适的 TikTok 达人合作伙伴。",
]

# 引导语模板
GUIDANCE_TEMPLATES = {
    "collect_requirements": "请告诉我您想推广什么商品，目标国家和需要多少达人。",
    "param_confirmation": "请确认当前的筛选参数是否正确，或告诉我需要修改什么。",
    "sorting_selection": "请选择排序方式（1-6），可以多选如 '1,3'。",
    "quantity_adjustment": "请选择一个调整方案，或告诉我您的想法。",
    "scraping_confirmation": "如果准备好了，请输入 '确认' 开始搜索。",
}

# 特殊问候回复
GREETING_RESPONSES = {
    "你好": "你好！我是 TikTok 达人推荐助手，可以帮您找到最适合推广商品的达人。",
    "hello": "Hello! 我是 TikTok 达人推荐助手，请告诉我您的推广需求。",
    "hi": "Hi! 需要我帮您找 TikTok 达人吗？请告诉我您想推广什么商品。",
    "嗨": "嗨！我可以帮您找到合适的 TikTok 达人，请问您想推广什么商品？",
}


def is_greeting(user_input: str) -> bool:
    """检查是否是问候语"""
    greetings = ["你好", "hello", "hi", "嗨", "hey", "早上好", "下午好", "晚上好"]
    user_input_lower = user_input.lower().strip()
    return any(g in user_input_lower for g in greetings)


def get_greeting_response(user_input: str) -> str:
    """获取问候回复"""
    for key, response in GREETING_RESPONSES.items():
        if key in user_input.lower():
            return response
    return GREETING_RESPONSES["你好"]


def polite_worker_node(state: UserInputState) -> Dict:
    """
    Polite Worker 节点

    处理无关话题，礼貌拒绝并引导回主流程。
    """
    user_input = state["raw_input"]
    current_stage = state["current_stage"]

    # 检查是否是问候
    if is_greeting(user_input):
        response = get_greeting_response(user_input)
        guidance = GUIDANCE_TEMPLATES.get(current_stage, "请告诉我您的需求。")

        return {
            "worker_response": f"{response}\n\n{guidance}",
            "should_continue": False,
            "extracted_params": {},
        }

    # 检查是否是关于系统身份的问题
    identity_keywords = ["你是谁", "who are you", "你叫什么", "什么系统"]
    if any(k in user_input.lower() for k in identity_keywords):
        response = """我是 TikTok 达人推荐智能助手！

我的功能是帮助您找到最适合推广商品的 TikTok 达人。您只需要告诉我：
1. 您想推广什么商品
2. 目标国家/地区
3. 需要多少达人

我会根据您的需求，为您筛选和推荐最合适的达人。"""

        guidance = GUIDANCE_TEMPLATES.get(current_stage, "请告诉我您的需求。")

        return {
            "worker_response": f"{response}\n\n{guidance}",
            "should_continue": False,
            "extracted_params": {},
        }

    # 通用无关话题回复
    polite_response = random.choice(POLITE_RESPONSES)
    guidance = GUIDANCE_TEMPLATES.get(current_stage, "请告诉我您的需求。")

    return {
        "worker_response": f"{polite_response}\n\n{guidance}",
        "should_continue": False,
        "extracted_params": {},
    }
