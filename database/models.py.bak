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

    # 手机号认证字段（新增）
    phone_number = Column(String(11), unique=True, nullable=True, index=True)  # 允许 NULL（向后兼容）

    # 用户名和邮箱改为可选（向后兼容）
    username = Column(String(50), unique=True, nullable=True, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)

    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=True, nullable=False)  # 默认激活，跳过邮箱验证
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login = Column(DateTime)

    # 手机号修改历史（新增）
    phone_change_history = Column(JSON)  # 存储手机号修改记录

    # Relationships
    sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    usage_info = relationship("UserUsage", back_populates="user", uselist=False, cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")
    created_codes = relationship("InvitationCode", foreign_keys="InvitationCode.created_by_admin", back_populates="creator")
    sms_verifications = relationship("SMSVerification", back_populates="user", cascade="all, delete-orphan")  # 新增关系

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


class SMSVerification(Base):
    """短信验证码表"""
    __tablename__ = "sms_verifications"

    verification_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number = Column(String(11), nullable=False, index=True)
    code = Column(String(64), nullable=False)  # 存储哈希后的验证码（bcrypt）
    code_type = Column(String(20), nullable=False, index=True)  # 'register', 'reset_password', 'change_phone'

    # 验证状态
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime)

    # 验证尝试次数
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)

    # IP 限流
    ip_address = Column(String(45))  # 支持 IPv6

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)  # 5分钟后过期

    # 关联用户（可选，仅在已登录情况下）
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)

    # Relationship
    user = relationship("User", back_populates="sms_verifications")

    @property
    def is_expired(self):
        """验证码是否已过期"""
        return datetime.utcnow() > self.expires_at

    @property
    def is_locked(self):
        """是否因尝试次数过多而锁定"""
        return self.attempt_count >= self.max_attempts

    @property
    def remaining_attempts(self):
        """剩余尝试次数"""
        return max(0, self.max_attempts - self.attempt_count)

    def __repr__(self):
        return f"<SMSVerification {self.phone_number} - {self.code_type} ({self.is_verified})>"


class UserUsage(Base):
    """用户积分表"""
    __tablename__ = "user_usage"

    usage_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), unique=True, nullable=False, index=True)
    total_credits = Column(Integer, default=300, nullable=False)  # 总积分（默认300积分，可查询3个达人，每个达人100积分）
    used_credits = Column(Integer, default=0, nullable=False)  # 已使用积分
    last_reset_date = Column(DateTime)  # 仅用于记录，不自动重置（永久累计）

    # Relationships
    user = relationship("User", back_populates="usage_info")

    @property
    def remaining_credits(self):
        """剩余积分"""
        return max(0, self.total_credits - self.used_credits)

    def __repr__(self):
        return f"<UserUsage {self.user_id} - {self.remaining_credits}/{self.total_credits} credits>"


class CreditHistory(Base):
    """积分变动历史表"""
    __tablename__ = "credit_history"

    history_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    change_type = Column(String(20), nullable=False, index=True)  # 'add', 'deduct', 'refund'
    amount = Column(Integer, nullable=False)  # 变动数量（正数为增加，负数为扣除）
    before_credits = Column(Integer, nullable=False)  # 变动前积分
    after_credits = Column(Integer, nullable=False)  # 变动后积分
    reason = Column(String(200))  # 变动原因
    related_report_id = Column(String(36), ForeignKey("reports.report_id"))  # 关联的报告ID（如果有）
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    meta_data = Column(JSON)  # 其他元数据

    # Relationships
    user = relationship("User")
    report = relationship("Report")

    def __repr__(self):
        return f"<CreditHistory {self.user_id} {self.change_type} {self.amount} credits>"


class Report(Base):
    """报告表"""
    __tablename__ = "reports"

    report_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    report_path = Column(String(500), nullable=False)  # 报告文件路径
    status = Column(String(20), default="queued", nullable=False, index=True)  # queued, generating, completed, failed
    progress = Column(Integer, default=0)  # 总进度百分比 (0-100) - 保留用于兼容性

    # 新增：两个独立的进度条
    scraping_progress = Column(Integer, default=0)  # 爬取达人数据的进度 (0-100)
    scraping_eta = Column(Integer)  # 爬取阶段预计剩余时间（秒）
    report_progress = Column(Integer, default=0)  # 报告生成的进度 (0-100)
    report_eta = Column(Integer)  # 报告生成阶段预计剩余时间（秒）

    estimated_time = Column(Integer)  # 总预计生成时间（秒）- 保留用于兼容性
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    meta_data = Column(JSON)  # 其他元数据（如产品名称、达人数量等）

    # Relationships
    user = relationship("User", back_populates="reports")
    session = relationship("ChatSession", back_populates="report")

    def __repr__(self):
        return f"<Report {self.report_id} - {self.title} ({self.status})>"


class Appeal(Base):
    """用户申诉表"""
    __tablename__ = "appeals"

    appeal_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=True)  # 可选关联会话
    title = Column(String(200), nullable=False)
    details = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, resolved, ignored
    admin_comment = Column(Text)  # 管理员回复/备注
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)  # 处理管理员ID

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="appeals")
    session = relationship("ChatSession")
    admin = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self):
        return f"<Appeal {self.appeal_id} - {self.title} ({self.status})>"
