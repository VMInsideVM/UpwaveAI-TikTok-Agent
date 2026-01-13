"""
Professional Data Visualization Module for Influencer Reports

Generates 7 types of interactive and static charts with automatic insights.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from typing import Dict, List, Any, Optional
import os
from datetime import datetime


class InfluencerVisualizer:
    """
    Generates professional visualizations for influencer analysis.

    Supported chart types:
    1. Engagement Trend - Time series of interactions
    2. Sales Funnel - Conversion pipeline
    3. Audience Pyramid - Age/gender demographics
    4. Category Distribution - Product categories pie chart
    5. Growth Curve - Follower growth over time
    6. GPM Box Plot - Sales efficiency distribution
    7. Radar Chart - Multi-dimensional performance
    """

    def __init__(self, output_dir: str = "output/charts"):
        """
        Initialize visualizer with output directory.

        Args:
            output_dir: Directory to save chart files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Professional color scheme
        self.colors = {
            "primary": "#1f77b4",
            "success": "#2ca02c",
            "warning": "#ff7f0e",
            "danger": "#d62728",
            "neutral": "#7f7f7f",
            "purple": "#9467bd",
            "pink": "#e377c2",
            "brown": "#8c564b",
            "lightblue": "#17becf"
        }

    def generate_engagement_trend(self, influencer_data: Dict,
                                  influencer_id: str) -> Dict[str, Any]:
        """
        Generate engagement trend line chart (90 days).

        Shows: plays, likes, comments, shares over time
        Identifies: viral spikes, trend direction

        Returns:
            {file_path, chart_type, insights}
        """
        try:
            datalist = influencer_data.get('api_responses', {}).get('datalist', {})

            # Extract data
            play_data = datalist.get('play', {}).get('list', [])
            like_data = datalist.get('like', {}).get('list', [])
            comment_data = datalist.get('video_comment', {}).get('list', [])
            share_data = datalist.get('video_share', {}).get('list', [])

            if not play_data:
                return {"error": "No engagement data available"}

            # Prepare data
            dates = [item['key'] for item in play_data]
            plays = [item['value'] for item in play_data]
            likes = [item['value'] for item in like_data] if like_data else []
            comments = [item['value'] for item in comment_data] if comment_data else []
            shares = [item['value'] for item in share_data] if share_data else []

            # Create figure with secondary y-axis
            fig = make_subplots(
                rows=1, cols=1,
                specs=[[{"secondary_y": True}]]
            )

            # Add traces
            fig.add_trace(
                go.Scatter(x=dates, y=plays, name="播放量",
                          line=dict(color=self.colors["primary"], width=2),
                          fill='tozeroy', fillcolor='rgba(31, 119, 180, 0.1)'),
                secondary_y=False
            )

            if likes:
                fig.add_trace(
                    go.Scatter(x=dates, y=likes, name="点赞数",
                              line=dict(color=self.colors["success"], width=1.5)),
                    secondary_y=True
                )

            if comments:
                fig.add_trace(
                    go.Scatter(x=dates, y=comments, name="评论数",
                              line=dict(color=self.colors["warning"], width=1.5)),
                    secondary_y=True
                )

            if shares:
                fig.add_trace(
                    go.Scatter(x=dates, y=shares, name="分享数",
                              line=dict(color=self.colors["purple"], width=1.5)),
                    secondary_y=True
                )

            # Update layout
            fig.update_layout(
                title=dict(text="互动数据趋势 (近90天)", font=dict(size=20)),
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=500,
                template="plotly_white"
            )

            fig.update_xaxes(title_text="日期", tickangle=-45)
            fig.update_yaxes(title_text="播放量", secondary_y=False)
            fig.update_yaxes(title_text="互动数", secondary_y=True)

            # Save chart
            filename = f"{influencer_id}_engagement_trend.html"
            filepath = os.path.join(self.output_dir, filename)
            fig.write_html(filepath)

            # Generate insights
            insights = self._analyze_trend_insights(plays, dates)

            return {
                "file_path": filepath,
                "chart_type": "line",
                "insights": insights
            }

        except Exception as e:
            return {"error": str(e)}

    def generate_sales_funnel(self, influencer_data: Dict,
                              influencer_id: str) -> Dict[str, Any]:
        """
        Generate sales conversion funnel chart.

        Shows: impressions → engagements → sales pipeline

        Returns:
            {file_path, chart_type, insights}
        """
        try:
            stats_info = influencer_data.get('api_responses', {}).get('getStatInfo', {})
            cargo_summary = influencer_data.get('api_responses', {}).get('cargoSummary', {})

            # Calculate funnel stages
            total_plays = stats_info.get('aweme_play_count', 0)
            avg_interaction_rate = float(stats_info.get('aweme_avg_interaction_rate', '0%').strip('%')) / 100
            total_interactions = int(total_plays * avg_interaction_rate)

            total_sold = cargo_summary.get('total_sold_count', 0)
            total_revenue = cargo_summary.get('total_sale_amount', 0)

            # Funnel stages
            stages = ['曝光量', '互动量', '销售件数', '销售额']
            values = [total_plays, total_interactions, total_sold, total_revenue]

            # Normalize for visualization (use log scale for revenue)
            if total_revenue > 0:
                values_normalized = [
                    total_plays,
                    total_interactions,
                    total_sold * 100,  # Scale up for visibility
                    total_revenue / 10  # Scale down
                ]
            else:
                values_normalized = values[:3]
                stages = stages[:3]

            # Create funnel chart
            fig = go.Figure(go.Funnel(
                y=stages,
                x=values_normalized,
                textinfo="value+percent initial",
                marker=dict(color=[self.colors["lightblue"], self.colors["primary"],
                                   self.colors["success"], self.colors["warning"]])
            ))

            fig.update_layout(
                title=dict(text="销售转化漏斗", font=dict(size=20)),
                height=500,
                template="plotly_white"
            )

            # Save chart
            filename = f"{influencer_id}_sales_funnel.html"
            filepath = os.path.join(self.output_dir, filename)
            fig.write_html(filepath)

            # Calculate conversion rates
            engagement_rate = (total_interactions / max(total_plays, 1)) * 100
            conversion_rate = (total_sold / max(total_interactions, 1)) * 100 if total_interactions > 0 else 0

            insights = [
                f"互动转化率{engagement_rate:.2f}%",
                f"销售转化率{conversion_rate:.2f}%" if total_sold > 0 else "暂无销售数据",
                f"总计销售{total_sold}件,收入${total_revenue:,.0f}" if total_revenue > 0 else "无电商数据"
            ]

            return {
                "file_path": filepath,
                "chart_type": "funnel",
                "insights": insights
            }

        except Exception as e:
            return {"error": str(e)}

    def generate_audience_pyramid(self, influencer_data: Dict,
                                  influencer_id: str) -> Dict[str, Any]:
        """
        Generate age-gender demographic pyramid chart.

        Returns:
            {file_path, chart_type, insights}
        """
        try:
            fans_portrait = influencer_data.get('api_responses', {}).get('fansPortrait', {})

            gender_dist = fans_portrait.get('follower_genders', [])
            age_dist = fans_portrait.get('follower_ages', [])

            if not gender_dist or not age_dist:
                return {"error": "No audience demographic data"}

            # Get gender percentages
            gender_dict = {item['key']: item['value'] for item in gender_dist}
            male_pct = gender_dict.get('male', 0)
            female_pct = gender_dict.get('female', 0)

            # Create pyramid data
            age_brackets = [item['key'] for item in age_dist]
            age_values = [item['value'] for item in age_dist]

            # Distribute by gender (approximate)
            male_values = [-v * (male_pct / 100) for v in age_values]
            female_values = [v * (female_pct / 100) for v in age_values]

            # Create horizontal bar chart (pyramid style)
            fig = go.Figure()

            fig.add_trace(go.Bar(
                y=age_brackets,
                x=male_values,
                name='男性',
                orientation='h',
                marker=dict(color=self.colors["primary"]),
                text=[f"{abs(v):.1f}%" for v in male_values],
                textposition='inside'
            ))

            fig.add_trace(go.Bar(
                y=age_brackets,
                x=female_values,
                name='女性',
                orientation='h',
                marker=dict(color=self.colors["pink"]),
                text=[f"{v:.1f}%" for v in female_values],
                textposition='inside'
            ))

            fig.update_layout(
                title=dict(text="受众年龄-性别分布", font=dict(size=20)),
                barmode='overlay',
                bargap=0.1,
                xaxis=dict(title='百分比 (%)', tickvals=[], showticklabels=False),
                yaxis=dict(title='年龄段'),
                height=500,
                template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            # Add vertical line at 0
            fig.add_vline(x=0, line_width=1, line_color="black")

            # Save chart
            filename = f"{influencer_id}_audience_pyramid.html"
            filepath = os.path.join(self.output_dir, filename)
            fig.write_html(filepath)

            # Generate insights
            dominant_age = age_dist[0]['key'] if age_dist else 'unknown'
            dominant_age_pct = age_dist[0]['value'] if age_dist else 0

            insights = [
                f"性别分布: 女性{female_pct:.0f}%, 男性{male_pct:.0f}%",
                f"年龄集中在{dominant_age} ({dominant_age_pct:.0f}%)",
                f"{'女性为主' if female_pct > 60 else '男性为主' if male_pct > 60 else '性别均衡'}"
            ]

            return {
                "file_path": filepath,
                "chart_type": "pyramid",
                "insights": insights
            }

        except Exception as e:
            return {"error": str(e)}

    def generate_category_distribution(self, influencer_data: Dict,
                                       influencer_id: str) -> Dict[str, Any]:
        """
        Generate product category distribution pie chart.

        Returns:
            {file_path, chart_type, insights}
        """
        try:
            cargo_summary = influencer_data.get('api_responses', {}).get('cargoSummary', {})

            # Get category data
            category_list = cargo_summary.get('most_sold_category_list', [])

            if not category_list:
                return {"error": "No product category data"}

            # Prepare data
            categories = [item['key'] for item in category_list]
            values = [item['value'] for item in category_list]

            # Create pie chart
            fig = go.Figure(data=[go.Pie(
                labels=categories,
                values=values,
                hole=0.3,  # Donut chart
                marker=dict(colors=[self.colors["primary"], self.colors["success"],
                                   self.colors["warning"], self.colors["purple"],
                                   self.colors["pink"]]),
                textinfo='label+percent',
                textposition='auto'
            )])

            fig.update_layout(
                title=dict(text="销售品类分布", font=dict(size=20)),
                height=500,
                template="plotly_white",
                showlegend=True
            )

            # Save chart
            filename = f"{influencer_id}_category_pie.html"
            filepath = os.path.join(self.output_dir, filename)
            fig.write_html(filepath)

            # Generate insights
            top_category = category_list[0] if category_list else {}
            insights = [
                f"主要销售品类: {top_category.get('key', 'unknown')} ({top_category.get('value', 0):.1f}%)",
                f"品类集中度: {'高' if top_category.get('value', 0) > 50 else '中' if top_category.get('value', 0) > 30 else '分散'}",
                f"共涉及{len(category_list)}个主要品类"
            ]

            return {
                "file_path": filepath,
                "chart_type": "pie",
                "insights": insights
            }

        except Exception as e:
            return {"error": str(e)}

    def generate_growth_quality(self, influencer_data: Dict,
                                influencer_id: str) -> Dict[str, Any]:
        """
        Generate follower growth quality analysis chart.

        Shows: Follower growth trend + quality index + health metrics
        Identifies: Suspicious growth spikes, engagement authenticity

        Returns:
            {file_path, chart_type, insights}
        """
        try:
            api_data = influencer_data.get('api_responses', {})
            datalist = api_data.get('datalist', {})
            author_idx = api_data.get('authorIndex', {})
            stat_info = api_data.get('getStatInfo', {})

            # Extract follower trend (90 days)
            follower_data = datalist.get('follower', {}).get('list', [])
            if len(follower_data) < 10:
                return {"error": "Insufficient follower data"}

            dates = [item['key'] for item in follower_data]
            followers = [item['value'] for item in follower_data]

            # Extract engagement data for quality calculation
            like_data = datalist.get('like', {}).get('list', [])
            comment_data = datalist.get('video_comment', {}).get('list', [])

            likes = [item['value'] for item in like_data] if like_data else [0] * len(followers)
            comments = [item['value'] for item in comment_data] if comment_data else [0] * len(followers)

            # Calculate quality index (engagement per 1000 followers)
            quality_index = []
            for i, f in enumerate(followers):
                if f > 0:
                    engagement = (likes[i] + comments[i]) if i < len(likes) else 0
                    quality = (engagement / f) * 1000
                    quality_index.append(quality)
                else:
                    quality_index.append(0)

            # Detect anomalies (suspicious growth spikes)
            follower_changes = np.diff(followers)
            mean_change = np.mean(follower_changes)
            std_change = np.std(follower_changes)
            threshold = mean_change + 3 * std_change
            anomaly_indices = [i+1 for i, change in enumerate(follower_changes) if change > threshold]

            # Create figure with secondary y-axis
            fig = go.Figure()

            # Follower trend (left y-axis)
            fig.add_trace(go.Scatter(
                x=dates,
                y=followers,
                name='粉丝数',
                line=dict(color=self.colors['primary'], width=3),
                yaxis='y'
            ))

            # Quality index (right y-axis)
            fig.add_trace(go.Scatter(
                x=dates,
                y=quality_index,
                name='质量指数',
                line=dict(color=self.colors['success'], width=2, dash='dot'),
                yaxis='y2'
            ))

            # Mark anomalies
            if anomaly_indices:
                anomaly_dates = [dates[i] for i in anomaly_indices]
                anomaly_values = [followers[i] for i in anomaly_indices]
                fig.add_trace(go.Scatter(
                    x=anomaly_dates,
                    y=anomaly_values,
                    mode='markers',
                    name='异常增长',
                    marker=dict(color=self.colors['danger'], size=10, symbol='star'),
                    yaxis='y'
                ))

            # Layout with dual y-axes
            fig.update_layout(
                title="粉丝增长质量分析",
                xaxis=dict(title="日期"),
                yaxis=dict(
                    title=dict(text="粉丝数", font=dict(color=self.colors['primary'])),
                    tickfont=dict(color=self.colors['primary'])
                ),
                yaxis2=dict(
                    title=dict(text="质量指数", font=dict(color=self.colors['success'])),
                    tickfont=dict(color=self.colors['success']),
                    overlaying='y',
                    side='right'
                ),
                hovermode='x unified',
                template='plotly_white',
                height=500
            )

            # Save chart
            filename = f"{influencer_id}_growth_quality.html"
            filepath = os.path.join(self.output_dir, filename)
            fig.write_html(filepath)

            # Generate insights
            insights = []

            # Growth stability
            cv = std_change / abs(mean_change) if mean_change != 0 else 0
            if cv < 0.3:
                insights.append(f"增长稳定性优秀 (CV={cv:.2f})")
            elif cv < 0.6:
                insights.append(f"增长较稳定 (CV={cv:.2f})")
            else:
                insights.append(f"增长波动较大 (CV={cv:.2f})")

            # Quality assessment
            avg_quality = np.mean(quality_index)
            if avg_quality > 20:
                insights.append(f"互动质量优秀 (指数{avg_quality:.1f})")
            elif avg_quality > 10:
                insights.append(f"互动质量良好 (指数{avg_quality:.1f})")
            else:
                insights.append(f"互动质量待提升 (指数{avg_quality:.1f})")

            # Anomaly detection
            if anomaly_indices:
                insights.append(f"检测到{len(anomaly_indices)}次异常增长,需关注真实性")
            else:
                insights.append("增长曲线自然,无异常峰值")

            # Add additional metrics if available (skip if "-" or missing)
            growth_rate = author_idx.get('follower_28_count_rate')
            if growth_rate and growth_rate != '-':
                insights.append(f"28天增长率: {growth_rate}")

            pop_rate = stat_info.get('aweme_pop_rate')
            if pop_rate and pop_rate != '-':
                insights.append(f"爆款率: {pop_rate}")

            return {
                "file_path": filepath,
                "chart_type": "dual_line",
                "insights": insights
            }

        except Exception as e:
            return {"error": str(e)}

    def generate_radar_chart(self, dimension_scores: Dict[str, Any],
                            influencer_id: str) -> Dict[str, Any]:
        """
        Generate multi-dimensional performance radar chart.

        Args:
            dimension_scores: Dict of {dimension: {score, reasoning, metrics}}
            influencer_id: Influencer ID

        Returns:
            {file_path, chart_type, insights}
        """
        try:
            # Extract dimensions and scores
            dimensions = ['互动能力', '带货能力', '受众匹配', '内容契合', '成长性', '稳定性']
            dimension_keys = ['engagement', 'sales', 'audience_match', 'content_fit', 'growth', 'stability']

            scores = [dimension_scores.get(key, {}).get('score', 0) for key in dimension_keys]

            # Create radar chart
            fig = go.Figure()

            fig.add_trace(go.Scatterpolar(
                r=scores,
                theta=dimensions,
                fill='toself',
                fillcolor='rgba(31, 119, 180, 0.3)',
                line=dict(color=self.colors["primary"], width=2),
                marker=dict(size=8),
                name='得分'
            ))

            # Add average reference line (60 points)
            fig.add_trace(go.Scatterpolar(
                r=[60] * len(dimensions),
                theta=dimensions,
                line=dict(color=self.colors["neutral"], width=1, dash='dash'),
                name='及格线(60分)'
            ))

            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 100], tickmode='linear', tick0=0, dtick=20)
                ),
                title=dict(text="六维能力雷达图", font=dict(size=20)),
                height=500,
                template="plotly_white",
                showlegend=True
            )

            # Save chart
            filename = f"{influencer_id}_radar.html"
            filepath = os.path.join(self.output_dir, filename)
            fig.write_html(filepath)

            # Generate insights
            max_score = max(scores)
            min_score = min(scores)
            max_dim = dimensions[scores.index(max_score)]
            min_dim = dimensions[scores.index(min_score)]

            insights = [
                f"最强维度: {max_dim} ({max_score:.0f}分)",
                f"最弱维度: {min_dim} ({min_score:.0f}分)",
                f"综合均衡度: {'优秀' if max_score - min_score < 20 else '中等' if max_score - min_score < 40 else '差异大'}"
            ]

            return {
                "file_path": filepath,
                "chart_type": "radar",
                "insights": insights
            }

        except Exception as e:
            return {"error": str(e)}

    def generate_all_charts(self, influencer_data: Dict,
                           dimension_scores: Dict[str, Any],
                           influencer_id: str) -> Dict[str, List[Dict]]:
        """
        Generate all charts for an influencer.

        Args:
            influencer_data: Complete influencer JSON data
            dimension_scores: Scoring results
            influencer_id: Influencer ID

        Returns:
            {
                "charts": [list of chart results],
                "summary": "X charts generated successfully"
            }
        """
        charts = []

        # Generate each chart
        chart_generators = [
            ("engagement_trend", self.generate_engagement_trend),
            ("sales_funnel", self.generate_sales_funnel),
            ("audience_pyramid", self.generate_audience_pyramid),
            ("category_distribution", self.generate_category_distribution),
            ("growth_quality", self.generate_growth_quality),
        ]

        for chart_name, generator in chart_generators:
            result = generator(influencer_data, influencer_id)
            if "error" not in result:
                result["chart_name"] = chart_name
                charts.append(result)

        # Generate radar chart separately (needs dimension_scores)
        radar_result = self.generate_radar_chart(dimension_scores, influencer_id)
        if "error" not in radar_result:
            radar_result["chart_name"] = "radar"
            charts.append(radar_result)

        return {
            "charts": charts,
            "summary": f"{len(charts)}个图表生成成功"
        }

    def _analyze_trend_insights(self, values: List[float], dates: List[str]) -> List[str]:
        """
        Analyze time series data for insights.

        Args:
            values: List of metric values
            dates: List of date strings

        Returns:
            List of insight strings
        """
        insights = []

        if len(values) < 10:
            return ["数据点不足,无法分析趋势"]

        # Find spikes (values > mean + 2*std)
        mean_val = np.mean(values)
        std_val = np.std(values)
        threshold = mean_val + 2 * std_val

        spikes = [(i, v) for i, v in enumerate(values) if v > threshold]

        if spikes:
            spike_date = dates[spikes[0][0]]
            spike_value = spikes[0][1]
            insights.append(f"{spike_date}出现爆款,播放量{spike_value:,.0f}(+{((spike_value/mean_val)-1)*100:.0f}%)")

        # Overall trend
        from scipy import stats as sp_stats
        if len(values) >= 30:
            recent_30 = values[-30:]
            x = np.arange(len(recent_30))
            slope, _, r_value, _, _ = sp_stats.linregress(x, recent_30)

            if slope > 0:
                insights.append(f"近30天趋势上升,R²={r_value**2:.2f}")
            elif slope < 0:
                insights.append(f"近30天趋势下降,R²={r_value**2:.2f}")
            else:
                insights.append("近30天趋势平稳")

        # Volatility
        cv = std_val / max(mean_val, 1)
        if cv < 0.5:
            insights.append("数据波动小,表现稳定")
        elif cv > 1.0:
            insights.append("数据波动大,表现不稳定")

        return insights if insights else ["整体表现平稳"]


if __name__ == "__main__":
    print("Testing Influencer Visualizer...")

    # Sample test data (use real data structure)
    test_data = {
        "api_responses": {
            "baseInfo": {"uid": "test123", "nickname": "TestUser"},
            "getStatInfo": {
                "aweme_play_count": 1000000,
                "aweme_avg_interaction_rate": "18.5%",
                "goods_sale_amount": 50000
            },
            "cargoSummary": {
                "total_sold_count": 2000,
                "total_sale_amount": 50000,
                "most_sold_category_list": [
                    {"key": "美妆个护", "value": 45.5},
                    {"key": "保健", "value": 30.2},
                    {"key": "食品饮料", "value": 24.3}
                ]
            },
            "fansPortrait": {
                "follower_genders": [
                    {"key": "female", "value": 70},
                    {"key": "male", "value": 30}
                ],
                "follower_ages": [
                    {"key": "35-44", "value": 30},
                    {"key": "25-34", "value": 25},
                    {"key": "45-54", "value": 20},
                    {"key": "18-24", "value": 15},
                    {"key": "55+", "value": 10}
                ]
            },
            "datalist": {
                "play": {
                    "list": [{"key": f"2025-{i//30+1:02d}-{i%30+1:02d}", "value": 10000 + i*100 + np.random.randint(-2000, 2000)}
                            for i in range(90)]
                }
            }
        }
    }

    test_scores = {
        "engagement": {"score": 75},
        "sales": {"score": 60},
        "audience_match": {"score": 85},
        "content_fit": {"score": 80},
        "growth": {"score": 55},
        "stability": {"score": 70}
    }

    visualizer = InfluencerVisualizer()

    # Test radar chart
    print("\n生成雷达图...")
    radar_result = visualizer.generate_radar_chart(test_scores, "test123")
    if "error" not in radar_result:
        print(f"✓ 雷达图已保存: {radar_result['file_path']}")
        print(f"  洞察: {radar_result['insights']}")

    # Test pyramid
    print("\n生成受众金字塔...")
    pyramid_result = visualizer.generate_audience_pyramid(test_data, "test123")
    if "error" not in pyramid_result:
        print(f"✓ 金字塔图已保存: {pyramid_result['file_path']}")
        print(f"  洞察: {pyramid_result['insights']}")

    # Test category pie
    print("\n生成品类饼图...")
    pie_result = visualizer.generate_category_distribution(test_data, "test123")
    if "error" not in pie_result:
        print(f"✓ 饼图已保存: {pie_result['file_path']}")
        print(f"  洞察: {pie_result['insights']}")

    print("\n✅ Visualizer test completed!")
