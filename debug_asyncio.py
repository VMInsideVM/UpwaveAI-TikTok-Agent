"""
调试 asyncio 事件循环问题
找出谁在 nest_asyncio 之前启动了事件循环
"""

import sys

# 第一步：在导入任何东西之前，检查是否已有事件循环
print("=" * 80)
print("🔍 步骤 1: 检查初始状态")
print("=" * 80)

try:
    import asyncio
    loop = asyncio.get_event_loop()
    print(f"⚠️ 发现已存在的事件循环: {loop}")
    print(f"   循环是否运行中: {loop.is_running()}")
    print(f"   循环是否关闭: {loop.is_closed()}")
except RuntimeError as e:
    print(f"✅ 没有事件循环: {e}")

# 第二步：应用 nest_asyncio
print("\n" + "=" * 80)
print("🔍 步骤 2: 应用 nest_asyncio")
print("=" * 80)

import nest_asyncio
print("✅ nest_asyncio 已导入")
nest_asyncio.apply()
print("✅ nest_asyncio.apply() 已调用")

# 第三步：再次检查事件循环
try:
    loop = asyncio.get_event_loop()
    print(f"✅ 事件循环状态: {loop}")
    print(f"   已打补丁: {hasattr(loop, '_nest_patched')}")
except RuntimeError as e:
    print(f"事件循环: {e}")

# 第四步：导入 main.py 看看会发生什么
print("\n" + "=" * 80)
print("🔍 步骤 3: 导入 main.py")
print("=" * 80)

try:
    from main import initialize_playwright, navigate_to_url
    print("✅ main.py 导入成功")
except Exception as e:
    print(f"❌ main.py 导入失败: {e}")
    import traceback
    traceback.print_exc()

# 第五步：测试 Playwright 初始化
print("\n" + "=" * 80)
print("🔍 步骤 4: 初始化 Playwright")
print("=" * 80)

try:
    initialize_playwright()
    print("✅ Playwright 初始化成功")
except Exception as e:
    print(f"❌ Playwright 初始化失败: {e}")
    import traceback
    traceback.print_exc()

# 第六步：检查 Playwright 内部
print("\n" + "=" * 80)
print("🔍 步骤 5: 深度检查 Playwright")
print("=" * 80)

try:
    from playwright.sync_api import sync_playwright
    print("测试 sync_playwright().start() ...")

    # 检查当前线程的事件循环
    try:
        current_loop = asyncio.get_running_loop()
        print(f"⚠️ 发现运行中的事件循环: {current_loop}")
        print(f"   这就是问题所在！")
    except RuntimeError:
        print("✅ 没有运行中的事件循环")

    pw = sync_playwright().start()
    print("✅ sync_playwright().start() 成功")
    pw.stop()

except Exception as e:
    print(f"❌ 失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("🔍 诊断完成")
print("=" * 80)
