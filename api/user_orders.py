"""
用户订单API
User Orders API - 用户查看订单和申请退款
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from database.connection import get_db
from database.models import User, Order, Refund
from api.auth import get_current_user
import uuid

# 东八区时区
CHINA_TZ = timezone(timedelta(hours=8))

router = APIRouter(prefix="/api/user", tags=["user_orders"])


class UserOrderResponse(BaseModel):
    """用户订单响应"""
    order_id: str
    order_no: str
    amount_yuan: int
    credits: int
    payment_method: str
    payment_status: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None  # 订单过期时间
    refund_status: Optional[str] = None  # pending/rejected/processing/success/failed


class UserOrdersListResponse(BaseModel):
    """用户订单列表响应"""
    orders: List[UserOrderResponse]
    total: int


class RefundRequest(BaseModel):
    """退款请求"""
    reason: str


class UserRefundResponse(BaseModel):
    """用户退款记录响应"""
    refund_id: str
    refund_no: str
    order_no: str
    refund_amount_yuan: int
    refund_credits: int
    status: str
    reason: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None  # 拒绝原因或退款失败原因


class UserRefundsListResponse(BaseModel):
    """用户退款列表响应"""
    refunds: List[UserRefundResponse]
    total: int


@router.get("/orders", response_model=UserOrdersListResponse)
async def get_user_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有订单"""
    orders = db.query(Order).filter(
        Order.user_id == current_user.user_id
    ).order_by(Order.created_at.desc()).all()

    # 检查每个订单的退款状态
    order_responses = []
    for order in orders:
        refund = db.query(Refund).filter(Refund.order_id == order.order_id).first()
        refund_status = refund.status if refund else None

        order_responses.append(UserOrderResponse(
            order_id=order.order_id,
            order_no=order.order_no,
            amount_yuan=order.amount_yuan,
            credits=order.credits,
            payment_method=order.payment_method,
            payment_status=order.payment_status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            expired_at=order.expired_at,
            refund_status=refund_status
        ))

    return UserOrdersListResponse(
        orders=order_responses,
        total=len(order_responses)
    )


@router.post("/orders/{order_id}/refund")
async def request_refund(
    order_id: str,
    request: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """用户申请退款"""
    # 查询订单
    order = db.query(Order).filter(
        Order.order_id == order_id,
        Order.user_id == current_user.user_id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    # 检查订单状态
    if order.payment_status != "paid":
        raise HTTPException(status_code=400, detail="只能对已支付订单申请退款")

    # 检查是否已经申请过退款
    existing_refund = db.query(Refund).filter(Refund.order_id == order_id).first()
    if existing_refund:
        raise HTTPException(status_code=400, detail="该订单已申请退款")

    # 创建退款记录
    refund_id = str(uuid.uuid4())
    refund_no = f"RF{datetime.now().strftime('%Y%m%d%H%M%S')}{refund_id[:6].upper()}"

    refund = Refund(
        refund_id=refund_id,
        order_id=order_id,
        refund_no=refund_no,
        refund_amount_yuan=order.amount_yuan,
        refund_credits=order.credits,
        status="pending",  # 待审核
        reason=request.reason,
        admin_id=None,
        created_at=datetime.now(CHINA_TZ).replace(tzinfo=None)
    )

    db.add(refund)
    db.commit()

    return {
        "message": "退款申请已提交",
        "refund_id": refund_id,
        "refund_no": refund_no
    }


@router.get("/refunds", response_model=UserRefundsListResponse)
async def get_user_refunds(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有退款记录"""
    # 查询用户所有订单的退款记录
    refunds = db.query(Refund, Order).join(
        Order, Refund.order_id == Order.order_id
    ).filter(
        Order.user_id == current_user.user_id
    ).order_by(Refund.created_at.desc()).all()

    refund_responses = []
    for refund, order in refunds:
        refund_responses.append(UserRefundResponse(
            refund_id=refund.refund_id,
            refund_no=refund.refund_no,
            order_no=order.order_no,
            refund_amount_yuan=refund.refund_amount_yuan,
            refund_credits=refund.refund_credits,
            status=refund.status,
            reason=refund.reason,
            created_at=refund.created_at,
            processed_at=refund.processed_at,
            error_message=refund.error_message
        ))

    return UserRefundsListResponse(
        refunds=refund_responses,
        total=len(refund_responses)
    )
