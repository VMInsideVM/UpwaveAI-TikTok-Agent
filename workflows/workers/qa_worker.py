"""
QA Worker - 回答用户问题

回答用户关于系统功能、参数含义等问题，然后引导用户回到主流程。
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
        temperature=0.5,
        max_tokens=1024
    )


# 知识库：常见问题的答案
KNOWLEDGE_BASE = {
    "sorting": {
        "粉丝数": "按达人的总粉丝数量排序，粉丝数越多排名越靠前。适合追求曝光量的品牌。",
        "近28天涨粉数": "按达人近28天新增粉丝数排序，反映达人的当前热度和成长性。适合找正在上升期的达人。",
        "互动率": "互动率 = (点赞 + 评论 + 分享) / 播放量。反映粉丝的活跃度和内容吸引力。高互动率通常意味着更好的转化效果。",
        "赞粉比": "赞粉比 = 总获赞数 / 粉丝数。反映内容质量和粉丝粘性。高赞粉比的达人通常内容质量更高。",
        "近28天视频平均播放量": "按达人近28天发布视频的平均播放量排序。反映内容的曝光能力和流量获取能力。",
        "近28天总销量": "按达人近28天的带货销量排序。直接反映达人的带货能力，适合注重销售转化的品牌。",
    },
    "params": {
        "粉丝范围": "可以设置达人的粉丝数量范围，如 '10万到50万'、'100万以上' 等。",
        "推广渠道": "可选择 '短视频带货' 或 '直播带货'，筛选对应类型的达人。",
        "联盟达人": "开启后只显示已加入 TikTok Shop 联盟计划的达人，可以直接建联合作。",
        "认证达人": "筛选已通过官方认证的达人，通常代表更高的可信度。",
    },
    "general": {
        "系统功能": "本系统帮助您找到最适合推广商品的 TikTok 达人。只需告诉我您的商品、目标国家和需求数量，系统会自动匹配最合适的达人。",
        "使用流程": "1. 告诉我您要推广的商品 → 2. 选择目标国家和筛选条件 → 3. 确认参数 → 4. 选择排序方式 → 5. 生成推荐报告",
    }
}


def find_relevant_knowledge(question: str, context: Dict) -> str:
    """从知识库中查找相关知识"""
    question_lower = question.lower()

    # 检查是否问排序相关
    for key, value in KNOWLEDGE_BASE["sorting"].items():
        if key in question or key.lower() in question_lower:
            return value

    # 检查是否问参数相关
    for key, value in KNOWLEDGE_BASE["params"].items():
        if key in question or key.lower() in question_lower:
            return value

    # 检查通用问题
    for key, value in KNOWLEDGE_BASE["general"].items():
        if key in question:
            return value

    return ""


def get_stage_guidance(current_stage: str) -> str:
    """获取当前阶段的引导语"""
    guidance = {
        "collect_requirements": "请告诉我您想推广什么商品，以及目标国家和达人数量。",
        "param_confirmation": "请确认上面的筛选参数是否正确，或告诉我需要修改什么。",
        "sorting_selection": "请选择排序方式（输入 1-6 的数字，可多选如 '1,3'）。",
        "quantity_adjustment": "请选择一个调整方案（输入序号），或告诉我您的想法。",
        "scraping_confirmation": "请输入 '确认' 开始搜索，或继续调整参数。",
    }
    return guidance.get(current_stage, "请继续输入您的需求。")


def qa_worker_node(state: UserInputState) -> Dict:
    """
    QA Worker 节点

    回答用户问题，然后引导回到主流程。
    """
    question = state["raw_input"]
    current_stage = state["current_stage"]
    context = state.get("context", {})

    # 先尝试从知识库查找
    knowledge = find_relevant_knowledge(question, context)

    if knowledge:
        # 使用知识库直接回答
        guidance = get_stage_guidance(current_stage)
        response = f"{knowledge}\n\n{guidance}"

        return {
            "worker_response": response,
            "should_continue": False,
            "extracted_params": {},
        }

    # 使用 LLM 生成回答
    llm = get_llm()

    # 构建排序选项说明
    sorting_info = "\n".join([
        f"- {name}: {desc}"
        for name, desc in KNOWLEDGE_BASE["sorting"].items()
    ])

    prompt = f"""你是 TikTok 达人推荐系统的智能助手。用户提出了一个问题，请简洁地回答。

用户问题: {question}

当前阶段: {current_stage}
上下文: {context}

排序方式说明:
{sorting_info}

请回答用户的问题（简洁明了，2-3句话），然后自然地引导用户回到当前任务。

注意:
1. 回答要专业但通俗易懂
2. 回答后要自然地引导用户继续当前流程
3. 不要生硬地说"请回到主流程"
"""

    try:
        response = llm.invoke(prompt)
        answer = response.content

        # 添加阶段引导（如果回答中没有包含）
        guidance = get_stage_guidance(current_stage)
        if guidance not in answer:
            answer += f"\n\n{guidance}"

        return {
            "worker_response": answer,
            "should_continue": False,
            "extracted_params": {},
        }

    except Exception as e:
        print(f"[QA Worker] LLM 调用失败: {e}")

        # 回退响应
        guidance = get_stage_guidance(current_stage)
        return {
            "worker_response": f"抱歉，我暂时无法回答这个问题。{guidance}",
            "should_continue": False,
            "extracted_params": {},
        }
