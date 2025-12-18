"""
工具调用追踪器 - 记录 Agent 的工具调用历史
"""


class ResponseValidator:
    """工具调用追踪器"""

    def __init__(self, debug: bool = False):
        """
        初始化追踪器

        Args:
            debug: 是否启用调试模式
        """
        self.debug = debug
        self.last_tool_calls = []  # 存储最近的工具调用历史

    def record_tool_call(self, tool_name: str, tool_output: str):
        """
        记录工具调用

        Args:
            tool_name: 工具名称
            tool_output: 工具返回的输出
        """
        self.last_tool_calls.append({
            'tool_name': tool_name,
            'output': tool_output
        })

        # 只保留最近 10 次工具调用
        if len(self.last_tool_calls) > 10:
            self.last_tool_calls.pop(0)

        if self.debug:
            print(f"[ToolCallTracker] 记录工具调用: {tool_name}")

    def clear_tool_history(self):
        """清空工具调用历史（用于新会话）"""
        self.last_tool_calls = []
        if self.debug:
            print("[ToolCallTracker] 已清空工具调用历史")


# 全局单例实例
_validator_instance = None


def get_validator(debug: bool = False) -> ResponseValidator:
    """
    获取全局工具追踪器实例（单例模式）

    Args:
        debug: 是否启用调试模式

    Returns:
        ResponseValidator 实例
    """
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ResponseValidator(debug=debug)
    return _validator_instance
