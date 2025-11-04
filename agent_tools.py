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
    """爬取达人数据并导出 JSON 的工具"""
    name: str = "scrape_and_export_json"
    description: str = """
    爬取 TikTok 达人的 data-row-key 并自动导出为 JSON 文件。
    支持多个排序维度的 URL,会自动合并去重并导出为单个 JSON 文件。

    参数:
    - urls: URL 列表(可以是多个排序维度的完整 URL)
    - max_pages: 每个 URL 最多爬取的页数
    - product_name: 商品名称(用于 JSON 文件命名)

    返回 JSON 文件路径和达人数量统计信息。
    """
    args_schema: type[BaseModel] = ScrapeInput

    def _run(self, urls: List[str], max_pages: int, product_name: str) -> str:
        """执行数据爬取和导出（通过 API）"""
        try:
            print(f"📊 开始爬取并导出数据...")
            print(f"   - URL 数量: {len(urls)}")
            print(f"   - 每个 URL 最多: {max_pages} 页")
            print(f"   - 商品名称: {product_name}")

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
                return "❌ 未能爬取到数据,可能是筛选条件太严格或网站响应异常"

            # 获取结果信息
            filepath = result.get("filepath", "")
            total_rows = result.get("total_rows", 0)
            source_count = result.get("source_count", 0)
            scraped_count = result.get("scraped_count", 0)

            if total_rows == 0:
                return "❌ 未能爬取到数据,可能是筛选条件太严格或网站响应异常"

            print(f"✅ 爬取并导出成功!")
            print(f"   - 文件路径: {filepath}")
            print(f"   - data-row-key 总数: {total_rows}")

            return f"""✅ 数据爬取和导出成功!
📁 文件路径: {filepath}
📊 data-row-key 总数: {total_rows}(已去重)
🔗 URL 数量: {source_count}
✓ 成功爬取: {scraped_count}/{source_count} 个 URL

🎉 你可以在 output 文件夹中找到这个 JSON 文件!"""

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"详细错误信息:\n{error_details}")
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


class ProcessInfluencerListInput(BaseModel):
    """处理达人列表的输入参数"""
    json_file_path: str = Field(description="导出的 JSON 文件路径")
    cache_days: int = Field(3, ge=1, le=30, description="缓存有效天数（1-30天，默认3天）")


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


class ProcessInfluencerListTool(BaseTool):
    """批量获取达人详细数据的工具"""
    name: str = "process_influencer_detail"
    description: str = """
    根据导出的 JSON 文件，批量获取达人详细数据并保存到 influencer 目录。

    功能：
    - 读取 JSON 文件中的 data_row_keys（达人 ID 列表）
    - 自动检查 influencer 目录中的缓存（默认 3 天有效）
    - 顺序爬取缺失/过期的达人详情（避免触发反爬）
    - 保存到 influencer/{id}.json，包含完整的 API 响应数据

    参数：
    - json_file_path: JSON 文件路径（如 output/tiktok_达人推荐_女士香水_20251104_165214.json）
    - cache_days: 缓存有效天数（可选，默认 3 天）

    注意：
    - 这是一个耗时操作，处理大量达人时可能需要数分钟到数小时
    - 每个达人需要 3-5 秒爬取，加上 2 秒间隔延迟
    - 单个失败不影响整体流程，会继续处理其他达人
    - 返回详细的统计信息（缓存/获取/失败数量）
    """
    args_schema: type[BaseModel] = ProcessInfluencerListInput

    def _run(self, json_file_path: str, cache_days: int = 3) -> str:
        """执行批量处理（通过 API）"""
        try:
            print(f"📊 开始批量获取达人详细数据...")
            print(f"   - 文件: {json_file_path}")
            print(f"   - 缓存有效期: {cache_days} 天")

            # 验证文件存在
            if not os.path.exists(json_file_path):
                return f"❌ 文件不存在: {json_file_path}"

            # 调用 API 批量处理
            # 注意：这可能是一个非常耗时的操作
            result = call_api(
                "/process_influencer_list",
                method="POST",
                data={
                    "json_file_path": json_file_path,
                    "cache_days": cache_days
                },
                timeout=3600  # 设置 1 小时超时（处理大量达人可能很耗时）
            )

            if not result.get("success"):
                return f"❌ 批量处理失败: {result.get('message', '未知错误')}"

            # 获取统计信息
            total_count = result.get("total_count", 0)
            cached_count = result.get("cached_count", 0)
            fetched_count = result.get("fetched_count", 0)
            failed_count = result.get("failed_count", 0)
            failed_ids = result.get("failed_ids", [])
            elapsed_time = result.get("elapsed_time", "未知")

            print(f"✅ 批量处理完成!")
            print(f"   - 总数: {total_count}")
            print(f"   - 使用缓存: {cached_count}")
            print(f"   - 重新获取: {fetched_count}")
            print(f"   - 失败: {failed_count}")
            print(f"   - 耗时: {elapsed_time}")

            # 格式化返回消息
            output = f"""✅ 达人详细数据批量处理完成！

📊 统计信息：
   • 总达人数: {total_count}
   • 使用缓存: {cached_count}
   • 重新获取: {fetched_count}
   • 失败: {failed_count}
   • 处理耗时: {elapsed_time}

📁 数据保存位置: influencer/ 目录
   格式: influencer/{{达人ID}}.json"""

            if failed_count > 0:
                output += f"\n\n⚠️ 失败的达人 ID（共 {failed_count} 个）："
                # 只显示前 10 个失败 ID
                display_failed = failed_ids[:10]
                for fid in display_failed:
                    output += f"\n   - {fid}"
                if len(failed_ids) > 10:
                    output += f"\n   ... 还有 {len(failed_ids) - 10} 个"

            return output

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"详细错误信息:\n{error_details}")
            return f"❌ 批量处理失败: {str(e)}"


# ==================== 工具列表 ====================

def get_all_tools() -> List[BaseTool]:
    """获取所有工具的列表"""
    return [
        BuildURLTool(),
        CategoryMatchTool(),
        GetMaxPageTool(),
        AnalyzeQuantityTool(),            # 分析数量缺口
        SuggestAdjustmentsTool(),         # 生成调整建议
        GetSortSuffixTool(),
        ScrapeInfluencersTool(),          # 爬取并导出 JSON(只保存 data-row-key)
        ProcessInfluencerListTool()       # 批量获取达人详细数据
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
