"""
Payment API Endpoints
用户支付 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from utils.timezone import now_naive
import logging
import os

from database.connection import get_db
from database.models import User, UserUsage, Order, Refund, CreditHistory
from auth.dependencies import get_current_user
from config.pricing import (
    CREDIT_TIERS, ORDER_EXPIRATION_SECONDS,
    MAX_PENDING_ORDERS_PER_USER, MAX_ORDERS_PER_HOUR,
    get_tier_by_id, get_all_tiers, validate_tier_id, validate_payment_method
)
from services.payment.manager import payment_manager
from utils.security import get_client_ip, rate_limiter
from services.security_service import security_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payment", tags=["充值支付"])


# ==================== Pydantic Models ====================

class TierInfo(BaseModel):
    """套餐信息"""
    id: str
    price_yuan: int
    credits: int
    name: str
    description: str
    popular: bool = False


class CreateOrderRequest(BaseModel):
    """创建订单请求"""
    tier_id: str
    payment_method: str  # alipay, wechat


class CreateOrderResponse(BaseModel):
    """创建订单响应"""
    order_id: str
    order_no: str
    qr_code_url: Optional[str] = None
    qr_code_base64: Optional[str] = None
    payment_url: Optional[str] = None  # 支付跳转链接（电脑网站支付）
    amount_yuan: int
    credits: int
    expires_at: datetime
    payment_method: str


class OrderStatusResponse(BaseModel):
    """订单状态响应"""
    order_id: str
    order_no: str
    payment_status: str
    amount_yuan: int
    credits: int
    payment_method: str
    created_at: datetime
    paid_at: Optional[datetime]
    expired: bool
    payment_url: Optional[str] = None  # 未过期的订单返回支付链接


class OrderListItem(BaseModel):
    """订单列表项"""
    order_id: str
    order_no: str
    tier_id: str
    tier_name: str
    amount_yuan: int
    credits: int
    payment_method: str
    payment_status: str
    created_at: datetime
    paid_at: Optional[datetime]


# ==================== API Endpoints ====================

@router.get("/tiers", response_model=List[TierInfo])
async def get_pricing_tiers():
    """获取充值套餐列表"""
    tiers = get_all_tiers()
    return [
        TierInfo(
            id=t["id"],
            price_yuan=t["price_yuan"],
            credits=t["credits"],
            name=t["name"],
            description=t["description"],
            popular=t.get("popular", False)
        )
        for t in tiers
    ]


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建充值订单，返回支付二维码

    1. 验证套餐和支付方式
    2. 检查订单限制
    3. 创建订单记录
    4. 调用支付SDK生成二维码
    5. 返回订单信息和二维码
    """
    # 1. 验证套餐
    tier = get_tier_by_id(request.tier_id)
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的套餐ID: {request.tier_id}"
        )

    # 2. 验证支付方式
    if not validate_payment_method(request.payment_method):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的支付方式: {request.payment_method}"
        )

    # 3. 检查待支付订单数量限制
    pending_count = db.query(Order).filter(
        Order.user_id == current_user.user_id,
        Order.payment_status == "pending",
        Order.expired_at > now_naive()
    ).count()

    if pending_count >= MAX_PENDING_ORDERS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"您有 {pending_count} 个未完成的订单，请先完成支付或等待过期"
        )

    # 4. 检查每小时订单限制
    hour_ago = now_naive() - timedelta(hours=1)
    hourly_count = db.query(Order).filter(
        Order.user_id == current_user.user_id,
        Order.created_at >= hour_ago
    ).count()

    if hourly_count >= MAX_ORDERS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="创建订单过于频繁，请稍后再试"
        )

    # 5. 生成订单号
    order_no = payment_manager.generate_order_no()

    # 6. 计算过期时间
    expires_at = now_naive() + timedelta(seconds=ORDER_EXPIRATION_SECONDS)

    # 7. 调用支付SDK生成二维码
    # 从环境变量获取回调URL
    if request.payment_method == "alipay":
        notify_url = os.getenv("ALIPAY_NOTIFY_URL", f"https://yourdomain.com/api/payment/callback/alipay")
    elif request.payment_method == "wechat":
        notify_url = os.getenv("WECHAT_NOTIFY_URL", f"https://yourdomain.com/api/payment/callback/wechat")
    else:
        notify_url = f"https://yourdomain.com/api/payment/callback/{request.payment_method}"

    payment_result = await payment_manager.create_payment(
        payment_method=request.payment_method,
        order_no=order_no,
        amount_fen=tier["price_fen"],
        subject=f"FastMoss积分充值 - {tier['name']}",
        notify_url=notify_url
    )

    if not payment_result.success:
        logger.error(f"创建支付订单失败: {payment_result.error_message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建支付订单失败: {payment_result.error_message}"
        )

    # 8. 创建订单记录
    order = Order(
        order_no=order_no,
        user_id=current_user.user_id,
        tier_id=request.tier_id,
        amount_yuan=tier["price_yuan"],
        credits=tier["credits"],
        payment_method=request.payment_method,
        payment_status="pending",
        qr_code_url=payment_result.qr_code_url,
        expired_at=expires_at,
        meta_data={
            "tier_name": tier["name"],
            "price_fen": tier["price_fen"]
        }
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    logger.info(f"订单创建成功: {order_no}, 用户: {current_user.user_id}, 金额: {tier['price_yuan']}元")

    return CreateOrderResponse(
        order_id=order.order_id,
        order_no=order.order_no,
        qr_code_url=payment_result.qr_code_url,
        qr_code_base64=payment_result.qr_code_base64,
        payment_url=payment_result.payment_url,
        amount_yuan=tier["price_yuan"],
        credits=tier["credits"],
        expires_at=expires_at,
        payment_method=request.payment_method
    )


@router.get("/orders/{order_id}/status", response_model=OrderStatusResponse)
async def get_order_status(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询订单支付状态（用于前端轮询）"""
    order = db.query(Order).filter(
        Order.order_id == order_id,
        Order.user_id == current_user.user_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    # 检查是否已过期
    expired = False
    if order.payment_status == "pending" and order.expired_at:
        if now_naive() > order.expired_at:
            expired = True
            # 自动更新状态为已取消
            order.payment_status = "cancelled"
            db.commit()

    # 如果订单未支付且未过期，返回支付链接
    payment_url = None
    if order.payment_status == "pending" and not expired:
        payment_url = order.qr_code_url  # qr_code_url 实际存储的是 payment_url

    return OrderStatusResponse(
        order_id=order.order_id,
        order_no=order.order_no,
        payment_status=order.payment_status,
        amount_yuan=order.amount_yuan,
        credits=order.credits,
        payment_method=order.payment_method,
        created_at=order.created_at,
        paid_at=order.paid_at,
        expired=expired,
        payment_url=payment_url
    )


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消未支付的订单"""
    order = db.query(Order).filter(
        Order.order_id == order_id,
        Order.user_id == current_user.user_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    if order.payment_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"订单状态为 {order.payment_status}，无法取消"
        )

    order.payment_status = "cancelled"
    db.commit()

    logger.info(f"订单已取消: {order.order_no}")

    return {"message": "订单已取消", "order_no": order.order_no}


@router.get("/orders", response_model=List[OrderListItem])
async def list_user_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 20
):
    """获取用户充值订单历史"""
    orders = db.query(Order).filter(
        Order.user_id == current_user.user_id
    ).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

    return [
        OrderListItem(
            order_id=o.order_id,
            order_no=o.order_no,
            tier_id=o.tier_id,
            tier_name=o.meta_data.get("tier_name", "") if o.meta_data else "",
            amount_yuan=o.amount_yuan,
            credits=o.credits,
            payment_method=o.payment_method,
            payment_status=o.payment_status,
            created_at=o.created_at,
            paid_at=o.paid_at
        )
        for o in orders
    ]


# ==================== Payment Callbacks ====================

async def process_payment_success(order_no: str, trade_no: str, db: Session):
    """
    处理支付成功的订单

    1. 更新订单状态
    2. 增加用户积分
    3. 记录积分变动历史
    """
    order = db.query(Order).filter(Order.order_no == order_no).first()

    if not order:
        logger.error(f"回调订单不存在: {order_no}")
        return False

    # 幂等性检查：如果订单已支付，直接返回成功
    if order.payment_status == "paid":
        logger.info(f"订单已处理过: {order_no}")
        return True

    # 检查订单状态
    if order.payment_status != "pending":
        logger.warning(f"订单状态异常: {order_no}, 当前状态: {order.payment_status}")
        return False

    try:
        # 1. 更新订单状态
        order.payment_status = "paid"
        order.trade_no = trade_no
        order.paid_at = now_naive()

        # 2. 获取或创建用户积分记录
        usage = db.query(UserUsage).filter(
            UserUsage.user_id == order.user_id
        ).first()

        if not usage:
            usage = UserUsage(user_id=order.user_id, total_credits=0, used_credits=0)
            db.add(usage)
            db.flush()

        # 3. 增加积分
        before_credits = usage.total_credits
        usage.total_credits += order.credits
        after_credits = usage.total_credits

        # 4. 记录积分变动历史
        credit_history = CreditHistory(
            user_id=order.user_id,
            change_type="recharge",
            amount=order.credits,
            before_credits=before_credits,
            after_credits=after_credits,
            reason=f"充值 {order.amount_yuan} 元",
            related_order_id=order.order_id,
            meta_data={
                "order_no": order.order_no,
                "tier_id": order.tier_id,
                "payment_method": order.payment_method,
                "trade_no": trade_no
            }
        )
        db.add(credit_history)

        db.commit()

        logger.info(f"支付成功处理完成: 订单={order_no}, 用户={order.user_id}, 积分+{order.credits}")
        return True

    except Exception as e:
        db.rollback()
        logger.exception(f"处理支付成功失败: {e}")
        return False


@router.post("/orders/{order_id}/simulate-pay")
async def simulate_payment(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    模拟支付成功（仅用于本地调试）
    生产环境应删除此接口
    """
    order = db.query(Order).filter(
        Order.order_id == order_id,
        Order.user_id == current_user.user_id
    ).first()

    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.payment_status != "pending":
        raise HTTPException(status_code=400, detail=f"订单状态为 {order.payment_status}，无法模拟支付")

    # 模拟支付成功
    success = await process_payment_success(
        order_no=order.order_no,
        trade_no=f"SIMULATE_{order.order_no}",
        db=db
    )

    if success:
        return {"message": "模拟支付成功", "credits": order.credits}
    else:
        raise HTTPException(status_code=500, detail="处理失败")


@router.post("/callback/alipay")
async def alipay_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """支付宝异步回调通知"""
    try:
        # 获取表单数据
        form_data = await request.form()
        data = dict(form_data)

        logger.info(f"收到支付宝回调: {data.get('out_trade_no')}")

        # 验证签名并解析通知
        notification = await payment_manager.verify_notification("alipay", data)

        if not notification.success:
            logger.warning(f"支付宝回调验证失败: {notification.error_message}")
            return PlainTextResponse("fail")

        # 处理支付成功
        success = await process_payment_success(
            order_no=notification.order_no,
            trade_no=notification.trade_no,
            db=db
        )

        if success:
            return PlainTextResponse("success")
        else:
            return PlainTextResponse("fail")

    except Exception as e:
        logger.exception(f"处理支付宝回调异常: {e}")
        return PlainTextResponse("fail")


@router.post("/callback/wechat")
async def wechat_callback(
    request: Request,
    db: Session = Depends(get_db)
):
    """微信支付异步回调通知"""
    try:
        # 获取请求头和请求体
        headers = dict(request.headers)
        body = await request.body()

        logger.info("收到微信支付回调")

        # 验证签名并解析通知
        notification = await payment_manager.verify_notification("wechat", {
            "headers": headers,
            "body": body.decode('utf-8')
        })

        if not notification.success:
            logger.warning(f"微信支付回调验证失败: {notification.error_message}")
            return {"code": "FAIL", "message": notification.error_message}

        # 处理支付成功
        success = await process_payment_success(
            order_no=notification.order_no,
            trade_no=notification.trade_no,
            db=db
        )

        if success:
            return {"code": "SUCCESS", "message": "成功"}
        else:
            return {"code": "FAIL", "message": "处理失败"}

    except Exception as e:
        logger.exception(f"处理微信支付回调异常: {e}")
        return {"code": "FAIL", "message": str(e)}


# ==================== 积分历史查询 ====================

class CreditHistoryItem(BaseModel):
    """积分历史记录"""
    history_id: str
    change_type: str
    amount: int
    before_credits: int
    after_credits: int
    reason: Optional[str]
    created_at: datetime
    order_no: Optional[str] = None  # 关联的订单号
    report_title: Optional[str] = None  # 关联的报告标题


@router.get("/credit-history", response_model=List[CreditHistoryItem])
async def get_credit_history(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取用户积分变动历史

    - **limit**: 返回记录数量（默认50，最大100）
    - **offset**: 跳过记录数量（用于分页）
    """
    # 限制最大查询数量
    limit = min(limit, 100)

    # 查询积分历史记录
    histories = db.query(CreditHistory).filter(
        CreditHistory.user_id == current_user.user_id
    ).order_by(
        CreditHistory.created_at.desc()
    ).limit(limit).offset(offset).all()

    # 构建响应数据
    result = []
    for history in histories:
        # 获取关联的订单号
        order_no = None
        if history.related_order_id:
            order = db.query(Order).filter(Order.order_id == history.related_order_id).first()
            if order:
                order_no = order.order_no

        # 获取关联的报告标题
        report_title = None
        if history.related_report_id:
            from database.models import Report
            report = db.query(Report).filter(Report.report_id == history.related_report_id).first()
            if report:
                report_title = report.report_name or "达人推荐报告"

        result.append(CreditHistoryItem(
            history_id=history.history_id,
            change_type=history.change_type,
            amount=history.amount,
            before_credits=history.before_credits,
            after_credits=history.after_credits,
            reason=history.reason,
            created_at=history.created_at,
            order_no=order_no,
            report_title=report_title
        ))

    return result
