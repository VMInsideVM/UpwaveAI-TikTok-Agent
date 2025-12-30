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
from workflow_enforcer import get_enforcer

# 加载环境变量
load_dotenv()


class TikTokInfluencerAgent:
    """TikTok 达人推荐智能 Agent"""

    def __init__(self, user_id: Optional[str] = None, session_id: Optional[str] = None, username: Optional[str] = None, callbacks: Optional[list] = None):
        """
        初始化 Agent

        Args:
            user_id: 用户 ID，用于后台任务队列
            session_id: 会话 ID，用于创建报告记录
            username: 用户名，用于任务队列显示
            callbacks: LangChain 回调列表
        """
        self.user_id = user_id  # 存储用户 ID
        self.session_id = session_id  # 存储会话 ID
        self.username = username  # 存储用户名

        # ⭐ 初始化工作流强制执行器
        self.workflow_enforcer = get_enforcer(debug=False)

        # ⭐ 合并用户提供的 callbacks 和工作流强制执行器
        self.callbacks = callbacks if callbacks else []
        if self.workflow_enforcer not in self.callbacks:
            self.callbacks.append(self.workflow_enforcer)

        self.llm = self._init_llm()
        self.tools = get_all_tools()

        # 为需要 user_id/session_id 的工具设置参数
        self._set_context_for_tools()

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
        self.user_confirmed_scraping = False  # 用户是否已确认开始搜索（新增）

        # 设置全局 agent 实例，供工具访问
        set_agent_instance(self)

    def _set_context_for_tools(self):
        """为需要 user_id/session_id 的工具设置上下文"""
        for tool in self.tools:
            # 检查工具是否有 user_id 属性
            if hasattr(tool, 'user_id'):
                tool.user_id = self.user_id
            # 检查工具是否有 session_id 属性
            if hasattr(tool, 'session_id'):
                tool.session_id = self.session_id

    def _init_llm(self) -> ChatOpenAI:
        """初始化 LLM"""
        return ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_BASE_URL"),
            temperature=0.7,
            max_tokens=4096
        )

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

    def _create_agent(self):
        """创建 Agent 使用 LangChain 1.0 API"""
        knowledge_base = self._load_knowledge_base()

        # 构建系统提示
        system_prompt = f"""你是一个专业的 TikTok 达人推荐助手,帮助用户找到最合适的达人进行商品推广。

## 知识库摘要:
{knowledge_base}

## 图像理解能力:
你可以分析用户提供的图像（本地文件或网络 URL），提取图像中的商品信息。

**使用场景**:
- 用户上传了商品图片，但没有明确说明商品名称
- 用户提供了商品图片 URL，需要识别商品类型
- 需要从图片中提取商品信息用于后续筛选

**如何使用 analyze_image 工具**:
1. 当用户提供图片路径或 URL 时，使用 analyze_image 工具分析图像
2. 对于商品图片，使用 analysis_type="product" 提取商品信息
3. 工具会返回商品名称、类别、特征、目标人群等信息
4. 将提取的商品信息用于后续的分类匹配和参数收集

**示例**:
- 用户说："这是我的产品图片：https://example.com/product.jpg"
  → 调用 analyze_image(image_url="https://example.com/product.jpg", analysis_type="product")
- 用户说："分析这张图片：C:/images/lipstick.jpg"
  → 调用 analyze_image(image_path="C:/images/lipstick.jpg", analysis_type="general")

## 你的工作流程:
1. **理解需求**: 询问用户的商品名称、目标国家、达人数量、粉丝要求等
   - 收集所有需要的信息（商品、国家、数量、筛选条件）
   - 🖼️ **图像识别**：如果用户提供了图片，先使用 analyze_image 工具识别商品
   - ⚠️ **特别重要：必须明确询问用户需要多少个达人！**
   - 将用户指定的达人数量记录下来（如果用户没说，默认10个）

2. **匹配分类**: 使用 match_product_category 工具推断商品分类
   - 工具会展示推理过程,让用户了解为什么选择这个分类
   - 如果找不到分类,礼貌地告知用户并结束对话
   - 分类信息会自动存储到参数中

3. **构建搜索 URL**: 使用 build_search_url 工具构建 URL
   - 传入所有收集到的筛选参数
   - 🚨 **极其重要：必须传入 target_influencer_count 参数！**
   - 这个参数是用户需要的达人数量（从步骤1中获取）
   - 示例调用：build_search_url(country_name="美国", ..., target_influencer_count=10)
   - 如果忘记传入这个参数，工具会返回错误，你需要重新调用
   - ✅ 完成后立即进入步骤4

4. **参数确认循环**:
   - **必须调用 review_parameters 工具**展示参数给用户
   - **调用时必须传入**:
     * current_params: 已存储的参数（从 current_params 获取）
     * product_name: 商品名称
     * target_count: 目标达人数量（从 current_params['target_count'] 获取）
     * category_info: 分类信息（从 current_params['category_info'] 获取，如果存在）
   - **⚠️ 关键要求（最高优先级）**: 工具调用后，你**必须立即生成一条消息**，将工具返回的完整文本**逐字逐句**地输出给用户
   - **绝对不能**只调用工具就结束！你必须在工具调用后继续输出内容！


   - 展示参数后，**等待用户确认**,识别以下表示满意的信号:
     * 中文: "好的"、"可以"、"没问题"、"行"、"开始"、"确认"、"就这样"、"ok"
     * 英文: "yes"、"good"、"proceed"、"let's go"

   - 如果用户要调整参数:
     * 询问要修改什么
     * 使用 update_parameter 工具更新参数（如果是简单修改）
     * 或者重新调用 build_search_url 工具（如果是多个参数修改）
     * **循环回到本步骤**,再次调用 review_parameters 展示更新后的参数

   - **只有在用户明确表示满意后**,才继续下一步

5. **添加分类后缀**: 将分类工具返回的 url_suffix 追加到 URL,形成完整的搜索 URL

6. **检查数量**: 使用 get_max_page_number(url=完整URL) 检查可用达人数
   - **重要**: 必须传递完整的 URL (包括分类后缀)
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
   - 展示 3-6 个具体方案(包含当前值、新值、预期效果)
   - 方案可能包括：放宽粉丝数、放宽商品分类、移除各种限制等
   - 询问用户: "请选择一个方案,或告诉我您的想法"
   - **等待用户回复**

9. **执行调整** (如果用户选择了调整方案):
   - **特殊处理 - 分类放宽**:
     * 如果方案包含 '_parent_category'，说明需要放宽商品分类
     * 从 changes['_parent_category'] 获取上级分类信息
     * 更新 agent.current_params['category_info'] 为父分类
     * 使用父分类的 url_suffix 替换原分类后缀
   - **常规参数调整**:
     * 应用新的筛选参数（粉丝数、认证类型等）
     * 保持国家不变
   - 重新构建 URL（使用新的分类后缀，如果分类被放宽）
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
     c. 将所有完整 URL 收集到一个列表中（这些 URL 存储在内存中，供后续使用）
   - **❌ 严禁展示 URL**:
     * 绝对不要向用户显示任何技术性的 URL 链接
     * 不要说"现在为您构建完整的搜索URL"
     * 不要显示"粉丝数排序URL"或"销量排序URL"之类的文字
     * URL 仅在内部处理，用户完全不需要看到
   - **排序处理完成后，直接简洁地告知用户**:
     "✅ 好的，已为您选择【排序方式名称】排序。

     现在可以为您提交搜索任务了！系统将在后台为您搜索和分析约 X 个达人的数据。

     请输入【确认】开始搜索，或继续调整筛选条件。"
   - **⚠️ 严格等待用户确认，绝对不要自动调用任何搜索工具！**

11. **提交搜索任务并结束对话**:
   - **触发条件**: 用户输入"确认"、"开始"、"提交"、"好的"等确认词汇
   - **⚠️ 严格执行以下步骤，不得跳过**:
     a. **第一步**: 调用 confirm_scraping 工具记录用户已确认
     b. **第二步**: 计算爬取页数:
        * 目标页数 = 用户需要的达人数量(X 个达人就爬 X 页)
        * 实际页数 = min(目标页数, 最大可用页数)
        * 例如: 用户要 50 个达人 → 目标 50 页，如果只有 30 页可用 → 爬取 30 页
     c. **第三步**: 调用 submit_search_task 工具提交后台任务，传入:
        * urls: 所有排序维度的完整 URL 列表
        * max_pages: 计算出的实际页数
        * product_name: 商品名称
   - 工具会立即返回报告 ID
   - **立即告知用户任务已提交**:
     "✅ 搜索任务已提交！

     📊 系统正在后台为您搜索和分析达人数据，预计需要几分钟时间。

     💡 您可以：
     - 点击左侧'报告库'按钮查看生成进度
     - 报告完成后会显示为'已完成'状态，点击即可查看
     - 或者继续开始新的搜索任务

     感谢您的使用！"
   - **结束对话**，不再等待后台任务完成

## 重要规则:
- **记住上下文**: 你拥有完整的对话历史，必须记住之前的所有信息（商品名、国家、URL、筛选条件、用户需求达人数量等）
- **爬取页数计算**: 必须根据用户需求的达人数量计算爬取页数（用户要 X 个达人就爬 X 页，但不超过最大可用页数）
- **⚠️ review_parameters 工具的特殊规则（最高优先级，严格执行）**:
  * 调用 review_parameters 工具后，**你必须在同一轮对话中生成一条完整的 AI 消息**
  * 这条消息的内容是：**将工具返回的文本完整复制粘贴**，不做任何修改
  * **严禁总结、改写、省略**工具返回的任何内容
  * **不要添加**"参数已展示"、"请确认"等额外话语（工具输出已包含这些）
  * **直接转发**工具返回的完整文本即可
  * ⚠️ **绝对不能只调用工具就结束响应**！你必须输出工具的返回值！
  * 如果你只调用了工具而没有生成消息，用户将看不到任何内容，这是严重的错误！
  * 这是强制性规则，违反会导致严重的用户体验问题
- 国家地区一旦确定,**绝对不能修改**
- 商品分类**默认不能修改**，但有一个例外：
  * 当达人数量严重不足时，可以通过调整方案将分类放宽到上一级（L3→L2 或 L2→L1）
  * 这是唯一允许修改分类的情况，且必须通过 suggest_parameter_adjustments 工具生成方案
  * 用户必须明确选择该方案才能执行
- 找不到商品分类时,立即礼貌地结束对话
- **绝对不能自动调整参数**,必须先询问用户意见
- 数量展示: 使用 analyze_quantity_gap 返回的 available_real (真实数量) 展示给用户
- 数量判断: 内部使用 available_conservative (保守估计) 判断是否需要调整参数
- 排序选项: 必须提供带序号的选项(1-6),方便用户输入数字选择
- **识别用户意图**: 当用户输入"1,2"或"1, 2"等数字组合时，理解为排序选择而非新的需求
- **❌ 严禁展示任何 URL 或链接**:
  * 不要在回复中展示任何以 http 或 https 开头的链接
  * 不要说"构建 URL"、"搜索 URL"等技术词汇
  * 不要显示"URL: ..."、"链接: ..."之类的内容
  * URL 是系统内部处理的技术细节，对用户完全透明
  * 用户只需要知道"已选择排序方式"即可
- 所有回复要友好、专业、简洁
- 多维度排序时保留第一次出现的达人(去重)

## 可用工具:
你有 11 个工具可以使用,它们的描述已经包含在工具定义中。

工具列表:
1. build_search_url - 构建搜索 URL（自动存储参数）
2. match_product_category - 匹配商品分类（自动存储分类信息）
3. review_parameters - 展示参数摘要供用户确认
4. update_parameter - 更新特定筛选参数
5. get_max_page_number - 获取最大页数
6. analyze_quantity_gap - 分析数量缺口
7. suggest_parameter_adjustments - 生成参数调整建议
8. get_sort_suffix - 获取排序后缀
9. confirm_scraping - **【重要】记录用户已确认开始搜索（必须在 submit_search_task 之前调用）**
10. submit_search_task - 提交后台搜索任务（必须在 confirm_scraping 之后调用）
11. process_influencer_detail - 批量获取达人详细数据（已废弃，请使用 submit_search_task）"""

        # 使用 LangChain 1.0 的 create_agent (重命名为 langchain_create_agent 避免冲突)
        agent = langchain_create_agent(
            self.llm,  # 位置参数
            self.tools,  # 位置参数
            system_prompt=system_prompt,
            debug=False  # 关闭调试模式（用于生产环境）
        )

        return agent

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
   - 只要联盟达人
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
            # 将用户输入添加到历史记录
            from langchain_core.messages import HumanMessage
            self.chat_history.append(HumanMessage(content=user_input))

            # LangChain 1.0 的 agent 返回的是 CompiledStateGraph
            # 需要调用 invoke 方法，传入完整的对话历史
            # ⭐ 支持传入 callbacks（包含工作流强制执行器）
            config = {}
            if hasattr(self, 'callbacks') and self.callbacks:
                config['callbacks'] = self.callbacks

            result = self.agent.invoke({
                "messages": self.chat_history
            }, config=config)

            # ⭐ 重置工作流强制执行器状态（为下一轮对话做准备）
            # 注意：不在这里重置，而是在处理完响应后重置

            # 提取 AI 的回复
            if "messages" in result and len(result["messages"]) > 0:
                messages = result["messages"]

                # 更新对话历史（保留 agent 返回的完整消息列表）
                self.chat_history = messages

                # 收集所有 AI 消息的内容
                ai_responses = []
                for msg in messages:
                    if hasattr(msg, 'type') and msg.type == 'ai':
                        # 检查是否有内容
                        if hasattr(msg, 'content') and msg.content:
                            ai_responses.append(msg.content)
                        # 检查是否有工具调用（但不显示技术性信息给用户）
                        # 工具调用由进度报告系统处理

                # 如果有回复,返回最后一个
                if ai_responses:
                    # ⭐ 在返回响应前重置工作流状态
                    self.workflow_enforcer.reset()
                    return ai_responses[-1] if ai_responses[-1] else "正在处理中..."

                # ⭐ 【新增】如果没有 AI 消息，检查工作流违反情况
                violation_status = self.workflow_enforcer.get_violation_status()

                if violation_status['expect_review_parameters']:
                    # Agent 调用了 build_search_url 但没有调用 review_parameters
                    print("⚠️ 工作流违反：Agent 调用了 build_search_url 但未调用 review_parameters")

                    # 🔥 强制调用 review_parameters 工具
                    try:
                        from agent_tools import ReviewParametersTool

                        # 准备参数
                        review_tool = ReviewParametersTool()
                        product_name = self.current_params.get('product_name', '未知商品')
                        target_count = self.current_params.get('target_count', 10)
                        category_info = self.current_params.get('category_info', None)

                        # 强制调用工具
                        print(f"🔧 强制调用 review_parameters: product_name={product_name}, target_count={target_count}")
                        tool_output = review_tool._run(
                            current_params=self.current_params,
                            product_name=product_name,
                            target_count=target_count,
                            category_info=category_info
                        )

                        # 重置工作流状态
                        self.workflow_enforcer.reset()

                        # 返回工具输出
                        return tool_output

                    except Exception as e:
                        print(f"❌ 强制调用 review_parameters 失败: {e}")
                        import traceback
                        traceback.print_exc()

                # 旧的降级保护机制（保留作为后备）
                from response_validator import get_validator
                validator = get_validator(debug=False)

                if validator.last_tool_calls:
                    # 查找最近的 review_parameters 调用
                    for tool_call in reversed(validator.last_tool_calls):
                        if tool_call['tool_name'] == 'review_parameters':
                            tool_output = tool_call['output']
                            print("⚠️ 检测到 review_parameters 调用但 Agent 未输出，强制返回工具输出")
                            self.workflow_enforcer.reset()
                            return tool_output

                # 检查是否有工具返回消息（不显示原始工具结果）
                # 工具结果会被 agent 处理后以自然语言返回

            # 重置工作流状态
            self.workflow_enforcer.reset()
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

            # 使用 astream_events 获取流式输出
            accumulated_content = ""

            async for event in self.agent.astream_events(
                {"messages": self.chat_history},
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

        ⭐ 双模型协作流程：
        1. 使用专门的视觉模型（IMAGE_MODEL）分析图片
        2. 将图片分析结果（文本）和用户输入合并
        3. 传给主 Agent（文本模型）继续处理

        Args:
            user_input: 用户输入的文本
            image_data: Base64 编码的图片数据（data:image/...;base64,...格式）

        Returns:
            Agent 的回复
        """
        try:
            print("[INFO] 检测到图片输入，启动双模型协作流程")

            # ⭐ 步骤 1: 使用视觉模型分析图片
            from image_analyzer import get_image_analyzer

            analyzer = get_image_analyzer()

            # 准备分析提示词
            if user_input and user_input.strip():
                # 用户提供了文字描述，使用自定义提示词
                analysis_prompt = f"""用户说："{user_input}"

请分析这张图片，提取以下信息：
1. **商品名称**：图片中商品的具体名称或类型
2. **商品类别**：所属的类别（如：美妆个护、服饰配饰、食品饮料、数码3C等）
3. **商品特征**：主要特征（颜色、材质、风格、品牌等）
4. **目标人群**：适合的用户群体（性别、年龄段等）
5. **推广场景**：适合的推广场景或使用场景

请结合用户的描述和图片内容，给出详细的分析结果。"""
            else:
                # 用户只上传了图片，没有文字
                analysis_prompt = """请分析这张商品图片，提取以下信息：

1. **商品名称**：图片中商品的具体名称或类型
2. **商品类别**：所属的类别（如：美妆个护、服饰配饰、食品饮料、数码3C等）
3. **商品特征**：主要特征（颜色、材质、风格、品牌等）
4. **目标人群**：适合的用户群体（性别、年龄段等）
5. **推广场景**：适合的推广场景或使用场景

请给出详细的分析结果。"""

            # 调用视觉模型分析图片
            if image_data.startswith('data:image'):
                # Data URL 格式 - 需要转换
                # 视觉模型的 analyze_image_from_url 期望纯 URL，不支持 data URL
                # 所以我们需要使用 HumanMessage 直接调用
                from langchain_core.messages import HumanMessage

                print("[INFO] 正在使用视觉模型分析图片（data URL格式）...")

                message = HumanMessage(
                    content=[
                        {"type": "text", "text": analysis_prompt},
                        {"type": "image_url", "image_url": {"url": image_data}}
                    ]
                )

                response = analyzer.image_model.invoke([message])
                image_analysis = response.content

            elif image_data.startswith(('http://', 'https://')):
                # HTTP/HTTPS URL
                print(f"[INFO] 正在使用视觉模型分析图片 URL: {image_data[:100]}...")
                image_analysis = analyzer.analyze_image_from_url(image_data, analysis_prompt)
            else:
                # 其他格式（可能是本地路径或纯 base64）
                print(f"[INFO] 正在使用视觉模型分析图片（未知格式，尝试作为 data URL）...")
                # 假设是纯 base64，添加前缀
                if not image_data.startswith('data:'):
                    image_data = f"data:image/jpeg;base64,{image_data}"

                message = HumanMessage(
                    content=[
                        {"type": "text", "text": analysis_prompt},
                        {"type": "image_url", "image_url": {"url": image_data}}
                    ]
                )

                response = analyzer.image_model.invoke([message])
                image_analysis = response.content

            print(f"[OK] 视觉模型分析完成，结果长度: {len(image_analysis)} 字符")
            print(f"[INFO] 图片分析结果（前200字符）: {image_analysis[:200]}...")

            # ⭐ 步骤 2: 构建包含图片分析结果的文本输入
            if user_input and user_input.strip():
                # 合并用户输入和图片分析结果
                combined_input = f"""{user_input}

【图片分析结果】
{image_analysis}

请根据以上信息（包括用户的文字描述和图片分析结果）继续处理。"""
            else:
                # 只有图片分析结果
                combined_input = f"""用户上传了一张商品图片。

【图片分析结果】
{image_analysis}

请根据图片分析结果，询问用户还需要提供哪些信息（如目标国家、达人数量、粉丝范围等）。"""

            print("[INFO] 将图片分析结果传递给主 Agent")

            # ⭐ 步骤 3: 调用主 Agent 的普通 run() 方法（纯文本输入）
            return self.run(combined_input)

        except Exception as e:
            error_msg = f"[ERROR] 处理图片时出错: {str(e)}\n请重新上传图片或描述需求。"
            print(error_msg)
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
