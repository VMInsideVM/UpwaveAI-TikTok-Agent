"""
快速测试脚本 - 只测试单个达人

这个脚本会测试获取单个达人的详细数据，耗时约 5-10 秒。
适合用于快速验证功能是否正常工作。
"""

import requests
import json
import os

API_BASE_URL = "http://127.0.0.1:8000"

# 测试用的单个达人 ID
TEST_INFLUENCER_ID = "7288986759428588590"


def test_single_influencer():
    """测试单个达人数据获取"""
    print("🧪 快速测试：获取单个达人详细数据")
    print("=" * 60)
    print()

    # 创建临时测试文件
    test_data = {
        "product_name": "快速测试",
        "timestamp": "20251104_test",
        "total_count": 1,
        "data_row_keys": [TEST_INFLUENCER_ID]
    }

    os.makedirs("output", exist_ok=True)
    test_file = "output/test_single.json"

    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 测试文件已创建: {test_file}")
    print(f"   达人 ID: {TEST_INFLUENCER_ID}")
    print()

    # 调用 API
    print("🔄 正在调用 API...")
    try:
        response = requests.post(
            f"{API_BASE_URL}/process_influencer_list",
            json={
                "json_file_path": test_file,
                "cache_days": 3
            },
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()
            print()
            print("✅ 成功!")
            print()
            print(f"📊 结果:")
            print(f"   • 总数: {result['total_count']}")
            print(f"   • 缓存: {result['cached_count']}")
            print(f"   • 获取: {result['fetched_count']}")
            print(f"   • 失败: {result['failed_count']}")
            print(f"   • 耗时: {result['elapsed_time']}")
            print()

            # 检查文件
            output_file = f"influencer/{TEST_INFLUENCER_ID}.json"
            if os.path.exists(output_file):
                print(f"✅ 文件已生成: {output_file}")
                file_size = os.path.getsize(output_file)
                print(f"   文件大小: {file_size:,} 字节")

                # 读取并显示部分内容
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"   capture_time: {data.get('capture_time')}")
                    print(f"   total_requests: {data.get('total_requests')}")
                    api_responses = data.get('api_responses', {})
                    print(f"   API 响应类型: {list(api_responses.keys())}")
            else:
                print(f"❌ 文件未生成: {output_file}")

        else:
            print(f"❌ API 调用失败: {response.status_code}")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 API 服务")
        print("   请先启动 Playwright API: python playwright_api.py")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)


if __name__ == "__main__":
    test_single_influencer()
