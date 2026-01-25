"""
LangGraph Workflow 状态定义

定义所有工作流使用的状态类型，使用 TypedDict 确保类型安全。
"""

from typing import TypedDict, List, Dict, Optional, Literal, Annotated
from pydantic import BaseModel, Field
import operator


# ============================================================================
# 主工作流状态
# ============================================================================

class MainWorkflowState(TypedDict):
    """主工作流状态"""

    # 用户输入
    user_message: str                          # 当前用户消息
    pending_user_input: Optional[str]          # 等待处理的用户输入 (Human-in-the-Loop)

    # 对话历史
    chat_history: List[Dict]                   # 对话历史记录

    # 需求收集
    product_name: Optional[str]                # 商品名称
    country_name: Optional[str]                # 国家/地区
    target_count: Optional[int]                # 目标达人数量

    # 分类匹配
    category_info: Optional[Dict]              # 分类信息 {level, category_name, category_id, url_suffix}
    category_found: bool                       # 是否找到分类

    # 筛选参数
    current_params: Dict                       # 当前所有筛选参数
    search_url: Optional[str]                  # 构建的搜索 URL
    params_confirmed: bool                     # 参数是否已确认

    # 数量检查
    max_pages: Optional[int]                   # 最大可用页数
    available_count: Optional[int]             # 可用达人数量
    quantity_status: Optional[str]             # "sufficient" | "acceptable" | "insufficient"

    # 排序选择
    selected_sorting: Optional[List[str]]      # 选择的排序维度
    sorted_urls: Optional[List[str]]           # 带排序后缀的 URL 列表

    # 确认状态
    user_confirmed_scraping: bool              # 用户是否确认开始搜索
    user_confirmed_params: bool                # 用户是否确认参数
    scraping_confirmed: bool                   # 是否确认开始爬取
    requirements_complete: bool                # 需求是否收集完整
    quantity_sufficient: bool                  # 数量是否充足

    # 爬取和分析
    scraped_data: Optional[List[Dict]]         # 爬取的达人数据
    analysis_results: Optional[List[Dict]]     # 分析结果
    analysis_report: Optional[Dict]            # 分析报告

    # 报告
    report_id: Optional[str]                   # 报告 ID
    report_path: Optional[str]                 # 报告路径
    final_report: Optional[str]                # 最终报告文本
    param_summary: Optional[str]               # 参数摘要

    # 排序
    selected_sorting_names: Optional[List[str]]  # 选择的排序名称

    # 响应
    response_to_user: str                      # 返回给用户的响应
    awaiting_input: bool                       # 是否等待用户输入
    current_stage: str                         # 当前工作流阶段
    workflow_complete: bool                    # 工作流是否完成

    # 会话信息
    user_id: Optional[str]                     # 用户 ID
    session_id: Optional[str]                  # 会话 ID


# ============================================================================
# Orchestrator-Worker 状态 (用户输入处理)
# ============================================================================

class UserInputState(TypedDict):
    """用户输入处理状态"""

    raw_input: str                             # 用户原始输入
    current_stage: str                         # 当前所在阶段
    context: Dict                              # 上下文信息

    # 意图分类结果
    intent: str                                # 识别的意图类型
    confidence: float                          # 置信度
    extracted_value: Optional[str]             # 提取的值
    needs_clarification: bool                  # 是否需要澄清

    # Worker 处理结果
    extracted_params: Dict                     # 提取的参数
    worker_response: str                       # Worker 的回复
    should_continue: bool                      # 是否可以继续主流程
    redirect_to: Optional[str]                 # 重定向目标节点


class UserIntent(BaseModel):
    """用户意图分类结果 (Pydantic Schema for structured output)"""

    intent_type: Literal[
        "expected_param",      # 预期的参数输入
        "question",            # 用户提问
        "suggestion_request",  # 请求建议
        "adjustment",          # 修改请求
        "confirmation",        # 确认信号
        "off_topic"            # 无关话题
    ] = Field(description="用户意图类型")

    confidence: float = Field(
        description="置信度 0-1",
        ge=0.0,
        le=1.0
    )

    extracted_value: Optional[str] = Field(
        default=None,
        description="提取的值 (如果是 expected_param)"
    )

    needs_clarification: bool = Field(
        default=False,
        description="是否需要进一步澄清"
    )

    reasoning: str = Field(
        description="判断理由"
    )


# ============================================================================
# Evaluator-Optimizer 状态 (参数优化)
# ============================================================================

class ParamOptimizerState(TypedDict):
    """参数优化工作流状态"""

    user_requirements: str                     # 用户原始需求描述
    current_params: Dict                       # 当前筛选参数
    param_summary: str                         # 参数摘要文本

    # 评估结果
    evaluation_result: str                     # "pass" | "fail"
    feedback: str                              # 改进建议
    quality_score: float                       # 质量评分

    # 迭代控制
    iteration_count: int                       # 迭代次数
    max_iterations: int                        # 最大迭代次数 (默认3)


class ParamEvaluation(BaseModel):
    """参数评估结果 (Pydantic Schema for structured output)"""

    is_complete: bool = Field(
        description="参数是否完整 (商品、国家、数量等必填项)"
    )

    is_reasonable: bool = Field(
        description="参数是否合理 (粉丝范围、筛选条件等)"
    )

    matches_intent: bool = Field(
        description="是否匹配用户原始意图"
    )

    quality_score: float = Field(
        description="质量评分 0-1",
        ge=0.0,
        le=1.0
    )

    feedback: str = Field(
        description="改进建议 (如果不通过)"
    )

    result: Literal["pass", "fail"] = Field(
        description="最终评估结果"
    )

    missing_params: List[str] = Field(
        default_factory=list,
        description="缺失的参数列表"
    )


# ============================================================================
# Parallelization 状态 (并行分析)
# ============================================================================

class AnalysisState(TypedDict):
    """并行分析工作流状态"""

    influencer_data: List[Dict]                # 爬取的达人原始数据
    batch_size: int                            # 每批处理数量
    total_count: int                           # 总达人数量

    # 批次信息
    batch_results: Annotated[List[Dict], operator.add]  # 各批次分析结果 (自动合并)
    processed_count: int                       # 已处理数量

    # 最终结果
    final_report: Optional[Dict]               # 最终聚合报告
    error_count: int                           # 错误数量


class InfluencerAnalysis(BaseModel):
    """单个达人分析结果 (Pydantic Schema for structured output)"""

    influencer_id: str = Field(
        description="达人 ID"
    )

    influencer_name: str = Field(
        description="达人名称"
    )

    audience_profile: str = Field(
        description="粉丝画像分析"
    )

    content_quality: float = Field(
        description="内容质量评分 0-10",
        ge=0.0,
        le=10.0
    )

    sales_potential: float = Field(
        description="带货能力评分 0-10",
        ge=0.0,
        le=10.0
    )

    cooperation_value: float = Field(
        description="合作价值评分 0-10",
        ge=0.0,
        le=10.0
    )

    recommendation_reason: str = Field(
        description="推荐理由"
    )

    risk_factors: List[str] = Field(
        default_factory=list,
        description="风险因素"
    )


# ============================================================================
# 排序选择状态
# ============================================================================

class SortingSelectionState(TypedDict):
    """排序选择状态"""

    available_options: List[Dict[str, str]]    # 可用排序选项
    user_input: str                            # 用户输入

    # 解析结果
    selected_indices: Optional[List[int]]      # 选择的序号列表
    selected_names: Optional[List[str]]        # 选择的排序名称
    is_valid: bool                             # 是否有效

    # 响应
    response: str                              # 返回给用户的响应
    needs_more_input: bool                     # 是否需要更多输入


# ============================================================================
# 数量调整状态
# ============================================================================

class AdjustmentState(TypedDict):
    """参数调整状态"""

    current_params: Dict                       # 当前参数
    target_count: int                          # 目标数量
    available_count: int                       # 可用数量

    # 调整方案
    suggestions: List[Dict]                    # 调整建议列表
    selected_suggestion: Optional[Dict]        # 选中的建议

    # 执行状态
    adjustment_applied: bool                   # 是否已应用调整


class AdjustmentSuggestion(BaseModel):
    """调整建议 (Pydantic Schema)"""

    suggestion_id: int = Field(
        description="建议序号"
    )

    description: str = Field(
        description="调整描述"
    )

    changes: Dict[str, str] = Field(
        description="参数变更 {参数名: 新值}"
    )

    expected_increase: str = Field(
        description="预期增加百分比"
    )

    risk_level: Literal["low", "medium", "high"] = Field(
        description="风险等级"
    )


# ============================================================================
# 辅助函数
# ============================================================================

def create_initial_state(
    user_message: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> MainWorkflowState:
    """创建初始主工作流状态"""

    return MainWorkflowState(
        # 用户输入
        user_message=user_message,
        pending_user_input=None,

        # 对话历史
        chat_history=[],

        # 需求收集
        product_name=None,
        country_name=None,
        target_count=None,

        # 分类匹配
        category_info=None,
        category_found=False,

        # 筛选参数
        current_params={},
        search_url=None,
        params_confirmed=False,

        # 数量检查
        max_pages=None,
        available_count=None,
        quantity_status=None,

        # 排序选择
        selected_sorting=None,
        sorted_urls=None,

        # 确认状态
        user_confirmed_scraping=False,
        user_confirmed_params=False,
        scraping_confirmed=False,
        requirements_complete=False,
        quantity_sufficient=False,

        # 爬取和分析
        scraped_data=None,
        analysis_results=None,
        analysis_report=None,

        # 报告
        report_id=None,
        report_path=None,
        final_report=None,
        param_summary=None,

        # 排序
        selected_sorting_names=None,

        # 响应
        response_to_user="",
        awaiting_input=False,
        current_stage="collect_requirements",
        workflow_complete=False,

        # 会话信息
        user_id=user_id,
        session_id=session_id,
    )


def create_user_input_state(
    raw_input: str,
    current_stage: str,
    context: Dict
) -> UserInputState:
    """创建用户输入处理状态"""

    return UserInputState(
        raw_input=raw_input,
        current_stage=current_stage,
        context=context,

        # 意图分类结果 (待填充)
        intent="",
        confidence=0.0,
        extracted_value=None,
        needs_clarification=False,

        # Worker 处理结果 (待填充)
        extracted_params={},
        worker_response="",
        should_continue=False,
        redirect_to=None,
    )
