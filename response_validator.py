"""
响应验证器 - 检测 agent 是否正确展示筛选参数

当 agent 调用 review_parameters 工具后，必须将工具返回的完整内容展示给用户。
此模块检测是否违反了这个规则，并触发自动重试。
"""

import re
from typing import Optional, Tuple


class ResponseValidator:
    """Agent 响应验证器"""

    # review_parameters 工具返回内容的特征标记
    PARAMETER_REVIEW_MARKERS = [
        "📋 **当前筛选参数摘要**",
        "🎯 **商品信息**",
        "🌍 **目标地区**",
        "🔍 **筛选条件**",
        "请确认以上参数是否满意"
    ]

    # 违规模式：agent 没有完整展示参数，而是进行了总结
    VIOLATION_PATTERNS = [
        r"参数如下[：:]",  # "参数如下："
        r"已经?为[您你]整理了?(?:筛选)?参数",  # "已为您整理筛选参数"
        r"(?:筛选)?参数已?(?:展示|列出|整理)",  # "参数已展示"、"筛选参数已列出"
        r"请确认(?:以下)?参数",  # "请确认参数"（但没有完整展示）
        r"好的[，,]?(?:我已经?)?为[您你](?:整理|汇总|列出)",  # "好的，我已为您整理"
    ]

    def __init__(self, debug: bool = False):
        """
        初始化验证器

        Args:
            debug: 是否启用调试模式（打印详细检测信息）
        """
        self.debug = debug
        self.last_tool_calls = []  # 存储最近的工具调用历史

    def record_tool_call(self, tool_name: str, tool_output: str):
        """
        记录工具调用（供后续验证使用）

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
            print(f"[ResponseValidator] 记录工具调用: {tool_name}")

    def validate_response(self, agent_response: str) -> Tuple[bool, Optional[str]]:
        """
        验证 agent 响应是否正确展示了 review_parameters 工具的输出

        Args:
            agent_response: Agent 的回复文本

        Returns:
            (is_valid, retry_prompt)
            - is_valid: True 表示验证通过，False 表示需要重试
            - retry_prompt: 如果需要重试，返回重试提示；否则返回 None
        """
        # 1. 检查最近是否调用了 review_parameters 工具
        review_tool_output = self._get_last_review_parameters_output()

        if not review_tool_output:
            # 没有调用 review_parameters 工具，跳过验证
            if self.debug:
                print("[ResponseValidator] 未检测到 review_parameters 调用，跳过验证")
            return True, None

        # 2. 检查 agent 是否完整展示了工具输出
        is_complete = self._check_complete_display(agent_response, review_tool_output)

        if is_complete:
            # 验证通过
            if self.debug:
                print("[ResponseValidator] ✅ Agent 正确展示了参数")
            return True, None

        # 3. 检查是否存在违规总结模式
        has_violation = self._check_violation_patterns(agent_response)

        if has_violation:
            # 发现违规，需要重试
            if self.debug:
                print("[ResponseValidator] ❌ Agent 违规：未完整展示参数")

            retry_prompt = self._generate_retry_prompt(review_tool_output)
            return False, retry_prompt

        # 4. 如果既没有完整展示，也没有明显违规，可能是其他正常情况（如工具报错）
        # 这种情况下允许通过
        if self.debug:
            print("[ResponseValidator] ⚠️ 未完整展示参数，但无明显违规，允许通过")
        return True, None

    def _get_last_review_parameters_output(self) -> Optional[str]:
        """获取最近一次 review_parameters 工具的输出"""
        # 倒序查找最近的 review_parameters 调用
        for call in reversed(self.last_tool_calls):
            if call['tool_name'] == 'review_parameters':
                return call['output']
        return None

    def _check_complete_display(self, agent_response: str, tool_output: str) -> bool:
        """
        检查 agent 响应是否包含工具输出的核心内容

        策略：检查工具输出的特征标记是否都出现在 agent 响应中
        """
        # 检查所有特征标记
        for marker in self.PARAMETER_REVIEW_MARKERS:
            if marker not in agent_response:
                if self.debug:
                    print(f"[ResponseValidator] 缺失标记: {marker}")
                return False

        # 所有标记都存在，认为是完整展示
        return True

    def _check_violation_patterns(self, agent_response: str) -> bool:
        """
        检查是否存在违规总结模式

        Returns:
            True 表示发现违规，False 表示未发现
        """
        for pattern in self.VIOLATION_PATTERNS:
            if re.search(pattern, agent_response, re.IGNORECASE):
                if self.debug:
                    print(f"[ResponseValidator] 发现违规模式: {pattern}")
                return True
        return False

    def _generate_retry_prompt(self, tool_output: str) -> str:
        """
        生成重试提示，强制 agent 重新输出

        Args:
            tool_output: review_parameters 工具的原始输出

        Returns:
            强制性的重试提示
        """
        return f"""⚠️ **系统检测到错误**：你没有完整展示筛选参数！

**违规行为**：你对 review_parameters 工具返回的内容进行了总结、改写或省略。

**强制要求**：
1. **必须**将以下内容**逐字逐句**地复制到你的回复中
2. **不得**进行任何总结、改写、省略或添加
3. **不得**说"参数已展示"、"请确认参数"等额外话语
4. **直接**将下面的文本作为你的完整回复发送给用户

---

{tool_output}

---

**立即重新生成回复**，严格遵守以上要求！"""

    def clear_tool_history(self):
        """清空工具调用历史（用于新会话）"""
        self.last_tool_calls = []
        if self.debug:
            print("[ResponseValidator] 已清空工具调用历史")


# 全局单例实例
_validator_instance = None


def get_validator(debug: bool = False) -> ResponseValidator:
    """
    获取全局验证器实例（单例模式）

    Args:
        debug: 是否启用调试模式

    Returns:
        ResponseValidator 实例
    """
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ResponseValidator(debug=debug)
    return _validator_instance


if __name__ == "__main__":
    # 测试验证器
    print("🧪 测试响应验证器\n")

    validator = ResponseValidator(debug=True)

    # 测试用例 1：正确展示参数
    print("=" * 60)
    print("测试 1：正确展示参数")
    print("=" * 60)

    tool_output = """📋 **当前筛选参数摘要**

🎯 **商品信息**
   • 商品名称: 女士香水
   • 商品分类: 美妆个护
   • 目标数量: 50 个达人

🌍 **目标地区**: 美国

🔍 **筛选条件**
   • 粉丝数: 10万 - 25万
   • 推广渠道: 不限制
   • 联盟达人: 不限制

---

请确认以上参数是否满意？
• 如果满意，请回复：好的/确认/可以/开始
• 如果需要调整，请告诉我要修改哪些参数"""

    validator.record_tool_call('review_parameters', tool_output)

    # 正确的响应（完整复制）
    good_response = tool_output
    is_valid, retry = validator.validate_response(good_response)
    print(f"结果: {'✅ 通过' if is_valid else '❌ 失败'}")
    if retry:
        print(f"重试提示: {retry[:100]}...")
    print()

    # 测试用例 2：违规总结
    print("=" * 60)
    print("测试 2：违规总结（应该被拦截）")
    print("=" * 60)

    validator.record_tool_call('review_parameters', tool_output)

    bad_response = "好的，我已经为您整理了筛选参数，请确认是否满意。"
    is_valid, retry = validator.validate_response(bad_response)
    print(f"结果: {'✅ 通过' if is_valid else '❌ 失败（符合预期）'}")
    if retry:
        print(f"重试提示:\n{retry}")
    print()

    # 测试用例 3：部分展示
    print("=" * 60)
    print("测试 3：部分展示（应该被拦截）")
    print("=" * 60)

    validator.record_tool_call('review_parameters', tool_output)

    partial_response = """参数如下：
商品：女士香水
粉丝数：10万-25万

请确认是否满意？"""
    is_valid, retry = validator.validate_response(partial_response)
    print(f"结果: {'✅ 通过' if is_valid else '❌ 失败（符合预期）'}")
    if retry:
        print(f"重试提示: {retry[:100]}...")
    print()

    print("✅ 测试完成！")
