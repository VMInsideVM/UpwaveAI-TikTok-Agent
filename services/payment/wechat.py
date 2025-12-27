"""
微信支付服务
WeChat Pay Provider
"""

import os
import logging
import hashlib
import hmac
import json
import base64
from typing import Optional
from datetime import datetime

from .base import PaymentProvider, PaymentResult, PaymentNotification, RefundResult

logger = logging.getLogger(__name__)


class WechatPayProvider(PaymentProvider):
    """微信支付服务提供者"""

    def __init__(self):
        self.mch_id = os.getenv("WECHAT_MCH_ID", "")
        self.app_id = os.getenv("WECHAT_APP_ID", "")
        self.api_key = os.getenv("WECHAT_API_KEY", "")
        self.api_v3_key = os.getenv("WECHAT_API_V3_KEY", "")
        self.cert_path = os.getenv("WECHAT_CERT_PATH", "")
        self.key_path = os.getenv("WECHAT_KEY_PATH", "")
        self.serial_no = os.getenv("WECHAT_SERIAL_NO", "")
        self.notify_url = os.getenv("WECHAT_NOTIFY_URL", "")

        self._client = None

        if not all([self.mch_id, self.app_id, self.api_v3_key]):
            logger.warning("微信支付配置不完整，部分功能可能不可用")

    @property
    def provider_name(self) -> str:
        return "wechat"

    def _get_client(self):
        """延迟初始化微信支付客户端"""
        if self._client is None:
            try:
                from wechatpayv3 import WeChatPay, WeChatPayType

                with open(self.key_path, 'r') as f:
                    private_key = f.read()

                self._client = WeChatPay(
                    wechatpay_type=WeChatPayType.NATIVE,  # 扫码支付
                    mchid=self.mch_id,
                    private_key=private_key,
                    cert_serial_no=self.serial_no,
                    apiv3_key=self.api_v3_key,
                    appid=self.app_id,
                    notify_url=self.notify_url
                )
            except ImportError:
                logger.error("未安装 wechatpayv3，请运行: pip install wechatpayv3")
                raise
            except Exception as e:
                logger.error(f"初始化微信支付客户端失败: {e}")
                raise

        return self._client

    async def create_payment(
        self,
        order_no: str,
        amount_fen: int,
        subject: str,
        notify_url: str,
        **kwargs
    ) -> PaymentResult:
        """创建微信扫码支付订单"""
        try:
            client = self._get_client()

            # 调用 Native 支付接口
            result = client.pay(
                description=subject,
                out_trade_no=order_no,
                amount={
                    "total": amount_fen,
                    "currency": "CNY"
                },
                notify_url=notify_url or self.notify_url
            )

            code, response = result

            if code == 200 and response.get("code_url"):
                return PaymentResult(
                    success=True,
                    order_no=order_no,
                    qr_code_url=response.get("code_url"),
                    raw_response=response
                )
            else:
                return PaymentResult(
                    success=False,
                    order_no=order_no,
                    error_message=response.get("message", "创建支付失败"),
                    raw_response=response
                )

        except Exception as e:
            logger.exception(f"创建微信支付失败: {e}")
            return PaymentResult(
                success=False,
                order_no=order_no,
                error_message=str(e)
            )

    async def query_payment(self, order_no: str) -> PaymentNotification:
        """查询微信支付订单状态"""
        try:
            client = self._get_client()

            code, response = client.query(out_trade_no=order_no)

            if code == 200:
                trade_state = response.get("trade_state")

                # 微信交易状态：SUCCESS, REFUND, NOTPAY, CLOSED, REVOKED, USERPAYING, PAYERROR
                success = trade_state == "SUCCESS"

                amount = response.get("amount", {})

                return PaymentNotification(
                    success=success,
                    order_no=order_no,
                    trade_no=response.get("transaction_id", ""),
                    amount_fen=amount.get("total", 0),
                    paid_at=response.get("success_time"),
                    raw_data=response
                )
            else:
                return PaymentNotification(
                    success=False,
                    order_no=order_no,
                    trade_no="",
                    amount_fen=0,
                    error_message=response.get("message", "查询失败"),
                    raw_data=response
                )

        except Exception as e:
            logger.exception(f"查询微信订单失败: {e}")
            return PaymentNotification(
                success=False,
                order_no=order_no,
                trade_no="",
                amount_fen=0,
                error_message=str(e)
            )

    async def verify_notification(self, data: dict) -> PaymentNotification:
        """验证微信支付回调通知"""
        try:
            client = self._get_client()

            # 解密回调数据
            headers = data.get("headers", {})
            body = data.get("body", "")

            # 验证签名并解密
            result = client.callback(headers, body)

            if result and result.get("event_type") == "TRANSACTION.SUCCESS":
                resource = result.get("resource", {})

                return PaymentNotification(
                    success=True,
                    order_no=resource.get("out_trade_no", ""),
                    trade_no=resource.get("transaction_id", ""),
                    amount_fen=resource.get("amount", {}).get("total", 0),
                    paid_at=resource.get("success_time"),
                    raw_data=resource
                )
            else:
                return PaymentNotification(
                    success=False,
                    order_no="",
                    trade_no="",
                    amount_fen=0,
                    error_message="支付未成功或验证失败",
                    raw_data=result
                )

        except Exception as e:
            logger.exception(f"验证微信通知失败: {e}")
            return PaymentNotification(
                success=False,
                order_no="",
                trade_no="",
                amount_fen=0,
                error_message=str(e)
            )

    async def refund(
        self,
        order_no: str,
        refund_no: str,
        refund_amount_fen: int,
        total_amount_fen: int,
        reason: str
    ) -> RefundResult:
        """微信退款"""
        try:
            client = self._get_client()

            code, response = client.refund(
                out_trade_no=order_no,
                out_refund_no=refund_no,
                amount={
                    "refund": refund_amount_fen,
                    "total": total_amount_fen,
                    "currency": "CNY"
                },
                reason=reason
            )

            if code == 200:
                status = response.get("status")
                # 微信退款状态：SUCCESS, CLOSED, PROCESSING, ABNORMAL
                success = status in ["SUCCESS", "PROCESSING"]

                return RefundResult(
                    success=success,
                    refund_no=refund_no,
                    refund_trade_no=response.get("refund_id"),
                    raw_response=response
                )
            else:
                return RefundResult(
                    success=False,
                    refund_no=refund_no,
                    error_message=response.get("message", "退款失败"),
                    raw_response=response
                )

        except Exception as e:
            logger.exception(f"微信退款失败: {e}")
            return RefundResult(
                success=False,
                refund_no=refund_no,
                error_message=str(e)
            )

    async def query_refund(self, refund_no: str) -> RefundResult:
        """查询微信退款状态"""
        try:
            client = self._get_client()

            code, response = client.query_refund(out_refund_no=refund_no)

            if code == 200:
                status = response.get("status")
                success = status == "SUCCESS"

                return RefundResult(
                    success=success,
                    refund_no=refund_no,
                    refund_trade_no=response.get("refund_id"),
                    error_message=None if success else f"退款状态: {status}",
                    raw_response=response
                )
            else:
                return RefundResult(
                    success=False,
                    refund_no=refund_no,
                    error_message=response.get("message", "查询退款失败"),
                    raw_response=response
                )

        except Exception as e:
            logger.exception(f"查询微信退款失败: {e}")
            return RefundResult(
                success=False,
                refund_no=refund_no,
                error_message=str(e)
            )
