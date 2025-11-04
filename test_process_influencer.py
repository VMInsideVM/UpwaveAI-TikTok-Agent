"""
测试批量获取达人详细数据功能

测试步骤：
1. 创建一个小的测试 JSON 文件（5个达人）
2. 调用 /process_influencer_list API
3. 验证结果

使用方法：
1. 确保 Chrome 运行在 CDP 端口 9224
2. 启动 Playwright API 服务：python playwright_api.py
3. 运行此测试：python test_process_influencer.py
"""

import requests
import json
import os
from datetime import datetime

# API 配置
API_BASE_URL = "http://127.0.0.1:8000"

def create_test_json():
    """创建测试用的 JSON 文件"""
    test_data = {
        "product_name": "测试商品",
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "total_count": 5,
        "data_row_keys": [
            "7288986759428588590",  # 这是一个真实的达人 ID
            "7170541438504420394",
            "6951979291350795269",
            "6829673971714688006",
            "7344820820893000743"
        ]
    }

    # 确保 output 目录存在
    os.makedirs("output", exist_ok=True)

    # 保存测试文件
    filepath = "output/test_influencer_list.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 测试 JSON 文件已创建: {filepath}")
    print(f"   包含 {test_data['total_count']} 个达人 ID")
    print()

    return filepath


def check_api_health():
    """检查 API 服务是否运行"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API 服务状态: {data.get('status')}")
            print(f"   Playwright 初始化: {data.get('playwright_initialized')}")
            print()
            return data.get('playwright_initialized', False)
        else:
            print(f"❌ API 服务响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到 API 服务 ({API_BASE_URL})")
        print("   请确保 Playwright API 服务已启动：python playwright_api.py")
        return False
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False


def test_process_influencer_list(json_file_path, cache_days=3):
    """测试批量处理达人列表"""
    print(f"📊 开始测试批量处理...")
    print(f"   - 文件: {json_file_path}")
    print(f"   - 缓存有效期: {cache_days} 天")
    print()

    try:
        # 调用 API
        print("🔄 正在调用 API...")
        response = requests.post(
            f"{API_BASE_URL}/process_influencer_list",
            json={
                "json_file_path": json_file_path,
                "cache_days": cache_days
            },
            timeout=600  # 10 分钟超时
        )

        # 检查响应
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ API 调用成功!")
            print(f"\n📊 处理结果:")
            print(f"   • 总达人数: {result.get('total_count', 0)}")
            print(f"   • 使用缓存: {result.get('cached_count', 0)}")
            print(f"   • 重新获取: {result.get('fetched_count', 0)}")
            print(f"   • 失败: {result.get('failed_count', 0)}")
            print(f"   • 耗时: {result.get('elapsed_time', '未知')}")

            # 显示失败的 ID
            failed_ids = result.get('failed_ids', [])
            if failed_ids:
                print(f"\n⚠️ 失败的达人 ID:")
                for fid in failed_ids:
                    print(f"   - {fid}")

            # 验证文件是否生成
            print(f"\n📁 验证文件生成...")
            influencer_dir = "influencer"
            if os.path.exists(influencer_dir):
                files = os.listdir(influencer_dir)
                print(f"   influencer 目录包含 {len(files)} 个文件")

                # 检查测试的几个 ID 是否生成了文件
                test_ids = ["7288986759428588590", "7170541438504420394"]
                for tid in test_ids:
                    filepath = os.path.join(influencer_dir, f"{tid}.json")
                    if os.path.exists(filepath):
                        print(f"   ✓ {tid}.json 已生成")
                        # 读取文件验证内容
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            print(f"      - capture_time: {data.get('capture_time')}")
                            print(f"      - total_requests: {data.get('total_requests')}")
                    else:
                        print(f"   ✗ {tid}.json 未生成")

            return True

        else:
            print(f"\n❌ API 调用失败")
            print(f"   状态码: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   错误信息: {error_data.get('detail', '未知错误')}")
            except:
                print(f"   响应内容: {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        print(f"\n⏰ API 请求超时（600秒）")
        print("   这可能是正常的，如果正在处理大量达人")
        return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试流程"""
    print("=" * 70)
    print("测试：批量获取达人详细数据功能")
    print("=" * 70)
    print()

    # 步骤 1: 检查 API 服务
    print("步骤 1: 检查 API 服务状态")
    print("-" * 70)
    if not check_api_health():
        print("\n❌ 测试终止：API 服务未就绪")
        print("\n请按以下步骤启动服务：")
        print("1. 启动 Chrome: chrome.exe --remote-debugging-port=9224")
        print("2. 启动 API: python playwright_api.py")
        return

    # 步骤 2: 创建测试文件
    print("步骤 2: 创建测试 JSON 文件")
    print("-" * 70)
    test_file = create_test_json()

    # 步骤 3: 执行测试
    print("步骤 3: 执行批量处理测试")
    print("-" * 70)
    success = test_process_influencer_list(test_file, cache_days=3)

    # 总结
    print()
    print("=" * 70)
    if success:
        print("✅ 测试完成！")
        print()
        print("💡 提示：")
        print("   - 第一次运行会爬取所有达人（每个约 5-7 秒）")
        print("   - 再次运行会使用缓存（瞬间完成）")
        print("   - 修改 cache_days 参数可以控制缓存有效期")
        print("   - 检查 influencer/ 目录查看生成的 JSON 文件")
    else:
        print("❌ 测试失败")
        print()
        print("💡 排查建议：")
        print("   1. 检查 Chrome 是否在 CDP 端口 9224 运行")
        print("   2. 检查 Playwright API 服务是否正常启动")
        print("   3. 查看 API 服务的日志输出")
        print("   4. 确保网络连接正常")
    print("=" * 70)


if __name__ == "__main__":
    main()
