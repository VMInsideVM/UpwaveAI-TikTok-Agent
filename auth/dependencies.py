"""
FastAPI Authentication Dependencies
FastAPI 认证依赖
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from database.connection import get_db
from database.models import User
from auth.security import decode_token

# HTTP Bearer 认证方案
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    从 JWT 令牌中提取当前用户

    Args:
        credentials: HTTP Authorization 头中的凭据
        db: 数据库会话

    Returns:
        User: 当前用户对象

    Raises:
        HTTPException: 令牌无效或用户不存在
    """
    token = credentials.credentials

    # 解码令牌
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查令牌类型
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 获取用户 ID
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中缺少用户信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 从数据库查询用户
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    确保当前用户是激活状态

    Args:
        current_user: 当前用户

    Returns:
        User: 激活的用户

    Raises:
        HTTPException: 用户未激活
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账户已被停用"
        )

    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    确保当前用户是管理员

    Args:
        current_user: 当前用户

    Returns:
        User: 管理员用户

    Raises:
        HTTPException: 用户不是管理员
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    可选的用户认证（如果有令牌则返回用户，否则返回 None）

    Args:
        credentials: HTTP Authorization 头中的凭据（可选）
        db: 数据库会话

    Returns:
        Optional[User]: 用户对象或 None
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = decode_token(token)

        if payload is None or payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if user_id is None:
            return None

        user = db.query(User).filter(User.user_id == user_id).first()
        return user

    except Exception:
        return None
