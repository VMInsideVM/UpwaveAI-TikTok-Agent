"""
SQLAlchemy ORM Models for FastMoss MVP
数据库模型定义
"""
from sqlalchemy import Boolean, Column, String, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship, declarative_base
import uuid
import sys
from pathlib import Path

# 添加项目根目录到路径，以便导入 utils.timezone
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.timezone import now_naive

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
    created_at = Column(DateTime, default=now_naive, nullable=False)
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
    created_at = Column(DateTime, default=now_naive, nullable=False)
    updated_at = Column(DateTime, default=now_naive, onupdate=now_naive, nullable=False)
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
    created_at = Column(DateTime, default=now_naive, nullable=False)

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
    created_at = Column(DateTime, default=now_naive, nullable=False)
    updated_at = Column(DateTime, default=now_naive, onupdate=now_naive, nullable=False)

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
    created_at = Column(DateTime, default=now_naive, nullable=False)
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
    created_at = Column(DateTime, default=now_naive, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)  # 5分钟后过期

    # 关联用户（可选，仅在已登录情况下）
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=True)

    # Relationship
    user = relationship("User", back_populates="sms_verifications")

    @property
    def is_expired(self):
        """验证码是否已过期"""
        return now_naive() > self.expires_at

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
    total_credits = Column(Integer, default=0, nullable=False)  # 总积分（默认0积分）
    used_credits = Column(Integer, default=0, nullable=False)  # 已使用积分
    total_tokens_used = Column(Integer, default=0, nullable=False)  # ⭐ 新增：总Token消耗
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
    change_type = Column(String(20), nullable=False, index=True)  # 'add', 'deduct', 'refund', 'recharge', 'refund_deduct'
    amount = Column(Integer, nullable=False)  # 变动数量（正数为增加，负数为扣除）
    before_credits = Column(Integer, nullable=False)  # 变动前积分
    after_credits = Column(Integer, nullable=False)  # 变动后积分
    reason = Column(String(200))  # 变动原因
    related_report_id = Column(String(36), ForeignKey("reports.report_id"))  # 关联的报告ID（如果有）
    related_order_id = Column(String(36), ForeignKey("orders.order_id"))  # 关联的订单ID（充值/退款）
    created_at = Column(DateTime, default=now_naive, nullable=False, index=True)
    meta_data = Column(JSON)  # 其他元数据

    # Relationships
    user = relationship("User")
    report = relationship("Report")
    order = relationship("Order", foreign_keys=[related_order_id])

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
    created_at = Column(DateTime, default=now_naive, nullable=False)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    meta_data = Column(JSON)  # 其他元数据（如产品名称、达人数量等）

    # 分享配置
    share_mode = Column(String(20), default="private", nullable=False, index=True)
    # private(不公开), public(完全公开), password(密码保护)
    share_password = Column(String(128))  # 分享密码（加密存储）
    share_expires_at = Column(DateTime, index=True)  # 分享过期时间
    share_created_at = Column(DateTime)  # 分享创建时间

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
    
    created_at = Column(DateTime, default=now_naive, nullable=False)
    resolved_at = Column(DateTime)
    resolved_by = Column(String(36), ForeignKey("users.user_id"), nullable=True)  # 处理管理员ID

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="appeals")
    session = relationship("ChatSession")
    admin = relationship("User", foreign_keys=[resolved_by])

    def __repr__(self):
        return f"<Appeal {self.appeal_id} - {self.title} ({self.status})>"


class TokenUsage(Base):
    """Token 使用记录表"""
    __tablename__ = "token_usage"

    usage_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=True, index=True)
    message_id = Column(String(36), nullable=True)

    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    model_name = Column(String(50))

    created_at = Column(DateTime, default=now_naive, nullable=False, index=True)

    # Relationships
    user = relationship("User")
    session = relationship("ChatSession")

    def __repr__(self):
        return f"<TokenUsage {self.user_id} - {self.total_tokens}>"


class Order(Base):
    """充值订单表"""
    __tablename__ = "orders"

    order_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_no = Column(String(32), unique=True, nullable=False, index=True)  # 系统订单号
    user_id = Column(String(36), ForeignKey("users.user_id"), nullable=False, index=True)

    # 套餐信息
    tier_id = Column(String(20), nullable=False)  # tier_299, tier_599, tier_999, tier_1799
    amount_yuan = Column(Integer, nullable=False)  # 金额（元）
    credits = Column(Integer, nullable=False)  # 积分数量

    # 支付信息
    payment_method = Column(String(20), nullable=False)  # 'alipay', 'wechat'
    payment_status = Column(String(20), default="pending", nullable=False, index=True)
    # pending(待支付), paid(已支付), cancelled(已取消), refunded(已退款), partial_refunded(部分退款)

    # 第三方支付信息
    trade_no = Column(String(64))  # 支付宝/微信交易号
    qr_code_url = Column(Text)  # 支付二维码URL

    # 时间戳
    created_at = Column(DateTime, default=now_naive, nullable=False, index=True)
    paid_at = Column(DateTime)
    expired_at = Column(DateTime)  # 订单过期时间（15分钟后）

    # 元数据
    meta_data = Column(JSON)  # IP地址、设备信息等

    # Relationships
    user = relationship("User", backref="orders")
    refunds = relationship("Refund", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order {self.order_no} - {self.amount_yuan}元 ({self.payment_status})>"


class Refund(Base):
    """退款记录表"""
    __tablename__ = "refunds"

    refund_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.order_id"), nullable=False, index=True)

    # 退款信息
    refund_no = Column(String(32), unique=True, nullable=False, index=True)  # 系统退款单号
    refund_amount_yuan = Column(Integer, nullable=False)  # 退款金额（元）
    refund_credits = Column(Integer, nullable=False)  # 扣回的积分

    # 状态
    status = Column(String(20), default="pending", nullable=False, index=True)
    # pending(待审核), rejected(已拒绝), processing(退款中), success(已退款), failed(退款失败)

    # 原因和审批
    reason = Column(Text, nullable=False)
    admin_id = Column(String(36), ForeignKey("users.user_id"))  # 处理管理员

    # 第三方退款信息
    refund_trade_no = Column(String(64))  # 支付平台退款交易号
    error_message = Column(Text)  # 退款失败原因

    # 时间戳
    created_at = Column(DateTime, default=now_naive, nullable=False, index=True)
    processed_at = Column(DateTime)

    # 元数据
    meta_data = Column(JSON)

    # Relationships
    order = relationship("Order", back_populates="refunds")
    admin = relationship("User", foreign_keys=[admin_id])

    def __repr__(self):
        return f"<Refund {self.refund_no} - {self.refund_amount_yuan}元 ({self.status})>"


class SecurityLog(Base):
    """安全事件日志表"""
    __tablename__ = "security_logs"

    log_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="SET NULL"))
    event_type = Column(String(50), nullable=False)  # rate_limit, content_violation, etc.
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    ip_address = Column(String(45))
    device_fingerprint = Column(String(64))
    event_details = Column(JSON)
    created_at = Column(DateTime, default=now_naive, nullable=False, index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<SecurityLog {self.event_type} - {self.severity}>"


class UserRiskScore(Base):
    """用户风险评分表"""
    __tablename__ = "user_risk_scores"

    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    risk_score = Column(Integer, default=0, nullable=False)  # 0-100
    violation_count = Column(Integer, default=0, nullable=False)
    last_violation_at = Column(DateTime)
    is_blocked = Column(Boolean, default=False, nullable=False, index=True)
    blocked_until = Column(DateTime)
    blocked_reason = Column(Text)
    updated_at = Column(DateTime, default=now_naive, onupdate=now_naive, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self):
        return f"<UserRiskScore {self.user_id} - {self.risk_score}>"


class IPBlacklist(Base):
    """IP黑名单表"""
    __tablename__ = "ip_blacklist"

    ip_address = Column(String(45), primary_key=True)
    reason = Column(Text, nullable=False)
    blocked_at = Column(DateTime, default=now_naive, nullable=False)
    expires_at = Column(DateTime)
    created_by = Column(String(36), ForeignKey("users.user_id", ondelete="SET NULL"))

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<IPBlacklist {self.ip_address}>"


class DeviceBlacklist(Base):
    """设备黑名单表"""
    __tablename__ = "device_blacklist"

    device_fingerprint = Column(String(64), primary_key=True)
    reason = Column(Text, nullable=False)
    blocked_at = Column(DateTime, default=now_naive, nullable=False)
    expires_at = Column(DateTime)
    created_by = Column(String(36), ForeignKey("users.user_id", ondelete="SET NULL"))

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<DeviceBlacklist {self.device_fingerprint[:8]}...>"
