"""
安全服务
Security Service for logging and risk management
"""
from sqlalchemy.orm import Session
from database.models import SecurityLog, UserRiskScore, IPBlacklist, DeviceBlacklist
from datetime import datetime, timedelta
from utils.timezone import now_naive
import uuid
import json


class SecurityService:
    """安全服务类"""

    @staticmethod
    def log_security_event(
        db: Session,
        event_type: str,
        severity: str,
        user_id: str = None,
        ip_address: str = None,
        device_fingerprint: str = None,
        event_details: dict = None
    ) -> SecurityLog:
        """记录安全事件"""
        log = SecurityLog(
            log_id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
            event_details=event_details
        )
        db.add(log)
        db.commit()
        return log

    @staticmethod
    def update_user_risk_score(
        db: Session,
        user_id: str,
        violation_increment: int = 1,
        risk_increment: int = 10
    ) -> UserRiskScore:
        """更新用户风险评分"""
        risk_score = db.query(UserRiskScore).filter(
            UserRiskScore.user_id == user_id
        ).first()

        if not risk_score:
            risk_score = UserRiskScore(
                user_id=user_id,
                risk_score=risk_increment,
                violation_count=violation_increment,
                last_violation_at=now_naive()
            )
            db.add(risk_score)
        else:
            risk_score.risk_score = min(100, risk_score.risk_score + risk_increment)
            risk_score.violation_count += violation_increment
            risk_score.last_violation_at = now_naive()

        db.commit()
        return risk_score

    @staticmethod
    def check_user_blocked(db: Session, user_id: str) -> tuple[bool, str]:
        """检查用户是否被封禁"""
        risk_score = db.query(UserRiskScore).filter(
            UserRiskScore.user_id == user_id
        ).first()

        if not risk_score:
            return False, None

        if not risk_score.is_blocked:
            return False, None

        # 检查是否永久封禁或临时封禁已过期
        if risk_score.blocked_until:
            if now_naive() > risk_score.blocked_until:
                # 解封
                risk_score.is_blocked = False
                risk_score.blocked_until = None
                db.commit()
                return False, None

        return True, risk_score.blocked_reason or "账号已被封禁"

    @staticmethod
    def check_ip_blocked(db: Session, ip_address: str) -> tuple[bool, str]:
        """检查IP是否被封禁"""
        blocked = db.query(IPBlacklist).filter(
            IPBlacklist.ip_address == ip_address
        ).first()

        if not blocked:
            return False, None

        # 检查是否过期
        if blocked.expires_at and now_naive() > blocked.expires_at:
            db.delete(blocked)
            db.commit()
            return False, None

        return True, blocked.reason

    @staticmethod
    def check_device_blocked(db: Session, device_fingerprint: str) -> tuple[bool, str]:
        """检查设备是否被封禁"""
        blocked = db.query(DeviceBlacklist).filter(
            DeviceBlacklist.device_fingerprint == device_fingerprint
        ).first()

        if not blocked:
            return False, None

        # 检查是否过期
        if blocked.expires_at and now_naive() > blocked.expires_at:
            db.delete(blocked)
            db.commit()
            return False, None

        return True, blocked.reason

    @staticmethod
    def count_registrations_by_ip(
        db: Session,
        ip_address: str,
        hours: int = 1
    ) -> int:
        """统计IP在指定时间内的注册次数"""
        cutoff = now_naive() - timedelta(hours=hours)

        count = db.query(SecurityLog).filter(
            SecurityLog.event_type == "registration",
            SecurityLog.ip_address == ip_address,
            SecurityLog.created_at >= cutoff
        ).count()

        return count

    @staticmethod
    def count_refunds_by_user(
        db: Session,
        user_id: str,
        days: int = 30
    ) -> int:
        """统计用户在指定时间内的退款次数"""
        from database.models import Refund

        cutoff = now_naive() - timedelta(days=days)

        count = db.query(Refund).filter(
            Refund.order_id.in_(
                db.query(Order.order_id).filter(Order.user_id == user_id)
            ),
            Refund.created_at >= cutoff
        ).count()

        return count


# 全局实例
security_service = SecurityService()
