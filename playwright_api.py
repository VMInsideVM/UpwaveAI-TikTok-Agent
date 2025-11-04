"""
Playwright 爬虫 API 服务 (Async 版本)
使用 FastAPI + Playwright Async API
解决 LangChain 多线程调用 Playwright 的 greenlet 线程切换问题
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
from playwright.async_api import async_playwright, Error as PlaywrightError
import pandas as pd
import asyncio
import sys
import re
from datetime import datetime
import os

# 导入路径设置
sys.path.insert(0, '.')

app = FastAPI(
    title="TikTok Influencer Scraping API (Async)",
    description="使用 Playwright Async API 将爬虫操作封装为 RESTful API",
    version="2.0.0"
)

# ============================================================================
# 全局变量：Playwright 实例
# ============================================================================
_playwright = None
_browser = None
_context = None
_page = None
_is_initialized = False

# ============================================================================
# Pydantic 模型定义
# ============================================================================

class NavigateRequest(BaseModel):
    """导航请求"""
    url: str = Field(..., description="要访问的 URL")
    wait_for_load: bool = Field(True, description="是否等待页面完全加载（networkidle）")

class ScrapeRequest(BaseModel):
    """爬取请求"""
    urls: List[str] = Field(..., description="搜索页面 URL 列表(支持多个排序维度)")
    max_pages: int = Field(..., ge=1, le=100, description="每个 URL 的最大爬取页数（1-100）")
    product_name: str = Field(..., description="商品名称(用于文件命名)")

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    playwright_initialized: bool
    message: str

# ============================================================================
# 生命周期管理
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """API 启动时初始化 Playwright (Async)"""
    global _playwright, _browser, _context, _page, _is_initialized

    try:
        print("🔧 正在初始化 Playwright API 服务 (Async 模式)...")

        # 启动 Playwright (异步 API)
        _playwright = await async_playwright().start()
        print("  ✓ Playwright 异步实例已创建")

        # 连接到现有的 Chrome 实例（CDP 端口 9224）
        _browser = await _playwright.chromium.connect_over_cdp("http://localhost:9224")
        print("  ✓ 已连接到 Chrome (CDP:9224)")

        # 获取浏览器上下文和页面
        _context = _browser.contexts[0]
        _page = _context.pages[0]
        print("  ✓ 已获取浏览器页面")

        _is_initialized = True
        print("✅ Playwright API 服务启动成功！(Async 模式)")
        print("📡 API 文档: http://127.0.0.1:8000/docs")

    except Exception as e:
        print(f"❌ Playwright 初始化失败: {e}")
        print("请确保:")
        print("  1. Chrome 浏览器已启动")
        print("  2. CDP 端口 9224 已开放")
        print("  3. 使用命令: chrome.exe --remote-debugging-port=9224")
        _is_initialized = False
        import traceback
        traceback.print_exc()

@app.on_event("shutdown")
async def shutdown_event():
    """API 关闭时清理资源"""
    global _playwright, _browser, _is_initialized

    print("\n🔧 正在关闭 Playwright API 服务...")

    try:
        if _browser:
            await _browser.close()
            print("  ✓ 浏览器连接已关闭")

        if _playwright:
            await _playwright.stop()
            print("  ✓ Playwright 实例已停止")

        _is_initialized = False
        print("✅ Playwright API 服务已安全关闭")

    except Exception as e:
        print(f"⚠️ 关闭时出现警告: {e}")

# ============================================================================
# 辅助函数
# ============================================================================

def check_initialized():
    """检查 Playwright 是否已初始化"""
    if not _is_initialized or _page is None:
        raise HTTPException(
            status_code=503,
            detail="Playwright 未初始化。请检查服务启动日志。"
        )

# ============================================================================
# API 端点
# ============================================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """根路径 - 健康检查"""
    return {
        "status": "running",
        "playwright_initialized": _is_initialized,
        "message": "Playwright API 服务正在运行 (Async 模式)。访问 /docs 查看 API 文档。"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy" if _is_initialized else "unhealthy",
        "playwright_initialized": _is_initialized,
        "message": "服务正常" if _is_initialized else "Playwright 未初始化"
    }

@app.post("/navigate")
async def navigate(req: NavigateRequest):
    """
    导航到指定 URL (Async)

    此端点执行页面导航操作，支持等待页面加载完成。
    """
    check_initialized()

    try:
        print(f"🌐 正在访问: {req.url}")

        if req.wait_for_load:
            await _page.goto(req.url, wait_until="networkidle", timeout=60000)
        else:
            await _page.goto(req.url, timeout=30000)

        # 等待表格加载
        await asyncio.sleep(2)

        print(f"✅ 访问成功: {req.url}")

        return {
            "success": True,
            "url": req.url,
            "message": "页面导航成功"
        }

    except PlaywrightError as e:
        error_msg = f"Playwright 错误: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    except Exception as e:
        error_msg = f"导航失败: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/max_page")
async def get_max_page():
    """
    获取当前页面的最大页数 (Async)

    从分页控件中提取最大页码。必须先调用 /navigate 导航到搜索页面。
    """
    check_initialized()

    try:
        print("📊 正在获取最大页数...")

        # 使用异步方式获取最大页数
        max_page = await get_max_page_number_async()

        estimated_count = max_page * 10

        print(f"✅ 最大页数: {max_page}, 预计约 {estimated_count} 个达人")

        return {
            "success": True,
            "max_page": max_page,
            "estimated_count": estimated_count,
            "message": f"最大页数: {max_page}"
        }

    except Exception as e:
        error_msg = f"获取最大页数失败: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/scrape")
async def scrape_pages(req: ScrapeRequest):
    """
    爬取多个 URL 的达人数据,合并去重后导出为 Excel 文件 (Async)

    支持多个排序维度的 URL,自动合并数据并去重,最终导出为单个 Excel 文件。
    """
    check_initialized()

    try:
        print(f"📊 开始爬取数据...")
        print(f"   - URL 数量: {len(req.urls)}")
        print(f"   - 每个 URL 最多爬取: {req.max_pages} 页")
        print(f"   - 商品名称: {req.product_name}")

        # 存储所有爬取的 DataFrame
        all_dataframes = []

        # 依次爬取每个 URL
        for idx, url in enumerate(req.urls, 1):
            print(f"\n🔄 正在爬取第 {idx}/{len(req.urls)} 个 URL...")
            print(f"   URL: {url}")

            df = await get_table_data_as_dataframe(url=url, max_pages=req.max_pages)

            if df is not None and not df.empty:
                all_dataframes.append(df)
                print(f"   ✅ 爬取成功: {len(df)} 条数据")
            else:
                print(f"   ⚠️ 该 URL 未获取到数据,跳过")

        # 检查是否有数据
        if not all_dataframes:
            raise HTTPException(status_code=404, detail="所有 URL 均未能爬取到数据")

        # 合并所有 DataFrame
        print(f"\n🔗 正在合并数据...")
        if len(all_dataframes) == 1:
            final_df = all_dataframes[0]
            print(f"   只有一个数据源,无需合并")
        else:
            # 检查所有 DataFrame 的列是否一致
            first_columns = list(all_dataframes[0].columns)

            # 对齐所有 DataFrame 的列顺序
            aligned_dataframes = [all_dataframes[0]]
            for idx, df in enumerate(all_dataframes[1:], 2):
                if list(df.columns) != first_columns:
                    print(f"   ⚠️ 警告: 第 {idx} 个 DataFrame 的列名与第一个不一致")
                    print(f"      第1个列: {first_columns[:3]}...")
                    print(f"      第{idx}个列: {list(df.columns)[:3]}...")
                    # 只保留共同的列,并按第一个 DataFrame 的顺序排列
                    common_cols = [col for col in first_columns if col in df.columns]
                    aligned_dataframes.append(df[common_cols])
                else:
                    aligned_dataframes.append(df)

            # 使用 concat 合并,忽略索引
            final_df = pd.concat(aligned_dataframes, ignore_index=True)
            print(f"   合并前总数: {len(final_df)} 条")

            # 去重(根据第一列,通常是 data-row-key)
            if len(final_df.columns) > 0:
                first_column = final_df.columns[0]
                final_df = final_df.drop_duplicates(subset=[first_column], keep='first')
                print(f"   去重后总数: {len(final_df)} 条")

        # 创建 output 目录
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tiktok_达人推荐_{req.product_name}_{timestamp}.xlsx"
        filepath = os.path.join(output_dir, filename)

        # 导出 Excel
        print(f"\n💾 正在导出 Excel...")
        final_df.to_excel(filepath, index=False, engine='openpyxl')
        print(f"   ✅ 导出成功: {filepath}")

        return {
            "success": True,
            "filepath": filepath,
            "total_rows": len(final_df),
            "source_count": len(req.urls),
            "scraped_count": len(all_dataframes),
            "message": f"成功导出 {len(final_df)} 个达人数据到 {filename}"
        }

    except PlaywrightError as e:
        error_msg = f"Playwright 错误: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    except Exception as e:
        error_msg = f"爬取失败: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/current_url")
async def get_current_url():
    """获取当前页面的 URL"""
    check_initialized()

    try:
        current_url = _page.url
        return {
            "success": True,
            "url": current_url,
            "message": "当前 URL"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# 异步爬取函数（从 main.py 移植）
# ============================================================================

async def get_max_page_number_async() -> int:
    """
    异步获取搜索结果的最大页数

    Returns:
        int: 最大页数，如果获取失败返回 1
    """
    try:
        # 滚动到页面底部以确保分页元素加载
        await _page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        # 等待分页元素出现
        pagination_selector = '.ant-pagination.ant-table-pagination.ant-table-pagination-right'

        try:
            await _page.wait_for_selector(pagination_selector, timeout=5000)
        except:
            print("⚠️ 未找到分页元素，可能只有一页数据")
            return 1

        # 获取所有li元素（修复：使用 _page 而不是 pagination_selector）
        li_elements = await _page.query_selector_all(f'{pagination_selector} li')

        if not li_elements:
            # 静默处理未找到
            return 1

        max_page = 0

        # 遍历所有li元素，提取数值
        for li in li_elements:
            # 获取li元素的文本内容（修复：添加 await）
            text = await li.inner_text()
            text = text.strip()

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
        print(f"获取最大页数时出错: {e}")
        return 1


async def get_table_data_as_dataframe(url, max_pages=None):
    """
    循环获取多页表格数据并返回DataFrame（不写文件）

    Args:
        url (str): 要爬取的起始 URL
        max_pages (int, optional): 最大页数，如果不指定则自动获取实际最大页码

    Returns:
        pd.DataFrame: 处理后的数据，如果失败则返回None
    """
    try:
        # 导航到指定 URL
        print(f"🌐 正在访问: {url}")
        await _page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)

        # 如果没有指定max_pages，则自动获取实际最大页码
        if max_pages is None:
            max_pages = await get_max_page_number_async()

        # 获取当前URL
        current_url = url

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

            print(f"   📄 正在爬取第 {page_num}/{max_pages} 页...")
            if page_num <= 2:  # 只打印前两页的完整 URL
                print(f"      URL: {page_url}")

            # 导航到当前页
            await _page.goto(page_url, wait_until="networkidle", timeout=60000)

            # 额外等待,确保页面完全加载
            await asyncio.sleep(1)

            # 滚动到页面底部以触发懒加载
            await _page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.5)

            # 查找class="ant-table-container"的元素
            table_container = await _page.query_selector('.ant-table-container')

            if not table_container:
                break

            # 获取表格行
            rows = await table_container.query_selector_all('tr')
            if not rows:
                break

            # 提取当前页的表格数据
            page_data = []

            for i, row in enumerate(rows):
                # 获取行中的单元格
                cells = await row.query_selector_all('td, th')
                row_data = []

                for cell in cells:
                    cell_text = await cell.inner_text()
                    row_data.append(cell_text.strip())

                if row_data:  # 只添加非空行
                    # 获取data-row-key属性
                    row_key = await row.get_attribute('data-row-key')

                    # 检查是否是表头行（没有data-row-key属性）
                    if not row_key:
                        if page_num == 1:  # 只在第一页时保存表头
                            # 只在第一次遇到表头时保存(避免重复)
                            if not headers:
                                headers = row_data.copy()  # 使用 copy 避免引用问题
                                # 为表头添加data-row-key列名
                                if len(headers) > 0:
                                    headers.append('data-row-key')
                                print(f"      ✓ 提取表头: {len(headers)} 列")
                                print(f"         前5列: {headers[:5]}")
                        # 跳过所有页面的表头行，不添加到page_data中
                        continue
                    else:
                        # 这是数据行，添加data-row-key
                        row_data.append(row_key)
                        page_data.append(row_data)

            # 如果当前页没有数据，说明已经到最后一页了
            if not page_data:
                print(f"      ⚠️ 第 {page_num} 页没有数据,停止爬取")
                break

            # 检查是否与上一页数据重复(用于调试)
            if page_num > 1 and page_data:
                # 比较第一条数据的 data-row-key
                current_first_key = page_data[0][-1] if page_data[0] else None
                previous_first_key = all_data[-1][-1] if all_data else None
                if current_first_key and current_first_key == previous_first_key:
                    print(f"      ⚠️ 警告: 第 {page_num} 页的数据与第 {page_num-1} 页重复!")
                    print(f"         重复的 data-row-key: {current_first_key}")

            # 将当前页数据添加到总数据中
            all_data.extend(page_data)
            total_rows += len(page_data)
            print(f"      ✓ 本页获取 {len(page_data)} 条数据,累计 {total_rows} 条")

        # 如果没有获取到任何数据，返回None
        if not all_data:
            return None

        # 创建DataFrame
        print(f"\n📋 正在创建 DataFrame...")
        print(f"   表头数量: {len(headers)}")
        print(f"   表头: {headers[:5]}..." if len(headers) > 5 else f"   表头: {headers}")
        print(f"   数据行数: {len(all_data)}")
        if all_data:
            print(f"   每行数据长度: {len(all_data[0])}")

        # 检查表头是否有重复
        if len(headers) != len(set(headers)):
            print(f"   ⚠️ 警告: 表头中有重复的列名!")
            from collections import Counter
            duplicates = [name for name, count in Counter(headers).items() if count > 1]
            print(f"   重复的列名: {duplicates}")

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




# ============================================================================
# 启动服务
# ============================================================================

def main():
    """启动 API 服务"""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║      🚀 Playwright Scraping API Service (Async) 🚀           ║
║                                                               ║
║      使用 Playwright Async API                                ║
║      解决 LangChain 多线程 greenlet 问题                      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    print("⚙️  配置:")
    print("   - Host: 127.0.0.1")
    print("   - Port: 8000")
    print("   - Mode: Async (异步模式)")
    print("   - Docs: http://127.0.0.1:8000/docs")
    print("   - Redoc: http://127.0.0.1:8000/redoc")
    print()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    main()
