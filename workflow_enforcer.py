"""
LangChain Callback 工作流强制执行器
确保 Agent 按照正确的工作流程执行工具调用
"""

from langchain_core.callbacks.base import BaseCallbackHandler
from typing import Any, Dict, List, Optional
from langchain_core.messages import AIMessage


class WorkflowEnforcer(BaseCallbackHandler):
    """工作流强制执行器 - 监控并强制正确的工具调用顺序"""

    def __init__(self, debug: bool = False):
        """
        初始化工作流强制执行器

        Args:
            debug: 是否启用调试模式
        """
        super().__init__()
        self.debug = debug
        self.tool_call_history = []  # 工具调用历史
        self.expect_review_parameters = False  # 是否期待调用 review_parameters
        self.last_tool_output = None  # 最后一个工具的输出
        self.last_tool_name = None  # 最后一个工具的名称
        self.should_inject_reminder = False  # 是否应该注入提醒消息

    def on_tool_start(
        self, serialized: Dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        """工具开始执行时的回调"""
        tool_name = serialized.get("name", "unknown")

        if self.debug:
            print(f"[WorkflowEnforcer] 工具开始: {tool_name}")

        # 记录工具调用
        self.tool_call_history.append({
            'name': tool_name,
            'input': input_str,
            'started': True,
            'completed': False
        })

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """工具执行完成时的回调"""
        # 更新最后一个工具的完成状态
        if self.tool_call_history:
            self.tool_call_history[-1]['completed'] = True
            self.tool_call_history[-1]['output'] = output

            tool_name = self.tool_call_history[-1]['name']
            self.last_tool_name = tool_name
            self.last_tool_output = output

            if self.debug:
                print(f"[WorkflowEnforcer] 工具完成: {tool_name}")

            # 🔥 关键逻辑：检查是否需要强制调用 review_parameters
            if tool_name == 'build_search_url':
                self.expect_review_parameters = True
                self.should_inject_reminder = True
                if self.debug:
                    print("[WorkflowEnforcer] ⚠️ 检测到 build_search_url 调用，期待下一个调用 review_parameters")

            # 如果调用了 review_parameters，清除期待状态
            elif tool_name == 'review_parameters':
                self.expect_review_parameters = False
                self.should_inject_reminder = False
                if self.debug:
                    print("[WorkflowEnforcer] ✅ review_parameters 已调用，清除期待状态")

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """工具执行出错时的回调"""
        if self.debug:
            print(f"[WorkflowEnforcer] 工具错误: {error}")

        # 更新最后一个工具的错误状态
        if self.tool_call_history:
            self.tool_call_history[-1]['error'] = str(error)
            self.tool_call_history[-1]['completed'] = False

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """LLM 开始生成时的回调"""
        if self.debug:
            print(f"[WorkflowEnforcer] LLM 开始生成")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """LLM 生成完成时的回调"""
        if self.debug:
            print(f"[WorkflowEnforcer] LLM 生成完成")

        # 🔥 关键逻辑：检查是否违反工作流
        if self.expect_review_parameters:
            # 检查 LLM 的输出中是否包含工具调用
            has_tool_call = False
            review_parameters_called = False

            if hasattr(response, 'generations'):
                for generation_list in response.generations:
                    for generation in generation_list:
                        message = generation.message
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            has_tool_call = True
                            # 检查是否调用了 review_parameters
                            for tool_call in message.tool_calls:
                                if tool_call.get('name') == 'review_parameters':
                                    review_parameters_called = True
                                    break

            # 如果 LLM 结束生成但没有调用 review_parameters
            if not review_parameters_called and not has_tool_call:
                if self.debug:
                    print("[WorkflowEnforcer] ⚠️ 警告：Agent 未调用 review_parameters，违反工作流！")
                self.should_inject_reminder = True

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Chain 执行完成时的回调"""
        if self.debug:
            print(f"[WorkflowEnforcer] Chain 完成")

    def get_violation_status(self) -> Dict[str, Any]:
        """
        获取工作流违反状态

        Returns:
            包含违反信息的字典
        """
        return {
            'expect_review_parameters': self.expect_review_parameters,
            'should_inject_reminder': self.should_inject_reminder,
            'last_tool_name': self.last_tool_name,
            'last_tool_output': self.last_tool_output,
            'tool_call_count': len(self.tool_call_history)
        }

    def reset(self):
        """重置工作流状态（用于新对话轮次）"""
        self.expect_review_parameters = False
        self.should_inject_reminder = False
        self.last_tool_output = None
        self.last_tool_name = None
        # 不清空历史记录，保留用于调试

    def get_reminder_message(self) -> Optional[str]:
        """
        获取提醒消息（如果需要）

        Returns:
            提醒消息字符串，或 None
        """
        if self.should_inject_reminder and self.expect_review_parameters:
            return """⚠️ 工作流提醒：

您刚刚调用了 build_search_url 工具构建了搜索URL。

根据工作流程，下一步您必须：
1. 调用 review_parameters 工具展示参数给用户
2. 将工具返回的文本完整展示给用户
3. 等待用户确认

请立即调用 review_parameters 工具！"""
        return None


# 全局单例实例
_enforcer_instance = None


def get_enforcer(debug: bool = False) -> WorkflowEnforcer:
    """
    获取全局工作流强制执行器实例（单例模式）

    Args:
        debug: 是否启用调试模式

    Returns:
        WorkflowEnforcer 实例
    """
    global _enforcer_instance
    if _enforcer_instance is None:
        _enforcer_instance = WorkflowEnforcer(debug=debug)
    return _enforcer_instance
