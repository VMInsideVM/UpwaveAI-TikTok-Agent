"""
Playwright API 服务启动脚本
简化启动 FastAPI 服务的便捷脚本
"""

import subprocess
import sys
import os

def main():
    """启动 Playwright API 服务"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║      🚀 启动 Playwright API 服务 🚀                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    print("📝 启动前检查:")
    print("   1. 确保 Chrome 浏览器已启动")
    print("   2. 确保 CDP 端口 9224 已开放")
    print("   3. 启动命令: chrome.exe --remote-debugging-port=9224")
    print()
    print("🔐 启动时自动检查:")
    print("   - 自动打开 https://www.fastmoss.com/zh/influencer/search?shop_window=1")
    print("   - 自动检测登录状态并在需要时登录")
    print()

    # 检查是否安装了依赖
    try:
        import fastapi
        import uvicorn
        print("✅ FastAPI 和 Uvicorn 已安装")
    except ImportError:
        print("❌ 缺少依赖！请先运行: pip install -r requirements.txt")
        sys.exit(1)

    # 检查 playwright_api.py 是否存在
    if not os.path.exists("playwright_api.py"):
        print("❌ 找不到 playwright_api.py 文件！")
        sys.exit(1)

    print("✅ playwright_api.py 文件存在")
    print()
    print("🚀 正在启动 API 服务...")
    print("   - Host: 127.0.0.1")
    print("   - Port: 8000")
    print("   - Docs: http://127.0.0.1:8000/docs")
    print()
    print("💡 提示:")
    print("   - 按 Ctrl+C 停止服务")
    print("   - 启动后请打开新终端运行: python run_agent.py")
    print()
    print("="*60)
    print()

    # 启动 API 服务
    try:
        subprocess.run([
            sys.executable,  # 当前 Python 解释器路径
            "playwright_api.py"
        ])
    except KeyboardInterrupt:
        print("\n\n⚠️ 检测到 Ctrl+C，正在关闭服务...")
        print("✅ API 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
