"""
Authentication API Endpoints
认证 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime, timedelta
from typing import Optional

from database.connection import get_db
from database.models import User, UserUsage, InvitationCode
from auth.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_token
)
from auth.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ==================== Pydantic Models ====================

class RegisterRequest(BaseModel):
    """注册请求"""
    username: str
    email: EmailStr
    password: str
    invitation_code: str

    @validator('username')
    def username_validator(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在 3-50 个字符之间')
        if not v.isalnum() and '_' not in v:
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    is_admin: bool


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    user_id: str
    username: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    remaining_quota: int
    total_quota: int


# ==================== API Endpoints ====================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    用户注册

    需要邀请码
    """
    # 1. 验证邀请码
    invitation = db.query(InvitationCode).filter(
        InvitationCode.code == request.invitation_code
    ).first()

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码不存在"
        )

    if invitation.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已被使用"
        )

    # 检查邀请码是否过期（expires_at 为 NULL 表示永久有效）
    if invitation.expires_at and invitation.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码已过期"
        )

    # 2. 检查用户名是否已存在
    existing_username = db.query(User).filter(User.username == request.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )

    # 3. 检查邮箱是否已存在
    existing_email = db.query(User).filter(User.email == request.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )

    # 4. 验证密码强度
    is_valid, error_msg = validate_password_strength(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # 5. 创建用户
    try:
        hashed_pw = hash_password(request.password)

        new_user = User(
            username=request.username,
            email=request.email,
            hashed_password=hashed_pw,
            is_active=True,
            is_verified=True,  # 跳过邮箱验证
            is_admin=False
        )

        db.add(new_user)
        db.flush()  # 获取 user_id

        # 6. 创建配额记录
        usage = UserUsage(
            user_id=new_user.user_id,
            total_quota=1,  # 默认 1 次
            used_count=0
        )
        db.add(usage)

        # 7. 标记邀请码为已使用
        invitation.is_used = True
        invitation.used_by_user = new_user.user_id
        invitation.used_at = datetime.utcnow()

        db.commit()

        # 8. 生成令牌
        access_token = create_access_token(data={"sub": new_user.user_id})
        refresh_token = create_refresh_token(data={"sub": new_user.user_id})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=new_user.user_id,
            username=new_user.username,
            is_admin=new_user.is_admin
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    用户登录

    返回访问令牌和刷新令牌
    """
    # 1. 查找用户
    user = db.query(User).filter(User.username == request.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 2. 验证密码
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )

    # 3. 检查用户是否激活
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被停用"
        )

    # 4. 更新最后登录时间
    user.last_login = datetime.utcnow()
    db.commit()

    # 5. 生成令牌
    access_token = create_access_token(data={"sub": user.user_id})
    refresh_token = create_refresh_token(data={"sub": user.user_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        username=user.username,
        is_admin=user.is_admin
    )


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户信息
    """
    # 获取配额信息
    usage = db.query(UserUsage).filter(UserUsage.user_id == current_user.user_id).first()

    if not usage:
        # 如果没有配额记录，创建一个
        usage = UserUsage(
            user_id=current_user.user_id,
            total_quota=1,
            used_count=0
        )
        db.add(usage)
        db.commit()

    return UserInfoResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        is_admin=current_user.is_admin,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        remaining_quota=usage.remaining_quota,
        total_quota=usage.total_quota
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    使用刷新令牌获取新的访问令牌
    """
    # 1. 解码刷新令牌
    payload = decode_token(request.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )

    # 2. 检查令牌类型
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误"
        )

    # 3. 获取用户
    user_id = payload.get("sub")
    user = db.query(User).filter(User.user_id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被停用"
        )

    # 4. 生成新的访问令牌
    access_token = create_access_token(data={"sub": user.user_id})

    # 可选：也可以生成新的刷新令牌
    new_refresh_token = create_refresh_token(data={"sub": user.user_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user_id=user.user_id,
        username=user.username,
        is_admin=user.is_admin
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    用户登出

    注意：JWT 是无状态的，服务器端不存储令牌
    实际的登出操作由客户端完成（删除本地存储的令牌）
    """
    return {
        "message": "登出成功",
        "detail": "请在客户端删除 access_token 和 refresh_token"
    }
