"""
Database Connection Manager
数据库连接管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
import os
from pathlib import Path

from database.models import Base, User, UserUsage
from auth.security import hash_password

# 数据库 URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///chatbot.db")

# 创建引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False  # 设置为 True 可以看到 SQL 日志
)

# 创建 SessionLocal 类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 依赖注入函数
    获取数据库会话

    Usage:
        @app.get("/users")
        async def get_users(db: Session = Depends(get_db)):
            users = db.query(User).all()
            return users
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    非 FastAPI 场景使用的上下文管理器

    Usage:
        with get_db_context() as db:
            users = db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库
    创建所有表
    """
    # 确保数据库文件目录存在
    if "sqlite" in DATABASE_URL:
        db_path = DATABASE_URL.replace("sqlite:///", "")
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    # 创建所有表
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")


def create_admin_user(username: str, password: str, email: str) -> bool:
    """
    创建管理员用户（如果不存在）

    Args:
        username: 管理员用户名
        password: 管理员密码
        email: 管理员邮箱

    Returns:
        bool: True 表示创建成功或已存在，False 表示失败
    """
    with get_db_context() as db:
        # 检查是否已存在
        existing_user = db.query(User).filter(User.username == username).first()

        if existing_user:
            print(f"ℹ️  管理员用户 '{username}' 已存在")

            # 确保该用户是管理员
            if not existing_user.is_admin:
                existing_user.is_admin = True
                db.commit()
                print(f"✅ 已将用户 '{username}' 设置为管理员")

            return True

        # 创建新管理员
        try:
            hashed_pw = hash_password(password)

            admin_user = User(
                username=username,
                email=email,
                hashed_password=hashed_pw,
                is_admin=True,
                is_active=True,
                is_verified=True
            )

            db.add(admin_user)
            db.flush()  # 获取 user_id

            # 创建积分记录
            usage = UserUsage(
                user_id=admin_user.user_id,
                total_credits=999999,  # 管理员无限积分
                used_credits=0
            )

            db.add(usage)
            db.commit()

            print(f"✅ 管理员用户 '{username}' 创建成功")
            return True

        except Exception as e:
            db.rollback()
            print(f"❌ 创建管理员失败: {e}")
            return False


def reset_database():
    """
    重置数据库（删除所有表并重新创建）
    ⚠️ 危险操作！仅用于开发环境
    """
    print("⚠️  警告：即将删除所有数据表...")
    Base.metadata.drop_all(bind=engine)
    print("✅ 所有表已删除")

    init_db()
    print("✅ 数据库重置完成")


if __name__ == "__main__":
    # 测试数据库连接
    print("🔧 测试数据库连接...")

    # 初始化数据库
    init_db()

    # 创建管理员
    create_admin_user(
        username="admin",
        password="***REMOVED***",
        email="admin@example.com"
    )

    # 测试查询
    with get_db_context() as db:
        users = db.query(User).all()
        print(f"\n📊 当前用户数量: {len(users)}")
        for user in users:
            print(f"  - {user.username} (Admin: {user.is_admin})")
