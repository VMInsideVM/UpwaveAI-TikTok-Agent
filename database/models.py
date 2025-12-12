"""
SQLAlchemy ORM Models for FastMoss MVP
数据库模型定义
"""
from sqlalchemy import Boolean, Column, String, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    """用户表"""
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=True, nullable=False)  # 默认激活，跳过邮箱验证
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime)

    # Relationships
    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    usage_info = relationship("UserUsage", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")
    created_codes = relationship("InvitationCode", foreign_keys="InvitationCode.created_by_admin", back_populates="creator")

    def __repr__(self):
        return f"<User {self.username} ({self.user_id})>"


class ChatSession(Base):
    """聊天会话表"""
    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    title = Column(String(200), default="新对话")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    meta_data = Column(JSON)  # 存储额外信息，如 JSON 文件路径

    # Relationships
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")
    # TODO: 添加 cascade="all, delete-orphan" 以自动删除关联报告（需要数据库迁移）
    # 当前在 session_manager_db.py 的 delete_session 中手动删除报告
    report = relationship("Report", back_populates="session", uselist=False)

    def __repr__(self):
        return f"<ChatSession {self.session_id} - {self.title}>"


class Message(Base):
    """消息表"""
    __tablename__ = "messages"

    message_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")  # text, image, etc.
    attachments = Column(JSON)  # 附件信息
    meta_data = Column(JSON)  # 其他元数据
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.message_id} - {self.role}>"


class Task(Base):
    """任务表（用于追踪后台任务）"""
    __tablename__ = "tasks"

    task_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.session_id"), index=True)
    task_type = Column(String(50), nullable=False)  # report_generation, data_scraping, etc.
    status = Column(String(20), default="pending", nullable=False)  # pending, running, completed, failed
    progress = Column(JSON)  # 进度信息
    result = Column(JSON)  # 结果数据
    error = Column(JSON)  # 错误信息
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Task {self.task_id} - {self.task_type} ({self.status})>"


class InvitationCode(Base):
    """邀请码表"""
    __tablename__ = "invitation_codes"

    code_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(16), unique=True, nullable=False, index=True)
    is_used = Column(Boolean, default=False, nullable=False)
    created_by_admin = Column(String(36), ForeignKey("users.user_id"), nullable=False)
    used_by_user = Column(String(36), ForeignKey("users.user_id"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    used_at = Column(DateTime)
    expires_at = Column(DateTime)  # NULL = 永久有效

    # Relationships
    creator = relationship("User", foreign_keys=[created_by_admin], back_populates="created_codes")
    user = relationship("User", foreign_keys=[used_by_user])

    def __repr__(self):
        return f"<InvitationCode {self.code} - Used: {self.is_used}>"


class UserUsage(Base):
    """用户配额表"""
    __tablename__ = "user_usage"

    usage_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), unique=True, nullable=False, index=True)
    total_quota = Column(Integer, default=1, nullable=False)  # 总配额
    used_count = Column(Integer, default=0, nullable=False)  # 已使用次数
    last_reset_date = Column(DateTime)  # 仅用于记录，不自动重置（永久累计）

    # Relationships
    user = relationship("User", back_populates="usage_info")

    @property
    def remaining_quota(self):
        """剩余配额"""
        return max(0, self.total_quota - self.used_count)

    def __repr__(self):
        return f"<UserUsage {self.user_id} - {self.remaining_quota}/{self.total_quota}>"


class Report(Base):
    """报告表"""
    __tablename__ = "reports"

    report_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    report_path = Column(String(500), nullable=False)  # 报告文件路径
    status = Column(String(20), default="queued", nullable=False, index=True)  # queued, generating, completed, failed
    estimated_time = Column(Integer)  # 预计生成时间（秒）
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    meta_data = Column(JSON)  # 其他元数据（如产品名称、达人数量等）

    # Relationships
    user = relationship("User", back_populates="reports")
    session = relationship("ChatSession", back_populates="report")

    def __repr__(self):
        return f"<Report {self.report_id} - {self.title} ({self.status})>"
