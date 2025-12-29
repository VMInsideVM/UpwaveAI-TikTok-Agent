"""
Admin Payment API Endpoints
管理员支付管理 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import logging

from database.connection import get_db
from database.models import User, UserUsage, Order, Refund, CreditHistory
from auth.dependencies import get_current_admin_user
from config.pricing import get_tier_by_id, CREDIT_TIERS
from services.payment.manager import payment_manager

logger = logging.getLogger(__name__)

# 东八区时区
CHINA_TZ = timezone(timedelta(hours=8))

router = APIRouter(prefix="/api/admin/payment", tags=["管理员-支付管理"])


# ==================== Pydantic Models ====================

class AdminOrderListItem(BaseModel):
    """管理员订单列表项"""
    order_id: str
    order_no: str
    user_id: str
    username: Optional[str]
    phone_number: Optional[str]
    tier_id: str
    tier_name: str
    amount_yuan: int
    credits: int
    payment_method: str
    payment_status: str
    trade_no: Optional[str]
    created_at: datetime
    paid_at: Optional[datetime]
    refunded_amount: int = 0  # 已退款金额


class AdminOrderDetail(BaseModel):
    """管理员订单详情"""
    order_id: str
    order_no: str
    user_id: str
    username: Optional[str]
    phone_number: Optional[str]
    email: Optional[str]
    tier_id: str
    tier_name: str
    amount_yuan: int
    credits: int
    payment_method: str
    payment_status: str
    trade_no: Optional[str]
    qr_code_url: Optional[str]
    created_at: datetime
    paid_at: Optional[datetime]
    expired_at: Optional[datetime]
    refunds: List[dict] = []
    meta_data: Optional[dict]


class RefundRequest(BaseModel):
    """退款请求"""
    refund_amount_yuan: int  # 退款金额（元）
    reason: str


class RefundReviewRequest(BaseModel):
    """审核退款请求"""
    action: str  # approve(同意) 或 reject(拒绝)
    admin_reason: Optional[str] = None  # 拒绝原因（拒绝时必填）


class RefundListItem(BaseModel):
    """退款列表项"""
    refund_id: str
    refund_no: str
    order_no: str
    user_id: str
    username: Optional[str]
    refund_amount_yuan: int
    refund_credits: int
    status: str
    reason: str
    admin_username: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]


class OrderStatistics(BaseModel):
    """订单统计"""
    total_revenue_yuan: int  # 总收入
    total_orders: int  # 总订单数
    paid_orders: int  # 已支付订单数
    pending_orders: int  # 待支付订单数
    refunded_orders: int  # 已退款订单数
    total_refunded_yuan: int  # 总退款金额
    today_revenue_yuan: int  # 今日收入
    today_orders: int  # 今日订单数
    pending_refunds: int  # 待处理退款数


# ==================== API Endpoints ====================

@router.get("/orders", response_model=List[AdminOrderListItem])
async def list_all_orders(
    skip: int = 0,
    limit: int = 50,
    payment_status: Optional[str] = None,
    payment_method: Optional[str] = None,
    user_search: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """列出所有订单（支持筛选）"""
    query = db.query(Order, User).join(User, Order.user_id == User.user_id)

    # 状态筛选
    if payment_status and payment_status != "all":
        query = query.filter(Order.payment_status == payment_status)

    # 支付方式筛选
    if payment_method and payment_method != "all":
        query = query.filter(Order.payment_method == payment_method)

    # 用户搜索
    if user_search:
        query = query.filter(
            (User.username.contains(user_search)) |
            (User.phone_number.contains(user_search)) |
            (Order.order_no.contains(user_search))
        )

    # 时间范围筛选
    if created_after:
        query = query.filter(Order.created_at >= created_after)
    if created_before:
        query = query.filter(Order.created_at <= created_before)

    # 排序和分页
    results = query.order_by(Order.created_at.desc()).offset(skip).limit(limit).all()

    order_list = []
    for order, user in results:
        # 计算已退款金额
        refunded_amount = db.query(func.sum(Refund.refund_amount_yuan)).filter(
            Refund.order_id == order.order_id,
            Refund.status == "success"
        ).scalar() or 0

        tier_name = ""
        if order.meta_data and "tier_name" in order.meta_data:
            tier_name = order.meta_data["tier_name"]
        else:
            tier = get_tier_by_id(order.tier_id)
            tier_name = tier["name"] if tier else ""

        order_list.append(AdminOrderListItem(
            order_id=order.order_id,
            order_no=order.order_no,
            user_id=order.user_id,
            username=user.username,
            phone_number=user.phone_number,
            tier_id=order.tier_id,
            tier_name=tier_name,
            amount_yuan=order.amount_yuan,
            credits=order.credits,
            payment_method=order.payment_method,
            payment_status=order.payment_status,
            trade_no=order.trade_no,
            created_at=order.created_at,
            paid_at=order.paid_at,
            refunded_amount=refunded_amount
        ))

    return order_list


@router.get("/orders/{order_id}", response_model=AdminOrderDetail)
async def get_order_detail(
    order_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取订单详情"""
    order = db.query(Order).filter(Order.order_id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    user = db.query(User).filter(User.user_id == order.user_id).first()

    # 获取退款记录
    refunds = db.query(Refund).filter(Refund.order_id == order_id).all()
    refund_list = [
        {
            "refund_id": r.refund_id,
            "refund_no": r.refund_no,
            "refund_amount_yuan": r.refund_amount_yuan,
            "refund_credits": r.refund_credits,
            "status": r.status,
            "reason": r.reason,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None
        }
        for r in refunds
    ]

    tier_name = ""
    if order.meta_data and "tier_name" in order.meta_data:
        tier_name = order.meta_data["tier_name"]
    else:
        tier = get_tier_by_id(order.tier_id)
        tier_name = tier["name"] if tier else ""

    return AdminOrderDetail(
        order_id=order.order_id,
        order_no=order.order_no,
        user_id=order.user_id,
        username=user.username if user else None,
        phone_number=user.phone_number if user else None,
        email=user.email if user else None,
        tier_id=order.tier_id,
        tier_name=tier_name,
        amount_yuan=order.amount_yuan,
        credits=order.credits,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        trade_no=order.trade_no,
        qr_code_url=order.qr_code_url,
        created_at=order.created_at,
        paid_at=order.paid_at,
        expired_at=order.expired_at,
        refunds=refund_list,
        meta_data=order.meta_data
    )


@router.post("/orders/{order_id}/refund")
async def process_refund(
    order_id: str,
    request: RefundRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    处理退款

    1. 验证订单可退款
    2. 计算退款积分
    3. 调用支付平台退款
    4. 扣除用户积分
    5. 记录积分变动
    """
    order = db.query(Order).filter(Order.order_id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    # 验证订单状态
    if order.payment_status not in ["paid", "partial_refunded"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"订单状态为 {order.payment_status}，无法退款"
        )

    # 计算已退款金额
    refunded_total = db.query(func.sum(Refund.refund_amount_yuan)).filter(
        Refund.order_id == order_id,
        Refund.status == "success"
    ).scalar() or 0

    # 检查退款金额
    max_refundable = order.amount_yuan - refunded_total
    if request.refund_amount_yuan <= 0 or request.refund_amount_yuan > max_refundable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"退款金额无效，最大可退款 {max_refundable} 元"
        )

    # 计算退款积分（按比例）
    refund_credits = int(order.credits * (request.refund_amount_yuan / order.amount_yuan))

    # 生成退款单号
    refund_no = payment_manager.generate_refund_no()

    # 创建退款记录
    refund = Refund(
        order_id=order_id,
        refund_no=refund_no,
        refund_amount_yuan=request.refund_amount_yuan,
        refund_credits=refund_credits,
        status="processing",
        reason=request.reason,
        admin_id=admin_user.user_id
    )
    db.add(refund)
    db.flush()

    try:
        # 调用支付平台退款
        refund_result = await payment_manager.refund(
            payment_method=order.payment_method,
            order_no=order.order_no,
            refund_no=refund_no,
            refund_amount_fen=request.refund_amount_yuan * 100,
            total_amount_fen=order.amount_yuan * 100,
            reason=request.reason
        )

        if refund_result.success:
            # 更新退款状态
            refund.status = "success"
            refund.refund_trade_no = refund_result.refund_trade_no
            refund.processed_at = datetime.now(CHINA_TZ).replace(tzinfo=None)

            # 更新订单状态
            new_refunded_total = refunded_total + request.refund_amount_yuan
            if new_refunded_total >= order.amount_yuan:
                order.payment_status = "refunded"
            else:
                order.payment_status = "partial_refunded"

            # 扣除用户积分
            usage = db.query(UserUsage).filter(
                UserUsage.user_id == order.user_id
            ).first()

            if usage:
                before_credits = usage.total_credits
                usage.total_credits = max(0, usage.total_credits - refund_credits)
                after_credits = usage.total_credits

                # 记录积分变动
                credit_history = CreditHistory(
                    user_id=order.user_id,
                    change_type="refund_deduct",
                    amount=-refund_credits,
                    before_credits=before_credits,
                    after_credits=after_credits,
                    reason=f"退款扣除 ({request.reason})",
                    related_order_id=order_id,
                    meta_data={
                        "refund_no": refund_no,
                        "refund_amount_yuan": request.refund_amount_yuan,
                        "admin_id": admin_user.user_id
                    }
                )
                db.add(credit_history)

            db.commit()

            logger.info(f"退款成功: 订单={order.order_no}, 退款={refund_no}, 金额={request.refund_amount_yuan}元")

            return {
                "success": True,
                "message": "退款成功",
                "refund_no": refund_no,
                "refund_credits": refund_credits
            }
        else:
            refund.status = "failed"
            refund.error_message = refund_result.error_message
            refund.processed_at = datetime.now(CHINA_TZ).replace(tzinfo=None)
            db.commit()

            logger.error(f"退款失败: {refund_result.error_message}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"退款失败: {refund_result.error_message}"
            )

    except HTTPException:
        raise
    except Exception as e:
        refund.status = "failed"
        refund.error_message = str(e)
        refund.processed_at = datetime.utcnow()
        db.commit()

        logger.exception(f"退款异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"退款异常: {str(e)}"
        )


@router.get("/refunds", response_model=List[RefundListItem])
async def list_refunds(
    skip: int = 0,
    limit: int = 50,
    refund_status: Optional[str] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """列出所有退款记录"""
    query = db.query(Refund, Order, User).join(
        Order, Refund.order_id == Order.order_id
    ).join(
        User, Order.user_id == User.user_id
    )

    if refund_status and refund_status != "all":
        query = query.filter(Refund.status == refund_status)

    results = query.order_by(Refund.created_at.desc()).offset(skip).limit(limit).all()

    refund_list = []
    for refund, order, user in results:
        # 获取处理管理员用户名
        admin_username = None
        if refund.admin_id:
            admin = db.query(User).filter(User.user_id == refund.admin_id).first()
            admin_username = admin.username if admin else None

        refund_list.append(RefundListItem(
            refund_id=refund.refund_id,
            refund_no=refund.refund_no,
            order_no=order.order_no,
            user_id=order.user_id,
            username=user.username,
            refund_amount_yuan=refund.refund_amount_yuan,
            refund_credits=refund.refund_credits,
            status=refund.status,
            reason=refund.reason,
            admin_username=admin_username,
            created_at=refund.created_at,
            processed_at=refund.processed_at,
            error_message=refund.error_message
        ))

    return refund_list


@router.post("/refunds/{refund_id}/review")
async def review_refund_request(
    refund_id: str,
    request: RefundReviewRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    审核用户退款申请

    action: approve (同意) 或 reject (拒绝)
    """
    # 查询退款记录
    refund = db.query(Refund).filter(Refund.refund_id == refund_id).first()

    if not refund:
        raise HTTPException(status_code=404, detail="退款记录不存在")

    # 只能审核 pending 状态的退款
    if refund.status != "pending":
        raise HTTPException(status_code=400, detail=f"退款状态为 {refund.status}，无法审核")

    # 查询关联订单
    order = db.query(Order).filter(Order.order_id == refund.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="关联订单不存在")

    if request.action == "reject":
        # 拒绝退款
        if not request.admin_reason:
            raise HTTPException(status_code=400, detail="拒绝退款时必须填写原因")

        refund.status = "rejected"
        refund.admin_id = admin_user.user_id
        refund.error_message = request.admin_reason
        refund.processed_at = datetime.utcnow()
        db.commit()

        logger.info(f"管理员 {admin_user.username} 拒绝退款: {refund.refund_no}, 原因: {request.admin_reason}")

        return {
            "success": True,
            "message": "已拒绝退款申请",
            "refund_no": refund.refund_no
        }

    elif request.action == "approve":
        # 同意退款，开始处理
        refund.status = "processing"
        refund.admin_id = admin_user.user_id
        db.flush()

        try:
            # 调用支付平台退款
            refund_result = await payment_manager.refund(
                payment_method=order.payment_method,
                order_no=order.order_no,
                refund_no=refund.refund_no,
                refund_amount_fen=refund.refund_amount_yuan * 100,
                total_amount_fen=order.amount_yuan * 100,
                reason=refund.reason
            )

            if refund_result.success:
                # 退款成功
                refund.status = "success"
                refund.refund_trade_no = refund_result.refund_trade_no
                refund.processed_at = datetime.now(CHINA_TZ).replace(tzinfo=None)

                # 更新订单状态（计算包含当前退款的总额）
                # 查询其他已成功的退款总额
                other_refunded = db.query(func.sum(Refund.refund_amount_yuan)).filter(
                    Refund.order_id == order.order_id,
                    Refund.refund_id != refund.refund_id,
                    Refund.status == "success"
                ).scalar() or 0

                # 加上当前退款金额
                refunded_total = other_refunded + refund.refund_amount_yuan

                if refunded_total >= order.amount_yuan:
                    order.payment_status = "refunded"
                else:
                    order.payment_status = "partial_refunded"

                # 扣除用户积分
                usage = db.query(UserUsage).filter(
                    UserUsage.user_id == order.user_id
                ).first()

                if usage:
                    before_credits = usage.total_credits
                    usage.total_credits = max(0, usage.total_credits - refund.refund_credits)
                    after_credits = usage.total_credits

                    # 记录积分变动
                    credit_history = CreditHistory(
                        user_id=order.user_id,
                        change_type="refund_deduct",
                        amount=-refund.refund_credits,
                        before_credits=before_credits,
                        after_credits=after_credits,
                        reason=f"退款扣除 ({refund.reason})",
                        related_order_id=order.order_id,
                        meta_data={
                            "refund_no": refund.refund_no,
                            "refund_amount_yuan": refund.refund_amount_yuan,
                            "admin_id": admin_user.user_id
                        }
                    )
                    db.add(credit_history)

                db.commit()

                logger.info(f"退款成功: 订单={order.order_no}, 退款={refund.refund_no}, 金额={refund.refund_amount_yuan}元")

                return {
                    "success": True,
                    "message": "退款成功",
                    "refund_no": refund.refund_no,
                    "refund_credits": refund.refund_credits
                }
            else:
                # 退款失败
                refund.status = "failed"
                refund.error_message = refund_result.error_message
                refund.processed_at = datetime.now(CHINA_TZ).replace(tzinfo=None)
                db.commit()

                logger.error(f"退款失败: {refund.refund_no}, 错误: {refund_result.error_message}")

                raise HTTPException(
                    status_code=500,
                    detail=f"退款失败: {refund_result.error_message}"
                )

        except Exception as e:
            refund.status = "failed"
            refund.error_message = str(e)
            refund.processed_at = datetime.utcnow()
            db.commit()

            logger.exception(f"退款异常: {refund.refund_no}")
            raise HTTPException(status_code=500, detail=f"退款异常: {str(e)}")

    else:
        raise HTTPException(status_code=400, detail="action 必须为 approve 或 reject")


@router.get("/statistics", response_model=OrderStatistics)
async def get_order_statistics(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """获取订单统计数据"""
    # 总收入（已支付订单）
    total_revenue = db.query(func.sum(Order.amount_yuan)).filter(
        Order.payment_status.in_(["paid", "partial_refunded", "refunded"])
    ).scalar() or 0

    # 总订单数
    total_orders = db.query(func.count(Order.order_id)).scalar() or 0

    # 已支付订单数
    paid_orders = db.query(func.count(Order.order_id)).filter(
        Order.payment_status.in_(["paid", "partial_refunded"])
    ).scalar() or 0

    # 待支付订单数
    pending_orders = db.query(func.count(Order.order_id)).filter(
        Order.payment_status == "pending"
    ).scalar() or 0

    # 已退款订单数
    refunded_orders = db.query(func.count(Order.order_id)).filter(
        Order.payment_status == "refunded"
    ).scalar() or 0

    # 总退款金额
    total_refunded = db.query(func.sum(Refund.refund_amount_yuan)).filter(
        Refund.status == "success"
    ).scalar() or 0

    # 今日数据
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    today_revenue = db.query(func.sum(Order.amount_yuan)).filter(
        Order.payment_status.in_(["paid", "partial_refunded", "refunded"]),
        Order.paid_at >= today_start
    ).scalar() or 0

    today_orders = db.query(func.count(Order.order_id)).filter(
        Order.created_at >= today_start
    ).scalar() or 0

    # 待处理退款
    pending_refunds = db.query(func.count(Refund.refund_id)).filter(
        Refund.status == "pending"
    ).scalar() or 0

    return OrderStatistics(
        total_revenue_yuan=total_revenue,
        total_orders=total_orders,
        paid_orders=paid_orders,
        pending_orders=pending_orders,
        refunded_orders=refunded_orders,
        total_refunded_yuan=total_refunded,
        today_revenue_yuan=today_revenue,
        today_orders=today_orders,
        pending_refunds=pending_refunds
    )


@router.get("/credit-changes")
async def list_all_credit_changes(
    skip: int = 0,
    limit: int = 50,
    change_type: Optional[str] = None,
    user_search: Optional[str] = None,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """列出所有积分变动记录（包含充值和退款）"""
    query = db.query(CreditHistory, User).join(
        User, CreditHistory.user_id == User.user_id
    )

    # 类型筛选
    if change_type and change_type != "all":
        query = query.filter(CreditHistory.change_type == change_type)

    # 用户搜索
    if user_search:
        query = query.filter(
            (User.username.contains(user_search)) |
            (User.phone_number.contains(user_search))
        )

    results = query.order_by(CreditHistory.created_at.desc()).offset(skip).limit(limit).all()

    return [
        {
            "history_id": h.history_id,
            "user_id": h.user_id,
            "username": u.username,
            "phone_number": u.phone_number,
            "change_type": h.change_type,
            "amount": h.amount,
            "before_credits": h.before_credits,
            "after_credits": h.after_credits,
            "reason": h.reason,
            "related_order_id": h.related_order_id,
            "related_report_id": h.related_report_id,
            "created_at": h.created_at.isoformat() if h.created_at else None,
            "meta_data": h.meta_data
        }
        for h, u in results
    ]
