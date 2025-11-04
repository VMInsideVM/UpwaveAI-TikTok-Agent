"""
测试 Agent 对话记忆功能
验证修复后 agent 能否正确记住上下文
"""

import nest_asyncio
nest_asyncio.apply()

from agent import create_agent

def test_memory():
    """测试对话记忆"""
    print("="*60)
    print("测试 Agent 对话记忆功能")
    print("="*60)

    # 创建 agent
    print("\n1. 创建 Agent...")
    agent = create_agent()

    # 第一轮对话
    print("\n2. 第一轮对话 - 用户提供需求")
    user_input_1 = "我要推广口红，在美国找10个达人，粉丝10万到50万"
    print(f"用户: {user_input_1}")

    response_1 = agent.run(user_input_1)
    print(f"Agent: {response_1[:200]}...")  # 只显示前200字符

    # 检查对话历史
    print(f"\n对话历史长度: {len(agent.chat_history)}")

    # 第二轮对话 - 模拟用户选择排序
    print("\n3. 第二轮对话 - 用户选择排序方式")
    user_input_2 = "1,2"
    print(f"用户: {user_input_2}")

    response_2 = agent.run(user_input_2)
    print(f"Agent: {response_2[:200]}...")

    # 检查对话历史
    print(f"\n对话历史长度: {len(agent.chat_history)}")

    # 验证
    print("\n" + "="*60)
    print("验证结果:")
    print("="*60)

    if len(agent.chat_history) > 2:
        print("✅ 对话历史已保存")
    else:
        print("❌ 对话历史未保存")

    # 检查第二轮回复是否仍然在问基本信息
    if "您要推广什么商品" in response_2 or "目标国家" in response_2:
        print("❌ Agent 忘记了上下文，重新询问基本信息")
    else:
        print("✅ Agent 记住了上下文，继续处理排序选择")

    print("\n测试完成!")

if __name__ == "__main__":
    test_memory()
