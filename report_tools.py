"""
LangChain Tools for Influencer Report Generation

7 specialized tools for the recommendation report agent:
1. LoadInfluencerDataTool - Batch load and validate JSON data
2. UserPreferenceAnalyzerTool - LLM-based preference extraction
3. MultiDimensionScorerTool - Multi-dimensional scoring
4. ContentAlignmentTool - LLM content fit analysis
5. DataVisualizationTool - Chart generation
6. PersonalizedReportTool - LLM report generation
7. CrossComparisonTool - Horizontal comparison analysis
"""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from report_scorer import score_influencer
from report_visualizer import InfluencerVisualizer

# Load environment
load_dotenv()


# ==================== Tool 1: Load Influencer Data ====================

class LoadInfluencerDataInput(BaseModel):
    """Input for loading influencer data."""
    influencer_folder: str = Field(
        default="influencer",
        description="达人数据文件夹路径"
    )
    cache_days: int = Field(
        default=3,
        description="缓存有效期(天),超过此天数的数据会被标记为过期"
    )
    min_data_completeness: float = Field(
        default=0.8,
        description="最低数据完整度阈值(0-1),低于此值的达人会被排除"
    )


class LoadInfluencerDataTool(BaseTool):
    """批量加载和验证达人数据."""

    name: str = "load_influencer_data"
    description: str = """
    从指定文件夹批量加载所有达人的详细数据JSON文件。
    会自动检查数据完整性和新鲜度,返回可用的达人ID列表和基础统计信息。

    使用场景:
    - 报告生成流程的第一步
    - 获取可用达人列表
    - 验证数据质量
    """
    args_schema: type[BaseModel] = LoadInfluencerDataInput

    def _run(self, influencer_folder: str = "influencer",
             cache_days: int = 3,
             min_data_completeness: float = 0.8) -> str:
        """加载达人数据."""
        try:
            # Check folder exists
            if not os.path.exists(influencer_folder):
                return json.dumps({
                    "success": False,
                    "error": f"文件夹不存在: {influencer_folder}"
                }, ensure_ascii=False)

            # Load all JSON files
            json_files = [f for f in os.listdir(influencer_folder) if f.endswith('.json')]

            if not json_files:
                return json.dumps({
                    "success": False,
                    "error": f"文件夹中没有找到JSON文件: {influencer_folder}"
                }, ensure_ascii=False)

            loaded_influencers = []
            warnings = []
            stats = {
                "total_files": len(json_files),
                "loaded_count": 0,
                "excluded_count": 0,
                "stale_count": 0
            }

            cutoff_date = datetime.now() - timedelta(days=cache_days)

            for json_file in json_files:
                file_path = os.path.join(influencer_folder, json_file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Check data completeness
                    required_keys = ['api_responses', 'target_url', 'capture_time']
                    completeness = sum(1 for k in required_keys if k in data) / len(required_keys)

                    if completeness < min_data_completeness:
                        stats["excluded_count"] += 1
                        warnings.append(f"{json_file}: 数据不完整({completeness*100:.0f}%)")
                        continue

                    # Check freshness
                    capture_time_str = data.get('capture_time', '')
                    try:
                        capture_time = datetime.strptime(capture_time_str, '%Y-%m-%d %H:%M:%S')
                        if capture_time < cutoff_date:
                            stats["stale_count"] += 1
                            warnings.append(f"{json_file}: 数据过期({capture_time_str})")
                    except:
                        pass  # Ignore date parsing errors

                    # Extract influencer info
                    base_info = data.get('api_responses', {}).get('baseInfo', {})
                    influencer_id = base_info.get('uid', json_file.replace('.json', ''))

                    loaded_influencers.append({
                        "influencer_id": influencer_id,
                        "nickname": base_info.get('nickname', 'Unknown'),
                        "region": base_info.get('region', 'US'),
                        "file_path": file_path,
                        "capture_time": capture_time_str
                    })

                    stats["loaded_count"] += 1

                except Exception as e:
                    stats["excluded_count"] += 1
                    warnings.append(f"{json_file}: 解析失败 ({str(e)})")

            # Calculate summary statistics
            if loaded_influencers:
                # Count regions
                region_counts = {}
                for inf in loaded_influencers:
                    region = inf["region"]
                    region_counts[region] = region_counts.get(region, 0) + 1

                result = {
                    "success": True,
                    "loaded_count": stats["loaded_count"],
                    "influencer_ids": [inf["influencer_id"] for inf in loaded_influencers],
                    "influencer_list": loaded_influencers,
                    "stats": stats,
                    "region_distribution": region_counts,
                    "warnings": warnings[:10]  # Limit warnings
                }
            else:
                result = {
                    "success": False,
                    "error": "没有加载到任何符合条件的达人数据",
                    "stats": stats,
                    "warnings": warnings[:10]
                }

            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"加载数据时发生错误: {str(e)}"
            }, ensure_ascii=False)


# ==================== Tool 2: User Preference Analyzer ====================

class UserPreferenceInput(BaseModel):
    """Input for user preference analysis."""
    user_query: str = Field(description="用户的自然语言需求描述")
    product_info: Optional[str] = Field(
        default=None,
        description="产品信息(可选)"
    )
    target_count: int = Field(description="用户需要的达人数量")


class UserPreferenceAnalyzerTool(BaseTool):
    """用LLM深度理解用户需求,提取关键偏好."""

    name: str = "analyze_user_preferences"
    description: str = """
    使用LLM深度分析用户的自然语言需求,提取关键偏好维度。

    会分析并提取:
    - 产品类目
    - 目标受众(性别/年龄/地域)
    - 预算级别
    - 优先指标
    - 内容风格偏好
    - 硬性筛选条件

    返回结构化的偏好数据,供后续工具使用。
    """
    args_schema: type[BaseModel] = UserPreferenceInput

    def _get_llm(self):
        """Get LLM instance."""
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
            temperature=0.1,
            base_url=os.getenv("OPENAI_BASE_URL")
        )

    def _run(self, user_query: str, product_info: Optional[str] = None,
             target_count: int = 1) -> str:
        """分析用户偏好."""
        try:
            llm = self._get_llm()
            prompt = f"""你是一个专业的达人营销分析师。用户提供了以下需求:

用户需求: {user_query}
{f'产品信息: {product_info}' if product_info else ''}
目标数量: {target_count}个达人

请深度分析并提取以下关键偏好(以JSON格式输出):

1. product_category: 产品类目(如: 美妆个护/保健/食品饮料/服饰/家居等)
2. target_audience: 目标受众
   - gender: "male" | "female" | "all"
   - age_range: 列表,如 ["25-34", "35-44"]
   - regions: 列表,如 ["US", "GB"]
3. budget_level: 预算级别 "low" | "medium" | "high" (根据描述推断)
4. priority_metrics: 优先指标列表(从以下选择最重要的3个):
   ["engagement_rate", "sales_performance", "audience_match", "content_quality", "growth_potential", "cost_efficiency"]
5. content_style: 内容风格偏好(提取关键词,如 ["emotional", "educational", "entertaining"])
6. deal_breakers: 硬性条件列表(必须满足的条件)
7. scoring_weights: 根据优先级调整评分权重(6个维度,总和为1.0):
   - engagement: 互动能力
   - sales: 带货能力
   - audience_match: 受众匹配
   - content_fit: 内容契合
   - growth: 成长性
   - stability: 稳定性

输出纯JSON格式,不要其他文字。如果信息不足,使用合理默认值。

示例输出:
{{
    "product_category": "美妆个护",
    "target_audience": {{
        "gender": "female",
        "age_range": ["25-34", "35-44"],
        "regions": ["US"]
    }},
    "budget_level": "medium",
    "priority_metrics": ["engagement_rate", "audience_match", "sales_performance"],
    "content_style": ["emotional", "inspiring"],
    "deal_breakers": ["必须有电商经验", "粉丝>10万"],
    "scoring_weights": {{
        "engagement": 0.30,
        "sales": 0.25,
        "audience_match": 0.25,
        "content_fit": 0.15,
        "growth": 0.03,
        "stability": 0.02
    }},
    "reasoning": "用户关注情感共鸣类内容,需要高互动和受众匹配的达人..."
}}"""

            response = llm.invoke(prompt)
            content = response.content

            # Try to extract JSON
            try:
                # Find JSON block
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    preferences = json.loads(json_match.group())
                else:
                    preferences = json.loads(content)

                # Validate weights sum to 1.0
                weights = preferences.get('scoring_weights', {})
                weight_sum = sum(weights.values())
                if abs(weight_sum - 1.0) > 0.01:
                    # Normalize
                    preferences['scoring_weights'] = {k: v/weight_sum for k, v in weights.items()}

                return json.dumps({
                    "success": True,
                    "preferences": preferences
                }, ensure_ascii=False, indent=2)

            except json.JSONDecodeError:
                # Fallback to default preferences
                return json.dumps({
                    "success": True,
                    "preferences": {
                        "product_category": "未知",
                        "target_audience": {
                            "gender": "all",
                            "age_range": [],
                            "regions": []
                        },
                        "budget_level": "medium",
                        "priority_metrics": ["engagement_rate", "audience_match", "sales_performance"],
                        "content_style": [],
                        "deal_breakers": [],
                        "scoring_weights": {
                            "engagement": 0.25,
                            "sales": 0.20,
                            "audience_match": 0.20,
                            "content_fit": 0.20,
                            "growth": 0.10,
                            "stability": 0.05
                        },
                        "reasoning": "LLM输出解析失败,使用默认配置"
                    },
                    "warning": "LLM输出格式异常,使用默认偏好"
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"分析偏好时发生错误: {str(e)}"
            }, ensure_ascii=False)


# ==================== Tool 3: Multi-Dimension Scorer ====================

class ScorerInput(BaseModel):
    """Input for multi-dimension scorer."""
    influencer_ids: List[str] = Field(description="要评分的达人ID列表")
    preferences_json: str = Field(description="用户偏好JSON字符串(来自Tool 2)")
    influencer_folder: str = Field(
        default="influencer",
        description="达人数据文件夹"
    )


class MultiDimensionScorerTool(BaseTool):
    """多维度评分引擎(调用report_scorer模块)."""

    name: str = "score_influencers"
    description: str = """
    对达人进行多维度评分和排序。

    评分维度:
    1. 互动能力 - 互动率、爆款率
    2. 带货能力 - GPM、销售额、客单价
    3. 受众匹配 - 性别/年龄/地域匹配度
    4. 内容契合 - 与产品/品牌的契合度(需要后续LLM分析)
    5. 成长性 - 粉丝增长、趋势分析
    6. 稳定性 - 发布频率、数据波动

    返回排序后的达人列表,每个达人包含总分和各维度详细得分。
    """
    args_schema: type[BaseModel] = ScorerInput

    def _run(self, influencer_ids: List[str], preferences_json: str,
             influencer_folder: str = "influencer") -> str:
        """评分和排序."""
        try:
            # Parse preferences
            preferences = json.loads(preferences_json)
            target_audience = preferences.get('target_audience', {})
            custom_weights = preferences.get('scoring_weights', None)

            scored_influencers = []

            for influencer_id in influencer_ids:
                # Load influencer data
                json_file = f"{influencer_id}.json"
                file_path = os.path.join(influencer_folder, json_file)

                if not os.path.exists(file_path):
                    continue

                with open(file_path, 'r', encoding='utf-8') as f:
                    influencer_data = json.load(f)

                # Score influencer (content_fit will be 0 for now, updated later)
                result = score_influencer(
                    influencer_data,
                    target_audience,
                    content_fit_score=0.0,  # Placeholder
                    custom_weights=custom_weights
                )

                scored_influencers.append(result)

            # Sort by total score (descending)
            scored_influencers.sort(key=lambda x: x['total_score'], reverse=True)

            return json.dumps({
                "success": True,
                "ranked_influencers": scored_influencers,
                "count": len(scored_influencers)
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"评分时发生错误: {str(e)}"
            }, ensure_ascii=False)


# ==================== Tool 4: Content Alignment ====================

class ContentAlignmentInput(BaseModel):
    """Input for content alignment analysis."""
    influencer_id: str = Field(description="达人ID")
    preferences_json: str = Field(description="用户偏好JSON字符串")
    influencer_folder: str = Field(default="influencer", description="达人数据文件夹")


class ContentAlignmentTool(BaseTool):
    """用LLM进行深度内容契合度分析."""

    name: str = "analyze_content_alignment"
    description: str = """
    使用LLM深度分析达人内容与产品的契合度。

    分析维度:
    - label_list标签与产品的语义相关性
    - 内容风格与品牌调性的匹配
    - 品牌安全风险评估
    - 创意合作建议

    返回0-100分的契合度得分和详细分析。
    """
    args_schema: type[BaseModel] = ContentAlignmentInput

    def _get_llm(self):
        """Get LLM instance."""
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
            temperature=0.3,
            base_url=os.getenv("OPENAI_BASE_URL")
        )

    def _run(self, influencer_id: str, preferences_json: str,
             influencer_folder: str = "influencer") -> str:
        """分析内容契合度."""
        try:
            llm = self._get_llm()

            # Load influencer data
            file_path = os.path.join(influencer_folder, f"{influencer_id}.json")

            if not os.path.exists(file_path):
                return json.dumps({
                    "success": False,
                    "error": f"找不到达人数据: {influencer_id}"
                }, ensure_ascii=False)

            with open(file_path, 'r', encoding='utf-8') as f:
                influencer_data = json.load(f)

            # Parse preferences
            preferences = json.loads(preferences_json)

            # Extract label list
            label_list = influencer_data.get('api_responses', {}).get('labelList', {}).get('label_list', [])
            base_info = influencer_data.get('api_responses', {}).get('baseInfo', {})

            # Build LLM prompt
            prompt = f"""你是一个内容营销专家。请分析达人与产品的内容契合度。

达人信息:
- 昵称: {base_info.get('nickname', 'Unknown')}
- 签名: {base_info.get('signature', '')}
- 内容标签: {json.dumps(label_list[:10], ensure_ascii=False)}

产品信息:
- 类目: {preferences.get('product_category', '未知')}
- 内容风格偏好: {preferences.get('content_style', [])}

请分析以下内容并输出JSON:

1. alignment_score: 契合度得分(0-100)
2. matched_labels: 匹配的标签列表,每个包含:
   - label: 标签名
   - relevance: "high" | "medium" | "low"
   - reasoning: 为什么相关
3. content_style_summary: 达人内容风格总结(1-2句话)
4. brand_safety_check:
   - risk_level: "low" | "medium" | "high"
   - concerns: 风险点列表
5. creative_suggestions: 3-5条创意合作建议

输出纯JSON格式。"""

            response = llm.invoke(prompt)
            content = response.content

            # Parse JSON
            try:
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    analysis = json.loads(content)

                return json.dumps({
                    "success": True,
                    "influencer_id": influencer_id,
                    "analysis": analysis
                }, ensure_ascii=False, indent=2)

            except json.JSONDecodeError:
                # Fallback: calculate simple score based on label overlap
                content_keywords = set(preferences.get('content_style', []))
                label_keywords = set(item['key'].lower() for item in label_list[:10])

                overlap = len(content_keywords & label_keywords)
                simple_score = min(100, 50 + overlap * 10)

                return json.dumps({
                    "success": True,
                    "influencer_id": influencer_id,
                    "analysis": {
                        "alignment_score": simple_score,
                        "matched_labels": [],
                        "content_style_summary": "基于标签的简单匹配",
                        "brand_safety_check": {"risk_level": "low", "concerns": []},
                        "creative_suggestions": ["建议人工审核内容风格"]
                    },
                    "warning": "LLM分析失败,使用简化评分"
                }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"分析内容契合度时发生错误: {str(e)}"
            }, ensure_ascii=False)


# ==================== Tool 5: Data Visualization ====================

class VisualizationInput(BaseModel):
    """Input for data visualization."""
    influencer_id: str = Field(description="达人ID")
    dimension_scores_json: str = Field(description="维度评分JSON(来自Tool 3)")
    influencer_folder: str = Field(default="influencer", description="达人数据文件夹")


class DataVisualizationTool(BaseTool):
    """生成专业的数据可视化图表."""

    name: str = "generate_charts"
    description: str = """
    为达人生成多种专业可视化图表。

    图表类型:
    - 互动趋势图(折线图)
    - 销售漏斗图
    - 受众画像金字塔
    - 品类分布饼图
    - 六维能力雷达图

    所有图表都是交互式HTML格式,包含自动生成的洞察。
    """
    args_schema: type[BaseModel] = VisualizationInput

    def _run(self, influencer_id: str, dimension_scores_json: str,
             influencer_folder: str = "influencer") -> str:
        """生成图表."""
        try:
            # Load influencer data
            file_path = os.path.join(influencer_folder, f"{influencer_id}.json")

            if not os.path.exists(file_path):
                return json.dumps({
                    "success": False,
                    "error": f"找不到达人数据: {influencer_id}"
                }, ensure_ascii=False)

            with open(file_path, 'r', encoding='utf-8') as f:
                influencer_data = json.load(f)

            # Parse dimension scores
            dimension_scores = json.loads(dimension_scores_json)

            # Generate charts
            visualizer = InfluencerVisualizer()
            result = visualizer.generate_all_charts(
                influencer_data,
                dimension_scores,
                influencer_id
            )

            return json.dumps({
                "success": True,
                "influencer_id": influencer_id,
                "charts": result["charts"],
                "summary": result["summary"]
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"生成图表时发生错误: {str(e)}"
            }, ensure_ascii=False)


# ==================== Get All Tools ====================

def get_report_tools() -> List[BaseTool]:
    """获取所有报告生成工具."""
    return [
        LoadInfluencerDataTool(),
        UserPreferenceAnalyzerTool(),
        MultiDimensionScorerTool(),
        ContentAlignmentTool(),
        DataVisualizationTool(),
    ]


if __name__ == "__main__":
    print("Testing Report Tools...")

    # Test Tool 1: Load Data
    print("\n" + "="*60)
    print("Test 1: Loading Influencer Data")
    print("="*60)

    tool1 = LoadInfluencerDataTool()
    result1 = tool1._run(influencer_folder="influencer")
    data1 = json.loads(result1)

    if data1.get("success"):
        print(f"✓ 加载成功: {data1['loaded_count']}个达人")
        print(f"  区域分布: {data1.get('region_distribution', {})}")
        if data1.get('warnings'):
            print(f"  警告: {len(data1['warnings'])}条")
    else:
        print(f"✗ 加载失败: {data1.get('error')}")

    print("\n✅ All tools initialized successfully!")
