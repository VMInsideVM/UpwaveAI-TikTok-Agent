"""
LangChain Tools 封装
将现有的爬虫函数封装为 LangChain 可用的工具
"""

from typing import Optional, List, Dict, Any
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import pandas as pd
from datetime import datetime
import os

# 导入现有函数
from main import (
    build_complete_url,
    get_max_page_number,
    get_sort_suffix,
    get_table_data_as_dataframe,
    initialize_playwright,
    navigate_to_url
)
from agent_category_classifier import ProductCategoryClassifierV3
import re

# 创建全局分类器实例（单例模式）
_classifier_instance = None

def get_classifier():
    """获取分类器单例实例"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = ProductCategoryClassifierV3(verbose=False)
    return _classifier_instance

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
    affiliate_check: bool = Field(default=False, description="是否只显示联盟达人")
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


class SortSuffixInput(BaseModel):
    """排序后缀的输入参数"""
    sort_param: str = Field(description="排序参数中文名,如'粉丝数'、'互动率'等")


class MaxPageInput(BaseModel):
    """获取最大页数的输入参数"""
    url: str = Field(description="搜索页面的完整 URL")


class ScrapeInput(BaseModel):
    """爬取数据的输入参数"""
    base_url: str = Field(description="基础搜索 URL")
    max_pages: int = Field(default=10, description="最多爬取的页数")


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
    - affiliate_check: True=只显示联盟达人, False=不限制
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

            # 返回格式化的结果，包含推理过程
            reasoning = result.get('reasoning', '无')
            return f"""✅ 分类匹配成功!
- 商品: {product_name}
- 一级分类: {result.get('main_category', '未知')}
- 匹配层级: {result.get('level', '未知')}
- 分类名称: {result.get('category_name', '未知')}
- URL后缀: {result.get('url_suffix', '')}

💡 推理过程: {reasoning}"""

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
        """执行获取最大页数"""
        try:
            # 初始化 Playwright(如果还没初始化)
            try:
                initialize_playwright()
            except:
                pass  # 可能已经初始化过了

            # 访问 URL
            print(f"🌐 正在访问: {url}")
            if not navigate_to_url(url):
                return "❌ 无法访问搜索页面,请检查 URL 是否正确"

            # 获取最大页数
            max_page = get_max_page_number()
            estimated_count = max_page * 10
            return f"✅ 最大页数: {max_page}, 预计约有 {estimated_count} 个达人"
        except Exception as e:
            return f"❌ 获取最大页数失败: {str(e)}"


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
    """爬取达人数据的工具"""
    name: str = "scrape_influencer_data"
    description: str = """
    爬取 TikTok 达人数据并返回 DataFrame。
    需要提供完整的搜索 URL(包括所有筛选条件和排序参数)。

    参数:
    - base_url: 完整的搜索 URL
    - max_pages: 最多爬取的页数(默认 10)

    返回爬取到的达人数量和基本统计信息。
    数据会暂存在内存中,供后续导出使用。
    """
    args_schema: type[BaseModel] = ScrapeInput

    def _run(self, base_url: str, max_pages: int = 10) -> str:
        """执行数据爬取"""
        try:
            # 初始化 Playwright(如果还没初始化)
            try:
                initialize_playwright()
            except:
                pass  # 可能已经初始化过了

            # 访问 URL
            print(f"🌐 正在访问: {base_url}")
            if not navigate_to_url(base_url):
                return "❌ 无法访问搜索页面,请检查 URL 是否正确"

            # 爬取数据
            df = get_table_data_as_dataframe(max_pages=max_pages)

            if df is None or df.empty:
                return "❌ 未能爬取到数据,可能是筛选条件太严格或网站响应异常"

            # 返回统计信息
            count = len(df)
            return f"""✅ 数据爬取成功!
- 爬取页数: {max_pages}
- 获得达人数: {count}
- 数据已暂存,可以导出为 Excel"""

        except Exception as e:
            return f"❌ 爬取数据失败: {str(e)}"


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


class SuggestAdjustmentsTool(BaseTool):
    """生成筛选条件调整建议的工具"""
    name: str = "suggest_parameter_adjustments"
    description: str = """
    当达人数量不足时，自动生成结构化的调整建议。

    会按优先级返回 3-5 个调整方案：
    1. 放宽粉丝数范围（效果最好）
    2. 移除新增粉丝数限制
    3. 移除联盟达人限制
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


class ExportExcelTool(BaseTool):
    """导出 Excel 的工具"""
    name: str = "export_to_excel"
    description: str = """
    将爬取的达人数据导出为 Excel 文件。
    文件会保存到 output/ 目录下。

    文件名格式: tiktok_达人推荐_{商品名}_{日期时间}.xlsx

    返回保存的文件路径。
    """

    class ExportInput(BaseModel):
        product_name: str = Field(description="商品名称,用于文件命名")
        dataframe_list: List[Any] = Field(description="DataFrame 列表(如果有多个排序维度)")

    args_schema: type[BaseModel] = ExportInput

    def _run(self, product_name: str, dataframe_list: List[pd.DataFrame]) -> str:
        """执行 Excel 导出"""
        try:
            # 创建 output 目录
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)

            # 合并所有 DataFrame 并去重
            if len(dataframe_list) == 1:
                final_df = dataframe_list[0]
            else:
                final_df = pd.concat(dataframe_list, ignore_index=True)
                # 假设第一列是达人 ID 或唯一标识
                final_df = final_df.drop_duplicates(subset=final_df.columns[0], keep='first')

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tiktok_达人推荐_{product_name}_{timestamp}.xlsx"
            filepath = os.path.join(output_dir, filename)

            # 导出 Excel
            final_df.to_excel(filepath, index=False, engine='openpyxl')

            return f"✅ Excel 导出成功!\n文件路径: {filepath}\n共 {len(final_df)} 个达人"

        except Exception as e:
            return f"❌ 导出 Excel 失败: {str(e)}"


# ==================== 工具列表 ====================

def get_all_tools() -> List[BaseTool]:
    """获取所有工具的列表"""
    return [
        BuildURLTool(),
        CategoryMatchTool(),
        GetMaxPageTool(),
        AnalyzeQuantityTool(),         # 新增：分析数量缺口
        SuggestAdjustmentsTool(),      # 新增：生成调整建议
        GetSortSuffixTool(),
        ScrapeInfluencersTool(),
        ExportExcelTool()
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
