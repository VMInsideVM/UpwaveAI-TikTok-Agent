"""
验证报告的双列对称布局
"""
import os

def verify_layout():
    """验证最新生成报告的布局特性"""
    # 找到最新的报告
    reports_dir = "output/reports"
    if not os.path.exists(reports_dir):
        print("❌ 报告目录不存在")
        return

    subdirs = [d for d in os.listdir(reports_dir) if os.path.isdir(os.path.join(reports_dir, d))]
    if not subdirs:
        print("❌ 没有找到报告")
        return

    latest_dir = sorted(subdirs)[-1]
    report_path = os.path.join(reports_dir, latest_dir, "report.html")

    if not os.path.exists(report_path):
        print(f"❌ 报告文件不存在: {report_path}")
        return

    print(f"📄 分析报告: {report_path}\n")

    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 验证布局特性
    checks = {
        "容器宽度1600px": "max-width: 1600px" in content,
        "双列对称布局CSS": "card-content-grid" in content and "grid-template-columns: 1fr 1fr" in content,
        "图表2列布局": 'grid-template-columns: repeat(2, 1fr)' in content,
        "达人卡片单列显示": ".tier-section" in content and "grid-template-columns: 1fr 1fr" not in content.split(".tier-section")[1].split("}")[0] if ".tier-section" in content else False,
    }

    print("=" * 60)
    print("布局特性验证")
    print("=" * 60)

    for name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {name}")

    # 统计card-content-grid使用次数
    grid_count = content.count('<div class="card-content-grid">')
    print(f"\n📊 统计:")
    print(f"  双列对称布局(优势/风险)使用次数: {grid_count}")

    # 统计charts-container使用次数
    charts_container_count = content.count('<div class="charts-container">')
    print(f"  双列图表容器使用次数: {charts_container_count}")

    # 统计达人卡片数量
    card_count = content.count('<div class="influencer-card">')
    print(f"  达人卡片总数: {card_count}")

    # 统计图表wrapper数量
    chart_wrapper_count = content.count('<div class="chart-wrapper">')
    print(f"  图表总数: {chart_wrapper_count}")

    # 检查图表文件数量
    charts_dir = os.path.join(reports_dir, latest_dir, "charts")
    if os.path.exists(charts_dir):
        chart_files = len([f for f in os.listdir(charts_dir) if f.endswith('.html')])
        print(f"  图表文件数: {chart_files}")

    print(f"\n💡 在浏览器中打开查看效果:")
    print(f"  file:///{os.path.abspath(report_path).replace(chr(92), '/')}")
    print("\n📝 布局说明:")
    print("  ✓ 每个达人卡片纵向排列(单列)")
    print("  ✓ 卡片内'核心优势'和'潜在风险'左右对称(双列)")
    print("  ✓ 图表区域2列展示")
    print("  ✓ 容器宽度1600px适配16:9横屏")
    print("=" * 60)

if __name__ == "__main__":
    verify_layout()
