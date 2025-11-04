"""
测试流式进度显示 - SSE 版本

这个脚本测试新的流式 API 端点，验证实时进度条显示功能。
使用少量达人（3个）进行快速测试。
"""

import requests
import json
import os
import time

API_BASE_URL = "http://127.0.0.1:8000"

# 测试用的达人 ID（3个）
TEST_INFLUENCER_IDS = [
    "7288986759428588590",
    "7170541438504420394",
    "6951979291350795269"
]


def test_streaming_progress():
    """测试流式进度显示"""
    print("🧪 测试流式进度显示功能")
    print("=" * 60)
    print()

    # 创建临时测试文件
    test_data = {
        "product_name": "流式测试",
        "timestamp": "20251104_streaming_test",
        "total_count": len(TEST_INFLUENCER_IDS),
        "data_row_keys": TEST_INFLUENCER_IDS
    }

    os.makedirs("output", exist_ok=True)
    test_file = "output/test_streaming.json"

    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 测试文件已创建: {test_file}")
    print(f"   达人数量: {len(TEST_INFLUENCER_IDS)}")
    print()

    # 调用流式 API
    print("🔄 开始调用流式 API...")
    print("   期待看到：")
    print("   - 初始化消息")
    print("   - 实时进度条（每10%更新）")
    print("   - 预估剩余时间")
    print("   - 成功/缓存/失败统计")
    print()
    print("-" * 60)
    print()

    try:
        url = f"{API_BASE_URL}/process_influencer_list_stream"
        params = {
            "json_file_path": test_file,
            "cache_days": 3
        }

        start_time = time.time()

        # 流式接收
        with requests.get(url, params=params, stream=True, timeout=300) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                # 解析 SSE 事件
                line_str = line.decode('utf-8')
                if not line_str.startswith('data: '):
                    continue

                event_data = line_str[6:]  # 移除 "data: " 前缀
                try:
                    event = json.loads(event_data)
                except json.JSONDecodeError:
                    print(f"⚠️ 无法解析事件: {event_data}")
                    continue

                # 处理不同类型的事件
                if event["type"] == "init":
                    total = event["total"]
                    product_name = event.get("product_name", "未知商品")
                    print(f"📦 商品: {product_name}")
                    print(f"⏳ 共需处理 {total} 个达人，请耐心等待")
                    print()

                elif event["type"] == "progress":
                    current = event["current"]
                    total = event["total"]
                    success = event["success"]
                    cached = event["cached"]
                    failed = event["failed"]
                    elapsed = event["elapsed_seconds"]

                    # 计算进度
                    percent = int(current / total * 100)

                    # 绘制进度条
                    bar_len = 30
                    filled = int(bar_len * percent / 100)
                    bar = '█' * filled + '░' * (bar_len - filled)

                    # 计算预估时间
                    if current > 0 and elapsed > 0:
                        avg_time = elapsed / current
                        remaining = int((total - current) * avg_time)
                        elapsed_str = format_time(elapsed)
                        remaining_str = format_time(remaining)
                        time_info = f"⏱️ 已用时: {elapsed_str} | 预计剩余: {remaining_str}"
                    else:
                        time_info = f"⏱️ 处理中..."

                    print(f"处理进度: {bar} {percent}% ({current}/{total})")
                    print(time_info)
                    print(f"✓ 成功: {success}  |  ⚡ 缓存: {cached}  |  ✗ 失败: {failed}")
                    print()

                elif event["type"] == "complete":
                    stats = event["stats"]
                    total_elapsed = time.time() - start_time

                    print()
                    print("=" * 60)
                    print("✅ 处理完成！")
                    print()
                    print(f"📊 最终统计:")
                    print(f"   • 总达人数: {stats['total']}")
                    print(f"   • 成功获取: {stats['success']}")
                    print(f"   • 使用缓存: {stats['cached']}")
                    print(f"   • 失败数量: {stats['failed']}")
                    print(f"   • 总耗时: {stats['elapsed_time']}")
                    print()

                    if stats['failed'] > 0:
                        print(f"⚠️ 失败的达人 ID:")
                        for failed_id in stats.get('failed_ids', []):
                            print(f"   - {failed_id}")
                        print()

                    # 验证文件生成
                    print("📁 验证文件生成:")
                    influencer_dir = "influencer"
                    if os.path.exists(influencer_dir):
                        generated_files = [f for f in os.listdir(influencer_dir) if f.endswith('.json')]
                        print(f"   influencer 目录包含 {len(generated_files)} 个文件")

                        for influencer_id in TEST_INFLUENCER_IDS:
                            filepath = os.path.join(influencer_dir, f"{influencer_id}.json")
                            if os.path.exists(filepath):
                                file_size = os.path.getsize(filepath)
                                print(f"   ✓ {influencer_id}.json 已生成 ({file_size:,} 字节)")
                            else:
                                print(f"   ✗ {influencer_id}.json 未找到")
                    print()

                elif event["type"] == "error":
                    print(f"❌ 处理失败: {event['message']}")
                    print()

        print("=" * 60)
        print("✅ 流式进度测试完成！")
        print()
        print("验证点：")
        print("  ✓ 看到了初始化消息")
        print("  ✓ 看到了实时进度条")
        print("  ✓ 看到了预估剩余时间")
        print("  ✓ 看到了成功/缓存/失败统计")
        print("  ✓ 看到了最终完成消息")
        print()

    except requests.exceptions.ConnectionError:
        print()
        print("❌ 无法连接到 API 服务")
        print("   请先启动 Playwright API: python playwright_api.py")
        print()
    except requests.exceptions.Timeout:
        print()
        print("❌ 请求超时")
        print()
    except Exception as e:
        print()
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        print()


def format_time(seconds: int) -> str:
    """格式化时间显示"""
    if seconds < 60:
        return f"{seconds} 秒"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes} 分 {secs} 秒"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} 小时 {minutes} 分"


if __name__ == "__main__":
    test_streaming_progress()
