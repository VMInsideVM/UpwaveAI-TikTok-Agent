"""
支付服务抽象基类
Abstract base class for payment providers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class PaymentStatus(Enum):
    """支付状态"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RefundStatus(Enum):
    """退款状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class PaymentResult:
    """支付结果"""
    success: bool
    order_no: str
    qr_code_url: Optional[str] = None  # 二维码URL
    payment_url: Optional[str] = None  # 支付跳转URL
    qr_code_base64: Optional[str] = None  # 二维码Base64编码
    trade_no: Optional[str] = None  # 第三方交易号
    error_message: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class RefundResult:
    """退款结果"""
    success: bool
    refund_no: str
    refund_trade_no: Optional[str] = None  # 第三方退款交易号
    error_message: Optional[str] = None
    raw_response: Optional[dict] = None


@dataclass
class PaymentNotification:
    """支付回调通知"""
    success: bool
    order_no: str  # 商户订单号
    trade_no: str  # 第三方交易号
    amount_fen: int  # 支付金额（分）
    paid_at: Optional[str] = None
    raw_data: Optional[dict] = None
    error_message: Optional[str] = None


class PaymentProvider(ABC):
    """支付服务提供者抽象基类"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供者名称"""
        pass

    @abstractmethod
    async def create_payment(
        self,
        order_no: str,
        amount_fen: int,
        subject: str,
        notify_url: str,
        **kwargs
    ) -> PaymentResult:
        """
        创建支付订单，返回支付二维码

        Args:
            order_no: 商户订单号
            amount_fen: 支付金额（分）
            subject: 订单标题
            notify_url: 异步通知URL

        Returns:
            PaymentResult: 包含二维码URL的支付结果
        """
        pass

    @abstractmethod
    async def query_payment(self, order_no: str) -> PaymentNotification:
        """
        查询支付状态

        Args:
            order_no: 商户订单号

        Returns:
            PaymentNotification: 支付状态信息
        """
        pass

    @abstractmethod
    async def verify_notification(self, data: dict) -> PaymentNotification:
        """
        验证并解析支付回调通知

        Args:
            data: 回调数据

        Returns:
            PaymentNotification: 解析后的通知信息
        """
        pass

    @abstractmethod
    async def refund(
        self,
        order_no: str,
        refund_no: str,
        refund_amount_fen: int,
        total_amount_fen: int,
        reason: str
    ) -> RefundResult:
        """
        发起退款

        Args:
            order_no: 原订单号
            refund_no: 退款单号
            refund_amount_fen: 退款金额（分）
            total_amount_fen: 原订单总金额（分）
            reason: 退款原因

        Returns:
            RefundResult: 退款结果
        """
        pass

    @abstractmethod
    async def query_refund(self, refund_no: str) -> RefundResult:
        """
        查询退款状态

        Args:
            refund_no: 退款单号

        Returns:
            RefundResult: 退款状态信息
        """
        pass
