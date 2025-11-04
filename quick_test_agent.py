"""
快速测试 Agent 的 URL 访问功能
"""

# CRITICAL: 必须在最开始就应用 nest_asyncio
import nest_asyncio
nest_asyncio.apply()

import sys
import traceback

print("=" * 80)
print("🧪 快速测试 Agent URL 访问")
print("=" * 80)

# 步骤 1: 导入模块
print("\n[1] 导入模块...")
try:
    from main import initialize_playwright
    from agent import create_agent
    print("✅ 模块导入成功")
except Exception as e:
    print(f"❌ 模块导入失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 步骤 2: 初始化 Playwright
print("\n[2] 初始化 Playwright...")
try:
    initialize_playwright()
    print("✅ Playwright 初始化成功")
except Exception as e:
    print(f"❌ Playwright 初始化失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 步骤 3: 创建 Agent
print("\n[3] 创建 Agent...")
try:
    agent = create_agent()
    print("✅ Agent 创建成功")
except Exception as e:
    print(f"❌ Agent 创建失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# 步骤 4: 测试简单的 URL 访问
print("\n[4] 测试 GetMaxPageTool...")
print("提示：这会触发 navigate_to_url()")
print()

try:
    from agent_tools import GetMaxPageTool
    tool = GetMaxPageTool()

    test_url = "https://www.fastmoss.com/zh/influencer/search?region=US&sale_category_l3=855952&follower=100000,300000"

    print(f"测试 URL: {test_url}")
    print("正在调用工具...")

    result = tool._run(url=test_url)

    print(f"\n工具返回:\n{result}")

    if "✅" in result:
        print("\n🎉 测试成功！Agent 可以正常访问 URL")
        sys.exit(0)
    else:
        print("\n⚠️ 工具执行了但可能有问题")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    print("\n详细错误:")
    traceback.print_exc()
    sys.exit(1)
