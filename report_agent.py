"""
TikTok Influencer Report Generation Agent

Main orchestrator that coordinates all tools to generate comprehensive
influencer recommendation reports.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from jinja2 import Template

from langchain_openai import ChatOpenAI

from report_tools import (
    LoadInfluencerDataTool,
    UserPreferenceAnalyzerTool,
    MultiDimensionScorerTool,
    ContentAlignmentTool,
    DataVisualizationTool
)

# Load environment
load_dotenv()


class TikTokInfluencerReportAgent:
    """
    Main agent for generating influencer recommendation reports.

    Workflow:
    1. Load all influencer data
    2. Analyze user preferences with LLM
    3. Score and rank influencers
    4. Analyze content fit for top candidates
    5. Generate visualizations
    6. Compile HTML report
    """

    def __init__(self):
        """Initialize the report generation agent."""
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
            temperature=0.3,
            base_url=os.getenv("OPENAI_BASE_URL")
        )

        # Initialize tools (viz_tool will be initialized per-report with dynamic path)
        self.loader_tool = LoadInfluencerDataTool()
        self.preference_tool = UserPreferenceAnalyzerTool()
        self.scorer_tool = MultiDimensionScorerTool()
        self.content_tool = ContentAlignmentTool()
        self.viz_tool = None  # Will be initialized in generate_report with timestamped path

    def _load_from_json_file(self, json_filename: str) -> Dict[str, Any]:
        """
        Load influencer IDs from a specific JSON file in the output folder.

        Args:
            json_filename: Name of the JSON file (e.g., "tiktok_达人推荐_女士香水_20251105_132850.json")

        Returns:
            Dictionary with success status and influencer_ids list
        """
        try:
            # Construct full path
            json_path = os.path.join("output", json_filename)

            # Check if file exists
            if not os.path.exists(json_path):
                return {
                    'success': False,
                    'error': f'文件不存在: {json_path}'
                }

            # Load JSON file
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract data_row_keys
            influencer_ids = data.get('data_row_keys', [])

            if not influencer_ids:
                return {
                    'success': False,
                    'error': f'JSON文件中没有找到 data_row_keys 字段'
                }

            # Verify that influencer JSON files exist
            missing_files = []
            existing_ids = []

            for inf_id in influencer_ids:
                inf_path = os.path.join("influencer", f"{inf_id}.json")
                if os.path.exists(inf_path):
                    existing_ids.append(inf_id)
                else:
                    missing_files.append(inf_id)

            if missing_files:
                print(f"⚠️  警告: {len(missing_files)}个达人文件不存在,已跳过")
                print(f"   缺失的达人ID: {missing_files[:5]}{'...' if len(missing_files) > 5 else ''}")

            if not existing_ids:
                return {
                    'success': False,
                    'error': f'所有达人文件都不存在于 influencer/ 文件夹'
                }

            print(f"✓ 从 {json_filename} 加载了 {len(existing_ids)}/{len(influencer_ids)} 个达人")
            print(f"  产品名称: {data.get('product_name', '未知')}")
            print(f"  时间戳: {data.get('timestamp', '未知')}")

            return {
                'success': True,
                'influencer_ids': existing_ids,
                'source_file': json_filename,
                'product_name': data.get('product_name', '未知')
            }

        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'JSON解析错误: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'加载文件失败: {str(e)}'
            }

    def generate_report(
        self,
        json_filename: str,
        user_query: str,
        target_count: int,
        product_info: str,
        progress_callback=None,
        report_id: str = None
    ) -> str:
        """
        Generate influencer recommendation report.

        Args:
            json_filename: JSON file name in output folder (e.g., "tiktok_达人推荐_女士香水_20251105_132850.json")
            user_query: User's natural language requirement
            target_count: Number of top influencers needed in final report
            product_info: Detailed product information for preference analysis
            progress_callback: Optional callback function(progress: int) for real-time progress updates

        Returns:
            Path to generated HTML report
        """
        def update_progress(progress: int):
            """Helper function to update progress"""
            if progress_callback:
                progress_callback(progress)
        try:
            print(f"\n{'='*60}")
            print(f"开始生成推荐报告")
            print(f"{'='*60}")
            print(f"数据文件: {json_filename}")
            print(f"用户需求: {user_query}")
            print(f"产品信息: {product_info[:100]}{'...' if len(product_info) > 100 else ''}")
            print(f"目标数量: Top {target_count}个达人")
            print(f"{'='*60}\n")

            # Step 1: Load influencer data from JSON file (10%-20%)
            update_progress(10)
            print("📂 步骤1: 加载达人数据...")
            load_result = self._load_from_json_file(json_filename)

            if not load_result.get('success'):
                print(f"❌ 加载失败: {load_result.get('error')}")
                return None

            influencer_ids = load_result['influencer_ids']
            print(f"✓ 成功加载{len(influencer_ids)}个达人\n")
            update_progress(20)

            # Step 2: Analyze user preferences (20%-30%)
            print("🧠 步骤2: 分析用户偏好...")
            pref_result = json.loads(self.preference_tool._run(
                user_query=user_query,
                product_info=product_info,  # Pass product info for better analysis
                target_count=target_count
            ))

            if not pref_result.get('success'):
                print(f"❌ 分析失败: {pref_result.get('error')}")
                return None

            preferences = pref_result['preferences']
            print(f"✓ 偏好分析完成")
            print(f"  产品类目: {preferences.get('product_category')}")
            print(f"  目标受众: {preferences.get('target_audience')}")
            print(f"  优先指标: {preferences.get('priority_metrics')}\n")
            update_progress(30)

            # Step 3: Score and rank influencers (30%-40%)
            print("📊 步骤3: 多维度评分...")
            score_result = json.loads(self.scorer_tool._run(
                influencer_ids=influencer_ids,
                preferences_json=json.dumps(preferences)
            ))

            if not score_result.get('success'):
                print(f"❌ 评分失败: {score_result.get('error')}")
                return None

            # 推荐层级: Tier 1 (1x) + Tier 2 (2x) + Tier 3 (3x) = 6x
            total_needed = target_count * 6  # 总共需要 6 倍的达人
            ranked_influencers = score_result['ranked_influencers'][:total_needed]
            print(f"✓ 评分完成,Top {len(ranked_influencers)}达人:")
            for i, inf in enumerate(ranked_influencers[:3], 1):
                print(f"  #{i}: {inf['nickname']} - {inf['total_score']:.1f}分")
            print()
            update_progress(40)

            # Step 4: Content alignment analysis (40%-80%)
            print(f"🔍 步骤4: 内容契合度分析 (Top {len(ranked_influencers)}达人)...")
            total_influencers = len(ranked_influencers)
            for i, inf in enumerate(ranked_influencers, 1):
                # 计算当前进度 (40% + 40% * (i-1)/total，因为第i个正在分析，前i-1个已完成)
                current_progress = 40 + int(40 * (i - 1) / total_influencers)
                update_progress(current_progress)

                print(f"  分析 {i}/{total_influencers}: {inf['nickname']}...", end=' ')

                content_result = json.loads(self.content_tool._run(
                    influencer_id=inf['influencer_id'],
                    preferences_json=json.dumps(preferences)
                ))

                if content_result.get('success'):
                    analysis = content_result['analysis']
                    inf['dimension_scores']['content_fit'] = {
                        'score': analysis.get('alignment_score', 50),
                        'reasoning': analysis.get('content_style_summary', ''),
                        'metrics': {}
                    }
                    # Recalculate total score with updated content_fit
                    from report_scorer import InfluencerScorer
                    scorer = InfluencerScorer()
                    updated = scorer.calculate_total_score(
                        inf['dimension_scores'],
                        preferences.get('scoring_weights')
                    )
                    inf['total_score'] = updated['total_score']
                    print(f"✓ {analysis.get('alignment_score', 50):.0f}分")
                else:
                    print("⚠ 跳过")

            # Re-sort after content fit update
            ranked_influencers.sort(key=lambda x: x['total_score'], reverse=True)
            print()
            update_progress(80)

            # Create report directory using report_id (UUID) for security
            # Using UUID prevents attackers from guessing directory names
            if report_id:
                # 安全：使用 report_id (UUID) 作为目录名，无法被猜测
                dir_name = report_id
            else:
                # 回退方案：使用时间戳（仅用于独立测试）
                dir_name = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_dir = os.path.join("output/reports", dir_name)
            charts_dir = os.path.join(report_dir, "charts")
            os.makedirs(charts_dir, exist_ok=True)
            print(f"📁 创建报告目录: {report_dir}")

            # Initialize visualizer with timestamped charts directory
            self.viz_tool = DataVisualizationTool(output_dir=charts_dir)

            # Step 5: Generate visualizations (80%-90%)
            # 🔥 修复: 为所有达人 (Tier1 + Tier2 + Tier3) 生成可视化图表
            total_influencers = len(ranked_influencers)
            print(f"📈 步骤5: 生成可视化图表 (为所有 {total_influencers} 个达人)...")
            charts_generated = 0
            for i, inf in enumerate(ranked_influencers, 1):
                # 计算进度 (80% + 10% * (i-1)/total_influencers)
                current_progress = 80 + int(10 * (i - 1) / total_influencers)
                update_progress(current_progress)

                print(f"  生成图表 {i}/{total_influencers}: {inf['nickname']}...", end=' ')

                viz_result = json.loads(self.viz_tool._run(
                    influencer_id=inf['influencer_id'],
                    dimension_scores_json=json.dumps(inf['dimension_scores'])
                ))

                if viz_result.get('success'):
                    inf['charts'] = viz_result['charts']
                    charts_generated += len(viz_result['charts'])
                    print(f"✓ {len(viz_result['charts'])}张图表")
                else:
                    inf['charts'] = []
                    print("⚠ 跳过")

            print(f"✓ 共生成{charts_generated}张图表\n")
            update_progress(90)

            # Step 6: Compile report (90%-95%)
            print("📝 步骤6: 编译HTML报告...")
            report_data = {
                "executive_summary": self._generate_executive_summary(
                    ranked_influencers, preferences, target_count
                ),
                "recommended_influencers": ranked_influencers,
                "comparison_analysis": {}
            }

            report_path = self._compile_html_report(
                json.dumps(report_data, ensure_ascii=False),
                user_query,
                target_count,
                report_dir
            )
            update_progress(95)

            print(f"\n{'='*60}")
            print(f"✅ 报告生成成功!")
            print(f"{'='*60}")
            print(f"报告路径: {report_path}")
            print(f"{'='*60}\n")
            update_progress(100)

            return report_path

        except Exception as e:
            print(f"\n❌ 报告生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_executive_summary(self, influencers: List[Dict],
                                   preferences: Dict, target_count: int) -> str:
        """Generate executive summary HTML."""
        top3 = influencers[:3]
        avg_score = sum(inf['total_score'] for inf in top3) / len(top3) if top3 else 0

        return f"""
<ul>
    <li><strong>分析达人数:</strong> {len(influencers)}个</li>
    <li><strong>推荐层级:</strong> Tier 1 ({target_count * 1}个) + Tier 2 ({target_count * 2}个) + Tier 3 ({target_count * 3}个)</li>
    <li><strong>Top 3平均分:</strong> {avg_score:.1f}/100</li>
    <li><strong>产品类目:</strong> {preferences.get('product_category', '未知')}</li>
    <li><strong>目标受众:</strong> {preferences.get('target_audience', {}).get('gender', 'all')}性,
        年龄{", ".join(preferences.get('target_audience', {}).get('age_range', []))}</li>
    <li><strong>核心洞察:</strong> Top {target_count * 1}达人在{", ".join(preferences.get('priority_metrics', [])[:2])}维度表现优异,建议优先合作</li>
</ul>
"""

    def _compile_html_report(self, agent_output: str, user_query: str,
                            target_count: int, report_dir: str) -> str:
        """
        Compile final HTML report from agent output.

        Args:
            agent_output: Agent's final output
            user_query: Original user query
            target_count: Target influencer count
            report_dir: Directory path for this report (e.g., "output/reports/20251105_180530")

        Returns:
            Path to HTML report
        """
        try:
            # Load HTML template
            template_path = "report_templates/base_template.html"

            if not os.path.exists(template_path):
                print(f"⚠️  模板文件不存在: {template_path}")
                # Create simplified report
                return self._create_simple_report(agent_output, user_query)

            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()

            template = Template(template_content)

            # Parse agent output (try to extract JSON)
            try:
                import re
                json_match = re.search(r'\{.*\}', agent_output, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    # Fallback: create basic structure
                    data = {
                        "executive_summary": "<p>报告生成中...</p>",
                        "recommended_influencers": [],
                        "comparison_analysis": "<p>对比分析...</p>"
                    }
            except:
                data = {
                    "executive_summary": f"<p>{agent_output[:500]}</p>",
                    "recommended_influencers": [],
                    "comparison_analysis": "<p>详细分析请参考原始输出</p>"
                }

            # Prepare template variables
            generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Build influencer sections HTML
            influencer_sections_html = self._build_influencer_sections(
                data.get('recommended_influencers', []),
                target_count
            )

            # Build comparison content HTML
            comparison_html = self._build_comparison_section(
                data.get('comparison_analysis', {}),
                data.get('recommended_influencers', [])
            )

            # Render template
            html_content = template.render(
                report_title=user_query[:100],
                generation_time=generation_time,
                total_influencers=len(data.get('recommended_influencers', [])),
                recommended_count=target_count * 6,  # 1x + 2x + 3x = 6x
                executive_summary=data.get('executive_summary', ''),
                influencer_sections=influencer_sections_html,
                comparison_content=comparison_html
            )

            # Save report to timestamped directory
            report_path = os.path.join(report_dir, "report.html")

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            return report_path

        except Exception as e:
            print(f"⚠️  HTML编译失败: {str(e)}")
            return self._create_simple_report(agent_output, user_query)

    def _build_influencer_sections(self, influencers: List[Dict],
                                   target_count: int) -> str:
        """Build HTML sections for influencers."""
        if not influencers:
            return "<div class='section'><p>暂无推荐数据</p></div>"

        html_parts = []

        # 新的层级分配: Tier 1 (1x) + Tier 2 (2x) + Tier 3 (3x)
        tier1_count = target_count * 1
        tier2_count = target_count * 2
        tier3_count = target_count * 3

        # Tier 1: Top 4x influencers (首选推荐)
        tier1 = influencers[:tier1_count]
        if tier1:
            html_parts.append(self._build_tier_section(tier1, 1, "首选推荐"))

        # Tier 2: Next 3x influencers (优质备选)
        tier2 = influencers[tier1_count:tier1_count + tier2_count]
        if tier2:
            html_parts.append(self._build_tier_section(tier2, 2, "优质备选"))

        # Tier 3: Next 2x influencers (候补方案)
        tier3 = influencers[tier1_count + tier2_count:tier1_count + tier2_count + tier3_count]
        if tier3:
            html_parts.append(self._build_tier_section(tier3, 3, "候补方案"))

        return "\n".join(html_parts)

    def _extract_contact_info(self, influencer_id: str) -> Dict[str, Any]:
        """Extract contact information from influencer JSON file."""
        try:
            file_path = os.path.join("influencer", f"{influencer_id}.json")
            if not os.path.exists(file_path):
                return {}

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract authorContact data
            author_contact = data.get('api_responses', {}).get('authorContact', {})
            contact_list = author_contact.get('list', [])

            # Build contact info dictionary from list where has=true
            contact_info = {}

            for contact in contact_list:
                if not contact.get('has', False):
                    continue  # Skip if has=false

                name = contact.get('name', '')
                contact_id = contact.get('id', '')
                link = contact.get('link', '')

                # For email, use id; for others, use link
                if name == 'email':
                    value = contact_id
                else:
                    value = link

                if value and name:
                    # Map common names to standard keys
                    if name == 'email':
                        contact_info['email'] = value
                    elif name == 'whatsapp':
                        contact_info['whatsapp'] = value
                    elif name == 'ins':
                        contact_info['instagram'] = value
                    elif name == 'youtube':
                        contact_info['youtube'] = value
                    elif name == 'tiktok':
                        contact_info['tiktok'] = value
                    elif name == 'facebook':
                        contact_info['facebook'] = value
                    elif name == 'twitter':
                        contact_info['twitter'] = value
                    elif name == 'bio':
                        contact_info['bio'] = value
                    elif name == 'line':
                        contact_info['line'] = value
                    elif name == 'zalo':
                        contact_info['zalo'] = value
                    elif name == 'viber':
                        contact_info['viber'] = value
                    else:
                        # Store other contacts
                        if 'other' not in contact_info:
                            contact_info['other'] = []
                        contact_info['other'].append(f"{name}: {value}")

            # Convert other list to string
            if 'other' in contact_info and isinstance(contact_info['other'], list):
                contact_info['other'] = ' | '.join(contact_info['other'])

            return contact_info

        except Exception as e:
            print(f"⚠️  提取联系方式失败 ({influencer_id}): {e}")
            return {}

    def _generate_contact_section(self, contact_info: Dict[str, Any]) -> str:
        """Generate contact information HTML section."""
        # Check if there's any contact info available
        has_contact = any(contact_info.values())

        if not has_contact:
            return """
    <div class="content-section" style="background:#fff9e6; padding:12px; border-radius:6px; margin-top:15px;">
        <h4 style="margin:0 0 8px 0; font-size:14px; color:#856404;">📞 达人联系方式</h4>
        <p style="margin:0; font-size:13px; color:#856404;">暂无联系方式信息</p>
    </div>
"""

        # Build contact items with proper formatting
        contact_items = []

        # Email (clickable)
        if contact_info.get('email'):
            email = contact_info['email']
            contact_items.append(f"<div style='margin:5px 0;'><strong>📧 Email:</strong> <a href='mailto:{email}' style='color:#1976d2;'>{email}</a></div>")

        # WhatsApp
        if contact_info.get('whatsapp'):
            whatsapp = contact_info['whatsapp']
            contact_items.append(f"<div style='margin:5px 0;'><strong>💬 WhatsApp:</strong> {whatsapp}</div>")

        # Instagram (clickable link if it's a URL)
        if contact_info.get('instagram'):
            instagram = contact_info['instagram']
            if instagram.startswith('http'):
                contact_items.append(f"<div style='margin:5px 0;'><strong>📷 Instagram:</strong> <a href='{instagram}' target='_blank' style='color:#e4405f;'>{instagram}</a></div>")
            else:
                # Extract username from URL if present
                username = instagram.split('/')[-1] if '/' in instagram else instagram
                contact_items.append(f"<div style='margin:5px 0;'><strong>📷 Instagram:</strong> <a href='{instagram}' target='_blank' style='color:#e4405f;'>@{username}</a></div>")

        # YouTube (clickable)
        if contact_info.get('youtube'):
            youtube = contact_info['youtube']
            if youtube.startswith('http'):
                contact_items.append(f"<div style='margin:5px 0;'><strong>📺 YouTube:</strong> <a href='{youtube}' target='_blank' style='color:#ff0000;'>{youtube}</a></div>")
            else:
                contact_items.append(f"<div style='margin:5px 0;'><strong>📺 YouTube:</strong> {youtube}</div>")

        # TikTok
        if contact_info.get('tiktok'):
            tiktok = contact_info['tiktok']
            contact_items.append(f"<div style='margin:5px 0;'><strong>🎵 TikTok:</strong> @{tiktok}</div>")

        # Facebook
        if contact_info.get('facebook'):
            facebook = contact_info['facebook']
            if facebook.startswith('http'):
                contact_items.append(f"<div style='margin:5px 0;'><strong>👤 Facebook:</strong> <a href='{facebook}' target='_blank' style='color:#4267B2;'>{facebook}</a></div>")
            else:
                contact_items.append(f"<div style='margin:5px 0;'><strong>👤 Facebook:</strong> {facebook}</div>")

        # Twitter
        if contact_info.get('twitter'):
            twitter = contact_info['twitter']
            if twitter.startswith('http'):
                contact_items.append(f"<div style='margin:5px 0;'><strong>🐦 Twitter:</strong> <a href='{twitter}' target='_blank' style='color:#1DA1F2;'>{twitter}</a></div>")
            else:
                contact_items.append(f"<div style='margin:5px 0;'><strong>🐦 Twitter:</strong> @{twitter}</div>")

        # Bio/Link in Bio
        if contact_info.get('bio'):
            bio = contact_info['bio']
            if bio.startswith('http'):
                contact_items.append(f"<div style='margin:5px 0;'><strong>🔗 Bio Link:</strong> <a href='{bio}' target='_blank' style='color:#00d084;'>{bio}</a></div>")
            else:
                contact_items.append(f"<div style='margin:5px 0;'><strong>🔗 Bio Link:</strong> {bio}</div>")

        # Line
        if contact_info.get('line'):
            line = contact_info['line']
            contact_items.append(f"<div style='margin:5px 0;'><strong>💚 Line:</strong> {line}</div>")

        # Zalo
        if contact_info.get('zalo'):
            zalo = contact_info['zalo']
            contact_items.append(f"<div style='margin:5px 0;'><strong>💙 Zalo:</strong> {zalo}</div>")

        # Viber
        if contact_info.get('viber'):
            viber = contact_info['viber']
            contact_items.append(f"<div style='margin:5px 0;'><strong>💜 Viber:</strong> {viber}</div>")

        # Other contacts
        if contact_info.get('other'):
            contact_items.append(f"<div style='margin:5px 0;'><strong>ℹ️ 其他:</strong> {contact_info['other']}</div>")

        contact_html = "\n".join(contact_items)

        return f"""
    <div class="content-section" style="background:#e8f5e9; padding:12px; border-radius:6px; margin-top:15px;">
        <h4 style="margin:0 0 8px 0; font-size:14px; color:#2e7d32;">📞 达人联系方式</h4>
        <div style="font-size:13px; color:#1b5e20;">
{contact_html}
        </div>
    </div>
"""

    def _build_tier_section(self, influencers: List[Dict], tier: int,
                           tier_name: str) -> str:
        """Build HTML for a single tier."""
        tier_class = f"tier-{tier}"

        cards_html = []
        for i, inf in enumerate(influencers, 1):
            # Extract metrics from dimension_scores
            dim_scores = inf.get('dimension_scores', {})
            engagement_metrics = dim_scores.get('engagement', {}).get('metrics', {})
            sales_metrics = dim_scores.get('sales', {}).get('metrics', {})

            # Extract contact information
            contact_info = self._extract_contact_info(inf.get('influencer_id', ''))

            # Get actual values from metrics
            follower_count = self._format_number(engagement_metrics.get('follower_count', inf.get('follower_count', 0)))
            engagement_rate = engagement_metrics.get('interaction_rate', inf.get('engagement_rate', 'N/A'))
            gpm = sales_metrics.get('max_gpm', inf.get('gpm', 0))
            gpm_display = f"{gpm:.2f}" if isinstance(gpm, (int, float)) and gpm > 0 else "暂无"

            # Generate contact info HTML
            contact_html = self._generate_contact_section(contact_info)

            # Generate detailed analysis
            detailed_analysis = self._generate_detailed_analysis(inf, tier)

            card_html = f"""
<div class="influencer-card">
    <div class="card-header">
        <div class="card-title">
            #{i}. {inf.get('nickname', 'Unknown')} - @{inf.get('unique_id', '')}
        </div>
        <div class="total-score">{inf.get('total_score', 0):.1f}</div>
    </div>

    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-label">粉丝数</div>
            <div class="metric-value">{follower_count}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">互动率</div>
            <div class="metric-value">{engagement_rate}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">GPM</div>
            <div class="metric-value">{gpm_display}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">地区</div>
            <div class="metric-value">{inf.get('region', 'US')}</div>
        </div>
    </div>

    {contact_html}

    {detailed_analysis}
</div>
"""
            cards_html.append(card_html)

        return f"""
<div class="section">
    <div class="tier-section">
        <div class="tier-header {tier_class}">
            🏆 Tier {tier}: {tier_name}
        </div>
        {"".join(cards_html)}
    </div>
</div>
"""

    def _format_number(self, num) -> str:
        """Format large numbers with K/M suffix."""
        if not isinstance(num, (int, float)):
            return str(num)

        num = float(num)
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        elif num >= 1_000:
            return f"{num/1_000:.1f}K"
        else:
            return str(int(num))

    def _generate_detailed_analysis(self, inf: Dict, tier: int) -> str:
        """Generate detailed analysis with charts integration."""
        dim_scores = inf.get('dimension_scores', {})
        charts = inf.get('charts', [])

        # All tiers now get full analysis with complete data visualization
        # Only difference is the recommendation emphasis level
        return self._generate_full_analysis(inf, dim_scores, charts, tier)

    def _generate_full_analysis(self, inf: Dict, dim_scores: Dict, charts: List, tier: int = 1) -> str:
        """Generate full detailed analysis with complete visualization for all tiers."""
        # Extract detailed metrics
        engagement_data = dim_scores.get('engagement', {})
        sales_data = dim_scores.get('sales', {})
        audience_data = dim_scores.get('audience_match', {})
        content_data = dim_scores.get('content_fit', {})
        growth_data = dim_scores.get('growth', {})
        stability_data = dim_scores.get('stability', {})

        # Build strengths based on high scores
        strengths = []
        weaknesses = []

        for dim_name, dim_data in [
            ('互动能力', engagement_data),
            ('带货能力', sales_data),
            ('受众匹配', audience_data),
            ('内容契合', content_data),
            ('成长性', growth_data),
            ('稳定性', stability_data)
        ]:
            score = dim_data.get('score', 0)
            reasoning = dim_data.get('reasoning', '')

            if score >= 75:
                strengths.append(f"<strong>{dim_name}</strong>({score:.0f}分): {reasoning}")
            elif score < 50:
                weaknesses.append(f"<strong>{dim_name}</strong>({score:.0f}分): {reasoning}")

        if not strengths:
            strengths.append("综合表现均衡,各维度得分较为平均")
        if not weaknesses:
            weaknesses.append("无明显短板,各项指标发展均衡")

        # Generate recommendation reasoning (adjusted by tier)
        total_score = inf.get('total_score', 0)

        # Adjust recommendation level based on tier
        if tier == 1:
            # Tier 1: Top recommendation
            if total_score >= 80:
                rec_level = "⭐️ 强烈推荐 (首选)"
                rec_reason = f"综合得分{total_score:.1f}分,在所有维度都表现优异,是最理想的合作对象。"
            elif total_score >= 70:
                rec_level = "⭐️ 推荐 (首选)"
                rec_reason = f"综合得分{total_score:.1f}分,多数维度表现良好,是优先考虑的合作伙伴。"
            else:
                rec_level = "✓ 推荐 (首选)"
                rec_reason = f"综合得分{total_score:.1f}分,在关键维度有优势,推荐优先合作。"
        elif tier == 2:
            # Tier 2: Alternative recommendation
            if total_score >= 80:
                rec_level = "强烈推荐 (备选)"
                rec_reason = f"综合得分{total_score:.1f}分,表现优异,是可靠的备选方案。"
            elif total_score >= 70:
                rec_level = "推荐 (备选)"
                rec_reason = f"综合得分{total_score:.1f}分,表现良好,适合作为备选合作对象。"
            else:
                rec_level = "可考虑 (备选)"
                rec_reason = f"综合得分{total_score:.1f}分,可作为补充备选方案。"
        else:
            # Tier 3: Supplementary recommendation
            if total_score >= 70:
                rec_level = "可考虑 (候补)"
                rec_reason = f"综合得分{total_score:.1f}分,作为候补方案,在特定场景下可能适合。"
            else:
                rec_level = "备用选项"
                rec_reason = f"综合得分{total_score:.1f}分,可在必要时作为补充选择。"

        # Add insights from top 2 strengths
        top_strengths = inf.get('strengths', [])[:2]
        if top_strengths:
            rec_reason += f" 特别是在{'/'.join(top_strengths)}方面有突出表现。"

        # Integrate charts
        charts_html = ""
        if charts:
            charts_html = '<div class="content-section"><h3>📊 数据可视化分析</h3><div class="charts-container">'

            for chart in charts:
                chart_path = chart.get('file_path', '')
                chart_name = chart.get('chart_name', '')
                insights = chart.get('insights', [])

                # Use relative path instead of embedding (charts are too large)
                if chart_path.endswith('.html') and os.path.exists(chart_path):
                    try:
                        # Convert absolute path to relative path from report location
                        # report is at: output/reports/20251105_180530/report.html
                        # charts are at: output/reports/20251105_180530/charts/xxx.html
                        # relative path: ./charts/xxx.html
                        chart_filename = os.path.basename(chart_path)
                        relative_chart_path = f"./charts/{chart_filename}"

                        charts_html += f'''
<div class="chart-wrapper">
    <h4>{'雷达图' if 'radar' in chart_name else '销售漏斗' if 'funnel' in chart_name else '受众画像' if 'pyramid' in chart_name else '品类分布' if ('pie' in chart_name or 'category' in chart_name) else '互动趋势' if 'trend' in chart_name else '成长质量' if 'growth' in chart_name else chart_name}</h4>
    <div style="width:100%; height:550px;">
        <iframe src='{relative_chart_path}' loading="lazy" style="width:100%; height:100%; border:none;"></iframe>
    </div>
    <div style="margin-top:10px; font-size:14px; color:#666;">
        <strong>洞察:</strong> {' | '.join(insights[:3]) if insights else '详见图表'}
    </div>
</div>
'''
                    except:
                        pass

            charts_html += '</div></div>'

        return f"""
    <div class="card-content-grid">
        <div class="content-section">
            <h3>💪 核心优势</h3>
            <ul class="strengths-list">
                {"".join(f"<li>{s}</li>" for s in strengths)}
            </ul>
        </div>

        <div class="content-section">
            <h3>⚠️ 潜在风险</h3>
            <ul class="weaknesses-list">
                {"".join(f"<li>{w}</li>" for w in weaknesses)}
            </ul>
        </div>
    </div>

    {charts_html}

    <div class="content-section">
        <h3>💡 推荐理由与合作建议</h3>
        <div style="background:#f8f9fa; padding:15px; border-radius:8px; border-left:4px solid #667eea;">
            <p style="margin-bottom:12px;"><strong>推荐等级:</strong> {rec_level}</p>
            <p style="margin-bottom:12px;">{rec_reason}</p>
            <p style="margin-bottom:8px;"><strong>合作建议:</strong></p>
            <ul style="margin:0; padding-left:20px;">
                {self._generate_collaboration_tips(inf, dim_scores)}
            </ul>
        </div>
    </div>
"""


    def _generate_collaboration_tips(self, inf: Dict, dim_scores: Dict) -> str:
        """Generate comprehensive collaboration tips based on strengths."""
        tips = []

        # 获取达人数据
        engagement_score = dim_scores.get('engagement', {}).get('score', 0)
        sales_score = dim_scores.get('sales', {}).get('score', 0)
        audience_score = dim_scores.get('audience_match', {}).get('score', 0)
        content_score = dim_scores.get('content_fit', {}).get('score', 0)
        growth_score = dim_scores.get('growth', {}).get('score', 0)
        influence_score = dim_scores.get('influence', {}).get('score', 0)

        # 1. 核心优势结合策略
        tips.append("<li><strong>💡 优势结合策略:</strong> ")
        strategy_parts = []

        if engagement_score >= 70 and content_score >= 70:
            strategy_parts.append("利用其高互动率与内容契合度优势，设计互动性强的原生广告(如挑战赛、教程类内容)，最大化粉丝参与和品牌认同")
        elif sales_score >= 70 and audience_score >= 70:
            strategy_parts.append("结合其强带货能力与精准受众，重点推广转化型产品，采用佣金+固定费用模式激励销售")
        elif growth_score >= 70:
            strategy_parts.append("把握其成长红利期，以较低成本锁定长期合作，随着达人影响力提升获得更高ROI")
        elif influence_score >= 70:
            strategy_parts.append("发挥其高影响力优势，聚焦品牌曝光和形象提升，适合新品发布或品牌升级场景")
        else:
            strategy_parts.append("建议从小规模测试合作开始，根据数据表现调整合作深度和投入")

        tips.append(strategy_parts[0] if strategy_parts else "综合评估后制定合作策略")
        tips.append("</li>")

        # 2. 建联方式建议
        tips.append("<li><strong>🤝 建联方式:</strong> ")
        contact_methods = []

        # 根据达人等级选择建联方式
        total_score = inf.get('total_score', 0)
        if total_score >= 75:
            contact_methods.append("优先通过MCN机构或经纪人联系(更专业高效)")
            contact_methods.append("准备详细的合作企划书和预算方案")
        elif total_score >= 60:
            contact_methods.append("可直接私信联系，同时关注其是否有商务邮箱")
            contact_methods.append("附上品牌简介和初步合作意向")
        else:
            contact_methods.append("直接私信或评论区留言，表达合作兴趣")

        if sales_score >= 60:
            contact_methods.append("强调产品佣金优势和销售支持")

        tips.append("；".join(contact_methods[:2]))
        tips.append("</li>")

        # 3. 合作模式建议
        tips.append("<li><strong>📋 合作模式:</strong> ")

        if sales_score >= 70:
            tips.append("佣金+固定费用模式，设置阶梯佣金激励销售")
        elif engagement_score >= 70:
            tips.append("按互动效果付费(CPE)，关注评论、点赞、分享等互动数据")
        elif influence_score >= 70:
            tips.append("按曝光付费(CPM)，适合品牌宣传和新品发布")
        else:
            tips.append("固定费用 + 效果分成，兼顾保底和激励")

        # 添加合作周期建议
        if growth_score >= 70:
            tips.append("，建议签订6-12个月长约锁定成长红利")
        elif growth_score < 40:
            tips.append("，建议1-3个月短期合作测试效果")
        else:
            tips.append("，建议3-6个月中期合作观察表现")

        tips.append("</li>")

        # 4. 风险规避要点
        tips.append("<li><strong>⚠️ 风险规避:</strong> ")
        risks = []

        # 内容风险
        if content_score < 60:
            risks.append("内容契合度较低，需详细审核内容脚本，避免品牌调性偏差")

        # 数据真实性风险
        if engagement_score < 40 or (engagement_score < 50 and influence_score >= 70):
            risks.append("互动率偏低可能存在刷粉风险，建议使用第三方工具核验数据真实性")

        # 销售能力风险
        if sales_score < 40 and audience_score >= 70:
            risks.append("带货经验不足，建议提供详细的产品培训和话术支持")

        # 增长风险
        if growth_score < 30:
            risks.append("账号增长停滞，需评估是否值得长期投入，建议短期测试")

        # 通用风险
        risks.append("签约前必须审核历史内容，确保无违规、负面内容")
        risks.append("合同中明确内容审核权、修改次数、违约责任等条款")

        tips.append("；".join(risks[:3]))
        tips.append("</li>")

        # 5. 执行建议
        tips.append("<li><strong>🎯 执行要点:</strong> ")
        execution = []

        if content_score >= 70:
            execution.append("给予充分的创作自由度，保持内容真实性和达人风格")
        else:
            execution.append("提供详细的内容指引和品牌调性说明，确保内容质量")

        if sales_score >= 60:
            execution.append("配合专属优惠码/链接追踪效果，提供售后支持")

        execution.append("建立定期沟通机制，及时调整策略")

        tips.append("；".join(execution[:2]))
        tips.append("</li>")

        return "".join(tips)

    def _build_comparison_section(self, comparison_data: Dict,
                                  influencers: List[Dict]) -> str:
        """Build comparison section HTML."""
        if not influencers:
            return "<p>暂无对比数据</p>"

        # Build comparison table
        table_html = """
<table class="comparison-table">
    <thead>
        <tr>
            <th>排名</th>
            <th>达人</th>
            <th>总分</th>
            <th>互动</th>
            <th>销售</th>
            <th>受众</th>
            <th>内容</th>
            <th>成长</th>
            <th>稳定</th>
        </tr>
    </thead>
    <tbody>
"""

        for i, inf in enumerate(influencers, 1):  # All influencers for comparison
            dim_scores = inf.get('dimension_scores', {})

            badge_class = f"rank-{i}" if i <= 3 else ""
            table_html += f"""
        <tr>
            <td><span class="rank-badge {badge_class}">#{i}</span></td>
            <td><strong>{inf.get('nickname', 'Unknown')}</strong></td>
            <td><strong>{inf.get('total_score', 0):.1f}</strong></td>
            <td>{dim_scores.get('engagement', {}).get('score', 0):.0f}</td>
            <td>{dim_scores.get('sales', {}).get('score', 0):.0f}</td>
            <td>{dim_scores.get('audience_match', {}).get('score', 0):.0f}</td>
            <td>{dim_scores.get('content_fit', {}).get('score', 0):.0f}</td>
            <td>{dim_scores.get('growth', {}).get('score', 0):.0f}</td>
            <td>{dim_scores.get('stability', {}).get('score', 0):.0f}</td>
        </tr>
"""

        table_html += """
    </tbody>
</table>
"""

        # Add insights
        insights_html = """
<div class="insights-box">
    <h4>关键洞察</h4>
    <ul>
        <li>综合对比显示,Top 3达人在多个维度均表现优异</li>
        <li>建议将70%预算分配给Tier 1,30%用于测试Tier 2</li>
        <li>根据实际效果动态调整合作策略</li>
    </ul>
</div>
"""

        return table_html + insights_html

    def _create_simple_report(self, content: str, title: str) -> str:
        """Create simplified text report as fallback."""
        os.makedirs("output/reports", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = f"output/reports/report_{timestamp}.txt"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"达人推荐分析报告\n")
            f.write(f"{'='*60}\n")
            f.write(f"标题: {title}\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*60}\n\n")
            f.write(content)

        return report_path


def main():
    """Main function for CLI usage."""
    import argparse

    print("""
╔═══════════════════════════════════════════════════════════╗
║   TikTok Influencer Report Generation Agent              ║
║   AI-Powered Recommendation System                        ║
╚═══════════════════════════════════════════════════════════╝
""")

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='生成达人推荐报告',
        epilog='命令行模式示例: python report_agent.py --json tiktok_达人推荐_女士香水_20251105_132850.json --query "推广女士香水" --count 10 --product "Dior Miss Dior香水"',
        add_help=True
    )
    parser.add_argument('--json', type=str, help='JSON文件名 (在output文件夹中)')
    parser.add_argument('--query', type=str, help='用户需求描述')
    parser.add_argument('--count', type=int, help='需要推荐的达人数量')
    parser.add_argument('--product', type=str, help='产品详细信息')

    args = parser.parse_args()

    # Check if any arguments were provided
    has_args = any([args.json, args.query, args.count, args.product])

    if has_args:
        # Command-line mode: validate all required arguments
        if not all([args.json, args.query, args.count, args.product]):
            print("❌ 命令行模式需要提供所有4个参数: --json, --query, --count, --product")
            print("   使用 --help 查看详细说明")
            return

        json_filename = args.json
        user_query = args.query
        target_count = args.count
        product_info = args.product

        print("📋 命令行模式 - 参数确认:")
        print(f"{'='*60}")
        print(f"数据文件: {json_filename}")
        print(f"用户需求: {user_query}")
        print(f"推荐数量: {target_count}个")
        print(f"产品信息: {product_info[:80]}{'...' if len(product_info) > 80 else ''}")
        print(f"{'='*60}\n")

    else:
        # Interactive mode
        print("欢迎使用达人推荐报告生成系统")
        print("提示: 您也可以使用命令行参数模式 (使用 --help 查看)\n")

        # Question 1: JSON file name
        print("📂 问题 1/4: 请输入JSON文件名 (在output文件夹中)")
        print("   示例: tiktok_达人推荐_女士香水_20251105_132850.json")
        json_filename = input("   > ").strip()

        if not json_filename:
            print("❌ 文件名不能为空")
            return

        # Question 2: User query
        print("\n💭 问题 2/4: 请描述您的需求")
        print("   示例: 推广高端女士香水,需要优雅风格、互动率高的达人")
        user_query = input("   > ").strip()

        if not user_query:
            print("❌ 需求描述不能为空")
            return

        # Question 3: Target count
        print("\n🎯 问题 3/4: 需要推荐多少个达人?")
        print("   建议: 5-15个")
        target_count_input = input("   > ").strip()

        try:
            target_count = int(target_count_input)
            if target_count <= 0:
                print("❌ 数量必须大于0")
                return
        except ValueError:
            print("❌ 请输入有效的数字")
            return

        # Question 4: Product info
        print("\n📦 问题 4/4: 请输入产品详细信息")
        print("   示例: Dior Miss Dior香水,花香调,目标客户25-35岁白领女性,价格800-1200元")
        product_info = input("   > ").strip()

        if not product_info:
            print("❌ 产品信息不能为空")
            return

        # Confirm inputs
        print(f"\n{'='*60}")
        print("📋 确认您的输入:")
        print(f"{'='*60}")
        print(f"数据文件: {json_filename}")
        print(f"用户需求: {user_query}")
        print(f"推荐数量: {target_count}个")
        print(f"产品信息: {product_info[:80]}{'...' if len(product_info) > 80 else ''}")
        print(f"{'='*60}")

        confirm = input("\n确认生成报告? (y/n, 默认y): ").strip().lower()
        if confirm and confirm != 'y':
            print("❌ 已取消")
            return

    # Initialize agent
    print("\n初始化Agent...")
    agent = TikTokInfluencerReportAgent()

    # Generate report
    report_path = agent.generate_report(
        json_filename=json_filename,
        user_query=user_query,
        target_count=target_count,
        product_info=product_info
    )

    if report_path:
        print(f"\n✅ 报告已保存至: {report_path}")
        print(f"\n提示: 在浏览器中打开查看完整报告")
    else:
        print("\n❌ 报告生成失败,请查看错误日志")


if __name__ == "__main__":
    main()
