"""
导航问题诊断脚本
帮助排查 navigate_to_url 失败的原因
"""

# 解决 asyncio 和同步 Playwright 的冲突
import nest_asyncio
nest_asyncio.apply()

from main import initialize_playwright, navigate_to_url
import traceback
import time

def diagnose_navigation_issue(test_url):
    """
    诊断导航到指定URL的问题

    Args:
        test_url: 要测试的URL
    """
    print("=" * 80)
    print("🔍 开始诊断导航问题...")
    print("=" * 80)

    # 步骤 1: 测试 Playwright 初始化
    print("\n[步骤 1] 测试 Playwright 初始化...")
    try:
        initialize_playwright()
        print("✅ Playwright 初始化成功")
    except Exception as e:
        print(f"❌ Playwright 初始化失败: {e}")
        print("\n可能原因:")
        print("1. Chrome 没有在 CDP 端口 9224 上运行")
        print("2. 启动命令: chrome.exe --remote-debugging-port=9224")
        traceback.print_exc()
        return

    # 步骤 2: 测试页面对象
    print("\n[步骤 2] 检查页面对象...")
    from main import page, browser, context

    if page is None:
        print("❌ 页面对象为 None")
        return
    else:
        print(f"✅ 页面对象存在")
        print(f"   - Browser: {browser is not None}")
        print(f"   - Context: {context is not None}")

    # 步骤 3: 获取当前页面URL
    print("\n[步骤 3] 获取当前页面状态...")
    try:
        current_url = page.url
        print(f"✅ 当前页面URL: {current_url}")
    except Exception as e:
        print(f"❌ 无法获取当前URL: {e}")
        traceback.print_exc()

    # 步骤 4: 测试简单导航
    print("\n[步骤 4] 测试导航到 Google...")
    try:
        page.goto("https://www.google.com", timeout=30000)
        time.sleep(2)
        print(f"✅ 成功导航到 Google")
        print(f"   当前URL: {page.url}")
    except Exception as e:
        print(f"❌ 导航到 Google 失败: {e}")
        traceback.print_exc()
        return

    # 步骤 5: 测试目标URL
    print(f"\n[步骤 5] 测试导航到目标URL...")
    print(f"目标URL: {test_url}")

    try:
        print("正在导航...")
        success = navigate_to_url(test_url, wait_for_load=True)

        if success:
            print(f"✅ 导航成功!")
            print(f"   最终URL: {page.url}")

            # 检查页面内容
            print("\n[步骤 6] 检查页面内容...")
            try:
                # 等待表格容器出现
                table = page.query_selector('.ant-table-container')
                if table:
                    print("✅ 找到表格容器")
                else:
                    print("⚠️ 未找到表格容器 (.ant-table-container)")

                # 检查分页
                pagination = page.query_selector('.ant-pagination')
                if pagination:
                    print("✅ 找到分页元素")
                else:
                    print("⚠️ 未找到分页元素 (.ant-pagination)")

            except Exception as e:
                print(f"⚠️ 检查页面元素时出错: {e}")
        else:
            print(f"❌ 导航失败")
            print(f"   当前URL: {page.url}")

    except Exception as e:
        print(f"❌ 导航过程中出现异常: {e}")
        print("\n详细错误信息:")
        traceback.print_exc()

    # 步骤 7: 提供建议
    print("\n" + "=" * 80)
    print("💡 建议检查项:")
    print("=" * 80)
    print("1. URL 是否包含完整的分类后缀（category_id 参数）")
    print("2. 筛选条件是否过于严格导致没有结果")
    print("3. 网络连接是否正常")
    print("4. fastmoss.com 网站是否可以正常访问")
    print("5. 是否需要登录才能查看数据")
    print()


if __name__ == "__main__":
    # 测试一个基本的URL（美国地区，美妆分类）
    test_url = "https://www.fastmoss.com/zh/influencer/search?region=US&category_id=4"

    print("请提供要诊断的URL（留空使用默认URL）:")
    user_input = input().strip()
    if user_input:
        test_url = user_input

    diagnose_navigation_issue(test_url)
