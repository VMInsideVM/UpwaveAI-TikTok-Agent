"""
工作流节点模块

节点功能已直接集成在 main_workflow.py 中实现。

主工作流节点包括：
- collect_requirements_node: 需求收集（支持 Orchestrator 处理）
- match_category_node: 分类匹配（调用 category_matcher.py）
- param_optimization_node: 参数优化（调用 Evaluator-Optimizer 子工作流）
- wait_user_confirm_node: 等待用户确认参数
- check_quantity_node: 检查可用达人数量
- select_sorting_node: 排序选择（Human-in-the-Loop）
- confirm_scraping_node: 最终确认开始爬取
- scrape_data_node: 数据爬取
- analyze_data_node: 并行分析（调用 Parallelization 子工作流）
- generate_report_node: 生成报告
- export_excel_node: 导出 Excel
- graceful_end_node: 优雅结束

节点导入方式:
    from workflows.main_workflow import (
        collect_requirements_node,
        match_category_node,
        ...
    )

如需扩展或自定义节点，可在此目录下创建独立模块。
"""

# 节点函数已在 main_workflow.py 中定义
# 这里仅作为文档和扩展入口

__all__ = []
