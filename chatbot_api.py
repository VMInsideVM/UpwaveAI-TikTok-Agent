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

# 导入认证相关
from database.connection import get_db
from database.models import User
from auth.dependencies import get_current_user, get_optional_user
from fastapi import Depends, Query
from sqlalchemy.orm import Session as DBSession

# 导入新的 API 路由
from api.auth import router as auth_router
from api.reports import router as reports_router
from api.admin import router as admin_router

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

# 挂载静态文件目录（用于提供前端页面）
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    print("⚠️ static 目录不存在，将在后续步骤创建")


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
    包含进度更新和心跳保活

    Args:
        agent: Agent 实例
        user_input: 用户文本输入
        websocket: WebSocket 连接
        image_data: Base64 编码的图片数据（可选）
    """
    try:
        # 创建一个包装函数来捕获 agent 的处理过程
        import sys
        import io
        from contextlib import redirect_stdout

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
            # 注意：由于 asyncio.run_in_executor 在不同线程中运行，
            # 这里的进度回调需要特殊处理
            # 简化版本：直接运行，后续可以改进为真正的实时进度

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
                # 执行 agent（同步调用）
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

        # 保存 assistant 响应到数据库
        if session_id and response:
            session_manager.save_message(
                session_id=session_id,
                role="assistant",
                content=response,
                message_type="text"
            )

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

        return JSONResponse({
            "session_id": session_id,
            "user_id": current_user.user_id,
            "created_at": datetime.now().isoformat(),
            "message": "会话创建成功"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """删除指定会话（需要认证和权限验证）"""
    # 验证用户是否有权删除此会话
    if not session_manager.verify_session_access(session_id, current_user.user_id):
        raise HTTPException(
            status_code=403,
            detail="无权删除此会话"
        )

    success = session_manager.delete_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")

    return JSONResponse({
        "message": "会话已删除",
        "session_id": session_id
    })


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
