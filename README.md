# 🎯 TikTok 达人推荐智能助手

基于 LangChain + Qwen3-VL-30B 构建的智能 Agent,帮助你快速找到合适的 TikTok 达人进行商品推广。

## ✨ 特性

- 🤖 **智能对话**: 使用自然语言描述需求,Agent 自动理解并执行
- 🧠 **语义分类**: 自动推断商品分类,无需手动查找
- 📊 **多维度筛选**: 支持粉丝数、国家、推广渠道、联系方式等多种筛选
- 🔄 **智能调整**: 当达人数量不足时,自动建议调整策略
- 📈 **多维排序**: 支持按粉丝数、互动率、带货能力等多维度排序
- 📁 **Excel 导出**: 自动合并去重,一键导出结果

## 🏗️ 项目结构

```
UpwaveAI-TikTok-Agent/
├── agent.py                 # Agent 主控制器
├── agent_tools.py           # LangChain 工具封装
├── category_matcher.py      # 商品分类智能匹配
├── knowledge_base.md        # 知识库(可编辑)
├── run_agent.py            # 启动脚本
├── main.py                 # 爬虫核心功能
├── category.py             # 分类查询
├── influcencer.py          # 达人详情爬取
├── requirements.txt        # 依赖列表
├── .env                    # API 配置
├── categories/             # 商品分类 JSON 文件
├── output/                 # Excel 输出目录
└── README.md              # 本文件
```

## 📦 安装

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

已配置 `.env` 文件:

```env
OPENAI_API_KEY="你的API密钥"
OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
OPENAI_MODEL="Qwen/Qwen3-VL-30B-A3B-Instruct"
```

### 3. 启动 Chrome 浏览器

**重要**: Agent 需要通过 Chrome DevTools Protocol 连接浏览器

```bash
# Windows
chrome.exe --remote-debugging-port=9224

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9224

# Linux
google-chrome --remote-debugging-port=9224
```

## 🚀 使用方法

### 启动 Agent

```bash
python run_agent.py
```

### 基本对话示例

```
👤 你: 我要推广口红,在美国找 50 个达人,粉丝 10 万到 50 万,要有邮箱

🤖 Agent: 好的,我来帮你找合适的达人!
[Agent 自动执行以下步骤]
1. 分析商品"口红" → 匹配到"美妆个护 > 彩妆 > 口红"
2. 构建筛选 URL
3. 检查可用达人数量
4. 爬取数据
5. 导出 Excel

✅ 导出成功!
📁 文件: output/tiktok_达人推荐_口红_20250103_143025.xlsx
📊 达人数量: 50
```

### 特殊命令

- `help` / `帮助` - 显示帮助信息
- `reset` / `重置` - 重置对话,开始新任务
- `exit` / `退出` - 退出程序

### 测试模式

```bash
python run_agent.py --test
```

## 📋 支持的筛选参数

### 必填参数
- **商品名称**: 例如 "口红"、"运动鞋"
- **国家/地区**: 例如 "美国"、"英国"
- **达人数量**: 例如 "50个"

### 可选参数

#### 粉丝相关
- **粉丝数范围**: "10万到50万"、"至少100万"
- **粉丝性别**: "男粉为主"、"女粉为主"
- **粉丝年龄**: "18-24岁"、"25-34岁"
- **近期涨粉**: "最近在涨粉的"

#### 达人类型
- **推广渠道**: "短视频带货"、"直播带货"
- **认证状态**: "只要认证达人"
- **联盟状态**: "只要联盟达人"
- **账号类型**: "个人账号"、"企业账号"

#### 联系方式
- "要有邮箱"
- "有 WhatsApp"
- "有 Instagram"

#### 关注维度
- "看重粉丝数"
- "关注互动率"
- "看重带货能力"
- "关注涨粉速度"

## 🔧 核心模块说明

### 1. agent.py - Agent 主控制器

使用 LangChain 的 ReAct agent 模式,集成知识库和工具。

**主要功能**:
- 加载知识库指导 Agent 行为
- 管理对话历史和上下文
- 协调工具调用和数据流转
- 带重试机制的数据爬取

### 2. agent_tools.py - LangChain 工具

封装现有爬虫函数为 LangChain Tools:

- `build_search_url` - 构建搜索 URL
- `match_product_category` - 匹配商品分类
- `get_max_page_number` - 获取最大页数
- `get_sort_suffix` - 获取排序后缀
- `scrape_influencer_data` - 爬取达人数据
- `export_to_excel` - 导出 Excel

### 3. category_matcher.py - 智能分类匹配

**工作流程**:
1. 使用 LLM 推断一级分类(29个分类中选一个)
2. 加载对应的 JSON 文件
3. 语义匹配多个三级分类候选
4. 深度推理选择最佳层级(L3 > L2 > L1)
5. 返回 URL 后缀

### 4. knowledge_base.md - 知识库

**可随时编辑的 Markdown 文件**,包含:
- 所有参数的通俗易懂说明
- 示例值和使用场景
- 最佳实践建议
- 调整策略指南

编辑后无需重启,Agent 会自动加载最新内容。

## 📊 工作流程

```
用户输入
   ↓
Agent 理解需求
   ↓
商品分类推理 (LLM 语义匹配)
   ↓
构建搜索 URL (基础筛选条件)
   ↓
添加分类后缀
   ↓
检查达人数量 (get_max_page_number)
   ↓
[数量不足?] → 调整策略 → 重新构建 URL
   ↓
多维度排序? → 为每个维度爬取数据
   ↓
合并去重 (保留第一次出现)
   ↓
导出 Excel
```

## 🛡️ 错误处理

### 1. 分类未找到
```
❌ 很抱歉,无法为商品 'XXX' 找到合适的分类
```
**处理**: Agent 礼貌地结束对话

### 2. 达人数量不足
```
⚠️ 只找到 30 个达人,但你需要 100 个
```
**处理**: Agent 建议调整参数(放宽粉丝范围、移除限制条件)

### 3. 爬取失败
```
❌ 第 1 次爬取失败,正在重试...
```
**处理**: 自动重试最多 3 次

## ⚙️ 配置说明

### 修改知识库

编辑 `knowledge_base.md` 文件,添加:
- 行业经验和案例
- 自定义沟通话术
- 数据解读标准

### 调整 Agent 行为

编辑 [agent.py:60-120](agent.py#L60-L120) 中的 system prompt:
- 修改工作流程
- 调整推理策略
- 增加新功能

### 添加新的筛选参数

1. 在 `main.py` 中添加函数
2. 在 `agent_tools.py` 中创建新 Tool
3. 在 `knowledge_base.md` 中添加说明

## 🐛 常见问题

### Q: Agent 无法启动

**A**: 检查以下项:
1. Chrome 是否已启动并开放 CDP 端口 9224
2. `.env` 文件配置是否正确
3. 依赖是否完整安装: `pip install -r requirements.txt`

### Q: 找不到商品分类

**A**:
1. 检查 `categories/` 文件夹是否包含 29 个 JSON 文件
2. 商品名称是否过于模糊(尝试更具体的名称)
3. 查看 LLM 推断的一级分类是否正确

### Q: 爬取数据失败

**A**:
1. 检查网络连接
2. 确认 FastMoss 网站可访问
3. 检查筛选条件是否过于严格
4. 查看浏览器是否已登录 FastMoss

### Q: Excel 导出失败

**A**:
1. 检查 `output/` 目录是否有写入权限
2. 确认 openpyxl 已安装: `pip install openpyxl`
3. 检查文件名是否包含非法字符

## 🔄 更新日志

### v1.0 (2025-01-03)
- ✅ 初始版本发布
- ✅ 集成 LangChain ReAct Agent
- ✅ 智能商品分类匹配
- ✅ 多维度排序和数据合并
- ✅ 完整的错误处理和重试机制
- ✅ 命令行交互界面

## 📄 许可证

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

## 📧 联系方式

如有问题,请通过 GitHub Issues 联系。

---

**祝使用愉快!** 🎉
