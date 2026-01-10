"""
LangGraph URL 构建工作流
强制执行 build_search_url → review_parameters 的工作流

使用 LangGraph 状态图确保 agent 在构建 URL 后必定调用 review_parameters
"""

from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, Dict, Any
from langchain_core.messages import AIMessage
import json


class URLBuildState(TypedDict):
    """URL 构建工作流状态"""
    # 输入参数
    params: Dict[str, Any]  # 传递给 build_search_url 的参数
    product_name: str  # 商品名称
    target_count: int  # 目标达人数量
    category_info: Optional[Dict]  # 分类信息

    # 工作流状态
    url: str  # 构建的 URL
    parameters_reviewed: bool  # 是否已展示参数
    review_output: str  # review_parameters 的输出

    # 消息历史 (用于返回给 agent)
    messages: list  # 工作流中的消息


class URLBuildWorkflow:
    """
    强制执行 build_url → review_params 的工作流

    使用 LangGraph 状态图保证:
    1. build_search_url 后必定调用 review_parameters
    2. review_parameters 的输出必定展示给用户
    3. 无法跳过任何步骤
    """

    def __init__(self, build_url_tool, review_params_tool, debug=False):
        """
        初始化工作流

        Args:
            build_url_tool: BuildURLTool 实例
            review_params_tool: ReviewParametersTool 实例
            debug: 是否启用调试输出
        """
        self.build_url_tool = build_url_tool
        self.review_params_tool = review_params_tool
        self.debug = debug
        self.graph = self._build_graph()

    def _build_graph(self):
        """构建 LangGraph 状态图"""
        workflow = StateGraph(URLBuildState)

        # 添加节点
        workflow.add_node("build_url", self._build_url_node)
        workflow.add_node("force_review", self._force_review_node)  # 🔥 强制节点

        # 设置入口点
        workflow.set_entry_point("build_url")

        # 🔥 关键: 强制路由 - build_url 后无条件进入 force_review
        workflow.add_edge("build_url", "force_review")

        # force_review 后结束
        workflow.add_edge("force_review", END)

        return workflow.compile()

    def _build_url_node(self, state: URLBuildState) -> Dict[str, Any]:
        """
        节点1: 调用 build_search_url 工具

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        if self.debug:
            print("[URLBuildWorkflow] 📍 步骤1: 构建搜索 URL")
            print(f"  参数: {json.dumps(state['params'], ensure_ascii=False, indent=2)}")

        try:
            # 调用 build_search_url 工具
            url = self.build_url_tool.invoke(state['params'])

            if self.debug:
                print(f"  ✅ URL 构建成功: {url}")

            return {
                "url": url,
                "parameters_reviewed": False,
                "messages": state.get("messages", []) + [
                    AIMessage(content=f"✅ 搜索 URL 已构建")
                ]
            }

        except Exception as e:
            error_msg = f"❌ 构建 URL 失败: {str(e)}"
            if self.debug:
                print(f"  {error_msg}")

            return {
                "url": "",
                "parameters_reviewed": False,
                "messages": state.get("messages", []) + [
                    AIMessage(content=error_msg)
                ]
            }

    def _force_review_node(self, state: URLBuildState) -> Dict[str, Any]:
        """
        节点2: 🔥 强制调用 review_parameters 工具

        这个节点无条件执行,确保参数必定被展示给用户

        Args:
            state: 当前状态

        Returns:
            更新后的状态
        """
        if self.debug:
            print("[URLBuildWorkflow] 📍 步骤2: 强制调用 review_parameters")

        try:
            # 🔥 无条件调用 review_parameters
            review_input = {
                "current_params": state['params'],
                "product_name": state['product_name'],
                "target_count": state['target_count'],
                "category_info": state.get('category_info')
            }

            review_output = self.review_params_tool.invoke(review_input)

            if self.debug:
                print(f"  ✅ 参数展示完成")
                print(f"  输出长度: {len(review_output)} 字符")

            return {
                "parameters_reviewed": True,
                "review_output": review_output,
                "messages": state.get("messages", []) + [
                    AIMessage(content=review_output)  # 🔥 将参数展示添加到消息
                ]
            }

        except Exception as e:
            error_msg = f"❌ 展示参数失败: {str(e)}"
            if self.debug:
                print(f"  {error_msg}")

            return {
                "parameters_reviewed": False,
                "review_output": error_msg,
                "messages": state.get("messages", []) + [
                    AIMessage(content=error_msg)
                ]
            }

    def execute(
        self,
        params: Dict[str, Any],
        product_name: str,
        target_count: int,
        category_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            params: 传递给 build_search_url 的参数字典
            product_name: 商品名称
            target_count: 目标达人数量
            category_info: 商品分类信息 (可选)

        Returns:
            执行结果字典,包含:
            - url: 构建的搜索 URL
            - parameters_reviewed: 是否已展示参数 (True)
            - review_output: review_parameters 的输出文本
            - messages: 工作流中的所有消息
        """
        if self.debug:
            print("=" * 60)
            print("[URLBuildWorkflow] 🚀 开始执行工作流")
            print("=" * 60)

        # 初始化状态
        initial_state = {
            "params": params,
            "product_name": product_name,
            "target_count": target_count,
            "category_info": category_info,
            "url": "",
            "parameters_reviewed": False,
            "review_output": "",
            "messages": []
        }

        # 执行图
        result = self.graph.invoke(initial_state)

        if self.debug:
            print("=" * 60)
            print("[URLBuildWorkflow] ✅ 工作流执行完成")
            print(f"  URL: {result.get('url', 'N/A')}")
            print(f"  参数已展示: {result.get('parameters_reviewed', False)}")
            print(f"  消息数量: {len(result.get('messages', []))}")
            print("=" * 60)

        return result

    def get_user_output(self, result: Dict[str, Any]) -> str:
        """
        从工作流结果中提取应该展示给用户的内容

        Args:
            result: execute() 方法返回的结果

        Returns:
            应该展示给用户的完整文本
        """
        # 返回 review_parameters 的输出
        return result.get("review_output", "")


# ============================================================================
# 辅助函数: 创建工作流实例
# ============================================================================

def create_url_build_workflow(agent_instance, debug=False):
    """
    为 agent 创建 URL 构建工作流实例

    Args:
        agent_instance: TikTokInfluencerAgent 实例
        debug: 是否启用调试模式

    Returns:
        URLBuildWorkflow 实例
    """
    from agent_tools import get_agent_instance, set_agent_instance

    # 确保 agent 实例被设置 (工具需要访问 agent)
    set_agent_instance(agent_instance)

    # 获取工具实例
    tools_dict = {tool.name: tool for tool in agent_instance.tools}

    build_url_tool = tools_dict.get("build_search_url")
    review_params_tool = tools_dict.get("review_parameters")

    if not build_url_tool or not review_params_tool:
        raise ValueError(
            "❌ 无法创建工作流: agent 缺少必要的工具 "
            "(build_search_url 或 review_parameters)"
        )

    return URLBuildWorkflow(
        build_url_tool=build_url_tool,
        review_params_tool=review_params_tool,
        debug=debug
    )


# ============================================================================
# 测试代码
# ============================================================================

if __name__ == "__main__":
    print("⚠️ 此模块需要完整的 agent 实例才能测试")
    print("请运行 test_url_workflow.py 进行测试")
