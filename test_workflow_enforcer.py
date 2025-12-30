"""
测试 WorkflowEnforcer 修复效果
模拟原始问题场景：Agent 调用 build_search_url 后返回 null
"""

import os
from dotenv import load_dotenv
from agent import TikTokInfluencerAgent

# 加载环境变量
load_dotenv()


def test_workflow_enforcement():
    """测试工作流强制执行"""
    print("=" * 80)
    print("测试场景：Agent 调用 build_search_url 后是否会强制调用 review_parameters")
    print("=" * 80)
    print()

    # 创建 Agent 实例
    print("📝 创建 Agent 实例...")
    agent = TikTokInfluencerAgent()
    print("✅ Agent 创建成功")
    print()

    # 测试用例：模拟 LangSmith trace 中的用户输入
    test_input = "美国地区Miss Dior香水，2个达人，10w-30w粉丝"

    print(f"🧪 测试输入: {test_input}")
    print()
    print("=" * 80)
    print("开始处理...")
    print("=" * 80)
    print()

    # 运行 Agent
    response = agent.run(test_input)

    print()
    print("=" * 80)
    print("Agent 响应:")
    print("=" * 80)
    print(response)
    print()

    # 验证结果
    print("=" * 80)
    print("验证结果:")
    print("=" * 80)

    # 检查响应是否包含参数摘要
    if "参数摘要" in response or "筛选参数" in response:
        print("✅ 成功：响应包含参数摘要，工作流强制执行有效！")
    elif response == "抱歉,我无法处理你的请求。Agent 没有返回有效响应。":
        print("❌ 失败：Agent 仍然返回 null，工作流强制执行未生效")
    else:
        print(f"⚠️ 未知结果：响应内容为 '{response[:100]}...'")

    # 检查 current_params 是否正确存储
    print()
    print("当前参数存储状态:")
    print(f"  - product_name: {agent.current_params.get('product_name', 'N/A')}")
    print(f"  - country_name: {agent.current_params.get('country_name', 'N/A')}")
    print(f"  - target_count: {agent.current_params.get('target_count', 'N/A')}")
    print(f"  - category_info: {agent.current_params.get('category_info', {}).get('category_name', 'N/A')}")

    # 检查工作流强制执行器状态
    violation_status = agent.workflow_enforcer.get_violation_status()
    print()
    print("工作流强制执行器状态:")
    print(f"  - expect_review_parameters: {violation_status['expect_review_parameters']}")
    print(f"  - last_tool_name: {violation_status['last_tool_name']}")
    print(f"  - tool_call_count: {violation_status['tool_call_count']}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_workflow_enforcement()
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
