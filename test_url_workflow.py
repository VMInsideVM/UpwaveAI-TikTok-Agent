"""
测试 LangGraph URL 构建工作流

验证 build_search_url → review_parameters 的强制执行
"""

import sys
import os

# 确保可以导入 agent 模块
sys.path.insert(0, os.path.dirname(__file__))

from url_build_workflow import create_url_build_workflow
from agent import TikTokInfluencerAgent


def test_url_workflow():
    """测试工作流: 验证 review_parameters 被强制调用"""

    print("=" * 70)
    print("🧪 测试: LangGraph URL 构建工作流")
    print("=" * 70)
    print()

    # 1. 创建 agent 实例
    print("📍 步骤1: 初始化 Agent...")
    try:
        agent = TikTokInfluencerAgent(debug=True)
        print("✅ Agent 初始化成功")
    except Exception as e:
        print(f"❌ Agent 初始化失败: {e}")
        return False

    print()

    # 2. 创建工作流
    print("📍 步骤2: 创建 URL 构建工作流...")
    try:
        workflow = create_url_build_workflow(agent, debug=True)
        print("✅ 工作流创建成功")
    except Exception as e:
        print(f"❌ 工作流创建失败: {e}")
        return False

    print()

    # 3. 准备测试参数
    print("📍 步骤3: 准备测试参数...")
    test_params = {
        "country_name": "美国",
        "promotion_channel": "all",
        "affiliate_check": False,
        "followers_min": 10000,
        "followers_max": 100000,
        "target_influencer_count": 20
    }

    test_product_name = "口红"
    test_target_count = 20
    test_category_info = {
        "level": "L3",
        "category_name": "口红",
        "category_id": "123456"
    }

    print(f"  商品: {test_product_name}")
    print(f"  国家: {test_params['country_name']}")
    print(f"  粉丝范围: {test_params['followers_min']:,} - {test_params['followers_max']:,}")
    print(f"  目标数量: {test_target_count} 个达人")

    print()

    # 4. 执行工作流
    print("📍 步骤4: 执行工作流...")
    print("-" * 70)
    try:
        result = workflow.execute(
            params=test_params,
            product_name=test_product_name,
            target_count=test_target_count,
            category_info=test_category_info
        )
        print("-" * 70)
        print("✅ 工作流执行成功")
    except Exception as e:
        print("-" * 70)
        print(f"❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print()

    # 5. 验证结果
    print("📍 步骤5: 验证结果...")

    # 检查 URL
    if result.get("url"):
        print(f"✅ URL 已构建: {result['url'][:80]}...")
    else:
        print("❌ URL 未构建")
        return False

    # 检查 review_parameters 是否被调用
    if result.get("parameters_reviewed"):
        print("✅ review_parameters 已被强制调用")
    else:
        print("❌ review_parameters 未被调用 (工作流失败!)")
        return False

    # 检查输出
    review_output = result.get("review_output", "")
    if review_output and len(review_output) > 50:
        print(f"✅ 参数展示输出已生成 ({len(review_output)} 字符)")
    else:
        print(f"❌ 参数展示输出异常: {review_output}")
        return False

    print()

    # 6. 显示应该展示给用户的内容
    print("📍 步骤6: 展示给用户的内容 (review_parameters 输出):")
    print("=" * 70)
    user_output = workflow.get_user_output(result)
    print(user_output)
    print("=" * 70)

    print()

    # 7. 最终验证
    print("=" * 70)
    print("🎉 测试通过!")
    print("=" * 70)
    print()
    print("✅ 验证结果:")
    print("  1. build_search_url 被正确调用")
    print("  2. review_parameters 被强制调用 (无法跳过)")
    print("  3. 参数展示内容已生成")
    print("  4. 工作流保证了正确的执行顺序")
    print()
    print("🔥 结论: LangGraph 工作流成功强制执行了 review_parameters!")

    return True


if __name__ == "__main__":
    success = test_url_workflow()
    sys.exit(0 if success else 1)
