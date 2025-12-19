"""
测试 review_parameters 工具输出问题的修复

这个脚本模拟了 Agent 调用 review_parameters 工具的场景，
并验证我们的修复方案是否能确保输出被正确返回给用户。
"""

import sys
sys.path.insert(0, '.')

from agent_tools import ReviewParametersTool
from response_validator import get_validator
from agent_wrapper import clean_response


def test_review_parameters_output():
    """测试 review_parameters 工具的输出"""
    print("=" * 60)
    print("测试 1: review_parameters 工具输出")
    print("=" * 60)

    # 创建工具实例
    tool = ReviewParametersTool()

    # 模拟调用参数
    current_params = {
        'country_name': '美国',
        'promotion_channel': 'all',
        'affiliate_check': False,
        'followers_min': 200000,
        'followers_max': 500000,
        'target_count': 40
    }

    product_name = "餐盘"
    target_count = 40
    category_info = {
        'category_name': '家居用品',
        'main_category': '家居生活'
    }

    # 调用工具
    result = tool._run(
        current_params=current_params,
        product_name=product_name,
        target_count=target_count,
        category_info=category_info
    )

    print("\n【工具原始输出】:")
    print(result)
    print("\n" + "=" * 60)

    # 测试清理后的输出
    cleaned = clean_response(result)
    print("\n【清理后的输出】:")
    print(cleaned)
    print("\n" + "=" * 60)

    # 验证输出是否包含关键信息
    checks = [
        ("包含标题", "当前筛选参数摘要" in result),
        ("包含商品信息", "餐盘" in result),
        ("包含国家", "美国" in result),
        ("包含粉丝范围", "20万 - 50万" in result),
        ("包含确认提示", "请确认以上参数是否满意" in result),
        ("内部标记已清理", "[🔔 请将以下内容完整展示给用户]" not in cleaned),
    ]

    print("\n【验证结果】:")
    all_passed = True
    for check_name, check_result in checks:
        status = "✅" if check_result else "❌"
        print(f"  {status} {check_name}")
        if not check_result:
            all_passed = False

    return all_passed


def test_validator_tracking():
    """测试工具调用追踪功能"""
    print("\n" + "=" * 60)
    print("测试 2: 工具调用追踪")
    print("=" * 60)

    # 获取 validator 实例
    validator = get_validator(debug=True)

    # 清空历史
    validator.clear_tool_history()

    # 模拟工具调用
    tool = ReviewParametersTool()
    result = tool._run(
        current_params={'country_name': '美国', 'target_count': 40},
        product_name="测试商品",
        target_count=40,
        category_info={'category_name': '测试类目'}
    )

    # 检查是否记录到 validator
    print(f"\n记录的工具调用数量: {len(validator.last_tool_calls)}")

    if validator.last_tool_calls:
        last_call = validator.last_tool_calls[-1]
        print(f"最后一次调用的工具: {last_call['tool_name']}")
        print(f"输出长度: {len(last_call['output'])} 字符")

        # 验证
        is_review_params = last_call['tool_name'] == 'review_parameters'
        has_output = len(last_call['output']) > 0

        print(f"\n✅ 工具名称正确: {is_review_params}")
        print(f"✅ 输出非空: {has_output}")

        return is_review_params and has_output
    else:
        print("❌ 没有记录到工具调用")
        return False


def test_fallback_mechanism():
    """测试兜底机制（模拟 Agent 未输出的情况）"""
    print("\n" + "=" * 60)
    print("测试 3: 兜底机制")
    print("=" * 60)

    from response_validator import get_validator

    # 获取 validator 实例
    validator = get_validator(debug=True)
    validator.clear_tool_history()

    # 模拟工具调用
    tool = ReviewParametersTool()
    tool_output = tool._run(
        current_params={'country_name': '美国', 'target_count': 40},
        product_name="测试商品",
        target_count=40
    )

    # 模拟 Agent 的兜底逻辑
    # 检查 validator 中是否有 review_parameters 调用
    found_output = None
    if validator.last_tool_calls:
        for tool_call in reversed(validator.last_tool_calls):
            if tool_call['tool_name'] == 'review_parameters':
                found_output = tool_call['output']
                print("✅ 兜底机制成功找到 review_parameters 输出")
                break

    if found_output:
        print(f"✅ 输出长度: {len(found_output)} 字符")
        print(f"✅ 输出内容包含关键信息: {'当前筛选参数摘要' in found_output}")
        return True
    else:
        print("❌ 兜底机制未能找到输出")
        return False


if __name__ == "__main__":
    print("\n🧪 开始测试 review_parameters 修复方案\n")

    results = []

    # 运行测试
    results.append(("工具输出", test_review_parameters_output()))
    results.append(("工具追踪", test_validator_tracking()))
    results.append(("兜底机制", test_fallback_mechanism()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {test_name}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n🎉 所有测试通过！修复方案有效。")
    else:
        print("\n⚠️ 部分测试失败，需要进一步调试。")

    print("\n说明:")
    print("1. 工具输出包含了明确的提示标记，提醒 Agent 必须输出")
    print("2. 工具调用会被记录到 validator，用于兜底")
    print("3. 如果 Agent 未输出，agent.run() 会从 validator 中提取并返回")
    print("4. 清理函数会移除内部标记，保持用户界面整洁")
