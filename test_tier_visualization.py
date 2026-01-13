"""
测试 Tier 可视化更新

验证所有 tier 达人都能获得完整的数据可视化分析
"""

import sys
import inspect
from report_agent import TikTokInfluencerReportAgent

def test_tier_methods():
    """测试 tier 相关方法是否正确配置"""
    print("=" * 60)
    print("测试 Tier 可视化系统")
    print("=" * 60)

    agent = TikTokInfluencerReportAgent()

    # 检查是否存在废弃的方法
    obsolete_methods = [
        '_generate_medium_analysis',
        '_generate_brief_analysis',
        '_generate_simple_recommendation',
        '_translate_dim'
    ]

    print("\n[1] 检查废弃方法是否已删除:")
    all_removed = True
    for method_name in obsolete_methods:
        if hasattr(agent, method_name):
            print(f"  FAIL {method_name} 仍然存在 (应该被删除)")
            all_removed = False
        else:
            print(f"  OK {method_name} 已删除")

    # 检查必需的方法是否存在
    print("\n[2] 检查必需方法是否存在:")
    required_methods = [
        '_generate_detailed_analysis',
        '_generate_full_analysis'
    ]

    all_exist = True
    for method_name in required_methods:
        if hasattr(agent, method_name):
            method = getattr(agent, method_name)
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())
            print(f"  OK {method_name} 存在")
            print(f"    参数: {params}")

            # 检查 _generate_full_analysis 是否有 tier 参数
            if method_name == '_generate_full_analysis':
                if 'tier' in params:
                    print(f"    OK tier 参数已添加")
                else:
                    print(f"    FAIL 缺少 tier 参数")
                    all_exist = False

            # 检查 _generate_detailed_analysis 是否有 tier 参数
            if method_name == '_generate_detailed_analysis':
                if 'tier' in params:
                    print(f"    OK tier 参数已添加")
                else:
                    print(f"    FAIL 缺少 tier 参数")
                    all_exist = False
        else:
            print(f"  FAIL {method_name} 不存在")
            all_exist = False

    # 测试推荐等级逻辑
    print("\n[3] 测试推荐等级逻辑:")
    test_cases = [
        {'tier': 1, 'score': 85, 'expected_keyword': '首选'},
        {'tier': 2, 'score': 85, 'expected_keyword': '备选'},
        {'tier': 3, 'score': 75, 'expected_keyword': '候补'},
    ]

    logic_correct = True
    for case in test_cases:
        tier = case['tier']
        score = case['score']
        expected = case['expected_keyword']

        # 创建模拟的达人数据
        mock_inf = {
            'total_score': score,
            'dimension_scores': {},
            'charts': [],
            'strengths': ['测试优势1', '测试优势2'],
            'weaknesses': ['测试劣势1']
        }

        try:
            result = agent._generate_detailed_analysis(mock_inf, tier)

            if expected in result:
                print(f"  OK Tier {tier} (得分{score}) → 包含 '{expected}'")
            else:
                print(f"  FAIL Tier {tier} (得分{score}) → 未找到 '{expected}'")
                logic_correct = False
        except Exception as e:
            print(f"  FAIL Tier {tier} 测试失败: {e}")
            logic_correct = False

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if all_removed:
        print("OK 所有废弃方法已删除")
    else:
        print("FAIL 部分废弃方法仍存在")

    if all_exist:
        print("OK 所有必需方法已正确配置")
    else:
        print("FAIL 部分必需方法缺失或配置错误")

    if logic_correct:
        print("OK 推荐等级逻辑工作正常")
    else:
        print("FAIL 推荐等级逻辑存在问题")

    print()
    if all_removed and all_exist and logic_correct:
        print("[SUCCESS] 所有测试通过！Tier 可视化系统更新成功！")
        return True
    else:
        print("[WARNING]  部分测试失败，需要进一步检查")
        return False

def test_code_structure():
    """测试代码结构"""
    print("\n" + "=" * 60)
    print("代码结构分析")
    print("=" * 60)

    with open('report_agent.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查关键代码模式
    checks = [
        ('_generate_full_analysis(inf, dim_scores, charts, tier)',
         'OK _generate_full_analysis 接受 tier 参数'),
        ('return self._generate_full_analysis(inf, dim_scores, charts, tier)',
         'OK _generate_detailed_analysis 传递 tier 参数'),
        ('⭐️ 强烈推荐 (首选)',
         'OK Tier 1 推荐等级标签存在'),
        ('强烈推荐 (备选)',
         'OK Tier 2 推荐等级标签存在'),
        ('可考虑 (候补)',
         'OK Tier 3 推荐等级标签存在'),
    ]

    all_found = True
    for pattern, message in checks:
        if pattern in content:
            print(f"  {message}")
        else:
            print(f"  FAIL 未找到: {pattern}")
            all_found = False

    return all_found

if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 12 + "Tier 可视化系统测试套件" + " " * 12 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    try:
        methods_ok = test_tier_methods()
        structure_ok = test_code_structure()

        if methods_ok and structure_ok:
            print("\n[PASS] 所有验证通过！系统已正确更新。")
            sys.exit(0)
        else:
            print("\n[FAIL] 部分验证失败，请检查代码。")
            sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
