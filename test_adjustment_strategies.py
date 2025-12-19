"""
测试和演示 Agent 的调整策略体系
"""

from adjustment_helper import analyze_quantity_gap, suggest_adjustments


def test_quantity_analysis():
    """测试数量分析功能"""
    print("=" * 70)
    print("测试 1: 数量分析（不同缺口程度）")
    print("=" * 70)

    test_cases = [
        (50, 50, "充足"),
        (30, 50, "可接受"),
        (5, 50, "严重不足")
    ]

    for max_pages, user_needs, expected in test_cases:
        print(f"\n场景: 最大页数 {max_pages}, 用户需求 {user_needs} 个达人")
        result = analyze_quantity_gap(max_pages, user_needs)

        print(f"  真实数量: {result['available_real']} 个")
        print(f"  保守估计: {result['available_conservative']} 个")
        print(f"  状态: {result['status']} (预期: {expected})")
        print(f"  提示: {result['message'][:50]}...")


def test_adjustment_suggestions():
    """测试调整建议生成"""
    print("\n" + "=" * 70)
    print("测试 2: 调整建议生成")
    print("=" * 70)

    # 场景 1: 所有限制都有
    print("\n场景 1: 所有限制都设置了（应生成 5 个方案）")
    params_full = {
        'followers_min': 100000,
        'followers_max': 500000,
        'new_followers_min': 10000,
        'new_followers_max': 100000,
        'affiliate_check': True,
        'auth_type': 'verified',
        'account_type': 'personal'
    }

    suggestions = suggest_adjustments(params_full, 50, 10)
    print(f"✅ 生成了 {len(suggestions)} 个调整方案:")
    for sugg in suggestions:
        print(f"  {sugg['priority']}. {sugg['name']}")
        print(f"     预期效果: {sugg['expected_increase']}")

    # 场景 2: 只有粉丝数限制
    print("\n场景 2: 只有粉丝数限制（应生成 1 个方案）")
    params_minimal = {
        'followers_min': 200000,
        'followers_max': 500000
    }

    suggestions = suggest_adjustments(params_minimal, 50, 10)
    print(f"✅ 生成了 {len(suggestions)} 个调整方案:")
    for sugg in suggestions:
        print(f"  {sugg['priority']}. {sugg['name']}")
        print(f"     当前: {sugg['current']}")
        print(f"     调整后: {sugg['new']}")
        print(f"     预期效果: {sugg['expected_increase']}")


def test_shortage_ratio_impact():
    """测试缺口比例对粉丝数调整的影响"""
    print("\n" + "=" * 70)
    print("测试 3: 缺口比例对粉丝数调整幅度的影响")
    print("=" * 70)

    params = {
        'followers_min': 100000,
        'followers_max': 500000
    }

    test_cases = [
        (50, 10, "缺口很大（需要 5 倍）"),
        (50, 30, "缺口适中（需要 1.67 倍）")
    ]

    for target, current, description in test_cases:
        print(f"\n场景: {description}")
        print(f"  目标: {target} 个, 当前: {current} 个")

        suggestions = suggest_adjustments(params, target, current)
        if suggestions:
            sugg = suggestions[0]  # 粉丝数调整是第一个方案
            print(f"  调整建议:")
            print(f"    当前: {sugg['current']}")
            print(f"    调整后: {sugg['new']}")
            print(f"    预期效果: {sugg['expected_increase']}")


def demonstrate_workflow():
    """演示完整的调整流程"""
    print("\n" + "=" * 70)
    print("演示: 完整的达人数量不足处理流程")
    print("=" * 70)

    # 初始参数
    current_params = {
        'country_name': '美国',
        'followers_min': 1000000,
        'followers_max': 2000000,
        'auth_type': 'verified',
        'affiliate_check': False
    }

    user_needs = 50
    max_pages = 3  # 模拟第一次查询结果

    print("\n步骤 1: 用户输入")
    print(f"  商品: 高端手表")
    print(f"  国家: {current_params['country_name']}")
    print(f"  粉丝范围: {current_params['followers_min']:,} - {current_params['followers_max']:,}")
    print(f"  认证要求: 仅认证达人")
    print(f"  需要数量: {user_needs} 个")

    print("\n步骤 2: 检查数量")
    result = analyze_quantity_gap(max_pages, user_needs)
    print(f"  最大页数: {max_pages}")
    print(f"  真实数量: {result['available_real']} 个")
    print(f"  状态: {result['status']}")

    if result['status'] == 'insufficient':
        print("\n步骤 3: 生成调整建议")
        suggestions = suggest_adjustments(
            current_params,
            user_needs,
            result['available_conservative']
        )

        print(f"  共生成 {len(suggestions)} 个方案:\n")
        for i, sugg in enumerate(suggestions, 1):
            print(f"  方案 {i}: {sugg['name']}")
            print(f"    • 当前: {sugg['current']}")
            print(f"    • 调整后: {sugg['new']}")
            print(f"    • 预期效果: {sugg['expected_increase']}")
            print(f"    • 理由: {sugg['reason']}\n")

        print("步骤 4: 用户选择方案 1（放宽粉丝数范围）")

        # 应用方案 1
        changes = suggestions[0]['changes']
        current_params.update(changes)

        print(f"  新粉丝范围: {current_params['followers_min']:,} - {current_params['followers_max']:,}")

        print("\n步骤 5: 重新检查数量")
        max_pages_new = 15  # 模拟调整后的查询结果
        result_new = analyze_quantity_gap(max_pages_new, user_needs)
        print(f"  最大页数: {max_pages_new}")
        print(f"  真实数量: {result_new['available_real']} 个")
        print(f"  状态: {result_new['status']}")

        if result_new['status'] == 'sufficient':
            print("\n✅ 成功！数量充足，可以进入排序选择流程")


def print_summary():
    """打印调整策略摘要"""
    print("\n" + "=" * 70)
    print("调整策略优先级摘要")
    print("=" * 70)

    strategies = [
        ("1", "放宽粉丝数范围", "50-150%", "效果最好"),
        ("2", "移除新增粉丝限制", "20-30%", "包含稳定型达人"),
        ("3", "移除联盟达人限制", "30-50%", "扩大候选池"),
        ("4", "移除认证类型限制", "10-20%", "包含所有认证状态"),
        ("5", "移除账号类型限制", "5-15%", "包含个人和企业")
    ]

    print("\n优先级 | 调整方案             | 预期增加 | 说明")
    print("-" * 70)
    for priority, name, increase, desc in strategies:
        print(f"   {priority}    | {name:20} | {increase:8} | {desc}")

    print("\n不可修改的参数:")
    print("  ❌ 国家/地区 (一旦确定不能修改)")
    print("  ❌ 商品分类 (一旦匹配不能修改)")


if __name__ == "__main__":
    print("\n🧪 Agent 调整策略测试与演示")
    print("=" * 70)

    # 运行所有测试
    test_quantity_analysis()
    test_adjustment_suggestions()
    test_shortage_ratio_impact()
    demonstrate_workflow()
    print_summary()

    print("\n" + "=" * 70)
    print("✅ 所有测试完成！")
    print("=" * 70)
    print("\n详细文档: ADJUSTMENT_STRATEGIES.md")
