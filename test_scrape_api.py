"""
测试新的 /scrape API 端点
"""
import requests
import json

# API 基础 URL
API_BASE_URL = "http://127.0.0.1:8000"

def test_scrape_single_url():
    """测试单个 URL 爬取"""
    print("=" * 80)
    print("🧪 测试单个 URL 爬取")
    print("=" * 80)

    # 测试 URL
    test_url = "https://www.fastmoss.com/zh/influencer/search?region=US&follower=100000,300000&sale_category_l3=855952&columnKey=2&field=follower_28d_count_show&order=2,2"

    # 请求数据
    request_data = {
        "urls": [test_url],  # 单个 URL 也要放在列表中
        "max_pages": 2,      # 测试爬取 2 页
        "product_name": "测试商品"
    }

    print(f"\n📊 请求参数:")
    print(f"   - URLs: {len(request_data['urls'])} 个")
    print(f"   - Max Pages: {request_data['max_pages']}")
    print(f"   - Product Name: {request_data['product_name']}")
    print(f"\n   URL: {test_url[:100]}...")

    try:
        print(f"\n🔄 发送请求到 {API_BASE_URL}/scrape ...")
        response = requests.post(
            f"{API_BASE_URL}/scrape",
            json=request_data,
            timeout=300  # 5 分钟超时
        )

        print(f"\n📡 响应状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 请求成功!")
            print(f"\n📋 返回结果:")
            print(f"   - Success: {result.get('success')}")
            print(f"   - 文件路径: {result.get('filepath')}")
            print(f"   - 总数据行: {result.get('total_rows')}")
            print(f"   - URL 数量: {result.get('source_count')}")
            print(f"   - 成功爬取: {result.get('scraped_count')}")
            print(f"   - 消息: {result.get('message')}")

            return True
        else:
            print(f"\n❌ 请求失败!")
            print(f"   错误信息: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"\n❌ 无法连接到 API 服务!")
        print(f"   请确保 API 服务已启动: python start_api.py")
        return False
    except requests.exceptions.Timeout:
        print(f"\n❌ 请求超时!")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_scrape_multiple_urls():
    """测试多个 URL 爬取(多排序维度)"""
    print("\n\n" + "=" * 80)
    print("🧪 测试多个 URL 爬取(多排序维度)")
    print("=" * 80)

    # 基础 URL
    base_url = "https://www.fastmoss.com/zh/influencer/search?region=US&follower=100000,300000&sale_category_l3=855952"

    # 不同排序维度的 URL
    test_urls = [
        f"{base_url}&columnKey=1&field=follower_count&order=2",  # 按粉丝数排序
        f"{base_url}&columnKey=3&field=engagement_rate&order=2",  # 按互动率排序
    ]

    # 请求数据
    request_data = {
        "urls": test_urls,
        "max_pages": 2,
        "product_name": "测试多维度"
    }

    print(f"\n📊 请求参数:")
    print(f"   - URLs: {len(request_data['urls'])} 个")
    print(f"   - Max Pages: {request_data['max_pages']}")
    print(f"   - Product Name: {request_data['product_name']}")

    for idx, url in enumerate(test_urls, 1):
        print(f"\n   URL {idx}: {url[:100]}...")

    try:
        print(f"\n🔄 发送请求到 {API_BASE_URL}/scrape ...")
        response = requests.post(
            f"{API_BASE_URL}/scrape",
            json=request_data,
            timeout=600  # 10 分钟超时(多个 URL 需要更长时间)
        )

        print(f"\n📡 响应状态码: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ 请求成功!")
            print(f"\n📋 返回结果:")
            print(f"   - Success: {result.get('success')}")
            print(f"   - 文件路径: {result.get('filepath')}")
            print(f"   - 总数据行: {result.get('total_rows')} (已去重)")
            print(f"   - URL 数量: {result.get('source_count')}")
            print(f"   - 成功爬取: {result.get('scraped_count')}")
            print(f"   - 消息: {result.get('message')}")

            return True
        else:
            print(f"\n❌ 请求失败!")
            print(f"   错误信息: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"\n❌ 无法连接到 API 服务!")
        print(f"   请确保 API 服务已启动: python start_api.py")
        return False
    except requests.exceptions.Timeout:
        print(f"\n❌ 请求超时!")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_api_health():
    """检查 API 服务健康状态"""
    print("=" * 80)
    print("🔧 检查 API 服务状态")
    print("=" * 80)

    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ API 服务正常运行")
            print(f"   - Status: {result.get('status')}")
            print(f"   - Playwright Initialized: {result.get('playwright_initialized')}")
            print(f"   - Message: {result.get('message')}")
            return result.get('playwright_initialized', False)
        else:
            print(f"\n⚠️ API 服务响应异常")
            return False
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 无法连接到 API 服务!")
        print(f"\n请先启动 API 服务:")
        print(f"   python start_api.py")
        return False
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        return False


def main():
    """主函数"""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║                                                               ║")
    print("║      🧪 测试新的 /scrape API 端点                            ║")
    print("║                                                               ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print("\n")

    # 1. 检查 API 健康状态
    if not check_api_health():
        print("\n❌ API 服务未就绪,测试终止")
        return 1

    # 2. 测试单个 URL
    print("\n")
    success1 = test_scrape_single_url()

    # 3. 询问是否继续测试多个 URL
    if success1:
        print("\n\n" + "=" * 80)
        choice = input("是否继续测试多个 URL (多排序维度)? (y/n): ").strip().lower()
        if choice == 'y':
            success2 = test_scrape_multiple_urls()
        else:
            success2 = True
            print("跳过多 URL 测试")
    else:
        success2 = False

    # 总结
    print("\n\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    print(f"单个 URL 测试:   {'✅ 通过' if success1 else '❌ 失败'}")
    print(f"多个 URL 测试:   {'✅ 通过' if success2 else '⏭️ 跳过' if success1 else '❌ 失败'}")
    print()

    if success1:
        print("🎉 测试通过!")
        print("💡 可以在 output/ 目录查看导出的 Excel 文件")
        return 0
    else:
        print("❌ 测试未通过")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
