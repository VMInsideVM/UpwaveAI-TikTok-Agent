"""
测试 "-" 值修复

验证修复后的代码能正确处理 JSON 中的 "-" 值
"""

import json
import os
import sys

sys.path.insert(0, '.')

from report_scorer import score_influencer, safe_parse_percentage, safe_parse_number


def test_safe_parse_functions():
    """测试安全解析函数"""
    print("=" * 60)
    print("测试 1: 安全解析函数")
    print("=" * 60)

    # 测试 safe_parse_percentage
    test_cases_pct = [
        ("12.5%", 0.125),
        ("-", 0.0),
        (None, 0.0),
        ("", 0.0),
        ("0%", 0.0),
        ("100%", 1.0),
    ]

    print("\n测试 safe_parse_percentage:")
    all_passed = True
    for value, expected in test_cases_pct:
        result = safe_parse_percentage(value)
        passed = abs(result - expected) < 0.0001
        status = "✓" if passed else "✗"
        print(f"  {status} safe_parse_percentage({repr(value)}) = {result} (期望: {expected})")
        if not passed:
            all_passed = False

    # 测试 safe_parse_number
    test_cases_num = [
        ("123.45", 123.45),
        ("-", 0.0),
        (None, 0.0),
        ("", 0.0),
        (42, 42.0),
    ]

    print("\n测试 safe_parse_number:")
    for value, expected in test_cases_num:
        result = safe_parse_number(value)
        passed = abs(result - expected) < 0.0001
        status = "✓" if passed else "✗"
        print(f"  {status} safe_parse_number({repr(value)}) = {result} (期望: {expected})")
        if not passed:
            all_passed = False

    return all_passed


def test_problematic_influencers():
    """测试之前有问题的达人文件"""
    print("\n" + "=" * 60)
    print("测试 2: 有问题的达人文件")
    print("=" * 60)

    # 这些达人的 JSON 包含 "-" 值
    problematic_uids = [
        '7187240227739206702',  # aweme_pop_rate = "-"
        '6759459884532122629',  # follower_28_count_rate = "-"
        '6652139074722709509',  # region_rank_rate = "-"
    ]

    all_passed = True

    for uid in problematic_uids:
        file_path = f'influencer/{uid}.json'

        if not os.path.exists(file_path):
            print(f"\n跳过 {uid}: 文件不存在")
            continue

        print(f"\n测试达人 {uid}:")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 运行评分
            result = score_influencer(
                data,
                target_audience={'gender': 'all', 'age_range': [], 'regions': []},
                content_fit_score=0.0
            )

            # 检查关键指标
            eng_metrics = result['dimension_scores']['engagement']['metrics']
            sales_metrics = result['dimension_scores']['sales']['metrics']

            follower_count = eng_metrics.get('follower_count')
            interaction_rate = eng_metrics.get('interaction_rate')
            gpm = sales_metrics.get('max_gpm')

            # 验证没有 None 或空值
            issues = []
            if follower_count is None or follower_count == 0:
                issues.append(f"粉丝数异常: {follower_count}")
            if interaction_rate is None or interaction_rate == 'N/A':
                issues.append(f"互动率异常: {interaction_rate}")
            if gpm is None:
                issues.append(f"GPM异常: {gpm}")

            if issues:
                print(f"  ✗ 失败:")
                for issue in issues:
                    print(f"    - {issue}")
                all_passed = False
            else:
                print(f"  ✓ 成功:")
                print(f"    - 粉丝数: {follower_count:,}")
                print(f"    - 互动率: {interaction_rate}")
                print(f"    - GPM: {gpm}")
                print(f"    - 总分: {result['total_score']}")

        except Exception as e:
            print(f"  ✗ 异常: {e}")
            all_passed = False

    return all_passed


def test_normal_influencers():
    """测试正常的达人文件（确保没有破坏原有功能）"""
    print("\n" + "=" * 60)
    print("测试 3: 正常达人文件（回归测试）")
    print("=" * 60)

    # 选择几个正常的达人
    normal_uids = [
        '123374803075383296',
        '2043302',
        '555481',
    ]

    all_passed = True

    for uid in normal_uids:
        file_path = f'influencer/{uid}.json'

        if not os.path.exists(file_path):
            continue

        print(f"\n测试达人 {uid}:")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            result = score_influencer(
                data,
                target_audience={'gender': 'all', 'age_range': [], 'regions': []},
                content_fit_score=0.0
            )

            eng_metrics = result['dimension_scores']['engagement']['metrics']

            follower_count = eng_metrics.get('follower_count')
            interaction_rate = eng_metrics.get('interaction_rate')

            print(f"  ✓ 评分成功")
            print(f"    - 粉丝数: {follower_count:,}")
            print(f"    - 互动率: {interaction_rate}")
            print(f"    - 总分: {result['total_score']}")

        except Exception as e:
            print(f"  ✗ 异常: {e}")
            all_passed = False

    return all_passed


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "修复验证测试套件" + " " * 15 + "║")
    print("╚" + "═" * 58 + "╝")

    results = []

    # 测试 1
    results.append(("安全解析函数", test_safe_parse_functions()))

    # 测试 2
    results.append(("有问题的达人", test_problematic_influencers()))

    # 测试 3
    results.append(("正常达人（回归）", test_normal_influencers()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    all_passed = all(passed for _, passed in results)

    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {name}")

    print()
    if all_passed:
        print("🎉 所有测试通过！修复成功！")
    else:
        print("⚠️  部分测试失败，需要进一步检查")

    print()
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
