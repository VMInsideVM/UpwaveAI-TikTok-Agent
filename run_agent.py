"""
TikTok 达人推荐 Agent 启动脚本
命令行交互式对话界面
"""

# CRITICAL: 必须在最开始就应用 nest_asyncio，在任何其他导入之前
import nest_asyncio
nest_asyncio.apply()

import sys
import os

# 强制单线程执行（解决 Playwright greenlet 线程切换错误）
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

# 尝试导入完整版 Agent,如果失败则使用简化版
try:
    from agent import create_agent
    AGENT_TYPE = "完整版"
except Exception as e:
    print(f"⚠️ 完整版 Agent 加载失败: {e}")
    print("🔄 切换到简化版 Agent...")
    from agent_simple import create_agent
    AGENT_TYPE = "简化版"

# API 模式不需要直接初始化 Playwright
# from main import initialize_playwright


def print_banner():
    """打印启动横幅"""
    banner = f"""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║      🚀 TikTok 达人推荐智能助手 v1.0 🚀                      ║
║                                                               ║
║      基于 LangChain + Qwen3-VL-30B 构建                       ║
║      当前版本: {AGENT_TYPE:^20s}                             ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_help():
    """打印帮助信息"""
    help_text = """
📖 **使用说明**:

1. 直接输入你的需求,例如:
   "我要推广口红,在美国找 50 个达人,粉丝 10 万到 50 万"

2. 也可以逐步回答问题,Agent 会引导你

3. 特殊命令:
   - 输入 'help' 或 '帮助' - 显示此帮助信息
   - 输入 'exit' 或 '退出' - 退出程序
   - 输入 'reset' 或 '重置' - 重置对话,开始新的推荐任务

4. 示例对话:
   你: "我要推广运动鞋"
   Agent: "好的,请问你希望在哪个国家/地区找达人?"
   你: "美国"
   Agent: "你需要多少个达人呢?"
   你: "100个,粉丝10万到50万,要有邮箱"

---
"""
    print(help_text)


def main():
    """主函数"""
    print_banner()

    # 检查 Playwright API 服务是否运行
    print("🔧 正在检查 Playwright API 服务...")
    try:
        import requests
        response = requests.get("http://127.0.0.1:8000/health", timeout=5)
        health_data = response.json()

        if health_data.get("playwright_initialized"):
            print("✅ Playwright API 服务已就绪!\n")
        else:
            print("❌ Playwright API 服务未初始化")
            print("请检查 API 服务的启动日志")
            sys.exit(1)

    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到 Playwright API 服务")
        print("请先启动 API 服务:")
        print("  方式 1: python start_api.py")
        print("  方式 2: python playwright_api.py")
        print("\n确保:")
        print("  1. API 服务已启动")
        print("  2. Chrome 浏览器已启动（CDP 端口 9224）")
        print("  3. 服务运行在 127.0.0.1:8000")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 检查 API 服务时出错: {e}")
        sys.exit(1)

    # 创建 Agent
    print("🤖 正在加载 AI Agent...")
    try:
        agent = create_agent()
        print("✅ Agent 加载成功!\n")
    except Exception as e:
        print(f"❌ Agent 加载失败: {e}")
        print("请检查:")
        print("  1. .env 文件是否正确配置")
        print("  2. API 密钥是否有效")
        print("  3. 网络连接是否正常")
        sys.exit(1)

    # 显示欢迎消息
    print(agent.welcome_message())
    print("\n💡 提示: 输入 'help' 查看使用说明\n")
    print("="*60)

    # 主对话循环
    conversation_count = 0

    while True:
        try:
            # 获取用户输入
            user_input = input("\n👤 你: ").strip()

            # 处理空输入
            if not user_input:
                continue

            # 处理特殊命令
            if user_input.lower() in ['exit', '退出', 'quit', 'q']:
                print("\n👋 感谢使用 TikTok 达人推荐助手,再见!")
                break

            if user_input.lower() in ['help', '帮助', 'h', '?']:
                print_help()
                continue

            if user_input.lower() in ['reset', '重置', 'restart']:
                print("\n🔄 重置对话...")
                agent = create_agent()
                print("✅ 对话已重置,可以开始新的推荐任务!")
                print(agent.welcome_message())
                conversation_count = 0
                continue

            # 处理用户输入
            print("\n🤖 Agent 思考中...\n")
            response = agent.run(user_input)

            # 显示回复
            print(f"\n🤖 Agent: {response}")
            print("\n" + "="*60)

            conversation_count += 1

            # 检查是否完成任务(简单的启发式判断)
            if "导出成功" in response or "Excel" in response:
                print("\n✨ 任务完成!")
                print("💡 你可以:")
                print("   - 继续提问或调整需求")
                print("   - 输入 'reset' 开始新的推荐任务")
                print("   - 输入 'exit' 退出程序")

        except KeyboardInterrupt:
            print("\n\n⚠️ 检测到 Ctrl+C")
            confirm = input("确定要退出吗? (y/n): ").strip().lower()
            if confirm in ['y', 'yes', '是', '确定']:
                print("\n👋 再见!")
                break
            else:
                print("继续对话...")
                continue

        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            print("请重新输入或输入 'reset' 重置对话")
            continue


def test_mode():
    """测试模式 - 运行预设的测试用例"""
    print("🧪 进入测试模式...\n")

    test_cases = [
        "我要推广口红,在美国找 20 个达人,粉丝 10 万到 50 万,要有邮箱",
        "我需要推广运动鞋,找 50 个英国的达人,粉丝越多越好,关注互动率",
        "推广瑜伽垫,印度尼西亚,30 个达人,女粉为主,18-34 岁"
    ]

    print("📋 测试用例:")
    for i, case in enumerate(test_cases, 1):
        print(f"{i}. {case}")

    choice = input("\n请选择测试用例 (1-3) 或按 Enter 进入正常模式: ").strip()

    if choice in ['1', '2', '3']:
        index = int(choice) - 1
        print(f"\n执行测试用例 {choice}: {test_cases[index]}\n")

        # 检查 API 服务
        print("🔧 正在检查 Playwright API 服务...")
        try:
            import requests
            response = requests.get("http://127.0.0.1:8000/health", timeout=5)
            if not response.json().get("playwright_initialized"):
                print("❌ Playwright API 服务未就绪，请先启动: python start_api.py")
                return
            print("✅ API 服务已就绪\n")
        except:
            print("❌ 无法连接到 API 服务，请先启动: python start_api.py")
            return

        # 创建 Agent
        agent = create_agent()

        # 运行测试
        response = agent.run(test_cases[index])
        print(f"\n🤖 Agent 回复:\n{response}")
    else:
        print("进入正常模式...")
        main()


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_mode()
    else:
        main()
