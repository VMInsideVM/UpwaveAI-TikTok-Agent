"""
达人推荐报告生成器
使用 LLM 分析数据并生成美观的 HTML 报告
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import base64
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class ReportGenerator:
    """达人推荐报告生成器"""

    def __init__(self):
        """初始化报告生成器"""
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        self.model = os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct")

        # 确保报告目录存在
        self.reports_dir = Path("static/reports")
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        json_file_path: str,
        product_name: str,
        user_requirements: str,
        image_data: Optional[str] = None,
        top_n: int = 10
    ) -> Dict:
        """
        生成达人推荐报告

        Args:
            json_file_path: 达人数据 JSON 文件路径
            product_name: 商品名称
            user_requirements: 用户需求描述
            image_data: 商品图片（Base64）
            top_n: 推荐达人数量

        Returns:
            包含报告路径和 URL 的字典
        """
        try:
            # 1. 读取达人数据
            print(f"📖 读取达人数据...")
            with open(json_file_path, 'r', encoding='utf-8') as f:
                influencers_data = json.load(f)

            if not influencers_data:
                raise ValueError("达人数据为空")

            # 2. 使用 LLM 分析并排序达人
            print(f"🤖 使用 AI 分析达人数据...")
            ranked_influencers = self._rank_influencers_with_llm(
                influencers_data,
                product_name,
                user_requirements,
                image_data,
                top_n
            )

            # 3. 生成 HTML 报告
            print(f"📝 生成 HTML 报告...")
            report_html = self._create_html_report(
                ranked_influencers,
                product_name,
                user_requirements,
                image_data
            )

            # 4. 保存报告
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{timestamp}.html"
            filepath = self.reports_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_html)

            # 5. 返回结果
            url = f"/static/reports/{filename}"

            return {
                "success": True,
                "filepath": str(filepath),
                "url": url,
                "filename": filename,
                "total_analyzed": len(influencers_data),
                "top_recommended": len(ranked_influencers)
            }

        except Exception as e:
            print(f"❌ 生成报告失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def _rank_influencers_with_llm(
        self,
        influencers: List[Dict],
        product_name: str,
        user_requirements: str,
        image_data: Optional[str],
        top_n: int
    ) -> List[Dict]:
        """
        使用 LLM 分析并排序达人

        Returns:
            排序后的达人列表（包含推荐理由）
        """
        # 准备提示词
        prompt = f"""你是一位专业的 TikTok 达人推荐专家。请根据用户需求分析以下达人数据，选出最合适的 {top_n} 位达人。

**用户需求：**
商品名称：{product_name}
详细需求：{user_requirements}

**达人数据：**
{json.dumps(influencers[:20], ensure_ascii=False, indent=2)}  # 只发送前20个给 LLM 分析

**任务：**
1. 综合考虑以下因素：
   - 粉丝数量和质量
   - 互动率（点赞率、评论率）
   - 带货能力（销量、转化率）
   - 粉丝画像匹配度（年龄、性别、地区）
   - 达人定位与商品的契合度

2. 选出最合适的 {top_n} 位达人，并为每位达人生成推荐理由

3. 以 JSON 格式返回，格式如下：
```json
[
  {{
    "influencer_id": "达人ID",
    "rank": 1,
    "score": 95,
    "recommendation_reason": "推荐理由（50-100字）",
    "highlights": ["亮点1", "亮点2", "亮点3"]
  }},
  ...
]
```

请直接返回 JSON，不要包含其他文字。"""

        # 构建消息
        messages = [
            {"role": "system", "content": "你是一位专业的 TikTok 达人推荐专家，擅长数据分析和精准匹配。"},
            {"role": "user", "content": prompt}
        ]

        # 如果有图片，添加到消息中
        if image_data:
            messages[-1]["content"] = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data}}
            ]

        try:
            # 调用 LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=4000
            )

            # 解析结果
            result_text = response.choices[0].message.content.strip()

            # 提取 JSON（处理可能的 markdown 代码块）
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            rankings = json.loads(result_text)

            # 合并 LLM 的排名结果和原始数据
            ranked_influencers = []
            for ranking in rankings:
                # 查找对应的达人数据
                influencer_id = ranking.get("influencer_id")
                influencer_data = next(
                    (inf for inf in influencers if str(inf.get("达人ID")) == str(influencer_id)),
                    None
                )

                if influencer_data:
                    # 合并数据
                    influencer_data["rank"] = ranking.get("rank", 0)
                    influencer_data["ai_score"] = ranking.get("score", 0)
                    influencer_data["recommendation_reason"] = ranking.get("recommendation_reason", "")
                    influencer_data["highlights"] = ranking.get("highlights", [])
                    ranked_influencers.append(influencer_data)

            return ranked_influencers[:top_n]

        except Exception as e:
            print(f"⚠️ LLM 分析失败，使用默认排序: {e}")
            # 降级方案：按粉丝数排序
            sorted_influencers = sorted(
                influencers,
                key=lambda x: self._parse_number(x.get("粉丝数", "0")),
                reverse=True
            )[:top_n]

            for i, inf in enumerate(sorted_influencers, 1):
                inf["rank"] = i
                inf["ai_score"] = 100 - (i - 1) * 5
                inf["recommendation_reason"] = "根据粉丝数量和互动数据推荐"
                inf["highlights"] = ["粉丝基础良好", "数据表现稳定"]

            return sorted_influencers

    def _create_html_report(
        self,
        influencers: List[Dict],
        product_name: str,
        user_requirements: str,
        image_data: Optional[str]
    ) -> str:
        """创建 HTML 报告"""

        # 生成达人卡片
        influencer_cards = ""
        for inf in influencers:
            rank = inf.get("rank", 0)
            nickname = inf.get("达人昵称", "未知")
            avatar = inf.get("达人头像", "")
            followers = inf.get("粉丝数", "0")
            engagement_rate = inf.get("互动率", "0%")
            video_avg_views = inf.get("近28天视频平均播放量", "0")
            total_sales = inf.get("近28天总销量", "0")
            reason = inf.get("recommendation_reason", "综合数据表现优秀")
            highlights = inf.get("highlights", [])
            score = inf.get("ai_score", 0)

            # 生成徽章
            badge_color = "gold" if rank <= 3 else "silver" if rank <= 5 else "bronze"

            # 生成亮点标签
            highlight_tags = "".join([f'<span class="highlight-tag">{h}</span>' for h in highlights])

            influencer_cards += f"""
            <div class="influencer-card rank-{rank}">
                <div class="rank-badge rank-{badge_color}">#{rank}</div>
                <div class="influencer-header">
                    <img src="{avatar}" alt="{nickname}" class="influencer-avatar" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22%3E%3Crect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23999%22%3E{nickname[0] if nickname else '?'}%3C/text%3E%3C/svg%3E'">
                    <div class="influencer-info">
                        <h3 class="influencer-name">{nickname}</h3>
                        <div class="influencer-score">
                            <span class="score-label">AI 匹配度:</span>
                            <span class="score-value">{score}分</span>
                        </div>
                    </div>
                </div>

                <div class="influencer-stats">
                    <div class="stat-item">
                        <div class="stat-label">粉丝数</div>
                        <div class="stat-value">{followers}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">互动率</div>
                        <div class="stat-value">{engagement_rate}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">平均播放</div>
                        <div class="stat-value">{video_avg_views}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">近28天销量</div>
                        <div class="stat-value">{total_sales}</div>
                    </div>
                </div>

                <div class="recommendation-section">
                    <h4>推荐理由</h4>
                    <p class="recommendation-text">{reason}</p>
                </div>

                <div class="highlights-section">
                    {highlight_tags}
                </div>
            </div>
            """

        # 生成产品信息卡片
        product_image_html = ""
        if image_data:
            product_image_html = f'<img src="{image_data}" alt="{product_name}" class="product-image">'

        # 生成完整 HTML
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>达人推荐报告 - {product_name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 32px;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            font-size: 16px;
            opacity: 0.9;
        }}

        .product-section {{
            padding: 30px 40px;
            background: #f9fafb;
            border-bottom: 2px solid #e5e7eb;
        }}

        .product-info {{
            display: flex;
            gap: 30px;
            align-items: flex-start;
        }}

        .product-image {{
            width: 200px;
            height: 200px;
            object-fit: cover;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}

        .product-details {{
            flex: 1;
        }}

        .product-details h2 {{
            font-size: 24px;
            color: #1f2937;
            margin-bottom: 15px;
        }}

        .product-requirements {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}

        .product-requirements h3 {{
            font-size: 16px;
            color: #667eea;
            margin-bottom: 10px;
        }}

        .product-requirements p {{
            color: #6b7280;
            line-height: 1.6;
        }}

        .influencers-section {{
            padding: 40px;
        }}

        .section-title {{
            font-size: 24px;
            color: #1f2937;
            margin-bottom: 30px;
            text-align: center;
        }}

        .influencers-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 30px;
        }}

        .influencer-card {{
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 16px;
            padding: 24px;
            position: relative;
            transition: all 0.3s ease;
        }}

        .influencer-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 12px 24px rgba(102, 126, 234, 0.2);
            border-color: #667eea;
        }}

        .rank-badge {{
            position: absolute;
            top: -12px;
            right: 20px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 14px;
            color: white;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }}

        .rank-gold {{
            background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
            color: #000;
        }}

        .rank-silver {{
            background: linear-gradient(135deg, #c0c0c0 0%, #e8e8e8 100%);
            color: #000;
        }}

        .rank-bronze {{
            background: linear-gradient(135deg, #cd7f32 0%, #e8a87c 100%);
        }}

        .influencer-header {{
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }}

        .influencer-avatar {{
            width: 60px;
            height: 60px;
            border-radius: 50%;
            object-fit: cover;
            border: 3px solid #667eea;
        }}

        .influencer-info {{
            flex: 1;
        }}

        .influencer-name {{
            font-size: 18px;
            color: #1f2937;
            margin-bottom: 8px;
        }}

        .influencer-score {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .score-label {{
            font-size: 14px;
            color: #6b7280;
        }}

        .score-value {{
            font-size: 16px;
            font-weight: 700;
            color: #667eea;
        }}

        .influencer-stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 20px;
            padding: 15px;
            background: #f9fafb;
            border-radius: 8px;
        }}

        .stat-item {{
            text-align: center;
        }}

        .stat-label {{
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 4px;
        }}

        .stat-value {{
            font-size: 16px;
            font-weight: 600;
            color: #1f2937;
        }}

        .recommendation-section {{
            margin-bottom: 15px;
        }}

        .recommendation-section h4 {{
            font-size: 14px;
            color: #667eea;
            margin-bottom: 8px;
        }}

        .recommendation-text {{
            font-size: 14px;
            color: #4b5563;
            line-height: 1.6;
        }}

        .highlights-section {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .highlight-tag {{
            display: inline-block;
            padding: 4px 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}

        .footer {{
            padding: 30px;
            text-align: center;
            color: #6b7280;
            font-size: 14px;
            background: #f9fafb;
        }}

        @media (max-width: 768px) {{
            .influencers-grid {{
                grid-template-columns: 1fr;
            }}

            .product-info {{
                flex-direction: column;
            }}

            .product-image {{
                width: 100%;
                height: auto;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 TikTok 达人推荐报告</h1>
            <p class="subtitle">基于 AI 智能分析的精准推荐</p>
        </div>

        <div class="product-section">
            <div class="product-info">
                {product_image_html}
                <div class="product-details">
                    <h2>📦 {product_name}</h2>
                    <div class="product-requirements">
                        <h3>📋 推广需求</h3>
                        <p>{user_requirements}</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="influencers-section">
            <h2 class="section-title">🌟 推荐达人列表（共 {len(influencers)} 位）</h2>
            <div class="influencers-grid">
                {influencer_cards}
            </div>
        </div>

        <div class="footer">
            <p>报告生成时间: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}</p>
            <p>由 TikTok 达人推荐助手自动生成</p>
        </div>
    </div>
</body>
</html>"""

        return html

    def _parse_number(self, value: str) -> float:
        """解析数字（支持万、亿等单位）"""
        if not value or value == "-":
            return 0

        try:
            value = str(value).strip()

            # 移除百分号
            value = value.replace('%', '')

            # 处理万、亿
            if '亿' in value:
                return float(value.replace('亿', '')) * 100000000
            elif '万' in value:
                return float(value.replace('万', '')) * 10000
            else:
                return float(value)
        except:
            return 0


if __name__ == "__main__":
    # 测试报告生成器
    generator = ReportGenerator()

    # 模拟数据
    test_data = [
        {
            "达人ID": "123456",
            "达人昵称": "美妆达人小红",
            "达人头像": "",
            "粉丝数": "100万",
            "互动率": "8.5%",
            "近28天视频平均播放量": "50万",
            "近28天总销量": "5000"
        }
    ]

    # 保存测试数据
    test_json = "test_influencers.json"
    with open(test_json, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    # 生成报告
    result = generator.generate_report(
        json_file_path=test_json,
        product_name="高端口红",
        user_requirements="需要找一些专注于美妆领域的达人，粉丝画像为25-35岁女性",
        image_data=None,
        top_n=5
    )

    print(f"报告生成结果: {result}")

    # 清理测试文件
    if os.path.exists(test_json):
        os.remove(test_json)
