"""
测试多标签页并发爬取功能

用途：
1. 验证并发爬取的正确性
2. 对比顺序处理 vs 并发处理的性能差异
3. 测试不同并发数的效果
"""

import requests
import time
import json
import os
from datetime import datetime

# API 配置
API_BASE_URL = "http://127.0.0.1:8000"

def test_concurrent_performance():
    """测试并发爬取性能"""

    print("="*80)
    print("🧪 多窗口并发爬取性能测试")
    print("="*80)
    print()

    # 1. 检查 API 服务是否运行
    print("1️⃣ 检查 API 服务状态...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ API 服务运行正常\n")
        else:
            print("   ❌ API 服务异常")
            return
    except requests.exceptions.ConnectionError:
        print("   ❌ 无法连接到 API 服务")
        print("   请先启动 Playwright API 服务: python playwright_api.py")
        return

    # 2. 查找测试数据文件
    print("2️⃣ 查找测试数据...")
    output_dir = "output"
    if not os.path.exists(output_dir):
        print(f"   ❌ 输出目录不存在: {output_dir}")
        return

    # 查找最新的 JSON 文件
    json_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
    if not json_files:
        print(f"   ❌ 未找到测试数据文件")
        print(f"   请先运行 agent 获取达人列表")
        return

    # 使用最新的文件
    latest_file = max(json_files, key=lambda f: os.path.getmtime(os.path.join(output_dir, f)))
    json_file_path = os.path.join(output_dir, latest_file)

    # 读取文件查看达人数量
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_count = len(data.get("data_row_keys", []))
    product_name = data.get("product_name", "未知")

    print(f"   ✅ 找到测试文件: {latest_file}")
    print(f"   📦 商品: {product_name}")
    print(f"   🎯 达人数: {total_count} 个\n")

    if total_count == 0:
        print("   ❌ 文件中没有达人数据")
        return

    # 为了测试，我们只取前 10 个达人（避免测试时间过长）
    test_count = min(10, total_count)
    test_data = {
        "product_name": product_name,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "total_count": test_count,
        "data_row_keys": data["data_row_keys"][:test_count]
    }

    # 创建测试文件
    test_file_path = os.path.join(output_dir, f"test_concurrent_{test_count}_influencers.json")
    with open(test_file_path, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    print(f"   📝 已创建测试文件（前 {test_count} 个达人）")
    print(f"   📁 {test_file_path}\n")

    # 3. 清除缓存（确保测试准确性）
    print("3️⃣ 清除缓存...")
    influencer_dir = "influencer"
    if os.path.exists(influencer_dir):
        cache_files = [f for f in os.listdir(influencer_dir)
                       if f.endswith('.json') and f.split('.')[0] in test_data["data_row_keys"]]
        for cache_file in cache_files:
            os.remove(os.path.join(influencer_dir, cache_file))
        print(f"   ✅ 已清除 {len(cache_files)} 个缓存文件\n")
    else:
        print("   ℹ️ 缓存目录不存在，跳过\n")

    # 4. 测试并发处理（3个窗口）
    print("4️⃣ 测试并发处理（3个独立窗口）...")
    print("   ⏳ 开始爬取...\n")

    start_time = time.time()
    try:
        response = requests.post(
            f"{API_BASE_URL}/process_influencer_list_concurrent",
            json={
                "json_file_path": test_file_path,
                "cache_days": 1,
                "max_concurrent": 3
            },
            timeout=600
        )
        concurrent_3_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 并发处理完成（3标签页）")
            print(f"   ⏱️ 耗时: {concurrent_3_time:.2f} 秒 ({concurrent_3_time/60:.2f} 分钟)")
            print(f"   📊 成功: {result['fetched_count']} / 失败: {result['failed_count']}\n")
        else:
            print(f"   ❌ 并发处理失败: {response.text}\n")
            concurrent_3_time = None
    except requests.exceptions.Timeout:
        print(f"   ⚠️ 并发处理超时\n")
        concurrent_3_time = None
    except Exception as e:
        print(f"   ❌ 并发处理出错: {e}\n")
        concurrent_3_time = None

    # 5. 清除缓存（准备5窗口测试）
    print("5️⃣ 清除缓存（准备5窗口测试）...")
    if os.path.exists(influencer_dir):
        cache_files = [f for f in os.listdir(influencer_dir)
                       if f.endswith('.json') and f.split('.')[0] in test_data["data_row_keys"]]
        for cache_file in cache_files:
            os.remove(os.path.join(influencer_dir, cache_file))
        print(f"   ✅ 已清除 {len(cache_files)} 个缓存文件\n")

    # 6. 测试并发处理（5个窗口）
    print("6️⃣ 测试并发处理（5个独立窗口）...")
    print("   ⏳ 开始爬取...\n")

    start_time = time.time()
    try:
        response = requests.post(
            f"{API_BASE_URL}/process_influencer_list_concurrent",
            json={
                "json_file_path": test_file_path,
                "cache_days": 1,
                "max_concurrent": 5
            },
            timeout=600
        )
        concurrent_5_time = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 并发处理完成（5窗口）")
            print(f"   ⏱️ 耗时: {concurrent_5_time:.2f} 秒 ({concurrent_5_time/60:.2f} 分钟)")
            print(f"   📊 成功: {result['fetched_count']} / 失败: {result['failed_count']}\n")
        else:
            print(f"   ❌ 并发处理失败: {response.text}\n")
            concurrent_5_time = None
    except requests.exceptions.Timeout:
        print(f"   ⚠️ 并发处理超时\n")
        concurrent_5_time = None
    except Exception as e:
        print(f"   ❌ 并发处理出错: {e}\n")
        concurrent_5_time = None

    # 7. 性能测试总结
    print("="*80)
    print("📊 多窗口并发性能测试总结")
    print("="*80)
    print()
    print(f"测试数据: {test_count} 个达人")
    print()

    if concurrent_3_time:
        print(f"⚡ 3窗口并发: {concurrent_3_time:.2f} 秒 ({concurrent_3_time/60:.2f} 分钟)")

    if concurrent_5_time:
        print(f"🚀 5窗口并发: {concurrent_5_time:.2f} 秒 ({concurrent_5_time/60:.2f} 分钟)")

    # 对比 3窗口 vs 5窗口
    if concurrent_3_time and concurrent_5_time:
        improvement = (concurrent_3_time / concurrent_5_time)
        print(f"\n💡 5窗口比3窗口提速: {improvement:.2f}x")

    print()

    # 估算 100 个达人的耗时
    print(f"📈 预估 100 个达人的处理时间:")

    if concurrent_3_time:
        estimated_concurrent_3 = (concurrent_3_time / test_count) * 100
        print(f"   3窗口并发: {estimated_concurrent_3/60:.1f} 分钟")

    if concurrent_5_time:
        estimated_concurrent_5 = (concurrent_5_time / test_count) * 100
        print(f"   5窗口并发: {estimated_concurrent_5/60:.1f} 分钟")

    print()
    print("="*80)


if __name__ == "__main__":
    test_concurrent_performance()
