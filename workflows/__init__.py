"""
LangGraph Workflow 模块

提供 TikTok 达人推荐系统的工作流实现，包括：
- 主工作流 (main_workflow)
- 参数优化工作流 (param_optimizer) - Evaluator-Optimizer Pattern
- 并行分析工作流 (parallel_analyzer) - Parallelization Pattern
- 用户输入处理工作流 (orchestrator) - Orchestrator-Worker Pattern
"""

from .states import (
    # 主要状态类型
    MainWorkflowState,
    UserInputState,
    ParamOptimizerState,
    AnalysisState,
    SortingSelectionState,
    AdjustmentState,

    # Pydantic 模型
    UserIntent,
    ParamEvaluation,
    InfluencerAnalysis,
    AdjustmentSuggestion,

    # 辅助函数
    create_initial_state,
    create_user_input_state,
)

from .orchestrator import create_orchestrator_workflow
from .param_optimizer import create_param_optimizer, optimize_params
from .parallel_analyzer import create_parallel_analyzer, analyze_influencers
from .main_workflow import create_main_workflow, WorkflowRunner

__all__ = [
    # 状态类型
    "MainWorkflowState",
    "UserInputState",
    "ParamOptimizerState",
    "AnalysisState",
    "SortingSelectionState",
    "AdjustmentState",

    # Pydantic 模型
    "UserIntent",
    "ParamEvaluation",
    "InfluencerAnalysis",
    "AdjustmentSuggestion",

    # 辅助函数
    "create_initial_state",
    "create_user_input_state",

    # 工作流工厂
    "create_orchestrator_workflow",
    "create_param_optimizer",
    "optimize_params",
    "create_parallel_analyzer",
    "analyze_influencers",
    "create_main_workflow",
    "WorkflowRunner",
]
