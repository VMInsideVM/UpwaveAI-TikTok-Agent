"""
找出谁启动了事件循环
"""

import sys
import asyncio

# 在导入任何东西之前检查
print("🔍 检查 1: 最初始状态")
try:
    loop = asyncio.get_running_loop()
    print(f"❌ 已有运行中的循环: {loop}")
except RuntimeError:
    print("✅ 没有运行中的循环")

# 应用 nest_asyncio
print("\n🔍 检查 2: 应用 nest_asyncio 后")
import nest_asyncio
nest_asyncio.apply()

try:
    loop = asyncio.get_running_loop()
    print(f"❌ 有运行中的循环: {loop}")
except RuntimeError:
    print("✅ 没有运行中的循环")

# 逐个导入模块，看谁触发了循环
modules_to_test = [
    'dotenv',
    'langchain',
    'langchain_openai',
    'langchain.tools',
    'pandas',
    'openpyxl',
]

for module_name in modules_to_test:
    print(f"\n🔍 检查 3.{modules_to_test.index(module_name) + 1}: 导入 {module_name}")
    try:
        __import__(module_name)
        print(f"   ✅ 导入成功")

        # 检查是否触发了循环
        try:
            loop = asyncio.get_running_loop()
            print(f"   ⚠️ 这个模块启动了事件循环！{loop}")
            print(f"   循环状态: running={loop.is_running()}")
            break
        except RuntimeError:
            print(f"   ✅ 没有启动循环")

    except ImportError as e:
        print(f"   ⏭️ 跳过（未安装）: {e}")

print("\n" + "=" * 80)
print("🔍 最终检查: 直接测试 Playwright 触发点")
print("=" * 80)

# 模拟 initialize_playwright 的第一行代码
from playwright.sync_api import sync_playwright

print("准备调用 sync_playwright().start() ...")

try:
    loop = asyncio.get_running_loop()
    print(f"⚠️ 调用前已有运行中的循环: {loop}")
except RuntimeError:
    print("✅ 调用前没有运行中的循环")

# 这是触发错误的地方
try:
    pw = sync_playwright().start()
    print("✅ 成功！")
    pw.stop()
except Exception as e:
    print(f"❌ 失败: {e}")
