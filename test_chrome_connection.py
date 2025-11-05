"""
测试 Chrome CDP 连接的详细诊断
"""

import requests
import socket

def test_connection():
    """测试各种连接方式"""
    print("=" * 60)
    print("🔍 Chrome CDP 详细诊断")
    print("=" * 60)

    # 测试不同的地址
    addresses = [
        "http://127.0.0.1:9224",
        "http://localhost:9224",
        "http://0.0.0.0:9224",
    ]

    for addr in addresses:
        print(f"\n测试: {addr}")
        try:
            response = requests.get(f"{addr}/json/version", timeout=2)
            print(f"  ✅ 成功！状态码: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  浏览器: {data.get('Browser', 'Unknown')}")
                print(f"  WebSocket URL: {data.get('webSocketDebuggerUrl', 'Unknown')}")
                return True
        except requests.exceptions.ConnectionError as e:
            print(f"  ❌ 连接失败: {e}")
        except Exception as e:
            print(f"  ❌ 错误: {e}")

    # 测试端口是否开放
    print("\n" + "=" * 60)
    print("🔌 测试端口连接")
    print("=" * 60)

    hosts = [
        ("127.0.0.1", 9224),
        ("localhost", 9224),
    ]

    for host, port in hosts:
        print(f"\n测试: {host}:{port}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                print(f"  ✅ 端口开放")
            else:
                print(f"  ❌ 端口关闭或无法访问")
        except Exception as e:
            print(f"  ❌ 错误: {e}")
        finally:
            sock.close()

    # 检查 Chrome 命令行参数
    print("\n" + "=" * 60)
    print("🔍 检查 Chrome 进程参数")
    print("=" * 60)

    try:
        import subprocess
        # 使用 wmic 查看 Chrome 进程的命令行
        result = subprocess.run(
            ['wmic', 'process', 'where', 'name="chrome.exe"', 'get', 'commandline'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            found_debug_port = False

            for line in lines:
                if '--remote-debugging-port' in line:
                    print("  ✅ 找到调试端口参数:")
                    # 提取端口号
                    if '9224' in line:
                        print("  ✅ 端口 9224 确认")
                        found_debug_port = True
                    else:
                        print("  ⚠️  使用的是其他端口，不是 9224")
                    # 显示部分命令行（避免太长）
                    import re
                    match = re.search(r'--remote-debugging-port=(\d+)', line)
                    if match:
                        print(f"  端口号: {match.group(1)}")
                    break

            if not found_debug_port:
                print("  ❌ 未找到 --remote-debugging-port 参数")
                print("  说明: Chrome 启动时没有添加调试端口参数")
        else:
            print("  ⚠️  无法获取进程信息")
    except Exception as e:
        print(f"  ⚠️  检查失败: {e}")

    print("\n" + "=" * 60)
    print("💡 建议")
    print("=" * 60)
    print("""
如果所有测试都失败，请尝试:

1. 完全关闭 Chrome:
   - 右键点击任务栏的 Chrome 图标 → 退出
   - 或在任务管理器中结束所有 chrome.exe 进程

2. 重新启动 Chrome (在 CMD 或 PowerShell 中):
   "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9224

3. 检查防火墙:
   - Windows 防火墙可能阻止了端口 9224
   - 尝试临时关闭防火墙测试

4. 尝试不同的端口:
   - 有些系统上某些端口可能被占用或限制
   - 可以尝试使用其他端口，如 9222 (默认) 或 9225
    """)

    return False

if __name__ == "__main__":
    test_connection()
