"""
Playwright 爬虫 API 服务 (Async 版本)
使用 FastAPI + Playwright Async API
解决 LangChain 多线程调用 Playwright 的 greenlet 线程切换问题
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
from playwright.async_api import async_playwright, Error as PlaywrightError
import pandas as pd
import asyncio
import sys
import re
from datetime import datetime, timedelta
import os
import json

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

class ProcessInfluencerListRequest(BaseModel):
    """处理达人列表的请求参数"""
    json_file_path: str = Field(..., description="导出的 JSON 文件路径")
    cache_days: int = Field(3, ge=1, le=30, description="缓存有效天数（1-30天，默认3天）")

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
        # 使用 127.0.0.1 而不是 localhost 避免 IPv6 解析问题
        _browser = await _playwright.chromium.connect_over_cdp("http://127.0.0.1:9224")
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

def check_influencer_cache(influencer_id: str, cache_days: int) -> Optional[str]:
    """
    检查达人缓存是否存在且有效

    Args:
        influencer_id: 达人 ID (data-row-key)
        cache_days: 缓存有效天数

    Returns:
        Optional[str]: 有效缓存文件路径，如果缓存不存在或已过期则返回 None
    """
    influencer_dir = "influencer"
    filepath = os.path.join(influencer_dir, f"{influencer_id}.json")

    # 检查文件是否存在
    if not os.path.exists(filepath):
        return None

    try:
        # 读取文件
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 获取 capture_time 字段
        capture_time_str = data.get("capture_time")
        if not capture_time_str:
            print(f"   ⚠️ 缓存文件缺少 capture_time 字段: {filepath}")
            return None

        # 解析时间（格式：2025-11-03 12:46:08）
        capture_time = datetime.strptime(capture_time_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()

        # 计算时间差
        days_diff = (now - capture_time).days

        if days_diff <= cache_days:
            # 缓存有效
            return filepath
        else:
            # 缓存过期
            print(f"   ⏰ 缓存已过期 ({days_diff} 天前): {filepath}")
            return None

    except json.JSONDecodeError:
        print(f"   ❌ 缓存文件格式错误: {filepath}")
        return None
    except ValueError as e:
        print(f"   ❌ 时间格式解析失败: {e}")
        return None
    except Exception as e:
        print(f"   ❌ 读取缓存文件出错: {e}")
        return None

def remove_show_fields(obj):
    """
    递归移除所有包含 'show' 的键（不区分大小写）

    Args:
        obj: 要处理的对象（dict, list, 或其他类型）

    Returns:
        处理后的对象
    """
    if isinstance(obj, dict):
        return {
            k: remove_show_fields(v)
            for k, v in obj.items()
            if 'show' not in k.lower()
        }
    elif isinstance(obj, list):
        return [remove_show_fields(item) for item in obj]
    else:
        return obj

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
            # 使用 domcontentloaded 替代 networkidle，更可靠
            await _page.goto(req.url, wait_until="domcontentloaded", timeout=30000)
            # 等待表格容器出现
            try:
                await _page.wait_for_selector('.ant-table-container', timeout=10000)
            except:
                print("   ⚠️ 未检测到表格容器，继续执行...")
            await asyncio.sleep(2)
        else:
            await _page.goto(req.url, timeout=30000)
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
    爬取多个 URL 的达人数据,提取 data-row-key 并保存到 JSON 文件 (Async)

    支持多个排序维度的 URL,自动合并数据并去重,最终保存为 JSON 文件。
    """
    check_initialized()

    try:
        print(f"📊 开始爬取数据...")
        print(f"   - URL 数量: {len(req.urls)}")
        print(f"   - 每个 URL 最多爬取: {req.max_pages} 页")
        print(f"   - 商品名称: {req.product_name}")

        # 存储所有爬取的 data-row-key
        all_row_keys = []

        # 依次爬取每个 URL
        for idx, url in enumerate(req.urls, 1):
            print(f"\n🔄 正在爬取第 {idx}/{len(req.urls)} 个 URL...")
            print(f"   URL: {url}")

            row_keys = await get_data_row_keys(url=url, max_pages=req.max_pages)

            if row_keys:
                all_row_keys.extend(row_keys)
                print(f"   ✅ 爬取成功: {len(row_keys)} 个 data-row-key")
            else:
                print(f"   ⚠️ 该 URL 未获取到数据,跳过")

        # 检查是否有数据
        if not all_row_keys:
            raise HTTPException(status_code=404, detail="所有 URL 均未能爬取到数据")

        # 去重
        print(f"\n🔗 正在去重...")
        print(f"   去重前总数: {len(all_row_keys)} 个")
        unique_row_keys = list(dict.fromkeys(all_row_keys))  # 保持顺序去重
        print(f"   去重后总数: {len(unique_row_keys)} 个")

        # 创建 output 目录
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tiktok_达人推荐_{req.product_name}_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        # 导出 JSON
        print(f"\n💾 正在导出 JSON...")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "product_name": req.product_name,
                "timestamp": timestamp,
                "total_count": len(unique_row_keys),
                "data_row_keys": unique_row_keys
            }, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 导出成功: {filepath}")

        return {
            "success": True,
            "filepath": filepath,
            "total_rows": len(unique_row_keys),
            "source_count": len(req.urls),
            "scraped_count": len(req.urls),
            "message": f"成功导出 {len(unique_row_keys)} 个达人 data-row-key 到 {filename}"
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

@app.post("/process_influencer_list")
async def process_influencer_list_endpoint(req: ProcessInfluencerListRequest):
    """
    批量处理导出的 JSON 文件，获取达人详细数据 (Async)

    根据 JSON 文件中的 data_row_keys 列表，批量获取达人详细信息。
    自动检查本地缓存（influencer 目录），跳过未过期的数据，
    只爬取缺失或过期的达人详情。

    功能特性：
    - 智能缓存：自动检查 capture_time，跳过未过期数据
    - 顺序处理：逐个爬取，避免触发反爬机制
    - 容错机制：单个失败不影响整体流程
    - 详细统计：返回缓存/获取/失败的数量和具体 ID

    参数：
    - json_file_path: 导出的 JSON 文件路径（如 output/tiktok_达人推荐_女士香水_20251104_165214.json）
    - cache_days: 缓存有效天数（1-30天，默认3天）

    返回：
    - total_count: 总达人数
    - cached_count: 使用缓存的数量
    - fetched_count: 重新获取的数量
    - failed_count: 失败的数量
    - failed_ids: 失败的达人 ID 列表
    - elapsed_time: 处理耗时
    """
    check_initialized()

    try:
        print(f"\n📊 收到批量处理请求...")
        print(f"   - 文件: {req.json_file_path}")
        print(f"   - 缓存有效期: {req.cache_days} 天")

        # 验证文件存在
        if not os.path.exists(req.json_file_path):
            raise HTTPException(status_code=404, detail=f"文件不存在: {req.json_file_path}")

        # 调用批量处理函数
        result = await process_influencer_list_async(
            json_file_path=req.json_file_path,
            cache_days=req.cache_days
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message", "处理失败"))

        return result

    except HTTPException:
        raise
    except PlaywrightError as e:
        error_msg = f"Playwright 错误: {str(e)}"
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"批量处理失败: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_msg)

@app.get("/process_influencer_list_stream")
async def process_influencer_list_stream_endpoint(
    json_file_path: str,
    cache_days: int = 3
):
    """
    流式批量处理导出的 JSON 文件，获取达人详细数据 (SSE)

    使用 Server-Sent Events 实时推送处理进度
    """
    check_initialized()

    async def generate():
        """SSE 事件生成器"""
        try:
            # 读取 JSON 文件
            if not os.path.exists(json_file_path):
                yield f"data: {json.dumps({'type': 'error', 'message': f'文件不存在: {json_file_path}'})}\n\n"
                return

            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            data_row_keys = data.get("data_row_keys", [])
            product_name = data.get("product_name", "未知商品")
            total_count = len(data_row_keys)

            if total_count == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'JSON 文件中没有达人数据'})}\n\n"
                return

            # 发送初始化事件
            yield f"data: {json.dumps({'type': 'init', 'total': total_count, 'product_name': product_name})}\n\n"

            # 统计信息
            cached_count = 0
            fetched_count = 0
            failed_count = 0
            failed_ids = []

            start_time = datetime.now()

            # ⭐ 新增：专门统计实际请求的耗时
            api_request_time = 0.0  # 只统计实际 API 请求的总耗时
            api_request_count = 0   # 实际 API 请求的次数

            # 创建 influencer 目录
            influencer_dir = "influencer"
            os.makedirs(influencer_dir, exist_ok=True)

            # 遍历每个达人
            for idx, influencer_id in enumerate(data_row_keys, 1):
                # 检查缓存
                cached_path = check_influencer_cache(influencer_id, cache_days)
                if cached_path:
                    cached_count += 1
                else:
                    # 重新爬取
                    request_start = datetime.now()  # ⭐ 记录单次请求开始时间
                    try:
                        result = await fetch_influencer_detail_async(influencer_id)
                        if result["success"]:
                            fetched_count += 1
                            api_request_count += 1
                            # ⭐ 累计实际请求耗时
                            api_request_time += (datetime.now() - request_start).total_seconds()
                        else:
                            failed_ids.append(influencer_id)
                            failed_count += 1
                    except Exception as e:
                        failed_ids.append(influencer_id)
                        failed_count += 1

                    # 间隔延迟
                    if idx < total_count:
                        await asyncio.sleep(2)

                # 计算预估剩余时间
                elapsed = (datetime.now() - start_time).total_seconds()

                # ⭐ 使用实际请求的平均耗时计算剩余时间
                if api_request_count > 0:
                    avg_request_time = api_request_time / api_request_count
                    remaining_uncached = total_count - idx - (cached_count * (total_count - idx) // idx if idx > 0 else 0)
                    # 更准确的方式：假设剩余达人的缓存比例和已处理的一样
                    remaining_total = total_count - idx
                    estimated_cache_ratio = cached_count / idx if idx > 0 else 0
                    remaining_requests = int(remaining_total * (1 - estimated_cache_ratio))
                    estimated_remaining_seconds = int(remaining_requests * avg_request_time)
                else:
                    # 如果还没有实际请求，无法估算
                    estimated_remaining_seconds = None

                # 推送进度事件
                yield f"data: {json.dumps({
                    'type': 'progress',
                    'current': idx,
                    'total': total_count,
                    'success': fetched_count,
                    'cached': cached_count,
                    'failed': failed_count,
                    'elapsed_seconds': int(elapsed),
                    'estimated_remaining_seconds': estimated_remaining_seconds,  # ⭐ 新增字段
                    'avg_request_time': round(api_request_time / api_request_count, 1) if api_request_count > 0 else None  # ⭐ 平均请求时间
                })}\n\n"

            # 计算总耗时
            end_time = datetime.now()
            elapsed_time = end_time - start_time
            elapsed_str = str(elapsed_time).split('.')[0]

            # 发送完成事件
            yield f"data: {json.dumps({
                'type': 'complete',
                'stats': {
                    'total': total_count,
                    'success': fetched_count,
                    'cached': cached_count,
                    'failed': failed_count,
                    'elapsed_time': elapsed_str,
                    'failed_ids': failed_ids
                }
            })}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': f'处理失败: {str(e)}'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )

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


async def process_influencer_list_async(json_file_path: str, cache_days: int) -> Dict[str, Any]:
    """
    批量处理导出的 JSON 文件，获取达人详细数据

    Args:
        json_file_path: 导出的 JSON 文件路径
        cache_days: 缓存有效天数

    Returns:
        Dict: 包含处理统计信息的结果字典
    """
    try:
        print(f"📊 开始批量处理达人列表...")
        print(f"   - 文件路径: {json_file_path}")
        print(f"   - 缓存有效期: {cache_days} 天")

        # 读取 JSON 文件
        if not os.path.exists(json_file_path):
            return {
                "success": False,
                "message": f"文件不存在: {json_file_path}"
            }

        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        data_row_keys = data.get("data_row_keys", [])
        product_name = data.get("product_name", "未知商品")
        total_count = len(data_row_keys)

        if total_count == 0:
            return {
                "success": False,
                "message": "JSON 文件中没有 data-row-keys"
            }

        print(f"   - 商品名称: {product_name}")
        print(f"   - 达人总数: {total_count}")
        print()

        # 统计信息
        cached_count = 0
        fetched_count = 0
        failed_count = 0
        failed_ids = []

        start_time = datetime.now()

        # 创建 influencer 目录（如不存在）
        influencer_dir = "influencer"
        os.makedirs(influencer_dir, exist_ok=True)

        # 遍历每个 data-row-key（顺序处理）
        for idx, influencer_id in enumerate(data_row_keys, 1):
            print(f"[{idx}/{total_count}] 处理达人 ID: {influencer_id}")

            # 检查缓存
            cached_path = check_influencer_cache(influencer_id, cache_days)
            if cached_path:
                print(f"   ✓ 使用缓存: {cached_path}")
                cached_count += 1
                continue

            # 重新爬取
            try:
                result = await fetch_influencer_detail_async(influencer_id)
                if result["success"]:
                    fetched_count += 1
                    print(f"   ✅ 成功获取并保存")
                else:
                    failed_ids.append(influencer_id)
                    failed_count += 1
                    print(f"   ❌ 失败: {result['message']}")
            except Exception as e:
                print(f"   ❌ 异常: {e}")
                failed_ids.append(influencer_id)
                failed_count += 1

            # 间隔延迟（避免频繁请求，防止反爬）
            if idx < total_count:  # 不是最后一个才延迟
                await asyncio.sleep(2)

        end_time = datetime.now()
        elapsed_time = end_time - start_time
        elapsed_str = str(elapsed_time).split('.')[0]  # 去掉微秒

        print()
        print(f"✅ 批量处理完成!")
        print(f"   - 总数: {total_count}")
        print(f"   - 使用缓存: {cached_count}")
        print(f"   - 重新获取: {fetched_count}")
        print(f"   - 失败: {failed_count}")
        print(f"   - 耗时: {elapsed_str}")

        return {
            "success": True,
            "total_count": total_count,
            "cached_count": cached_count,
            "fetched_count": fetched_count,
            "failed_count": failed_count,
            "failed_ids": failed_ids,
            "elapsed_time": elapsed_str,
            "message": f"处理完成：{cached_count} 个使用缓存，{fetched_count} 个重新获取，{failed_count} 个失败"
        }

    except json.JSONDecodeError:
        return {
            "success": False,
            "message": f"JSON 文件格式错误: {json_file_path}"
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"批量处理失败: {str(e)}"
        }


async def fetch_influencer_detail_async(influencer_id: str) -> Dict[str, Any]:
    """
    异步获取单个达人的详细数据

    Args:
        influencer_id: 达人 ID (data-row-key)

    Returns:
        Dict: 包含 success 和 message 的结果字典
    """
    try:
        # 构建详情页 URL
        target_url = f"https://www.fastmoss.com/zh/influencer/detail/{influencer_id}"
        print(f"   🌐 正在访问达人详情页: {target_url}")

        # 定义所有支持的API类型
        api_types = [
            'datalist', 'baseInfo', 'authorIndex', 'getStatInfo',
            'fansPortrait', 'labelList', 'cargoStat', 'cargoSummary', 'authorContact'
        ]

        # 存储所有响应数据，按类型分组
        all_responses = {api_type: [] for api_type in api_types}

        # 跟踪只需要保存一次的API类型
        captured_once = {'baseInfo': False, 'authorIndex': False, 'getStatInfo': False, 'categoryList': False, 'authorContact': False}

        async def handle_response(response):
            """处理响应事件（异步版本）"""
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
                elif api_type == 'cargoStat' and 'cargoStat' in url:
                    matched_type = 'cargoStat'
                    break
                elif api_type == 'cargoSummary' and 'cargoSummary' in url:
                    matched_type = 'cargoSummary'
                    break
                elif api_type == 'authorContact' and 'authorContact' in url:
                    matched_type = 'authorContact'
                    break

            if matched_type:
                # 对于baseInfo、authorIndex、getStatInfo、categoryList，如果已经捕获过一次就跳过
                if matched_type in captured_once:
                    if captured_once[matched_type]:
                        return
                    else:
                        captured_once[matched_type] = True

                # 过滤date_type=28的请求
                if matched_type in ['datalist', 'fansPortrait']:
                    if 'date_type=28' in url:
                        return

                response_info = {
                    'url': url,
                    'status': response.status,
                    'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S"),
                    'api_type': matched_type
                }

                try:
                    if response.status == 200:
                        data = await response.json()
                        response_info['data'] = data

                        # 提取URL参数
                        from urllib.parse import urlparse, parse_qs
                        parsed_url = urlparse(url)
                        query_params = parse_qs(parsed_url.query)

                        # 根据API类型提取特定参数
                        common_params = ['uid', 'id', 'author_id', 'page', 'size', 'limit', 'offset']
                        for param in common_params:
                            if param in query_params:
                                response_info[param] = query_params[param][0]

                        # 对于datalist类型，额外提取field_type参数
                        if matched_type == 'datalist':
                            field_type = query_params.get('field_type', [''])[0]
                            if field_type:
                                response_info['field_type'] = field_type

                    else:
                        response_info['error'] = f"HTTP {response.status}"

                except Exception as e:
                    response_info['error'] = str(e)
                    try:
                        text_data = await response.text()
                        response_info['text'] = text_data
                    except:
                        pass

                all_responses[matched_type].append(response_info)

        # 设置响应监听器
        _page.on("response", handle_response)

        # 访问目标网页（使用 domcontentloaded，更稳定）
        await _page.goto(target_url, wait_until="domcontentloaded", timeout=30000)

        # 等待页面稳定
        await asyncio.sleep(2)

        # 分段滚动策略：逐步触发各区域的懒加载
        # 滚动5次，每次滚动页面高度的20%，确保所有区域都被访问到
        for i in range(5):
            scroll_position = f"window.scrollTo(0, document.body.scrollHeight * {(i + 1) * 0.2})"
            await _page.evaluate(scroll_position)
            await asyncio.sleep(1)  # 等待该区域的 API 请求触发

        # 点击近90天选项
        try:
            ninety_days_button = await _page.query_selector("label.ant-radio-button-wrapper:has-text('近90天')")
            if ninety_days_button:
                await ninety_days_button.click()
                await asyncio.sleep(1.5)  # 等待近90天数据加载
        except:
            pass

        # 下拉菜单处理函数
        async def process_dropdown_menu(section_name, index):
            """处理下拉菜单，点击所有选项以触发API请求"""
            try:
                # 查找下拉菜单选择器
                selector_div = await _page.query_selector(f'div.flex.justify-between.items-center:has-text("{section_name}") div.ant-select-selector')
                if not selector_div:
                    return

                # 点击展开
                await selector_div.click()
                await asyncio.sleep(0.5)

                # 获取下拉选项
                dropdown_holder = _page.locator('div.rc-virtual-list-holder-inner').nth(index)
                child_divs = await dropdown_holder.locator('> div').all()
                total_divs = len(child_divs)

                # 点击所有选项以触发所有 API 请求
                for i in range(total_divs):
                    try:
                        await child_divs[i].click()
                        await asyncio.sleep(1.5)  # 等待API响应

                        # 重新打开下拉菜单（如果不是最后一个）
                        if i < total_divs - 1:
                            await selector_div.click()
                            await asyncio.sleep(0.3)
                            # 重新获取选项列表（DOM可能更新）
                            child_divs = await dropdown_holder.locator('> div').all()
                    except Exception as e:
                        print(f"   ⚠️ 点击第{i+1}个选项时出错: {e}")
                        continue

            except Exception as e:
                print(f"   ⚠️ 处理{section_name}菜单时出错: {e}")

        # 处理两个下拉菜单
        await process_dropdown_menu("近期数据", 0)
        await process_dropdown_menu("带货数据", 1)

        # 最后再滚动到底部确保所有内容加载
        await _page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)

        # 重组datalist数据：按field_type分组，只保留data字段
        datalist_by_field_type = {}
        if 'datalist' in all_responses:
            for response in all_responses['datalist']:
                field_type = response.get('field_type')
                if field_type and 'data' in response:
                    datalist_by_field_type[field_type] = response['data'].get('data', response['data'])

        all_responses['datalist'] = datalist_by_field_type

        # 对其他API类型也只保留data字段
        api_types_to_simplify = [
            'baseInfo', 'authorIndex', 'getStatInfo', 'fansPortrait',
            'labelList', 'cargoStat', 'cargoSummary', 'authorContact'
        ]

        for api_type in api_types_to_simplify:
            if api_type in all_responses and all_responses[api_type]:
                if isinstance(all_responses[api_type], list) and len(all_responses[api_type]) > 0:
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

        # 保存到influencer文件夹
        influencer_dir = "influencer"
        os.makedirs(influencer_dir, exist_ok=True)

        merged_filename = os.path.join(influencer_dir, f"{influencer_id}.json")
        with open(merged_filename, 'w', encoding='utf-8') as f:
            json.dump(merged_data_cleaned, f, ensure_ascii=False, indent=2)

        print(f"   ✅ 达人数据已保存: {merged_filename}")

        # 移除响应监听器
        _page.remove_listener("response", handle_response)

        return {
            "success": True,
            "message": f"成功获取达人 {influencer_id} 的详细数据",
            "file_path": merged_filename
        }

    except Exception as e:
        print(f"   ❌ 获取达人详细数据失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"获取失败: {str(e)}"
        }


async def get_data_row_keys(url: str, max_pages: int) -> List[str]:
    """
    循环获取多页的 data-row-key 属性值

    Args:
        url (str): 要爬取的起始 URL
        max_pages (int): 最大爬取页数

    Returns:
        List[str]: data-row-key 列表，如果失败则返回空列表
    """
    try:
        # 导航到指定 URL
        print(f"🌐 正在访问: {url}")
        await _page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 等待表格容器出现
        try:
            await _page.wait_for_selector('.ant-table-container', timeout=10000)
        except:
            print("   ⚠️ 未检测到表格容器")
        await asyncio.sleep(2)

        # 获取当前URL
        current_url = url

        # 检查URL中是否已有page参数
        if '&page=' in current_url:
            # 如果已有page参数，替换为page=1
            base_url = re.sub(r'&page=\d+', '', current_url)
        else:
            # 如果没有page参数，直接使用当前URL
            base_url = current_url

        # 汇总所有页面的 data-row-key
        all_row_keys = []

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
            await _page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            # 等待表格出现
            try:
                await _page.wait_for_selector('.ant-table-container', timeout=5000)
            except:
                pass

            # 额外等待,确保页面完全加载
            await asyncio.sleep(1)

            # 滚动到页面底部以触发懒加载
            await _page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.5)

            # 查找class="ant-table-container"的元素
            table_container = await _page.query_selector('.ant-table-container')

            if not table_container:
                print(f"      ⚠️ 第 {page_num} 页未找到表格容器,停止爬取")
                break

            # 获取所有带有 data-row-key 属性的表格行
            rows = await table_container.query_selector_all('tr[data-row-key]')

            if not rows:
                print(f"      ⚠️ 第 {page_num} 页没有数据行,停止爬取")
                break

            # 提取当前页的 data-row-key
            page_row_keys = []
            for row in rows:
                row_key = await row.get_attribute('data-row-key')
                if row_key:
                    page_row_keys.append(row_key)

            # 如果当前页没有数据，说明已经到最后一页了
            if not page_row_keys:
                print(f"      ⚠️ 第 {page_num} 页没有有效数据,停止爬取")
                break

            # 检查是否与上一页数据重复
            if page_num > 1 and page_row_keys and all_row_keys:
                if page_row_keys[0] == all_row_keys[-1]:
                    print(f"      ⚠️ 警告: 第 {page_num} 页的数据与第 {page_num-1} 页重复!")
                    print(f"         重复的 data-row-key: {page_row_keys[0]}")

            # 将当前页数据添加到总数据中
            all_row_keys.extend(page_row_keys)
            print(f"      ✓ 本页获取 {len(page_row_keys)} 个 data-row-key,累计 {len(all_row_keys)} 个")

        print(f"\n📋 data-row-key 获取完成: 共 {len(all_row_keys)} 个")
        return all_row_keys

    except Exception as e:
        print(f"获取 data-row-key 时出错: {e}")
        import traceback
        traceback.print_exc()
        return []


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
        await _page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 等待表格容器出现
        try:
            await _page.wait_for_selector('.ant-table-container', timeout=10000)
        except:
            print("   ⚠️ 未检测到表格容器")
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
            await _page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            # 等待表格出现
            try:
                await _page.wait_for_selector('.ant-table-container', timeout=5000)
            except:
                pass

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
