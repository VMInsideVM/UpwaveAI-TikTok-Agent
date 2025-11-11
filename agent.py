"""
TikTok 达人推荐 LangChain Agent 主控制器
使用 LangChain 1.0 的 create_agent API
"""

import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent as langchain_create_agent
import pandas as pd
from datetime import datetime

# 解决 asyncio 和同步 Playwright 的冲突
import nest_asyncio
nest_asyncio.apply()

from agent_tools import get_all_tools, set_agent_instance
from main import initialize_playwright, navigate_to_url

# 加载环境变量
load_dotenv()


class TikTokInfluencerAgent:
    """TikTok 达人推荐智能 Agent"""

    def __init__(self):
        """初始化 Agent"""
        self.llm = self._init_llm()
        self.tools = get_all_tools()
        self.agent = self._create_agent()
        self.scraped_dataframes = []  # 存储爬取的数据
        self.current_product = None  # 当前商品名
        self.current_url = None  # 当前搜索 URL
        self.retry_count = 0  # 重试计数
        self.max_retries = 3  # 最大重试次数
        self.chat_history = []  # 存储对话历史

        # 新增：参数确认循环相关属性
        self.current_params = {}  # 当前收集到的所有筛选参数
        self.params_confirmed = False  # 参数是否已确认
        self.target_influencer_count = None  # 目标达人数量
        self.waiting_for_param_confirmation = False  # 🆕 是否正在等待参数确认

        # 新增：图片数据（用于报告生成）
        self.current_image = None  # 用户上传的商品图片（Base64）
        self.user_requirements_summary = ""  # 用户需求汇总（用于报告）

        # 设置全局 agent 实例，供工具访问
        set_agent_instance(self)

    def _init_llm(self) -> ChatOpenAI:
        """初始化 LLM"""
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_BASE_URL"),
            temperature=0.7,
            max_tokens=4096
        )

        # 添加 LangSmith 追踪配置
        return llm.with_config({
            "run_name": "TikTok_LLM",
            "tags": ["llm", "qwen3-vl"],
            "metadata": {
                "model": os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
                "temperature": 0.7,
                "max_tokens": 4096,
                "api_provider": "siliconflow"
            }
        })

    def _load_knowledge_base(self) -> str:
        """加载知识库"""
        kb_path = "knowledge_base.md"
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 限制长度以避免超出 token 限制
                return content[:3000] if len(content) > 3000 else content
        except Exception as e:
            print(f"⚠️ 无法加载知识库: {e}")
            return ""

    def _is_informational_question(self, user_input: str) -> bool:
        """
        判断用户输入是否为咨询性提问

        咨询性提问的特征：
        - 包含疑问词（什么、哪些、怎么、为什么、有哪几种等）
        - 不包含实质性需求信息（商品名、数量、地区等）
        - 询问系统功能、参数含义、可选值

        Returns:
            bool: True表示咨询性提问，False表示流程推进
        """
        # 疑问词列表
        question_words = [
            '什么', '哪些', '哪个', '怎么', '如何', '为什么', '为啥',
            '有哪几种', '有几种', '有什么', '是什么', '有哪些',
            '可以选', '能不能', '可不可以', '是否',
            '？', '?'  # 问号
        ]

        # 流程推进关键词（如果包含这些，很可能不是咨询）
        workflow_keywords = [
            '确认', '好的', '可以', '开始', '没问题', '行', 'ok',
            '选1', '选2', '选3', '选4', '选5', '选6',
            '修改', '调整', '换成', '改为',
            '万', '个达人', '位达人',
            # 国家名
            '美国', '英国', '日本', '印度', '泰国', '越南', '马来西亚', '菲律宾',
            '西班牙', '墨西哥', '德国', '法国', '意大利', '巴西'
        ]

        user_input_lower = user_input.lower()

        # 如果包含流程推进关键词，优先判定为非咨询
        for keyword in workflow_keywords:
            if keyword in user_input:
                return False

        # 如果包含疑问词，判定为咨询
        for word in question_words:
            if word in user_input:
                return True

        # 默认：如果很短（<10个字）且没有明确意图，判定为流程推进
        return False

    def _create_agent(self):
        """创建 Agent 使用 LangChain 1.0 API"""
        knowledge_base = self._load_knowledge_base()

        # 构建系统提示
        system_prompt = f"""你是一个专业的 TikTok 达人推荐助手,帮助用户找到最合适的达人进行商品推广。

## 知识库摘要:
{knowledge_base}

## ⚠️ 核心原则：智能对话 + 流程连贯

**你必须区分两种用户消息**:

1️⃣ **咨询性提问** (Informational Questions):
   - 用户询问系统功能、参数说明、可选值等
   - 例如: "粉丝年龄有哪几种区间？"、"认证类型是什么？"、"排序方式有哪些？"
   - **处理方式**:
     * 直接从知识库或已有信息中回答
     * **⛔ 绝对禁止调用任何工具**（不要调用 record_user_needs、match_product_category、get_max_page_number、analyze_quantity_gap 等）
     * **🌟 主动推荐（智能增值）**：
       - 如果用户在参数确认阶段询问某个筛选条件（如粉丝年龄、粉丝性别、认证类型），说明他可能想添加这个条件
       - 回答问题后，**结合商品类型给出推荐**：
         * 例如：美妆产品 → 推荐"粉丝性别：女粉为主"、"粉丝年龄：25-34岁"
         * 例如：运动产品 → 推荐"粉丝性别：男粉为主"、"粉丝年龄：18-24岁"
         * 例如：奢侈品 → 推荐"粉丝年龄：25-34岁"、"认证类型：已认证"
       - **推荐格式（必须明确提供应用方式）**：
         "💡 **针对您的商品（XXX）的智能推荐**：
         1. **粉丝性别**：建议选 `female`（女粉为主）→ ✅ 美妆香水的核心消费群体
         2. **粉丝年龄**：建议选 `25-34` → ✅ 该年龄段女性是香水主力购买人群
         3. **认证类型**：建议选 `verified` → ✅ 奢侈品推荐已认证达人提升信任度

         ---

         **如何应用这些推荐**：
         • 如果接受推荐，请回复：**'应用推荐'** 或 **'添加这些条件'**
         • 如果只想添加部分条件，请告诉我具体要添加哪些
         • 如果不需要，直接回复 **'确认当前参数'** 继续下一步"
     * 回答后**根据对话历史判断当前阶段**，提醒用户继续：
       - 如果刚展示了参数摘要（有"请您确认以上参数是否满意"）→ **⛔ 绝对不要调用任何工具，只回答问题并等待用户确认或修改参数**
       - 如果在询问排序（有"请选择排序方式"、"输入序号1-6"）→ 提醒："请选择排序方式（1-6）"
       - 如果在等待确认调整方案 → 提醒："请选择调整方案"
     * **🚨 重要**：在参数确认阶段（review_parameters 之后），只有当用户明确说"确认"、"好的"、"可以"、"应用推荐"等确认词时，才能调用 get_max_page_number 等工具推进流程。否则必须停留在参数确认阶段

2️⃣ **需求变更或流程推进** (Workflow Actions):
   - 用户提供新需求、确认参数、选择排序、修改条件等
   - 例如: "美国10w粉丝达人"、"确认"、"选1"、"修改粉丝数"
   - **处理方式**:
     * 根据当前流程阶段，调用相应工具
     * 继续推进工作流

**判断技巧**:
- 如果用户消息包含疑问词（"什么"、"哪些"、"有哪几种"、"是什么意思"），大概率是咨询性提问
- 如果用户消息包含数字、地区、商品名、确认词（"好的"、"可以"、"选X"），大概率是流程推进

## 你的工作流程:
1. **理解需求**: 询问用户的商品名称、目标国家、达人数量、粉丝要求等
   - 收集所有需要的信息（商品、国家、数量、筛选条件）
   - **一旦获得商品名称和目标达人数量，立即调用 record_user_needs 工具记录**
   - 🔥 **关键：处理模糊表达**
     * **粉丝数量模糊表达**：当用户说"30万左右"、"大约50万"、"100w差不多"等
       - **禁止**设置相同的最小值和最大值（如 followers=[300000, 300000] ❌）
       - 必须设置一个合理范围，通常为目标值的 ±15-20%
       - 示例：
         * "30万左右" → followers=[250000, 350000] ✅ (不是 [300000, 300000] ❌)
         * "大约50万" → followers=[400000, 600000] ✅ (不是 [500000, 500000] ❌)
         * "100w左右" → followers=[800000, 1200000] ✅ (不是 [1000000, 1000000] ❌)
     * **粉丝年龄模糊表达**：当用户说"年轻"、"年轻人"、"粉丝画像年轻一些"等
       - 必须映射到具体的年龄段参数
       - 映射规则：
         * "年轻"、"年轻人"、"年轻群体"、"粉丝画像年轻"、"Z世代" → followers_age="18-24"
         * "年轻白领"、"职场新人"、"轻熟" → followers_age="25-34"
         * "中年"、"成熟"、"家庭主力" → followers_age="35-44"
         * "年长"、"银发"、"中老年" → followers_age="45+"

2. **匹配分类**: 使用 match_product_category 工具推断商品分类
   - 工具会展示推理过程,让用户了解为什么选择这个分类
   - 如果找不到分类,礼貌地告知用户并结束对话
   - 分类信息会自动存储到参数中

3. **构建搜索 URL**: 使用 build_search_url 工具构建 URL
   - 传入所有收集到的筛选参数
   - 工具会自动将参数存储起来

4. **【强制】参数确认循环** - ⚠️ 此步骤必须执行，不可跳过:
   - **你必须调用 review_parameters 工具**来展示参数摘要（无需传入任何参数，工具会自动获取）
   - **禁止自己总结参数**：不要尝试自己列出参数，必须使用工具
   - **禁止直接询问用户**：不要直接说"请确认参数是否正确"，必须先调用工具展示参数
   - 工具会自动展示: 商品名称、分类、国家、目标数量、所有筛选条件的完整摘要
   - **⛔ 调用 review_parameters 工具后立即停止，结束本轮对话，等待用户的下一条消息**
   - **绝对不要在调用 review_parameters 的同一轮对话中继续执行其他操作**
   - **🚨 进入参数确认等待状态**:
     * **如果用户提出咨询性问题**（例如"账号类型有哪几种"、"认证类型是什么"）：
       - **⛔ 绝对不要调用任何工具**（特别是 get_max_page_number、analyze_quantity_gap）
       - 只回答问题并给出推荐
       - **继续等待用户确认或修改参数**
       - 不要自动推进到步骤 5
     * **只有在用户明确表示满意时才继续**:
       - 中文确认词: "好的"、"可以"、"没问题"、"行"、"开始"、"确认"、"就这样"、"ok"、"确认当前参数"、"应用推荐"、"添加这些条件"
       - 英文确认词: "yes"、"good"、"proceed"、"let's go"
       - **只有出现这些确认词，才能进入步骤 5**
   - 如果用户要调整参数:
     * 询问要修改什么
     * 使用 update_parameter 工具更新参数（如果是简单修改）
     * 或者重新调用 build_search_url 工具（如果是多个参数修改）
     * **循环回到本步骤**,再次调用 review_parameters 展示更新后的参数
   - **🔥 关键规则**: 在参数确认阶段（review_parameters 之后），**除非用户明确确认**，否则**绝对不允许调用 get_max_page_number 或任何后续工具**

5. **添加分类后缀**: 将分类工具返回的 url_suffix 追加到 URL,形成完整的搜索 URL
   - ⚠️ **关键规则**: 必须使用 match_product_category 工具返回的完整 url_suffix（格式为 &sale_category_l3=123456 或 &sale_category_l2=123456）
   - **禁止自己构造后缀**: 不要使用 &cat=、&category= 等其他格式
   - 正确示例: 基础URL + url_suffix → https://www.fastmoss.com/zh/influencer/search?region=US&follower=250000,350000&sale_category_l3=855952
   - 错误示例: https://www.fastmoss.com/zh/influencer/search?region=US&follower=250000,350000&cat=855952 ❌

6. **检查数量**: 使用 get_max_page_number(url=完整URL) 检查可用达人数
   - **重要**: 必须传递完整的 URL (包括分类后缀，格式必须是 &sale_category_lX=数字)
   - 记录最大页数,用于后续判断

7. **分析数量缺口**: 使用 analyze_quantity_gap 工具判断数量是否足够
   - 传递: max_pages (最大页数) 和 user_needs (用户需求数量)
   - 工具会返回状态: 充足/可接受/严重不足

8. **根据状态处理**:

   **情况A - 数量充足** (可用数 ≥ 用户需求):
   - 告知用户找到足够的达人（显示真实数量 available_real）
   - 询问用户希望按什么标准筛选，提供带序号的排序选项：
     "现在可以开始为您爬取数据。为了给您提供更好的推荐，请选择排序方式：

     1. 粉丝数 - 按粉丝数量排序
     2. 近28天涨粉数 - 选择近期活跃的达人
     3. 互动率 - 选择粉丝互动度高的达人
     4. 赞粉比 - 选择内容质量高的达人
     5. 近28天视频平均播放量 - 选择视频曝光度高的达人
     6. 近28天总销量 - 选择带货能力强的达人

     请输入序号（1-6）或直接说明您的需求。"
   - **等待用户回复排序方式**

   **情况B - 数量可接受** (可用数 ≥ 用户需求 × 50%):
   - 展示: "找到约 X 个达人,略少于您需要的 Y 个"
   - 询问用户:
     "您可以选择:
      1. 接受当前数量,开始爬取
      2. 调整筛选条件以找到更多达人
      请问您想怎么做?"
   - **等待用户回复**

   **情况C - 数量严重不足** (可用数 < 用户需求 × 50%):
   - 告知用户当前数量太少
   - 使用 suggest_parameter_adjustments 工具生成调整方案
   - 展示 3-5 个具体方案(包含当前值、新值、预期效果)
   - 询问用户: "请选择一个方案,或告诉我您的想法"
   - **等待用户回复**

9. **执行调整** (如果用户选择了调整方案):
   - 应用新的筛选参数
   - 重新构建 URL (保持国家和分类不变)
   - 重新检查数量 (回到步骤6)
   - **重复步骤7-8,直到用户满意**

10. **处理排序选择**:
   - 当用户输入序号（如"1"、"2"、"1,2"等）时，识别为排序选择
   - 映射规则：
     1 → "粉丝数"
     2 → "近28天涨粉数"
     3 → "互动率"
     4 → "赞粉比"
     5 → "近28天视频平均播放量"
     6 → "近28天总销量"
   - 如果用户选择多个（如"1,2"），需要分别处理：
     a. 对每个排序维度，使用 get_sort_suffix 获取 URL 后缀
     b. 将后缀追加到之前构建的完整 URL（基础 URL + 分类后缀）
     c. 将所有完整 URL 收集到一个列表中

11. **搜索达人候选**:
   - **计算爬取页数**:
     * 目标页数 = 用户需要的达人数量(X 个达人就爬 X 页)
     * 实际页数 = min(目标页数, 最大可用页数)
     * 例如: 用户要 50 个达人 → 目标 50 页，如果只有 30 页可用 → 爬取 30 页
   - 调用 scrape_and_export_json 工具，传入:
     * urls: 所有排序维度的完整 URL 列表
     * max_pages: 计算出的实际页数
     * product_name: 商品名称
   - 工具会返回找到的达人候选数量和保存的 JSON 文件路径

12. **自动获取详细数据** (关键步骤):
   - **立即调用** process_influencer_detail 工具
   - 传入参数:
     * json_file_path: 上一步返回的 JSON 文件路径
     * cache_days: 3 (默认值)
   - 这个工具会:
     * 自动显示实时进度条
     * 显示预估完成时间
     * 批量获取所有达人的详细信息（粉丝画像、带货数据等）
   - **注意**: 这是一个耗时操作，工具会自动显示进度，不需要你做任何额外提示

13. **生成推荐报告** (最终步骤):
   - 在详细数据获取完成后，**立即调用** generate_recommendation_report 工具
   - 传入参数:
     * json_file_path: 与步骤12相同的 JSON 文件路径
     * product_name: 商品名称
     * user_requirements: 用户需求摘要（从对话历史中总结，包括国家、粉丝要求、带货需求等）
     * top_n: 推荐达人数量（默认10，根据用户需要的达人数量调整）
   - 工具会:
     * 使用 AI 智能分析所有达人数据
     * 根据用户需求进行精准排序和推荐
     * 为每位达人生成推荐理由和亮点标签
     * 生成精美的 HTML 网页报告
     * 返回可在浏览器中打开的报告链接
   - 将报告链接展示给用户，告知他们：
     "✅ 所有达人数据分析完成！已为您生成精美的推荐报告，包含 AI 智能分析的推荐理由和数据亮点。

     🔗 点击链接在浏览器中查看完整报告：[报告链接]

     报告包含详细的达人对比和推荐排名，助您快速选择最合适的合作对象！"

## 重要规则:
- **记住上下文**: 你拥有完整的对话历史，必须记住之前的所有信息（商品名、国家、URL、筛选条件、用户需求达人数量等）
- **🔥 智能处理临时提问**:
  * **如果用户在流程中提出咨询性问题**（例如"粉丝年龄有哪些选项"、"认证类型是什么意思"）：
    - **⛔ 绝对禁止调用任何工具**（特别是不要调用 record_user_needs、match_product_category、build_search_url、get_max_page_number、analyze_quantity_gap 等）
    - 直接回答问题（从知识库或对话历史中获取答案）
    - **🌟 主动推荐筛选条件**（如果用户在参数确认阶段询问）：
      * 美妆/护肤/香水类 → 推荐：粉丝性别女粉为主、粉丝年龄25-34岁、认证类型已认证
      * 运动/健身类 → 推荐：粉丝性别男粉为主、粉丝年龄18-24岁
      * 母婴/儿童类 → 推荐：粉丝性别女粉为主、粉丝年龄25-34岁
      * 奢侈品/高端产品 → 推荐：认证类型已认证、粉丝年龄25-34岁或35-44岁
      * 数码/科技类 → 推荐：粉丝性别男粉为主、粉丝年龄18-24岁或25-34岁
      * **必须明确告知应用方式**："💡 针对您的商品（XXX），建议添加：
        1. 粉丝年龄：25-34岁（主力消费群）
        2. 粉丝性别：女粉为主
        3. 认证类型：已认证

        **如何应用**：
        • 回复 '应用推荐' 自动添加
        • 回复 '确认当前参数' 保持现状继续
        • 告诉我具体要添加/修改什么"
    - **回答后，查看对话历史判断当前阶段**：
      * 如果最后的工具调用是 review_parameters → **⛔ 绝对不要调用 get_max_page_number 等工具，必须等待用户明确确认**
      * 如果最后消息包含"请选择排序方式"或"输入序号（1-6）" → 提醒："请选择排序方式（1-6）"
      * 如果最后消息是询问调整方案 → 提醒："请选择调整方案"
    - **🚨 关键防御机制**：如果发现自己在回答咨询问题的同时调用了 get_max_page_number 或 analyze_quantity_gap，立即停止，这是错误的行为
  * **判断是否为咨询性提问的关键特征**：
    - 包含疑问词：什么、哪些、怎么、为什么、有哪几种
    - 不包含新的商品名、数量、地区等实质性需求信息
    - 不包含确认词：确认、好的、可以、应用推荐等
    - 询问系统功能、参数含义、可选值
  * **只有在用户明确提出新需求时才重新开始工作流**（例如："我要换个商品"、"重新开始"）
- **强制调用 review_parameters 工具**: 在调用 build_search_url 之后，**必须调用 review_parameters 工具**展示参数
- **禁止自己展示参数**: 绝对不要尝试自己列出参数摘要，必须使用 review_parameters 工具
- **🛑 禁止连续操作**: 调用 review_parameters 后，**绝对不允许**在同一轮对话中调用其他工具或继续下一步
- **🛑 参数确认阶段防御**: 在 review_parameters 之后，**只有检测到用户明确确认**（"好的"、"确认"、"应用推荐"等），才允许调用 get_max_page_number。用户提问时绝对禁止推进流程
- **爬取页数计算**: 必须根据用户需求的达人数量计算爬取页数（用户要 X 个达人就爬 X 页，但不超过最大可用页数）
- 国家地区一旦确定,**绝对不能修改**
- 商品分类一旦确定,**绝对不能修改**
- 找不到商品分类时,立即礼貌地结束对话
- **绝对不能自动调整参数**,必须先询问用户意见
- 数量展示: 使用 analyze_quantity_gap 返回的 available_real (真实数量) 展示给用户
- 数量判断: 内部使用 available_conservative (保守估计) 判断是否需要调整参数
- 排序选项: 必须提供带序号的选项(1-6),方便用户输入数字选择
- **识别用户意图**: 当用户输入"1,2"或"1, 2"等数字组合时，理解为排序选择而非新的需求
- 所有回复要友好、专业、简洁
- 多维度排序时保留第一次出现的达人(去重)

## 可用工具:
你有 11 个工具可以使用,它们的描述已经包含在工具定义中。

工具列表:
1. record_user_needs - **记录用户需求（商品名称+目标达人数量）**
2. build_search_url - 构建搜索 URL（自动存储参数）
3. match_product_category - 匹配商品分类（自动存储分类信息）
4. review_parameters - 展示参数摘要供用户确认（无需传参）
5. update_parameter - 更新特定筛选参数
6. get_max_page_number - 获取最大页数
7. analyze_quantity_gap - 分析数量缺口
8. suggest_parameter_adjustments - 生成参数调整建议
9. get_sort_suffix - 获取排序后缀
10. scrape_and_export_json - 搜索达人候选并保存列表
11. process_influencer_detail - 批量获取达人详细数据（自动显示进度）"""

        # 使用 LangChain 1.0 的 create_agent (重命名为 langchain_create_agent 避免冲突)
        agent = langchain_create_agent(
            self.llm,  # 位置参数
            self.tools,  # 位置参数
            system_prompt=system_prompt,
            debug=False  # 关闭调试模式（用于生产环境）
        )

        # 为 Agent 添加 LangSmith 追踪配置
        configured_agent = agent.with_config({
            "run_name": "TikTok_Agent",
            "tags": ["agent", "tiktok-influencer", "react"],
            "metadata": {
                "agent_type": "react",
                "tool_count": len(self.tools),
                "knowledge_base": "loaded" if knowledge_base else "not_loaded"
            }
        })

        return configured_agent

    def welcome_message(self) -> str:
        """生成欢迎消息"""
        return """
╔══════════════════════════════════════════════════════════╗
║     🎯 欢迎使用 TikTok 达人推荐智能助手 🎯              ║
╚══════════════════════════════════════════════════════════╝

我可以帮助你找到最适合推广你商品的 TikTok 达人!

📋 **可用的筛选参数**:

1️⃣  **商品名称** (必填)
   例如: 口红、运动鞋、瑜伽垫

2️⃣  **国家/地区** (重要!)
   例如: 美国、英国、全部

3️⃣  **达人数量**
   例如: 我想找 50 个达人

4️⃣  **粉丝数范围**
   例如: 10万到50万粉丝、至少100万粉丝

5️⃣  **推广渠道**
   - 短视频带货
   - 直播带货
   - 不限制

6️⃣  **联系方式**
   例如: 要有邮箱、有 WhatsApp

7️⃣  **粉丝特征**
   - 性别: 男粉为主/女粉为主
   - 年龄: 18-24岁/25-34岁/35-44岁/45+

8️⃣  **其他筛选**
   - 只要认证达人
   - 只要带货达人
   - 近期在涨粉的达人

💡 **你关注哪些方面**:
   - 粉丝数量
   - 互动率
   - 带货能力
   - 涨粉速度
   - 视频播放量

---

请告诉我:
1. 你要推广什么商品?
2. 你希望在哪个国家/地区找达人?
3. 你需要多少个达人?
4. 还有其他特殊要求吗?

(你可以一次性告诉我所有信息,也可以逐步回答~)
"""

    def run(self, user_input: str) -> str:
        """
        运行 Agent 处理用户输入

        Args:
            user_input: 用户输入的文本

        Returns:
            Agent 的回复
        """
        try:
            # 保存用户需求摘要（用于报告生成）
            if user_input and user_input.strip():
                if not self.user_requirements_summary:
                    self.user_requirements_summary = user_input
                else:
                    self.user_requirements_summary += f"\n{user_input}"

            # 将用户输入添加到历史记录
            from langchain_core.messages import HumanMessage
            self.chat_history.append(HumanMessage(content=user_input))

            # 准备 LangSmith 追踪元数据
            run_metadata = {
                "user_input": user_input[:100],  # 截断长文本
                "timestamp": datetime.now().isoformat(),
                "chat_turn": len([m for m in self.chat_history if hasattr(m, 'type') and m.type == 'human']),
                "product": self.current_product or "not_set",
                "country": self.current_params.get('country_name', 'not_set'),
                "mode": "cli"
            }

            run_config = {
                "run_name": f"Agent_Run_{datetime.now().strftime('%H%M%S')}",
                "tags": ["agent-run", "sync"],
                "metadata": run_metadata
            }

            # LangChain 1.0 的 agent 返回的是 CompiledStateGraph
            # 需要调用 invoke 方法，传入完整的对话历史
            result = self.agent.invoke(
                {"messages": self.chat_history},
                config=run_config
            )

            # 提取 AI 的回复
            if "messages" in result and len(result["messages"]) > 0:
                messages = result["messages"]

                # 🔧 修复死循环：在更新历史之前，记录本轮之前的消息数量
                previous_history_len = len(self.chat_history)

                # 更新对话历史（保留 agent 返回的完整消息列表）
                self.chat_history = messages

                # 🔍 特殊处理：检查是否调用了 review_parameters 工具
                # 只有在用户**非咨询性**输入时，才强制返回工具输出以中断流程
                # 如果用户是咨询性提问，应该让AI回答问题，而不是强制返回参数摘要
                is_question = self._is_informational_question(user_input)

                if not is_question:  # 只有非咨询性输入才强制返回
                    # 只检查本轮新增的消息（避免重复返回旧的参数摘要）
                    new_messages = messages[previous_history_len:] if len(messages) > previous_history_len else []

                    # 只在新消息中查找 review_parameters
                    for msg in reversed(new_messages):
                        msg_type = type(msg).__name__
                        if msg_type == 'ToolMessage':
                            # 检查是否是 review_parameters 的返回
                            tool_name = getattr(msg, 'name', '')
                            if tool_name == 'review_parameters':
                                tool_content = getattr(msg, 'content', '')
                                if tool_content and isinstance(tool_content, str):
                                    # 返回工具输出，而不是继续等待 AI 的最终回复
                                    return tool_content

                # 从消息列表的最后开始查找最新的 AI 响应
                # 这样可以跳过中间的工具调用消息，直接找到最终回复
                for msg in reversed(messages):
                    if type(msg).__name__ == 'AIMessage':
                        content = getattr(msg, 'content', '')
                        # 找到第一个（最新的）有内容的 AI 消息
                        if content and isinstance(content, str) and content.strip():
                            return content

            # 如果没有找到有效的 AI 响应

            return "抱歉,我无法处理你的请求。Agent 没有返回有效响应。"

        except Exception as e:
            error_msg = f"❌ 处理时出错: {str(e)}\n请重新描述你的需求。"
            print(f"Error details: {e}")
            import traceback
            traceback.print_exc()
            return error_msg

    async def run_streaming(self, user_input: str):
        """
        异步流式运行 Agent 处理用户输入

        Args:
            user_input: 用户输入的文本

        Yields:
            str: Agent 响应的片段
        """
        try:
            # 将用户输入添加到历史记录
            from langchain_core.messages import HumanMessage
            self.chat_history.append(HumanMessage(content=user_input))

            # 准备 LangSmith 追踪元数据
            run_metadata = {
                "user_input": user_input[:100],
                "timestamp": datetime.now().isoformat(),
                "chat_turn": len([m for m in self.chat_history if hasattr(m, 'type') and m.type == 'human']),
                "product": self.current_product or "not_set",
                "streaming": True,
                "mode": "web"
            }

            run_config = {
                "run_name": f"Agent_Stream_{datetime.now().strftime('%H%M%S')}",
                "tags": ["agent-run", "streaming"],
                "metadata": run_metadata
            }

            # 使用 astream_events 获取流式输出
            accumulated_content = ""

            async for event in self.agent.astream_events(
                {"messages": self.chat_history},
                config=run_config,
                version="v1"
            ):
                kind = event.get("event")

                # 处理不同类型的事件
                if kind == "on_chat_model_stream":
                    # LLM 输出的内容流
                    chunk = event.get("data", {}).get("chunk", None)
                    if chunk and hasattr(chunk, "content"):
                        content = chunk.content
                        if content:
                            accumulated_content += content
                            yield content

                elif kind == "on_tool_start":
                    # 工具开始执行
                    tool_name = event.get("name", "unknown")
                    yield f"\n[正在调用工具: {tool_name}]\n"

                elif kind == "on_tool_end":
                    # 工具执行完成
                    tool_name = event.get("name", "unknown")
                    yield f"\n[工具 {tool_name} 执行完成]\n"

            # 如果没有内容输出，尝试使用同步方法
            if not accumulated_content:
                import asyncio
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self.run, user_input)
                yield response
            else:
                # 更新聊天历史（使用同步方法获取完整结果）
                result = self.agent.invoke({"messages": self.chat_history})
                if "messages" in result:
                    self.chat_history = result["messages"]

        except Exception as e:
            error_msg = f"❌ 处理时出错: {str(e)}\n请重新描述你的需求。"
            print(f"Error details: {e}")
            import traceback
            traceback.print_exc()
            yield error_msg

    def run_with_image(self, user_input: str, image_data: str) -> str:
        """
        运行 Agent 处理用户输入（支持图片）

        Args:
            user_input: 用户输入的文本
            image_data: Base64 编码的图片数据（data:image/...;base64,...格式）

        Returns:
            Agent 的回复
        """
        try:
            # 保存图片数据（用于后续报告生成）
            if image_data:
                self.current_image = image_data

            # 将用户输入添加到历史记录（包含图片）
            from langchain_core.messages import HumanMessage

            # LangChain 支持多模态消息
            # 构建包含文本和图片的消息
            message_content = []

            # 添加文本内容
            if user_input and user_input.strip():
                # 同时保存用户需求摘要（用于报告）
                if not self.user_requirements_summary:
                    self.user_requirements_summary = user_input
                else:
                    self.user_requirements_summary += f"\n{user_input}"

                message_content.append({
                    "type": "text",
                    "text": user_input
                })

            # 添加图片内容
            has_image = False
            if image_data:
                has_image = True
                # 如果图片数据是 Base64 格式（data:image/...;base64,xxx）
                # 需要提取实际的 Base64 数据
                if image_data.startswith('data:image'):
                    # 提取 Base64 部分
                    image_url = image_data
                else:
                    # 如果只是纯 Base64，添加前缀
                    image_url = f"data:image/jpeg;base64,{image_data}"

                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                })

            # 创建多模态消息
            self.chat_history.append(HumanMessage(content=message_content))

            # 准备 LangSmith 追踪元数据
            run_metadata = {
                "user_input": user_input[:100] if user_input else "image_only",
                "timestamp": datetime.now().isoformat(),
                "chat_turn": len([m for m in self.chat_history if hasattr(m, 'type') and m.type == 'human']),
                "has_image": has_image,
                "multimodal": True,
                "product": self.current_product or "not_set",
                "mode": "web"
            }

            run_config = {
                "run_name": f"Agent_Multimodal_{datetime.now().strftime('%H%M%S')}",
                "tags": ["agent-run", "multimodal", "image"],
                "metadata": run_metadata
            }

            # 调用 agent
            result = self.agent.invoke(
                {"messages": self.chat_history},
                config=run_config
            )

            # 提取 AI 的回复（与 run() 方法相同）
            if "messages" in result and len(result["messages"]) > 0:
                messages = result["messages"]

                # 🔧 修复死循环：在更新历史之前，记录本轮之前的消息数量
                previous_history_len = len(self.chat_history)

                self.chat_history = messages

                # 🔍 特殊处理：检查是否调用了 review_parameters 工具
                # 只有在用户**非咨询性**输入时，才强制返回工具输出以中断流程
                # 如果用户是咨询性提问，应该让AI回答问题，而不是强制返回参数摘要
                is_question = self._is_informational_question(user_input) if user_input else False

                if not is_question:  # 只有非咨询性输入才强制返回
                    # 只检查本轮新增的消息（避免重复返回旧的参数摘要）
                    new_messages = messages[previous_history_len:] if len(messages) > previous_history_len else []

                    # 只在新消息中查找 review_parameters
                    for msg in reversed(new_messages):
                        msg_type = type(msg).__name__
                        if msg_type == 'ToolMessage':
                            # 检查是否是 review_parameters 的返回
                            tool_name = getattr(msg, 'name', '')
                            if tool_name == 'review_parameters':
                                tool_content = getattr(msg, 'content', '')
                                if tool_content and isinstance(tool_content, str):
                                    # 返回工具输出，而不是继续等待 AI 的最终回复
                                    return tool_content

                ai_responses = []
                for msg in messages:
                    if hasattr(msg, 'type') and msg.type == 'ai':
                        if hasattr(msg, 'content') and msg.content:
                            ai_responses.append(msg.content)
                        # 工具调用由进度报告系统处理，不显示给用户

                if ai_responses:
                    return ai_responses[-1] if ai_responses[-1] else "正在处理中..."

                # 工具结果会被 agent 处理后以自然语言返回

            return "抱歉,我无法处理你的请求。Agent 没有返回有效响应。"

        except Exception as e:
            error_msg = f"❌ 处理图片时出错: {str(e)}\n请重新描述你的需求。"
            print(f"Error details: {e}")
            import traceback
            traceback.print_exc()
            return error_msg

    def scrape_with_retry(self, url: str, max_pages: int) -> Optional[pd.DataFrame]:
        """
        带重试机制的数据爬取

        Args:
            url: 搜索 URL
            max_pages: 最大页数

        Returns:
            DataFrame 或 None
        """
        for attempt in range(self.max_retries):
            try:
                print(f"🔄 尝试爬取数据 (第 {attempt + 1}/{self.max_retries} 次)...")

                # 访问 URL
                if not navigate_to_url(url):
                    print(f"⚠️ 第 {attempt + 1} 次访问URL失败")
                    continue

                # 导入并调用爬取函数
                from main import get_table_data_as_dataframe
                df = get_table_data_as_dataframe(max_pages=max_pages)

                if df is not None and not df.empty:
                    print(f"✅ 数据爬取成功! 获得 {len(df)} 个达人")
                    return df
                else:
                    print(f"⚠️ 第 {attempt + 1} 次爬取未获得数据")

            except Exception as e:
                print(f"❌ 第 {attempt + 1} 次爬取失败: {e}")

            if attempt < self.max_retries - 1:
                print("⏳ 等待 3 秒后重试...")
                import time
                time.sleep(3)

        print(f"❌ 已达到最大重试次数 ({self.max_retries}),爬取失败")
        return None

    def export_to_excel(self, product_name: str) -> str:
        """
        导出数据到 Excel

        Args:
            product_name: 商品名称

        Returns:
            导出结果消息
        """
        if not self.scraped_dataframes:
            return "❌ 没有可导出的数据,请先爬取数据"

        try:
            # 创建 output 目录
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)

            # 合并所有 DataFrame
            if len(self.scraped_dataframes) == 1:
                final_df = self.scraped_dataframes[0]
            else:
                final_df = pd.concat(self.scraped_dataframes, ignore_index=True)
                # 根据第一列(通常是达人 ID 或名称)去重
                if len(final_df.columns) > 0:
                    final_df = final_df.drop_duplicates(subset=[final_df.columns[0]], keep='first')

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tiktok_达人推荐_{product_name}_{timestamp}.xlsx"
            filepath = os.path.join(output_dir, filename)

            # 导出
            final_df.to_excel(filepath, index=False, engine='openpyxl')

            return f"""✅ 导出成功!
📁 文件路径: {filepath}
📊 达人数量: {len(final_df)}
🎉 你可以在 output 文件夹中找到这个 Excel 文件"""

        except Exception as e:
            return f"❌ 导出失败: {str(e)}"


def create_agent() -> TikTokInfluencerAgent:
    """创建并返回 Agent 实例"""
    return TikTokInfluencerAgent()


if __name__ == "__main__":
    # 测试 Agent
    print("🧪 测试 Agent 初始化...")

    try:
        agent = create_agent()
        print("✅ Agent 初始化成功!")
        print("\n" + agent.welcome_message())

        # 简单的测试对话
        test_input = "你好"
        print(f"\n📝 测试输入: {test_input}")
        response = agent.run(test_input)
        print(f"\n🤖 Agent 回复:\n{response}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
