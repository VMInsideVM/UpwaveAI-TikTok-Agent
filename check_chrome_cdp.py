"""
检查 Chrome CDP 状态的诊断脚本
"""

import requests
import subprocess
import sys

def check_chrome_cdp():
    """检查 Chrome CDP 是否可用"""
    print("=" * 60)
    print("🔍 Chrome CDP 诊断工具")
    print("=" * 60)

    # 1. 尝试访问 CDP 端点
    print("\n1️⃣  检查 CDP 端口 9224...")
    try:
        response = requests.get("http://127.0.0.1:9224/json/version", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print("✅ Chrome CDP 正常运行！")
            print(f"   浏览器: {data.get('Browser', 'Unknown')}")
            print(f"   协议版本: {data.get('Protocol-Version', 'Unknown')}")
            print(f"   WebSocket: {data.get('webSocketDebuggerUrl', 'Unknown')}")
            return True
        else:
            print(f"⚠️  CDP 响应异常，状态码: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 Chrome CDP (端口 9224)")
        print("   可能原因:")
        print("   1. Chrome 未启动")
        print("   2. Chrome 启动时未添加 --remote-debugging-port=9224 参数")
        print("   3. 端口被防火墙阻止")
        return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

def check_chrome_process():
    """检查 Chrome 进程是否运行"""
    print("\n2️⃣  检查 Chrome 进程...")
    try:
        # Windows: 使用 tasklist
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq chrome.exe'],
            capture_output=True,
            text=True
        )

        if 'chrome.exe' in result.stdout:
            print("✅ Chrome 进程正在运行")
            # 统计进程数量
            chrome_lines = [line for line in result.stdout.split('\n') if 'chrome.exe' in line]
            print(f"   找到 {len(chrome_lines)} 个 Chrome 进程")
            return True
        else:
            print("❌ Chrome 进程未运行")
            return False
    except Exception as e:
        print(f"⚠️  无法检查进程: {e}")
        return False

def print_solution():
    """打印解决方案"""
    print("\n" + "=" * 60)
    print("💡 解决方案")
    print("=" * 60)
    print("""
方式 1 - 手动启动 Chrome（推荐）:
    1. 关闭所有 Chrome 窗口
    2. 打开命令提示符（CMD）或 PowerShell
    3. 执行以下命令:

    Windows (CMD):
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9224

    Windows (PowerShell):
        & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9224

    如果 Chrome 安装在其他位置，请修改路径。

方式 2 - 使用脚本启动（推荐创建）:
    创建一个 start_chrome.bat 文件:
        @echo off
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9224

    然后双击运行该文件。

⚠️  注意事项:
    - 启动前必须关闭所有 Chrome 窗口
    - CDP 参数只在 Chrome 首次启动时生效
    - 如果 Chrome 已经运行，需要先完全退出再重新启动
    """)

def create_chrome_launcher():
    """创建 Chrome 启动脚本"""
    print("\n3️⃣  是否创建 Chrome 启动脚本？(y/n): ", end="")
    choice = input().strip().lower()

    if choice == 'y':
        # 常见的 Chrome 安装路径
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(
                subprocess.getoutput('echo %USERNAME%')
            )
        ]

        # 查找 Chrome
        chrome_path = None
        import os
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_path = path
                break

        if not chrome_path:
            print("⚠️  无法自动找到 Chrome，请手动指定路径")
            chrome_path = input("请输入 Chrome 完整路径: ").strip()

        # 创建批处理文件
        bat_content = f'''@echo off
echo =========================================
echo   启动 Chrome (CDP 端口 9224)
echo =========================================
echo.
echo 提示: 启动前会尝试关闭现有 Chrome 进程
echo.
pause

REM 关闭现有 Chrome 进程
taskkill /F /IM chrome.exe /T 2>nul
timeout /t 2 /nobreak >nul

REM 启动 Chrome
echo 正在启动 Chrome...
start "" "{chrome_path}" --remote-debugging-port=9224

echo.
echo ✅ Chrome 已启动！CDP 端口: 9224
echo.
echo 请保持此窗口打开，不要关闭 Chrome
echo.
pause
'''

        with open("start_chrome.bat", "w", encoding="utf-8") as f:
            f.write(bat_content)

        print("✅ 已创建 start_chrome.bat")
        print("   现在可以双击该文件启动 Chrome")

        # 询问是否立即启动
        print("\n是否立即启动？(y/n): ", end="")
        run_now = input().strip().lower()
        if run_now == 'y':
            subprocess.Popen(['start_chrome.bat'], shell=True)
            print("✅ Chrome 正在启动...")
            print("⏳ 等待 3 秒后重新检查...")
            import time
            time.sleep(3)
            check_chrome_cdp()

def main():
    """主函数"""
    cdp_ok = check_chrome_cdp()
    process_ok = check_chrome_process()

    print("\n" + "=" * 60)
    print("📊 诊断结果")
    print("=" * 60)
    print(f"Chrome 进程: {'✅ 运行中' if process_ok else '❌ 未运行'}")
    print(f"CDP 端口:   {'✅ 可用' if cdp_ok else '❌ 不可用'}")

    if not cdp_ok:
        print_solution()
        create_chrome_launcher()
    else:
        print("\n🎉 所有检查通过！可以正常使用 Playwright API")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 检查已取消")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
