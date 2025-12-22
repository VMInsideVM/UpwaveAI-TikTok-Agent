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
from database.models import User, ChatSession, Message, CreditHistory, TokenUsage, Report
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
    total_tokens: int = 0  # ⭐ 新增：会话总Token
    report_id: Optional[str] = None # ⭐ 新增：关联报告ID
    report_status: Optional[str] = None # ⭐ 新增：关联报告状态

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
        
        # 统计会话的 Token 消耗
        session_tokens = db.query(func.sum(TokenUsage.total_tokens)).filter(
            TokenUsage.session_id == session.session_id
        ).scalar() or 0

        # ⭐ 查询关联报告
        report = db.query(Report).filter(Report.session_id == session.session_id).first()
        report_id = report.report_id if report else None
        report_status = report.status if report else None

        # 过滤掉消息数为 0 的会话（可选：如果要显示空会话但关联了报告的也行？通常空会话没报告）
        if message_count and message_count > 0:
            result.append(SessionInfo(
                session_id=session.session_id,
                title=session.title,
                created_at=session.created_at,
                message_count=message_count,
                total_tokens=int(session_tokens),
                report_id=report_id,
                report_status=report_status
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


# ==================== 数据看板 ====================

@router.get("/statistics/charts")
async def get_dashboard_charts(
    days: int = 30,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    获取仪表盘图表数据
    """
    from datetime import timedelta
    from sqlalchemy import func, cast, Date

    # 生成日期范围
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)  # 包含今天

    # 初始化日期字典（确保每天都有数据，即使是0）
    date_range = [(start_date + timedelta(days=x)) for x in range(days)]
    date_labels = [d.strftime("%Y-%m-%d") for d in date_range]
    
    # 1. 每日新注册用户
    new_users_query = db.query(
        cast(User.created_at, Date).label('date'),
        func.count(User.user_id).label('count')
    ).filter(
        User.created_at >= start_date
    ).group_by(
        cast(User.created_at, Date)
    ).all()
    
    new_users_map = {row.date: row.count for row in new_users_query}
    new_users_data = [new_users_map.get(d, 0) for d in date_range]

    # 2. 总用户数曲线 (累积)
    # 先获取 start_date 之前的总用户数
    base_count = db.query(func.count(User.user_id)).filter(
        User.created_at < start_date
    ).scalar() or 0
    
    total_users_data = []
    current_total = base_count
    for d in date_range:
        current_total += new_users_map.get(d, 0)
        total_users_data.append(current_total)

    # 3. 每日 Token 消耗
    token_usage_query = db.query(
        cast(TokenUsage.created_at, Date).label('date'),
        func.sum(TokenUsage.total_tokens).label('count')
    ).filter(
        TokenUsage.created_at >= start_date
    ).group_by(
        cast(TokenUsage.created_at, Date)
    ).all()
    
    token_usage_map = {row.date: (row.count or 0) for row in token_usage_query}
    token_usage_data = [token_usage_map.get(d, 0) for d in date_range]

    # 4. 每日生成的报告
    reports_query = db.query(
        cast(Report.created_at, Date).label('date'),
        func.count(Report.report_id).label('count')
    ).filter(
        Report.created_at >= start_date
    ).group_by(
        cast(Report.created_at, Date)
    ).all()
    
    reports_map = {row.date: row.count for row in reports_query}
    reports_data = [reports_map.get(d, 0) for d in date_range]

    return {
        "dates": date_labels,
        "new_users": new_users_data,
        "total_users": total_users_data,
        "token_usage": token_usage_data,
        "reports": reports_data
    }
