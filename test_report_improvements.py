"""
测试报告系统改进
验证16:9布局、图表完整显示、中文翻译和独立目录结构
"""

from report_agent import TikTokInfluencerReportAgent
import os

def test_report_generation():
    """测试报告生成功能"""
    print("\n" + "="*70)
    print("测试报告系统改进")
    print("="*70)

    # Initialize agent
    agent = TikTokInfluencerReportAgent()

    # Test parameters
    json_file = "tiktok_达人推荐_女士香水_20251105_132850.json"
    user_query = "推广Dior Miss Dior女士香水,目标美国市场"
    target_count = 3
    product_info = "Dior Miss Dior是一款经典女士香水,主打优雅浪漫风格,目标人群为25-45岁都市女性"

    print(f"\n测试参数:")
    print(f"  数据文件: {json_file}")
    print(f"  用户需求: {user_query}")
    print(f"  目标数量: Top {target_count}")
    print(f"  产品信息: {product_info[:50]}...")

    # Generate report
    print("\n" + "-"*70)
    report_path = agent.generate_report(
        json_filename=json_file,
        user_query=user_query,
        target_count=target_count,
        product_info=product_info
    )

    # Verify results
    print("\n" + "="*70)
    print("验证结果:")
    print("="*70)

    if report_path and os.path.exists(report_path):
        print(f"✅ 报告生成成功!")
        print(f"   路径: {report_path}")

        # Check directory structure
        report_dir = os.path.dirname(report_path)
        charts_dir = os.path.join(report_dir, "charts")

        print(f"\n📁 目录结构检查:")
        print(f"   报告目录: {report_dir}")

        if os.path.exists(charts_dir):
            chart_files = [f for f in os.listdir(charts_dir) if f.endswith('.html')]
            print(f"   ✅ charts子目录存在")
            print(f"   📊 图表文件数: {len(chart_files)}")
            if chart_files:
                print(f"   示例: {chart_files[0]}")
        else:
            print(f"   ⚠️ charts目录不存在")

        # Check file size
        file_size = os.path.getsize(report_path) / 1024
        print(f"\n📄 报告文件:")
        print(f"   大小: {file_size:.1f} KB")

        # Read a snippet to verify content
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"   内容长度: {len(content)} 字符")

            # Check for key improvements
            checks = {
                "16:9布局 (max-width: 1600px)": "max-width: 1600px" in content,
                "双列达人卡片": "grid-template-columns: 1fr 1fr" in content,
                "图表2列布局": "grid-template-columns: repeat(2, 1fr)" in content,
                "图表相对路径": "./charts/" in content,
            }

            print(f"\n✨ 改进验证:")
            for check_name, passed in checks.items():
                status = "✅" if passed else "❌"
                print(f"   {status} {check_name}")

        print(f"\n💡 提示: 在浏览器中打开查看完整效果")
        print(f"   file:///{os.path.abspath(report_path).replace(chr(92), '/')}")

    else:
        print(f"❌ 报告生成失败")
        if report_path:
            print(f"   预期路径: {report_path}")

    print("\n" + "="*70)

if __name__ == "__main__":
    test_report_generation()
