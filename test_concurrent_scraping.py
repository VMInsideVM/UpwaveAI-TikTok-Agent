"""
测试多标签页并发爬取功能

使用方法：
1. 确保 Chrome 在端口 9224 运行
2. 确保 Playwright API 服务已启动（python start_api.py）
3. 运行此脚本：python test_concurrent_scraping.py
"""

import requests
import json
import time
import os
from datetime import datetime

# API 配置
API_BASE_URL = "http://127.0.0.1:8000"

def test_health_check():
    """测试 API 健康状态"""
    print("\n=== 1. 健康检查 ===")
    response = requests.get(f"{API_BASE_URL}/health")
    data = response.json()
    print(f"状态: {data['status']}")
    print(f"Playwright 已初始化: {data['playwright_initialized']}")

    if not data['playwright_initialized']:
        print("❌ Playwright 未初始化，请先启动 API 服务")
        return False

    print("✅ API 服务运行正常")
    return True

def create_test_json():
    """创建测试用的 JSON 文件（包含少量达人 ID）"""
    print("\n=== 2. 创建测试数据 ===")

    # 使用实际的达人 ID（这些需要根据你的实际数据调整）
    test_ids = [
        "7498937853482583070",
        "691772",
        "6786998724234658821"
    ]

    test_data = {
        "product_name": "测试商品",
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "total_count": len(test_ids),
        "data_row_keys": test_ids
    }

    # 创建 output 目录
    os.makedirs("output", exist_ok=True)

    # 保存测试文件
    test_file = f"output/test_concurrent_{test_data['timestamp']}.json"
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 测试文件已创建: {test_file}")
    print(f"   包含 {len(test_ids)} 个达人 ID")

    return test_file

def test_concurrent_scraping(json_file_path, max_concurrent):
    """测试并发爬取"""
    print(f"\n=== 3. 测试并发爬取（并发数: {max_concurrent}）===")

    start_time = time.time()

    response = requests.post(
        f"{API_BASE_URL}/process_influencer_list",
        json={
            "json_file_path": json_file_path,
            "cache_days": 3,
            "max_concurrent": max_concurrent
        }
    )

    elapsed = time.time() - start_time

    if response.status_code == 200:
        data = response.json()

        print(f"\n✅ 爬取完成!")
        print(f"   总数: {data['total_count']}")
        print(f"   使用缓存: {data['cached_count']}")
        print(f"   重新获取: {data['fetched_count']}")
        print(f"   失败: {data['failed_count']}")
        print(f"   耗时: {data['elapsed_time']}")
        print(f"   实际耗时: {elapsed:.2f} 秒")

        if data['failed_count'] > 0:
            print(f"   失败 ID: {data['failed_ids']}")

        return data
    else:
        print(f"❌ 爬取失败: {response.status_code}")
        print(f"   错误: {response.text}")
        return None

def compare_performance():
    """对比串行和并发性能"""
    print("\n=== 4. 性能对比测试 ===")

    # 创建测试数据
    test_file = create_test_json()

    # 测试串行（并发数=1）
    print("\n--- 串行模式（并发数=1）---")
    result_serial = test_concurrent_scraping(test_file, max_concurrent=1)

    # 清空缓存（可选，如果想看真实爬取时间）
    # 注意：这里不清空缓存，因为我们想测试的是并发调度逻辑

    # 测试并发（并发数=3）
    print("\n--- 并发模式（并发数=3）---")
    result_concurrent = test_concurrent_scraping(test_file, max_concurrent=3)

    # 对比结果
    if result_serial and result_concurrent:
        print("\n=== 性能对比结果 ===")
        print(f"串行耗时: {result_serial['elapsed_time']}")
        print(f"并发耗时: {result_concurrent['elapsed_time']}")

        # 计算提升比例
        # 注意：如果都命中缓存，可能看不出差异
        if result_concurrent['fetched_count'] > 0:
            print("\n💡 提示: 如果想看到真实的性能差异，请删除 influencer/ 目录中的缓存文件后重新测试")

def main():
    """主函数"""
    print("=" * 60)
    print("多标签页并发爬取功能测试")
    print("=" * 60)

    # 1. 健康检查
    if not test_health_check():
        return

    # 2. 创建测试数据并测试
    test_file = create_test_json()

    # 3. 测试不同并发数
    print("\n=== 测试不同并发数 ===")

    for concurrent in [1, 3, 5]:
        print(f"\n{'=' * 60}")
        result = test_concurrent_scraping(test_file, max_concurrent=concurrent)
        if result:
            print(f"✅ 并发数 {concurrent} 测试通过")
        else:
            print(f"❌ 并发数 {concurrent} 测试失败")
        time.sleep(2)  # 间隔2秒

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)

    print("\n💡 建议:")
    print("   1. 查看 Playwright API 服务的日志，观察并发标签页的创建/关闭过程")
    print("   2. 使用 Chrome DevTools 查看 CDP 端口，可以看到多个标签页同时工作")
    print("   3. 如果需要测试真实爬取性能，请删除 influencer/ 目录中的缓存文件")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
