"""
TikTok 达人推荐聊天机器人 API 服务
提供基于 WebSocket 的实时聊天功能，支持多用户会话隔离
"""

import asyncio
import json
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import requests
from datetime import datetime

from session_manager import session_manager
from agent import TikTokInfluencerAgent
from agent_wrapper import AgentProgressWrapper, clean_response, translate_tool_call

# 导入 LangSmith 追踪上下文
import langsmith as ls

# 创建 FastAPI 应用
app = FastAPI(
    title="TikTok 达人推荐聊天机器人",
    description="基于 LangChain Agent 的智能聊天服务",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


async def stream_agent_response(agent: TikTokInfluencerAgent, user_input: str, websocket: WebSocket, image_data: Optional[str] = None):
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

            # 按行分割并发送
            lines = response.split('\n')
            for line in lines:
                if line.strip():
                    await websocket.send_json({
                        "type": "message",
                        "content": line + '\n',
                        "timestamp": datetime.now().isoformat()
                    })
                    # 添加小延迟模拟打字效果
                    await asyncio.sleep(0.03)

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
        "active_sessions": len(session_manager.sessions)
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
async def create_session():
    """创建新的聊天会话"""
    try:
        # 检查 Playwright API 是否可用
        if not check_playwright_api():
            raise HTTPException(
                status_code=503,
                detail="Playwright API 服务不可用，无法创建会话"
            )

        session_id = session_manager.create_session()

        # 记录会话创建（LangSmith 追踪将在 agent.run() 中自动启用）
        print(f"[Session] Created: {session_id}")

        return JSONResponse({
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "message": "会话创建成功"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    success = session_manager.delete_session(session_id)

    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")

    return JSONResponse({
        "message": "会话已删除",
        "session_id": session_id
    })


@app.get("/api/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """获取会话状态"""
    info = session_manager.get_session_info(session_id)

    if not info:
        raise HTTPException(status_code=404, detail="会话不存在")

    return JSONResponse(info)


@app.get("/api/sessions")
async def list_sessions():
    """列出所有活跃会话"""
    sessions = session_manager.get_all_sessions()

    return JSONResponse({
        "total": len(sessions),
        "sessions": sessions
    })


# ==================== WebSocket 端点 ====================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket 聊天端点

    消息格式：
    - 客户端发送: {"type": "message", "content": "用户消息"}
    - 服务端返回: {"type": "message", "content": "响应片段", "timestamp": "..."}
    - 服务端完成: {"type": "complete", "timestamp": "..."}
    - 服务端错误: {"type": "error", "content": "错误信息", "timestamp": "..."}
    """
    # 接受 WebSocket 连接
    await websocket.accept()

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
                    # 发送"正在输入"指示器
                    await websocket.send_json({
                        "type": "typing",
                        "timestamp": datetime.now().isoformat()
                    })

                    # 记录消息接收（LangSmith 追踪将在 agent.run() 中自动启用）
                    message_id = str(uuid.uuid4())
                    print(f"[WebSocket] Message {message_id} from session {session_id}, has_image={bool(image_data)}")

                    # 处理并流式返回响应（包括图片）
                    # agent.run_with_image() 和 agent.run() 内部已经有完整的 LangSmith 追踪
                    await stream_agent_response(agent, content, websocket, image_data)

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
