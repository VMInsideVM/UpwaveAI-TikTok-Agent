"""
达人筛选条件智能调整助手
当达人数量不足时，生成结构化的调整建议
"""

from typing import Dict, List


def analyze_quantity_gap(max_pages: int, user_needs: int) -> Dict:
    """
    分析数量缺口

    判断标准：
    - 真实达人数 = 最大页数 × 10（每页约10个达人，展示给用户）
    - 保守估计 = 最大页数 × 5（用于内部判断是否需要调整参数）
    - 充足：保守估计 ≥ 用户需求
    - 可接受：保守估计 ≥ 用户需求 × 50%
    - 严重不足：保守估计 < 用户需求 × 50%

    Args:
        max_pages: 最大页数
        user_needs: 用户需要的达人数量

    Returns:
        {
            'status': 'sufficient' | 'acceptable' | 'insufficient',
            'available_real': 真实达人数（max_pages × 10，展示给用户）,
            'available_conservative': 保守估计（max_pages × 5，内部判断用）,
            'message': 给用户的提示信息
        }
    """
    # 真实数量：每页约10个达人（展示给用户）
    available_real = max_pages * 10

    # 保守估计：每页约5个有效达人（用于判断是否需要调整）
    available_conservative = max_pages * 5

    if available_conservative >= user_needs:
        return {
            'status': 'sufficient',
            'available_real': available_real,
            'available_conservative': available_conservative,
            'message': f'✅ 找到足够的达人！约 {available_real} 个可用达人，满足您需要的 {user_needs} 个。'
        }
    elif available_conservative >= user_needs * 0.5:  # 至少有需求的50%
        return {
            'status': 'acceptable',
            'available_real': available_real,
            'available_conservative': available_conservative,
            'message': f'⚠️ 当前找到约 {available_real} 个达人，略少于您需要的 {user_needs} 个。\n\n您可以：\n1. 接受当前数量（约 {available_real} 个）\n2. 调整筛选条件以找到更多达人\n\n请问您想怎么做？'
        }
    else:
        return {
            'status': 'insufficient',
            'available_real': available_real,
            'available_conservative': available_conservative,
            'message': f'❌ 当前只找到约 {available_real} 个达人，远少于您需要的 {user_needs} 个。\n强烈建议调整筛选条件以增加候选达人数量。'
        }


def suggest_adjustments(current_params: Dict, target_count: int, current_count: int) -> List[Dict]:
    """
    生成调整建议

    按优先级生成3-5个调整方案：
    1. 放宽粉丝数范围
    2. 移除新增粉丝数限制
    3. 移除联盟达人限制
    4. 移除认证类型限制
    5. 移除账号类型限制

    Args:
        current_params: 当前筛选参数字典
            例如: {
                'followers_min': 100000,
                'followers_max': 500000,
                'new_followers_min': 10000,
                'affiliate_check': True,
                'auth_type': 'verified',
                ...
            }
        target_count: 用户需要的数量
        current_count: 当前可用数量

    Returns:
        调整方案列表，按优先级排序
    """
    suggestions = []
    shortage_ratio = target_count / max(current_count, 1)  # 缺口比例

    # 优先级1: 粉丝数调整
    if current_params.get('followers_min') or current_params.get('followers_max'):
        min_f = current_params.get('followers_min', 0)
        max_f = current_params.get('followers_max', 10000000)

        # 根据缺口程度决定放宽幅度
        if shortage_ratio > 3:  # 缺口很大（需要3倍以上）
            new_min = min_f // 2  # 下限减半
            new_max = max_f * 3   # 上限扩大3倍
            expected = '预计增加 100-150%'
        else:  # 缺口适中
            new_min = int(min_f * 0.7)  # 下限降低30%
            new_max = int(max_f * 1.5)  # 上限扩大50%
            expected = '预计增加 50-50%'

        suggestions.append({
            'priority': 1,
            'name': '放宽粉丝数范围',
            'changes': {
                'followers_min': new_min,
                'followers_max': new_max
            },
            'current': f'{min_f:,} - {max_f:,}',
            'new': f'{new_min:,} - {new_max:,}',
            'expected_increase': expected,
            'reason': '粉丝数是主要限制因素，放宽范围可显著增加候选达人'
        })

    # 优先级2: 移除新增粉丝限制
    if current_params.get('new_followers_min') or current_params.get('new_followers_max'):
        nf_min = current_params.get('new_followers_min', 0)
        nf_max = current_params.get('new_followers_max', 0)

        suggestions.append({
            'priority': 2,
            'name': '移除新增粉丝数限制',
            'changes': {
                'new_followers_min': None,
                'new_followers_max': None
            },
            'current': f'限制在 {nf_min:,} - {nf_max:,}',
            'new': '无限制',
            'expected_increase': '预计增加 20-30%',
            'reason': '新增粉丝数要求过于严格，移除可包含更多稳定型达人'
        })

    # 优先级3: 移除联盟达人限制
    if current_params.get('affiliate_check'):
        suggestions.append({
            'priority': 3,
            'name': '移除联盟达人限制',
            'changes': {
                'affiliate_check': False
            },
            'current': '仅联盟达人',
            'new': '所有达人（包含非联盟）',
            'expected_increase': '预计增加 30-50%',
            'reason': '扩大候选池，包含更多潜在合作达人'
        })

    # 优先级4: 移除认证限制
    if current_params.get('auth_type') and current_params.get('auth_type') != 'all':
        auth_type = current_params.get('auth_type')
        auth_name = '已认证' if auth_type == 'verified' else '未认证'

        suggestions.append({
            'priority': 4,
            'name': '移除认证类型限制',
            'changes': {
                'auth_type': 'all'
            },
            'current': f'仅{auth_name}达人',
            'new': '不限制认证状态',
            'expected_increase': '预计增加 10-20%',
            'reason': '包含所有认证状态的达人'
        })

    # 优先级5: 移除账号类型限制
    if current_params.get('account_type') and current_params.get('account_type') != 'all':
        account_type = current_params.get('account_type')
        type_name = '个人账号' if account_type == 'personal' else '企业账号'

        suggestions.append({
            'priority': 5,
            'name': '移除账号类型限制',
            'changes': {
                'account_type': 'all'
            },
            'current': f'仅{type_name}',
            'new': '不限制账号类型',
            'expected_increase': '预计增加 5-15%',
            'reason': '包含个人和企业两种账号类型'
        })

    return suggestions


if __name__ == "__main__":
    # 测试代码
    print("="*50)
    print("测试1: 数量分析")
    print("="*50)

    test_cases = [
        (50, 100),   # 数量充足
        (15, 50),    # 数量可接受
        (5, 50)      # 数量严重不足
    ]

    for max_pages, user_needs in test_cases:
        print(f"\n最大页数: {max_pages}, 用户需求: {user_needs}")
        result = analyze_quantity_gap(max_pages, user_needs)
        print(f"状态: {result['status']}")
        print(f"可用数: {result['available']}")
        print(result['message'])

    print("\n" + "="*50)
    print("测试2: 调整建议")
    print("="*50)

    current_params = {
        'followers_min': 100000,
        'followers_max': 500000,
        'new_followers_min': 10000,
        'new_followers_max': 100000,
        'affiliate_check': True,
        'auth_type': 'verified',
        'account_type': 'personal'
    }

    suggestions = suggest_adjustments(current_params, 50, 10)

    print(f"\n当前有 10 个达人，需要 50 个")
    print(f"生成 {len(suggestions)} 个调整方案：\n")

    for sugg in suggestions:
        print(f"方案 {sugg['priority']}: {sugg['name']}")
        print(f"  当前: {sugg['current']}")
        print(f"  调整后: {sugg['new']}")
        print(f"  预期效果: {sugg['expected_increase']}")
        print(f"  理由: {sugg['reason']}\n")
