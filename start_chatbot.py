"""
聊天机器人服务启动脚本
自动检查依赖服务并启动聊天机器人 API
"""

import os
import sys
import time
import requests
import subprocess
import shutil
from pathlib import Path
from typing import Tuple


def clear_python_cache():
    """清理Python缓存文件，确保代码修改生效"""
    print("🧹 清理Python缓存...")

    # 清理 __pycache__ 目录
    for pycache_dir in Path('.').rglob('__pycache__'):
        try:
            shutil.rmtree(pycache_dir)
        except Exception as e:
            pass

    # 清理 .pyc 文件
    for pyc_file in Path('.').rglob('*.pyc'):
        try:
            pyc_file.unlink()
        except Exception as e:
            pass

    print("✅ 缓存清理完成")


def print_banner():
    """打印启动横幅"""
    print("""
╔══════════════════════════════════════════════════════════╗
║     🤖 TikTok 达人推荐聊天机器人启动助手 🤖             ║
╚══════════════════════════════════════════════════════════╝
    """)


def check_port(port: int) -> bool:
    """检查端口是否被占用"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0


def check_chrome_cdp() -> bool:
    """检查 Chrome CDP 是否可用"""
    try:
        response = requests.get("http://127.0.0.1:9224/json/version", timeout=2)
        return response.status_code == 200
    except:
        return False


def check_playwright_api() -> bool:
    """检查 Playwright API 是否可用"""
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def check_dependencies() -> Tuple[bool, bool, bool]:
    """
    检查所有依赖服务

    Returns:
        (chrome_ok, playwright_ok, port_available)
    """
    print("\n🔍 检查依赖服务...\n")

    # 检查 Chrome CDP
    print("1️⃣  检查 Chrome CDP (端口 9224)...", end=" ")
    chrome_ok = check_chrome_cdp()
    if chrome_ok:
        print("✅ 正常")
    else:
        print("❌ 不可用")

    # 检查 Playwright API
    print("2️⃣  检查 Playwright API (端口 8000)...", end=" ")
    playwright_ok = check_playwright_api()
    if playwright_ok:
        print("✅ 正常")
    else:
        print("❌ 不可用")

    # 检查聊天机器人端口
    print("3️⃣  检查聊天机器人端口 (8001)...", end=" ")
    port_available = not check_port(8001)
    if port_available:
        print("✅ 可用")
    else:
        print("❌ 已被占用")

    return chrome_ok, playwright_ok, port_available


def print_chrome_instructions():
    """打印 Chrome 启动说明"""
    print("""
📌 如何启动 Chrome CDP:

Windows:
    chrome.exe --remote-debugging-port=9224

macOS:
    /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9224

Linux:
    google-chrome --remote-debugging-port=9224
    """)


def print_playwright_instructions():
    """打印 Playwright API 启动说明"""
    print("""
📌 如何启动 Playwright API:

    python start_api.py

或者:

    python playwright_api.py
    """)


def start_chatbot_service():
    """启动聊天机器人服务"""
    print("\n🚀 启动聊天机器人服务...\n")

    try:
        # 1. 初始化数据库
        print("🔧 初始化数据库...")
        from database.connection import init_db, create_admin_user
        import os

        init_db()
        print("✅ 数据库表创建完成")

        # 2. 创建管理员账户（如果不存在）
        admin_username = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
        admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "***REMOVED***")
        admin_email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@fastmoss.com")

        create_admin_user(admin_username, admin_password, admin_email)

        # 3. 导入并启动服务
        from chatbot_api import start_server

        print("\n" + "=" * 60)
        print("📍 服务地址:")
        print("   - 登录页面: http://127.0.0.1:8001/login.html")
        print("   - 聊天界面: http://127.0.0.1:8001/")
        print("   - 管理后台: http://127.0.0.1:8001/admin.html")
        print("   - API 文档: http://127.0.0.1:8001/docs")
        print("=" * 60)
        print("\n🔐 管理员账户:")
        print(f"   - 用户名: {admin_username}")
        print(f"   - 密码: {admin_password}")
        print("   ⚠️  请在首次登录后立即修改密码！")
        print("=" * 60)
        print("\n💡 提示: 按 Ctrl+C 停止服务\n")
        print("=" * 60)

        # 启动服务
        start_server()

    except KeyboardInterrupt:
        print("\n\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print_banner()

    # 清理Python缓存，确保代码修改生效
    clear_python_cache()
    print()

    # 检查依赖
    chrome_ok, playwright_ok, port_available = check_dependencies()

    print("\n" + "=" * 60)

    # 检查结果
    all_ok = chrome_ok and playwright_ok and port_available

    if not chrome_ok:
        print("\n⚠️  Chrome CDP 服务未启动")
        print_chrome_instructions()

    if not playwright_ok:
        print("\n⚠️  Playwright API 服务未启动")
        print_playwright_instructions()

    if not port_available:
        print("\n⚠️  端口 8001 已被占用")
        print("   请关闭占用该端口的程序，或修改配置使用其他端口")

    if not all_ok:
        print("\n" + "=" * 60)
        response = input("\n是否继续启动? (y/n): ")
        if response.lower() != 'y':
            print("\n❌ 启动已取消")
            print("\n💡 提示: 请先启动所需的依赖服务，然后重新运行此脚本")
            return

    # 启动服务
    start_chatbot_service()


if __name__ == "__main__":
    main()
