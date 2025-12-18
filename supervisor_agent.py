"""
监督 Agent - 审核 TikTok 达人推荐 Agent 的输出质量

职责：
1. 验证 Agent 是否按照工作流程的步骤执行
2. 检查必需信息是否完整展示（如参数摘要、工具输出）
3. 识别违规行为（如总结、省略、改写工具输出）
4. 生成明确的修正指令，引导 Agent 重新生成正确回复

工作流程步骤：
- Step 1: 理解用户需求（商品、地区、数量）
- Step 2: 匹配商品分类
- Step 3: 收集筛选参数
- Step 4: 展示参数摘要（调用 review_parameters）
- Step 5: 等待用户确认
- Step 6: 提交搜索任务/生成报告
- Step 7: 返回报告结果
"""

import os
from typing import Tuple, Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class SupervisorAgent:
    """监督 Agent - 审核原 Agent 输出的质量和完整性"""

    # 工作流程步骤定义
    WORKFLOW_STEPS = {
        "understand_requirement": {
            "name": "理解需求",
            "description": "理解用户的商品、地区、粉丝数量等需求",
            "required_info": ["商品名称", "目标地区"],
            "optional_info": ["粉丝数", "达人数量"]
        },
        "match_category": {
            "name": "匹配分类",
            "description": "使用 category_match 工具匹配商品分类",
            "required_tools": ["category_match"],
            "success_indicators": ["商品分类", "category_id"]
        },
        "collect_parameters": {
            "name": "收集参数",
            "description": "收集并确认所有筛选参数",
            "required_tools": ["build_url", "review_parameters"],
        },
        "display_parameters": {
            "name": "展示参数",
            "description": "完整展示 review_parameters 工具返回的参数摘要",
            "required_markers": [
                "📋 **当前筛选参数摘要**",
                "🎯 **商品信息**",
                "🌍 **目标地区**",
                "🔍 **筛选条件**",
                "请确认以上参数是否满意"
            ],
            "forbidden_behaviors": [
                "总结参数内容",
                "改写工具输出",
                "省略部分信息",
                "只说'参数已展示'而不实际展示"
            ]
        },
        "wait_confirmation": {
            "name": "等待确认",
            "description": "等待用户确认参数或提出修改",
            "user_actions": ["确认", "修改参数"]
        },
        "submit_task": {
            "name": "提交任务",
            "description": "用户确认后提交搜索任务或生成报告",
            "required_tools": ["confirm_scraping", "submit_search_task"],
        },
        "return_result": {
            "name": "返回结果",
            "description": "返回报告链接或错误信息",
            "required_info": ["report_id", "任务状态"]
        }
    }

    # 常见违规模式
    VIOLATION_PATTERNS = {
        "incomplete_display": {
            "description": "未完整展示工具输出",
            "examples": [
                "现在为您展示参数：（但后面什么都没有）",
                "参数已整理好，请确认",
                "以下是筛选参数：（但缺少必需标记）"
            ]
        },
        "summarized_output": {
            "description": "对工具输出进行了总结",
            "examples": [
                "商品是茶杯，地区是英国，粉丝10-25万",
                "参数包括：商品、地区、粉丝数",
            ]
        },
        "skipped_step": {
            "description": "跳过了必需的工作流程步骤",
            "examples": [
                "没有调用 review_parameters 就要求用户确认",
                "没有匹配分类就直接搜索",
            ]
        },
        "missing_tool_call": {
            "description": "应该调用工具但没有调用",
            "examples": [
                "应该调用 category_match 但直接猜测分类",
                "应该调用 review_parameters 但手动列举参数",
            ]
        }
    }

    def __init__(self, debug: bool = True):
        """
        初始化监督 Agent

        Args:
            debug: 是否启用调试模式
        """
        self.debug = debug
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "deepseek-ai/DeepSeek-V3.1-Terminus"),
            temperature=0.1,  # 低温度，保持严格判断
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )

        # 系统提示词
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """构建监督 Agent 的系统提示词"""
        return """你是一个严格的监督 Agent，负责审核 TikTok 达人推荐 Agent 的输出质量。

**你的职责**：
1. 验证 Agent 是否按照工作流程步骤执行
2. 检查必需信息是否完整展示
3. 识别违规行为（总结、省略、改写）
4. 判断是否需要重新生成回复

**工作流程步骤**：
1. 理解需求 → 2. 匹配分类 → 3. 收集参数 → 4. 展示参数 → 5. 等待确认 → 6. 提交任务 → 7. 返回结果

**⭐ 最重要的检查项（步骤 4：展示参数）**：
- Agent 调用 `review_parameters` 工具后，**必须将工具返回的文本作为完整回复发送给用户**
- **逐字逐句复制**，不得有任何总结、改写、省略、添加
- **必须包含所有标记**：📋 **当前筛选参数摘要**、🎯 **商品信息**、🌍 **目标地区**、🔍 **筛选条件**、"请确认以上参数是否满意"
- **禁止行为**：
  ✗ "现在为您展示参数："（然后什么都不展示）
  ✗ "参数已整理好，请确认"（总结而非完整展示）
  ✗ "商品是茶杯，地区是英国"（改写工具输出）
  ✗ 只展示部分参数，省略其他内容

**你的输出格式**：
{
  "is_valid": true/false,
  "current_step": "步骤名称",
  "issues": ["问题1", "问题2", ...],
  "severity": "critical/warning/info",
  "retry_needed": true/false,
  "correction_prompt": "如果需要重试，这里是修正指令"
}

**判断标准**：
- `critical`（严重）：未完整复制工具输出、缺失必需信息、跳过步骤、违规总结 → **必须重试**
- `warning`（警告）：格式不规范、措辞不当 → 可以放行
- `info`（信息）：正常执行，无问题 → 放行

现在开始审核！"""

    def review_response(
        self,
        agent_response: str,
        conversation_history: list,
        tool_calls: list,
        expected_step: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        审核 Agent 的响应

        Args:
            agent_response: Agent 生成的回复
            conversation_history: 对话历史
            tool_calls: Agent 调用的工具列表
            expected_step: 预期的当前步骤（可选）

        Returns:
            (is_valid, correction_prompt, review_details)
            - is_valid: True 表示通过审核，False 表示需要重试
            - correction_prompt: 如果需要重试，返回修正指令
            - review_details: 审核详情（问题列表、严重程度等）
        """
        try:
            # 构建审核请求
            review_request = self._build_review_request(
                agent_response,
                conversation_history,
                tool_calls,
                expected_step
            )

            if self.debug:
                print(f"\n{'='*60}")
                print(f"[SupervisorAgent] 开始审核 Agent 响应")
                print(f"{'='*60}")
                print(f"工具调用: {[t['tool_name'] for t in tool_calls]}")
                print(f"预期步骤: {expected_step or '自动推断'}")

            # 调用 LLM 进行审核
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=review_request)
            ]

            response = self.llm.invoke(messages)
            review_result = self._parse_review_result(response.content)

            if self.debug:
                print(f"\n审核结果: {'✅ 通过' if review_result['is_valid'] else '❌ 不通过'}")
                print(f"严重程度: {review_result['severity']}")
                if review_result['issues']:
                    print(f"问题列表:")
                    for issue in review_result['issues']:
                        print(f"  - {issue}")
                print(f"{'='*60}\n")

            return (
                review_result['is_valid'],
                review_result.get('correction_prompt'),
                review_result
            )

        except Exception as e:
            if self.debug:
                print(f"[SupervisorAgent] 审核过程出错: {e}")
                import traceback
                traceback.print_exc()

            # 如果监督 Agent 出错，默认放行（避免阻塞）
            return True, None, {
                "is_valid": True,
                "error": str(e),
                "issues": [f"监督 Agent 出错: {e}"]
            }

    def _build_review_request(
        self,
        agent_response: str,
        conversation_history: list,
        tool_calls: list,
        expected_step: Optional[str]
    ) -> str:
        """构建审核请求内容"""

        # 提取最近的对话
        recent_history = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
        history_text = "\n".join([
            f"{'用户' if msg['role'] == 'user' else 'Agent'}: {msg['content'][:200]}..."
            for msg in recent_history
        ])

        # 提取工具调用信息
        tools_text = "\n".join([
            f"- {call['tool_name']}: {call.get('output', 'N/A')[:200]}..."
            for call in tool_calls[-3:]  # 只显示最近 3 次工具调用
        ])

        # 检查是否调用了 review_parameters
        review_tool_output = None
        for call in reversed(tool_calls):
            if call['tool_name'] == 'review_parameters':
                review_tool_output = call.get('output', '')
                break

        # 构建请求
        request = f"""请审核以下 Agent 响应是否符合规范：

**对话历史**：
{history_text}

**最近工具调用**：
{tools_text if tools_text else '（无工具调用）'}

**Agent 响应**：
{agent_response}

**预期步骤**：{expected_step or '请根据对话历史自动推断'}
"""

        # ⭐ 如果调用了 review_parameters，附加工具输出用于对比
        if review_tool_output:
            request += f"""
**⚠️ 重要提醒**：
Agent 调用了 `review_parameters` 工具。请严格检查：
1. Agent 是否将工具输出**逐字逐句**完整复制到回复中？
2. 是否包含所有必需标记（📋 🎯 🌍 🔍）？
3. 是否有任何总结、改写、省略行为？

**review_parameters 工具的原始输出**（供对比）：
{review_tool_output[:500]}...
"""

        request += "\n请严格按照 JSON 格式返回审核结果。"

        return request

    def _parse_review_result(self, llm_output: str) -> Dict[str, Any]:
        """解析 LLM 返回的审核结果"""
        import json
        import re

        try:
            # 尝试提取 JSON（去除可能的 markdown 代码块标记）
            json_match = re.search(r'\{[\s\S]*\}', llm_output)
            if json_match:
                result = json.loads(json_match.group(0))
                return result
            else:
                # 如果没有找到 JSON，返回默认结果
                return {
                    "is_valid": True,
                    "current_step": "unknown",
                    "issues": ["无法解析审核结果"],
                    "severity": "warning",
                    "retry_needed": False,
                    "correction_prompt": None
                }
        except json.JSONDecodeError as e:
            if self.debug:
                print(f"[SupervisorAgent] JSON 解析失败: {e}")
                print(f"LLM 输出: {llm_output}")

            # 解析失败，默认放行
            return {
                "is_valid": True,
                "current_step": "unknown",
                "issues": [f"JSON 解析失败: {e}"],
                "severity": "warning",
                "retry_needed": False,
                "correction_prompt": None
            }

    def quick_check(self, agent_response: str, tool_calls: list) -> Tuple[bool, Optional[str]]:
        """
        快速检查（基于规则，不调用 LLM）

        用于高频场景，先进行快速规则检查，只有发现可疑情况才调用完整审核

        Returns:
            (is_valid, issue_description)
        """
        # 检查 1: 如果调用了 review_parameters，必须包含所有必需标记
        review_tool_called = any(
            call['tool_name'] == 'review_parameters'
            for call in tool_calls
        )

        if review_tool_called:
            required_markers = self.WORKFLOW_STEPS['display_parameters']['required_markers']
            missing_markers = [
                marker for marker in required_markers
                if marker not in agent_response
            ]

            if missing_markers:
                return False, f"调用了 review_parameters 但缺失必需标记: {missing_markers}"

            # ⭐ 检查 1.1: 获取工具输出，验证是否完整复制
            review_tool_output = None
            for call in reversed(tool_calls):
                if call['tool_name'] == 'review_parameters':
                    review_tool_output = call.get('output', '')
                    break

            if review_tool_output:
                # 检查工具输出的关键内容是否在 Agent 响应中
                # 提取工具输出的特征片段（去除可能的空白字符差异）
                tool_lines = [line.strip() for line in review_tool_output.split('\n') if line.strip()]
                response_lines = [line.strip() for line in agent_response.split('\n') if line.strip()]

                # 检查工具输出的主要内容是否都在响应中
                missing_content = []
                for line in tool_lines:
                    # 跳过纯分隔符行
                    if line in ['---', '═', '─']:
                        continue
                    # 检查重要内容行是否存在
                    if any(marker in line for marker in ['📋', '🎯', '🌍', '🔍', '商品名称', '目标地区', '粉丝数']):
                        if line not in response_lines:
                            missing_content.append(line)

                if missing_content:
                    return False, f"Agent 未完整复制 review_parameters 输出，缺失内容: {missing_content[:2]}"

        # 检查 2: 响应长度异常短（可能是总结）
        if review_tool_called and len(agent_response) < 100:
            return False, "响应过短，可能进行了不当总结（应完整展示工具输出）"

        # 检查 3: 常见违规关键词
        violation_keywords = [
            "参数如下：",
            "已经为您整理",
            "参数已展示",
            "现在为您展示当前收集的所有筛选参数：",
            "以下是筛选参数",
            "接下来让我展示",
            "接下来展示",
            "让我展示当前的筛选参数",
            "供您确认：",
        ]

        if review_tool_called:
            for keyword in violation_keywords:
                if keyword in agent_response:
                    # 如果包含违规关键词，检查是否真的完整展示了
                    required_markers = self.WORKFLOW_STEPS['display_parameters']['required_markers']
                    if not all(marker in agent_response for marker in required_markers):
                        return False, f"发现违规关键词但未完整展示: {keyword}"

        # 通过快速检查
        return True, None


# 全局单例实例
_supervisor_instance = None


def get_supervisor(debug: bool = True) -> SupervisorAgent:
    """
    获取全局监督 Agent 实例（单例模式）

    Args:
        debug: 是否启用调试模式

    Returns:
        SupervisorAgent 实例
    """
    global _supervisor_instance
    if _supervisor_instance is None:
        _supervisor_instance = SupervisorAgent(debug=debug)
    return _supervisor_instance


if __name__ == "__main__":
    # 测试监督 Agent
    print("🧪 测试监督 Agent\n")

    supervisor = SupervisorAgent(debug=True)

    # 测试用例 1: 正确展示参数
    print("=" * 60)
    print("测试 1: 正确展示参数（应该通过）")
    print("=" * 60)

    good_response = """📋 **当前筛选参数摘要**

🎯 **商品信息**
   • 商品名称: 茶杯
   • 商品分类: 家居生活
   • 目标数量: 2 个达人

🌍 **目标地区**: 英国

🔍 **筛选条件**
   • 粉丝数: 10万 - 25万
   • 推广渠道: 不限制
   • 联盟达人: 不限制

---

请确认以上参数是否满意？
• 如果满意，请回复：好的/确认/可以/开始
• 如果需要调整，请告诉我要修改哪些参数"""

    conversation_history = [
        {"role": "user", "content": "英国地区的茶杯，找10-25w粉丝的达人，2个"}
    ]

    tool_calls = [
        {"tool_name": "category_match", "output": "家居生活"},
        {"tool_name": "build_url", "output": "URL constructed"},
        {"tool_name": "review_parameters", "output": good_response}
    ]

    is_valid, correction, details = supervisor.review_response(
        good_response,
        conversation_history,
        tool_calls,
        expected_step="display_parameters"
    )

    print(f"结果: {'✅ 通过' if is_valid else '❌ 不通过'}")
    print()

    # 测试用例 2: 违规总结
    print("=" * 60)
    print("测试 2: 违规总结（应该被拦截）")
    print("=" * 60)

    bad_response = "现在为您展示当前收集的所有筛选参数："

    is_valid, correction, details = supervisor.review_response(
        bad_response,
        conversation_history,
        tool_calls,
        expected_step="display_parameters"
    )

    print(f"结果: {'✅ 通过（不符合预期）' if is_valid else '❌ 不通过（符合预期）'}")
    if correction:
        print(f"修正指令: {correction[:200]}...")
    print()

    # 测试用例 3: 快速检查
    print("=" * 60)
    print("测试 3: 快速检查功能")
    print("=" * 60)

    is_valid, issue = supervisor.quick_check(bad_response, tool_calls)
    print(f"快速检查结果: {'✅ 通过' if is_valid else '❌ 不通过'}")
    if issue:
        print(f"问题: {issue}")

    print("\n✅ 测试完成！")
