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
   - 如果找不到分类,礼貌地告知用户并结束对话
3. **构建搜索**: 使用 build_search_url 工具构建 URL
4. **添加分类**: 将分类工具返回的 url_suffix 追加到 URL
5. **检查数量**: 使用 get_max_page_number 检查可用达人数
6. **处理不足**: 如果数量不足,建议调整参数(但**绝对不修改国家**)
7. **爬取数据**: 使用 scrape_influencer_data 爬取数据
8. **导出结果**: 使用 export_to_excel 导出 Excel

## 重要规则:
- 国家地区一旦确定,**绝对不能修改**
- 找不到商品分类时,立即礼貌地结束对话
- 所有回复要友好、专业、简洁
- 多维度排序时保留第一次出现的达人(去重)

## 可用工具:
你有 6 个工具可以使用,它们的描述已经包含在工具定义中。"""

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
            # LangChain 1.0 的 agent 返回的是 CompiledStateGraph
            # 需要调用 invoke 方法
            result = self.agent.invoke({
                "messages": [{"role": "user", "content": user_input}]
            })

            # 提取 AI 的回复
            if "messages" in result and len(result["messages"]) > 0:
                messages = result["messages"]

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
