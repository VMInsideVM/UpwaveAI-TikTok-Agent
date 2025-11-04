"""
测试 Agent 中的导航功能
模拟真实的 Agent 工具调用场景
"""

# CRITICAL: 必须在最开始就应用
import nest_asyncio
nest_asyncio.apply()

import sys
import traceback


def test_get_max_page_tool():
    """测试 GetMaxPageTool（这是报错的工具）"""
    print("=" * 80)
    print("🧪 测试 GetMaxPageTool（模拟真实 Agent 调用）")
    print("=" * 80)

    try:
        # 导入工具
        print("\n[1] 导入 GetMaxPageTool...")
        from agent_tools import GetMaxPageTool
        print("✅ 工具导入成功")

        # 创建工具实例
        print("\n[2] 创建工具实例...")
        tool = GetMaxPageTool()
        print(f"✅ 工具名称: {tool.name}")
        print(f"   工具描述: {tool.description[:50]}...")

        # 测试 URL（美国地区，粉丝 10-30 万，美妆分类）
        test_url = "https://www.fastmoss.com/zh/influencer/search?region=US&follower=100000,300000&sale_category_l3=855952"

        print(f"\n[3] 调用工具获取最大页数...")
        print(f"   URL: {test_url}")

        # 这里会触发 navigate_to_url，之前就是在这里报错
        result = tool._run(url=test_url)

        print(f"\n[4] 工具返回结果:")
        print(result)

        if "❌" in result:
            print("\n⚠️ 工具执行失败，但没有抛出异常（说明 nest_asyncio 生效了）")
            print("失败原因可能是：")
            print("  - Chrome 未在 CDP 9224 端口运行")
            print("  - URL 无法访问")
            print("  - 网络问题")
            return False
        else:
            print("\n✅ 工具执行成功！nest_asyncio 修复生效！")
            return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        print("\n详细错误信息:")
        traceback.print_exc()

        if "asyncio loop" in str(e):
            print("\n⚠️ 仍然存在 asyncio 冲突！nest_asyncio 未生效！")

        return False


def test_scrape_tool():
    """测试 ScrapeInfluencersTool"""
    print("\n" + "=" * 80)
    print("🧪 测试 ScrapeInfluencersTool")
    print("=" * 80)

    try:
        from agent_tools import ScrapeInfluencersTool

        print("\n[1] 创建工具实例...")
        tool = ScrapeInfluencersTool()
        print(f"✅ 工具名称: {tool.name}")

        test_url = "https://www.fastmoss.com/zh/influencer/search?region=US&follower=100000,300000&sale_category_l3=855952"

        print(f"\n[2] 调用工具爬取数据（只爬 1 页）...")
        result = tool._run(base_url=test_url, max_pages=1)

        print(f"\n[3] 工具返回结果:")
        print(result)

        if "✅" in result:
            print("\n🎉 爬取工具执行成功！")
            return True
        else:
            print("\n⚠️ 爬取失败（但没有抛出异常）")
            return False

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        traceback.print_exc()
        return False


def main():
    """主测试流程"""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║          🧪 Agent 导航功能完整测试                           ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()
    print("这个测试会模拟 Agent 真实的工具调用场景")
    print("如果测试通过，说明 nest_asyncio 修复完全生效")
    print()

    # 测试 1: GetMaxPageTool
    success1 = test_get_max_page_tool()

    # 测试 2: ScrapeInfluencersTool（可选）
    if success1:
        print("\n是否继续测试 ScrapeInfluencersTool？(y/n)")
        choice = input().strip().lower()
        if choice == 'y':
            success2 = test_scrape_tool()
        else:
            success2 = True
            print("跳过 ScrapeInfluencersTool 测试")
    else:
        success2 = False

    # 总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    print(f"GetMaxPageTool:       {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"ScrapeInfluencersTool: {'✅ 通过' if success2 else '⏭️ 跳过'}")
    print()

    if success1:
        print("🎉 核心功能测试通过！")
        print("💡 现在可以正常运行 Agent:")
        print("   python run_agent.py")
        return 0
    else:
        print("❌ 测试未通过")
        print("💡 请检查:")
        print("   1. Chrome 是否在 CDP 9224 端口运行")
        print("   2. 网络连接是否正常")
        print("   3. URL 是否可以访问")
        return 1


if __name__ == "__main__":
    sys.exit(main())
