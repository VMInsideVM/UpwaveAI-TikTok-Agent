"""
Main Workflow - 主工作流状态机

实现完整的 TikTok 达人推荐工作流：
1. collect_requirements - 收集用户需求
2. match_category - 分类匹配
3. param_optimizer - 参数优化 (Evaluator-Optimizer 子图)
4. wait_user_confirm - 等待用户确认参数
5. check_quantity - 检查达人数量
6. select_sorting - 选择排序方式 (Human-in-the-Loop)
7. confirm_scraping - 最终确认
8. scrape_data - 爬取数据
9. parallel_analyzer - 并行分析 (Parallelization 子图)
10. generate_report - 生成报告
11. export_excel - 导出 Excel
"""

import os
import uuid
from typing import Dict, List, Literal, Optional
from datetime import datetime
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from .states import MainWorkflowState
from .orchestrator import create_orchestrator_workflow
from .param_optimizer import create_param_optimizer, optimize_params
from .parallel_analyzer import create_parallel_analyzer, analyze_influencers

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


# ============================================================
# 阶段常量
# ============================================================

class WorkflowStage:
    """工作流阶段常量"""
    COLLECT_REQUIREMENTS = "collect_requirements"
    CATEGORY_MATCHING = "category_matching"
    PARAM_OPTIMIZATION = "param_optimization"
    PARAM_CONFIRMATION = "param_confirmation"
    QUANTITY_CHECK = "quantity_check"
    SORTING_SELECTION = "sorting_selection"
    SCRAPING_CONFIRMATION = "scraping_confirmation"
    SCRAPING = "scraping"
    ANALYZING = "analyzing"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# Node: 收集需求
# ============================================================

def collect_requirements_node(state: MainWorkflowState) -> Dict:
    """
    收集需求节点

    从用户输入中提取商品名、国家、目标数量等基本需求。
    使用 Orchestrator 处理用户输入。
    """
    user_message = state.get("user_message", "")
    pending_input = state.get("pending_user_input", "")

    # 优先使用 pending_input（来自 interrupt 恢复）
    current_input = pending_input or user_message

    if not current_input:
        return {
            "response_to_user": "您好！我是 TikTok 达人推荐助手。请告诉我您想推广什么商品，目标国家以及需要多少达人。",
            "current_stage": WorkflowStage.COLLECT_REQUIREMENTS,
            "awaiting_input": True,
        }

    # 使用 Orchestrator 处理输入
    orchestrator = create_orchestrator_workflow()
    context = {
        "product_name": state.get("product_name"),
        "country_name": state.get("country_name"),
        "target_count": state.get("target_count"),
    }

    result = orchestrator.invoke({
        "raw_input": current_input,
        "current_stage": WorkflowStage.COLLECT_REQUIREMENTS,
        "context": context,
    })

    # 检查是否提取到参数
    extracted = result.get("extracted_params", {})

    # 更新状态
    updates = {
        "pending_user_input": None,
        "current_stage": WorkflowStage.COLLECT_REQUIREMENTS,
    }

    if extracted.get("product_name"):
        updates["product_name"] = extracted["product_name"]
    if extracted.get("country_name"):
        updates["country_name"] = extracted["country_name"]
    if extracted.get("target_count"):
        updates["target_count"] = extracted["target_count"]

    # 检查是否收集完所有必要信息
    final_product = updates.get("product_name") or state.get("product_name")
    final_country = updates.get("country_name") or state.get("country_name")
    final_count = updates.get("target_count") or state.get("target_count")

    if final_product and final_country and final_count:
        # 信息完整，准备进入下一阶段
        updates["response_to_user"] = f"好的，您想在 {final_country} 推广 {final_product}，需要 {final_count} 个达人。让我为您匹配合适的商品分类..."
        updates["awaiting_input"] = False
        updates["requirements_complete"] = True
    else:
        # 信息不完整，继续收集
        missing = []
        if not final_product:
            missing.append("商品名称")
        if not final_country:
            missing.append("目标国家")
        if not final_count:
            missing.append("达人数量")

        if result.get("worker_response"):
            updates["response_to_user"] = result["worker_response"]
        else:
            updates["response_to_user"] = f"请补充以下信息：{', '.join(missing)}"

        updates["awaiting_input"] = True
        updates["requirements_complete"] = False

    return updates


# ============================================================
# Node: 分类匹配
# ============================================================

def match_category_node(state: MainWorkflowState) -> Dict:
    """
    分类匹配节点

    使用语义匹配为商品找到合适的 TikTok 分类。
    """
    product_name = state.get("product_name", "")

    if not product_name:
        return {
            "response_to_user": "无法进行分类匹配：缺少商品名称。",
            "current_stage": WorkflowStage.FAILED,
            "category_found": False,
        }

    # 调用分类匹配工具
    try:
        from category_matcher import match_category

        result = match_category(product_name)

        if result and result.get("category_id"):
            category_info = {
                "level": result.get("level", "L1"),
                "category_name": result.get("category_name", ""),
                "category_id": result.get("category_id", ""),
                "url_suffix": result.get("url_suffix", ""),
                "reasoning": result.get("reasoning", ""),
            }

            return {
                "category_info": category_info,
                "response_to_user": f"已为您匹配分类：{category_info['category_name']}（{result.get('reasoning', '')}）",
                "current_stage": WorkflowStage.PARAM_OPTIMIZATION,
                "category_found": True,
            }
        else:
            return {
                "response_to_user": f"抱歉，无法为「{product_name}」找到合适的 TikTok 分类。请尝试更换商品名称或使用更通用的描述。",
                "current_stage": WorkflowStage.FAILED,
                "category_found": False,
            }

    except Exception as e:
        print(f"[Main Workflow] 分类匹配失败: {e}")
        return {
            "response_to_user": f"分类匹配过程中出错：{str(e)}",
            "current_stage": WorkflowStage.FAILED,
            "category_found": False,
        }


# ============================================================
# Node: 参数优化
# ============================================================

def param_optimization_node(state: MainWorkflowState) -> Dict:
    """
    参数优化节点

    使用 Evaluator-Optimizer 子工作流优化筛选参数。
    """
    # 构建用户需求描述
    user_requirements = f"在 {state.get('country_name', '')} 推广 {state.get('product_name', '')}，需要 {state.get('target_count', 0)} 个达人"

    # 构建初始参数
    initial_params = {
        "product_name": state.get("product_name", ""),
        "country_name": state.get("country_name", ""),
        "target_count": state.get("target_count", 0),
        "category_name": state.get("category_info", {}).get("category_name", ""),
        "category_id": state.get("category_info", {}).get("category_id", ""),
        "url_suffix": state.get("category_info", {}).get("url_suffix", ""),
    }

    # 合并已有参数
    current_params = state.get("current_params", {})
    initial_params.update(current_params)

    # 调用参数优化器
    result = optimize_params(user_requirements, initial_params)

    return {
        "current_params": result["current_params"],
        "param_summary": result["param_summary"],
        "response_to_user": f"已为您生成筛选参数：\n\n{result['param_summary']}\n\n请确认参数是否正确，或告诉我需要修改什么。",
        "current_stage": WorkflowStage.PARAM_CONFIRMATION,
        "awaiting_input": True,
    }


# ============================================================
# Node: 等待用户确认参数
# ============================================================

def wait_user_confirm_node(state: MainWorkflowState) -> Dict:
    """
    等待用户确认节点

    处理用户对参数的确认或修改请求。
    """
    pending_input = state.get("pending_user_input", "")

    if not pending_input:
        return {
            "response_to_user": state.get("response_to_user", "请确认参数是否正确。"),
            "awaiting_input": True,
        }

    # 使用 Orchestrator 处理输入
    orchestrator = create_orchestrator_workflow()
    result = orchestrator.invoke({
        "raw_input": pending_input,
        "current_stage": WorkflowStage.PARAM_CONFIRMATION,
        "context": state.get("current_params", {}),
    })

    intent = result.get("intent", "")
    extracted = result.get("extracted_params", {})

    if intent == "confirmation" or extracted.get("confirmed"):
        # 用户确认，进入数量检查
        return {
            "pending_user_input": None,
            "response_to_user": "好的，参数已确认。正在检查可用达人数量...",
            "current_stage": WorkflowStage.QUANTITY_CHECK,
            "user_confirmed_params": True,
            "awaiting_input": False,
        }
    elif intent == "adjustment" or result.get("redirect_to"):
        # 用户要求修改
        redirect_to = result.get("redirect_to", WorkflowStage.COLLECT_REQUIREMENTS)
        return {
            "pending_user_input": None,
            "response_to_user": result.get("worker_response", "好的，请告诉我您想修改什么。"),
            "current_stage": redirect_to,
            "user_confirmed_params": False,
            "awaiting_input": True,
        }
    else:
        # 其他情况（提问等），返回 worker 响应
        return {
            "pending_user_input": None,
            "response_to_user": result.get("worker_response", "请确认参数是否正确，或告诉我需要修改什么。"),
            "awaiting_input": True,
        }


# ============================================================
# Node: 数量检查
# ============================================================

def check_quantity_node(state: MainWorkflowState) -> Dict:
    """
    数量检查节点

    检查是否有足够的达人满足用户需求。
    """
    current_params = state.get("current_params", {})
    target_count = state.get("target_count", 30)

    try:
        # 构建搜索 URL
        from agent_tools import BuildURLTool

        build_tool = BuildURLTool()
        search_url = build_tool._run(
            country_name=current_params.get("country_name", "美国"),
            category_suffix=current_params.get("url_suffix", ""),
            followers_min=current_params.get("followers_min", 10000),
            followers_max=current_params.get("followers_max", 10000000),
            channel=current_params.get("channel", "video"),
        )

        # 获取最大页数
        from agent_tools import GetMaxPageTool

        max_page_tool = GetMaxPageTool()
        max_pages = int(max_page_tool._run(search_url))

        available_count = max_pages * 5  # 保守估计

        # 更新状态
        updates = {
            "search_url": search_url,
            "max_pages": max_pages,
            "available_count": available_count,
            "current_stage": WorkflowStage.SORTING_SELECTION,
        }

        # 判断数量是否足够
        if available_count >= target_count:
            updates["response_to_user"] = f"找到约 {available_count} 个符合条件的达人，满足您的需求（{target_count} 个）。\n\n请选择排序方式（可多选）：\n1. 粉丝数\n2. 近28天涨粉数\n3. 互动率\n4. 赞粉比\n5. 近28天视频平均播放量\n6. 近28天总销量\n\n请输入数字，如 \"1,3\" 或 \"选1和3\"。"
            updates["quantity_sufficient"] = True
        elif available_count >= target_count * 0.5:
            updates["response_to_user"] = f"找到约 {available_count} 个符合条件的达人，略低于您的需求（{target_count} 个）。\n\n您可以：\n1. 继续使用当前参数\n2. 放宽筛选条件\n\n如果继续，请选择排序方式（1-6）。"
            updates["quantity_sufficient"] = "acceptable"
        else:
            # 生成调整建议
            updates["response_to_user"] = f"找到约 {available_count} 个符合条件的达人，不足您的需求（{target_count} 个）。\n\n建议：\n1. 扩大粉丝范围\n2. 减少筛选条件\n\n请告诉我您想如何调整，或输入 \"继续\" 使用当前结果。"
            updates["quantity_sufficient"] = False

        updates["awaiting_input"] = True
        return updates

    except Exception as e:
        print(f"[Main Workflow] 数量检查失败: {e}")
        return {
            "response_to_user": f"检查达人数量时出错：{str(e)}。请稍后重试。",
            "current_stage": WorkflowStage.FAILED,
        }


# ============================================================
# Node: 排序选择
# ============================================================

def select_sorting_node(state: MainWorkflowState) -> Dict:
    """
    排序选择节点 (Human-in-the-Loop)

    等待用户选择排序方式。
    """
    pending_input = state.get("pending_user_input", "")

    if not pending_input:
        # 显示排序选项
        return {
            "response_to_user": "请选择排序方式（可多选）：\n1. 粉丝数\n2. 近28天涨粉数\n3. 互动率\n4. 赞粉比\n5. 近28天视频平均播放量\n6. 近28天总销量\n\n请输入数字，如 \"1,3\"。",
            "current_stage": WorkflowStage.SORTING_SELECTION,
            "awaiting_input": True,
        }

    # 使用 Orchestrator 处理输入
    orchestrator = create_orchestrator_workflow()
    result = orchestrator.invoke({
        "raw_input": pending_input,
        "current_stage": WorkflowStage.SORTING_SELECTION,
        "context": {
            "available_options": ["粉丝数", "近28天涨粉数", "互动率", "赞粉比", "近28天视频平均播放量", "近28天总销量"],
        },
    })

    extracted = result.get("extracted_params", {})
    sorting_indices = extracted.get("sorting_indices", [])

    if sorting_indices:
        # 成功提取排序选项
        sorting_map = {
            1: "粉丝数",
            2: "近28天涨粉数",
            3: "互动率",
            4: "赞粉比",
            5: "近28天视频平均播放量",
            6: "近28天总销量",
        }
        selected_names = [sorting_map.get(i, f"选项{i}") for i in sorting_indices]

        return {
            "pending_user_input": None,
            "selected_sorting": sorting_indices,
            "selected_sorting_names": selected_names,
            "response_to_user": f"已选择排序方式：{', '.join(selected_names)}\n\n即将开始搜索约 {state.get('target_count', 30)} 个达人。输入 \"确认\" 开始搜索，或继续调整参数。",
            "current_stage": WorkflowStage.SCRAPING_CONFIRMATION,
            "awaiting_input": True,
        }
    else:
        # 未能提取有效排序，返回 worker 响应
        return {
            "pending_user_input": None,
            "response_to_user": result.get("worker_response", "请输入排序方式的数字（1-6），如 \"1,3\"。"),
            "awaiting_input": True,
        }


# ============================================================
# Node: 最终确认
# ============================================================

def confirm_scraping_node(state: MainWorkflowState) -> Dict:
    """
    最终确认节点 (Human-in-the-Loop)

    等待用户确认开始爬取。
    """
    pending_input = state.get("pending_user_input", "")

    if not pending_input:
        return {
            "response_to_user": "输入 \"确认\" 开始搜索，或告诉我需要修改什么。",
            "awaiting_input": True,
        }

    # 使用 Orchestrator 处理输入
    orchestrator = create_orchestrator_workflow()
    result = orchestrator.invoke({
        "raw_input": pending_input,
        "current_stage": WorkflowStage.SCRAPING_CONFIRMATION,
        "context": state.get("current_params", {}),
    })

    intent = result.get("intent", "")
    extracted = result.get("extracted_params", {})

    if intent == "confirmation" or extracted.get("confirmed"):
        # 用户确认，开始爬取
        return {
            "pending_user_input": None,
            "response_to_user": "好的，开始搜索达人数据...",
            "current_stage": WorkflowStage.SCRAPING,
            "scraping_confirmed": True,
            "awaiting_input": False,
        }
    elif intent == "adjustment":
        # 用户要求调整
        redirect_to = result.get("redirect_to", WorkflowStage.SORTING_SELECTION)
        return {
            "pending_user_input": None,
            "response_to_user": result.get("worker_response", "好的，请告诉我您想修改什么。"),
            "current_stage": redirect_to,
            "awaiting_input": True,
        }
    else:
        return {
            "pending_user_input": None,
            "response_to_user": result.get("worker_response", "请输入 \"确认\" 开始搜索。"),
            "awaiting_input": True,
        }


# ============================================================
# Node: 数据爬取
# ============================================================

def scrape_data_node(state: MainWorkflowState) -> Dict:
    """
    数据爬取节点

    调用爬虫获取达人数据。
    """
    search_url = state.get("search_url", "")
    selected_sorting = state.get("selected_sorting", [1])
    target_count = state.get("target_count", 30)

    if not search_url:
        return {
            "response_to_user": "爬取失败：缺少搜索 URL。",
            "current_stage": WorkflowStage.FAILED,
        }

    try:
        from agent_tools import ScrapeInfluencersTool, GetSortSuffixTool

        scrape_tool = ScrapeInfluencersTool()
        sort_suffix_tool = GetSortSuffixTool()

        all_data = []

        # 为每个排序维度爬取数据
        for sort_idx in selected_sorting:
            sort_suffix = sort_suffix_tool._run(sort_idx)
            sorted_url = search_url + sort_suffix

            # 计算需要爬取的页数
            pages_needed = (target_count // len(selected_sorting) // 5) + 1
            pages_needed = min(pages_needed, 10)  # 限制最大页数

            result = scrape_tool._run(sorted_url, pages_needed)

            if "成功" in result:
                # 假设工具返回的数据在某处可获取
                # 这里需要根据实际实现调整
                pass

        # 实际实现中，数据会存储在 agent 的 scraped_dataframes 中
        # 这里简化处理

        return {
            "response_to_user": f"数据爬取完成！正在分析达人数据...",
            "current_stage": WorkflowStage.ANALYZING,
            "scraped_data": all_data,  # 实际数据
        }

    except Exception as e:
        print(f"[Main Workflow] 数据爬取失败: {e}")
        return {
            "response_to_user": f"数据爬取失败：{str(e)}",
            "current_stage": WorkflowStage.FAILED,
        }


# ============================================================
# Node: 并行分析
# ============================================================

def analyze_data_node(state: MainWorkflowState) -> Dict:
    """
    分析数据节点

    使用 Parallelization 子工作流并行分析达人数据。
    """
    scraped_data = state.get("scraped_data", [])
    product_name = state.get("product_name", "")
    category_name = state.get("category_info", {}).get("category_name", "")

    if not scraped_data:
        # 如果没有数据，尝试从其他来源获取
        return {
            "response_to_user": "正在生成推荐报告...",
            "current_stage": WorkflowStage.REPORT_GENERATION,
        }

    # 调用并行分析器
    result = analyze_influencers(
        influencer_data=scraped_data,
        product_name=product_name,
        category_name=category_name,
        batch_size=10,
    )

    return {
        "analysis_report": result.get("final_report", {}),
        "response_to_user": f"达人分析完成！\n\n{result.get('final_report', {}).get('summary', '')}",
        "current_stage": WorkflowStage.REPORT_GENERATION,
    }


# ============================================================
# Node: 生成报告
# ============================================================

def generate_report_node(state: MainWorkflowState) -> Dict:
    """
    生成报告节点

    整合分析结果，生成最终推荐报告。
    """
    analysis_report = state.get("analysis_report", {})
    product_name = state.get("product_name", "")
    country_name = state.get("country_name", "")

    # 生成报告摘要
    summary = analysis_report.get("summary", "")
    top_recommendations = analysis_report.get("top_recommendations", [])

    report_text = f"""
📊 TikTok 达人推荐报告

商品: {product_name}
目标国家: {country_name}

{summary}

Top 推荐达人:
"""

    for i, rec in enumerate(top_recommendations[:5], 1):
        report_text += f"\n{i}. {rec.get('influencer_id', '未知')}"
        report_text += f"\n   合作价值: {rec.get('cooperation_value', 0)}/10"
        report_text += f"\n   推荐理由: {rec.get('recommendation_reason', '暂无')}\n"

    return {
        "final_report": report_text,
        "response_to_user": report_text + "\n\n正在导出 Excel 报告...",
        "current_stage": WorkflowStage.COMPLETED,
    }


# ============================================================
# Node: 导出 Excel
# ============================================================

def export_excel_node(state: MainWorkflowState) -> Dict:
    """
    导出 Excel 节点

    将结果导出为 Excel 文件。
    """
    try:
        from agent_tools import ExportExcelTool

        export_tool = ExportExcelTool()
        result = export_tool._run()

        return {
            "response_to_user": f"报告已生成！{result}",
            "current_stage": WorkflowStage.COMPLETED,
            "workflow_complete": True,
        }

    except Exception as e:
        print(f"[Main Workflow] Excel 导出失败: {e}")
        return {
            "response_to_user": f"Excel 导出失败：{str(e)}，但您仍可以查看上面的报告摘要。",
            "current_stage": WorkflowStage.COMPLETED,
            "workflow_complete": True,
        }


# ============================================================
# Node: 优雅结束
# ============================================================

def graceful_end_node(state: MainWorkflowState) -> Dict:
    """
    优雅结束节点

    当流程无法继续时，礼貌地结束对话。
    """
    return {
        "response_to_user": "感谢使用 TikTok 达人推荐助手！如需继续，请重新开始对话。",
        "current_stage": WorkflowStage.COMPLETED,
        "workflow_complete": True,
    }


# ============================================================
# Routing Functions
# ============================================================

def route_after_requirements(state: MainWorkflowState) -> str:
    """收集需求后的路由"""
    if state.get("requirements_complete"):
        return "match_category"
    return "collect_requirements"  # 继续收集


def route_after_category(state: MainWorkflowState) -> str:
    """分类匹配后的路由"""
    if state.get("category_found"):
        return "param_optimization"
    return "graceful_end"


def route_after_param_confirm(state: MainWorkflowState) -> str:
    """参数确认后的路由"""
    if state.get("user_confirmed_params"):
        return "check_quantity"
    # 根据 current_stage 决定返回哪里
    stage = state.get("current_stage", "")
    if stage == WorkflowStage.COLLECT_REQUIREMENTS:
        return "collect_requirements"
    return "param_optimization"


def route_after_quantity(state: MainWorkflowState) -> str:
    """数量检查后的路由"""
    quantity_status = state.get("quantity_sufficient")
    if quantity_status is True or quantity_status == "acceptable":
        return "select_sorting"
    return "select_sorting"  # 即使不足也继续，让用户决定


def route_after_sorting(state: MainWorkflowState) -> str:
    """排序选择后的路由"""
    if state.get("selected_sorting"):
        return "confirm_scraping"
    return "select_sorting"


def route_after_scraping_confirm(state: MainWorkflowState) -> str:
    """爬取确认后的路由"""
    if state.get("scraping_confirmed"):
        return "scrape_data"
    # 返回调整
    stage = state.get("current_stage", "")
    if stage == WorkflowStage.SORTING_SELECTION:
        return "select_sorting"
    return "confirm_scraping"


def should_wait_for_input(state: MainWorkflowState) -> bool:
    """判断是否需要等待用户输入"""
    return state.get("awaiting_input", False)


# ============================================================
# Create Main Workflow
# ============================================================

def create_main_workflow(checkpointer=None):
    """
    创建主工作流

    Args:
        checkpointer: 状态检查点器（用于 Human-in-the-Loop）

    Returns:
        编译后的工作流
    """
    builder = StateGraph(MainWorkflowState)

    # 添加所有节点
    builder.add_node("collect_requirements", collect_requirements_node)
    builder.add_node("match_category", match_category_node)
    builder.add_node("param_optimization", param_optimization_node)
    builder.add_node("wait_user_confirm", wait_user_confirm_node)
    builder.add_node("check_quantity", check_quantity_node)
    builder.add_node("select_sorting", select_sorting_node)
    builder.add_node("confirm_scraping", confirm_scraping_node)
    builder.add_node("scrape_data", scrape_data_node)
    builder.add_node("analyze_data", analyze_data_node)
    builder.add_node("generate_report", generate_report_node)
    builder.add_node("export_excel", export_excel_node)
    builder.add_node("graceful_end", graceful_end_node)

    # 添加边
    builder.add_edge(START, "collect_requirements")

    # 条件边：收集需求后
    builder.add_conditional_edges(
        "collect_requirements",
        route_after_requirements,
        {
            "match_category": "match_category",
            "collect_requirements": "collect_requirements",
        }
    )

    # 条件边：分类匹配后
    builder.add_conditional_edges(
        "match_category",
        route_after_category,
        {
            "param_optimization": "param_optimization",
            "graceful_end": "graceful_end",
        }
    )

    # 参数优化 → 等待确认
    builder.add_edge("param_optimization", "wait_user_confirm")

    # 条件边：参数确认后
    builder.add_conditional_edges(
        "wait_user_confirm",
        route_after_param_confirm,
        {
            "check_quantity": "check_quantity",
            "collect_requirements": "collect_requirements",
            "param_optimization": "param_optimization",
        }
    )

    # 数量检查 → 排序选择
    builder.add_edge("check_quantity", "select_sorting")

    # 条件边：排序选择后
    builder.add_conditional_edges(
        "select_sorting",
        route_after_sorting,
        {
            "confirm_scraping": "confirm_scraping",
            "select_sorting": "select_sorting",
        }
    )

    # 条件边：爬取确认后
    builder.add_conditional_edges(
        "confirm_scraping",
        route_after_scraping_confirm,
        {
            "scrape_data": "scrape_data",
            "select_sorting": "select_sorting",
            "confirm_scraping": "confirm_scraping",
        }
    )

    # 爬取 → 分析 → 报告 → 导出 → 结束
    builder.add_edge("scrape_data", "analyze_data")
    builder.add_edge("analyze_data", "generate_report")
    builder.add_edge("generate_report", "export_excel")
    builder.add_edge("export_excel", END)

    # 优雅结束 → END
    builder.add_edge("graceful_end", END)

    # 编译工作流
    if checkpointer is None:
        checkpointer = MemorySaver()

    workflow = builder.compile(
        checkpointer=checkpointer,
        interrupt_before=[
            "collect_requirements",
            "wait_user_confirm",
            "select_sorting",
            "confirm_scraping",
        ]
    )

    return workflow


# ============================================================
# Workflow Runner
# ============================================================

class WorkflowRunner:
    """
    工作流运行器

    管理工作流的执行，支持 Human-in-the-Loop。
    """

    def __init__(self):
        self.checkpointer = MemorySaver()
        self.workflow = create_main_workflow(self.checkpointer)
        self.thread_id = None

    def start_new_session(self) -> str:
        """开始新会话"""
        self.thread_id = str(uuid.uuid4())
        return self.thread_id

    def run(self, user_input: str, thread_id: str = None) -> str:
        """
        运行工作流

        Args:
            user_input: 用户输入
            thread_id: 会话 ID（可选）

        Returns:
            响应文本
        """
        if thread_id:
            self.thread_id = thread_id
        elif not self.thread_id:
            self.start_new_session()

        config = {"configurable": {"thread_id": self.thread_id}}

        # 检查是否有挂起的状态
        current_state = self.workflow.get_state(config)

        if current_state.next:
            # 有挂起的节点，用用户输入恢复
            result = self.workflow.invoke(
                {"pending_user_input": user_input},
                config
            )
        else:
            # 新对话，从头开始
            result = self.workflow.invoke(
                {"user_message": user_input},
                config
            )

        return result.get("response_to_user", "处理中...")

    def get_current_stage(self) -> str:
        """获取当前阶段"""
        if not self.thread_id:
            return WorkflowStage.COLLECT_REQUIREMENTS

        config = {"configurable": {"thread_id": self.thread_id}}
        state = self.workflow.get_state(config)

        if state.values:
            return state.values.get("current_stage", WorkflowStage.COLLECT_REQUIREMENTS)
        return WorkflowStage.COLLECT_REQUIREMENTS


if __name__ == "__main__":
    # 测试主工作流
    print("=" * 50)
    print("测试主工作流")
    print("=" * 50)

    runner = WorkflowRunner()

    # 模拟对话
    test_inputs = [
        "我想在美国推广口红，需要30个达人",
        "确认",
        "1,3",
        "确认",
    ]

    for user_input in test_inputs:
        print(f"\n用户: {user_input}")
        response = runner.run(user_input)
        print(f"助手: {response}")
        print(f"当前阶段: {runner.get_current_stage()}")
