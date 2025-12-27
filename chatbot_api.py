"""
TikTok 达人推荐聊天机器人 API 服务
提供基于 WebSocket 的实时聊天功能，支持多用户会话隔离
"""

import asyncio
import json
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
from datetime import datetime

from session_manager_db import session_manager  # 使用数据库版本
from agent import TikTokInfluencerAgent
from agent_wrapper import AgentProgressWrapper, clean_response, translate_tool_call
from response_validator import get_validator  # 导入工具调用追踪器
from services.token_tracker import TokenTrackingCallbackHandler  # 导入 Token 追踪器

# 导入认证相关
from database.connection import get_db, get_db_context
from database.models import User, ChatSession, Report
from auth.dependencies import get_current_user, get_optional_user
from fastapi import Depends, Query
from sqlalchemy.orm import Session as DBSession

# 导入新的 API 路由
from api.auth import router as auth_router
from api.reports import router as reports_router
from api.admin import router as admin_router
from api.admin_extensions import router as admin_ext_router
from api.appeals import router as appeals_router
from api.payment import router as payment_router
from api.admin_payment import router as admin_payment_router
from api.user_orders import router as user_orders_router

# 导入安全相关模块
from utils.security import content_moderator, get_client_ip, rate_limiter
from services.security_service import security_service
from config.pricing import MAX_ROUNDS_PER_SESSION, calculate_max_daily_conversations
from utils.timezone import today_start as get_today_start  # 东八区时间工具

# 创建 FastAPI 应用
app = FastAPI(
    title="TikTok 达人推荐聊天机器人",
    description="基于 LangChain Agent 的智能聊天服务",
    version="1.0.0"
)

# 配置 CORS（修复安全问题）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8001",
        "http://localhost:8001",
        # 生产环境添加实际域名
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(auth_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(admin_ext_router)  # 注册管理员扩展路由
app.include_router(appeals_router)  # 注册申诉路由
app.include_router(payment_router)  # 注册支付路由
app.include_router(admin_payment_router)  # 注册管理员支付路由
app.include_router(user_orders_router)  # 注册用户订单路由

# 挂载静态文件目录（用于提供前端页面）
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    print("⚠️ static 目录不存在，将在后续步骤创建")

# 挂载报告文件目录（用于托管生成的报告和图表）
import os
reports_dir = "output/reports"
if os.path.exists(reports_dir):
    app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")
    print(f"✅ 报告静态文件服务已启动: /reports -> {reports_dir}")
else:
    print(f"⚠️ 报告目录不存在，将在生成报告时创建: {reports_dir}")


# ==================== 辅助函数 ====================

def check_playwright_api() -> bool:
    """检查 Playwright API 服务是否可用"""
    try:
        response = requests.get("http://127.0.0.1:8000/health", timeout=3)
        return response.status_code == 200
    except:
        return False


async def stream_agent_response(agent: TikTokInfluencerAgent, user_input: str, websocket: WebSocket, image_data: Optional[str] = None, session_id: Optional[str] = None):
    """
    流式传输 agent 响应到 WebSocket
    包含进度更新、心跳保活和响应验证

    Args:
        agent: Agent 实例
        user_input: 用户文本输入
        websocket: WebSocket 连接
        image_data: Base64 编码的图片数据（可选）
        session_id: 会话 ID（可选）
    """
    try:
        # 获取工具调用追踪器实例
        validator = get_validator(debug=True)  # 启用调试模式

        # ⭐ 初始化 Token 追踪器
        if agent.user_id:
            token_handler = TokenTrackingCallbackHandler(
                user_id=agent.user_id,
                session_id=session_id
            )
            # 确保 agent.callbacks 已初始化
            if not hasattr(agent, 'callbacks') or agent.callbacks is None:
                agent.callbacks = []
            
            # 避免重复添加 (虽然 agent 默认是单例或缓存的，但 handler 需要是新的以免混淆 session?)
            # 其实 agent 是缓存的，但 handler 是针对单次调用的 context 吗？ 
            # Handler has session_id, so it should be fine.
            # But we should probably add it for this run.
            # Since we modify agent.callbacks which is persistent for the cached agent, we might accumulate handlers.
            # BETTER APPROACH: Pass callbacks to agent.run methods instead of setting on instance persistently.
            
            # Let's verify agent.run in agent.py
            # agent.run calls self.agent.invoke(..., config=config) where config uses self.callbacks.
            # If we append to self.callbacks, it persists.
            # We should probably set it temporarily or ensure uniqueness.
            
            # For now, let's just append and rely on the fact that if session_id changes, we might have multiple handlers?
            # Creating a new handler for each request seems correct for tracking per-request usage.
            # But if we keep appending to `agent.callbacks`, the list grows indefinitely!
            
            # Fix: We should probably replace callbacks or manage them better.
            # But `agent.py` uses `self.callbacks` in `__init__`. 
            # Let's set `agent.callbacks = [token_handler]` for this execution.
            # Since `stream_agent_response` handles one user request, setting it here is fine as long as concurrent requests don't overwrite each other (but agent is likely per-session/user, so concurrency on same agent instance is rare/handled by lock usually, though here it's asyncio).
            
            agent.callbacks = [token_handler]
        else:
            print("⚠️ Agent user_id 为空，无法追踪 Token")

        # 发送开始处理的消息
        await websocket.send_json({
            "type": "status",
            "content": "正在处理您的请求...",
            "timestamp": datetime.now().isoformat()
        })

        # 在后台线程中执行 agent
        loop = asyncio.get_event_loop()

        # 定时发送心跳，防止超时
        async def send_heartbeat():
            """定期发送心跳保持连接"""
            try:
                while True:
                    await asyncio.sleep(10)  # 每 10 秒发送一次心跳
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat()
                    })
            except:
                pass  # WebSocket 关闭时会抛出异常，忽略即可

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(send_heartbeat())

        # 创建进度追踪器
        last_progress_time = [0]  # 使用列表以便在内部函数中修改

        async def report_progress(msg: str):
            """报告进度消息"""
            import time
            current_time = time.time()
            # 限制进度更新频率（最多每 0.5 秒一次）
            if current_time - last_progress_time[0] < 0.5:
                return
            last_progress_time[0] = current_time

            try:
                await websocket.send_json({
                    "type": "status",
                    "content": msg,
                    "timestamp": datetime.now().isoformat()
                })
            except:
                pass  # 忽略发送失败

        # 使用进度包装器执行 agent
        def run_with_progress():
            """在进度包装器中运行 agent"""
            # 如果有图片，调用支持视觉输入的方法
            if image_data:
                return agent.run_with_image(user_input, image_data)
            else:
                return agent.run(user_input)

        try:
            # 定期报告"处理中"状态
            processing_messages = [
                "正在理解您的需求...",
                "正在分析参数...",
                "正在执行查询...",
                "正在处理数据...",
            ]
            current_msg_idx = [0]

            async def report_processing():
                """定期报告处理状态"""
                try:
                    while True:
                        await asyncio.sleep(5)  # 每 5 秒更新一次
                        msg = processing_messages[current_msg_idx[0] % len(processing_messages)]
                        current_msg_idx[0] += 1
                        await report_progress(msg)
                except:
                    pass

            # 启动处理状态报告任务
            processing_task = asyncio.create_task(report_processing())

            try:
                # ⭐ 执行 agent（同步调用）
                response = await loop.run_in_executor(None, run_with_progress)
            finally:
                # 取消处理状态任务
                processing_task.cancel()
                try:
                    await processing_task
                except asyncio.CancelledError:
                    pass
        finally:
            # 取消心跳任务
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        # 清理响应内容（隐藏品牌相关字样）
        if response:
            response = clean_response(response)

            # 检查是否需要用户确认生成报告
            needs_confirmation = any(keyword in response for keyword in [
                "请输入【确认】开始搜索",
                "输入【确认】",
                '请输入"确认"',
                "confirm"
            ]) or "confirm" in response.lower()

            # 发送开始标记，告诉前端开始新消息
            await websocket.send_json({
                "type": "message_start",
                "timestamp": datetime.now().isoformat()
            })

            # 逐字符流式发送（模拟打字效果）
            for char in response:
                await websocket.send_json({
                    "type": "message_chunk",
                    "content": char,
                    "timestamp": datetime.now().isoformat()
                })
                # 添加小延迟模拟打字效果
                await asyncio.sleep(0.02)

            # 发送结束标记
            await websocket.send_json({
                "type": "message_end",
                "timestamp": datetime.now().isoformat()
            })

            # 如果需要确认，发送确认请求
            if needs_confirmation:
                print("🔔 检测到需要用户确认，发送confirm_generate消息")

                # ⭐ 从 Agent 实例获取真实的达人数量
                agent = session_manager.get_agent(session_id)
                influencer_count = 10  # 默认值

                print(f"🔍 调试信息:")
                print(f"  - session_id: {session_id}")
                print(f"  - agent: {agent}")
                print(f"  - has target_influencer_count attr: {hasattr(agent, 'target_influencer_count') if agent else False}")

                if agent:
                    print(f"  - target_influencer_count value: {getattr(agent, 'target_influencer_count', None)}")

                    if hasattr(agent, 'target_influencer_count') and agent.target_influencer_count:
                        influencer_count = agent.target_influencer_count
                        print(f"✅ 从 Agent 获取目标达人数: {influencer_count}")
                    else:
                        print(f"⚠️ Agent 的 target_influencer_count 为空或不存在，使用默认值: {influencer_count}")
                else:
                    print(f"⚠️ 无法获取 Agent 实例，使用默认值: {influencer_count}")

                await websocket.send_json({
                    "type": "confirm_generate",
                    "data": {
                        "session_id": session_id,
                        "influencer_count": influencer_count  # ⭐ 传递真实的达人数量
                    },
                    "timestamp": datetime.now().isoformat()
                })

        # 保存 assistant 响应到数据库
        if session_id and response:
            session_manager.save_message(
                session_id=session_id,
                role="assistant",
                content=response,
                message_type="text"
            )

            # 尝试自动更新会话标题（如果需要）
            try:
                # 获取更新前的标题
                from database.connection import get_db_context
                from database.models import ChatSession
                with get_db_context() as db:
                    session = db.query(ChatSession).filter(
                        ChatSession.session_id == session_id
                    ).first()
                    old_title = session.title if session else None

                # 执行自动更新
                session_manager.auto_update_title_if_needed(session_id)

                # 检查标题是否变化
                if old_title:
                    with get_db_context() as db:
                        session = db.query(ChatSession).filter(
                            ChatSession.session_id == session_id
                        ).first()
                        new_title = session.title if session else None

                        if new_title and new_title != old_title:
                            # 通知前端标题已更新
                            await websocket.send_json({
                                "type": "title_updated",
                                "title": new_title,
                                "timestamp": datetime.now().isoformat()
                            })

            except Exception as title_error:
                print(f"⚠️ 自动更新标题失败（不影响主流程）: {title_error}")

        # 发送完成信号
        await websocket.send_json({
            "type": "complete",
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        error_message = f"❌ 处理消息时出错: {str(e)}"
        print(f"[Error] stream_agent_response: {e}")
        import traceback
        traceback.print_exc()

        try:
            await websocket.send_json({
                "type": "error",
                "content": error_message,
                "timestamp": datetime.now().isoformat()
            })
        except:
            print("[Error] 无法发送错误消息，WebSocket 可能已关闭")


# ==================== API 端点 ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """返回聊天界面（如果存在）"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="""
            <html>
                <head><title>TikTok 达人推荐聊天机器人</title></head>
                <body>
                    <h1>TikTok 达人推荐聊天机器人</h1>
                    <p>聊天界面正在准备中...</p>
                    <p>API 文档: <a href="/docs">/docs</a></p>
                </body>
            </html>
            """
        )


@app.get("/login.html", response_class=HTMLResponse)
async def login_page():
    """返回登录页面"""
    try:
        with open("static/login.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 - 登录页面不存在</h1>", status_code=404)


@app.get("/register.html", response_class=HTMLResponse)
async def register_page():
    """返回注册页面"""
    try:
        with open("static/register.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 - 注册页面不存在</h1>", status_code=404)


@app.get("/reset-password.html", response_class=HTMLResponse)
async def reset_password_page():
    """返回密码重置页面"""
    try:
        with open("static/reset-password.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 - 密码重置页面不存在</h1>", status_code=404)


@app.get("/settings.html", response_class=HTMLResponse)
async def settings_page():
    """返回个人设置页面"""
    try:
        with open("static/settings.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 - 设置页面不存在</h1>", status_code=404)


@app.get("/admin.html", response_class=HTMLResponse)
async def admin_page():
    """返回管理员后台页面"""
    try:
        with open("static/admin.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>404 - 管理后台页面不存在</h1>", status_code=404)


@app.get("/api/health")
async def health_check():
    """健康检查"""
    playwright_status = check_playwright_api()

    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "chatbot_api": "running",
            "playwright_api": "running" if playwright_status else "unavailable"
        },
        "active_agents": len(session_manager._agent_cache)
    })


@app.get("/api/check-playwright")
async def check_playwright():
    """检查 Playwright API 服务状态"""
    is_available = check_playwright_api()

    if not is_available:
        raise HTTPException(
            status_code=503,
            detail="Playwright API 服务不可用。请确保已启动 playwright_api.py（端口 8000）"
        )

    return JSONResponse({
        "status": "available",
        "url": "http://127.0.0.1:8000"
    })


@app.post("/api/sessions")
async def create_session(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db)
):
    """创建新的聊天会话（需要认证）"""
    try:
        # ⭐ 检查用户积分是否足够（至少需要100积分）
        MIN_CREDITS_REQUIRED = 100
        from database.models import UserUsage

        usage = db.query(UserUsage).filter(
            UserUsage.user_id == current_user.user_id
        ).first()

        if usage:
            remaining_credits = usage.total_credits - usage.used_credits
            if remaining_credits < MIN_CREDITS_REQUIRED:
                raise HTTPException(
                    status_code=403,
                    detail=f"积分不足：您当前剩余 {remaining_credits} 积分，至少需要 {MIN_CREDITS_REQUIRED} 积分才能创建新对话。每个达人消耗100积分。"
                )

            # ⭐ 检查每日新对话创建限制（基于积分动态计算）
            today_start = get_today_start()  # 使用东八区时间

            # 统计今日已创建的新对话数（有消息的会话才算）
            # 先获取今日所有会话
            today_sessions = db.query(ChatSession.session_id).filter(
                ChatSession.user_id == current_user.user_id,
                ChatSession.created_at >= today_start
            ).all()

            # 统计有消息的会话数
            today_sessions_count = 0
            for session in today_sessions:
                message_count = db.query(Message).filter(
                    Message.session_id == session.session_id
                ).count()
                if message_count > 0:
                    today_sessions_count += 1

            # 计算用户每日最大新对话数
            max_daily_conversations = calculate_max_daily_conversations(remaining_credits)

            if today_sessions_count >= max_daily_conversations:
                raise HTTPException(
                    status_code=429,
                    detail=f"今日新对话数已达上限（{today_sessions_count}/{max_daily_conversations}）。当前积分 {remaining_credits} 对应每日 {max_daily_conversations} 个新对话。充值可增加额度。"
                )
        
        # 检查 Playwright API 是否可用
        if not check_playwright_api():
            raise HTTPException(
                status_code=503,
                detail="Playwright API 服务不可用，无法创建会话"
            )

        # 使用数据库版本的 session_manager
        session_id = session_manager.create_session(
            user_id=current_user.user_id,
            title="新对话"
        )

        print(f"✅ 新会话已创建: {session_id} (用户: {current_user.user_id})")

        return JSONResponse({
            "session_id": session_id,
            "user_id": current_user.user_id,
            "created_at": datetime.now().isoformat(),
            "message": "会话创建成功"
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """删除指定会话（需要认证和权限验证）"""
    print(f"🗑️ 收到删除请求: session_id={session_id}, user_id={current_user.user_id}")

    # 验证用户是否有权删除此会话
    has_access = session_manager.verify_session_access(session_id, current_user.user_id)
    print(f"   权限验证结果: {has_access}")

    if not has_access:
        print(f"❌ 用户 {current_user.user_id} 无权删除会话 {session_id}")
        raise HTTPException(
            status_code=403,
            detail="无权删除此会话"
        )

    success = session_manager.delete_session(session_id)
    print(f"   删除结果: {success}")

    if not success:
        print(f"❌ 会话 {session_id} 不存在")
        raise HTTPException(status_code=404, detail="会话不存在")

    print(f"✅ 会话 {session_id} 已删除")
    return JSONResponse({
        "message": "会话已删除",
        "session_id": session_id
    })


@app.patch("/api/sessions/{session_id}")
async def update_session(
    session_id: str,
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """更新会话信息（如标题）"""
    print(f"✏️ 收到重命名请求: session_id={session_id}, user_id={current_user.user_id}")

    # 验证用户是否有权修改此会话
    has_access = session_manager.verify_session_access(session_id, current_user.user_id)
    print(f"   权限验证结果: {has_access}")

    if not has_access:
        print(f"❌ 用户 {current_user.user_id} 无权修改会话 {session_id}")
        raise HTTPException(
            status_code=403,
            detail="无权修改此会话"
        )

    try:
        title = request.get('title')
        if not title:
            print(f"❌ 标题为空")
            raise HTTPException(status_code=400, detail="标题不能为空")

        title = title.strip()  # 去除首尾空格
        print(f"   新标题: {title}")

        # ⭐ 检查标题是否与该用户的其他会话重复
        with get_db_context() as db:
            duplicate_session = db.query(ChatSession).filter(
                ChatSession.user_id == current_user.user_id,
                ChatSession.session_id != session_id,
                ChatSession.title == title
            ).first()

            if duplicate_session:
                print(f"❌ 标题重复: 已存在相同标题的会话 {duplicate_session.session_id}")
                raise HTTPException(
                    status_code=400,
                    detail="该标题已存在，请使用不同的标题"
                )

        # 更新会话标题
        success = session_manager.update_session_title(session_id, title)

        if not success:
            print(f"❌ 会话 {session_id} 不存在")
            raise HTTPException(status_code=404, detail="会话不存在")

        # ⭐ 同步更新该会话关联的所有报告标题
        updated_count = 0
        with get_db_context() as db:
            updated_count = db.query(Report).filter(
                Report.session_id == session_id
            ).update({Report.title: title})
            db.commit()

            if updated_count > 0:
                print(f"✅ 同步更新了 {updated_count} 个关联报告的标题")
            else:
                print(f"ℹ️ 该会话没有关联报告")

        print(f"✅ 会话 {session_id} 重命名成功")
        return JSONResponse({
            "message": "会话已更新",
            "session_id": session_id,
            "title": title,
            "updated_reports": updated_count
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@app.get("/api/sessions/{session_id}/status")
async def get_session_status(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db)
):
    """获取会话状态（需要认证和权限验证）"""
    # 验证用户是否有权访问此会话
    if not session_manager.verify_session_access(session_id, current_user.user_id) and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="无权访问此会话"
        )

    # 从数据库获取会话历史
    history = session_manager.get_session_history(session_id, limit=50)

    return JSONResponse({
        "session_id": session_id,
        "user_id": current_user.user_id,
        "message_count": len(history),
        "messages": history
    })


@app.get("/api/sessions/{session_id}/reports")
async def get_session_reports(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取指定会话关联的所有报告（需要认证和权限验证）"""
    # 验证用户是否有权访问此会话
    if not session_manager.verify_session_access(session_id, current_user.user_id) and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="无权访问此会话"
        )

    try:
        from database.connection import get_db_context
        from database.models import Report

        with get_db_context() as db:
            # 查询该会话关联的所有报告
            reports = db.query(Report).filter(
                Report.session_id == session_id
            ).all()

            # 转换为字典列表
            reports_data = []
            for report in reports:
                report_type = report.meta_data.get('type', 'unknown') if report.meta_data else 'unknown'

                reports_data.append({
                    "report_id": report.report_id,
                    "title": report.title,
                    "status": report.status,
                    "report_type": report_type,
                    "created_at": report.created_at.isoformat() if report.created_at else None,
                })

            return JSONResponse({
                "session_id": session_id,
                "total": len(reports_data),
                "reports": reports_data
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"获取会话报告失败: {str(e)}"}
        )


@app.get("/api/sessions")
async def list_user_sessions(
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0
):
    """列出当前用户的所有会话"""
    sessions = session_manager.get_user_sessions(
        user_id=current_user.user_id,
        limit=limit,
        offset=offset
    )

    return JSONResponse({
        "total": len(sessions),
        "sessions": sessions
    })


@app.get("/api/reports")
async def get_user_reports(
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0
):
    """获取当前用户的所有报告"""
    try:
        from database.connection import get_db_context
        from database.models import Report
        from sqlalchemy import desc

        with get_db_context() as db:
            # 查询当前用户的报告，按创建时间倒序
            reports = db.query(Report).filter(
                Report.user_id == current_user.user_id
            ).order_by(
                desc(Report.created_at)  # ⭐ 修复：使用 created_at 而不是 updated_at
            ).offset(offset).limit(limit).all()

            # 转换为字典列表
            reports_data = []
            for report in reports:
                # 从 meta_data 中提取 type 字段
                report_type = report.meta_data.get('type', 'unknown') if report.meta_data else 'unknown'

                reports_data.append({
                    "report_id": report.report_id,
                    "session_id": report.session_id,  # ⭐ 新增：返回 session_id
                    "title": report.title,
                    "status": report.status,
                    "report_type": report_type,  # ⭐ 从 meta_data 中提取
                    "file_path": report.report_path,  # ⭐ 修复：使用正确的字段名
                    "error_message": report.error_message,
                    "scraping_progress": report.scraping_progress,  # ⭐ 新增：爬取进度
                    "report_progress": report.report_progress,      # ⭐ 新增：报告生成进度
                    "created_at": report.created_at.isoformat() if report.created_at else None,
                    "completed_at": report.completed_at.isoformat() if report.completed_at else None
                })

            return JSONResponse({
                "total": len(reports_data),
                "reports": reports_data
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"获取报告列表失败: {str(e)}"}
        )


@app.get("/api/reports/{report_id}/view")
async def view_report(
    report_id: str,
    current_user: User = Depends(get_current_user)
):
    """查看报告HTML文件"""
    try:
        from database.connection import get_db_context
        from database.models import Report
        from fastapi.responses import FileResponse
        import os

        with get_db_context() as db:
            # 查询报告
            report = db.query(Report).filter(
                Report.report_id == report_id
            ).first()

            if not report:
                raise HTTPException(status_code=404, detail="报告不存在")

            # 验证权限
            if report.user_id != current_user.user_id and not current_user.is_admin:
                raise HTTPException(status_code=403, detail="无权访问此报告")

            # 检查报告状态
            if report.status != 'completed':
                raise HTTPException(status_code=400, detail=f"报告尚未完成，当前状态: {report.status}")

            # 检查文件路径
            if not report.report_path:
                raise HTTPException(status_code=404, detail="报告文件路径不存在")

            # 处理路径（支持反斜杠和正斜杠）
            file_path = report.report_path.replace('\\', os.sep).replace('/', os.sep)

            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"❌ 报告文件不存在: {file_path}")
                raise HTTPException(status_code=404, detail=f"报告文件不存在: {file_path}")

            print(f"📄 返回报告文件: {file_path}")

            # 返回HTML文件
            return FileResponse(
                path=file_path,
                media_type='text/html',
                filename=os.path.basename(file_path)
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 查看报告失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"查看报告失败: {str(e)}")


@app.get("/api/reports/{report_id}")
async def get_report_detail(
    report_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取单个报告的详细信息"""
    try:
        from database.connection import get_db_context
        from database.models import Report
        import os

        print(f"📄 获取报告详情: {report_id}")

        with get_db_context() as db:
            # 查询报告
            report = db.query(Report).filter(
                Report.report_id == report_id
            ).first()

            if not report:
                raise HTTPException(status_code=404, detail="报告不存在")

            # 验证权限
            if report.user_id != current_user.user_id and not current_user.is_admin:
                raise HTTPException(status_code=403, detail="无权访问此报告")

            # 检查报告文件是否存在
            report_file_exists = False
            if report.report_path and report.status == 'completed':
                # 处理路径（支持反斜杠和正斜杠）
                file_path = report.report_path.replace('\\', os.sep).replace('/', os.sep)
                report_file_exists = os.path.exists(file_path)
                print(f"   报告路径: {file_path}")
                print(f"   文件存在: {report_file_exists}")

            # 从 meta_data 中提取信息
            report_type = report.meta_data.get('type', 'unknown') if report.meta_data else 'unknown'

            result = {
                "report_id": report.report_id,
                "title": report.title,
                "status": report.status,
                "report_type": report_type,
                "file_path": report.report_path,
                "file_exists": report_file_exists,
                "error_message": report.error_message,
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "completed_at": report.completed_at.isoformat() if report.completed_at else None,
                "message": "报告详情获取成功"
            }

            print(f"✅ 返回报告详情: status={result['status']}, file_exists={result['file_exists']}")
            return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 获取报告详情失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取报告详情失败: {str(e)}")


# ==================== WebSocket 端点 ====================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...)  # JWT token from query parameter
):
    """
    WebSocket 聊天端点（需要认证）

    消息格式：
    - 客户端发送: {"type": "message", "content": "用户消息"}
    - 服务端返回: {"type": "message", "content": "响应片段", "timestamp": "..."}
    - 服务端完成: {"type": "complete", "timestamp": "..."}
    - 服务端错误: {"type": "error", "content": "错误信息", "timestamp": "..."}
    """
    # 接受 WebSocket 连接
    await websocket.accept()

    # 验证 JWT token
    try:
        from auth.security import decode_token
        from database.connection import get_db_context

        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            await websocket.send_json({
                "type": "error",
                "content": "认证失败，请重新登录",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4001)
            return

        user_id = payload.get("sub")
        if not user_id:
            await websocket.send_json({
                "type": "error",
                "content": "无效的认证令牌",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4001)
            return

        # 验证用户是否有权访问此会话
        if not session_manager.verify_session_access(session_id, user_id):
            await websocket.send_json({
                "type": "error",
                "content": "无权访问此会话",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=4003)
            return

    except Exception as e:
        print(f"[WebSocket] 认证错误: {e}")
        await websocket.send_json({
            "type": "error",
            "content": "认证失败",
            "timestamp": datetime.now().isoformat()
        })
        await websocket.close(code=4001)
        return

    # 验证会话是否存在
    agent = session_manager.get_agent(session_id)
    if not agent:
        await websocket.send_json({
            "type": "error",
            "content": "会话不存在或已过期，请重新创建会话",
            "timestamp": datetime.now().isoformat()
        })
        await websocket.close()
        return

    # 发送欢迎消息
    welcome = agent.welcome_message()
    await websocket.send_json({
        "type": "welcome",
        "content": welcome,
        "timestamp": datetime.now().isoformat()
    })

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()

            try:
                # 解析 JSON 消息
                message_data = json.loads(data)
                message_type = message_data.get("type", "message")
                content = message_data.get("content", "")
                image_data = message_data.get("image", None)  # 获取图片数据

                if message_type == "message" and (content or image_data):
                    # ⭐ 安全检查 1: 内容审核
                    if content:
                        is_safe, violation_reason = content_moderator.check_content(content)
                        if not is_safe:
                            with get_db_context() as db:
                                client_ip = websocket.client.host if websocket.client else "unknown"
                                security_service.log_security_event(
                                    db=db,
                                    event_type="content_violation",
                                    severity="medium",
                                    user_id=user_id,
                                    ip_address=client_ip,
                                    event_details={"reason": violation_reason, "content_preview": content[:100]}
                                )
                                security_service.update_user_risk_score(db, user_id, violation_increment=1, risk_increment=5)

                            await websocket.send_json({
                                "type": "error",
                                "content": f"内容违规：{violation_reason}。请遵守使用规范。",
                                "timestamp": datetime.now().isoformat()
                            })
                            continue

                        # ⭐ 安全检查 2: Prompt注入检测
                        is_injection, injection_reason = content_moderator.detect_prompt_injection(content)
                        if is_injection:
                            with get_db_context() as db:
                                client_ip = websocket.client.host if websocket.client else "unknown"
                                security_service.log_security_event(
                                    db=db,
                                    event_type="prompt_injection",
                                    severity="high",
                                    user_id=user_id,
                                    ip_address=client_ip,
                                    event_details={"reason": injection_reason, "content_preview": content[:100]}
                                )
                                security_service.update_user_risk_score(db, user_id, violation_increment=1, risk_increment=15)

                            await websocket.send_json({
                                "type": "error",
                                "content": f"检测到可疑输入模式，已被拦截。请正常使用对话功能。",
                                "timestamp": datetime.now().isoformat()
                            })
                            continue

                    # ⭐ 安全检查 3: 对话频率限制（每分钟最多5条消息）
                    allowed, remaining = rate_limiter.check_rate_limit(
                        key=f"chat_message:{user_id}",
                        max_requests=5,
                        window_seconds=60
                    )
                    if not allowed:
                        with get_db_context() as db:
                            client_ip = websocket.client.host if websocket.client else "unknown"
                            security_service.log_security_event(
                                db=db,
                                event_type="rate_limit_exceeded",
                                severity="low",
                                user_id=user_id,
                                ip_address=client_ip,
                                event_details={"action": "chat_message", "limit": "per_minute"}
                            )

                        await websocket.send_json({
                            "type": "error",
                            "content": "发送消息过快，请稍后再试（每分钟最多5条消息）",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue

                    # ⭐ 安全检查 4: 检查会话轮次是否超限（最多50轮）
                    with get_db_context() as db:
                        message_count = db.query(Message).filter(
                            Message.session_id == session_id
                        ).count()

                        # 计算轮次：每2条消息（1用户+1助手）= 1轮
                        current_rounds = message_count // 2

                        if current_rounds >= MAX_ROUNDS_PER_SESSION:
                            await websocket.send_json({
                                "type": "error",
                                "content": f"当前会话已达到最大轮次限制（{MAX_ROUNDS_PER_SESSION}轮）。请创建新会话继续对话。",
                                "timestamp": datetime.now().isoformat()
                            })
                            continue

                    # ⭐ 检查用户积分是否足够（至少需要100积分）
                    MIN_CREDITS_REQUIRED = 100
                    with get_db_context() as db:
                        from database.models import UserUsage
                        usage = db.query(UserUsage).filter(
                            UserUsage.user_id == user_id
                        ).first()

                        if usage:
                            remaining_credits = usage.total_credits - usage.used_credits
                            if remaining_credits < MIN_CREDITS_REQUIRED:
                                await websocket.send_json({
                                    "type": "error",
                                    "content": f"积分不足：您当前剩余 {remaining_credits} 积分，至少需要 {MIN_CREDITS_REQUIRED} 积分才能使用。每个达人消耗100积分。",
                                    "timestamp": datetime.now().isoformat()
                                })
                                continue
                    
                    # 保存用户消息到数据库
                    session_manager.save_message(
                        session_id=session_id,
                        role="user",
                        content=content,
                        message_type="text" if not image_data else "image",
                        attachments={"image": image_data} if image_data else None
                    )

                    # 发送"正在输入"指示器
                    await websocket.send_json({
                        "type": "typing",
                        "timestamp": datetime.now().isoformat()
                    })

                    # 处理并流式返回响应（包括图片）
                    await stream_agent_response(agent, content, websocket, image_data, session_id)

                elif message_type == "ping":
                    # 心跳响应
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })

            except json.JSONDecodeError:
                # 兼容纯文本消息
                if data.strip():
                    await websocket.send_json({
                        "type": "typing",
                        "timestamp": datetime.now().isoformat()
                    })
                    await stream_agent_response(agent, data, websocket)

    except WebSocketDisconnect:
        print(f"[WebSocket] 客户端断开连接: {session_id}")

    except Exception as e:
        print(f"[WebSocket] 错误: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "content": f"服务器错误: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass

    finally:
        # 不自动删除会话，让用户或定时任务来清理
        pass


# ==================== 启动函数 ====================

def start_server(host: str = "127.0.0.1", port: int = 8001):
    """启动聊天机器人服务器"""
    print("""
╔══════════════════════════════════════════════════════════╗
║     🤖 TikTok 达人推荐聊天机器人 API 服务启动中...      ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 初始化后台任务队列
    print("🔧 初始化后台任务队列...")
    try:
        from background_tasks import task_queue
        print("✅ 后台任务队列已就绪")
    except Exception as e:
        print(f"⚠️  警告: 后台任务队列初始化失败: {e}")

    # 检查 Playwright API
    print("🔍 检查 Playwright API 服务...")
    if check_playwright_api():
        print("✅ Playwright API 服务正常 (http://127.0.0.1:8000)")
    else:
        print("⚠️  警告: Playwright API 服务不可用")
        print("   请先运行: python start_api.py")
        print("   或者运行: python playwright_api.py")
        print()
        response = input("是否继续启动聊天机器人服务? (y/n): ")
        if response.lower() != 'y':
            print("❌ 启动已取消")
            return

    print(f"\n🚀 启动聊天机器人服务...")
    print(f"📍 地址: http://{host}:{port}")
    print(f"📖 API 文档: http://{host}:{port}/docs")
    print(f"💬 聊天界面: http://{host}:{port}/")
    print(f"\n按 Ctrl+C 停止服务\n")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
