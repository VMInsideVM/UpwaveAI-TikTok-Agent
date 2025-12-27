"""
支付服务管理器
Payment Service Manager
"""

import os
import logging
from typing import Optional
from datetime import datetime
import uuid
import qrcode
import io
import base64

from .base import PaymentProvider, PaymentResult, PaymentNotification, RefundResult
from .alipay import AlipayProvider
from .wechat import WechatPayProvider

logger = logging.getLogger(__name__)

# 检测是否为本地调试模式（支付宝配置为空时启用）
DEBUG_MODE = not os.getenv("ALIPAY_APP_ID", "")


class PaymentManager:
    """支付服务管理器，统一管理各支付渠道"""

    def __init__(self):
        self._providers: dict[str, PaymentProvider] = {}
        self._init_providers()

    def _init_providers(self):
        """初始化支付服务提供者"""
        try:
            self._providers["alipay"] = AlipayProvider()
            logger.info("支付宝服务已初始化")
        except Exception as e:
            logger.warning(f"支付宝服务初始化失败: {e}")

        try:
            self._providers["wechat"] = WechatPayProvider()
            logger.info("微信支付服务已初始化")
        except Exception as e:
            logger.warning(f"微信支付服务初始化失败: {e}")

    def get_provider(self, payment_method: str) -> Optional[PaymentProvider]:
        """获取指定的支付服务提供者"""
        return self._providers.get(payment_method)

    def is_provider_available(self, payment_method: str) -> bool:
        """检查支付服务是否可用"""
        return payment_method in self._providers

    @staticmethod
    def generate_order_no() -> str:
        """
        生成唯一订单号
        格式：年月日时分秒 + 6位随机数，共20位
        """
        now = datetime.now()
        time_part = now.strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:6].upper()
        return f"{time_part}{random_part}"

    @staticmethod
    def generate_refund_no() -> str:
        """
        生成唯一退款单号
        格式：R + 年月日时分秒 + 5位随机数，共20位
        """
        now = datetime.now()
        time_part = now.strftime("%Y%m%d%H%M%S")
        random_part = uuid.uuid4().hex[:5].upper()
        return f"R{time_part}{random_part}"

    @staticmethod
    def generate_qr_code_base64(content: str) -> str:
        """
        根据内容生成二维码的Base64编码

        Args:
            content: 二维码内容（URL）

        Returns:
            Base64编码的PNG图片
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(content)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    async def create_payment(
        self,
        payment_method: str,
        order_no: str,
        amount_fen: int,
        subject: str,
        notify_url: str
    ) -> PaymentResult:
        """
        创建支付订单

        Args:
            payment_method: 支付方式 (alipay/wechat)
            order_no: 订单号
            amount_fen: 金额（分）
            subject: 订单标题
            notify_url: 异步通知URL

        Returns:
            PaymentResult: 支付结果
        """
        # 本地调试模式：返回占位二维码
        if DEBUG_MODE:
            logger.info(f"[调试模式] 创建模拟支付订单: {order_no}, 金额: {amount_fen}分")
            placeholder_url = f"DEBUG_MODE_ORDER_{order_no}"
            return PaymentResult(
                success=True,
                order_no=order_no,
                qr_code_url=placeholder_url,
                qr_code_base64=self.generate_qr_code_base64(f"调试模式\n订单号: {order_no}\n金额: ¥{amount_fen/100:.2f}\n\n请点击【模拟支付】按钮完成测试"),
                raw_response={"debug_mode": True}
            )

        provider = self.get_provider(payment_method)
        if not provider:
            return PaymentResult(
                success=False,
                order_no=order_no,
                error_message=f"不支持的支付方式: {payment_method}"
            )

        result = await provider.create_payment(
            order_no=order_no,
            amount_fen=amount_fen,
            subject=subject,
            notify_url=notify_url
        )

        # 如果成功获取到二维码URL或支付URL，生成Base64编码的二维码
        if result.success:
            qr_content = result.qr_code_url or result.payment_url
            if qr_content:
                try:
                    result.qr_code_base64 = self.generate_qr_code_base64(qr_content)
                    # 如果只有 payment_url，也设置 qr_code_url 以兼容前端
                    if not result.qr_code_url and result.payment_url:
                        result.qr_code_url = result.payment_url
                except Exception as e:
                    logger.warning(f"生成二维码Base64失败: {e}")

        return result

    async def query_payment(
        self,
        payment_method: str,
        order_no: str
    ) -> PaymentNotification:
        """
        查询支付状态

        Args:
            payment_method: 支付方式
            order_no: 订单号

        Returns:
            PaymentNotification: 支付状态
        """
        provider = self.get_provider(payment_method)
        if not provider:
            return PaymentNotification(
                success=False,
                order_no=order_no,
                trade_no="",
                amount_fen=0,
                error_message=f"不支持的支付方式: {payment_method}"
            )

        return await provider.query_payment(order_no)

    async def verify_notification(
        self,
        payment_method: str,
        data: dict
    ) -> PaymentNotification:
        """
        验证支付回调

        Args:
            payment_method: 支付方式
            data: 回调数据

        Returns:
            PaymentNotification: 验证结果
        """
        provider = self.get_provider(payment_method)
        if not provider:
            return PaymentNotification(
                success=False,
                order_no="",
                trade_no="",
                amount_fen=0,
                error_message=f"不支持的支付方式: {payment_method}"
            )

        return await provider.verify_notification(data)

    async def refund(
        self,
        payment_method: str,
        order_no: str,
        refund_no: str,
        refund_amount_fen: int,
        total_amount_fen: int,
        reason: str
    ) -> RefundResult:
        """
        发起退款

        Args:
            payment_method: 支付方式
            order_no: 原订单号
            refund_no: 退款单号
            refund_amount_fen: 退款金额（分）
            total_amount_fen: 原订单金额（分）
            reason: 退款原因

        Returns:
            RefundResult: 退款结果
        """
        provider = self.get_provider(payment_method)
        if not provider:
            return RefundResult(
                success=False,
                refund_no=refund_no,
                error_message=f"不支持的支付方式: {payment_method}"
            )

        return await provider.refund(
            order_no=order_no,
            refund_no=refund_no,
            refund_amount_fen=refund_amount_fen,
            total_amount_fen=total_amount_fen,
            reason=reason
        )

    async def query_refund(
        self,
        payment_method: str,
        refund_no: str
    ) -> RefundResult:
        """
        查询退款状态

        Args:
            payment_method: 支付方式
            refund_no: 退款单号

        Returns:
            RefundResult: 退款状态
        """
        provider = self.get_provider(payment_method)
        if not provider:
            return RefundResult(
                success=False,
                refund_no=refund_no,
                error_message=f"不支持的支付方式: {payment_method}"
            )

        return await provider.query_refund(refund_no)


# 全局单例
payment_manager = PaymentManager()
