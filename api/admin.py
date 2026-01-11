"""
Admin API Endpoints
管理员 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta  # Add timedelta import
import secrets

from database.connection import get_db
from database.connection import get_db
from database.models import User, UserUsage, Report, ChatSession, Message, InvitationCode, CreditHistory, Appeal, TokenUsage
from auth.dependencies import get_current_admin_user
from background.report_queue import report_queue
from sqlalchemy import or_, func, distinct, and_

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
    total_sessions: int = 0  # ⭐ 新增：总聊天数
    total_tokens: int = 0  # ⭐ 新增：总token数
    tokens_24h: int = 0  # ⭐ 新增：24小时Token消耗


class UpdateCreditsRequest(BaseModel):
    """更新积分请求"""
    new_credits: int


class UpdateUserInfoRequest(BaseModel):
    """更新用户信息请求"""
    username: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    password: Optional[str] = None  # 新密码（明文，会自动加密）


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


class AppealAdminInfo(BaseModel):
    """管理员查看的申诉信息"""
    appeal_id: str
    user_id: str
    username: str
    session_id: Optional[str]
    title: str
    details: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    admin_comment: Optional[str]


class ProcessAppealRequest(BaseModel):
    """处理申诉请求"""
    status: str  # resolved, ignored, pending
    comment: Optional[str]


# ==================== User Management ====================

@router.get("/users", response_model=List[UserInfo])
async def list_all_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    # 筛选参数
    min_credits: Optional[int] = None,
    max_credits: Optional[int] = None,
    min_sessions: Optional[int] = None,
    max_sessions: Optional[int] = None,
    min_tokens: Optional[int] = None,
    max_tokens: Optional[int] = None,
    min_tokens_24h: Optional[int] = None,
    max_tokens_24h: Optional[int] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    列出所有用户（带配额信息），支持多维度筛选
    """
    # 1. 准备子查询：统计每个用户的有效会话数（有消息的会话）
    # SELECT user_id, COUNT(DISTINCT session_id) FROM sessions JOIN messages ... GROUP BY user_id
    subq_sessions = db.query(
        ChatSession.user_id,
        func.count(distinct(ChatSession.session_id)).label('session_count')
    ).join(Message, ChatSession.session_id == Message.session_id)\
     .group_by(ChatSession.user_id).subquery()

    # 2. 准备子查询：统计每个用户的24小时Token消耗
    time_24h_ago = datetime.utcnow() - timedelta(hours=24)
    subq_tokens_24h = db.query(
        TokenUsage.user_id,
        func.sum(TokenUsage.total_tokens).label('tokens_24h')
    ).filter(TokenUsage.created_at >= time_24h_ago)\
     .group_by(TokenUsage.user_id).subquery()

    # 3. 构建主查询：连接用户表、积分表和上述子查询
    # 使用 outerjoin 确保即使没有会话或积分记录的用户也能被查出来
    query = db.query(
        User,
        UserUsage,
        func.coalesce(subq_sessions.c.session_count, 0).label('session_count'),
        func.coalesce(subq_tokens_24h.c.tokens_24h, 0).label('tokens_24h')
    ).outerjoin(UserUsage, User.user_id == UserUsage.user_id)\
     .outerjoin(subq_sessions, User.user_id == subq_sessions.c.user_id)\
     .outerjoin(subq_tokens_24h, User.user_id == subq_tokens_24h.c.user_id)

    # 4. 应用筛选条件
    
    # 搜索框过滤（用户名/邮箱/手机）
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.phone_number.ilike(f"%{search}%")
            )
        )
    
    # 积分筛选
    if min_credits is not None:
        # 注意：这里假设 UserUsage 存在。如果没有 UserUsage (NULL)，则 remaining 为 0 (代码逻辑稍后处理)
        # SQL中 NULL >= X 通常为 False，这符合预期
        query = query.filter((UserUsage.total_credits - UserUsage.used_credits) >= min_credits)
    if max_credits is not None:
        query = query.filter((UserUsage.total_credits - UserUsage.used_credits) <= max_credits)
        
    # 会话数筛选
    if min_sessions is not None:
        query = query.filter(func.coalesce(subq_sessions.c.session_count, 0) >= min_sessions)
    if max_sessions is not None:
        query = query.filter(func.coalesce(subq_sessions.c.session_count, 0) <= max_sessions)
        
    # 总 Token 筛选
    if min_tokens is not None:
        query = query.filter(UserUsage.total_tokens_used >= min_tokens)
    if max_tokens is not None:
        query = query.filter(UserUsage.total_tokens_used <= max_tokens)
        
    # 24h Token 筛选
    if min_tokens_24h is not None:
        query = query.filter(func.coalesce(subq_tokens_24h.c.tokens_24h, 0) >= min_tokens_24h)
    if max_tokens_24h is not None:
        query = query.filter(func.coalesce(subq_tokens_24h.c.tokens_24h, 0) <= max_tokens_24h)

    # 5. 执行查询和分页
    # 默认按注册时间倒序
    query = query.order_by(User.created_at.desc())
    results = query.offset(skip).limit(limit).all()

    # 6. 构建返回结果
    response_data = []
    
    for user, usage, session_count, tokens_24h in results:
        # 处理 UserUsage 为空的情况（虽然通常应该有，但为了健壮性）
        if not usage:
             # 如果查出来没有 usage 记录，手动创建一个临时的对象用于展示（不存库）
             # 实际上 list_all_users 旧逻辑会 create，但 GET 请求一般不应产生副作用。
             # 我们展示默认值 0
             total_credits = 300
             used_credits = 0
             remaining_credits = 300
             total_tokens = 0
        else:
            total_credits = usage.total_credits
            used_credits = usage.used_credits
            remaining_credits = usage.remaining_credits
            total_tokens = usage.total_tokens_used

        response_data.append(UserInfo(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            phone_number=user.phone_number,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            last_login=user.last_login,
            total_credits=total_credits,
            used_credits=used_credits,
            remaining_credits=remaining_credits,
            total_sessions=int(session_count),
            total_tokens=total_tokens,
            tokens_24h=int(tokens_24h)
        ))

    return response_data


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

    # 记录变动前的积分
    if not usage:
        before_total = 0
        usage = UserUsage(user_id=user_id, total_credits=request.new_credits, used_credits=0)
        db.add(usage)
    else:
        before_total = usage.total_credits
        usage.total_credits = request.new_credits

    # ⭐ 创建积分变动历史记录
    change_amount = request.new_credits - before_total
    change_type = 'add' if change_amount > 0 else 'deduct' if change_amount < 0 else 'adjust'

    credit_history = CreditHistory(
        user_id=user_id,
        change_type=change_type,
        amount=change_amount,
        before_credits=before_total,
        after_credits=request.new_credits,
        reason=f"管理员调整积分: {admin_user.username or admin_user.user_id}",
        meta_data={
            "admin_id": admin_user.user_id,
            "admin_username": admin_user.username
        }
    )
    db.add(credit_history)

    db.commit()

    return {
        "message": "积分更新成功",
        "user_id": user_id,
        "username": user.username,
        "new_credits": request.new_credits,
        "remaining": usage.remaining_credits,
        "change_amount": change_amount
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


@router.put("/users/{user_id}")
async def update_user_info(
    user_id: str,
    request: UpdateUserInfoRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    修改用户信息（用户名、手机号、邮箱、密码）
    """
    # 检查用户是否存在
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )

    # 记录修改前的信息
    old_info = {
        "username": user.username,
        "email": user.email,
        "phone_number": user.phone_number
    }

    # 更新用户名（如果提供）
    if request.username is not None:
        # 检查用户名是否已被使用
        existing = db.query(User).filter(
            User.username == request.username,
            User.user_id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"用户名 '{request.username}' 已被使用"
            )
        user.username = request.username

    # 更新邮箱（如果提供）
    if request.email is not None:
        # 检查邮箱是否已被使用
        existing = db.query(User).filter(
            User.email == request.email,
            User.user_id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"邮箱 '{request.email}' 已被使用"
            )
        user.email = request.email

    # 更新手机号（如果提供）
    if request.phone_number is not None:
        # 检查手机号是否已被使用（如果不为空）
        if request.phone_number:
            existing = db.query(User).filter(
                User.phone_number == request.phone_number,
                User.user_id != user_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"手机号 '{request.phone_number}' 已被使用"
                )
        user.phone_number = request.phone_number

    # 更新密码（如果提供）
    if request.password is not None:
        # 使用 bcrypt 加密密码
        import bcrypt
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(request.password.encode('utf-8'), salt)
        user.hashed_password = hashed_password.decode('utf-8')

    db.commit()
    db.refresh(user)

    return {
        "message": "用户信息更新成功",
        "user_id": user_id,
        "old_info": old_info,
        "new_info": {
            "username": user.username,
            "email": user.email,
            "phone_number": user.phone_number,
            "password_updated": request.password is not None
        }
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
    search: Optional[str] = None,
    # 日期筛选参数
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    completed_after: Optional[datetime] = None,
    completed_before: Optional[datetime] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    列出所有报告（所有用户），支持日期筛选
    """
    query = db.query(Report).join(User, Report.user_id == User.user_id)

    if search:
        query = query.filter(
            or_(
                Report.title.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )

    # 日期筛选
    if created_after:
        query = query.filter(Report.created_at >= created_after)
    if created_before:
        query = query.filter(Report.created_at <= created_before)
        
    if completed_after:
        query = query.filter(Report.completed_at >= completed_after)
    if completed_before:
        query = query.filter(Report.completed_at <= completed_before)

    reports = query.order_by(
        Report.created_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for report in reports:
        # report.user is already joined/available via User join usually, but the select was just Report (implied by db.query(Report))
        # But wait, db.query(Report).join(User) -> selects Report columns.
        # So we can access report.user if lazy load or access the joined User columns if we selected them.
        # Since we use ORM relationship 'user', accessing report.user works (lazy or joined load).
        # We did not optimize with joinedload, so it might do N+1 if we access report.user.username, 
        # BUT we joined in query, filtering works.
        # Let's trust ORM relationship for simplicity, or we could select both.
        # For filtering, we used Join. For accessing username in result loop:
        
        # Accessing report.user will trigger a query if not loaded.
        # Since we joined User, we might as well rely on accessing report.user relationship. 
        # SQLAlchemy session cache might help, or simple lazy load.
        
        result.append({
            "report_id": report.report_id,
            "title": report.title,
            "status": report.status,
            "user_id": report.user_id,
            "username": report.user.username if report.user else "Unknown",
            "session_id": report.session_id,
            "created_at": report.created_at.isoformat(),
            "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            "error_message": report.error_message
        })

    return result


@router.get("/reports/{report_id}")
async def get_report_detail(
    report_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    查看单个报告的详细信息（管理员可以查看任何用户的报告）
    """
    import os
    import json

    # 查询报告
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    # 获取用户信息
    user = db.query(User).filter(User.user_id == report.user_id).first()

    # 读取报告文件内容（HTML或JSON）
    report_content = None
    report_data = None

    if report.report_path and os.path.exists(report.report_path):
        try:
            # 如果是JSON文件，读取数据
            if report.report_path.endswith('.json'):
                with open(report.report_path, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                    report_content = f"JSON报告，包含 {len(report_data)} 条数据"
            # 如果是HTML文件，读取内容
            elif report.report_path.endswith('.html'):
                with open(report.report_path, 'r', encoding='utf-8') as f:
                    report_content = f.read()
        except Exception as e:
            report_content = f"无法读取报告文件: {str(e)}"

    return {
        "report_id": report.report_id,
        "title": report.title,
        "status": report.status,
        "user_id": report.user_id,
        "username": user.username if user else "Unknown",
        "user_email": user.email if user else None,
        "session_id": report.session_id,
        "created_at": report.created_at.isoformat(),
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
        "report_path": report.report_path,
        "error_message": report.error_message,
        "report_content": report_content,
        "report_data": report_data  # 如果是JSON，返回实际数据
    }


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
    try:
        queue_info = report_queue.get_all_tasks()

        # 过滤出排队中的任务
        all_statuses = queue_info.get("all_statuses", [])
        queued_tasks = [task for task in all_statuses if task.get("status") == "queued"]

        return {
            "success": True,
            "current_task": queue_info["current_task"],
            "queue_size": queue_info["queue_size"],
            "queue_length": len(queued_tasks),  # 添加 queue_length
            "queued_tasks": queued_tasks,  # 添加 queued_tasks
            "is_processing": queue_info["is_processing"],
            "tasks": all_statuses  # 保留原字段用于兼容
        }
    except Exception as e:
        # 返回错误信息而不是抛出异常，避免前端显示混乱
        return {
            "success": False,
            "error": f"获取任务队列失败: {str(e)}",
            "current_task": None,
            "queue_size": 0,
            "queue_length": 0,
            "queued_tasks": [],
            "is_processing": False,
            "tasks": []
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



# ==================== Appeal Management ====================

@router.get("/appeals", response_model=List[AppealAdminInfo])
async def list_appeals(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    列出所有申诉
    """
    query = db.query(Appeal).join(User, Appeal.user_id == User.user_id)
    
    if status_filter and status_filter != 'all':
        query = query.filter(Appeal.status == status_filter)
        
    if search:
        query = query.filter(
            or_(
                Appeal.title.ilike(f"%{search}%"),
                Appeal.details.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%")
            )
        )
        
    appeals = query.order_by(
        Appeal.created_at.desc()
    ).offset(skip).limit(limit).all()

    result = []
    for appeal in appeals:
        user = db.query(User).filter(User.user_id == appeal.user_id).first()
        resolver = None
        if appeal.resolved_by:
            resolver = db.query(User).filter(User.user_id == appeal.resolved_by).first()
            
        result.append(AppealAdminInfo(
            appeal_id=appeal.appeal_id,
            user_id=appeal.user_id,
            username=user.username if user else "Unknown",
            session_id=appeal.session_id,
            title=appeal.title,
            details=appeal.details,
            status=appeal.status,
            created_at=appeal.created_at,
            resolved_at=appeal.resolved_at,
            resolved_by=resolver.username if resolver else None,
            admin_comment=appeal.admin_comment
        ))
    
    return result

@router.put("/appeals/{appeal_id}")
async def process_appeal(
    appeal_id: str,
    request: ProcessAppealRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    处理申诉
    """
    appeal = db.query(Appeal).filter(Appeal.appeal_id == appeal_id).first()
    
    if not appeal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="申诉不存在"
        )
        
    if request.status not in ["pending", "resolved", "ignored"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的状态"
        )
        
    appeal.status = request.status
    appeal.admin_comment = request.comment
    appeal.resolved_at = datetime.utcnow()
    appeal.resolved_by = admin_user.user_id
    
    db.commit()
    
    return {"message": "申诉已处理", "appeal_id": appeal_id, "status": appeal.status}


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
    # 统计有效会话（包含消息的会话）
    total_sessions = db.query(ChatSession).join(Message).distinct().count()
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
