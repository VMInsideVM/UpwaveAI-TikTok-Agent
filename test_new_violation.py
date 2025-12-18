"""测试新增的违规模式"""

from response_validator import ResponseValidator
from supervisor_agent import SupervisorAgent

# 测试 ResponseValidator
print("=" * 60)
print("测试 1: ResponseValidator - 新违规模式")
print("=" * 60)

validator = ResponseValidator(debug=True)

# 模拟工具调用
tool_output = """📋 **当前筛选参数摘要**

🎯 **商品信息**
   • 商品名称: 茶杯

🌍 **目标地区**: 英国

🔍 **筛选条件**
   • 粉丝数: 10万 - 25万

请确认以上参数是否满意？"""

validator.record_tool_call('review_parameters', tool_output)

# 测试违规响应
bad_response = "接下来让我展示当前的筛选参数供您确认："

is_valid, retry_prompt = validator.validate_response(bad_response)
print(f"\n结果: {'✅ 通过（不应该）' if is_valid else '❌ 被拦截（正确）'}")
if retry_prompt:
    print(f"重试提示: {retry_prompt[:150]}...")

print("\n" + "=" * 60)
print("测试 2: SupervisorAgent - 快速检查")
print("=" * 60)

supervisor = SupervisorAgent(debug=False)

tool_calls = [
    {"tool_name": "review_parameters", "output": tool_output}
]

is_valid, issue = supervisor.quick_check(bad_response, tool_calls)
print(f"\n快速检查结果: {'✅ 通过（不应该）' if is_valid else '❌ 被拦截（正确）'}")
if issue:
    print(f"问题: {issue}")

print("\n✅ 测试完成！")
