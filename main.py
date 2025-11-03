from playwright.sync_api import sync_playwright
import time
import json
import re
import pandas as pd
from datetime import datetime
import os


# 全局变量
playwright_instance = None
browser = None
context = None
page = None
main_url = 'https://www.fastmoss.com/zh/influencer/search?'



def initialize_playwright():
    """初始化Playwright连接"""
    global playwright_instance, browser, context, page
    playwright_instance = sync_playwright().start()
    browser = playwright_instance.chromium.connect_over_cdp("http://localhost:9224")
    context = browser.contexts[0]
    page = context.pages[0]

def cleanup_playwright():
    """清理Playwright资源"""
    global playwright_instance, browser, context, page
    if browser:
        browser.close()
    if playwright_instance:
        playwright_instance.stop()
    playwright_instance = None
    browser = None
    context = None
    page = None

# 国家/地区选项映射表
COUNTRY_OPTIONS = {
    "全部": "",
    "美国": "US",
    "印度尼西亚": "ID", 
    "英国": "GB",
    "越南": "VN",
    "泰国": "TH",
    "马来西亚": "MY",
    "菲律宾": "PH",
    "西班牙": "ES",
    "墨西哥": "MX",
    "德国": "DE",
    "法国": "FR",
    "意大利": "IT",
    "巴西": "BR",
    "日本": "JP"
}

def choose_country(country_name):
    """
    根据用户输入的国家/地区名称返回对应的URL后缀
    
    Args:
        country_name (str): 国家/地区名称（中文或英文）
    
    Returns:
        str: 对应的URL后缀参数，格式为 "region=XX" 或空字符串（全部）
    
    Examples:
        >>> choose_country("美国")
        "region=US"
        >>> choose_country("US")
        "region=US"
        >>> choose_country("全部")
        ""
        >>> choose_country("不存在的国家")
        None
    """
    if not country_name:
        return None
    
    # 直接匹配中文名称
    if country_name in COUNTRY_OPTIONS:
        country_code = COUNTRY_OPTIONS[country_name]
        return f"region={country_code}" if country_code else ""
    

    return None

creator_category_options = {
  "购物与零售": 2,
  "家居、家具和电器": 3,
  "美妆": 4,
  "食品和饮料": 5,
  "服饰与配饰": 6,
  "媒体和娱乐": 7,
  "个人博客": 8,
  "音乐舞蹈": 9,
  "婴幼儿": 10,
  "运动、健身与户外活动": 11,
  "教育和培训": 12,
  "宠物": 13,
  "旅游观光": 14,
  "品牌": 15,
  "软件与应用": 16,
  "生活": "986120",
  "艺术与手工艺": 18,
  "健康": 19,
  "专业服务": 20,
  "IT/高科技": 21,
  "理财与投资": 22,
  "游戏": 23,
  "政务": 24,
  "非政府组织": 25,
  "机械与设备": 26,
  "汽车与运输": 27,
  "公众人物": 28,
  "公共管理": 29,
  "房地产": 30,
  "餐厅&酒吧": 32,
  "美食&烹饪": 33,
  "搞笑": 34,
  "口型同步": 35,
  "动物与自然": 36,
  "社会": 37,
  "DIY和生活窍门": 38,
  "解压": 39,
  "动画与角色扮演": 40,
  "测评&产品教程": 41,
  "摄影": 42,
  "MCN": 43,
  "直播公会": 44,
  "其他": "31"
}

def creator_category(category_name):
    if category_name in creator_category_options:
        return f"cid={creator_category_options[category_name]}"
    else:
        return ''

def affiliate_type(promotion_channel='all', check=False):
    """
    带货方式筛选函数，用于筛选不同类型的带货方式
    
    Args:
        promotion_channel (str): 带货方式筛选
            - 'all': 全部带货方式 (shop_window=1)
            - 'live': 直播带货 (product=2)
            - 'video': 短视频带货 (product=3)
        check (bool): 是否启用带货达人筛选
            - True: 启用筛选，返回对应的URL参数
            - False: 不启用筛选，返回空字符串
    
    Returns:
        str: URL参数字符串
            - 当check=True时，返回对应的筛选参数
            - 当check=False时，返回空字符串
    
    Examples:
        >>> affiliate_type('all', True)
        '&shop_window=1'
        >>> affiliate_type('live', True)
        '&product=2'
        >>> affiliate_type('video', True)
        '&product=3'
        >>> affiliate_type('all', False)
        ''
    """
    # 检查是否启用带货达人筛选
    if check:
        # 根据带货方式进行筛选
        if promotion_channel == 'all':
            # 全部带货方式
            return '&shop_window=1'
        elif promotion_channel == 'live':
            # 直播带货：筛选通过直播带货的达人
            return '&shop_window=1&product=2'
        elif promotion_channel == 'video':
            # 短视频带货：筛选通过短视频带货的达人
            return '&shop_window=1&product=3'
        else:
            # 无效的带货方式，返回空字符串
            return ''
    else:
        # 不启用带货达人筛选
        return ''

def creator_filter(account_type='all', cap_status='all', auth_type='all'):
    """
    达人筛选过滤器函数，用于生成达人筛选的URL参数

    Args:
        account_type (str): 账户类型筛选
            - 'all': 全部账户
            - '&shop_owneed': 商店拥有者账户 (is_shop=1)
            - 'personal': 个人账户 (is_shop=2)
        cap_status (str): 合作状态筛选
            - 'all': 全部状态
            - 'signed': 已签约 (has_partner=1)
            - 'unsigned': 未签约 (has_partner=2)
        auth_type (str): 认证类型筛选
            - 'all': 全部认证状态
            - 'personal': 个人认证 (verify=1)
            - 'verified': 官方认证 (verify=2)

    Returns:
        str: 组合后的URL参数字符串，格式如 "&is_shop=1&has_partner=1&verify=2"

    Examples:
        >>> creator_filter('personal', 'signed', 'verified')
        '&is_shop=2&has_partner=1&verify=2'
        >>> creator_filter()
        ''
    """
    # 处理账户类型筛选
    if account_type == 'all':
        url_params0 = ''
    elif account_type == '&shop_owneed':
        url_params0 = '&is_shop=1'
    elif account_type == 'personal':
        url_params0 = '&is_shop=2'
    else:
        url_params0 = ''
    
    # 处理合作状态筛选
    if cap_status == 'all':
        url_params1 = ''
    elif cap_status == 'signed':
        url_params1 = '&has_partner=1'
    elif cap_status == 'unsigned':
        url_params1 = '&has_partner=2'
    else:
        url_params1 = ''
    
    # 处理认证类型筛选
    if auth_type == 'all':
        url_params2 = ''
    elif auth_type == 'personal':
        url_params2 = '&verify=1'
    elif auth_type == 'verified':
        url_params2 = '&verify=2'
    else:
        url_params2 = ''

    # 组合所有URL参数并返回
    return f"{url_params0}{url_params1}{url_params2}"

def follower_demographic(followers=[], followers_gender='all', followers_age='all', new_followers=[]):
    """
    粉丝信息统计筛选函数，用于根据粉丝特征进行筛选
    
    Args:
        followers (list): 粉丝数量范围筛选
            - 格式: [最小值, 最大值]
            - 例如: [1000, 10000] 表示粉丝数在1000-10000之间
            - 空列表表示不筛选粉丝数量
        followers_gender (str): 粉丝性别筛选
            - 'all': 全部性别
            - 'male': 男性粉丝居多 (gender=1)
            - 'female': 女性粉丝居多 (gender=0)
        followers_age (str): 粉丝年龄筛选
            - 'all': 全部年龄段
            - '18-24': 18-24岁 (age=1)
            - '25-34': 25-34岁 (age=2)
            - '35+': 35岁以上 (age=3)
        new_followers (list): 过去28天新增粉丝数量范围
            - 格式: [最小值, 最大值]
            - 例如: [100, 500] 表示28天内新增粉丝100-500个
            - 空列表表示不筛选新增粉丝数量
    
    Returns:
        str: 组合后的URL参数字符串，格式如 "&follower=1000,10000&gender=1&age=2&follower_28d_count=100,500"
    
    Examples:
        >>> follower_demographic([1000, 10000], 'male', '25-34', [100, 500])
        '&followers=1000,10000&gender=0&age=2&follower_28d_count=100,500'
        >>> follower_demographic()
        ''
    """
    # 处理粉丝数量范围筛选
    if followers == []:
        url_params0 = ''
    else:
        url_params0 = f"&follower={followers[0]},{followers[1]}"
    
    # 处理粉丝性别筛选
    if followers_gender == 'all':
        url_params1 = ''
    elif followers_gender == 'male':
        url_params1 = '&gender=1'  # 男性粉丝居多
    elif followers_gender == 'female':
        url_params1 = '&gender=0'  # 女性粉丝居多
    else:
        url_params1 = ''
    
    # 处理粉丝年龄筛选
    if followers_age == 'all':
        url_params2 = ''
    elif followers_age == '18-24':
        url_params2 = '&age=1'
    elif followers_age == '25-34':
        url_params2 = '&age=2'
    elif followers_age == '35+':
        url_params2 = '&age=3'
    else:
        url_params2 = ''
    
    # 处理过去28天新增粉丝数量筛选
    if new_followers == []:
        url_params3 = ''
    else:
        url_params3 = f"&follower_28d_count={new_followers[0]},{new_followers[1]}"
    
    # 组合所有URL参数并返回
    return f"{url_params0}{url_params1}{url_params2}{url_params3}"



def get_sort_suffix(sort_param):
    """
    根据排序参数返回URL后缀

    Args:
        sort_param: 排序参数，支持以下选项：
            - "近28天涨粉数" (默认)
            - "近28天视频平均播放量"
            - "近28天总销量"
            - "粉丝数"
            - "互动率"
            - "赞粉比"

    Returns:
        str: 对应的URL后缀
    """
    sort_mapping = {
        "近28天涨粉数": "&columnKey=2&field=follower_28d_count_show&order=2,2",
        "近28天视频平均播放量": "&columnKey=6&field=avg_28d_play_count_show&order=6,2",
        "近28天总销量": "&columnKey=12&field=sale_28d_count_show&order=12,2",
        "粉丝数": "&columnKey=1&field=follower_count_show&order=1,2",
        "互动率": "&columnKey=8&field=interaction_v1_rate&order=8,2",
        "赞粉比": "&columnKey=9&field=like_followers_than&order=9,2"
    }

    return sort_mapping.get(sort_param)


def get_max_page_number():
    """
    遍历class="ant-pagination ant-table-pagination ant-table-pagination-right"的ul元素下的所有li元素，
    返回包含文本数值的最大值

    Returns:
        int: 最大页码数值，如果未找到或出错则返回1
    """
    try:
        # 等待页面加载完成
        page.wait_for_load_state('networkidle')

        # 滚动到页面底部以确保分页元素加载完成
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)  # 滚动后等待1秒确保内容加载

        # 显式等待分页元素出现（最多等待10秒）
        try:
            page.wait_for_selector('.ant-pagination.ant-table-pagination.ant-table-pagination-right', timeout=10000)
        except:
            # 静默处理超时
            return 1

        # 额外等待确保分页数据渲染完成
        time.sleep(1)

        # 查找分页容器
        pagination = page.query_selector('.ant-pagination.ant-table-pagination.ant-table-pagination-right')

        if not pagination:
            # 静默处理未找到
            return 1

        # 获取所有li元素
        li_elements = pagination.query_selector_all('li')

        if not li_elements:
            # 静默处理未找到
            return 1

        max_page = 0

        # 遍历所有li元素，提取数值
        for li in li_elements:
            # 获取li元素的文本内容
            text = li.inner_text().strip()

            # 尝试将文本转换为整数
            try:
                page_num = int(text)
                if page_num > max_page:
                    max_page = page_num
            except ValueError:
                # 如果不是数字（如"上一页"、"下一页"等），跳过
                continue

        # 如果没有找到任何数字，返回1
        if max_page == 0:
            # 静默处理未找到
            return 1

        return max_page

    except Exception as e:
        # 静默处理错误
        return 1


def get_table_data_as_dataframe(max_pages=None):
    """
    循环获取多页表格数据并返回DataFrame（不写文件）

    Args:
        max_pages (int, optional): 最大页数，如果不指定则自动获取实际最大页码

    Returns:
        pd.DataFrame: 处理后的数据，如果失败则返回None
    """
    try:
        # 如果没有指定max_pages，则自动获取实际最大页码
        if max_pages is None:
            max_pages = get_max_page_number()

        # 获取当前URL
        current_url = page.url

        # 检查URL中是否已有page参数
        if '&page=' in current_url:
            # 如果已有page参数，替换为page=1
            base_url = re.sub(r'&page=\d+', '', current_url)
        else:
            # 如果没有page参数，直接使用当前URL
            base_url = current_url

        # 汇总所有页面的数据
        all_data = []
        headers = []
        total_rows = 0

        for page_num in range(1, max_pages + 1):
            # 构建当前页的URL
            if '?' in base_url:
                page_url = f"{base_url}&page={page_num}"
            else:
                page_url = f"{base_url}?page={page_num}"

            # 导航到当前页
            page.goto(page_url)

            # 等待页面加载完成
            page.wait_for_load_state('networkidle')

            # 等待3秒确保数据加载完全
            time.sleep(3)

            # 滚动到页面底部以触发懒加载
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)  # 滚动后额外等待1秒

            # 查找class="ant-table-container"的元素
            table_container = page.query_selector('.ant-table-container')

            if not table_container:
                break

            # 获取表格行
            rows = table_container.query_selector_all('tr')
            if not rows:
                break

            # 提取当前页的表格数据
            page_data = []

            for i, row in enumerate(rows):
                # 获取行中的单元格
                cells = row.query_selector_all('td, th')
                row_data = []

                for cell in cells:
                    cell_text = cell.inner_text().strip()
                    row_data.append(cell_text)

                if row_data:  # 只添加非空行
                    # 获取data-row-key属性
                    row_key = row.get_attribute('data-row-key')

                    # 检查是否是表头行（没有data-row-key属性）
                    if not row_key:
                        if page_num == 1:  # 只在第一页时保存表头
                            headers = row_data
                            # 为表头添加data-row-key列名
                            if len(headers) > 0:
                                headers.append('data-row-key')
                        # 跳过所有页面的表头行，不添加到page_data中
                        continue
                    else:
                        # 这是数据行，添加data-row-key
                        row_data.append(row_key)
                        page_data.append(row_data)

            # 如果当前页没有数据，说明已经到最后一页了
            if not page_data:
                break

            # 将当前页数据添加到总数据中
            all_data.extend(page_data)
            total_rows += len(page_data)

        # 如果没有获取到任何数据，返回None
        if not all_data:
            return None

        # 创建DataFrame
        df = pd.DataFrame(all_data, columns=headers)

        # 清洗"带货品类"列的数据
        if '带货品类' in df.columns:
            def clean_category(text):
                if pd.isna(text) or text == '':
                    return text
                # 去掉类似 +45 这样的内容（+号后面跟数字）
                text = re.sub(r'\+\d+', '', text)
                # 替换换行符为逗号
                text = text.replace('\n', ',')
                # 去掉多余的空格和逗号
                text = re.sub(r',\s*,', ',', text)  # 去掉连续的逗号
                text = re.sub(r',\s*$', '', text)  # 去掉末尾的逗号
                text = re.sub(r'^\s*,', '', text)  # 去掉开头的逗号
                text = text.strip()
                return text

            df['带货品类'] = df['带货品类'].apply(clean_category)

        # 转换带单位的数值为纯数字
        def convert_to_number(text):
            """
            将带有万、亿等单位的数值字符串转换为实际数值
            例如: 3.99万 -> 39900, 1.5亿 -> 150000000
            """
            if pd.isna(text) or text == '' or text == '-':
                return None  # 返回None以便pandas识别为缺失值

            text = str(text).strip()

            # 匹配数字+单位的格式
            match = re.match(r'([\d.]+)\s*([万亿千百]?)', text)
            if match:
                number_str, unit = match.groups()
                try:
                    number = float(number_str)

                    # 根据单位进行转换
                    if unit == '万':
                        return number * 10000
                    elif unit == '亿':
                        return number * 100000000
                    elif unit == '千':
                        return number * 1000
                    elif unit == '百':
                        return number * 100
                    else:
                        # 没有单位，直接返回数值
                        return number
                except ValueError:
                    return None

            return None

        # 转换百分比格式为小数
        def convert_percentage(text):
            """
            将百分比字符串转换为小数
            例如: 5.23% -> 0.0523
            """
            if pd.isna(text) or text == '' or text == '-':
                return None

            text = str(text).strip()

            # 匹配百分比格式
            match = re.match(r'([\d.]+)%', text)
            if match:
                try:
                    number = float(match.group(1))
                    return number / 100
                except ValueError:
                    return None

            # 如果不是百分比格式，尝试直接转换为数字
            try:
                return float(text)
            except ValueError:
                return None

        # 需要转换为数值的列
        numeric_columns = {
            '粉丝数': convert_to_number,
            '近28天涨粉数': convert_to_number,
            '近28天视频平均播放量': convert_to_number,
            '近28天总销量': convert_to_number,
            '互动率': convert_percentage,
            '赞粉比': convert_to_number
        }

        # 处理所有需要转换的列
        for col_name, convert_func in numeric_columns.items():
            if col_name in df.columns:
                df[col_name] = df[col_name].apply(convert_func)
                # 确保列类型为数值类型
                df[col_name] = pd.to_numeric(df[col_name], errors='coerce')

        # 定义需要排除的列名
        columns_to_exclude = ['近28天销量趋势', '操作']

        # 过滤掉不需要的列
        columns_to_keep = [col for col in df.columns if col not in columns_to_exclude]
        df = df[columns_to_keep]

        print(f"多页表格数据获取完成: 共 {total_rows} 行数据，{len(columns_to_keep)} 列")

        return df

    except Exception as e:
        print(f"获取多页表格数据时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def build_complete_url(
        country_name="全部",
        category_name=None,
        promotion_channel='all',
        affiliate_check=False,
        account_type='all',
        cap_status='all',
        auth_type='all',
        followers=[],
        followers_gender='all',
        followers_age='all',
        new_followers=[],
    ):
    """
    获取URL后缀并拼接到main_url后面返回完整的URL

    Args:
        country_name (str): 国家/地区名称，默认"全部"
        category_name (str): 创作者类别名称，默认None
        promotion_channel (str): 带货方式筛选，默认'all'
        affiliate_check (bool): 是否启用带货达人筛选，默认False
        account_type (str): 账户类型筛选，默认'all'
        cap_status (str): 合作状态筛选，默认'all'
        auth_type (str): 认证类型筛选，默认'all'
        followers (list): 粉丝数量范围筛选，默认[]
        followers_gender (str): 粉丝性别筛选，默认'all'
        followers_age (str): 粉丝年龄筛选，默认'all'
        new_followers (list): 过去28天新增粉丝数量范围，默认[]


    Returns:
        str: 完整的URL字符串（不包含排序参数）

    Examples:
        >>> build_complete_url(country_name="美国", category_name="美妆", followers=[1000, 10000])
        'https://www.fastmoss.com/zh/influencer/search?region=US&cid=4&followers=1000,10000'
    """
    # 收集所有URL后缀
    url_suffixes = []

    # 1. 调用 choose_country 获取国家/地区后缀
    country_suffix = choose_country(country_name)
    if country_suffix:
        url_suffixes.append(country_suffix)

    # 2. 调用 creator_category 获取创作者类别后缀
    if category_name:
        category_suffix = creator_category(category_name)
        if category_suffix:
            url_suffixes.append(category_suffix)

    # 3. 调用 affiliate_type 获取带货达人类型后缀
    affiliate_suffix = affiliate_type(promotion_channel, affiliate_check)
    if affiliate_suffix:
        url_suffixes.append(affiliate_suffix)

    # 4. 调用 creator_filter 获取创作者过滤后缀
    filter_suffix = creator_filter(account_type, cap_status, auth_type)
    if filter_suffix:
        url_suffixes.append(filter_suffix)

    # 5. 调用 follower_demographic 获取粉丝人口统计后缀
    demographic_suffix = follower_demographic(followers, followers_gender, followers_age, new_followers)
    if demographic_suffix:
        url_suffixes.append(demographic_suffix)
    # 拼接完整URL
    # 处理URL后缀的连接符

    complete_url = main_url
    for i, suffix in enumerate(url_suffixes):
        if i == 0:
            # 第一个后缀，检查是否以&开头
            if suffix.startswith('&'):
                complete_url += suffix[1:]  # 去掉开头的&
            else:
                complete_url += suffix
        else:
            # 后续后缀，确保以&连接
            if suffix.startswith('&'):
                complete_url += suffix
            else:
                complete_url += '&' + suffix

    return complete_url


def navigate_to_url(url: str, wait_for_load: bool = True) -> bool:
    """
    导航到指定的 URL

    Args:
        url: 要访问的 URL
        wait_for_load: 是否等待页面完全加载

    Returns:
        bool: 是否成功访问
    """
    global page

    if page is None:
        print("❌ Playwright 未初始化,请先调用 initialize_playwright()")
        return False

    try:
        if wait_for_load:
            page.goto(url, wait_until="networkidle", timeout=60000)
        else:
            page.goto(url, timeout=30000)

        # 等待表格加载
        time.sleep(2)
        return True

    except Exception as e:
        print(f"❌ 访问 URL 失败: {e}")
        return False


