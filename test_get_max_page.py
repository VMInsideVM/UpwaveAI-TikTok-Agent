"""
测试 get_max_page_number 工具
"""
from main import initialize_playwright
from agent_tools import GetMaxPageTool

def test_get_max_page():
    """测试获取最大页数功能"""
    print("="*60)
    print("测试 GetMaxPageTool")
    print("="*60)

    # 1. 初始化 Playwright
    print("\n步骤 1: 初始化 Playwright")
    try:
        initialize_playwright()
        print("✅ Playwright 初始化成功")
    except Exception as e:
        print(f"❌ Playwright 初始化失败: {e}")
        print("\n请确保:")
        print("1. Chrome 浏览器已启动")
        print("2. 使用命令: chrome.exe --remote-debugging-port=9224")
        print("3. CDP 端口 9224 已开放")
        return

    # 2. 测试 URL(使用一个简单的搜索条件)
    test_url = "https://www.fastmoss.com/zh/influencer/search?region=US&sale_category_l1=2"
    print(f"\n步骤 2: 测试 URL")
    print(f"URL: {test_url}")

    # 3. 创建工具并执行
    print("\n步骤 3: 执行 GetMaxPageTool")
    tool = GetMaxPageTool()
    result = tool._run(url=test_url)

    print("\n" + "-"*60)
    print("工具返回结果:")
    print(result)
    print("-"*60)

    # 4. 分析结果
    print("\n步骤 4: 分析结果")
    if "✅" in result:
        print("✅ 测试成功! 工具正常工作")
    elif "⚠️" in result:
        print("⚠️ 警告: 找到的数据较少")
    else:
        print("❌ 测试失败: 工具返回错误")
        print("\n可能的原因:")
        print("1. Playwright 未正确初始化")
        print("2. Chrome 浏览器未在 CDP 端口运行")
        print("3. URL 格式不正确或网络问题")
        print("4. 页面元素加载超时")

    print("\n" + "="*60)

if __name__ == "__main__":
    test_get_max_page()
