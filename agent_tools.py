"""
LangChain Tools 封装
将现有的爬虫函数封装为 LangChain 可用的工具
"""

# 解决 asyncio 和同步 Playwright 的冲突
import nest_asyncio
nest_asyncio.apply()

from typing import Optional, List, Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import pandas as pd
from datetime import datetime
import os
import time
import json

# 导入现有函数（非 Playwright 相关）
from main import (
    build_complete_url,
    get_sort_suffix
)
from agent_category_classifier import ProductCategoryClassifierV3
import re
import requests  # 用于调用 API

# ============================================================================
# API 配置
# ============================================================================
API_BASE_URL = "http://127.0.0.1:8000"  # Playwright API 服务地址

def call_api(endpoint: str, method: str = "GET", data: Optional[Dict] = None, timeout: int = 120) -> Dict:
    """
    调用 Playwright API 的辅助函数

    Args:
        endpoint: API 端点（例如 "/navigate"）
        method: HTTP 方法（GET 或 POST）
        data: POST 请求的数据（字典）
        timeout: 超时时间（秒）

    Returns:
        API 响应的 JSON 数据

    Raises:
        Exception: API 调用失败时抛出异常
    """
    url = f"{API_BASE_URL}{endpoint}"

    try:
        if method.upper() == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        else:
            response = requests.get(url, timeout=timeout)

        response.raise_for_status()  # 如果状态码不是 2xx，抛出异常
        return response.json()

    except requests.exceptions.ConnectionError:
        raise Exception(
            f"❌ 无法连接到 Playwright API 服务 ({API_BASE_URL})。\n"
            "请确保:\n"
            "1. API 服务已启动（python playwright_api.py）\n"
            "2. 服务运行在 127.0.0.1:8000"
        )
    except requests.exceptions.Timeout:
        raise Exception(f"❌ API 请求超时（{timeout}秒）")
    except requests.exceptions.HTTPError as e:
        error_detail = "未知错误"
        try:
            error_detail = response.json().get("detail", str(e))
        except:
            pass
        raise Exception(f"❌ API 请求失败: {error_detail}")
    except Exception as e:
        raise Exception(f"❌ API 调用异常: {str(e)}")

# ============================================================================
# 原有代码
# ============================================================================

# 创建全局分类器实例（单例模式）
_classifier_instance = None

# 全局变量：存储爬取的数据（临时方案）
_scraped_data = None

# 全局变量：存储 agent 实例（用于工具访问 agent 状态）
_agent_instance = None

# 全局变量：进度回调函数（用于 WebSocket 模式的进度报告）
_progress_callback = None

def get_classifier():
    """获取分类器单例实例"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = ProductCategoryClassifierV3(verbose=False)
    return _classifier_instance


def set_agent_instance(agent):
    """设置全局 agent 实例"""
    global _agent_instance
    _agent_instance = agent


def get_agent_instance():
    """获取全局 agent 实例"""
    return _agent_instance


def set_progress_callback(callback):
    """设置进度回调函数"""
    global _progress_callback
    _progress_callback = callback


def get_progress_callback():
    """获取进度回调函数"""
    return _progress_callback

def match_product_category(product_name: str) -> Optional[Dict]:
    """
    适配器函数：将新分类器包装成兼容旧接口的形式

    Args:
        product_name: 商品名称

    Returns:
        兼容旧格式的分类结果字典，或 None
    """
    try:
        classifier = get_classifier()
        result = classifier.classify(text=product_name)

        # 检查分类是否成功
        if result.get('status') != 'success':
            return None

        # 转换为旧格式
        # 从 url_suffix 中提取 category_id
        url_suffix = result.get('url_suffix', '')
        category_id = ''
        if url_suffix:
            match = re.search(r'=(\d+)', url_suffix)
            if match:
                category_id = match.group(1)

        return {
            'level': result.get('category_level', '').lower(),  # L3 -> l3
            'category_name': result.get('selected_category', ''),
            'category_id': category_id,
            'url_suffix': url_suffix,
            'main_category': result.get('main_category', ''),
            'reasoning': result.get('reasoning', '')
        }

    except Exception as e:
        print(f"分类器错误: {str(e)}")
        return None


# ==================== 输入模型定义 ====================

class BuildURLInput(BaseModel):
    """构建 URL 的输入参数"""
    country_name: str = Field(default="全部", description="国家或地区名称")
    promotion_channel: str = Field(default="all", description="推广渠道: all/video/live")
    affiliate_check: bool = Field(default=False, description="是否只显示带货达人")
    account_type: str = Field(default="all", description="账号类型: all/personal/business")
    cap_status: str = Field(default="all", description="联盟上限状态: all/not_full/full")
    auth_type: str = Field(default="all", description="认证类型: all/verified/not_verified")
    followers_min: Optional[int] = Field(default=None, description="最小粉丝数")
    followers_max: Optional[int] = Field(default=None, description="最大粉丝数")
    followers_gender: str = Field(default="all", description="粉丝性别: all/male/female")
    followers_age: str = Field(default="all", description="粉丝年龄段")
    new_followers_min: Optional[int] = Field(default=None, description="最小新增粉丝")
    new_followers_max: Optional[int] = Field(default=None, description="最大新增粉丝")


class CategoryInput(BaseModel):
    """商品分类匹配的输入参数"""
    product_name: str = Field(description="商品名称")


class RecordUserNeedsInput(BaseModel):
    """记录用户需求的输入参数"""
    product_name: str = Field(description="用户要推广的商品名称")
    target_count: int = Field(description="用户需要的达人数量")


class SortSuffixInput(BaseModel):
    """排序后缀的输入参数"""
    sort_param: str = Field(description="排序参数中文名,如'粉丝数'、'互动率'等")


class MaxPageInput(BaseModel):
    """获取最大页数的输入参数"""
    url: str = Field(description="搜索页面的完整 URL")


class ScrapeInput(BaseModel):
    """爬取数据的输入参数"""
    urls: List[str] = Field(description="URL 列表(可以是多个排序维度的 URL)")
    max_pages: int = Field(default=10, description="每个 URL 的最大爬取页数")
    product_name: str = Field(description="商品名称,用于 Excel 文件命名")


# ==================== 工具类定义 ====================

class BuildURLTool(BaseTool):
    """构建完整搜索 URL 的工具"""
    name: str = "build_search_url"
    description: str = """
    构建 TikTok 达人搜索的完整 URL。
    输入参数包括国家、推广渠道、粉丝数范围等筛选条件。
    返回完整的搜索 URL 字符串(不包含商品分类后缀)。

    参数说明:
    - country_name: 国家名称,如"美国"、"全部"
    - promotion_channel: "all"(全部)/"video"(短视频)/"live"(直播)
    - affiliate_check: True=只显示带货达人, False=不限制
    - followers_min/max: 粉丝数范围,如 100000, 500000
    """
    args_schema: type[BaseModel] = BuildURLInput

    def _run(
        self,
        country_name: str = "全部",
        promotion_channel: str = "all",
        affiliate_check: bool = False,
        account_type: str = "all",
        cap_status: str = "all",
        auth_type: str = "all",
        followers_min: Optional[int] = None,
        followers_max: Optional[int] = None,
        followers_gender: str = "all",
        followers_age: str = "all",
        new_followers_min: Optional[int] = None,
        new_followers_max: Optional[int] = None
    ) -> str:
        """执行 URL 构建"""
        try:
            # 存储参数到 agent 的 current_params
            agent = get_agent_instance()
            if agent:
                agent.current_params['country_name'] = country_name
                agent.current_params['promotion_channel'] = promotion_channel
                agent.current_params['affiliate_check'] = affiliate_check
                agent.current_params['account_type'] = account_type
                agent.current_params['cap_status'] = cap_status
                agent.current_params['auth_type'] = auth_type
                agent.current_params['followers_min'] = followers_min
                agent.current_params['followers_max'] = followers_max
                agent.current_params['followers_gender'] = followers_gender
                agent.current_params['followers_age'] = followers_age
                agent.current_params['new_followers_min'] = new_followers_min
                agent.current_params['new_followers_max'] = new_followers_max

            # 处理粉丝数范围
            followers = []
            if followers_min is not None and followers_max is not None:
                followers = [followers_min, followers_max]

            # 处理新增粉丝范围
            new_followers = []
            if new_followers_min is not None and new_followers_max is not None:
                new_followers = [new_followers_min, new_followers_max]

            # 调用原函数
            url = build_complete_url(
                country_name=country_name,
                category_name=None,  # 分类由另一个工具处理
                promotion_channel=promotion_channel,
                affiliate_check=affiliate_check,
                account_type=account_type,
                cap_status=cap_status,
                auth_type=auth_type,
                followers=followers,
                followers_gender=followers_gender,
                followers_age=followers_age,
                new_followers=new_followers
            )

            return url

        except Exception as e:
            return f"❌ 构建 URL 失败: {str(e)}"


class RecordUserNeedsTool(BaseTool):
    """记录用户的基本需求（商品名称和目标达人数量）"""
    name: str = "record_user_needs"
    description: str = """
    记录用户的基本需求信息。

    当你从用户输入中提取到商品名称和目标达人数量时，必须调用此工具进行记录。

    参数：
    - product_name: 用户要推广的商品名称（如"口红"、"运动鞋"、"女士香水"）
    - target_count: 用户需要的达人数量（如 2、10、50）

    此工具会将信息存储到 agent 实例中，供后续步骤使用。
    """
    args_schema: type[BaseModel] = RecordUserNeedsInput

    def _run(self, product_name: str, target_count: int) -> str:
        """执行需求记录"""
        try:
            agent = get_agent_instance()
            if not agent:
                return "❌ 无法获取 agent 实例"

            # 存储到 agent 实例
            agent.current_product = product_name
            agent.target_influencer_count = target_count

            return f"✅ 已记录您的需求：\n📦 商品: {product_name}\n🎯 目标达人数: {target_count} 个"

        except Exception as e:
            return f"❌ 记录需求时出错: {str(e)}"


class CategoryMatchTool(BaseTool):
    """商品分类智能匹配工具"""
    name: str = "match_product_category"
    description: str = """
    根据商品名称智能匹配商品分类,返回分类的 URL 后缀。
    使用 LLM 进行语义推理,自动匹配到最合适的三级/二级/一级分类。

    输入: 商品名称(如"口红"、"运动鞋")
    输出: 包含分类信息和 URL 后缀的 JSON 字符串

    如果找不到合适的分类,返回错误信息。
    """
    args_schema: type[BaseModel] = CategoryInput

    def _run(self, product_name: str) -> str:
        """执行分类匹配"""
        try:
            result = match_product_category(product_name)

            if result is None:
                return f"❌ 很抱歉,无法为商品 '{product_name}' 找到合适的分类。请检查商品名称或联系管理员。"

            # 存储商品名称和分类信息到 agent
            agent = get_agent_instance()
            if agent:
                agent.current_product = product_name
                agent.current_params['product_name'] = product_name
                agent.current_params['category_info'] = result

            # 返回用户友好的结果（隐藏技术细节）
            reasoning = result.get('reasoning', '无')
            return f"""✅ 商品分类匹配成功！

📦 商品: {product_name}
📂 分类: {result.get('category_name', '未知')} ({result.get('main_category', '未知')})

💡 匹配说明: {reasoning}

现在可以继续设置其他筛选条件了。"""

        except Exception as e:
            return f"❌ 匹配分类时出错: {str(e)}"


class GetMaxPageTool(BaseTool):
    """获取最大页数的工具"""
    name: str = "get_max_page_number"
    description: str = """
    获取搜索结果的最大页数。
    需要提供完整的搜索 URL（包括所有筛选条件）。

    参数:
    - url: 完整的搜索 URL

    工作流程:
    1. 访问指定的 URL
    2. 自动滚动到页面底部
    3. 等待网页加载完成
    4. 读取分页元素获取最大页数

    返回整数表示最大页数。
    每页通常有 10 个达人,所以总达人数约为 max_page * 10。
    """
    args_schema: type[BaseModel] = MaxPageInput

    def _run(self, url: str) -> str:
        """执行获取最大页数（通过 API）"""
        try:
            # 调用 API 导航到 URL
            print(f"🌐 正在访问: {url}")
            nav_result = call_api("/navigate", method="POST", data={"url": url, "wait_for_load": True})

            if not nav_result.get("success"):
                return "❌ 无法访问搜索页面。可能原因:\n1. URL 格式不正确\n2. 网络连接问题\n3. 页面加载超时\n请检查 URL 是否完整(包含分类后缀)"

            # 调用 API 获取最大页数
            print("📊 正在获取最大页数...")
            result = call_api("/max_page", method="GET")

            if not result.get("success"):
                return "❌ 获取最大页数失败"

            max_page = result.get("max_page", 0)
            estimated_count = result.get("estimated_count", 0)

            if max_page <= 1:
                return f"⚠️ 当前筛选条件下只找到 1 页数据(约10个达人)。\n建议:\n1. 检查 URL 是否包含正确的分类后缀\n2. 尝试放宽筛选条件"

            return f"✅ 最大页数: {max_page}, 预计约有 {estimated_count} 个达人"

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"详细错误信息:\n{error_details}")
            return f"❌ 获取最大页数失败: {str(e)}\n请检查:\n1. Playwright API 服务是否已启动\n2. Chrome 浏览器是否正在运行\n3. URL 是否正确"


class GetSortSuffixTool(BaseTool):
    """获取排序 URL 后缀的工具"""
    name: str = "get_sort_suffix"
    description: str = """
    根据排序参数获取 URL 后缀。

    支持的排序参数(中文):
    - "近28天涨粉数"
    - "近28天视频平均播放量"
    - "近28天总销量"
    - "粉丝数"
    - "互动率"
    - "赞粉比"

    返回对应的 URL 后缀字符串,可以追加到搜索 URL 后面。
    """
    args_schema: type[BaseModel] = SortSuffixInput

    def _run(self, sort_param: str) -> str:
        """执行获取排序后缀"""
        try:
            suffix = get_sort_suffix(sort_param)
            return f"✅ 排序后缀: {suffix}"
        except Exception as e:
            return f"❌ 获取排序后缀失败: {str(e)},请检查排序参数是否正确"


class ScrapeInfluencersTool(BaseTool):
    """搜索并保存达人候选列表的工具"""
    name: str = "scrape_and_export_json"
    description: str = """
    根据筛选条件搜索 TikTok 达人候选并保存列表。
    支持多个排序维度的 URL,会自动合并去重。

    参数:
    - urls: URL 列表(可以是多个排序维度的完整 URL)
    - max_pages: 每个 URL 最多爬取的页数
    - product_name: 商品名称(用于数据标识)

    返回达人候选数量统计信息。
    """
    args_schema: type[BaseModel] = ScrapeInput

    def _run(self, urls: List[str], max_pages: int, product_name: str) -> str:
        """执行数据爬取和导出（通过 API）"""
        try:
            print(f"📊 开始搜索达人候选...")

            # 调用 API 爬取数据并导出 JSON
            result = call_api(
                "/scrape",
                method="POST",
                data={
                    "urls": urls,
                    "max_pages": max_pages,
                    "product_name": product_name
                },
                timeout=len(urls) * max_pages * 30  # 每个 URL 每页约 30 秒
            )

            if not result.get("success"):
                return "❌ 未能获取到达人数据，可能是筛选条件太严格或网络异常"

            # 获取结果信息
            total_rows = result.get("total_rows", 0)
            filepath = result.get("filepath", "")

            if total_rows == 0:
                return "❌ 未能获取到达人数据，可能是筛选条件太严格或网络异常"

            print(f"✅ 搜索完成！")

            # 返回包含文件路径的信息（用于 agent 传递给下一个工具）
            return f"""✅ 成功获取 {total_rows} 个达人候选
📁 数据已保存到: {filepath}

请立即调用 process_influencer_detail 工具获取详细数据"""

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"详细错误信息:\n{error_details}")
            return f"❌ 搜索达人失败: {str(e)}"


class AnalyzeQuantityInput(BaseModel):
    """分析数量缺口的输入参数"""
    max_pages: int = Field(description="最大页数")
    user_needs: int = Field(description="用户需要的达人数量")


class AnalyzeQuantityTool(BaseTool):
    """分析达人数量是否足够的工具"""
    name: str = "analyze_quantity_gap"
    description: str = """
    分析当前找到的达人数量是否满足用户需求。

    判断标准:
    - 可用数量 = 最大页数 × 5（保守估计，每页约5个有效达人）
    - 充足：可用数 ≥ 用户需求
    - 可接受：可用数 ≥ 用户需求 × 50%
    - 严重不足：可用数 < 用户需求 × 50%

    参数:
    - max_pages: 最大页数
    - user_needs: 用户需要的达人数量

    返回：状态判断和给用户的建议信息
    """
    args_schema: type[BaseModel] = AnalyzeQuantityInput

    def _run(self, max_pages: int, user_needs: int) -> str:
        """执行数量分析"""
        try:
            from adjustment_helper import analyze_quantity_gap
            result = analyze_quantity_gap(max_pages, user_needs)
            return result['message']
        except Exception as e:
            return f"❌ 分析数量时出错: {str(e)}"


class AdjustmentSuggestionInput(BaseModel):
    """调整建议的输入参数"""
    current_params: Dict = Field(description="当前筛选参数JSON字典")
    target_count: int = Field(description="用户需要的达人数量")
    current_count: int = Field(description="当前可用达人数量")


class ProcessInfluencerListInput(BaseModel):
    """处理达人列表的输入参数"""
    json_file_path: str = Field(description="导出的 JSON 文件路径")
    cache_days: int = Field(3, ge=1, le=30, description="缓存有效天数（1-30天，默认3天）")


class GenerateReportInput(BaseModel):
    """生成推荐报告的输入参数"""
    json_file_path: str = Field(description="达人数据 JSON 文件路径")
    product_name: str = Field(description="商品名称")
    user_requirements: str = Field(description="用户需求描述")
    top_n: int = Field(10, ge=1, le=50, description="推荐达人数量（默认10）")


class ReviewParametersInput(BaseModel):
    """审查参数的输入参数"""
    # 不需要任何参数，工具会自动从 agent 实例中读取
    pass


class UpdateParametersInput(BaseModel):
    """更新参数的输入参数"""
    param_name: str = Field(description="要更新的参数名称")
    param_value: Any = Field(description="参数的新值")


class SuggestAdjustmentsTool(BaseTool):
    """生成筛选条件调整建议的工具"""
    name: str = "suggest_parameter_adjustments"
    description: str = """
    当达人数量不足时，自动生成结构化的调整建议。

    会按优先级返回 3-5 个调整方案：
    1. 放宽粉丝数范围（效果最好）
    2. 移除新增粉丝数限制
    3. 移除带货达人限制
    4. 移除认证类型限制
    5. 移除账号类型限制

    每个方案包含：
    - 具体改动内容
    - 当前值 vs 新值对比
    - 预期增加的达人数量
    - 调整理由

    参数:
    - current_params: 当前的筛选参数（JSON格式字典）
    - target_count: 用户需要的达人数量
    - current_count: 当前可用的达人数量

    注意：绝对不会修改国家地区和商品分类
    """
    args_schema: type[BaseModel] = AdjustmentSuggestionInput

    def _run(self, current_params: Dict, target_count: int, current_count: int) -> str:
        """执行调整建议生成"""
        try:
            from adjustment_helper import suggest_adjustments

            suggestions = suggest_adjustments(current_params, target_count, current_count)

            if not suggestions:
                return "当前筛选条件已经比较宽松，没有更多调整建议。"

            # 格式化输出
            output = f"📊 为您生成 {len(suggestions)} 个调整方案：\n\n"

            for i, sugg in enumerate(suggestions, 1):
                output += f"**方案 {i}: {sugg['name']}**\n"
                output += f"  • 当前: {sugg['current']}\n"
                output += f"  • 调整后: {sugg['new']}\n"
                output += f"  • 预期效果: {sugg['expected_increase']}\n"
                output += f"  • 理由: {sugg['reason']}\n\n"

            output += "请告诉我您想选择哪个方案，或者让我自动选择最优方案。"

            return output

        except Exception as e:
            return f"❌ 生成调整建议时出错: {str(e)}"


class ReviewParametersTool(BaseTool):
    """审查并展示当前收集到的所有筛选参数"""
    name: str = "review_parameters"
    description: str = """
    展示当前收集到的所有筛选参数，供用户确认。

    这个工具会自动从 agent 实例中读取并格式化显示：
    - 商品名称和分类信息
    - 目标国家/地区
    - 目标达人数量
    - 所有筛选条件（粉丝范围、推广渠道、认证类型等）

    **无需传入任何参数**，工具会自动从当前对话上下文中获取所有信息。

    返回格式化的参数摘要，并询问用户是否满意。
    """
    args_schema: type[BaseModel] = ReviewParametersInput

    def _run(self) -> str:
        """执行参数审查"""
        try:
            # 从 agent 实例中获取信息
            agent = get_agent_instance()
            if not agent:
                return "❌ 无法获取 agent 实例"

            current_params = agent.current_params
            product_name = agent.current_product or "未设置"
            target_count = agent.target_influencer_count or "未设置"
            category_info = current_params.get('category_info')

            # 构建参数摘要
            output = "📋 **当前筛选参数摘要**\n\n"

            # 1. 商品信息
            output += f"🎯 **商品信息**\n"
            output += f"   • 商品名称: {product_name}\n"
            if category_info:
                output += f"   • 商品分类: {category_info.get('main_category', '未知')} > {category_info.get('category_name', '未知')}\n"
            output += f"   • 目标数量: {target_count} 个达人\n\n"

            # 2. 国家/地区
            country = current_params.get('country_name', '全部')
            output += f"🌍 **目标地区**: {country}\n\n"

            # 3. 筛选条件
            output += f"🔍 **筛选条件**\n"

            # 粉丝范围
            followers_min = current_params.get('followers_min')
            followers_max = current_params.get('followers_max')
            if followers_min or followers_max:
                if followers_min and followers_max:
                    output += f"   • 粉丝数: {self._format_number(followers_min)} - {self._format_number(followers_max)}\n"
                elif followers_min:
                    output += f"   • 粉丝数: 至少 {self._format_number(followers_min)}\n"
                elif followers_max:
                    output += f"   • 粉丝数: 最多 {self._format_number(followers_max)}\n"
            else:
                output += f"   • 粉丝数: 不限制\n"

            # 推广渠道
            channel = current_params.get('promotion_channel', 'all')
            channel_map = {'all': '不限制', 'video': '短视频带货', 'live': '直播带货'}
            output += f"   • 推广渠道: {channel_map.get(channel, channel)}\n"

            # 带货达人
            affiliate = current_params.get('affiliate_check', False)
            output += f"   • 带货达人: {'仅带货达人' if affiliate else '不限制'}\n"

            # 认证类型
            auth_type = current_params.get('auth_type', 'all')
            auth_map = {'all': '不限制', 'verified': '仅认证达人', 'not_verified': '仅未认证达人'}
            output += f"   • 认证类型: {auth_map.get(auth_type, auth_type)}\n"

            # 账号类型
            account_type = current_params.get('account_type', 'all')
            account_map = {'all': '不限制', 'personal': '个人账号', 'business': '企业账号'}
            output += f"   • 账号类型: {account_map.get(account_type, account_type)}\n"

            # 粉丝性别
            gender = current_params.get('followers_gender', 'all')
            gender_map = {'all': '不限制', 'male': '男粉为主', 'female': '女粉为主'}
            output += f"   • 粉丝性别: {gender_map.get(gender, gender)}\n"

            # 粉丝年龄
            age = current_params.get('followers_age', 'all')
            age_map = {'all': '不限制', '18-24': '18-24岁', '25-34': '25-34岁', '35-44': '35-44岁', '45+': '45岁以上'}
            output += f"   • 粉丝年龄: {age_map.get(age, age)}\n"

            # 新增粉丝
            new_followers_min = current_params.get('new_followers_min')
            new_followers_max = current_params.get('new_followers_max')
            if new_followers_min or new_followers_max:
                if new_followers_min and new_followers_max:
                    output += f"   • 近28天涨粉: {self._format_number(new_followers_min)} - {self._format_number(new_followers_max)}\n"
                elif new_followers_min:
                    output += f"   • 近28天涨粉: 至少 {self._format_number(new_followers_min)}\n"
                elif new_followers_max:
                    output += f"   • 近28天涨粉: 最多 {self._format_number(new_followers_max)}\n"

            output += "\n"
            output += "---\n\n"
            output += "⚠️ **请您确认以上参数是否满意？**\n\n"
            output += "• 如果满意，请回复：**好的** / **确认** / **可以** / **开始**\n"
            output += "• 如果需要调整，请告诉我要修改哪些参数\n\n"
            output += "🛑 **重要：我会等待您的明确回复后再继续。请不要自动进入下一步。**"

            return output

        except Exception as e:
            return f"❌ 审查参数时出错: {str(e)}"

    def _format_number(self, num: int) -> str:
        """格式化数字显示"""
        if num >= 10000:
            return f"{num // 10000}万"
        else:
            return str(num)


class UpdateParametersTool(BaseTool):
    """更新特定的筛选参数"""
    name: str = "update_parameter"
    description: str = """
    更新特定的筛选参数。

    用于在参数确认循环中修改用户不满意的参数。

    参数：
    - param_name: 要更新的参数名称（如 'followers_min', 'promotion_channel'）
    - param_value: 参数的新值

    注意：
    - 国家（country_name）和商品分类一旦确定不可修改
    - 参数名称必须是有效的筛选参数

    返回更新结果。
    """
    args_schema: type[BaseModel] = UpdateParametersInput

    def _run(self, param_name: str, param_value: Any) -> str:
        """执行参数更新"""
        try:
            # 检查不可修改的参数
            immutable_params = ['country_name', 'category_id', 'category_name']
            if param_name in immutable_params:
                return f"❌ 参数 '{param_name}' 不可修改。国家和商品分类一旦确定就不能更改。"

            # 有效参数列表
            valid_params = [
                'followers_min', 'followers_max', 'promotion_channel',
                'affiliate_check', 'account_type', 'auth_type',
                'followers_gender', 'followers_age',
                'new_followers_min', 'new_followers_max', 'cap_status'
            ]

            if param_name not in valid_params:
                return f"❌ 无效的参数名称: {param_name}\n可用参数: {', '.join(valid_params)}"

            # 获取 agent 实例并更新参数
            agent = get_agent_instance()
            if not agent:
                return "❌ 无法获取 agent 实例"

            # 实际更新参数到 agent.current_params
            agent.current_params[param_name] = param_value

            # 返回成功信息
            return f"✅ 参数 '{param_name}' 已更新为: {param_value}"

        except Exception as e:
            return f"❌ 更新参数时出错: {str(e)}"


class ProcessInfluencerListTool(BaseTool):
    """批量获取达人详细数据的工具"""
    name: str = "process_influencer_detail"
    description: str = """
    批量获取达人候选的详细信息，包含粉丝画像、带货数据等。

    功能：
    - 自动检查已有数据缓存（默认 3 天有效）
    - 批量获取缺失或过期的达人详情
    - 实时显示处理进度和预估完成时间

    参数：
    - json_file_path: 之前保存的达人候选列表路径
    - cache_days: 数据有效天数（可选，默认 3 天）

    注意：
    - 这是一个耗时操作，大量达人可能需要数分钟到数小时
    - 单个达人获取失败不影响整体流程
    - 自动显示实时进度条和统计信息
    """
    args_schema: type[BaseModel] = ProcessInfluencerListInput

    def _run(self, json_file_path: str, cache_days: int = 3) -> str:
        """执行批量处理（流式接收，实时显示进度）"""
        try:
            # 获取进度回调函数（用于 WebSocket 模式）
            progress_callback = get_progress_callback()

            print(f"📊 开始批量获取达人详细数据...")

            # 验证文件存在
            if not os.path.exists(json_file_path):
                return f"❌ 文件不存在"

            # 使用流式 API
            url = f"{API_BASE_URL}/process_influencer_list_stream"
            params = {
                "json_file_path": json_file_path,
                "cache_days": cache_days
            }

            print(f"⏳ 正在处理，请稍候...\n")

            start_time = time.time()
            last_percent = -1
            stats = None

            # 流式接收进度（使用 decode_unicode=True 立即解码）
            with requests.get(url, params=params, stream=True, timeout=3600) as response:
                response.raise_for_status()

                # 使用 iter_lines(decode_unicode=True) 立即获取行
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue

                    # 解析 SSE 事件
                    if not line.startswith('data: '):
                        continue

                    event_data = line[6:]  # 移除 "data: " 前缀
                    event = json.loads(event_data)

                    if event["type"] == "init":
                        total = event["total"]
                        msg = f"⏳ 共需处理 {total} 个达人，请耐心等待"
                        print(f"{msg}\n")

                        # 发送到前端
                        if progress_callback:
                            progress_callback({
                                "type": "crawler_init",
                                "total": total,
                                "message": msg
                            })

                    elif event["type"] == "progress":
                        current = event["current"]
                        total = event["total"]
                        success = event["success"]
                        cached = event["cached"]
                        failed = event["failed"]
                        elapsed = event["elapsed_seconds"]

                        # 计算进度
                        percent = int(current / total * 100)

                        # 每 1% 或每个达人都显示进度
                        should_display = (
                            percent > last_percent or  # 每 1% 变化
                            current == total  # 最后一个
                        )

                        if should_display:
                            last_percent = percent

                            # 绘制进度条（命令行模式）
                            bar_len = 30
                            filled = int(bar_len * percent / 100)
                            bar = '█' * filled + '░' * (bar_len - filled)

                            # 计算预估时间
                            if current > 0 and elapsed > 0:
                                avg_time = elapsed / current
                                remaining = int((total - current) * avg_time)
                                elapsed_str = self._format_time(elapsed)
                                remaining_str = self._format_time(remaining)
                                time_info = f"⏱️ 已用时: {elapsed_str} | 预计剩余: {remaining_str}"
                            else:
                                time_info = f"⏱️ 处理中..."

                            print(f"处理进度: {bar} {percent}% ({current}/{total})")
                            print(time_info)
                            print(f"✓ 成功: {success}  |  ⚡ 缓存: {cached}  |  ✗ 失败: {failed}\n")

                            # 发送到前端（WebSocket 模式）
                            if progress_callback:
                                progress_callback({
                                    "type": "crawler_progress",
                                    "current": current,
                                    "total": total,
                                    "percent": percent,
                                    "success": success,
                                    "cached": cached,
                                    "failed": failed,
                                    "elapsed": elapsed,
                                    "remaining": int((total - current) * avg_time) if current > 0 and elapsed > 0 else 0
                                })

                    elif event["type"] == "complete":
                        stats = event["stats"]
                        total_elapsed = time.time() - start_time
                        print(f"处理进度: {'█' * 30} 100% ({stats['total']}/{stats['total']})")
                        print(f"⏱️ 总耗时: {self._format_time(int(total_elapsed))}\n")

                        # 发送完成消息到前端
                        if progress_callback:
                            progress_callback({
                                "type": "crawler_complete",
                                "stats": stats
                            })

                    elif event["type"] == "error":
                        error_msg = f"❌ 处理失败: {event['message']}"
                        if progress_callback:
                            progress_callback({
                                "type": "crawler_error",
                                "message": event['message']
                            })
                        return error_msg

            # 显示最终统计
            if stats:
                output = f"✅ 完成！\n"
                output += f"   共处理 {stats['total']} 个达人\n"
                output += f"   成功获取 {stats['success']} 个\n"
                if stats['cached'] > 0:
                    output += f"   使用缓存 {stats['cached']} 个\n"
                if stats['failed'] > 0:
                    output += f"   失败 {stats['failed']} 个\n"
                output += f"\n📁 详细数据已保存，可供后续分析"
                return output
            else:
                return "✅ 处理完成"

        except requests.exceptions.Timeout:
            return "❌ 处理超时，请稍后重试"
        except requests.exceptions.ConnectionError:
            return "❌ 无法连接到服务，请确认 API 服务已启动"
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"详细错误信息:\n{error_details}")
            return f"❌ 批量处理失败: {str(e)}"

    def _format_time(self, seconds: int) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds} 秒"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes} 分 {secs} 秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours} 小时 {minutes} 分"


class GenerateReportTool(BaseTool):
    """生成达人推荐报告的工具"""
    name: str = "generate_recommendation_report"
    description: str = """
    生成精美的达人推荐 HTML 报告。

    功能：
    - 使用 AI 分析达人数据
    - 根据用户需求智能排序推荐
    - 为每位达人生成推荐理由和亮点
    - 创建美观的网页报告
    - 返回可访问的报告链接

    参数：
    - json_file_path: 达人数据文件路径
    - product_name: 商品名称
    - user_requirements: 用户需求描述
    - top_n: 推荐达人数量（默认10）

    注意：
    - 需要在获取完达人详细数据后调用
    - 报告会保存到 static/reports 目录
    - 返回可在浏览器中打开的 URL
    """
    args_schema: type[BaseModel] = GenerateReportInput

    def _run(self, json_file_path: str, product_name: str, user_requirements: str, top_n: int = 10) -> str:
        """执行报告生成（使用完整的 report_agent）"""
        try:
            from report_agent import TikTokInfluencerReportAgent

            print(f"📝 开始生成达人推荐报告...")

            # 从完整路径提取文件名（report_agent 只需要文件名）
            json_filename = os.path.basename(json_file_path)

            # 构建产品详细信息（合并商品名称和用户需求）
            product_info = f"{product_name}。用户需求：{user_requirements}"

            # 获取进度回调（如果有的话）
            progress_callback = get_progress_callback()

            # 定义报告生成的进度回调包装器
            def report_progress_wrapper(progress_data: dict):
                """将报告生成进度转发到 WebSocket"""
                if progress_callback:
                    try:
                        # 转换为前端可识别的格式
                        progress_callback({
                            "type": "report_generation_progress",
                            "step": progress_data.get('step', 'unknown'),
                            "current": progress_data.get('current', 0),
                            "total": progress_data.get('total', 0),
                            "percent": progress_data.get('percent', 0),
                            "message": progress_data.get('message', '')
                        })
                    except Exception as e:
                        print(f"[Error] 发送报告生成进度失败: {e}")

            # 初始化报告 agent（传入进度回调）
            report_agent = TikTokInfluencerReportAgent(progress_callback=report_progress_wrapper)

            # 生成报告（返回 HTML 文件路径）
            report_path = report_agent.generate_report(
                json_filename=json_filename,
                user_query=user_requirements,
                target_count=top_n,
                product_info=product_info
            )

            if not report_path or not os.path.exists(report_path):
                return f"❌ 报告生成失败：未能生成报告文件"

            # 将报告文件路径转换为 web 可访问的 URL
            # report_path 格式: output/reports/20251105_180530/report.html
            # 需要转换为: /reports/20251105_180530/report.html
            relative_path = report_path.replace("output/", "/")
            full_url = f"http://127.0.0.1:8001{relative_path}"

            # 计算报告中的达人数量
            # 报告包含 3 个 tier，每个 tier 有 top_n 个达人
            total_in_report = top_n * 3

            output = f"""✅ 达人推荐报告生成成功！

📊 **报告详情**
   • 推荐层级: Tier 1 ({top_n}个) + Tier 2 ({top_n}个) + Tier 3 ({top_n}个)
   • 报告总数: {total_in_report} 位达人
   • 数据来源: {json_filename}

🔗 **查看报告**
   点击链接在浏览器中打开：{full_url}

💡 报告包含：
   ✓ 多维度智能评分与排名
   ✓ 详细的达人分析（优势/风险/合作建议）
   ✓ 数据可视化图表
   ✓ 受众画像与内容契合度分析
   ✓ 达人联系方式提取"""

            return output

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"详细错误信息:\n{error_details}")
            return f"❌ 生成报告失败: {str(e)}"


# ==================== 工具列表 ====================

def get_all_tools() -> List[BaseTool]:
    """获取所有工具的列表"""
    # LangSmith 追踪说明：
    # 工具级别的追踪会自动继承 Agent 的配置
    # 每个工具调用都会在 LangSmith 中显示为独立的 span
    # 包含工具名称、输入参数、输出结果、执行时长

    return [
        RecordUserNeedsTool(),            # 记录用户需求（商品+数量）
        BuildURLTool(),
        CategoryMatchTool(),
        ReviewParametersTool(),           # 审查参数
        UpdateParametersTool(),           # 更新参数
        GetMaxPageTool(),
        AnalyzeQuantityTool(),            # 分析数量缺口
        SuggestAdjustmentsTool(),         # 生成调整建议
        GetSortSuffixTool(),
        ScrapeInfluencersTool(),          # 搜索并保存达人候选
        ProcessInfluencerListTool(),      # 批量获取达人详细数据
        GenerateReportTool()              # 生成推荐报告
    ]


if __name__ == "__main__":
    # 测试工具
    print("🧪 测试 LangChain 工具...")

    # 测试 BuildURLTool
    print("\n" + "="*50)
    print("测试 1: 构建 URL")
    tool = BuildURLTool()
    result = tool._run(
        country_name="美国",
        followers_min=100000,
        followers_max=500000,
        promotion_channel="live"
    )
    print(result)

    # 测试 CategoryMatchTool
    print("\n" + "="*50)
    print("测试 2: 匹配分类")
    tool = CategoryMatchTool()
    result = tool._run(product_name="口红")
    print(result)

    # 测试 GetSortSuffixTool
    print("\n" + "="*50)
    print("测试 3: 获取排序后缀")
    tool = GetSortSuffixTool()
    result = tool._run(sort_param="粉丝数")
    print(result)

    print("\n✅ 所有工具测试完成!")
