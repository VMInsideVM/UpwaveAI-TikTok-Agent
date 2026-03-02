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

# 设置UTF-8编码输出（解决Windows下emoji显示问题）
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def clear_python_cache():
    """清理Python缓存文件，确保代码修改生效"""
    print("🧹 清理Python缓存...")

    # 清理 __pycache__ 目录
    for pycache_dir in Path(".").rglob("__pycache__"):
        try:
            shutil.rmtree(pycache_dir)
        except Exception as e:
            pass

    # 清理 .pyc 文件
    for pyc_file in Path(".").rglob("*.pyc"):
        try:
            pyc_file.unlink()
        except Exception as e:
            pass

    print("✅ 缓存清理完成")


def print_banner():
    """打印启动横幅"""
    print(
        """
╔══════════════════════════════════════════════════════════╗
║     🤖 TikTok 达人推荐聊天机器人启动助手 🤖             ║
╚══════════════════════════════════════════════════════════╝
    """
    )


def check_port(port: int) -> bool:
    """检查端口是否被占用"""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", port))
    sock.close()
    return result == 0


def find_pid_by_port(port: int) -> list:
    """查找占用指定端口的进程 PID"""
    try:
        # 运行 netstat 命令
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )

        # 解析输出
        pids = []
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                # 提取 PID（最后一列）
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids.append(int(pid))

        return pids

    except Exception as e:
        print(f"❌ 查找进程失败: {e}")
        return []


def kill_process(pid: int) -> bool:
    """终止指定 PID 的进程"""
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"], check=True, capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def clear_port(port: int) -> bool:
    """清理占用指定端口的进程"""
    pids = find_pid_by_port(port)

    if not pids:
        return True  # 端口未被占用

    print(f"\n⚠️  发现 {len(pids)} 个进程占用端口 {port}:")
    for pid in pids:
        print(f"   - PID: {pid}")

    print(f"\n🔨 正在自动清理占用端口的进程...")
    success_count = 0
    for pid in pids:
        if kill_process(pid):
            print(f"✅ 已终止进程 {pid}")
            success_count += 1
        else:
            print(f"❌ 无法终止进程 {pid} (可能需要管理员权限)")

    if success_count == len(pids):
        print(f"✅ 端口 {port} 已清理完成\n")
        return True
    else:
        print(f"⚠️  部分进程清理失败 ({success_count}/{len(pids)})\n")
        return False


def check_playwright_api() -> bool:
    """检查 Playwright API 是否可用"""
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def check_dependencies() -> bool:
    """
    检查所有依赖服务

    Returns:
        playwright_ok: Playwright API 是否可用
    """
    # 检查 Playwright API
    print("1️⃣  检查 Playwright API (端口 8000)...", end=" ")
    playwright_ok = check_playwright_api()
    if playwright_ok:
        print("✅ 正常")
    else:
        print("❌ 不可用")

    # 检查并清理聊天机器人端口
    print("2️⃣  检查聊天机器人端口 (8001)...", end=" ")
    if check_port(8001):
        print("❌ 已被占用")
        # 自动清理端口
        clear_port(8001)
    else:
        print("✅ 可用")

    return playwright_ok


def print_playwright_instructions():
    """打印 Playwright API 启动说明"""
    print(
        """
📌 如何启动 Playwright API:

    python start_api.py

或者:

    python playwright_api.py
    """
    )


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
        admin_password = os.getenv("INITIAL_ADMIN_PASSWORD")
        if not admin_password:
            print("❌ 请设置环境变量 INITIAL_ADMIN_PASSWORD")
            return
        admin_email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@fastmoss.com")

        create_admin_user(admin_username, admin_password, admin_email)

        # 3. 导入并启动服务
        from chatbot_api import start_server

        print("\n" + "=" * 60)
        print("📍 服务地址:")
        print("   - 本地访问: http://127.0.0.1:8001/")
        print("   - 网络访问: http://0.0.0.0:8001/")
        print("   - 登录页面: /login.html")
        print("   - 聊天界面: /")
        print("   - 管理后台: /admin.html")
        print("   - API 文档: /docs")
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

    # 检查依赖（端口会自动清理）
    playwright_ok = check_dependencies()

    print("\n" + "=" * 60)

    # 检查结果
    if not playwright_ok:
        print("\n⚠️  Playwright API 服务未启动")
        print_playwright_instructions()
        print("\n" + "=" * 60)
        response = input("\n是否继续启动? (y/n): ")
        if response.lower() != "y":
            print("\n❌ 启动已取消")
            print("\n💡 提示: 请先启动所需的依赖服务，然后重新运行此脚本")
            return

    # 启动服务
    start_chatbot_service()


if __name__ == "__main__":
    main()
