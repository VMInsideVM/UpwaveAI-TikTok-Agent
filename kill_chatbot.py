"""
清理占用端口 8001 的进程
用于解决端口被占用的问题
"""

import subprocess
import sys
import re


def find_pid_by_port(port: int) -> list:
    """查找占用指定端口的进程 PID"""
    try:
        # 运行 netstat 命令
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
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
            ["taskkill", "/PID", str(pid), "/F"],
            check=True,
            capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def main():
    """主函数"""
    PORT = 8001

    print(f"🔍 查找占用端口 {PORT} 的进程...")

    pids = find_pid_by_port(PORT)

    if not pids:
        print(f"✅ 端口 {PORT} 未被占用")
        return

    print(f"📌 发现 {len(pids)} 个进程占用端口 {PORT}:")
    for pid in pids:
        print(f"   - PID: {pid}")

    # 询问是否终止
    response = input(f"\n是否终止这些进程? (y/n): ")

    if response.lower() != 'y':
        print("❌ 已取消")
        return

    # 终止进程
    print("\n🔨 正在终止进程...")
    success_count = 0
    for pid in pids:
        if kill_process(pid):
            print(f"✅ 已终止进程 {pid}")
            success_count += 1
        else:
            print(f"❌ 无法终止进程 {pid} (可能需要管理员权限)")

    print(f"\n✅ 完成! 成功终止 {success_count}/{len(pids)} 个进程")
    print(f"💡 现在可以运行: python start_chatbot.py")


if __name__ == "__main__":
    main()
