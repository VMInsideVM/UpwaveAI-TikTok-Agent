"""
测试 nest_asyncio 修复后的导航功能
"""

# IMPORTANT: 必须在最开始就应用 nest_asyncio
import nest_asyncio
nest_asyncio.apply()

import sys
import traceback

def test_navigation():
    """测试导航功能是否正常"""
    print("=" * 80)
    print("🧪 测试 nest_asyncio 修复后的导航功能")
    print("=" * 80)

    try:
        # 导入修复后的模块
        print("\n[1] 导入模块...")
        import main
        from main import initialize_playwright, navigate_to_url
        print("✅ 模块导入成功（nest_asyncio 已应用）")

        # 初始化 Playwright
        print("\n[2] 初始化 Playwright...")
        initialize_playwright()
        print("✅ Playwright 初始化成功")

        # 测试简单导航
        print("\n[3] 测试导航到百度...")
        test_url = "https://www.baidu.com"
        success = navigate_to_url(test_url, wait_for_load=False)

        if success:
            print(f"✅ 导航成功！当前 URL: {main.page.url}")
        else:
            print("❌ 导航失败")
            return False

        # 测试 fastmoss 导航
        print("\n[4] 测试导航到 fastmoss（美国地区，美妆分类）...")
        fastmoss_url = "https://www.fastmoss.com/zh/influencer/search?region=US&category_id=4"
        success = navigate_to_url(fastmoss_url, wait_for_load=True)

        if success:
            print(f"✅ 导航成功！当前 URL: {main.page.url}")

            # 检查页面元素
            print("\n[5] 检查页面元素...")
            import time
            time.sleep(3)

            table = main.page.query_selector('.ant-table-container')
            if table:
                print("✅ 找到表格容器")
            else:
                print("⚠️ 未找到表格容器（可能需要登录或筛选条件无结果）")

            pagination = main.page.query_selector('.ant-pagination')
            if pagination:
                print("✅ 找到分页元素")
            else:
                print("⚠️ 未找到分页元素")
        else:
            print("❌ 导航失败")
            return False

        print("\n" + "=" * 80)
        print("🎉 所有测试通过！nest_asyncio 修复生效")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        print("\n详细错误信息:")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_navigation()
    sys.exit(0 if success else 1)
