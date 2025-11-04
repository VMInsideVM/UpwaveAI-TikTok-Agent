"""
Multi-Dimensional Influencer Scoring Engine

This module implements a sophisticated scoring system that evaluates influencers
across 6 key dimensions with context-aware reasoning.
"""

import numpy as np
from scipy import stats
from typing import Dict, List, Any, Optional
import json


class InfluencerScorer:
    """
    Multi-dimensional scoring engine for TikTok influencers.

    Scoring Dimensions:
    1. Engagement Score - Interaction rate and viral capability
    2. Sales Score - E-commerce performance and conversion
    3. Audience Match Score - Demographic alignment with target
    4. Content Fit Score - Semantic alignment (requires LLM)
    5. Growth Score - Follower growth and momentum
    6. Stability Score - Consistency and reliability
    """

    def __init__(self, default_weights: Optional[Dict[str, float]] = None):
        """
        Initialize scorer with customizable weights.

        Args:
            default_weights: Dict of dimension weights (must sum to 1.0)
                           Default: balanced weighting
        """
        self.default_weights = default_weights or {
            "engagement": 0.25,
            "sales": 0.20,
            "audience_match": 0.20,
            "content_fit": 0.20,
            "growth": 0.10,
            "stability": 0.05
        }

        # Validate weights
        assert abs(sum(self.default_weights.values()) - 1.0) < 0.01, \
            "Weights must sum to 1.0"

    def score_engagement(self, influencer_data: Dict) -> Dict[str, Any]:
        """
        Score engagement quality.

        Considers:
        - Average interaction rate
        - Viral content rate (pop_rate)
        - Interaction volume vs follower count

        Returns:
            {score: float, reasoning: str, metrics: dict}
        """
        try:
            # Extract key metrics
            stats_info = influencer_data.get('api_responses', {}).get('getStatInfo', {})
            author_index = influencer_data.get('api_responses', {}).get('authorIndex', {})

            # Parse interaction rate (remove %)
            interaction_rate_str = stats_info.get('aweme_avg_interaction_rate', '0%')
            interaction_rate = float(interaction_rate_str.strip('%')) / 100

            # Parse pop rate (viral video rate)
            pop_rate_str = stats_info.get('aweme_pop_rate', '0%')
            pop_rate = float(pop_rate_str.strip('%')) / 100

            # Recent interaction count
            recent_interaction = author_index.get('video_28_avg_interaction_count', 0)

            # Scoring logic
            # Base score: 20% interaction rate = 100 points
            base_score = min(100, (interaction_rate / 0.20) * 100)

            # Viral bonus: up to 30 points
            viral_bonus = min(30, pop_rate * 100)

            # Recent performance: compare recent to overall
            overall_avg = stats_info.get('aweme_avg_play_count', 1)
            recent_avg = author_index.get('video_28_avg_play_count', 0)
            recent_momentum = (recent_avg / max(overall_avg, 1)) * 10

            # Final score (weighted)
            final_score = (base_score * 0.6 + viral_bonus * 0.3 +
                          min(recent_momentum, 10) * 1.0)

            # Generate reasoning
            level = "优秀" if final_score >= 80 else "良好" if final_score >= 60 else "一般"
            reasoning = (
                f"互动率{interaction_rate*100:.1f}%(行业平均15%), "
                f"爆款率{pop_rate*100:.1f}%, "
                f"近期表现{'上升' if recent_momentum > 10 else '平稳'}, "
                f"整体{level}"
            )

            return {
                "score": round(final_score, 1),
                "reasoning": reasoning,
                "metrics": {
                    "interaction_rate": f"{interaction_rate*100:.1f}%",
                    "pop_rate": f"{pop_rate*100:.1f}%",
                    "recent_interaction_count": recent_interaction,
                    "follower_count": author_index.get('follower_count', 0)
                }
            }

        except Exception as e:
            return {
                "score": 50.0,
                "reasoning": f"数据不完整,使用默认分数 ({str(e)})",
                "metrics": {}
            }

    def score_sales(self, influencer_data: Dict) -> Dict[str, Any]:
        """
        Score e-commerce performance.

        Considers:
        - Max/Min GPM (sales per 1000 views)
        - Total sales amount
        - Average customer value
        - Conversion consistency

        Returns:
            {score: float, reasoning: str, metrics: dict}
        """
        try:
            stats_info = influencer_data.get('api_responses', {}).get('getStatInfo', {})
            cargo_summary = influencer_data.get('api_responses', {}).get('cargoSummary', {})

            # Extract GPM metrics
            max_gpm = stats_info.get('aweme_max_gpm', 0)
            min_gpm = stats_info.get('aweme_min_gpm', 0)

            # Sales metrics
            total_sales = stats_info.get('goods_sale_amount', 0)
            per_customer = cargo_summary.get('per_customer_amount', 0)

            # Video sales metrics
            video_avg_sale = cargo_summary.get('video_avg_sale_amount', 0)
            video_avg_sold = cargo_summary.get('video_avg_sold_count', 0)

            # Scoring logic
            # GPM Score: 30 GPM = 100 points
            gpm_score = min(100, (max_gpm / 30.0) * 100)

            # Revenue Score: $100k = 100 points
            revenue_score = min(100, (total_sales / 100000.0) * 100)

            # Customer Value Score: $50 = 100 points
            customer_score = min(100, (per_customer / 50.0) * 100)

            # Consistency: ratio of min to max GPM
            consistency = (min_gpm / max(max_gpm, 0.1)) * 100 if max_gpm > 0 else 0

            # Final weighted score
            final_score = (gpm_score * 0.4 + revenue_score * 0.3 +
                          customer_score * 0.2 + consistency * 0.1)

            # Generate reasoning
            level = "强" if final_score >= 75 else "中等" if final_score >= 50 else "弱"
            reasoning = (
                f"GPM {max_gpm:.2f}(行业优秀>25), "
                f"总销售额${total_sales:,.0f}, "
                f"客单价${per_customer:.0f}, "
                f"带货能力{level}"
            )

            # Add warning for low sales
            if total_sales < 1000:
                reasoning += " ⚠️ 电商数据较少"

            return {
                "score": round(final_score, 1),
                "reasoning": reasoning,
                "metrics": {
                    "max_gpm": round(max_gpm, 2),
                    "total_sales_amount": round(total_sales, 2),
                    "per_customer_amount": round(per_customer, 2),
                    "video_avg_sold_count": video_avg_sold
                }
            }

        except Exception as e:
            return {
                "score": 0.0,
                "reasoning": f"无电商数据或数据异常 ({str(e)})",
                "metrics": {}
            }

    def score_audience_match(self, influencer_data: Dict,
                            target_audience: Dict) -> Dict[str, Any]:
        """
        Score demographic alignment with target audience.

        Args:
            influencer_data: Influencer JSON data
            target_audience: {
                "gender": "female" | "male" | "all",
                "age_range": ["25-34", "35-44"],
                "regions": ["US", "GB"]
            }

        Returns:
            {score: float, reasoning: str, metrics: dict}
        """
        try:
            fans_portrait = influencer_data.get('api_responses', {}).get('fansPortrait', {})
            base_info = influencer_data.get('api_responses', {}).get('baseInfo', {})

            # Gender matching
            gender_dist = fans_portrait.get('follower_genders', [])
            gender_dict = {item['key']: item['value'] for item in gender_dist}

            target_gender = target_audience.get('gender', 'all')
            if target_gender == 'all':
                gender_score = 100
            else:
                gender_score = gender_dict.get(target_gender, 0)

            # Age matching
            age_dist = fans_portrait.get('follower_ages', [])
            age_dict = {item['key']: item['value'] for item in age_dist}

            target_ages = target_audience.get('age_range', [])
            if not target_ages:
                age_score = 100
            else:
                # Sum up matching age brackets
                age_match_pct = sum(age_dict.get(age, 0) for age in target_ages)
                age_score = min(100, age_match_pct * 2)  # Scale up

            # Region matching
            influencer_region = base_info.get('region', 'US')
            target_regions = target_audience.get('regions', [])

            if not target_regions or influencer_region in target_regions:
                region_score = 100
            else:
                region_score = 30  # Partial credit for wrong region

            # Final weighted score
            final_score = (gender_score * 0.4 + age_score * 0.4 + region_score * 0.2)

            # Generate reasoning
            max_gender = gender_dist[0] if gender_dist else {'key': 'unknown', 'value': 0}
            max_age = age_dist[0] if age_dist else {'key': 'unknown', 'value': 0}

            reasoning = (
                f"受众: {max_gender['key']} {max_gender['value']:.0f}%, "
                f"年龄集中{max_age['key']} ({max_age['value']:.0f}%), "
                f"地区{influencer_region}"
            )

            if final_score >= 85:
                reasoning += " - 高度匹配✓"
            elif final_score >= 60:
                reasoning += " - 基本匹配"
            else:
                reasoning += " - 匹配度偏低"

            return {
                "score": round(final_score, 1),
                "reasoning": reasoning,
                "metrics": {
                    "gender_distribution": gender_dict,
                    "age_distribution": age_dict,
                    "region": influencer_region
                }
            }

        except Exception as e:
            return {
                "score": 50.0,
                "reasoning": f"受众数据不完整 ({str(e)})",
                "metrics": {}
            }

    def score_growth(self, influencer_data: Dict) -> Dict[str, Any]:
        """
        Score growth momentum and trend.

        Considers:
        - 28-day follower growth rate
        - Category rank change
        - Time-series trend analysis (if datalist available)

        Returns:
            {score: float, reasoning: str, metrics: dict}
        """
        try:
            author_index = influencer_data.get('api_responses', {}).get('authorIndex', {})
            datalist = influencer_data.get('api_responses', {}).get('datalist', {})

            # Parse growth rates (remove %)
            follower_growth_str = author_index.get('follower_28_count_rate', '0%')
            follower_growth = float(follower_growth_str.strip('%'))

            rank_change_str = author_index.get('category_rank_rate', '0%')
            rank_change = float(rank_change_str.strip('%'))

            # Analyze time-series if available
            follower_data = datalist.get('follower', {}).get('list', [])
            trend_score = 50  # Default neutral

            if len(follower_data) >= 30:
                # Extract recent 30 days
                recent_values = [item.get('value', 0) for item in follower_data[-30:]]

                # Linear regression to find trend
                x = np.arange(len(recent_values))
                slope, _, r_value, _, _ = stats.linregress(x, recent_values)

                # Positive slope = growth
                if slope > 0:
                    trend_score = min(100, 50 + slope * 10)
                else:
                    trend_score = max(0, 50 + slope * 10)

            # Scoring logic
            # Follower growth: 10% = 100 points
            growth_score = min(100, max(0, 50 + follower_growth * 5))

            # Rank improvement
            rank_score = min(100, max(0, 50 - rank_change * 2))

            # Final weighted score
            final_score = (growth_score * 0.5 + rank_score * 0.2 + trend_score * 0.3)

            # Generate reasoning
            if follower_growth > 5:
                level = "高速增长"
            elif follower_growth > 0:
                level = "稳定增长"
            elif follower_growth > -2:
                level = "增长停滞"
            else:
                level = "粉丝下降"

            reasoning = (
                f"近28天粉丝增长{follower_growth:+.2f}%, "
                f"类目排名变化{rank_change:+.2f}%, "
                f"{level}"
            )

            return {
                "score": round(final_score, 1),
                "reasoning": reasoning,
                "metrics": {
                    "follower_28_count_rate": f"{follower_growth:+.2f}%",
                    "category_rank_rate": f"{rank_change:+.2f}%",
                    "trend_analysis": "上升" if trend_score > 50 else "下降"
                }
            }

        except Exception as e:
            return {
                "score": 50.0,
                "reasoning": f"增长数据不足 ({str(e)})",
                "metrics": {}
            }

    def score_stability(self, influencer_data: Dict) -> Dict[str, Any]:
        """
        Score consistency and reliability.

        Considers:
        - Posting frequency stability
        - Engagement rate volatility
        - Revenue consistency (if e-commerce data available)

        Returns:
            {score: float, reasoning: str, metrics: dict}
        """
        try:
            author_index = influencer_data.get('api_responses', {}).get('authorIndex', {})
            datalist = influencer_data.get('api_responses', {}).get('datalist', {})

            # Posting frequency (28 days)
            video_count_28 = author_index.get('aweme_28_count', 0)
            posting_frequency = video_count_28 / 28.0

            # Ideal frequency: 1-3 videos per day
            if 1 <= posting_frequency <= 3:
                frequency_score = 100
            elif posting_frequency < 1:
                frequency_score = max(30, posting_frequency * 100)
            else:
                frequency_score = max(50, 100 - (posting_frequency - 3) * 10)

            # Engagement volatility
            play_data = datalist.get('play', {}).get('list', [])
            volatility_score = 50  # Default

            if len(play_data) >= 30:
                recent_plays = [item.get('value', 0) for item in play_data[-30:]]
                recent_plays = [p for p in recent_plays if p > 0]  # Remove zeros

                if len(recent_plays) >= 10:
                    # Calculate coefficient of variation
                    mean_plays = np.mean(recent_plays)
                    std_plays = np.std(recent_plays)
                    cv = std_plays / max(mean_plays, 1)

                    # Lower CV = higher stability
                    volatility_score = max(0, 100 - cv * 50)

            # Revenue consistency (if available)
            sale_data = datalist.get('sale_amount', {}).get('list', [])
            revenue_score = 50  # Default

            if len(sale_data) >= 30:
                recent_sales = [item.get('value', 0) for item in sale_data[-30:]]
                non_zero_sales = [s for s in recent_sales if s > 0]

                if len(non_zero_sales) >= 10:
                    # Consistency = percentage of days with sales
                    consistency_pct = len(non_zero_sales) / len(recent_sales) * 100
                    revenue_score = consistency_pct

            # Final weighted score
            final_score = (frequency_score * 0.4 + volatility_score * 0.4 +
                          revenue_score * 0.2)

            # Generate reasoning
            level = "高" if final_score >= 75 else "中" if final_score >= 50 else "低"
            reasoning = (
                f"发布频率{posting_frequency:.1f}条/天, "
                f"数据波动{'小' if volatility_score > 60 else '较大'}, "
                f"稳定性{level}"
            )

            return {
                "score": round(final_score, 1),
                "reasoning": reasoning,
                "metrics": {
                    "posting_frequency": round(posting_frequency, 2),
                    "video_count_28": video_count_28,
                    "volatility_level": "低" if volatility_score > 70 else "中" if volatility_score > 40 else "高"
                }
            }

        except Exception as e:
            return {
                "score": 50.0,
                "reasoning": f"稳定性数据不足 ({str(e)})",
                "metrics": {}
            }

    def calculate_total_score(self, dimension_scores: Dict[str, Dict],
                             custom_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Calculate weighted total score from dimension scores.

        Args:
            dimension_scores: Dict of {dimension: {score, reasoning, metrics}}
            custom_weights: Optional custom weights (overrides default)

        Returns:
            {
                "total_score": float,
                "dimension_scores": dict,
                "weights_used": dict,
                "strengths": list,
                "weaknesses": list
            }
        """
        weights = custom_weights or self.default_weights

        # Calculate weighted sum
        total = 0.0
        for dimension, weight in weights.items():
            score = dimension_scores.get(dimension, {}).get('score', 0)
            total += score * weight

        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []

        for dimension, data in dimension_scores.items():
            score = data.get('score', 0)
            if score >= 80:
                strengths.append(f"{dimension}({score:.0f}分)")
            elif score < 50:
                weaknesses.append(f"{dimension}({score:.0f}分)")

        return {
            "total_score": round(total, 1),
            "dimension_scores": dimension_scores,
            "weights_used": weights,
            "strengths": strengths if strengths else ["综合表现均衡"],
            "weaknesses": weaknesses if weaknesses else ["无明显短板"]
        }


# Helper function for batch scoring
def score_influencer(influencer_data: Dict,
                    target_audience: Dict,
                    content_fit_score: float,
                    custom_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Score a single influencer across all dimensions.

    Args:
        influencer_data: Complete influencer JSON data
        target_audience: Target audience dict
        content_fit_score: Pre-calculated content fit score (0-100)
        custom_weights: Optional custom weights

    Returns:
        Complete scoring result with all dimensions
    """
    scorer = InfluencerScorer(custom_weights)

    # Calculate each dimension
    dimension_scores = {
        "engagement": scorer.score_engagement(influencer_data),
        "sales": scorer.score_sales(influencer_data),
        "audience_match": scorer.score_audience_match(influencer_data, target_audience),
        "content_fit": {
            "score": content_fit_score,
            "reasoning": "由LLM内容分析工具计算",
            "metrics": {}
        },
        "growth": scorer.score_growth(influencer_data),
        "stability": scorer.score_stability(influencer_data)
    }

    # Calculate total
    result = scorer.calculate_total_score(dimension_scores, custom_weights)

    # Add influencer metadata
    base_info = influencer_data.get('api_responses', {}).get('baseInfo', {})
    result.update({
        "influencer_id": base_info.get('uid', 'unknown'),
        "nickname": base_info.get('nickname', 'Unknown'),
        "unique_id": base_info.get('unique_id', ''),
        "region": base_info.get('region', 'US')
    })

    return result


if __name__ == "__main__":
    # Test scoring engine
    print("Testing Multi-Dimensional Scoring Engine...")

    # Sample test data
    test_influencer = {
        "api_responses": {
            "baseInfo": {
                "uid": "7170541438504420394",
                "nickname": "TestInfluencer",
                "region": "US"
            },
            "authorIndex": {
                "follower_28_count_rate": "2.5%",
                "category_rank_rate": "-0.3%",
                "aweme_28_count": 45,
                "video_28_avg_interaction_count": 1500
            },
            "getStatInfo": {
                "aweme_avg_interaction_rate": "18.5%",
                "aweme_pop_rate": "12.3%",
                "aweme_max_gpm": 22.5,
                "aweme_min_gpm": 8.2,
                "goods_sale_amount": 45000
            },
            "cargoSummary": {
                "per_customer_amount": 28,
                "video_avg_sale_amount": 120
            },
            "fansPortrait": {
                "follower_genders": [
                    {"key": "female", "value": 72},
                    {"key": "male", "value": 28}
                ],
                "follower_ages": [
                    {"key": "35-44", "value": 28},
                    {"key": "25-34", "value": 25},
                    {"key": "45-54", "value": 20}
                ]
            },
            "datalist": {
                "follower": {"list": []},
                "play": {"list": []}
            }
        }
    }

    target_audience = {
        "gender": "female",
        "age_range": ["25-34", "35-44"],
        "regions": ["US"]
    }

    # Test scoring
    result = score_influencer(test_influencer, target_audience, content_fit_score=85.0)

    print("\n" + "="*60)
    print(f"达人: {result['nickname']} (ID: {result['influencer_id']})")
    print(f"总分: {result['total_score']:.1f}/100")
    print("="*60)

    print("\n各维度得分:")
    for dimension, data in result['dimension_scores'].items():
        print(f"  {dimension:20s}: {data['score']:5.1f}分 - {data['reasoning']}")

    print(f"\n优势: {', '.join(result['strengths'])}")
    print(f"劣势: {', '.join(result['weaknesses'])}")

    print("\n✅ Scoring engine test completed!")
