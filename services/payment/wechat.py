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
        # 新增：支持公钥方式
        self.public_key_path = os.getenv("WECHAT_PUBLIC_KEY", "")
        self.public_key_id = os.getenv("WECHAT_PUBLIC_KEY_ID", "")

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

                # 读取公钥（用于验签）
                public_key = None
                if self.public_key_path and os.path.exists(self.public_key_path):
                    with open(self.public_key_path, 'r') as f:
                        public_key = f.read()
                    logger.info(f"已加载微信支付公钥: {self.public_key_path}")

                self._client = WeChatPay(
                    wechatpay_type=WeChatPayType.NATIVE,  # 扫码支付
                    mchid=self.mch_id,
                    private_key=private_key,
                    cert_serial_no=self.serial_no,
                    apiv3_key=self.api_v3_key,
                    appid=self.app_id,
                    notify_url=self.notify_url,
                    # 使用公钥代替平台证书（参数名是 public_key，不是 wechatpay_public_key）
                    public_key=public_key,
                    public_key_id=self.public_key_id
                )

                logger.info("微信支付客户端初始化成功（使用公钥验签）")
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

            # 准备支付参数
            pay_params = {
                "description": subject,
                "out_trade_no": order_no,
                "amount": {
                    "total": amount_fen,
                    "currency": "CNY"
                },
                "notify_url": notify_url or self.notify_url
            }

            # 添加过期时间（如果提供）
            time_expire = kwargs.get('time_expire')
            if time_expire:
                from datetime import datetime
                # 微信支付要求 RFC 3339 格式: 2025-12-31T23:59:59+08:00
                time_expire_str = time_expire.strftime('%Y-%m-%dT%H:%M:%S+08:00')
                pay_params["time_expire"] = time_expire_str
                logger.info(f"订单 {order_no} 设置过期时间: {time_expire_str}")

            # 调用 Native 支付接口
            result = client.pay(**pay_params)

            code, response = result

            # 调试日志：查看返回值类型和内容
            logger.info(f"微信支付API返回: code={code}, response类型={type(response)}, response内容={response}")

            # 如果 response 是字符串，尝试解析为 JSON
            if isinstance(response, str):
                import json
                try:
                    response = json.loads(response)
                except:
                    logger.error(f"无法解析响应为JSON: {response}")
                    return PaymentResult(
                        success=False,
                        order_no=order_no,
                        error_message=f"API返回格式错误: {response}"
                    )

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

            # 调试日志：查看返回值类型和内容
            logger.info(f"微信退款API返回: code={code}, response类型={type(response)}, response内容={response}")

            # 如果 response 是字符串，尝试解析为 JSON
            if isinstance(response, str):
                import json
                try:
                    response = json.loads(response)
                    logger.info(f"成功解析退款响应为JSON: {response}")
                except Exception as parse_error:
                    logger.error(f"无法解析退款响应为JSON: {response}, 错误: {parse_error}")
                    # 如果无法解析，但code是200，可能退款成功了
                    if code == 200:
                        return RefundResult(
                            success=True,
                            refund_no=refund_no,
                            error_message="退款已提交（响应格式异常）",
                            raw_response={"raw": response}
                        )
                    else:
                        return RefundResult(
                            success=False,
                            refund_no=refund_no,
                            error_message=f"退款失败: {response}",
                            raw_response={"raw": response}
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
                # 确保response是字典
                error_msg = "退款失败"
                if isinstance(response, dict):
                    error_msg = response.get("message", f"退款失败 (HTTP {code})")
                else:
                    error_msg = f"退款失败: {response}"

                return RefundResult(
                    success=False,
                    refund_no=refund_no,
                    error_message=error_msg,
                    raw_response=response if isinstance(response, dict) else {"raw": str(response)}
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

            # 调试日志：查看返回值类型和内容
            logger.info(f"查询微信退款API返回: code={code}, response类型={type(response)}, response内容={response}")

            # 如果 response 是字符串，尝试解析为 JSON
            if isinstance(response, str):
                import json
                try:
                    response = json.loads(response)
                    logger.info(f"成功解析退款查询响应为JSON: {response}")
                except Exception as parse_error:
                    logger.error(f"无法解析退款查询响应为JSON: {response}, 错误: {parse_error}")
                    return RefundResult(
                        success=False,
                        refund_no=refund_no,
                        error_message=f"查询失败: {response}",
                        raw_response={"raw": response}
                    )

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
                # 确保response是字典
                error_msg = "查询退款失败"
                if isinstance(response, dict):
                    error_msg = response.get("message", f"查询退款失败 (HTTP {code})")
                else:
                    error_msg = f"查询退款失败: {response}"

                return RefundResult(
                    success=False,
                    refund_no=refund_no,
                    error_message=error_msg,
                    raw_response=response if isinstance(response, dict) else {"raw": str(response)}
                )

        except Exception as e:
            logger.exception(f"查询微信退款失败: {e}")
            return RefundResult(
                success=False,
                refund_no=refund_no,
                error_message=str(e)
            )
