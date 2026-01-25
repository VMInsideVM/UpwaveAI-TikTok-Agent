"""
TikTok 达人推荐 LangGraph Agent 主控制器

使用纯 LangGraph Workflow 替代 LangChain ReAct Agent：
- Evaluator-Optimizer Workflow: 筛选参数优化
- Parallelization Workflow: 并行达人分析
- Orchestrator-Worker Pattern: 用户输入处理

保持与原 agent.py 完全相同的对外接口。
"""

import os
import uuid
from typing import List, Dict, Optional
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime

from workflows import WorkflowRunner, create_main_workflow

# 加载环境变量
load_dotenv()


class TikTokInfluencerAgent:
    """
    TikTok 达人推荐智能 Agent (LangGraph 版本)

    使用纯 LangGraph 状态机实现，完全替代 LangChain ReAct Agent。
    保持对外接口不变：run(), run_streaming(), run_with_image()
    """

    def __init__(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        username: Optional[str] = None,
        callbacks: Optional[list] = None
    ):
        """
        初始化 Agent

        Args:
            user_id: 用户 ID，用于后台任务队列
            session_id: 会话 ID，用于创建报告记录
            username: 用户名，用于任务队列显示
            callbacks: 回调列表（LangGraph 中用于进度通知）
        """
        self.user_id = user_id
        self.session_id = session_id
        self.username = username
        self.callbacks = callbacks or []

        # 初始化 LangGraph 工作流运行器
        self.workflow_runner = WorkflowRunner()
        self.thread_id = self.workflow_runner.start_new_session()

        # 兼容性属性（供工具和前端使用）
        self.scraped_dataframes = []  # 存储爬取的数据
        self.current_product = None  # 当前商品名
        self.current_url = None  # 当前搜索 URL
        self.retry_count = 0  # 重试计数
        self.max_retries = 3  # 最大重试次数
        self.chat_history = []  # 存储对话历史

        # 参数相关属性
        self.current_params = {}  # 当前收集到的所有筛选参数
        self.params_confirmed = False  # 参数是否已确认
        self.target_influencer_count = None  # 目标达人数量
        self.user_confirmed_scraping = False  # 用户是否已确认开始搜索

        # 设置全局 agent 实例（供工具访问）
        try:
            from agent_tools import set_agent_instance
            set_agent_instance(self)
        except ImportError:
            pass

        print("✅ LangGraph Workflow Agent 已初始化")

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

6️⃣  **排序方式**
   - 粉丝数
   - 近28天涨粉数
   - 互动率
   - 赞粉比
   - 视频平均播放量
   - 近28天总销量

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
            # 更新对话历史
            self.chat_history.append({"role": "user", "content": user_input})

            # 通知回调（如果有）
            self._notify_status("正在处理您的请求...")

            # 使用 LangGraph 工作流处理
            response = self.workflow_runner.run(user_input, self.thread_id)

            # 更新对话历史
            self.chat_history.append({"role": "assistant", "content": response})

            # 同步内部状态（从工作流状态中提取）
            self._sync_state_from_workflow()

            return response

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
            # 更新对话历史
            self.chat_history.append({"role": "user", "content": user_input})

            # 通知开始处理
            yield "[正在处理...]"

            # LangGraph 目前不原生支持 token 级流式输出
            # 使用分段返回模拟流式效果
            response = self.workflow_runner.run(user_input, self.thread_id)

            # 分段输出（模拟流式）
            chunk_size = 50
            for i in range(0, len(response), chunk_size):
                yield response[i:i + chunk_size]
                import asyncio
                await asyncio.sleep(0.02)  # 小延迟模拟打字效果

            # 更新对话历史
            self.chat_history.append({"role": "assistant", "content": response})

            # 同步状态
            self._sync_state_from_workflow()

        except Exception as e:
            error_msg = f"❌ 处理时出错: {str(e)}\n请重新描述你的需求。"
            print(f"Error details: {e}")
            import traceback
            traceback.print_exc()
            yield error_msg

    def run_with_image(self, user_input: str, image_data: str) -> str:
        """
        运行 Agent 处理用户输入（支持图片）

        使用双模型协作流程：
        1. 使用视觉模型分析图片
        2. 将分析结果传递给主工作流

        Args:
            user_input: 用户输入的文本
            image_data: Base64 编码的图片数据

        Returns:
            Agent 的回复
        """
        try:
            print("[INFO] 检测到图片输入，启动双模型协作流程")

            # 使用视觉模型分析图片
            from image_analyzer import get_image_analyzer

            analyzer = get_image_analyzer()

            # 准备分析提示词
            if user_input and user_input.strip():
                analysis_prompt = f"""用户说："{user_input}"

请分析这张图片，提取以下信息：
1. **商品名称**：图片中商品的具体名称或类型
2. **商品类别**：所属的类别（如：美妆个护、服饰配饰、食品饮料、数码3C等）
3. **商品特征**：主要特征（颜色、材质、风格、品牌等）
4. **目标人群**：适合的用户群体（性别、年龄段等）
5. **推广场景**：适合的推广场景或使用场景

请结合用户的描述和图片内容，给出详细的分析结果。"""
            else:
                analysis_prompt = """请分析这张商品图片，提取以下信息：

1. **商品名称**：图片中商品的具体名称或类型
2. **商品类别**：所属的类别
3. **商品特征**：主要特征
4. **目标人群**：适合的用户群体
5. **推广场景**：适合的推广场景

请给出详细的分析结果。"""

            # 调用视觉模型
            from langchain_core.messages import HumanMessage

            if image_data.startswith('data:image'):
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": analysis_prompt},
                        {"type": "image_url", "image_url": {"url": image_data}}
                    ]
                )
                response = analyzer.image_model.invoke([message])
                image_analysis = response.content
            elif image_data.startswith(('http://', 'https://')):
                image_analysis = analyzer.analyze_image_from_url(image_data, analysis_prompt)
            else:
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

            print(f"[OK] 视觉模型分析完成")

            # 构建合并输入
            if user_input and user_input.strip():
                combined_input = f"""{user_input}

【图片分析结果】
{image_analysis}

请根据以上信息继续处理。"""
            else:
                combined_input = f"""用户上传了一张商品图片。

【图片分析结果】
{image_analysis}

请根据图片分析结果，询问用户还需要提供哪些信息（如目标国家、达人数量等）。"""

            # 调用主工作流
            return self.run(combined_input)

        except Exception as e:
            error_msg = f"[ERROR] 处理图片时出错: {str(e)}\n请重新上传图片或描述需求。"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return error_msg

    def _sync_state_from_workflow(self):
        """从工作流状态同步内部状态"""
        try:
            config = {"configurable": {"thread_id": self.thread_id}}
            state = self.workflow_runner.workflow.get_state(config)

            if state.values:
                values = state.values
                # 同步关键状态
                if values.get("product_name"):
                    self.current_product = values["product_name"]
                if values.get("search_url"):
                    self.current_url = values["search_url"]
                if values.get("current_params"):
                    self.current_params = values["current_params"]
                if values.get("target_count"):
                    self.target_influencer_count = values["target_count"]
                self.params_confirmed = values.get("user_confirmed_params", False)
                self.user_confirmed_scraping = values.get("scraping_confirmed", False)

        except Exception as e:
            print(f"[Warning] 状态同步失败: {e}")

    def _notify_status(self, message: str):
        """通知状态更新"""
        for callback in self.callbacks:
            if hasattr(callback, 'on_status'):
                callback.on_status(message)

    def get_current_stage(self) -> str:
        """获取当前工作流阶段"""
        return self.workflow_runner.get_current_stage()

    def reset_session(self):
        """重置会话"""
        self.thread_id = self.workflow_runner.start_new_session()
        self.scraped_dataframes = []
        self.current_product = None
        self.current_url = None
        self.current_params = {}
        self.params_confirmed = False
        self.target_influencer_count = None
        self.user_confirmed_scraping = False
        self.chat_history = []

    # ============================================================
    # 兼容性方法（供旧代码调用）
    # ============================================================

    def scrape_with_retry(self, url: str, max_pages: int) -> Optional[pd.DataFrame]:
        """带重试机制的数据爬取（兼容性方法）"""
        from main import navigate_to_url, get_table_data_as_dataframe

        for attempt in range(self.max_retries):
            try:
                print(f"🔄 尝试爬取数据 (第 {attempt + 1}/{self.max_retries} 次)...")

                if not navigate_to_url(url):
                    print(f"⚠️ 第 {attempt + 1} 次访问URL失败")
                    continue

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
        """导出数据到 Excel（兼容性方法）"""
        if not self.scraped_dataframes:
            return "❌ 没有可导出的数据,请先爬取数据"

        try:
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)

            if len(self.scraped_dataframes) == 1:
                final_df = self.scraped_dataframes[0]
            else:
                final_df = pd.concat(self.scraped_dataframes, ignore_index=True)
                if len(final_df.columns) > 0:
                    final_df = final_df.drop_duplicates(subset=[final_df.columns[0]], keep='first')

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tiktok_达人推荐_{product_name}_{timestamp}.xlsx"
            filepath = os.path.join(output_dir, filename)

            final_df.to_excel(filepath, index=False, engine='openpyxl')

            return f"""✅ 导出成功!
📁 文件路径: {filepath}
📊 达人数量: {len(final_df)}
🎉 你可以在 output 文件夹中找到这个 Excel 文件"""

        except Exception as e:
            return f"❌ 导出失败: {str(e)}"


def create_agent(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    username: Optional[str] = None
) -> TikTokInfluencerAgent:
    """创建并返回 Agent 实例"""
    return TikTokInfluencerAgent(
        user_id=user_id,
        session_id=session_id,
        username=username
    )


if __name__ == "__main__":
    # 测试 Agent
    print("🧪 测试 LangGraph Agent 初始化...")

    try:
        agent = create_agent()
        print("✅ Agent 初始化成功!")
        print("\n" + agent.welcome_message())

        # 简单的测试对话
        test_inputs = [
            "你好",
            "我想在美国推广口红，需要30个达人",
        ]

        for test_input in test_inputs:
            print(f"\n📝 测试输入: {test_input}")
            response = agent.run(test_input)
            print(f"\n🤖 Agent 回复:\n{response}")
            print(f"\n📊 当前阶段: {agent.get_current_stage()}")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
