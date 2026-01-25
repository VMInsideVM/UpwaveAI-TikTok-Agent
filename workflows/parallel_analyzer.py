"""
Parallel Analyzer - Parallelization Workflow

使用 Parallelization 模式并行分析达人数据：
1. 准备批次：将达人数据分批
2. 并行分析：使用 Send API 并行处理每批数据
3. 聚合结果：合并所有批次的分析结果
"""

import os
from typing import Dict, List, Any, Annotated
from operator import add
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .states import AnalysisState

load_dotenv()


def get_llm() -> ChatOpenAI:
    """获取 LLM 实例"""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL"),
        temperature=0.5,
        max_tokens=2048
    )


class InfluencerAnalysis(BaseModel):
    """单个达人分析结果"""
    influencer_id: str = Field(description="达人ID或名称")
    audience_profile: str = Field(description="粉丝画像分析")
    content_quality: float = Field(description="内容质量评分 0-10")
    sales_potential: float = Field(description="带货能力评分 0-10")
    cooperation_value: float = Field(description="合作价值评分 0-10")
    recommendation_reason: str = Field(description="推荐理由")


class BatchAnalysisState(Dict):
    """批次分析状态"""
    batch: List[Dict]           # 当前批次的达人数据
    batch_index: int            # 批次索引
    product_name: str           # 商品名称（用于分析）
    category_name: str          # 分类名称


# ============================================================
# Prepare Batches Node
# ============================================================

def prepare_batches_node(state: AnalysisState) -> Dict:
    """
    准备批次节点

    将达人数据分成多个批次，准备并行处理。
    """
    influencer_data = state.get("influencer_data", [])
    batch_size = state.get("batch_size", 10)

    # 计算批次数量
    total_count = len(influencer_data)
    batch_count = (total_count + batch_size - 1) // batch_size

    print(f"[Parallel Analyzer] 准备分析 {total_count} 个达人，分为 {batch_count} 批")

    return {
        "batch_count": batch_count,
        "total_count": total_count,
    }


# ============================================================
# Dispatch to Analyzers (Send API)
# ============================================================

def dispatch_to_analyzers(state: AnalysisState) -> List[Send]:
    """
    分发函数：使用 Send API 创建并行分析任务

    为每个批次创建一个 Send 对象，触发并行执行。
    """
    influencer_data = state.get("influencer_data", [])
    batch_size = state.get("batch_size", 10)
    product_name = state.get("product_name", "")
    category_name = state.get("category_name", "")

    sends = []
    for i in range(0, len(influencer_data), batch_size):
        batch = influencer_data[i:i + batch_size]
        batch_index = i // batch_size

        sends.append(
            Send(
                "analyze_batch",
                {
                    "batch": batch,
                    "batch_index": batch_index,
                    "product_name": product_name,
                    "category_name": category_name,
                }
            )
        )

    print(f"[Parallel Analyzer] 创建 {len(sends)} 个并行分析任务")

    return sends


# ============================================================
# Analyze Batch Node
# ============================================================

def analyze_batch_node(state: BatchAnalysisState) -> Dict:
    """
    分析批次节点

    对单个批次的达人数据进行 LLM 分析。
    """
    batch = state.get("batch", [])
    batch_index = state.get("batch_index", 0)
    product_name = state.get("product_name", "商品")
    category_name = state.get("category_name", "")

    print(f"[Parallel Analyzer] 开始分析批次 {batch_index}，包含 {len(batch)} 个达人")

    analyses = []

    for influencer in batch:
        analysis = analyze_single_influencer(influencer, product_name, category_name)
        analyses.append(analysis)

    print(f"[Parallel Analyzer] 批次 {batch_index} 分析完成")

    return {
        "batch_results": [{"batch_index": batch_index, "analyses": analyses}]
    }


def analyze_single_influencer(
    influencer: Dict,
    product_name: str,
    category_name: str
) -> Dict:
    """
    分析单个达人

    使用 LLM 生成达人的详细分析。
    """
    # 提取达人基本信息
    name = influencer.get("达人昵称", influencer.get("name", "未知"))
    followers = influencer.get("粉丝数", influencer.get("followers", 0))
    engagement_rate = influencer.get("互动率", influencer.get("engagement_rate", "0%"))
    recent_views = influencer.get("近28天视频平均播放量", influencer.get("avg_views", 0))
    recent_sales = influencer.get("近28天总销量", influencer.get("recent_sales", 0))

    try:
        llm = get_llm()

        prompt = f"""分析以下 TikTok 达人是否适合推广 "{product_name}"（{category_name}类）。

达人信息:
- 昵称: {name}
- 粉丝数: {followers}
- 互动率: {engagement_rate}
- 近28天视频平均播放量: {recent_views}
- 近28天总销量: {recent_sales}
- 其他数据: {influencer}

请提供:
1. 粉丝画像分析（1-2句话，推测该达人的粉丝群体特征）
2. 内容质量评分（0-10分，基于互动率和播放量）
3. 带货能力评分（0-10分，基于销量和粉丝活跃度）
4. 合作价值评分（0-10分，综合性价比）
5. 推荐理由（1-2句话，说明为什么适合/不适合推广该商品）

请用 JSON 格式返回，包含以下字段:
- audience_profile: 粉丝画像
- content_quality: 内容质量评分
- sales_potential: 带货能力评分
- cooperation_value: 合作价值评分
- recommendation_reason: 推荐理由
"""

        response = llm.invoke(prompt)
        content = response.content

        # 解析 LLM 响应
        import json
        import re

        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            analysis_data = json.loads(json_match.group())
            return {
                "influencer_id": name,
                "original_data": influencer,
                "audience_profile": analysis_data.get("audience_profile", "暂无分析"),
                "content_quality": float(analysis_data.get("content_quality", 5)),
                "sales_potential": float(analysis_data.get("sales_potential", 5)),
                "cooperation_value": float(analysis_data.get("cooperation_value", 5)),
                "recommendation_reason": analysis_data.get("recommendation_reason", "暂无推荐理由"),
            }
    except Exception as e:
        print(f"[Parallel Analyzer] 分析达人 {name} 失败: {e}")

    # 回退：基于规则的简单评分
    return generate_fallback_analysis(influencer, name, followers, engagement_rate, recent_sales)


def generate_fallback_analysis(
    influencer: Dict,
    name: str,
    followers: Any,
    engagement_rate: Any,
    recent_sales: Any
) -> Dict:
    """
    生成回退分析（当 LLM 调用失败时）

    基于简单规则计算评分。
    """
    # 转换粉丝数
    try:
        if isinstance(followers, str):
            if "万" in followers:
                followers_num = float(followers.replace("万", "")) * 10000
            elif "亿" in followers:
                followers_num = float(followers.replace("亿", "")) * 100000000
            else:
                followers_num = float(followers)
        else:
            followers_num = float(followers)
    except:
        followers_num = 0

    # 转换互动率
    try:
        if isinstance(engagement_rate, str):
            engagement_num = float(engagement_rate.replace("%", ""))
        else:
            engagement_num = float(engagement_rate) * 100
    except:
        engagement_num = 0

    # 简单评分逻辑
    content_quality = min(10, engagement_num * 1.5)  # 互动率越高，内容质量越好
    sales_potential = min(10, 5 + (recent_sales or 0) / 1000)  # 基于销量
    cooperation_value = (content_quality + sales_potential) / 2

    # 粉丝画像（基于粉丝数量推测）
    if followers_num > 1000000:
        audience = "大众市场用户，覆盖面广"
    elif followers_num > 100000:
        audience = "中等规模垂直领域用户"
    else:
        audience = "小众精准用户群体"

    return {
        "influencer_id": name,
        "original_data": influencer,
        "audience_profile": audience,
        "content_quality": round(content_quality, 1),
        "sales_potential": round(sales_potential, 1),
        "cooperation_value": round(cooperation_value, 1),
        "recommendation_reason": f"基于数据分析，该达人综合评分 {round(cooperation_value, 1)} 分",
    }


# ============================================================
# Aggregate Results Node
# ============================================================

def aggregate_results_node(state: AnalysisState) -> Dict:
    """
    聚合结果节点

    合并所有批次的分析结果，生成最终报告。
    """
    batch_results = state.get("batch_results", [])

    # 合并所有批次
    all_analyses = []
    for batch_result in batch_results:
        analyses = batch_result.get("analyses", [])
        all_analyses.extend(analyses)

    print(f"[Parallel Analyzer] 聚合完成，共 {len(all_analyses)} 个达人分析")

    # 按合作价值排序
    all_analyses.sort(key=lambda x: x.get("cooperation_value", 0), reverse=True)

    # 生成最终报告
    final_report = {
        "total_analyzed": len(all_analyses),
        "top_recommendations": all_analyses[:10],  # 前10名
        "all_analyses": all_analyses,
        "summary": generate_summary(all_analyses),
    }

    return {
        "final_report": final_report,
        "analyzed_count": len(all_analyses),
    }


def generate_summary(analyses: List[Dict]) -> str:
    """生成分析摘要"""
    if not analyses:
        return "暂无达人数据分析"

    total = len(analyses)
    avg_content = sum(a.get("content_quality", 0) for a in analyses) / total
    avg_sales = sum(a.get("sales_potential", 0) for a in analyses) / total
    avg_value = sum(a.get("cooperation_value", 0) for a in analyses) / total

    high_quality = len([a for a in analyses if a.get("cooperation_value", 0) >= 7])

    return f"""共分析 {total} 个达人:
- 平均内容质量: {avg_content:.1f}/10
- 平均带货能力: {avg_sales:.1f}/10
- 平均合作价值: {avg_value:.1f}/10
- 高价值达人（≥7分）: {high_quality} 个"""


# ============================================================
# Create Workflow
# ============================================================

def create_parallel_analyzer():
    """
    创建并行分析器工作流

    流程:
    START → prepare_batches → [dispatch] → analyze_batch (并行) → aggregate_results → END
    """
    # 定义聚合状态，使用 Annotated 支持并行结果合并
    class AggregatedAnalysisState(AnalysisState):
        batch_results: Annotated[List[Dict], add]  # 使用 add reducer 合并并行结果

    builder = StateGraph(AggregatedAnalysisState)

    # 添加节点
    builder.add_node("prepare_batches", prepare_batches_node)
    builder.add_node("analyze_batch", analyze_batch_node)
    builder.add_node("aggregate_results", aggregate_results_node)

    # 添加边
    builder.add_edge(START, "prepare_batches")

    # 条件边：分发到并行分析节点
    builder.add_conditional_edges(
        "prepare_batches",
        dispatch_to_analyzers,
        ["analyze_batch"]
    )

    # 所有并行任务完成后聚合
    builder.add_edge("analyze_batch", "aggregate_results")
    builder.add_edge("aggregate_results", END)

    return builder.compile()


# ============================================================
# Utility Functions
# ============================================================

def analyze_influencers(
    influencer_data: List[Dict],
    product_name: str,
    category_name: str = "",
    batch_size: int = 10,
) -> Dict:
    """
    便捷函数：并行分析达人数据

    Args:
        influencer_data: 达人数据列表
        product_name: 商品名称
        category_name: 分类名称
        batch_size: 每批处理数量

    Returns:
        分析报告字典，包含:
        - final_report: 最终报告
        - analyzed_count: 分析的达人数量
    """
    workflow = create_parallel_analyzer()

    initial_state = {
        "influencer_data": influencer_data,
        "product_name": product_name,
        "category_name": category_name,
        "batch_size": batch_size,
        "batch_results": [],
        "final_report": {},
    }

    result = workflow.invoke(initial_state)

    return {
        "final_report": result.get("final_report", {}),
        "analyzed_count": result.get("analyzed_count", 0),
    }


if __name__ == "__main__":
    # 测试并行分析器
    test_data = [
        {
            "达人昵称": "美妆达人A",
            "粉丝数": "50万",
            "互动率": "5.2%",
            "近28天视频平均播放量": "10万",
            "近28天总销量": 500,
        },
        {
            "达人昵称": "美妆达人B",
            "粉丝数": "120万",
            "互动率": "3.8%",
            "近28天视频平均播放量": "25万",
            "近28天总销量": 1200,
        },
        {
            "达人昵称": "生活博主C",
            "粉丝数": "30万",
            "互动率": "8.1%",
            "近28天视频平均播放量": "8万",
            "近28天总销量": 300,
        },
    ]

    print("=" * 50)
    print("测试并行分析器")
    print("=" * 50)

    result = analyze_influencers(
        influencer_data=test_data,
        product_name="口红",
        category_name="唇部彩妆",
        batch_size=2,
    )

    print(f"\n分析完成，共 {result['analyzed_count']} 个达人")
    print(f"\n摘要:\n{result['final_report'].get('summary', '')}")

    print("\nTop 推荐:")
    for i, rec in enumerate(result['final_report'].get('top_recommendations', [])[:3], 1):
        print(f"{i}. {rec['influencer_id']} - 合作价值: {rec['cooperation_value']}/10")
        print(f"   推荐理由: {rec['recommendation_reason']}")
