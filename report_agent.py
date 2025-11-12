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

    def __init__(self, progress_callback=None):
        """
        Initialize the report generation agent.

        Args:
            progress_callback: Optional callback function to report progress
                               Should accept dict with keys: step, current, total, message
        """
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

        # Progress callback
        self.progress_callback = progress_callback

    def _report_progress(self, step: str, current: int, total: int, message: str):
        """
        Report progress to callback if available.

        Args:
            step: Step name (e.g., 'content_analysis', 'visualization')
            current: Current item number
            total: Total items
            message: Progress message
        """
        if self.progress_callback:
            try:
                self.progress_callback({
                    'type': 'report_progress',
                    'step': step,
                    'current': current,
                    'total': total,
                    'message': message,
                    'percent': int(current / total * 100) if total > 0 else 0
                })
            except Exception as e:
                print(f"⚠️ 进度回调失败: {e}")

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

    def generate_report(self, json_filename: str, user_query: str, target_count: int, product_info: str) -> str:
        """
        Generate influencer recommendation report.

        Args:
            json_filename: JSON file name in output folder (e.g., "tiktok_达人推荐_女士香水_20251105_132850.json")
            user_query: User's natural language requirement
            target_count: Number of top influencers needed in final report
            product_info: Detailed product information for preference analysis

        Returns:
            Path to generated HTML report
        """
        try:
            print(f"\n{'='*60}")
            print(f"开始生成推荐报告")
            print(f"{'='*60}")
            print(f"数据文件: {json_filename}")
            print(f"用户需求: {user_query}")
            print(f"产品信息: {product_info[:100]}{'...' if len(product_info) > 100 else ''}")
            print(f"目标数量: Top {target_count}个达人")
            print(f"{'='*60}\n")

            # Step 1: Load influencer data from JSON file
            print("📂 步骤1: 加载达人数据...")
            load_result = self._load_from_json_file(json_filename)

            if not load_result.get('success'):
                print(f"❌ 加载失败: {load_result.get('error')}")
                return None

            influencer_ids = load_result['influencer_ids']
            print(f"✓ 成功加载{len(influencer_ids)}个达人\n")

            # Step 2: Analyze user preferences
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

            # Step 3: Score and rank influencers
            print("📊 步骤3: 多维度评分...")
            score_result = json.loads(self.scorer_tool._run(
                influencer_ids=influencer_ids,
                preferences_json=json.dumps(preferences)
            ))

            if not score_result.get('success'):
                print(f"❌ 评分失败: {score_result.get('error')}")
                return None

            ranked_influencers = score_result['ranked_influencers'][:target_count * 3]
            print(f"✓ 评分完成,Top {len(ranked_influencers)}达人:")
            for i, inf in enumerate(ranked_influencers[:5], 1):
                print(f"  #{i}: {inf['nickname']} - {inf['total_score']:.1f}分")
            print()

            # Step 4: Content alignment analysis (for top influencers)
            print(f"🔍 步骤4: 内容契合度分析 (Top {len(ranked_influencers)}达人)...")
            for i, inf in enumerate(ranked_influencers, 1):
                # 发送进度更新到前端
                self._report_progress(
                    step='content_analysis',
                    current=i,
                    total=len(ranked_influencers),
                    message=f"正在分析 {inf['nickname']} 的内容契合度..."
                )

                print(f"  分析 {i}/{len(ranked_influencers)}: {inf['nickname']}...", end=' ')

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

            # Create timestamped report directory
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_dir = os.path.join("output/reports", timestamp)
            charts_dir = os.path.join(report_dir, "charts")
            os.makedirs(charts_dir, exist_ok=True)
            print(f"📁 创建报告目录: {report_dir}")

            # Initialize visualizer with timestamped charts directory
            self.viz_tool = DataVisualizationTool(output_dir=charts_dir)

            # Step 5: Generate visualizations (for top influencers)
            print(f"📈 步骤5: 生成可视化图表...")
            charts_generated = 0
            top_influencers_for_viz = ranked_influencers[:10]  # Only top 10 to save time
            for i, inf in enumerate(top_influencers_for_viz, 1):
                # 发送进度更新到前端
                self._report_progress(
                    step='visualization',
                    current=i,
                    total=len(top_influencers_for_viz),
                    message=f"正在为 {inf['nickname']} 生成可视化图表..."
                )

                print(f"  生成图表 {i}/{len(top_influencers_for_viz)}: {inf['nickname']}...", end=' ')

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

            # Step 6: Compile report
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

            print(f"\n{'='*60}")
            print(f"✅ 报告生成成功!")
            print(f"{'='*60}")
            print(f"报告路径: {report_path}")
            print(f"{'='*60}\n")

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
    <li><strong>推荐层级:</strong> Tier 1 ({target_count}个) + Tier 2 ({target_count}个) + Tier 3 ({target_count}个)</li>
    <li><strong>Top 3平均分:</strong> {avg_score:.1f}/100</li>
    <li><strong>产品类目:</strong> {preferences.get('product_category', '未知')}</li>
    <li><strong>目标受众:</strong> {preferences.get('target_audience', {}).get('gender', 'all')}性,
        年龄{", ".join(preferences.get('target_audience', {}).get('age_range', []))}</li>
    <li><strong>核心洞察:</strong> Top {target_count}达人在{", ".join(preferences.get('priority_metrics', [])[:2])}维度表现优异,建议优先合作</li>
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
                recommended_count=target_count * 3,
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

        # Tier 1: Top X influencers
        tier1 = influencers[:target_count]
        if tier1:
            html_parts.append(self._build_tier_section(tier1, 1, "首选推荐"))

        # Tier 2: Next X influencers
        tier2 = influencers[target_count:target_count*2]
        if tier2:
            html_parts.append(self._build_tier_section(tier2, 2, "优质备选"))

        # Tier 3: Remaining influencers
        tier3 = influencers[target_count*2:]
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

        # Determine detail level based on tier
        if tier == 1:
            # Full detailed analysis for Tier 1
            return self._generate_full_analysis(inf, dim_scores, charts)
        elif tier == 2:
            # Medium analysis for Tier 2
            return self._generate_medium_analysis(inf, dim_scores, charts)
        else:
            # Brief analysis for Tier 3
            return self._generate_brief_analysis(inf, dim_scores)

    def _generate_full_analysis(self, inf: Dict, dim_scores: Dict, charts: List) -> str:
        """Generate full detailed analysis for Tier 1."""
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

        # Generate recommendation reasoning
        total_score = inf.get('total_score', 0)
        if total_score >= 80:
            rec_level = "强烈推荐"
            rec_reason = f"综合得分{total_score:.1f}分,在所有维度都表现优异,是理想的合作对象。"
        elif total_score >= 70:
            rec_level = "推荐"
            rec_reason = f"综合得分{total_score:.1f}分,多数维度表现良好,具有较高合作价值。"
        else:
            rec_level = "可考虑"
            rec_reason = f"综合得分{total_score:.1f}分,在某些特定维度有优势,可根据具体需求评估。"

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
        <iframe src='{relative_chart_path}' style="width:100%; height:100%; border:none;"></iframe>
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

    def _generate_medium_analysis(self, inf: Dict, dim_scores: Dict, charts: List) -> str:
        """Generate medium analysis for Tier 2."""
        # Similar to full but shorter
        strengths = inf.get('strengths', ['综合表现良好'])[:3]
        weaknesses = inf.get('weaknesses', ['无明显短板'])[:2]

        # Select 1-2 key charts (use relative paths)
        key_charts = []
        for chart in charts[:2]:
            chart_path = chart.get('file_path', '')
            if chart_path.endswith('.html') and os.path.exists(chart_path):
                try:
                    chart_filename = os.path.basename(chart_path)
                    relative_chart_path = f"./charts/{chart_filename}"
                    key_charts.append((relative_chart_path, chart.get('insights', [])))
                except:
                    pass

        charts_html = ""
        if key_charts:
            charts_html = '<div class="content-section"><h3>📊 关键数据</h3><div class="charts-container">'
            for chart_path, insights in key_charts:
                charts_html += f'''
<div class="chart-wrapper">
    <iframe src='{chart_path}' style="width:100%; height:450px; border:none;"></iframe>
    <p style="font-size:13px; color:#666;">{insights[0] if insights else ''}</p>
</div>
'''
            charts_html += '</div></div>'

        return f"""
    <div class="card-content-grid">
        <div class="content-section">
            <h3>核心优势</h3>
            <ul class="strengths-list">
                {"".join(f"<li>{s}</li>" for s in strengths)}
            </ul>
        </div>

        <div class="content-section">
            <h3>注意事项</h3>
            <ul class="weaknesses-list">
                {"".join(f"<li>{w}</li>" for w in weaknesses)}
            </ul>
        </div>
    </div>

    {charts_html}

    <div class="content-section">
        <h3>推荐理由</h3>
        <p>{self._generate_simple_recommendation(inf, dim_scores)}</p>
    </div>
"""

    def _generate_brief_analysis(self, inf: Dict, dim_scores: Dict) -> str:
        """Generate brief analysis for Tier 3."""
        strengths = inf.get('strengths', ['综合表现'])[:2]
        rec = self._generate_simple_recommendation(inf, dim_scores)

        return f"""
    <div class="content-section">
        <div style="background:#f8f9fa; padding:15px; border-radius:8px;">
            <p><strong>优势:</strong> {', '.join(strengths)}</p>
            <p style="margin-top:8px;"><strong>推荐:</strong> {rec}</p>
        </div>
    </div>
"""

    def _generate_collaboration_tips(self, _inf: Dict, dim_scores: Dict) -> str:
        """Generate collaboration tips based on strengths."""
        tips = []

        # Based on engagement
        engagement_score = dim_scores.get('engagement', {}).get('score', 0)
        if engagement_score >= 70:
            tips.append("<li>利用其高互动率优势,设计互动性强的营销活动(如挑战赛、问答等)</li>")

        # Based on sales
        sales_score = dim_scores.get('sales', {}).get('score', 0)
        if sales_score >= 70:
            tips.append("<li>重点合作带货视频,可考虑佣金激励模式以最大化ROI</li>")
        elif sales_score < 40:
            tips.append("<li>电商经验有限,建议从品牌曝光类合作开始,逐步引入带货</li>")

        # Based on audience match
        audience_score = dim_scores.get('audience_match', {}).get('score', 0)
        if audience_score >= 80:
            tips.append("<li>受众高度匹配,可直接推广核心产品,转化率预期较高</li>")

        # Based on content fit
        content_score = dim_scores.get('content_fit', {}).get('score', 0)
        if content_score >= 75:
            tips.append("<li>内容风格与品牌契合度高,建议给予创作自由度,保持真实性</li>")

        # Based on growth
        growth_score = dim_scores.get('growth', {}).get('score', 0)
        if growth_score >= 70:
            tips.append("<li>处于高速成长期,建议尽早合作锁定长期关系,享受成长红利</li>")
        elif growth_score < 40:
            tips.append("<li>增长放缓,建议短期合作测试效果,根据数据决定是否长期投入</li>")

        # Default tip
        if not tips:
            tips.append("<li>建议先进行小规模测试合作,根据数据表现调整策略</li>")
            tips.append("<li>保持沟通频率,了解达人的内容规划和粉丝反馈</li>")

        # Add generic tips
        tips.append("<li>签约前务必审核达人的历史内容,确保品牌安全</li>")

        return "".join(tips[:5])  # Max 5 tips

    def _generate_simple_recommendation(self, inf: Dict, dim_scores: Dict) -> str:
        """Generate simple recommendation text."""
        total_score = inf.get('total_score', 0)

        # Find top 2 dimensions
        dims = []
        for name, data in dim_scores.items():
            score = data.get('score', 0)
            if score >= 60:
                dims.append((name, score))
        dims.sort(key=lambda x: x[1], reverse=True)

        top_dims = [self._translate_dim(d[0]) for d in dims[:2]]

        if total_score >= 70:
            return f"综合得分{total_score:.1f}分,在{'/'.join(top_dims) if top_dims else '多个维度'}表现出色,值得优先考虑合作。"
        else:
            return f"综合得分{total_score:.1f}分,适合特定场景下的备选合作,可根据预算和需求灵活安排。"

    def _translate_dim(self, dim_key: str) -> str:
        """Translate dimension key to Chinese."""
        translations = {
            'engagement': '互动能力',
            'sales': '带货能力',
            'audience_match': '受众匹配',
            'content_fit': '内容契合',
            'growth': '成长潜力',
            'stability': '稳定性'
        }
        return translations.get(dim_key, dim_key)

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

        for i, inf in enumerate(influencers[:10], 1):  # Top 10 for comparison
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
