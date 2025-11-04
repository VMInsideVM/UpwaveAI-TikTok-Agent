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

from agent_tools import get_all_tools
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

## 你的工作流程:
1. **理解需求**: 询问用户的商品名称、目标国家、达人数量、粉丝要求等
2. **匹配分类**: 使用 match_product_category 工具推断商品分类
   - 工具会展示推理过程,让用户了解为什么选择这个分类
   - 如果找不到分类,礼貌地告知用户并结束对话
3. **构建搜索**: 使用 build_search_url 工具构建 URL
4. **添加分类**: 将分类工具返回的 url_suffix 追加到 URL,形成完整的搜索 URL
5. **检查数量**: 使用 get_max_page_number(url=完整URL) 检查可用达人数
   - **重要**: 必须传递完整的 URL (包括分类后缀)
   - 记录最大页数,用于后续判断

6. **分析数量缺口**: 使用 analyze_quantity_gap 工具判断数量是否足够
   - 传递: max_pages (最大页数) 和 user_needs (用户需求数量)
   - 工具会返回状态: 充足/可接受/严重不足

7. **根据状态处理**:

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

8. **执行调整** (如果用户选择了调整方案):
   - 应用新的筛选参数
   - 重新构建 URL (保持国家和分类不变)
   - 重新检查数量 (回到步骤5)
   - **重复步骤6-7,直到用户满意**

9. **处理排序选择**:
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

10. **搜索达人候选**:
   - **计算爬取页数**:
     * 目标页数 = 用户需要的达人数量(X 个达人就爬 X 页)
     * 实际页数 = min(目标页数, 最大可用页数)
     * 例如: 用户要 50 个达人 → 目标 50 页，如果只有 30 页可用 → 爬取 30 页
   - 调用 scrape_and_export_json 工具，传入:
     * urls: 所有排序维度的完整 URL 列表
     * max_pages: 计算出的实际页数
     * product_name: 商品名称
   - 工具会返回找到的达人候选数量和保存的 JSON 文件路径

11. **自动获取详细数据** (关键步骤):
   - **立即调用** process_influencer_detail 工具
   - 传入参数:
     * json_file_path: 上一步返回的 JSON 文件路径
     * cache_days: 3 (默认值)
   - 这个工具会:
     * 自动显示实时进度条
     * 显示预估完成时间
     * 批量获取所有达人的详细信息（粉丝画像、带货数据等）
   - **注意**: 这是一个耗时操作，工具会自动显示进度，不需要你做任何额外提示
   - 等待工具完成后，告知用户："所有达人的详细数据已获取完成，可供后续分析使用"

## 重要规则:
- **记住上下文**: 你拥有完整的对话历史，必须记住之前的所有信息（商品名、国家、URL、筛选条件、用户需求达人数量等）
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
你有 7 个工具可以使用,它们的描述已经包含在工具定义中。

工具列表:
1. build_search_url - 构建搜索 URL
2. match_product_category - 匹配商品分类
3. get_max_page_number - 获取最大页数
4. analyze_quantity_gap - 分析数量缺口
5. suggest_parameter_adjustments - 生成参数调整建议
6. get_sort_suffix - 获取排序后缀
7. scrape_and_export_json - 搜索达人候选并保存列表
8. process_influencer_detail - 批量获取达人详细数据（自动显示进度）"""

        # 使用 LangChain 1.0 的 create_agent (重命名为 langchain_create_agent 避免冲突)
        agent = langchain_create_agent(
            self.llm,  # 位置参数
            self.tools,  # 位置参数
            system_prompt=system_prompt,
            debug=True  # 开启调试模式
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
            result = self.agent.invoke({
                "messages": self.chat_history
            })

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
                        # 检查是否有工具调用
                        elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                            tool_info = f"[正在调用工具: {', '.join([tc['name'] for tc in msg.tool_calls])}]"
                            ai_responses.append(tool_info)

                # 如果有回复,返回最后一个
                if ai_responses:
                    return ai_responses[-1] if ai_responses[-1] else "正在处理中..."

                # 检查是否有工具返回消息
                tool_messages = [msg for msg in messages if hasattr(msg, 'type') and msg.type == 'tool']
                if tool_messages:
                    last_tool = tool_messages[-1]
                    if hasattr(last_tool, 'content'):
                        return f"工具执行结果:\n{last_tool.content}"

            return "抱歉,我无法处理你的请求。Agent 没有返回有效响应。"

        except Exception as e:
            error_msg = f"❌ 处理时出错: {str(e)}\n请重新描述你的需求。"
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
