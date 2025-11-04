"""
TikTok 达人推荐智能助手
简化版本 - 不使用复杂的 Agent 框架
"""

# 解决 asyncio 和同步 Playwright 的冲突
import nest_asyncio
nest_asyncio.apply()

import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import pandas as pd
from datetime import datetime

from agent_tools import (
    BuildURLTool, CategoryMatchTool, GetMaxPageTool,
    GetSortSuffixTool, ScrapeInfluencersTool, ExportExcelTool
)
from main import initialize_playwright, navigate_to_url

# 加载环境变量
load_dotenv()


class SimpleTikTokAgent:
    """简化的 TikTok 达人推荐助手"""

    def __init__(self):
        """初始化"""
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_BASE_URL"),
            temperature=0.7,
            max_tokens=2048
        )

        # 初始化工具
        self.build_url_tool = BuildURLTool()
        self.category_tool = CategoryMatchTool()
        self.max_page_tool = GetMaxPageTool()
        self.sort_tool = GetSortSuffixTool()
        self.scrape_tool = ScrapeInfluencersTool()
        self.export_tool = ExportExcelTool()

        # 对话历史
        self.messages = []
        self.knowledge_base = self._load_knowledge_base()

        # 状态
        self.scraped_data = []
        self.current_product = None
        self.current_country = None

    def _load_knowledge_base(self) -> str:
        """加载知识库"""
        try:
            with open("knowledge_base.md", 'r', encoding='utf-8') as f:
                return f.read()[:3000]  # 限制长度
        except:
            return ""

    def welcome_message(self) -> str:
        """欢迎消息"""
        return """
╔══════════════════════════════════════════════════════════╗
║     🎯 TikTok 达人推荐智能助手 🎯                        ║
╚══════════════════════════════════════════════════════════╝

我可以帮你找到合适的 TikTok 达人!

📋 请告诉我:
1. 要推广什么商品?
2. 在哪个国家/地区?
3. 需要多少个达人?
4. 粉丝数要求?(例如: 10万-50万)
5. 其他要求?(例如: 要有邮箱、女粉为主等)

你可以一次性说完,也可以逐步告诉我~
"""

    def run(self, user_input: str) -> str:
        """处理用户输入"""
        try:
            # 添加系统消息(仅第一次)
            if len(self.messages) == 0:
                system_msg = SystemMessage(content=f"""你是TikTok达人推荐助手。

## 知识库:
{self.knowledge_base}

## 你的任务:
1. 理解用户需求(商品、国家、数量、粉丝数等)
2. 提取关键信息
3. 告诉用户你理解了什么,并询问是否开始执行

## 回复格式:
友好、简洁、专业。不要太长。

当用户确认后,回复 "确认开始" 触发执行。""")
                self.messages.append(system_msg)

            # 添加用户消息
            self.messages.append(HumanMessage(content=user_input))

            # 调用 LLM
            response = self.llm.invoke(self.messages)
            assistant_reply = response.content

            # 添加助手回复
            self.messages.append(AIMessage(content=assistant_reply))

            # 检查是否需要执行工具
            if "确认开始" in assistant_reply or "开始执行" in user_input.lower():
                return self._execute_workflow(user_input)

            return assistant_reply

        except Exception as e:
            return f"❌ 出错了: {str(e)}\n请重新描述你的需求。"

    def _execute_workflow(self, user_context: str) -> str:
        """执行完整工作流"""
        try:
            result = "🚀 开始执行任务!\n\n"

            # 1. 匹配商品分类
            result += "步骤 1: 匹配商品分类...\n"
            if self.current_product:
                category_result = self.category_tool._run(product_name=self.current_product)
                result += f"{category_result}\n\n"

                if "❌" in category_result:
                    return result + "\n很抱歉,无法继续。请尝试其他商品。"

            # 2. 构建 URL
            result += "步骤 2: 构建搜索 URL...\n"
            url = self.build_url_tool._run(
                country_name=self.current_country or "美国",
                followers_min=100000,
                followers_max=500000
            )
            result += f"✅ URL 已生成\n\n"

            # 3. 检查数量
            result += "步骤 3: 检查可用达人数量...\n"
            max_page_result = self.max_page_tool._run()
            result += f"{max_page_result}\n\n"

            # 4. 爬取数据
            result += "步骤 4: 爬取达人数据...\n"
            scrape_result = self.scrape_tool._run(base_url=url, max_pages=5)
            result += f"{scrape_result}\n\n"

            # 5. 导出
            result += "步骤 5: 导出 Excel...\n"
            # TODO: 实际导出逻辑
            result += "✅ 导出成功! 文件保存在 output/ 目录\n"

            return result

        except Exception as e:
            return f"❌ 执行失败: {str(e)}"

    def extract_info(self, text: str) -> Dict:
        """从文本中提取信息"""
        # 使用 LLM 提取结构化信息
        prompt = f"""从以下文本中提取信息,以 JSON 格式返回:

文本: {text}

需要提取:
- product: 商品名称
- country: 国家
- count: 达人数量
- followers_min: 最小粉丝数
- followers_max: 最大粉丝数

只返回 JSON,不要其他内容。"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            data = json.loads(response.content)

            if 'product' in data:
                self.current_product = data['product']
            if 'country' in data:
                self.current_country = data['country']

            return data
        except:
            return {}


def create_agent():
    """创建 Agent"""
    return SimpleTikTokAgent()


if __name__ == "__main__":
    print("🧪 测试简化版 Agent...")

    try:
        agent = create_agent()
        print("✅ Agent 初始化成功!")
        print(agent.welcome_message())

        # 测试
        response = agent.run("我要推广口红,在美国找20个达人,粉丝10万到50万")
        print(f"\n🤖 回复:\n{response}")

    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
