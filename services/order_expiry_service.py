"""
订单超时检查服务
定期检查并取消超时的待支付订单
"""

import asyncio
from datetime import datetime
from sqlalchemy import and_
from database.connection import get_db_context
from database.models import Order


class OrderExpiryService:
    """订单超时检查服务（单例）"""

    _instance = None
    _task = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._running = False

    async def start(self):
        """启动定时检查任务"""
        if self._running:
            print("⚠️  订单超时检查服务已在运行")
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        print("✅ 订单超时检查服务已启动（每分钟检查一次）")

    async def stop(self):
        """停止定时检查任务"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("⏹️  订单超时检查服务已停止")

    async def _check_loop(self):
        """定时检查循环（每分钟执行一次）"""
        while self._running:
            try:
                await self.check_and_cancel_expired_orders()
                # 等待60秒后再次检查
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ 订单超时检查出错: {e}")
                import traceback
                traceback.print_exc()
                # 出错后等待60秒再继续
                await asyncio.sleep(60)

    async def check_and_cancel_expired_orders(self):
        """检查并取消所有超时的待支付订单"""
        try:
            with get_db_context() as db:
                # 查找所有超时的待支付订单
                now = datetime.now()
                expired_orders = db.query(Order).filter(
                    and_(
                        Order.payment_status == "pending",
                        Order.expired_at != None,
                        Order.expired_at < now
                    )
                ).all()

                if not expired_orders:
                    return

                # 批量取消订单
                cancelled_count = 0
                for order in expired_orders:
                    order.payment_status = "cancelled"
                    cancelled_count += 1
                    print(f"⏰ 自动取消超时订单: {order.order_no} (用户: {order.user_id}, 创建于: {order.created_at})")

                db.commit()

                if cancelled_count > 0:
                    print(f"✅ 成功取消 {cancelled_count} 个超时订单")

        except Exception as e:
            print(f"❌ 取消超时订单失败: {e}")
            import traceback
            traceback.print_exc()


# 全局单例
order_expiry_service = OrderExpiryService()
