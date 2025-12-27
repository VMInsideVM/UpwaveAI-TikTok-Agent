"""
Authentication API Endpoints
认证 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime, timedelta
from utils.timezone import now_naive
from typing import Optional
import secrets

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
from services.sms_service import get_sms_service
from utils.security import get_client_ip, generate_device_fingerprint, rate_limiter
from services.security_service import security_service

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
    remaining_credits: int
    total_credits: int
    phone_number: Optional[str] = None


# ==================== SMS 认证相关模型 ====================

class SendSMSRequest(BaseModel):
    """发送短信验证码请求"""
    phone_number: str
    code_type: str  # 'register', 'reset_password', 'change_phone'

    @validator('phone_number')
    def phone_validator(cls, v):
        import re
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('请输入正确的11位中国大陆手机号')
        return v

    @validator('code_type')
    def code_type_validator(cls, v):
        if v not in ['register', 'reset_password', 'change_phone']:
            raise ValueError('验证码类型错误')
        return v


class PhoneRegisterRequest(BaseModel):
    """手机号注册请求"""
    phone_number: str
    password: str
    sms_code: str
    username: Optional[str] = None  # 可选
    email: Optional[EmailStr] = None  # 可选

    @validator('phone_number')
    def phone_validator(cls, v):
        import re
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('请输入正确的11位中国大陆手机号')
        return v

    @validator('sms_code')
    def code_validator(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('请输入6位数字验证码')
        return v

    @validator('username')
    def username_validator(cls, v):
        if v is None:
            return v  # 允许为空
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在 3-50 个字符之间')
        if not v.replace('_', '').isalnum():
            raise ValueError('用户名只能包含字母、数字和下划线')
        return v


class PhoneLoginRequest(BaseModel):
    """手机号或用户名登录请求"""
    identifier: str  # 手机号或用户名
    password: str


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    phone_number: str
    sms_code: str
    new_password: str

    @validator('phone_number')
    def phone_validator(cls, v):
        import re
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('请输入正确的11位中国大陆手机号')
        return v


class ChangePhoneRequest(BaseModel):
    """修改手机号请求"""
    new_phone_number: str
    sms_code: str

    @validator('new_phone_number')
    def phone_validator(cls, v):
        import re
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('请输入正确的11位中国大陆手机号')
        return v


class ChangePasswordRequest(BaseModel):
    """修改密码请求（已登录用户）"""
    old_password: str
    new_password: str


class UpdateEmailRequest(BaseModel):
    """更新邮箱请求"""
    new_email: EmailStr


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
    if invitation.expires_at and invitation.expires_at < now_naive():
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
            total_credits=0,
            used_credits=0
        )
        db.add(usage)

        # 7. 标记邀请码为已使用
        invitation.is_used = True
        invitation.used_by_user = new_user.user_id
        invitation.used_at = now_naive()

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
    user.last_login = now_naive()
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
    # 获取积分信息
    usage = db.query(UserUsage).filter(UserUsage.user_id == current_user.user_id).first()

    if not usage:
        # 如果没有积分记录，创建一个（默认300积分）
        usage = UserUsage(
            user_id=current_user.user_id,
            total_credits=0,
            used_credits=0
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
        remaining_credits=usage.remaining_credits,
        total_credits=usage.total_credits,
        phone_number=current_user.phone_number
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


# ==================== SMS 认证端点 ====================

@router.post("/send-sms-code")
async def send_sms_code(
    request: SendSMSRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    发送短信验证码

    支持类型:
    - register: 注册验证码
    - reset_password: 密码重置验证码
    - change_phone: 修改手机号验证码（需登录）
    """
    # 获取客户端 IP
    ip_address = http_request.client.host

    # 如果是修改手机号，无需检查手机号是否已注册
    if request.code_type != 'change_phone':
        # 检查手机号是否已注册
        existing_user = db.query(User).filter(User.phone_number == request.phone_number).first()

        if request.code_type == 'register' and existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该手机号已被注册"
            )

        if request.code_type == 'reset_password' and not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="该手机号未注册"
            )

    # 发送验证码
    sms_service = get_sms_service()
    success, message = await sms_service.send_verification_code(
        db=db,
        phone=request.phone_number,
        code_type=request.code_type,
        ip_address=ip_address
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message
        )

    return {
        "message": message,
        "phone_number": request.phone_number,
        "expires_in_minutes": 5
    }


@router.post("/register-phone", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_with_phone(
    request: PhoneRegisterRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    使用手机号注册

    只需要短信验证码（已移除邀请码要求）
    """
    # 0. 获取IP和设备指纹
    client_ip = get_client_ip(http_request)
    device_fp = generate_device_fingerprint(http_request)

    # 0.1 检查IP是否被封禁
    is_blocked, reason = security_service.check_ip_blocked(db, client_ip)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"该IP已被封禁: {reason}"
        )

    # 0.2 检查设备是否被封禁
    is_blocked, reason = security_service.check_device_blocked(db, device_fp)
    if is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"该设备已被封禁: {reason}"
        )

    # 0.3 检查IP注册频率限制（每小时最多3次，每天最多5次）
    allowed, remaining = rate_limiter.check_rate_limit(
        key=f"register_ip_hour:{client_ip}",
        max_requests=3,
        window_seconds=3600
    )
    if not allowed:
        security_service.log_security_event(
            db=db,
            event_type="rate_limit_exceeded",
            severity="medium",
            ip_address=client_ip,
            device_fingerprint=device_fp,
            event_details={"action": "register", "limit": "hourly"}
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="注册过于频繁，请稍后再试（每小时最多3次）"
        )

    allowed, remaining = rate_limiter.check_rate_limit(
        key=f"register_ip_day:{client_ip}",
        max_requests=5,
        window_seconds=86400
    )
    if not allowed:
        security_service.log_security_event(
            db=db,
            event_type="rate_limit_exceeded",
            severity="high",
            ip_address=client_ip,
            device_fingerprint=device_fp,
            event_details={"action": "register", "limit": "daily"}
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="注册过于频繁，请明天再试（每天最多5次）"
        )

    # 0.4 检查设备注册频率（每天最多2次）
    allowed, remaining = rate_limiter.check_rate_limit(
        key=f"register_device:{device_fp}",
        max_requests=2,
        window_seconds=86400
    )
    if not allowed:
        security_service.log_security_event(
            db=db,
            event_type="rate_limit_exceeded",
            severity="high",
            ip_address=client_ip,
            device_fingerprint=device_fp,
            event_details={"action": "register", "limit": "device_daily"}
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="该设备今日注册次数已达上限"
        )

    # 1. 验证短信验证码（强制验证）
    sms_service = get_sms_service()
    is_valid, message, _ = sms_service.verify_code(
        db=db,
        phone=request.phone_number,
        code=request.sms_code,
        code_type='register'
    )

    if not is_valid:
        security_service.log_security_event(
            db=db,
            event_type="invalid_sms_code",
            severity="low",
            ip_address=client_ip,
            device_fingerprint=device_fp,
            event_details={"phone": request.phone_number, "error": message}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    # 3. 检查手机号是否已存在
    existing_phone = db.query(User).filter(User.phone_number == request.phone_number).first()
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该手机号已被注册"
        )

    # 4. 生成用户名（如果未提供）
    username = request.username
    if not username:
        username = f"user_{secrets.token_hex(6)}"

        # 确保生成的用户名不重复
        while db.query(User).filter(User.username == username).first():
            username = f"user_{secrets.token_hex(6)}"
    else:
        # 检查用户名是否已存在
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

    # 4. 检查邮箱（如果提供）
    if request.email:
        existing_email = db.query(User).filter(User.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )

    # 5. 验证密码强度
    is_valid, error_msg = validate_password_strength(request.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # 6. 创建用户
    try:
        hashed_pw = hash_password(request.password)

        new_user = User(
            phone_number=request.phone_number,
            username=username,
            email=request.email,
            hashed_password=hashed_pw,
            is_active=True,
            is_verified=True,
            is_admin=False
        )

        db.add(new_user)
        db.flush()

        # 7. 创建积分记录（默认0积分）
        usage = UserUsage(
            user_id=new_user.user_id,
            total_credits=0,
            used_credits=0
        )
        db.add(usage)

        db.commit()

        # 7.5 记录注册成功的安全日志
        security_service.log_security_event(
            db=db,
            event_type="registration",
            severity="low",
            user_id=new_user.user_id,
            ip_address=client_ip,
            device_fingerprint=device_fp,
            event_details={
                "phone": request.phone_number,
                "username": username,
                "success": True
            }
        )

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


@router.post("/login-phone", response_model=TokenResponse)
async def login_with_phone_or_username(
    request: PhoneLoginRequest,
    db: Session = Depends(get_db)
):
    """
    使用手机号或用户名登录

    identifier 可以是:
    - 手机号 (11位数字)
    - 用户名
    """
    # 判断是手机号还是用户名
    import re
    is_phone = bool(re.match(r'^1[3-9]\d{9}$', request.identifier))

    # 查找用户
    if is_phone:
        user = db.query(User).filter(User.phone_number == request.identifier).first()
    else:
        user = db.query(User).filter(User.username == request.identifier).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号/用户名或密码错误"
        )

    # 验证密码
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号/用户名或密码错误"
        )

    # 检查激活状态
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被停用"
        )

    # 更新最后登录时间
    user.last_login = now_naive()
    db.commit()

    # 生成令牌
    access_token = create_access_token(data={"sub": user.user_id})
    refresh_token = create_refresh_token(data={"sub": user.user_id})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        username=user.username,
        is_admin=user.is_admin
    )


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    通过短信验证码重置密码
    """
    # 1. 验证短信验证码
    sms_service = get_sms_service()
    is_valid, message, _ = sms_service.verify_code(
        db=db,
        phone=request.phone_number,
        code=request.sms_code,
        code_type='reset_password'
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    # 2. 查找用户
    user = db.query(User).filter(User.phone_number == request.phone_number).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该手机号未注册"
        )

    # 3. 验证新密码强度
    is_valid, error_msg = validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # 4. 更新密码
    user.hashed_password = hash_password(request.new_password)
    db.commit()

    return {
        "message": "密码重置成功",
        "phone_number": request.phone_number
    }


@router.post("/change-phone")
async def change_phone_number(
    request: ChangePhoneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    修改绑定的手机号
    需要新手机号的短信验证码
    """
    # 1. 验证短信验证码
    sms_service = get_sms_service()
    is_valid, message, _ = sms_service.verify_code(
        db=db,
        phone=request.new_phone_number,
        code=request.sms_code,
        code_type='change_phone'
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )

    # 2. 检查新手机号是否已被使用
    existing_user = db.query(User).filter(
        User.phone_number == request.new_phone_number,
        User.user_id != current_user.user_id
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该手机号已被其他用户使用"
        )

    # 3. 记录修改历史
    old_phone = current_user.phone_number
    change_record = {
        "old": old_phone,
        "new": request.new_phone_number,
        "changed_at": now_naive().isoformat()
    }

    if current_user.phone_change_history:
        history = current_user.phone_change_history
        if isinstance(history, list):
            history.append(change_record)
        else:
            history = [change_record]
        current_user.phone_change_history = history
    else:
        current_user.phone_change_history = [change_record]

    # 4. 更新手机号
    current_user.phone_number = request.new_phone_number
    db.commit()

    return {
        "message": "手机号修改成功",
        "old_phone": old_phone,
        "new_phone": request.new_phone_number
    }


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    修改密码（已登录用户）
    需要验证旧密码
    """
    # 1. 验证旧密码
    if not verify_password(request.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码错误"
        )

    # 2. 验证新密码与旧密码不同
    if verify_password(request.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同"
        )

    # 3. 验证新密码强度
    is_valid, error_msg = validate_password_strength(request.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # 4. 更新密码
    current_user.hashed_password = hash_password(request.new_password)
    db.commit()

    return {
        "message": "密码修改成功",
        "username": current_user.username
    }


@router.post("/update-email")
async def update_email(
    request: UpdateEmailRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新邮箱地址（已登录用户）
    """
    # 1. 检查邮箱是否已被其他用户使用
    existing_user = db.query(User).filter(
        User.email == request.new_email,
        User.user_id != current_user.user_id
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被其他用户使用"
        )

    # 2. 更新邮箱
    current_user.email = request.new_email
    db.commit()

    return {
        "message": "邮箱更新成功",
        "new_email": request.new_email
    }
