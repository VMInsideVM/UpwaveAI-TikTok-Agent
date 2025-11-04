"""
Simple test for report generation system (without LLM calls)
"""

import json
from report_tools import LoadInfluencerDataTool, MultiDimensionScorerTool
from report_visualizer import InfluencerVisualizer

print("=" * 60)
print("测试达人推荐报告生成系统")
print("=" * 60)

# Test 1: Load data
print("\n1. 测试数据加载...")
loader = LoadInfluencerDataTool()
result = json.loads(loader._run())

if result.get('success'):
    print(f"✓ 成功加载 {result['loaded_count']} 个达人")
    print(f"  区域分布: {result.get('region_distribution')}")
    influencer_ids = result['influencer_ids'][:5]  # Test with first 5
    print(f"  测试达人: {influencer_ids[:3]}...")
else:
    print(f"✗ 加载失败: {result.get('error')}")
    exit(1)

# Test 2: Simple scoring (without LLM preference analysis)
print("\n2. 测试评分系统 (使用默认偏好)...")
scorer = MultiDimensionScorerTool()

default_preferences = {
    "target_audience": {
        "gender": "female",
        "age_range": ["35-44", "25-34"],
        "regions": ["US"]
    },
    "scoring_weights": {
        "engagement": 0.25,
        "sales": 0.20,
        "audience_match": 0.20,
        "content_fit": 0.20,
        "growth": 0.10,
        "stability": 0.05
    }
}

score_result = json.loads(scorer._run(
    influencer_ids=influencer_ids,
    preferences_json=json.dumps(default_preferences)
))

if score_result.get('success'):
    ranked = score_result['ranked_influencers']
    print(f"✓ 评分完成,Top 3:")
    for i, inf in enumerate(ranked[:3], 1):
        print(f"  #{i}: {inf['nickname']} - {inf['total_score']:.1f}分")
        print(f"      互动:{inf['dimension_scores']['engagement']['score']:.0f} "
              f"销售:{inf['dimension_scores']['sales']['score']:.0f} "
              f"受众:{inf['dimension_scores']['audience_match']['score']:.0f}")
else:
    print(f"✗ 评分失败: {score_result.get('error')}")
    exit(1)

# Test 3: Visualization
print("\n3. 测试可视化生成...")
visualizer = InfluencerVisualizer()

test_influencer = ranked[0]
viz_result = visualizer.generate_all_charts(
    influencer_data={"api_responses": {}},  # Simplified
    dimension_scores=test_influencer['dimension_scores'],
    influencer_id=test_influencer['influencer_id']
)

print(f"✓ 图表生成: {viz_result['summary']}")
for chart in viz_result['charts']:
    print(f"  - {chart['chart_name']}: {chart.get('file_path', 'N/A')}")

print("\n" + "=" * 60)
print("✅ 所有测试通过!")
print("=" * 60)
print("\n提示: 完整的报告生成需要调用LLM,可能需要几分钟时间。")
print("运行命令: python report_agent.py")
