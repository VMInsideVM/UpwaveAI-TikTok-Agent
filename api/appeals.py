"""
Appeals API Endpoints
用户申诉 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from database.connection import get_db
from database.models import User, Appeal, ChatSession
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/appeals", tags=["申诉"])

# ==================== Pydantic Models ====================

class AppealCreate(BaseModel):
    title: str
    details: str
    session_id: Optional[str] = None

class AppealResponse(BaseModel):
    appeal_id: str
    title: str
    details: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
    admin_comment: Optional[str]
    session_id: Optional[str]

# ==================== Endpoints ====================

@router.post("", response_model=AppealResponse)
async def submit_appeal(
    appeal: AppealCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    提交申诉
    每位用户 24 小时内仅限提交一次
    """
    # 1. 检查频率限制 (24小时)
    last_appeal = db.query(Appeal).filter(
        Appeal.user_id == current_user.user_id
    ).order_by(
        desc(Appeal.created_at)
    ).first()

    if last_appeal:
        # 计算时间差
        now = datetime.utcnow()
        if now - last_appeal.created_at < timedelta(hours=24):
            # 计算剩余等待时间
            wait_time = timedelta(hours=24) - (now - last_appeal.created_at)
            hours, remainder = divmod(wait_time.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"您提交虽然很急，但请先别急。申诉频率限制为每天一次，请在 {hours} 小时 {minutes} 分钟后再试。"
            )

    # 2. 验证 session_id (如果提供)
    if appeal.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.session_id == appeal.session_id,
            ChatSession.user_id == current_user.user_id
        ).first()
        if not session:
            raise HTTPException(
                status_code=400,
                detail="关联的会话不存在或不属于您"
            )

    # 3. 创建申诉
    new_appeal = Appeal(
        user_id=current_user.user_id,
        title=appeal.title,
        details=appeal.details,
        session_id=appeal.session_id,
        status="pending"
    )
    
    db.add(new_appeal)
    db.commit()
    db.refresh(new_appeal)

    return AppealResponse(
        appeal_id=new_appeal.appeal_id,
        title=new_appeal.title,
        details=new_appeal.details,
        status=new_appeal.status,
        created_at=new_appeal.created_at,
        resolved_at=new_appeal.resolved_at,
        admin_comment=new_appeal.admin_comment,
        session_id=new_appeal.session_id
    )

@router.get("", response_model=List[AppealResponse])
async def list_my_appeals(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """列出我的申诉记录"""
    appeals = db.query(Appeal).filter(
        Appeal.user_id == current_user.user_id
    ).order_by(
        desc(Appeal.created_at)
    ).offset(skip).limit(limit).all()

    return [
        AppealResponse(
            appeal_id=a.appeal_id,
            title=a.title,
            details=a.details,
            status=a.status,
            created_at=a.created_at,
            resolved_at=a.resolved_at,
            admin_comment=a.admin_comment,
            session_id=a.session_id
        )
        for a in appeals
    ]
