"""
直接测试 API 端点

这个脚本直接测试各个 API 端点，不依赖文件。
用于验证 API 服务本身是否正常工作。
"""

import requests
import json

API_BASE_URL = "http://127.0.0.1:8000"


def test_health():
    """测试健康检查端点"""
    print("\n1️⃣ 测试健康检查端点 GET /health")
    print("-" * 60)
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 状态: {data.get('status')}")
            print(f"   Playwright 初始化: {data.get('playwright_initialized')}")
            return data.get('playwright_initialized', False)
        else:
            print(f"❌ 失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_max_page():
    """测试获取最大页数（需要先导航）"""
    print("\n2️⃣ 测试获取最大页数 GET /max_page")
    print("-" * 60)
    print("⚠️ 跳过（需要先调用 /navigate）")


def test_navigate():
    """测试导航端点"""
    print("\n3️⃣ 测试导航端点 POST /navigate")
    print("-" * 60)
    test_url = "https://www.fastmoss.com/zh/influencer/detail/7288986759428588590"
    try:
        response = requests.post(
            f"{API_BASE_URL}/navigate",
            json={"url": test_url, "wait_for_load": True},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 导航成功")
            print(f"   URL: {data.get('url')}")
            return True
        else:
            print(f"❌ 失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_current_url():
    """测试获取当前 URL"""
    print("\n4️⃣ 测试获取当前 URL GET /current_url")
    print("-" * 60)
    try:
        response = requests.get(f"{API_BASE_URL}/current_url", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 当前 URL: {data.get('url')}")
            return True
        else:
            print(f"❌ 失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def test_scrape():
    """测试爬取端点（获取 data-row-keys）"""
    print("\n5️⃣ 测试爬取端点 POST /scrape")
    print("-" * 60)
    print("⚠️ 跳过（会生成文件，耗时较长）")


def test_process_influencer_list():
    """测试批量处理端点"""
    print("\n6️⃣ 测试批量处理端点 POST /process_influencer_list")
    print("-" * 60)
    print("⚠️ 跳过（需要先创建测试文件）")
    print("   请运行: python test_process_influencer.py")


def test_api_docs():
    """测试 API 文档"""
    print("\n7️⃣ 测试 API 文档")
    print("-" * 60)
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print(f"✅ API 文档可访问")
            print(f"   URL: {API_BASE_URL}/docs")
            return True
        else:
            print(f"❌ 失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False


def main():
    """主测试流程"""
    print("=" * 60)
    print("🧪 直接测试 API 端点")
    print("=" * 60)

    # 测试健康检查
    playwright_ready = test_health()

    if not playwright_ready:
        print("\n❌ Playwright 未初始化，无法继续测试")
        print("\n请确保:")
        print("1. Chrome 运行在 CDP 端口 9224")
        print("   chrome.exe --remote-debugging-port=9224")
        print("2. Playwright API 服务已启动")
        print("   python playwright_api.py")
        return

    # 测试导航
    test_navigate()

    # 测试获取当前 URL
    test_current_url()

    # 测试 API 文档
    test_api_docs()

    # 其他测试（跳过）
    test_max_page()
    test_scrape()
    test_process_influencer_list()

    print()
    print("=" * 60)
    print("✅ API 基础功能测试完成")
    print()
    print("💡 下一步:")
    print("   • 运行完整测试: python test_process_influencer.py")
    print("   • 快速测试: python test_quick.py")
    print("   • 查看 API 文档: http://127.0.0.1:8000/docs")
    print("=" * 60)


if __name__ == "__main__":
    main()
