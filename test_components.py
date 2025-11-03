"""
组件测试脚本
快速验证各个模块是否正常工作
"""

import sys
import os

def test_imports():
    """测试所有模块是否可以正常导入"""
    print("="*60)
    print("🧪 测试 1: 模块导入")
    print("="*60)

    try:
        print("  ✓ 导入 dotenv...", end="")
        from dotenv import load_dotenv
        print(" ✅")

        print("  ✓ 导入 langchain...", end="")
        from langchain_openai import ChatOpenAI
        from langchain.tools import BaseTool
        print(" ✅")

        print("  ✓ 导入 pandas...", end="")
        import pandas as pd
        print(" ✅")

        print("  ✓ 导入 openpyxl...", end="")
        import openpyxl
        print(" ✅")

        print("  ✓ 导入 playwright...", end="")
        from playwright.sync_api import sync_playwright
        print(" ✅")

        print("\n✅ 所有依赖导入成功!\n")
        return True

    except ImportError as e:
        print(f" ❌\n\n❌ 导入失败: {e}")
        print("\n请运行: pip install -r requirements.txt")
        return False


def test_env_config():
    """测试环境变量配置"""
    print("="*60)
    print("🧪 测试 2: 环境变量配置")
    print("="*60)

    from dotenv import load_dotenv
    load_dotenv()

    required_vars = ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"]
    all_ok = True

    for var in required_vars:
        value = os.getenv(var)
        if value:
            # 隐藏 API key 的中间部分
            if "KEY" in var:
                display_value = f"{value[:10]}...{value[-10:]}"
            else:
                display_value = value
            print(f"  ✓ {var}: {display_value} ✅")
        else:
            print(f"  ✗ {var}: 未设置 ❌")
            all_ok = False

    if all_ok:
        print("\n✅ 环境变量配置完整!\n")
    else:
        print("\n❌ 请检查 .env 文件配置\n")

    return all_ok


def test_category_files():
    """测试分类文件是否存在"""
    print("="*60)
    print("🧪 测试 3: 商品分类文件")
    print("="*60)

    categories_dir = "categories"

    if not os.path.exists(categories_dir):
        print(f"❌ 目录不存在: {categories_dir}\n")
        return False

    json_files = [f for f in os.listdir(categories_dir) if f.endswith('.json')]
    count = len(json_files)

    print(f"  ✓ 找到 {count} 个分类文件")

    if count >= 29:
        print("  ✓ 分类文件完整 ✅\n")
        return True
    else:
        print(f"  ⚠️  预期 29 个文件,实际 {count} 个 ⚠️\n")
        return False


def test_category_matcher():
    """测试分类匹配功能(不调用 LLM)"""
    print("="*60)
    print("🧪 测试 4: 分类匹配模块")
    print("="*60)

    try:
        from category_matcher import CategoryMatcher
        matcher = CategoryMatcher()
        print("  ✓ CategoryMatcher 初始化成功")

        # 测试加载分类文件
        category_data = matcher.load_category_json("美妆个护")
        if category_data:
            print("  ✓ 分类文件加载成功")
            categories = matcher.extract_all_categories(category_data)
            print(f"    - 一级分类: {len(categories['l1'])} 个")
            print(f"    - 二级分类: {len(categories['l2'])} 个")
            print(f"    - 三级分类: {len(categories['l3'])} 个")
            print("\n✅ 分类匹配模块正常!\n")
            return True
        else:
            print("  ❌ 无法加载分类文件\n")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {e}\n")
        return False


def test_agent_tools():
    """测试 Agent 工具模块"""
    print("="*60)
    print("🧪 测试 5: Agent 工具模块")
    print("="*60)

    try:
        from agent_tools import get_all_tools
        tools = get_all_tools()
        print(f"  ✓ 成功加载 {len(tools)} 个工具:")

        for tool in tools:
            print(f"    - {tool.name}")

        print("\n✅ Agent 工具模块正常!\n")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}\n")
        return False


def test_output_dir():
    """测试输出目录"""
    print("="*60)
    print("🧪 测试 6: 输出目录")
    print("="*60)

    output_dir = "output"

    if os.path.exists(output_dir):
        print(f"  ✓ 输出目录存在: {output_dir} ✅\n")
        return True
    else:
        print(f"  ⚠️  输出目录不存在,正在创建...")
        os.makedirs(output_dir)
        print(f"  ✓ 已创建输出目录 ✅\n")
        return True


def test_llm_connection():
    """测试 LLM 连接(可选,需要网络)"""
    print("="*60)
    print("🧪 测试 7: LLM 连接 (可选)")
    print("="*60)

    try:
        from langchain_openai import ChatOpenAI
        from dotenv import load_dotenv
        load_dotenv()

        print("  ⏳ 正在测试 LLM 连接...(可能需要几秒)")

        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_BASE_URL"),
            temperature=0.1
        )

        response = llm.invoke("你好,请回复'OK'")
        print(f"  ✓ LLM 响应: {response.content[:50]}...")
        print("\n✅ LLM 连接正常!\n")
        return True

    except Exception as e:
        print(f"  ⚠️  LLM 连接测试失败: {e}")
        print("  这不影响其他功能,但 Agent 可能无法正常工作\n")
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("   🚀 TikTok 达人推荐 Agent - 组件测试")
    print("="*60 + "\n")

    results = []

    # 运行测试
    results.append(("模块导入", test_imports()))
    results.append(("环境变量", test_env_config()))
    results.append(("分类文件", test_category_files()))
    results.append(("分类匹配", test_category_matcher()))
    results.append(("Agent工具", test_agent_tools()))
    results.append(("输出目录", test_output_dir()))

    # LLM 测试(可选)
    print("是否测试 LLM 连接? (需要网络,可能需要几秒)")
    test_llm = input("输入 'y' 测试,其他键跳过: ").strip().lower()
    if test_llm == 'y':
        results.append(("LLM连接", test_llm_connection()))

    # 汇总结果
    print("="*60)
    print("📊 测试结果汇总")
    print("="*60)

    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name:12s}: {status}")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\n总计: {passed}/{total} 项测试通过")

    if passed == total:
        print("\n🎉 所有测试通过! 可以运行 Agent 了:")
        print("   python run_agent.py")
    else:
        print("\n⚠️  部分测试失败,请检查相关配置")
        print("   详细说明请查看 README.md")

    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    main()
