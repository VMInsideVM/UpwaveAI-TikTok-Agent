"""
Security Utilities
安全工具（密码加密、JWT 令牌）
"""
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Tuple
import os
import re

# 密码加密上下文
# bcrypt 有 72 字节限制，我们在应用层处理
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__default_rounds=12
)

# JWT 配置
# 安全警告：JWT_SECRET_KEY 必须在生产环境中设置为强随机密钥
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    # 开发环境允许使用默认值，但会发出警告
    import sys
    _is_dev = os.getenv("ENVIRONMENT", "development").lower() in ("development", "dev", "local")
    if _is_dev:
        JWT_SECRET_KEY = "dev-only-secret-key-not-for-production"
        print("⚠️  警告: 使用开发环境默认 JWT_SECRET_KEY，请勿在生产环境使用！", file=sys.stderr)
    else:
        print("❌ 错误: 生产环境必须设置 JWT_SECRET_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def _truncate_password(password: str) -> str:
    """
    截断密码到 72 字节（bcrypt 限制）

    Args:
        password: 明文密码

    Returns:
        str: 截断后的密码
    """
    # bcrypt 限制为 72 字节
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # 截断到 72 字节，确保不会在 UTF-8 字符中间截断
        password_bytes = password_bytes[:72]
        # 尝试解码，如果失败则继续向前截断
        while len(password_bytes) > 0:
            try:
                return password_bytes.decode('utf-8')
            except UnicodeDecodeError:
                password_bytes = password_bytes[:-1]
        return ""
    return password


def hash_password(password: str) -> str:
    """
    哈希密码

    Args:
        password: 明文密码

    Returns:
        str: 哈希后的密码
    """
    # 先截断密码以满足 bcrypt 72 字节限制
    truncated = _truncate_password(password)
    return pwd_context.hash(truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        bool: 密码是否匹配
    """
    # 先截断密码以满足 bcrypt 72 字节限制
    truncated = _truncate_password(plain_password)
    return pwd_context.verify(truncated, hashed_password)


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    验证密码强度
    要求：至少8位，包含字母和数字

    Args:
        password: 待验证的密码

    Returns:
        Tuple[bool, str]: (是否通过, 错误消息)
    """
    if len(password) < 8:
        return False, "密码至少需要 8 位字符"

    # 检查是否包含字母
    if not re.search(r'[a-zA-Z]', password):
        return False, "密码必须包含字母"

    # 检查是否包含数字
    if not re.search(r'\d', password):
        return False, "密码必须包含数字"

    return True, ""


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌（Access Token）

    Args:
        data: 要编码的数据字典
        expires_delta: 过期时间差（可选）

    Returns:
        str: JWT 令牌
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    创建刷新令牌（Refresh Token）

    Args:
        data: 要编码的数据字典

    Returns:
        str: JWT 刷新令牌
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    解码 JWT 令牌

    Args:
        token: JWT 令牌字符串

    Returns:
        Optional[dict]: 解码后的数据，失败返回 None
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_token_type(token: str, expected_type: str) -> bool:
    """
    验证令牌类型

    Args:
        token: JWT 令牌
        expected_type: 期望的类型（'access' 或 'refresh'）

    Returns:
        bool: 类型是否匹配
    """
    payload = decode_token(token)
    if payload is None:
        return False

    return payload.get("type") == expected_type


if __name__ == "__main__":
    # 测试密码加密
    print("🔐 测试密码加密...")
    password = "Test123456"
    hashed = hash_password(password)
    print(f"原始密码: {password}")
    print(f"哈希密码: {hashed}")
    print(f"验证正确密码: {verify_password(password, hashed)}")
    print(f"验证错误密码: {verify_password('wrong', hashed)}")

    # 测试密码强度验证
    print("\n🔒 测试密码强度验证...")
    test_passwords = [
        "short",           # 太短
        "nonnumber",       # 无数字
        "12345678",        # 无字母
        "Valid123"         # 通过
    ]

    for pwd in test_passwords:
        is_valid, msg = validate_password_strength(pwd)
        status = "✅" if is_valid else "❌"
        print(f"{status} {pwd}: {msg if msg else '通过'}")

    # 测试 JWT
    print("\n🎫 测试 JWT...")
    data = {"user_id": "test123", "username": "testuser"}
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    print(f"Access Token: {access_token[:50]}...")
    print(f"Refresh Token: {refresh_token[:50]}...")

    decoded_access = decode_token(access_token)
    print(f"解码后的数据: {decoded_access}")
    print(f"Token 类型验证: {verify_token_type(access_token, 'access')}")
