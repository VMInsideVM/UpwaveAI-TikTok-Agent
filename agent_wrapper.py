"""
Agent 包装器 - 用于捕获和报告 Agent 处理进度
"""

import sys
import io
import re
from typing import Callable, Optional


class AgentProgressWrapper:
    """
    包装 Agent 的输出，实时捕获并报告进度
    """

    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """
        初始化进度包装器

        Args:
            progress_callback: 进度回调函数，接收进度消息字符串
        """
        self.progress_callback = progress_callback
        self.original_stdout = sys.stdout
        self.captured_output = io.StringIO()

    def parse_progress(self, text: str) -> Optional[str]:
        """
        解析输出文本，提取有用的进度信息

        Args:
            text: 原始输出文本

        Returns:
            用户友好的进度消息，如果没有则返回 None
        """
        # 过滤掉品牌相关字样
        text = text.replace("fastmoss", "系统")
        text = text.replace("FastMoss", "系统")
        text = text.replace("FASTMOSS", "系统")

        # 匹配常见的进度模式
        patterns = {
            r'🔄.*爬取': '正在获取数据...',
            r'✅.*成功': '操作成功',
            r'🔍.*检查': '正在检查参数...',
            r'📊.*分析': '正在分析数据...',
            r'💾.*保存': '正在保存结果...',
            r'🎯.*匹配': '正在匹配分类...',
            r'📈.*计算': '正在计算...',
            r'⏳.*等待': '请稍候...',
            r'正在.*': None,  # 保留原始的"正在..."消息
            r'\[.*调用.*工具.*\]': '正在执行操作...',
            r'Tool:.*': '正在使用工具...',
        }

        for pattern, message in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                return message if message else text.strip()

        # 如果包含关键词但没有匹配到具体模式
        keywords = ['匹配', '分类', '搜索', '爬取', '导出', '分析', '检查', '计算']
        for keyword in keywords:
            if keyword in text:
                return f'正在{keyword}...'

        return None


def translate_tool_call(tool_name: str) -> str:
    """
    将技术性的工具名称转换为用户友好的描述

    Args:
        tool_name: 工具名称（如 build_search_url）

    Returns:
        用户友好的描述
    """
    tool_translations = {
        'build_search_url': '正在构建搜索条件...',
        'match_product_category': '正在识别商品类型...',
        'get_max_page_number': '正在检查可用数据量...',
        'analyze_quantity_gap': '正在分析结果数量...',
        'suggest_parameter_adjustments': '正在生成优化建议...',
        'get_sort_suffix': '正在设置排序方式...',
        'scrape_and_export_json': '正在搜索达人...',
        'process_influencer_detail': '正在获取详细信息...',
        'scrape_influencers': '正在爬取达人数据...',
        'export_excel': '正在导出结果...',
    }

    return tool_translations.get(tool_name, '正在处理...')

    def write(self, text: str):
        """捕获输出并解析进度"""
        # 写入原始输出（用于调试）
        self.captured_output.write(text)

        # 解析进度信息
        progress = self.parse_progress(text)
        if progress and self.progress_callback:
            self.progress_callback(progress)

    def flush(self):
        """刷新输出"""
        self.captured_output.flush()

    def __enter__(self):
        """进入上下文管理器"""
        sys.stdout = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        sys.stdout = self.original_stdout

    def get_captured(self) -> str:
        """获取捕获的完整输出"""
        return self.captured_output.getvalue()


def clean_response(response: str) -> str:
    """
    清理 Agent 响应，移除品牌相关字样和内部标记

    Args:
        response: 原始响应文本

    Returns:
        清理后的响应文本
    """
    if not response:
        return response

    # 替换品牌相关词汇
    replacements = {
        "fastmoss": "系统",
        "FastMoss": "系统",
        "FASTMOSS": "系统",
        "TikTok 达人推荐智能助手": "智能推荐助手",
        "TikTok 达人推荐": "达人推荐",
    }

    cleaned = response
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)

    # ⭐ 移除内部标记（不应显示给用户）
    # 移除 review_parameters 工具添加的提醒标记
    cleaned = re.sub(r'\[🔔 请将以下内容完整展示给用户\]\n*', '', cleaned)

    return cleaned


if __name__ == "__main__":
    # 测试代码
    def mock_progress_callback(msg: str):
        print(f"[进度] {msg}")

    wrapper = AgentProgressWrapper(progress_callback=mock_progress_callback)

    # 测试解析
    test_messages = [
        "🔄 正在爬取数据...",
        "✅ 数据爬取成功！",
        "🎯 正在匹配商品分类...",
        "📊 正在分析数量缺口...",
        "[正在调用工具: match_product_category]",
        "fastmoss 系统提示",
    ]

    for msg in test_messages:
        progress = wrapper.parse_progress(msg)
        print(f"原文: {msg}")
        print(f"解析: {progress}")
        print()

    # 测试清理响应
    response = "欢迎使用 fastmoss TikTok 达人推荐智能助手！"
    cleaned = clean_response(response)
    print(f"原响应: {response}")
    print(f"清理后: {cleaned}")
