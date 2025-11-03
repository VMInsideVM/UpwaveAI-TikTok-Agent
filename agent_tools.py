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
from category_matcher import match_product_category


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

            # 返回格式化的结果
            return f"""✅ 分类匹配成功!
- 商品: {product_name}
- 一级分类: {result.get('main_category', '未知')}
- 匹配层级: {result.get('level', '未知')}
- 分类名称: {result.get('category_name', '未知')}
- URL后缀: {result.get('url_suffix', '')}"""

        except Exception as e:
            return f"❌ 匹配分类时出错: {str(e)}"


class GetMaxPageTool(BaseTool):
    """获取最大页数的工具"""
    name: str = "get_max_page_number"
    description: str = """
    获取当前搜索结果的最大页数。
    需要先初始化 Playwright 并访问搜索页面。

    工作流程:
    1. 自动滚动到页面底部
    2. 等待网页加载完成
    3. 读取分页元素获取最大页数

    返回整数表示最大页数。
    每页通常有 10 个达人,所以总达人数约为 max_page * 10。
    """

    def _run(self) -> str:
        """执行获取最大页数"""
        try:
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
