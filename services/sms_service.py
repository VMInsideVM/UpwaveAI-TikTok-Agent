"""
阿里云短信服务
处理验证码发送和验证
"""
import os
import random
import string
from datetime import timedelta
from typing import Tuple, Optional
from passlib.context import CryptContext

from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
from sqlalchemy.orm import Session

from database.models import SMSVerification

# 验证码哈希上下文（使用更快的 rounds 数）
sms_code_context = CryptContext(
    schemes=["bcrypt"],
    bcrypt__default_rounds=4  # 短信验证码用较少的 rounds（仅需临时存储）
)

# 阿里云配置
ALIYUN_ACCESS_KEY_ID = os.getenv("ALIYUN_ACCESS_KEY_ID", "***REMOVED***")
ALIYUN_ACCESS_KEY_SECRET = os.getenv("ALIYUN_ACCESS_KEY_SECRET", "***REMOVED***")
ALIYUN_SMS_SIGN_NAME = os.getenv("ALIYUN_SMS_SIGN_NAME", "杭州升澜智能科技有限公司")

# 短信模板 ID
SMS_TEMPLATE_REGISTER = os.getenv("SMS_TEMPLATE_REGISTER", "SMS_499310186")  # 注册验证码
SMS_TEMPLATE_RESET_PASSWORD = os.getenv("SMS_TEMPLATE_RESET_PASSWORD", "SMS_499080375")  # 密码重置
SMS_TEMPLATE_REPORT_READY = os.getenv("SMS_TEMPLATE_REPORT_READY", "SMS_499100445")  # 报告完成通知

# 验证码配置
SMS_CODE_LENGTH = int(os.getenv("SMS_CODE_LENGTH", "6"))
SMS_CODE_EXPIRE_MINUTES = int(os.getenv("SMS_CODE_EXPIRE_MINUTES", "5"))
MAX_ATTEMPTS = int(os.getenv("SMS_MAX_ATTEMPTS", "3"))

# 限流配置
RATE_LIMIT_PER_PHONE_HOUR = int(os.getenv("RATE_LIMIT_PER_PHONE_HOUR", "5"))
RATE_LIMIT_PER_IP_DAY = int(os.getenv("RATE_LIMIT_PER_IP_DAY", "5"))


class SMSService:
    """阿里云短信服务"""

    def __init__(self):
        """初始化阿里云客户端"""
        config = open_api_models.Config(
            access_key_id=ALIYUN_ACCESS_KEY_ID,
            access_key_secret=ALIYUN_ACCESS_KEY_SECRET,
            endpoint='dysmsapi.aliyuncs.com'
        )
        self.client = DysmsapiClient(config)

    @staticmethod
    def generate_code() -> str:
        """生成 6 位随机数字验证码"""
        return ''.join(random.choices(string.digits, k=SMS_CODE_LENGTH))

    @staticmethod
    def validate_phone_format(phone: str) -> bool:
        """
        验证手机号格式（仅支持中国大陆）
        格式: 1[3-9]\\d{9}
        """
        import re
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone))

    def check_rate_limit(self, db: Session, phone: str, ip_address: str) -> Tuple[bool, str]:
        """
        检查发送频率限制

        Returns:
            (is_allowed, error_message)
        """
        from utils.timezone import now_naive

        one_hour_ago = now_naive() - timedelta(hours=1)
        one_day_ago = now_naive() - timedelta(days=1)

        # 检查手机号频率限制（每小时 5 次）
        phone_count = db.query(SMSVerification).filter(
            SMSVerification.phone_number == phone,
            SMSVerification.created_at >= one_hour_ago
        ).count()

        if phone_count >= RATE_LIMIT_PER_PHONE_HOUR:
            return False, f"该手机号每小时最多发送 {RATE_LIMIT_PER_PHONE_HOUR} 次验证码，请稍后再试"

        # 检查 IP 频率限制（每天 5 次）
        ip_count = db.query(SMSVerification).filter(
            SMSVerification.ip_address == ip_address,
            SMSVerification.created_at >= one_day_ago
        ).count()

        if ip_count >= RATE_LIMIT_PER_IP_DAY:
            return False, f"您的IP今日验证码发送次数已达上限（{RATE_LIMIT_PER_IP_DAY}次），请明天再试"

        return True, ""

    async def send_verification_code(
        self,
        db: Session,
        phone: str,
        code_type: str,
        ip_address: str,
        user_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        发送短信验证码

        Args:
            db: 数据库会话
            phone: 手机号
            code_type: 验证码类型 ('register', 'reset_password', 'change_phone')
            ip_address: 客户端 IP 地址
            user_id: 用户 ID（可选，仅在已登录时提供）

        Returns:
            (success, message)
        """
        # 1. 验证手机号格式
        if not self.validate_phone_format(phone):
            return False, "手机号格式不正确，请输入11位中国大陆手机号"

        # 2. 检查频率限制
        is_allowed, error_msg = self.check_rate_limit(db, phone, ip_address)
        if not is_allowed:
            return False, error_msg

        # 3. 生成验证码
        code = self.generate_code()

        # 4. 选择短信模板
        template_map = {
            'register': SMS_TEMPLATE_REGISTER,
            'reset_password': SMS_TEMPLATE_RESET_PASSWORD,
            'change_phone': SMS_TEMPLATE_REGISTER  # 修改手机号使用注册模板
        }
        template_code = template_map.get(code_type, SMS_TEMPLATE_REGISTER)

        # 5. 调用阿里云 API 发送短信
        try:
            request = dysmsapi_models.SendSmsRequest(
                phone_numbers=phone,
                sign_name=ALIYUN_SMS_SIGN_NAME,
                template_code=template_code,
                template_param=f'{{"code":"{code}"}}'  # 模板变量 ${code}
            )

            response = self.client.send_sms(request)

            # 检查发送结果
            if response.body.code != 'OK':
                error_msg = f"短信发送失败: {response.body.message}"
                print(f"❌ Aliyun SMS Error: {error_msg}")
                return False, "短信发送失败，请稍后重试"

        except Exception as e:
            print(f"❌ Aliyun SMS Exception: {str(e)}")
            return False, "短信服务暂时不可用，请稍后重试"

        # 6. 存储验证码记录（哈希后）
        from utils.timezone import now_naive

        hashed_code = sms_code_context.hash(code)
        expires_at = now_naive() + timedelta(minutes=SMS_CODE_EXPIRE_MINUTES)

        verification = SMSVerification(
            phone_number=phone,
            code=hashed_code,
            code_type=code_type,
            ip_address=ip_address,
            user_id=user_id,
            expires_at=expires_at,
            max_attempts=MAX_ATTEMPTS
        )

        db.add(verification)
        db.commit()

        print(f"✅ SMS sent to {phone}: {code} (expires in {SMS_CODE_EXPIRE_MINUTES} min)")

        return True, f"验证码已发送至 {phone}，{SMS_CODE_EXPIRE_MINUTES} 分钟内有效"

    def verify_code(
        self,
        db: Session,
        phone: str,
        code: str,
        code_type: str
    ) -> Tuple[bool, str, Optional[SMSVerification]]:
        """
        验证短信验证码

        Returns:
            (is_valid, message, verification_record)
        """
        # 1. 查找最近的未验证记录
        verification = db.query(SMSVerification).filter(
            SMSVerification.phone_number == phone,
            SMSVerification.code_type == code_type,
            SMSVerification.is_verified == False
        ).order_by(SMSVerification.created_at.desc()).first()

        if not verification:
            return False, "验证码不存在或已使用", None

        # 2. 检查是否已过期
        if verification.is_expired:
            return False, "验证码已过期，请重新获取", None

        # 3. 检查是否已锁定
        if verification.is_locked:
            return False, "验证码尝试次数过多，请重新获取", None

        # 4. 验证验证码
        if not sms_code_context.verify(code, verification.code):
            # 增加尝试次数
            verification.attempt_count += 1
            db.commit()

            remaining = verification.remaining_attempts
            if remaining > 0:
                return False, f"验证码错误，还剩 {remaining} 次尝试机会", None
            else:
                return False, "验证码尝试次数过多，请重新获取", None

        # 5. 验证成功
        from utils.timezone import now_naive

        verification.is_verified = True
        verification.verified_at = now_naive()
        db.commit()

        return True, "验证成功", verification

    def cleanup_expired_codes(self, db: Session) -> int:
        """
        清理过期的验证码记录（定时任务）

        Returns:
            删除的记录数
        """
        from utils.timezone import now_naive

        one_day_ago = now_naive() - timedelta(days=1)

        deleted_count = db.query(SMSVerification).filter(
            SMSVerification.created_at < one_day_ago
        ).delete()

        db.commit()

        return deleted_count

    def send_report_ready_notification(self, phone: str, product_name: str) -> Tuple[bool, str]:
        """
        发送报告完成通知短信

        Args:
            phone: 手机号
            product_name: 产品名称

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            # 构建短信请求（根据模板变量要求）
            request = dysmsapi_models.SendSmsRequest(
                phone_numbers=phone,
                sign_name=ALIYUN_SMS_SIGN_NAME,
                template_code=SMS_TEMPLATE_REPORT_READY,
                template_param=f'{{"product":"{product_name}"}}'
            )

            # 发送短信
            response = self.client.send_sms(request)

            # 检查发送结果
            if response.body.code == 'OK':
                print(f"✅ 报告完成通知短信发送成功: {phone}")
                return True, "短信发送成功"
            else:
                error_msg = f"短信发送失败: {response.body.message}"
                print(f"❌ {error_msg}")
                return False, error_msg

        except Exception as e:
            error_msg = f"发送报告通知短信时发生错误: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg


# 单例模式
_sms_service_instance = None


def get_sms_service() -> SMSService:
    """获取短信服务单例"""
    global _sms_service_instance
    if _sms_service_instance is None:
        _sms_service_instance = SMSService()
    return _sms_service_instance
