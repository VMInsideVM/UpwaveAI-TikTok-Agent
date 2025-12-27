"""
支付宝支付服务
Alipay Payment Provider
"""

import os
import logging
from typing import Optional
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from .base import PaymentProvider, PaymentResult, PaymentNotification, RefundResult

logger = logging.getLogger(__name__)


def load_key_from_file_or_env(file_path_env: str, direct_env: str) -> str:
    """从文件路径或直接环境变量加载密钥"""
    # 优先从文件路径加载
    file_path = os.getenv(file_path_env, "")
    if file_path:
        try:
            path = Path(file_path)
            if path.exists():
                content = path.read_text(encoding='utf-8').strip()
                logger.info(f"从文件加载密钥: {file_path}")
                return content
        except Exception as e:
            logger.warning(f"从文件加载密钥失败 {file_path}: {e}")

    # 回退到直接环境变量
    return os.getenv(direct_env, "")


class AlipayProvider(PaymentProvider):
    """支付宝支付服务提供者"""

    def __init__(self):
        self.app_id = os.getenv("ALIPAY_APP_ID", "")
        self.private_key = load_key_from_file_or_env("ALIPAY_PRIVATE_KEY_PATH", "ALIPAY_PRIVATE_KEY")
        self.alipay_public_key = load_key_from_file_or_env("ALIPAY_PUBLIC_KEY_PATH", "ALIPAY_PUBLIC_KEY")
        self.notify_url = os.getenv("ALIPAY_NOTIFY_URL", "")
        self.sandbox = os.getenv("ALIPAY_SANDBOX", "false").lower() == "true"

        self._client = None

        if not all([self.app_id, self.private_key, self.alipay_public_key]):
            logger.warning("支付宝配置不完整，部分功能可能不可用")

    @property
    def provider_name(self) -> str:
        return "alipay"

    def _get_client(self):
        """延迟初始化支付宝客户端"""
        if self._client is None:
            try:
                from alipay import AliPay

                self._client = AliPay(
                    appid=self.app_id,
                    app_notify_url=self.notify_url,
                    app_private_key_string=self.private_key,
                    alipay_public_key_string=self.alipay_public_key,
                    sign_type="RSA2",
                    debug=self.sandbox
                )
            except ImportError:
                logger.error("未安装 python-alipay-sdk，请运行: pip install python-alipay-sdk")
                raise
            except Exception as e:
                logger.error(f"初始化支付宝客户端失败: {e}")
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
        """创建支付宝扫码支付订单"""
        try:
            client = self._get_client()

            # 金额转换：分 -> 元
            amount_yuan = f"{amount_fen / 100:.2f}"
            
            # 使用电脑网站支付接口 (api_alipay_trade_page_pay)
            # 该接口返回的是带有签名的查询字符串
            order_string = client.api_alipay_trade_page_pay(
                subject=subject,
                out_trade_no=order_no,
                total_amount=amount_yuan,
                product_code="FAST_INSTANT_TRADE_PAY",  # 电脑网站支付必填
                notify_url=notify_url or self.notify_url,
                return_url=kwargs.get("return_url")  # 如果有同步跳转地址
            )
            
            # 拼接完整的跳转链接
            # 根据沙箱环境选择网关
            gateway = "https://openapi-sandbox.dl.alipaydev.com/gateway.do" if self.sandbox else "https://openapi.alipay.com/gateway.do"
            payment_url = f"{gateway}?{order_string}"

            if order_string:
                return PaymentResult(
                    success=True,
                    order_no=order_no,
                    payment_url=payment_url,
                    # 为了兼容前端二维码显示，我们也可以通过 payment_url 生成二维码（可选）
                    # 但本质是跳转支付，所以主要通过 payment_url
                    raw_response={"payment_url": payment_url}
                )
            else:
                return PaymentResult(
                    success=False,
                    order_no=order_no,
                    error_message="生成支付链接失败",
                    raw_response={}
                )

        except Exception as e:
            logger.exception(f"创建支付宝支付失败: {e}")
            return PaymentResult(
                success=False,
                order_no=order_no,
                error_message=str(e)
            )

    async def query_payment(self, order_no: str) -> PaymentNotification:
        """查询支付宝订单状态"""
        try:
            client = self._get_client()

            result = client.api_alipay_trade_query(out_trade_no=order_no)

            if result.get("code") == "10000":
                trade_status = result.get("trade_status")

                # 支付宝交易状态：WAIT_BUYER_PAY, TRADE_CLOSED, TRADE_SUCCESS, TRADE_FINISHED
                success = trade_status in ["TRADE_SUCCESS", "TRADE_FINISHED"]

                return PaymentNotification(
                    success=success,
                    order_no=order_no,
                    trade_no=result.get("trade_no", ""),
                    amount_fen=int(float(result.get("total_amount", 0)) * 100),
                    paid_at=result.get("send_pay_date"),
                    raw_data=result
                )
            else:
                return PaymentNotification(
                    success=False,
                    order_no=order_no,
                    trade_no="",
                    amount_fen=0,
                    error_message=result.get("sub_msg", "查询失败"),
                    raw_data=result
                )

        except Exception as e:
            logger.exception(f"查询支付宝订单失败: {e}")
            return PaymentNotification(
                success=False,
                order_no=order_no,
                trade_no="",
                amount_fen=0,
                error_message=str(e)
            )

    async def verify_notification(self, data: dict) -> PaymentNotification:
        """验证支付宝异步通知"""
        try:
            client = self._get_client()

            # 验证签名
            signature = data.pop("sign", None)
            sign_type = data.pop("sign_type", None)

            if not client.verify(data, signature):
                return PaymentNotification(
                    success=False,
                    order_no=data.get("out_trade_no", ""),
                    trade_no="",
                    amount_fen=0,
                    error_message="签名验证失败"
                )

            # 检查交易状态
            trade_status = data.get("trade_status")
            success = trade_status in ["TRADE_SUCCESS", "TRADE_FINISHED"]

            return PaymentNotification(
                success=success,
                order_no=data.get("out_trade_no", ""),
                trade_no=data.get("trade_no", ""),
                amount_fen=int(float(data.get("total_amount", 0)) * 100),
                paid_at=data.get("gmt_payment"),
                raw_data=data
            )

        except Exception as e:
            logger.exception(f"验证支付宝通知失败: {e}")
            return PaymentNotification(
                success=False,
                order_no=data.get("out_trade_no", ""),
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
        """支付宝退款"""
        try:
            client = self._get_client()

            # 金额转换：分 -> 元
            refund_amount_yuan = f"{refund_amount_fen / 100:.2f}"

            result = client.api_alipay_trade_refund(
                out_trade_no=order_no,
                refund_amount=refund_amount_yuan,
                out_request_no=refund_no,
                refund_reason=reason
            )

            if result.get("code") == "10000":
                return RefundResult(
                    success=True,
                    refund_no=refund_no,
                    refund_trade_no=result.get("trade_no"),
                    raw_response=result
                )
            else:
                return RefundResult(
                    success=False,
                    refund_no=refund_no,
                    error_message=result.get("sub_msg", result.get("msg", "退款失败")),
                    raw_response=result
                )

        except Exception as e:
            logger.exception(f"支付宝退款失败: {e}")
            return RefundResult(
                success=False,
                refund_no=refund_no,
                error_message=str(e)
            )

    async def query_refund(self, refund_no: str) -> RefundResult:
        """查询支付宝退款状态"""
        try:
            client = self._get_client()

            result = client.api_alipay_trade_fastpay_refund_query(
                out_request_no=refund_no
            )

            if result.get("code") == "10000":
                return RefundResult(
                    success=True,
                    refund_no=refund_no,
                    refund_trade_no=result.get("trade_no"),
                    raw_response=result
                )
            else:
                return RefundResult(
                    success=False,
                    refund_no=refund_no,
                    error_message=result.get("sub_msg", "查询退款失败"),
                    raw_response=result
                )

        except Exception as e:
            logger.exception(f"查询支付宝退款失败: {e}")
            return RefundResult(
                success=False,
                refund_no=refund_no,
                error_message=str(e)
            )
