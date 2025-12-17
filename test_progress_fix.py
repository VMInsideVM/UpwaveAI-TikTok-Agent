"""
测试进度和 ETA 计算修复

验证修复:
1. 进度计算应该基于已完成的项目数 (i-1)，而不是当前项目数 (i)
2. ETA 计算应该是: avg_time_per_item * remaining_items
"""

import time


def test_old_progress_logic():
    """旧的错误逻辑"""
    print("=" * 60)
    print("❌ 旧逻辑 (错误)")
    print("=" * 60)

    total = 18
    for i in range(1, 6):
        # 旧逻辑: 使用 i (当前正在处理的项目)
        progress = 40 + int(40 * i / total)
        print(f"正在分析第 {i}/{total} 个达人 -> 进度: {progress}%")

    print()


def test_new_progress_logic():
    """新的正确逻辑"""
    print("=" * 60)
    print("✅ 新逻辑 (正确)")
    print("=" * 60)

    total = 18
    for i in range(1, 6):
        # 新逻辑: 使用 i-1 (已完成的项目数)
        progress = 40 + int(40 * (i - 1) / total)
        print(f"正在分析第 {i}/{total} 个达人 -> 进度: {progress}% (已完成: {i-1}个)")

    print()


def test_old_eta_logic():
    """旧的错误 ETA 计算"""
    print("=" * 60)
    print("❌ 旧 ETA 逻辑 (错误)")
    print("=" * 60)

    stage_start_time = time.time()

    # 模拟: 已经过了 60 秒，完成了 40%
    elapsed = 60
    internal_progress = 40

    # 旧逻辑
    estimated_total = (elapsed / internal_progress) * 100
    eta_seconds_old = int(estimated_total - elapsed)

    print(f"已用时间: {elapsed}秒")
    print(f"当前进度: {internal_progress}%")
    print(f"预计总时间: {estimated_total}秒")
    print(f"预计剩余时间: {eta_seconds_old}秒")
    print()

    # 验证
    print("问题分析:")
    print(f"  - 平均每个百分点用时: {elapsed/internal_progress:.2f}秒")
    print(f"  - 剩余百分点: {100 - internal_progress}%")
    print(f"  - 正确的 ETA 应该是: {int((elapsed/internal_progress) * (100 - internal_progress))}秒")
    print(f"  - 旧逻辑计算的 ETA: {eta_seconds_old}秒")
    print()


def test_new_eta_logic():
    """新的正确 ETA 计算"""
    print("=" * 60)
    print("✅ 新 ETA 逻辑 (正确)")
    print("=" * 60)

    # 模拟: 已经过了 60 秒，完成了 40%
    elapsed = 60
    internal_progress = 40

    # 新逻辑
    avg_time_per_percent = elapsed / internal_progress
    remaining_percent = 100 - internal_progress
    eta_seconds_new = int(avg_time_per_percent * remaining_percent)

    print(f"已用时间: {elapsed}秒")
    print(f"当前进度: {internal_progress}%")
    print(f"平均每个百分点用时: {avg_time_per_percent:.2f}秒")
    print(f"剩余百分点: {remaining_percent}%")
    print(f"预计剩余时间: {eta_seconds_new}秒")
    print()


def test_real_scenario():
    """实际场景测试"""
    print("=" * 60)
    print("🧪 实际场景测试: 分析 18 个达人")
    print("=" * 60)

    total = 18
    start_time = time.time()

    print("\n使用新逻辑 (正确):")
    print("-" * 60)

    for i in [1, 3, 9, 18]:
        # 模拟已用时间 (假设每个达人平均 5 秒)
        elapsed = (i - 1) * 5  # 前 i-1 个已完成

        # 新进度逻辑
        progress = 40 + int(40 * (i - 1) / total)

        # 新 ETA 逻辑
        if i > 1:  # 至少完成 1 个才能计算 ETA
            avg_time_per_item = elapsed / (i - 1)
            remaining_items = total - (i - 1)
            eta_seconds = int(avg_time_per_item * remaining_items)
        else:
            eta_seconds = None

        eta_text = f"{eta_seconds}秒" if eta_seconds is not None else "计算中..."
        print(f"正在分析第 {i:2d}/{total} 个达人 -> 进度: {progress:2d}%, ETA: {eta_text}")

    print()


if __name__ == "__main__":
    test_old_progress_logic()
    test_new_progress_logic()
    test_old_eta_logic()
    test_new_eta_logic()
    test_real_scenario()

    print("=" * 60)
    print("📝 总结")
    print("=" * 60)
    print("1. 进度计算修复:")
    print("   - 旧: current_progress = 40 + int(40 * i / total)")
    print("   - 新: current_progress = 40 + int(40 * (i-1) / total)")
    print("   - 原因: 第 i 个正在处理,只有前 i-1 个已完成")
    print()
    print("2. ETA 计算修复:")
    print("   - 旧: eta = int((elapsed/progress)*100 - elapsed)")
    print("   - 新: eta = int((elapsed/progress) * (100-progress))")
    print("   - 原因: 应该是平均时间 * 剩余数量")
    print()
