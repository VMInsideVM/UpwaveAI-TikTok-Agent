"""
Admin API Extensions
管理员 API 扩展端点（积分历史、用户会话、聊天详情等）
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from database.connection import get_db
from database.models import User, ChatSession, Message, CreditHistory
from auth.dependencies import get_current_admin_user
from api.admin import router


# ==================== Pydantic Models ====================

class CreditHistoryInfo(BaseModel):
    """积分变动历史信息"""
    history_id: str
    user_id: str
    username: Optional[str]
    change_type: str
    amount: int
    before_credits: int
    after_credits: int
    reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    title: str
    created_at: datetime
    message_count: int

    class Config:
        from_attributes = True


class MessageInfo(BaseModel):
    """消息信息"""
    message_id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 积分历史 ====================

@router.get("/users/{user_id}/credit-history", response_model=List[CreditHistoryInfo])
async def get_user_credit_history(
    user_id: str,
    skip: int = 0,
    limit: int = 100,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    获取用户积分变动历史

    Args:
        user_id: 用户ID
        skip: 跳过记录数
        limit: 返回记录数限制
    """
    # 检查用户是否存在
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 查询积分历史
    histories = db.query(CreditHistory).filter(
        CreditHistory.user_id == user_id
    ).order_by(CreditHistory.created_at.desc()).offset(skip).limit(limit).all()

    username = user.username

    return [
        CreditHistoryInfo(
            history_id=h.history_id,
            user_id=h.user_id,
            username=username,
            change_type=h.change_type,
            amount=h.amount,
            before_credits=h.before_credits,
            after_credits=h.after_credits,
            reason=h.reason,
            created_at=h.created_at
        ) for h in histories
    ]


# ==================== 用户聊天列表 ====================

@router.get("/users/{user_id}/sessions", response_model=List[SessionInfo])
async def get_user_sessions(
    user_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    获取用户所有聊天会话

    Args:
        user_id: 用户ID
    """
    # 检查用户是否存在
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 查询用户的所有会话
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == user_id
    ).order_by(ChatSession.created_at.desc()).all()

    result = []
    for session in sessions:
        # 统计每个会话的消息数
        message_count = db.query(func.count(Message.message_id)).filter(
            Message.session_id == session.session_id
        ).scalar()

        result.append(SessionInfo(
            session_id=session.session_id,
            title=session.title,
            created_at=session.created_at,
            message_count=message_count or 0
        ))

    return result


# ==================== 聊天详情 ====================

@router.get("/sessions/{session_id}/messages", response_model=List[MessageInfo])
async def get_session_messages(
    session_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    获取会话的所有消息

    Args:
        session_id: 会话ID
    """
    # 检查会话是否存在
    session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    # 查询会话的所有消息
    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at).all()

    return [
        MessageInfo(
            message_id=m.message_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at
        ) for m in messages
    ]
