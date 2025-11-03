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


def remove_show_fields(data):
    """
    递归删除数据中所有包含'show'的字段

    Args:
        data: 要处理的数据（字典、列表或其他类型）

    Returns:
        处理后的数据（已删除所有包含'show'的字段）
    """
    if isinstance(data, dict):
        # 创建新字典，排除所有包含'show'的字段（不区分大小写）
        return {k: remove_show_fields(v) for k, v in data.items() if 'show' not in k.lower()}
    elif isinstance(data, list):
        # 递归处理列表中的每个元素
        return [remove_show_fields(item) for item in data]
    else:
        # 其他类型直接返回
        return data


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
    
def capture_api_responses(api_types=None, wait_time=5):
    """
    通用的API请求响应捕获函数
    
    监听网络请求，捕获指定类型的API请求并获取其响应数据
    
    Args:
        api_types (list): 要捕获的API类型列表，支持以下类型：
            - 'datalist': 包含dataList?uid=的请求
            - 'baseInfo': 包含baseInfo的请求
            - 'authorIndex': 包含authorIndex的请求
            - 'getStatInfo': 包含getStatInfo的请求
            - 'all': 捕获所有API请求
        如果为None，默认捕获datalist请求
        wait_time (int): 等待时间（秒），默认为5秒
    
    Returns:
        dict: 包含各种API类型响应的字典，格式为 {api_type: [responses]}
    """
    try:
        if api_types is None:
            api_types = ['datalist']
        
        # 如果包含'all'，则捕获所有类型的API请求
        if 'all' in api_types:
            api_types = ['datalist', 'baseInfo', 'authorIndex', 'getStatInfo']
        
        # 存储所有响应数据，按类型分组
        all_responses = {api_type: [] for api_type in api_types}
        
        def handle_response(response):
            """处理响应事件"""
            url = response.url
            
            # 检查URL是否匹配任何目标API类型
            matched_type = None
            for api_type in api_types:
                if api_type == 'datalist' and 'dataList?uid=' in url:
                    matched_type = 'datalist'
                    break
                elif api_type == 'baseInfo' and 'baseInfo' in url:
                    matched_type = 'baseInfo'
                    break
                elif api_type == 'authorIndex' and 'authorIndex' in url:
                    matched_type = 'authorIndex'
                    break
                elif api_type == 'getStatInfo' and 'getStatInfo' in url:
                    matched_type = 'getStatInfo'
                    break
            
            if matched_type:
                print(f"找到{matched_type}请求: {url}")
                
                response_info = {
                    'url': url,
                    'status': response.status,
                    'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
                    'api_type': matched_type
                }
                
                try:
                    # 获取响应数据
                    if response.status == 200:
                        data = response.json()
                        response_info['data'] = data
                        
                        print(f"成功获取{matched_type}响应数据")
                        print(f"响应状态: {response.status}")
                        print(f"数据长度: {len(str(data))} 字符")
                        
                        # 提取URL参数
                        import urllib.parse
                        parsed_url = urllib.parse.urlparse(url)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        
                        # 根据API类型提取特定参数
                        if matched_type == 'datalist':
                            uid = query_params.get('uid', [''])[0]
                            if uid:
                                response_info['uid'] = uid
                                print(f"提取到UID: {uid}")
                            # 提取field_type参数
                            field_type = query_params.get('field_type', [''])[0]
                            if field_type:
                                response_info['field_type'] = field_type
                                print(f"提取到field_type: {field_type}")
                        elif matched_type == 'baseInfo':
                            # 提取baseInfo相关参数
                            for param in ['uid', 'id', 'author_id']:
                                if param in query_params:
                                    response_info[param] = query_params[param][0]
                                    print(f"提取到{param}: {query_params[param][0]}")
                        elif matched_type == 'authorIndex':
                            # 提取authorIndex相关参数
                            for param in ['uid', 'id', 'author_id', 'index']:
                                if param in query_params:
                                    response_info[param] = query_params[param][0]
                                    print(f"提取到{param}: {query_params[param][0]}")
                        elif matched_type == 'getStatInfo':
                            # 提取getStatInfo相关参数
                            for param in ['uid', 'id', 'author_id', 'stat_type']:
                                if param in query_params:
                                    response_info[param] = query_params[param][0]
                                    print(f"提取到{param}: {query_params[param][0]}")
                        
                    else:
                        print(f"请求失败，状态码: {response.status}")
                        response_info['error'] = f"HTTP {response.status}"
                        
                except Exception as e:
                    print(f"解析{matched_type}响应数据时出错: {e}")
                    response_info['error'] = str(e)
                    
                    # 尝试获取文本内容
                    try:
                        text_data = response.text()
                        response_info['text'] = text_data
                        print(f"获取到{matched_type}文本响应数据，长度: {len(text_data)} 字符")
                    except Exception as text_e:
                        print(f"获取{matched_type}文本响应也失败: {text_e}")
                        response_info['text_error'] = str(text_e)
                
                all_responses[matched_type].append(response_info)
        
        # 设置响应监听器
        page.on("response", handle_response)
        
        # 等待页面加载完成
        page.wait_for_load_state('networkidle')
        
        # 等待指定时间确保捕获到所有请求
        time.sleep(wait_time)
        
        # 保存所有响应到JSON文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 为每种API类型创建单独的文件
        saved_files = {}
        for api_type, responses in all_responses.items():
            if responses:
                filename = f"{api_type}_responses_{timestamp}.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(responses, f, ensure_ascii=False, indent=2)
                saved_files[api_type] = filename
                print(f"所有{api_type}响应数据已保存到: {filename}")
                print(f"总共捕获到 {len(responses)} 个{api_type}响应")
            else:
                print(f"未找到{api_type}类型的请求")
        
        # 如果捕获到了任何数据，也保存一个汇总文件
        if any(responses for responses in all_responses.values()):
            summary_filename = f"api_responses_summary_{timestamp}.json"
            with open(summary_filename, 'w', encoding='utf-8') as f:
                json.dump(all_responses, f, ensure_ascii=False, indent=2)
            saved_files['summary'] = summary_filename
            print(f"所有API响应汇总已保存到: {summary_filename}")
        
        return all_responses
            
    except Exception as e:
        print(f"捕捉API响应时出错: {e}")
        return {}


def capture_datalist_response():
    """
    捕捉包含dataList?uid=的请求响应
    
    监听网络请求，找到包含dataList?uid=的API请求并获取其响应数据
    
    Returns:
        list: 包含所有dataList响应的列表，如果未找到则返回空列表
    """
    try:
        # 使用通用函数捕获datalist请求
        result = capture_api_responses(['datalist'])
        return result.get('datalist', [])
            
    except Exception as e:
        print(f"捕捉dataList响应时出错: {e}")
        return []


def capture_baseInfo_response():
    """
    捕捉包含baseInfo的请求响应
    
    Returns:
        list: 包含所有baseInfo响应的列表，如果未找到则返回空列表
    """
    try:
        # 使用通用函数捕获baseInfo请求
        result = capture_api_responses(['baseInfo'])
        return result.get('baseInfo', [])
            
    except Exception as e:
        print(f"捕捉baseInfo响应时出错: {e}")
        return []


def capture_authorIndex_response():
    """
    捕捉包含authorIndex的请求响应
    
    Returns:
        list: 包含所有authorIndex响应的列表，如果未找到则返回空列表
    """
    try:
        # 使用通用函数捕获authorIndex请求
        result = capture_api_responses(['authorIndex'])
        return result.get('authorIndex', [])
            
    except Exception as e:
        print(f"捕捉authorIndex响应时出错: {e}")
        return []


def capture_getStatInfo_response():
    """
    捕捉包含getStatInfo的请求响应
    
    Returns:
        list: 包含所有getStatInfo响应的列表，如果未找到则返回空列表
    """
    try:
        # 使用通用函数捕获getStatInfo请求
        result = capture_api_responses(['getStatInfo'])
        return result.get('getStatInfo', [])
            
    except Exception as e:
        print(f"捕捉getStatInfo响应时出错: {e}")
        return []


def capture_all_api_responses():
    """
    捕捉所有类型的API请求响应
    
    Returns:
        dict: 包含所有API类型响应的字典
    """
    try:
        # 使用通用函数捕获所有类型的请求
        return capture_api_responses(['all'])
            
    except Exception as e:
        print(f"捕捉所有API响应时出错: {e}")
        return {}




def get_influencer_data(target_url):
    """
    获取达人详细数据的完整函数
    
    Args:
        target_url (str): 达人详情页面的URL，例如：
            "https://www.fastmoss.com/zh/influencer/detail/7288986759428588590"
    
    Returns:
        dict: 包含所有API响应数据的字典，如果失败则返回空字典
    
    Example:
        >>> data = get_influencer_data("https://www.fastmoss.com/zh/influencer/detail/7288986759428588590")
        >>> print(f"捕获到 {data.get('total_requests', 0)} 个API请求")
    """
    try:
        print(f"开始获取达人详细数据: {target_url}")
        
        # 初始化Playwright
        initialize_playwright()
        
        # 定义所有支持的API类型
        api_types = [
            'datalist', 'baseInfo', 'authorIndex', 'getStatInfo',
            'fansPortrait', 'labelList',  'cargoStat', 'cargoSummary'
        ]
        # 'videoList', 'videoStat','liveList', 'liveStat','categoryList', 'shopList', 'goodsList', 'goodsFilter', 'similarityList'
        # 存储所有响应数据，按类型分组
        all_responses = {api_type: [] for api_type in api_types}

        # 跟踪只需要保存一次的API类型
        captured_once = {'baseInfo': False, 'authorIndex': False, 'getStatInfo': False, 'categoryList': False}

        def handle_response(response):
            """处理响应事件"""
            url = response.url

            # 检查URL是否匹配任何目标API类型
            matched_type = None
            for api_type in api_types:
                if api_type == 'datalist' and 'dataList?uid=' in url:
                    matched_type = 'datalist'
                    break
                elif api_type == 'baseInfo' and 'baseInfo' in url:
                    matched_type = 'baseInfo'
                    break
                elif api_type == 'authorIndex' and 'authorIndex' in url:
                    matched_type = 'authorIndex'
                    break
                elif api_type == 'getStatInfo' and 'getStatInfo' in url:
                    matched_type = 'getStatInfo'
                    break
                elif api_type == 'fansPortrait' and 'fansPortrait' in url:
                    matched_type = 'fansPortrait'
                    break
                elif api_type == 'labelList' and 'labelList' in url:
                    matched_type = 'labelList'
                    break
                elif api_type == 'videoList' and 'videoList' in url:
                    matched_type = 'videoList'
                    break
                elif api_type == 'videoStat' and 'videoStat' in url:
                    matched_type = 'videoStat'
                    break
                elif api_type == 'liveList' and 'liveList' in url:
                    matched_type = 'liveList'
                    break
                elif api_type == 'liveStat' and 'liveStat' in url:
                    matched_type = 'liveStat'
                    break
                elif api_type == 'cargoStat' and 'cargoStat' in url:
                    matched_type = 'cargoStat'
                    break
                elif api_type == 'cargoSummary' and 'cargoSummary' in url:
                    matched_type = 'cargoSummary'
                    break
                elif api_type == 'categoryList' and 'categoryList' in url:
                    matched_type = 'categoryList'
                    break
                elif api_type == 'shopList' and 'shopList' in url:
                    matched_type = 'shopList'
                    break
                elif api_type == 'goodsList' and 'goodsList' in url:
                    matched_type = 'goodsList'
                    break
                elif api_type == 'goodsFilter' and 'goodsFilter' in url:
                    matched_type = 'goodsFilter'
                    break
                elif api_type == 'similarityList' and 'similarityList' in url:
                    matched_type = 'similarityList'
                    break

            if matched_type:
                # 对于baseInfo、authorIndex、getStatInfo、categoryList，如果已经捕获过一次就跳过
                if matched_type in captured_once:
                    if captured_once[matched_type]:
                        print(f"跳过{matched_type}请求（已经捕获过）: {url}")
                        return
                    else:
                        # 立即标记为已捕获，防止并发请求重复保存
                        captured_once[matched_type] = True

                # 过滤date_type=28的请求（针对datalist, fansPortrait, liveList, liveStat, goodsList, goodsFilter）
                if matched_type in ['datalist', 'fansPortrait','videoList','videoStat', 'liveList', 'liveStat', 'goodsList', 'goodsFilter']:
                    if 'date_type=28' in url:
                        print(f"跳过{matched_type}请求（date_type=28）: {url}")
                        return


                print(f"找到{matched_type}请求: {url}")

                response_info = {
                    'url': url,
                    'status': response.status,
                    'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
                    'api_type': matched_type
                }

                try:
                    # 获取响应数据
                    if response.status == 200:
                        data = response.json()
                        response_info['data'] = data

                        print(f"成功获取{matched_type}响应数据")
                        print(f"响应状态: {response.status}")
                        print(f"数据长度: {len(str(data))} 字符")

                        # 提取URL参数
                        import urllib.parse
                        parsed_url = urllib.parse.urlparse(url)
                        query_params = urllib.parse.parse_qs(parsed_url.query)

                        # 根据API类型提取特定参数
                        common_params = ['uid', 'id', 'author_id', 'page', 'size', 'limit', 'offset']
                        for param in common_params:
                            if param in query_params:
                                response_info[param] = query_params[param][0]
                                print(f"提取到{param}: {query_params[param][0]}")

                        # 对于datalist类型，额外提取field_type参数
                        if matched_type == 'datalist':
                            field_type = query_params.get('field_type', [''])[0]
                            if field_type:
                                response_info['field_type'] = field_type
                                print(f"提取到field_type: {field_type}")

                    else:
                        print(f"请求失败，状态码: {response.status}")
                        response_info['error'] = f"HTTP {response.status}"

                except Exception as e:
                    print(f"解析{matched_type}响应数据时出错: {e}")
                    response_info['error'] = str(e)

                    # 尝试获取文本内容
                    try:
                        text_data = response.text()
                        response_info['text'] = text_data
                        print(f"获取到{matched_type}文本响应数据，长度: {len(text_data)} 字符")
                    except Exception as text_e:
                        print(f"获取{matched_type}文本响应也失败: {text_e}")
                        response_info['text_error'] = str(text_e)

                all_responses[matched_type].append(response_info)

        # 先设置响应监听器
        print("正在设置API请求监听器...")
        page.on("response", handle_response)

        # 访问目标网页
        print(f"正在访问页面: {target_url}")
        page.goto(target_url)

        # 等待页面加载完成
        print("等待页面加载完成...")
        page.wait_for_load_state('networkidle')

        # 执行全面滚动策略
        print("执行全面滚动策略以加载所有数据...")
        print("使用慢速滚动确保所有懒加载内容都能被触发...")
        
        # 获取页面高度
        page_height = page.evaluate("document.body.scrollHeight")
        print(f"页面总高度: {page_height}px")
        
        # 慢速滚动策略：分步滚动，每次滚动一小段距离
        scroll_step = 300  # 每次滚动300px
        current_position = 0
        scroll_count = 0
        
        while current_position < page_height:
            scroll_count += 1
            next_position = min(current_position + scroll_step, page_height)
            
            print(f"第 {scroll_count} 次滚动: {current_position}px → {next_position}px")
            
            # 滚动到下一个位置
            page.evaluate(f"window.scrollTo(0, {next_position})")
            
            # 等待内容加载
            time.sleep(0.5)
            
            # 检查是否有"加载更多"按钮并点击
            try:
                load_more_selectors = [
                    'button:has-text("加载更多")',
                    'button:has-text("Load More")',
                    'button:has-text("查看更多")',
                    'button:has-text("显示更多")',
                    '.load-more',
                    '.load-more-btn',
                    '[data-testid="load-more"]',
                    '.ant-btn:has-text("加载更多")',
                    '.ant-btn:has-text("查看更多")'
                ]
                
                for selector in load_more_selectors:
                    try:
                        load_more_btn = page.query_selector(selector)
                        if load_more_btn and load_more_btn.is_visible():
                            print(f"找到加载更多按钮，点击: {selector}")
                            load_more_btn.click()
                            time.sleep(2)
                            # 重新获取页面高度，因为可能加载了新内容
                            new_height = page.evaluate("document.body.scrollHeight")
                            if new_height > page_height:
                                print(f"页面高度增加: {page_height}px → {new_height}px")
                                page_height = new_height
                            break
                    except:
                        continue
                        
            except Exception as e:
                print(f"检查加载更多按钮时出错: {e}")
            
            # 更新当前位置
            current_position = next_position
            
            # 每滚动10次检查一次页面高度是否有变化
            if scroll_count % 10 == 0:
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height > page_height:
                    print(f"检测到页面高度变化: {page_height}px → {new_height}px")
                    page_height = new_height
        
        print(f"慢速滚动完成，总共滚动 {scroll_count} 次")
        
        # 滚动到顶部
        print("滚动到页面顶部...")
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(2)
        
        # 再次慢速滚动到底部确保所有内容都加载
        print("再次慢速滚动到底部确保所有内容加载...")
        final_height = page.evaluate("document.body.scrollHeight")
        if final_height > page_height:
            print(f"最终页面高度: {final_height}px")
            page_height = final_height
        
        # 最终滚动到底部
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(3)
        
        ninety_days_spans = page.locator("label.ant-radio-button-wrapper:has-text('近90天')").all()
        for span in ninety_days_spans:
            span.click()
            page.wait_for_timeout(1000)

        # 定义处理下拉菜单的函数
        def process_dropdown_menu(section_name):
            """
            处理指定区域的下拉菜单选项

            Args:
                section_name: 区域名称，如"近期数据"或"带货数据"
            """
            print(f"开始处理{section_name}区域的下拉菜单...")
            try:
                # 先定位包含指定文本的div元素
                section_div = page.locator(f'div.flex.justify-between.items-center:has-text("{section_name}")').first

                # 在这个div上下文中定位ant-select-selector
                selector_div = section_div.locator('div.ant-select-selector').first

                # 点击selector_div展开下拉菜单
                selector_div.click()
                page.wait_for_timeout(1000)

                # 获取下拉菜单的所有子div元素
                if section_name == "近期数据":
                    dropdown_holder = page.locator('div.rc-virtual-list-holder-inner').first
                elif section_name == "带货数据":
                    dropdown_holder = page.locator('div.rc-virtual-list-holder-inner').nth(1)
                child_divs = dropdown_holder.locator('> div').all()
                total_divs = len(child_divs)
                print(f"找到 {total_divs} 个下拉选项")

                # 从第二个div开始遍历(索引从1开始,跳过第0个)
                for i in range(1, total_divs):
                    print(f"点击第 {i+1} 个选项...")
                    child_divs = dropdown_holder.locator('> div').all()
                    # 点击当前div
                    child_divs[i].click()
                    page.wait_for_timeout(1500)

                    # 如果不是最后一个元素，重新点击selector展开下拉菜单
                    if i < total_divs - 1:
                        selector_div.click()
                        page.wait_for_timeout(1000)
                        # 重新获取dropdown_holder
                        if section_name == "近期数据":
                            dropdown_holder = page.locator('div.rc-virtual-list-holder-inner').first
                        elif section_name == "带货数据":
                            dropdown_holder = page.locator('div.rc-virtual-list-holder-inner').nth(1)

                print(f"{section_name}区域的下拉菜单处理完成")

            except Exception as e:
                print(f"处理{section_name}区域的下拉菜单时出错: {e}")

        # 处理"近期数据"区域的下拉菜单
        process_dropdown_menu("近期数据")

        # 处理"带货数据"区域的下拉菜单
        process_dropdown_menu("带货数据")



        # 从target_url中提取数字作为文件名
        import re
        url_number = re.search(r'/(\d+)$', target_url)
        if url_number:
            file_number = url_number.group(1)
        else:
            # 如果没有找到数字，使用时间戳
            file_number = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建influencer文件夹（如果不存在）
        influencer_dir = "influencer"
        if not os.path.exists(influencer_dir):
            os.makedirs(influencer_dir)
            print(f"创建文件夹: {influencer_dir}")

        # 重组datalist数据：按field_type分组，只保留data字段
        datalist_by_field_type = {}
        if 'datalist' in all_responses:
            for response in all_responses['datalist']:
                field_type = response.get('field_type')
                if field_type and 'data' in response:
                    # 只保留data字段的内容
                    datalist_by_field_type[field_type] = response['data'].get('data', response['data'])

        # 替换原来的datalist数据
        all_responses['datalist'] = datalist_by_field_type

        # 对其他API类型也只保留data字段
        api_types_to_simplify = [
            'baseInfo', 'authorIndex', 'getStatInfo', 'fansPortrait',
            'labelList', 'videoList', 'videoStat', 'liveList', 'liveStat',
            'cargoStat', 'cargoSummary', 'categoryList', 'shopList',
            'goodsList', 'goodsFilter', 'similarityList'
        ]

        for api_type in api_types_to_simplify:
            if api_type in all_responses and all_responses[api_type]:
                if isinstance(all_responses[api_type], list) and len(all_responses[api_type]) > 0:
                    # 取第一个响应的data字段
                    response = all_responses[api_type][0]
                    if 'data' in response:
                        all_responses[api_type] = response['data'].get('data', response['data'])

        # 创建合并的数据结构
        merged_data = {
            'target_url': target_url,
            'capture_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_requests': sum(len(responses) if isinstance(responses, list) else 1 for responses in all_responses.values()),
            'api_responses': all_responses
        }

        # 删除所有'show'字段
        merged_data_cleaned = remove_show_fields(merged_data)

        # 保存合并后的数据到influencer文件夹，只用数字命名
        merged_filename = os.path.join(influencer_dir, f"{file_number}.json")
        with open(merged_filename, 'w', encoding='utf-8') as f:
            json.dump(merged_data_cleaned, f, ensure_ascii=False, indent=2)
        
        print(f"所有API响应数据已合并保存到: {merged_filename}")
        
        # 显示统计信息
        total_captured = sum(len(responses) for responses in all_responses.values())
        print(f"总共捕获到 {total_captured} 个API请求")
        
        for api_type, responses in all_responses.items():
            if responses:
                print(f"  ✓ {api_type}: {len(responses)} 个请求")
            else:
                print(f"  ✗ {api_type}: 0 个请求")
        
        # 清理资源
        cleanup_playwright()
        
        return merged_data
            
    except Exception as e:
        print(f"获取达人数据时出错: {e}")
        # 确保清理资源
        try:
            cleanup_playwright()
        except:
            pass
        return {}


def capture_api_responses_with_navigation(target_url, api_types=None, wait_time=10, scroll_strategy='comprehensive'):
    """
    先启动监听，再访问指定网页来捕获API响应，支持更多API类型和智能滚动策略
    
    Args:
        target_url (str): 要访问的目标URL
        api_types (list): 要捕获的API类型列表
        wait_time (int): 等待时间（秒）
        scroll_strategy (str): 滚动策略
            - 'simple': 简单滚动（上下各一次）
            - 'comprehensive': 全面滚动（多次滚动到底部加载所有数据）
    
    Returns:
        dict: 包含各种API类型响应的字典
    """
    try:
        if api_types is None:
            api_types = ['all']
        
        # 定义所有支持的API类型
        all_api_types = [
            'datalist', 'baseInfo', 'authorIndex', 'getStatInfo',
            'fansPortrait', 'labelList', 'videoList', 'videoStat',
            'liveList', 'liveStat', 'cargoStat', 'cargoSummary',
            'categoryList', 'shopList', 'goodsList', 'goodsFilter', 'similarityList'
        ]
        
        # 如果包含'all'，则捕获所有类型的API请求
        if 'all' in api_types:
            api_types = all_api_types
        
        # 存储所有响应数据，按类型分组
        all_responses = {api_type: [] for api_type in api_types}

        # 跟踪只需要保存一次的API类型
        captured_once = {'baseInfo': False, 'authorIndex': False, 'getStatInfo': False, 'categoryList': False}

        def handle_response(response):
            """处理响应事件"""
            url = response.url

            # 检查URL是否匹配任何目标API类型
            matched_type = None
            for api_type in api_types:
                if api_type == 'datalist' and 'dataList?uid=' in url:
                    matched_type = 'datalist'
                    break
                elif api_type == 'baseInfo' and 'baseInfo' in url:
                    matched_type = 'baseInfo'
                    break
                elif api_type == 'authorIndex' and 'authorIndex' in url:
                    matched_type = 'authorIndex'
                    break
                elif api_type == 'getStatInfo' and 'getStatInfo' in url:
                    matched_type = 'getStatInfo'
                    break
                elif api_type == 'fansPortrait' and 'fansPortrait' in url:
                    matched_type = 'fansPortrait'
                    break
                elif api_type == 'labelList' and 'labelList' in url:
                    matched_type = 'labelList'
                    break
                elif api_type == 'videoList' and 'videoList' in url:
                    matched_type = 'videoList'
                    break
                elif api_type == 'videoStat' and 'videoStat' in url:
                    matched_type = 'videoStat'
                    break
                elif api_type == 'liveList' and 'liveList' in url:
                    matched_type = 'liveList'
                    break
                elif api_type == 'liveStat' and 'liveStat' in url:
                    matched_type = 'liveStat'
                    break
                elif api_type == 'cargoStat' and 'cargoStat' in url:
                    matched_type = 'cargoStat'
                    break
                elif api_type == 'cargoSummary' and 'cargoSummary' in url:
                    matched_type = 'cargoSummary'
                    break
                elif api_type == 'categoryList' and 'categoryList' in url:
                    matched_type = 'categoryList'
                    break
                elif api_type == 'shopList' and 'shopList' in url:
                    matched_type = 'shopList'
                    break
                elif api_type == 'goodsList' and 'goodsList' in url:
                    matched_type = 'goodsList'
                    break
                elif api_type == 'goodsFilter' and 'goodsFilter' in url:
                    matched_type = 'goodsFilter'
                    break
                elif api_type == 'similarityList' and 'similarityList' in url:
                    matched_type = 'similarityList'
                    break

            if matched_type:
                # 对于baseInfo、authorIndex、getStatInfo、categoryList，如果已经捕获过一次就跳过
                if matched_type in captured_once:
                    if captured_once[matched_type]:
                        print(f"跳过{matched_type}请求（已经捕获过）: {url}")
                        return
                    else:
                        # 立即标记为已捕获，防止并发请求重复保存
                        captured_once[matched_type] = True

                # 过滤date_type=28的请求（针对datalist, fansPortrait, liveList, liveStat, goodsList, goodsFilter）
                if matched_type in ['datalist', 'fansPortrait', 'liveList', 'liveStat', 'goodsList', 'goodsFilter']:
                    if 'date_type=28' in url:
                        print(f"跳过{matched_type}请求（date_type=28）: {url}")
                        return


                print(f"找到{matched_type}请求: {url}")

                response_info = {
                    'url': url,
                    'status': response.status,
                    'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
                    'api_type': matched_type
                }

                try:
                    # 获取响应数据
                    if response.status == 200:
                        data = response.json()
                        response_info['data'] = data

                        print(f"成功获取{matched_type}响应数据")
                        print(f"响应状态: {response.status}")
                        print(f"数据长度: {len(str(data))} 字符")

                        # 提取URL参数
                        import urllib.parse
                        parsed_url = urllib.parse.urlparse(url)
                        query_params = urllib.parse.parse_qs(parsed_url.query)

                        # 根据API类型提取特定参数
                        common_params = ['uid', 'id', 'author_id', 'page', 'size', 'limit', 'offset']
                        for param in common_params:
                            if param in query_params:
                                response_info[param] = query_params[param][0]
                                print(f"提取到{param}: {query_params[param][0]}")

                        # 对于datalist类型，额外提取field_type参数
                        if matched_type == 'datalist':
                            field_type = query_params.get('field_type', [''])[0]
                            if field_type:
                                response_info['field_type'] = field_type
                                print(f"提取到field_type: {field_type}")

                    else:
                        print(f"请求失败，状态码: {response.status}")
                        response_info['error'] = f"HTTP {response.status}"

                except Exception as e:
                    print(f"解析{matched_type}响应数据时出错: {e}")
                    response_info['error'] = str(e)

                    # 尝试获取文本内容
                    try:
                        text_data = response.text()
                        response_info['text'] = text_data
                        print(f"获取到{matched_type}文本响应数据，长度: {len(text_data)} 字符")
                    except Exception as text_e:
                        print(f"获取{matched_type}文本响应也失败: {text_e}")
                        response_info['text_error'] = str(text_e)

                all_responses[matched_type].append(response_info)

        # 先设置响应监听器
        print("正在设置API请求监听器...")
        page.on("response", handle_response)

        # 访问目标网页
        print(f"正在访问页面: {target_url}")
        page.goto(target_url)

        # 等待页面加载完成
        print("等待页面加载完成...")
        page.wait_for_load_state('networkidle')

        # 根据滚动策略执行不同的滚动操作
        if scroll_strategy == 'comprehensive':
            print("执行全面滚动策略以加载所有数据...")
            print("使用慢速滚动确保所有懒加载内容都能被触发...")
            
            # 获取页面高度
            page_height = page.evaluate("document.body.scrollHeight")
            print(f"页面总高度: {page_height}px")
            
            # 慢速滚动策略：分步滚动，每次滚动一小段距离
            scroll_step = 300  # 每次滚动300px
            current_position = 0
            scroll_count = 0
            
            while current_position < page_height:
                scroll_count += 1
                next_position = min(current_position + scroll_step, page_height)
                
                print(f"第 {scroll_count} 次滚动: {current_position}px → {next_position}px")
                
                # 滚动到下一个位置
                page.evaluate(f"window.scrollTo(0, {next_position})")
                
                # 等待内容加载
                time.sleep(1.5)
                
                # 检查是否有"加载更多"按钮并点击
                try:
                    load_more_selectors = [
                        'button:has-text("加载更多")',
                        'button:has-text("Load More")',
                        'button:has-text("查看更多")',
                        'button:has-text("显示更多")',
                        '.load-more',
                        '.load-more-btn',
                        '[data-testid="load-more"]',
                        '.ant-btn:has-text("加载更多")',
                        '.ant-btn:has-text("查看更多")'
                    ]
                    
                    for selector in load_more_selectors:
                        try:
                            load_more_btn = page.query_selector(selector)
                            if load_more_btn and load_more_btn.is_visible():
                                print(f"找到加载更多按钮，点击: {selector}")
                                load_more_btn.click()
                                time.sleep(2)
                                # 重新获取页面高度，因为可能加载了新内容
                                new_height = page.evaluate("document.body.scrollHeight")
                                if new_height > page_height:
                                    print(f"页面高度增加: {page_height}px → {new_height}px")
                                    page_height = new_height
                                break
                        except:
                            continue
                            
                except Exception as e:
                    print(f"检查加载更多按钮时出错: {e}")
                
                # 更新当前位置
                current_position = next_position
                
                # 每滚动10次检查一次页面高度是否有变化
                if scroll_count % 10 == 0:
                    new_height = page.evaluate("document.body.scrollHeight")
                    if new_height > page_height:
                        print(f"检测到页面高度变化: {page_height}px → {new_height}px")
                        page_height = new_height
            
            print(f"慢速滚动完成，总共滚动 {scroll_count} 次")
            
            # 滚动到顶部
            print("滚动到页面顶部...")
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(2)
            
            # 再次慢速滚动到底部确保所有内容都加载
            print("再次慢速滚动到底部确保所有内容加载...")
            final_height = page.evaluate("document.body.scrollHeight")
            if final_height > page_height:
                print(f"最终页面高度: {final_height}px")
                page_height = final_height
            
            # 最终滚动到底部
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            
        else:  # simple strategy
            print("执行简单滚动策略...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(2)

        # 从target_url中提取数字作为文件名
        import re
        url_number = re.search(r'/(\d+)$', target_url)
        if url_number:
            file_number = url_number.group(1)
        else:
            # 如果没有找到数字，使用时间戳
            file_number = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 创建influencer文件夹（如果不存在）
        influencer_dir = "influencer"
        if not os.path.exists(influencer_dir):
            os.makedirs(influencer_dir)
            print(f"创建文件夹: {influencer_dir}")

        # 重组datalist数据：按field_type分组，只保留data字段
        datalist_by_field_type = {}
        if 'datalist' in all_responses:
            for response in all_responses['datalist']:
                field_type = response.get('field_type')
                if field_type and 'data' in response:
                    # 只保留data字段的内容
                    datalist_by_field_type[field_type] = response['data'].get('data', response['data'])

        # 替换原来的datalist数据
        all_responses['datalist'] = datalist_by_field_type

        # 对其他API类型也只保留data字段
        api_types_to_simplify = [
            'baseInfo', 'authorIndex', 'getStatInfo', 'fansPortrait',
            'labelList', 'videoList', 'videoStat', 'liveList', 'liveStat',
            'cargoStat', 'cargoSummary', 'categoryList', 'shopList',
            'goodsList', 'goodsFilter', 'similarityList'
        ]

        for api_type in api_types_to_simplify:
            if api_type in all_responses and all_responses[api_type]:
                if isinstance(all_responses[api_type], list) and len(all_responses[api_type]) > 0:
                    # 取第一个响应的data字段
                    response = all_responses[api_type][0]
                    if 'data' in response:
                        all_responses[api_type] = response['data'].get('data', response['data'])

        # 创建合并的数据结构
        merged_data = {
            'target_url': target_url,
            'capture_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'total_requests': sum(len(responses) if isinstance(responses, list) else 1 for responses in all_responses.values()),
            'api_responses': all_responses
        }

        # 删除所有'show'字段
        merged_data_cleaned = remove_show_fields(merged_data)

        # 保存合并后的数据到influencer文件夹，只用数字命名
        merged_filename = os.path.join(influencer_dir, f"{file_number}.json")
        with open(merged_filename, 'w', encoding='utf-8') as f:
            json.dump(merged_data_cleaned, f, ensure_ascii=False, indent=2)
        
        print(f"所有API响应数据已合并保存到: {merged_filename}")
        
        # 显示统计信息
        total_captured = sum(len(responses) for responses in all_responses.values())
        print(f"总共捕获到 {total_captured} 个API请求")
        
        for api_type, responses in all_responses.items():
            if responses:
                print(f"  ✓ {api_type}: {len(responses)} 个请求")
            else:
                print(f"  ✗ {api_type}: 0 个请求")
        
        return all_responses
            
    except Exception as e:
        print(f"捕捉API响应时出错: {e}")
        return {}


if __name__ == "__main__":
    # 使用新的独立函数获取达人详细数据
    target_url = "https://www.fastmoss.com/zh/influencer/detail/7288986759428588590"
    
    # 调用独立函数
    result = get_influencer_data(target_url)
    
    # 检查结果
    if result:
        print(f"\n✅ 成功获取达人数据！")
        print(f"📊 总共捕获到 {result.get('total_requests', 0)} 个API请求")
        print(f"📁 数据已保存到: influencer/{target_url.split('/')[-1]}.json")
        
        # 显示API类型统计
        api_responses = result.get('api_responses', {})
        print(f"\n📈 API类型统计：")
        for api_type, responses in api_responses.items():
            if responses:
                print(f"  ✓ {api_type}: {len(responses)} 个请求")
            else:
                print(f"  ✗ {api_type}: 0 个请求")
    else:
        print(f"\n❌ 获取达人数据失败！")
        print("请检查URL是否正确或网络连接是否正常")


