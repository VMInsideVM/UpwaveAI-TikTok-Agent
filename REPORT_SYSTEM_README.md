# 达人推荐报告生成系统

## 📋 系统概述

这是一个基于LangChain和AI的智能达人推荐分析报告生成系统。它能够从`influencer/`文件夹中的达人详细数据,根据用户需求生成**专业的、多维度的、个性化的**推荐报告。

### 核心特性

✅ **智能需求理解** - 用LLM深度解析用户自然语言需求
✅ **多维度评分** - 6个维度科学评估达人价值
✅ **个性化分析** - 每个达人报告都独一无二,避免千篇一律
✅ **专业可视化** - 自动生成7种交互式图表
✅ **横向对比** - 深度对比分析,提供分层建议
✅ **3x超额推荐** - 用户需要x个达人,系统推荐3x个供选择

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────┐
│      report_agent.py (主控制器)         │
│        协调整个报告生成流程              │
└──────────────┬──────────────────────────┘
               │
   ┌───────────┼───────────┬─────────────┐
   │           │           │             │
   ▼           ▼           ▼             ▼
┌──────┐  ┌─────────┐  ┌────────┐  ┌────────┐
│Scorer│  │Visualizer│ │Tools   │  │Template│
│      │  │         │  │        │  │        │
│6维度 │  │7种图表  │  │5个工具 │  │HTML    │
│评分  │  │生成     │  │        │  │模板    │
└──────┘  └─────────┘  └────────┘  └────────┘
```

---

## 📦 新增文件说明

### 核心模块

1. **report_agent.py** - 主Agent控制器
   - 协调所有工具的调用
   - 管理报告生成流程
   - 输出HTML报告

2. **report_scorer.py** - 多维度评分引擎
   - 6个评分维度算法
   - 可解释性reasoning生成
   - 动态权重调整

3. **report_visualizer.py** - 数据可视化模块
   - 7种专业图表类型
   - Plotly交互式图表
   - 自动洞察提取

4. **report_tools.py** - LangChain工具集
   - 5个专业工具
   - 与LLM集成
   - 标准化输入输出

5. **report_templates/base_template.html** - HTML报告模板
   - 响应式设计
   - 专业样式
   - 支持动态内容

### 测试文件

- **test_report_simple.py** - 快速功能测试(无LLM调用)

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install plotly kaleido scipy jinja2
```

(如果已经运行过,这些包应该已经安装好了)

### 2. 准备数据

确保`influencer/`文件夹中有达人详细数据JSON文件:

```bash
ls influencer/
# 应该看到: 7166823863484089387.json, 3673475.json, 等等
```

### 3. 运行测试

```bash
# 快速测试(不调用LLM)
python test_report_simple.py

# 输出:
# ✓ 成功加载 20 个达人
# ✓ 评分完成,Top 3: ...
# ✓ 图表生成: 2个图表生成成功
```

### 4. 生成完整报告

```bash
# 方式1: 交互式输入
python report_agent.py

# 方式2: 命令行参数
python report_agent.py "我需要推广保健品,目标30-50岁美国女性,需要互动率高的达人"
```

### 5. 查看报告

报告会保存在`output/reports/`目录:

```bash
output/
├── charts/              # 图表文件(HTML)
│   ├── 3673475_radar.html
│   ├── 3673475_sales_funnel.html
│   └── ...
└── reports/             # 报告文件(HTML)
    └── report_20251104_223000.html
```

在浏览器中打开HTML文件查看完整报告。

---

## 📊 报告内容结构

### 1. 执行摘要 (Executive Summary)
- 分析达人数统计
- Top 3平均分
- 产品类目和目标受众
- 核心洞察

### 2. Tier 1: 首选推荐 (Top X个)
每个达人包含:
- 📈 **核心指标卡片** - 粉丝数、互动率、GPM、地区
- 💪 **核心优势** - 3-5条数据支撑的优势
- ⚠️ **潜在风险** - 客观指出局限性
- 👥 **受众洞察** - 性别/年龄/地域分析
- 📊 **数据可视化** - 雷达图、趋势图等
- 💡 **合作建议** - 3-5条可执行建议
- 💰 **ROI预估** - 基于历史数据的预测

### 3. Tier 2: 优质备选 (第X+1到2X个)
- 标准版分析(比Tier 1简洁)
- 重点突出差异化优势

### 4. Tier 3: 候补方案 (第2X+1到3X个)
- 精简版分析
- 关键指标 + 推荐理由

### 5. 横向对比分析
- 📊 **对比表格** - Top 10达人6维度得分
- 📈 **可视化对比** - 平行坐标图等
- 🎯 **分层建议** - 预算分配策略
- 💡 **关键洞察** - 3-5个数据驱动的发现
- ⚖️ **Trade-off分析** - 权衡取舍建议

---

## 🔬 评分维度详解

系统对每个达人进行6个维度的评分(0-100分):

### 1. 互动能力 (Engagement) - 默认权重25%
- 平均互动率
- 爆款视频率
- 近期表现趋势

**评分公式**:
```
base_score = (互动率 / 20%) * 100
viral_bonus = 爆款率 * 100
final_score = base_score * 0.6 + viral_bonus * 0.3 + 近期趋势 * 0.1
```

### 2. 带货能力 (Sales) - 默认权重20%
- Max GPM (每千次播放销售额)
- 总销售额
- 客单价
- 转化一致性

**评分公式**:
```
gpm_score = (max_gpm / 30) * 100
revenue_score = (总销售额 / $100k) * 100
customer_score = (客单价 / $50) * 100
final_score = gpm * 0.4 + revenue * 0.3 + customer * 0.2 + 一致性 * 0.1
```

### 3. 受众匹配 (Audience Match) - 默认权重20%
- 性别分布匹配度
- 年龄分布匹配度
- 地域匹配度

**评分公式**:
```
final_score = gender_match * 0.4 + age_match * 0.4 + geo_match * 0.2
```

### 4. 内容契合 (Content Fit) - 默认权重20%
- **LLM语义分析** label_list标签
- 内容风格与品牌调性匹配
- 品牌安全检查

**评分方式**: 由LLM根据语义相关性打分(0-100)

### 5. 成长性 (Growth) - 默认权重10%
- 28天粉丝增长率
- 类目排名变化
- 时序趋势分析(线性回归)

**评分公式**:
```
growth_score = 50 + 粉丝增长率 * 5
rank_score = 50 - 排名变化率 * 2
final_score = growth * 0.5 + rank * 0.2 + 趋势 * 0.3
```

### 6. 稳定性 (Stability) - 默认权重5%
- 发布频率稳定性
- 互动数据波动性(变异系数)
- 收入一致性

**评分公式**:
```
frequency_score = 根据发布频率(理想1-3条/天)打分
volatility_score = 100 - CV(播放量) * 50
final_score = frequency * 0.4 + volatility * 0.4 + revenue_consistency * 0.2
```

---

## 🎨 可视化图表类型

系统自动为每个达人生成以下图表:

### 1. 互动趋势图 (Engagement Trend)
- 类型: 折线图(双Y轴)
- 内容: 90天播放/点赞/评论/分享趋势
- 洞察: 爆款时间点、趋势方向、波动性

### 2. 销售漏斗图 (Sales Funnel)
- 类型: 漏斗图
- 内容: 曝光 → 互动 → 销售 → 收入
- 洞察: 各层级转化率

### 3. 受众画像金字塔 (Audience Pyramid)
- 类型: 双向条形图
- 内容: 年龄-性别分布
- 洞察: 性别倾向、年龄集中度

### 4. 品类分布饼图 (Category Distribution)
- 类型: 环形饼图
- 内容: 销售品类占比
- 洞察: 品类集中度、跨品类机会

### 5. 六维能力雷达图 (Radar Chart)
- 类型: 雷达图
- 内容: 6个维度得分可视化
- 洞察: 最强/最弱维度、均衡度

### 6. 成长曲线图 (Growth Curve) *可选*
- 类型: 折线图
- 内容: 90天粉丝增长
- 洞察: 增长拐点、趋势预测

### 7. GPM箱线图 (GPM Box Plot) *可选*
- 类型: 箱线图
- 内容: GPM分布(最小/Q1/中位数/Q3/最大)
- 洞察: 销售效率稳定性

---

## 💡 使用示例

### 示例1: 保健品推广

```python
from report_agent import TikTokInfluencerReportAgent

agent = TikTokInfluencerReportAgent()

report_path = agent.generate_report(
    user_query="我需要推广针对女性的保健品(补铁+维生素),目标受众30-50岁美国女性,需要互动率高、带货能力强的达人",
    target_count=5  # 将生成15个推荐
)

print(f"报告已生成: {report_path}")
```

**系统执行流程**:
```
📂 步骤1: 加载达人数据...
✓ 成功加载20个达人

🧠 步骤2: 分析用户偏好...
✓ 偏好分析完成
  产品类目: 保健
  目标受众: {'gender': 'female', 'age_range': ['30-39', '40-49']}
  优先指标: ['engagement_rate', 'sales_performance', 'audience_match']

📊 步骤3: 多维度评分...
✓ 评分完成,Top 15达人:
  #1: UserA - 87.5分
  #2: UserB - 85.2分
  #3: UserC - 83.8分
  ...

🔍 步骤4: 内容契合度分析 (Top 15达人)...
  分析 1/15: UserA... ✓ 88分
  分析 2/15: UserB... ✓ 85分
  ...

📈 步骤5: 生成可视化图表...
  生成图表 1/10: UserA... ✓ 5张图表
  生成图表 2/10: UserB... ✓ 5张图表
  ...

📝 步骤6: 编译HTML报告...

✅ 报告生成成功!
报告路径: output/reports/report_20251104_223000.html
```

### 示例2: 自定义权重

如果用户特别关注带货能力:

```python
# 用户需求中明确提到"带货能力最重要"
# LLM会自动调整权重:
{
    "scoring_weights": {
        "sales": 0.40,        # 带货能力权重提升到40%
        "engagement": 0.20,
        "audience_match": 0.20,
        "content_fit": 0.15,
        "growth": 0.03,
        "stability": 0.02
    }
}
```

---

## 🔧 高级配置

### 自定义缓存天数

```python
from report_tools import LoadInfluencerDataTool

loader = LoadInfluencerDataTool()
result = loader._run(
    influencer_folder="influencer",
    cache_days=7,  # 修改为7天
    min_data_completeness=0.9  # 提高数据完整度要求
)
```

### 调整图表输出目录

```python
from report_visualizer import InfluencerVisualizer

visualizer = InfluencerVisualizer(output_dir="custom/charts/path")
```

### 修改HTML模板

编辑 `report_templates/base_template.html` 即可自定义报告样式。

---

## 📁 项目文件结构

```
fastmoss_MVP/
├── influencer/                  # 达人详细数据(JSON)
│   ├── 7166823863484089387.json
│   ├── 3673475.json
│   └── ... (20个文件)
│
├── output/                      # 输出目录
│   ├── charts/                  # 图表输出
│   │   ├── 3673475_radar.html
│   │   ├── 3673475_sales_funnel.html
│   │   └── ...
│   └── reports/                 # 报告输出
│       └── report_20251104_223000.html
│
├── report_templates/            # HTML模板
│   └── base_template.html
│
├── report_agent.py              # 主Agent控制器
├── report_scorer.py             # 评分引擎
├── report_visualizer.py         # 可视化模块
├── report_tools.py              # LangChain工具
├── test_report_simple.py        # 测试脚本
│
├── agent.py                     # 原有搜索Agent
├── agent_tools.py               # 原有搜索工具
├── playwright_api.py            # Playwright API服务
├── run_agent.py                 # 搜索Agent CLI
│
├── .env                         # API配置
├── requirements.txt             # 依赖包(已更新)
├── CLAUDE.md                    # 项目文档
└── REPORT_SYSTEM_README.md      # 本文档
```

---

## 🆚 vs 原有搜索系统

| 维度 | 原有搜索系统 | 新推荐报告系统 |
|------|-------------|---------------|
| **功能定位** | 搜索和爬取达人列表 | 深度分析和推荐报告 |
| **数据来源** | 实时爬取FastMoss | 读取已保存的JSON |
| **输出格式** | Excel表格 | 专业HTML报告 |
| **分析深度** | 基础筛选 | 6维度评分+LLM分析 |
| **可视化** | 无 | 7种专业图表 |
| **个性化** | 统一模板 | 每个达人独特报告 |
| **推荐策略** | 无 | 3层级推荐(Tier 1/2/3) |
| **使用场景** | 数据采集 | 决策支持 |

**两个系统是互补关系**:
1. 先用`run_agent.py`搜索和爬取达人数据 → 保存到`influencer/`
2. 再用`report_agent.py`生成深度分析报告 → 输出到`output/reports/`

---

## 🐛 故障排查

### 问题1: "找不到influencer文件夹"

**原因**: 没有达人数据
**解决**: 先运行搜索Agent采集数据
```bash
python run_agent.py
# 然后使用ProcessInfluencerListTool批量获取详情
```

### 问题2: "LLM调用失败"

**原因**: `.env`配置错误或API额度不足
**解决**: 检查`.env`文件
```bash
OPENAI_API_KEY="your-api-key"
OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
OPENAI_MODEL="Qwen/Qwen3-VL-30B-A3B-Instruct"
```

### 问题3: "图表生成失败"

**原因**: 达人数据不完整(缺少datalist等)
**解决**: 使用`--force-refresh`重新爬取达人详情

### 问题4: "报告生成很慢"

**原因**: LLM调用需要时间(每个达人需要2-3个LLM调用)
**优化**:
- 减少推荐数量(例如target_count=2 → 生成6个推荐)
- 注释掉可视化生成部分(如果只需要文字报告)

---

## 🚧 未来扩展

### 已规划功能

1. **PDF导出** - 使用weasyprint生成PDF版本
2. **实时数据更新** - 定时调用API刷新数据
3. **A/B测试模拟** - 预测不同达人组合的效果
4. **竞品分析** - 爬取竞品合作达人并对比
5. **多语言支持** - 国际化报告模板
6. **PersonalizedReportTool** - 用LLM生成完全个性化的报告文本
7. **CrossComparisonTool** - 更深度的横向对比分析

### 贡献指南

欢迎提交PR或Issue!

---

## 📞 支持

如有问题,请参考:
1. 本文档(REPORT_SYSTEM_README.md)
2. 主项目文档(CLAUDE.md)
3. 测试脚本(test_report_simple.py)

---

## 📄 许可证

MIT License

---

**🎉 享受智能达人推荐报告生成系统!**
