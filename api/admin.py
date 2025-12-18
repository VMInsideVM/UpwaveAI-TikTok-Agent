"""
Admin API Endpoints
管理员 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import secrets

from database.connection import get_db
from database.models import User, UserUsage, Report, ChatSession, Message, InvitationCode
from auth.dependencies import get_current_admin_user
from background.report_queue import report_queue

router = APIRouter(prefix="/api/admin", tags=["管理员"])


# ==================== Pydantic Models ====================

class UserInfo(BaseModel):
    """用户信息"""
    user_id: str
    username: Optional[str]
    email: Optional[str]
    phone_number: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]
    total_credits: int
    used_credits: int
    remaining_credits: int


class UpdateCreditsRequest(BaseModel):
    """更新积分请求"""
    new_credits: int


class GenerateCodesRequest(BaseModel):
    """生成邀请码请求"""
    count: int = 1


class InvitationCodeInfo(BaseModel):
    """邀请码信息"""
    code_id: str
    code: str
    is_used: bool
    created_at: datetime
    used_at: Optional[datetime]
    used_by_username: Optional[str]


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    user_id: str
    username: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageInfo(BaseModel):
    """消息信息"""
    message_id: str
    role: str
    content: str
    created_at: datetime


# ==================== User Management ====================

@router.get("/users", response_model=List[UserInfo])
async def list_all_users(
    skip: int = 0,
    limit: int = 100,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    列出所有用户（带配额信息）
    """
    users = db.query(User).offset(skip).limit(limit).all()

    result = []
    for user in users:
        usage = db.query(UserUsage).filter(UserUsage.user_id == user.user_id).first()

        if not usage:
            # 创建默认积分（300积分）
            usage = UserUsage(user_id=user.user_id, total_credits=300, used_credits=0)
            db.add(usage)
            db.commit()

        result.append(UserInfo(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            phone_number=user.phone_number,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login,
            total_credits=usage.total_credits,
            used_credits=usage.used_credits,
            remaining_credits=usage.remaining_credits
        ))

    return result


@router.put("/users/{user_id}/credits")
async def update_user_credits(
    user_id: str,
    request: UpdateCreditsRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    修改用户积分
    """
    # 检查用户是否存在
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 获取或创建积分记录
    usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()

    if not usage:
        usage = UserUsage(user_id=user_id, total_credits=request.new_credits, used_credits=0)
        db.add(usage)
    else:
        usage.total_credits = request.new_credits

    db.commit()

    return {
        "message": "积分更新成功",
        "user_id": user_id,
        "username": user.username,
        "new_credits": request.new_credits,
        "remaining": usage.remaining_credits
    }


@router.post("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    激活/停用用户账户
    """
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 不能停用管理员自己
    if user.user_id == admin_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能停用自己的账户"
        )

    user.is_active = not user.is_active
    db.commit()

    return {
        "message": f"用户已{'激活' if user.is_active else '停用'}",
        "user_id": user_id,
        "username": user.username,
        "is_active": user.is_active
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    删除用户及其所有相关数据
    """
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 不能删除管理员自己
    if user.user_id == admin_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户"
        )

    username = user.username

    # 删除用户（CASCADE会自动删除关联的usage、sessions、messages、reports）
    db.delete(user)
    db.commit()

    return {
        "message": f"用户 {username} 已被删除",
        "user_id": user_id,
        "username": username
    }


# ==================== Report Management ====================

@router.get("/reports")
async def list_all_reports(
    skip: int = 0,
    limit: int = 100,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    列出所有报告（所有用户）
    """
    reports = db.query(Report).order_by(
        Report.created_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for report in reports:
        user = db.query(User).filter(User.user_id == report.user_id).first()

        result.append({
            "report_id": report.report_id,
            "title": report.title,
            "status": report.status,
            "user_id": report.user_id,
            "username": user.username if user else "Unknown",
            "created_at": report.created_at.isoformat(),
            "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            "error_message": report.error_message
        })

    return result


# ==================== Session Management ====================

@router.get("/sessions", response_model=List[SessionInfo])
async def list_all_sessions(
    skip: int = 0,
    limit: int = 100,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    列出所有聊天会话
    """
    sessions = db.query(ChatSession).order_by(
        ChatSession.updated_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for session in sessions:
        user = db.query(User).filter(User.user_id == session.user_id).first()
        message_count = db.query(Message).filter(
            Message.session_id == session.session_id
        ).count()

        result.append(SessionInfo(
            session_id=session.session_id,
            user_id=session.user_id,
            username=user.username if user else "Unknown",
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=message_count
        ))

    return result


@router.get("/sessions/{session_id}/messages", response_model=List[MessageInfo])
async def view_session_messages(
    session_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    查看会话的所有消息（管理员监控）
    """
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at).all()

    return [
        MessageInfo(
            message_id=msg.message_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at
        )
        for msg in messages
    ]


# ==================== Task Queue ====================

@router.get("/tasks")
async def view_task_queue(
    admin_user: User = Depends(get_current_admin_user)
):
    """
    查看当前报告生成队列状态
    """
    queue_info = report_queue.get_all_tasks()

    return {
        "current_task": queue_info["current_task"],
        "queue_size": queue_info["queue_size"],
        "is_processing": queue_info["is_processing"],
        "tasks": queue_info["all_statuses"]
    }


# ==================== Invitation Codes ====================

@router.post("/invitation-codes")
async def generate_invitation_codes(
    request: GenerateCodesRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    批量生成邀请码（永久有效）
    """
    if request.count < 1 or request.count > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="生成数量必须在 1-100 之间"
        )

    codes = []

    for _ in range(request.count):
        # 生成随机邀请码
        code = secrets.token_urlsafe(12)[:16].upper()

        inv = InvitationCode(
            code=code,
            is_used=False,
            created_by_admin=admin_user.user_id,
            expires_at=None  # NULL = 永久有效
        )

        db.add(inv)
        codes.append(code)

    db.commit()

    return {
        "codes": codes,
        "count": len(codes),
        "message": f"已生成 {len(codes)} 个永久有效的邀请码"
    }


@router.get("/invitation-codes", response_model=List[InvitationCodeInfo])
async def list_invitation_codes(
    skip: int = 0,
    limit: int = 100,
    show_used: bool = True,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    列出所有邀请码
    """
    query = db.query(InvitationCode)

    if not show_used:
        query = query.filter(InvitationCode.is_used == False)

    codes = query.order_by(
        InvitationCode.created_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for code in codes:
        used_by_user = None
        if code.used_by_user:
            user = db.query(User).filter(User.user_id == code.used_by_user).first()
            used_by_user = user.username if user else "Unknown"

        result.append(InvitationCodeInfo(
            code_id=code.code_id,
            code=code.code,
            is_used=code.is_used,
            created_at=code.created_at,
            used_at=code.used_at,
            used_by_username=used_by_user
        ))

    return result


# ==================== Statistics ====================

@router.get("/statistics")
async def get_statistics(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    获取系统统计信息
    """
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_reports = db.query(Report).count()
    completed_reports = db.query(Report).filter(Report.status == "completed").count()
    total_sessions = db.query(ChatSession).count()
    total_messages = db.query(Message).count()
    unused_codes = db.query(InvitationCode).filter(InvitationCode.is_used == False).count()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users
        },
        "reports": {
            "total": total_reports,
            "completed": completed_reports,
            "in_progress": total_reports - completed_reports
        },
        "sessions": {
            "total": total_sessions,
            "avg_messages_per_session": round(total_messages / total_sessions, 2) if total_sessions > 0 else 0
        },
        "invitation_codes": {
            "unused": unused_codes
        }
    }
