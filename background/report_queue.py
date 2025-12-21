"""
Report Generation Queue
报告生成队列系统（异步后台任务）
"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import json
import os
from pathlib import Path

from database.connection import get_db_context
from database.models import Report, UserUsage


class ReportQueue:
    """报告生成队列（单线程串行处理）"""

    def __init__(self):
        self._queue = asyncio.Queue()  # 任务队列
        self._current_task: Optional[str] = None  # 当前正在执行的任务
        self._is_processing = False  # 是否正在处理
        self._task_statuses: Dict[str, dict] = {}  # report_id -> status dict
        self._processor_task: Optional[asyncio.Task] = None

    async def enqueue_report(
        self,
        report_id: str,
        user_id: str,
        session_id: str,
        json_file_path: str,
        product_name: str,
        credits_deducted: int = 0
    ) -> str:
        """
        将报告生成任务加入队列

        Args:
            report_id: 报告 ID
            user_id: 用户 ID
            session_id: 会话 ID
            json_file_path: JSON 数据文件路径
            product_name: 产品名称
            credits_deducted: 已扣除的积分数量（用于失败时退还）

        Returns:
            str: 报告 ID
        """
        # 添加到队列
        await self._queue.put({
            "report_id": report_id,
            "user_id": user_id,
            "session_id": session_id,
            "json_file_path": json_file_path,
            "product_name": product_name,
            "credits_deducted": credits_deducted
        })

        # 初始化状态
        self._task_statuses[report_id] = {
            "report_id": report_id,
            "status": "queued",
            "progress": 0,
            "queue_position": self._queue.qsize(),
            "created_at": datetime.utcnow().isoformat()
        }

        # 如果队列处理器未运行，启动它
        if not self._is_processing:
            self._processor_task = asyncio.create_task(self._process_queue())

        return report_id

    async def _process_queue(self):
        """
        单线程队列处理器（串行处理报告生成）

        由于 Playwright 是单浏览器实例，必须一个接一个处理
        """
        self._is_processing = True
        print("🚀 报告队列处理器启动")

        while True:
            try:
                # 从队列获取任务（阻塞等待，5秒超时）
                try:
                    task_data = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    # 队列空闲，检查是否应该停止
                    if self._queue.empty():
                        break
                    continue

                report_id = task_data["report_id"]
                self._current_task = report_id

                print(f"📊 开始生成报告: {report_id}")

                # 更新状态为 'generating'
                await self._update_status(report_id, "generating", progress=10)

                # 执行报告生成
                try:
                    await self._generate_report(task_data)
                    await self._update_status(report_id, "completed", progress=100)

                    print(f"✅ 报告生成完成: {report_id}")

                except Exception as e:
                    error_msg = str(e)
                    await self._update_status(report_id, "failed", error=error_msg)

                    # 失败时退还积分
                    credits_to_refund = task_data.get("credits_deducted", 0)
                    if credits_to_refund > 0:
                        await self._refund_user_credits(task_data["user_id"], credits_to_refund)

                    print(f"❌ 报告生成失败: {report_id} - {error_msg}")

                self._current_task = None
                self._queue.task_done()

            except asyncio.CancelledError:
                print("⚠️ 报告队列处理器被取消")
                break
            except Exception as e:
                print(f"❌ 队列处理器错误: {e}")

        self._is_processing = False
        print("🛑 报告队列处理器停止")

    async def _generate_report(self, task_data: dict):
        """
        调用 report_agent.py 生成报告

        注意：这是同步操作，会阻塞队列

        Args:
            task_data: 任务数据
        """
        report_id = task_data["report_id"]
        json_file_path = task_data["json_file_path"]
        product_name = task_data["product_name"]

        # 检查 JSON 文件是否存在
        if not os.path.exists(json_file_path):
            raise FileNotFoundError(f"数据文件不存在: {json_file_path}")

        # 读取 JSON 文件获取达人列表
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        influencer_ids = data.get("data_row_keys", [])
        if not influencer_ids:
            raise ValueError("数据文件中没有达人 ID")

        # 动态导入 report_agent（避免循环导入）
        try:
            from report_agent import TikTokInfluencerReportAgent

            # 创建报告生成器
            report_agent = TikTokInfluencerReportAgent()

            # 估算完成时间（每个达人约 10 秒）
            estimated_time = len(influencer_ids) * 10

            # 更新数据库中的预估时间
            with get_db_context() as db:
                report = db.query(Report).filter(Report.report_id == report_id).first()
                if report:
                    report.estimated_time = estimated_time
                    db.commit()

            # 创建进度回调函数（异步更新状态）
            def progress_callback(progress: int):
                """进度回调函数（同步，但会调度异步更新）"""
                # 在事件循环中调度异步更新
                asyncio.create_task(
                    self._update_status(report_id, "generating", progress=progress)
                )

            # 生成报告（同步调用）
            # 在事件循环中运行同步函数
            loop = asyncio.get_event_loop()
            report_path = await loop.run_in_executor(
                None,
                report_agent.generate_report,
                json_file_path,  # json_filename
                f"为{product_name}推荐达人",  # user_query
                10,  # target_count
                f"产品名称: {product_name}",  # product_info
                progress_callback  # progress_callback
            )

            # 更新数据库中的报告路径和状态
            with get_db_context() as db:
                report = db.query(Report).filter(Report.report_id == report_id).first()
                if report:
                    report.report_path = report_path
                    report.status = "completed"
                    report.completed_at = datetime.utcnow()
                    db.commit()

                    # 发送通知（异步）
                    asyncio.create_task(
                        self._send_report_notifications(
                            report_id=report_id,
                            user_id=task_data["user_id"],
                            product_name=product_name,
                            report_path=report_path
                        )
                    )

            print(f"✅ 报告已保存到: {report_path}")

        except ImportError as e:
            raise RuntimeError(f"无法导入报告生成器: {e}")

    async def _update_status(
        self,
        report_id: str,
        status: str,
        progress: int = 0,
        error: Optional[str] = None
    ):
        """
        更新任务状态

        Args:
            report_id: 报告 ID
            status: 状态
            progress: 进度（0-100）
            error: 错误信息
        """
        self._task_statuses[report_id] = {
            "report_id": report_id,
            "status": status,
            "progress": progress,
            "error": error,
            "updated_at": datetime.utcnow().isoformat()
        }

        # 同步更新数据库
        with get_db_context() as db:
            report = db.query(Report).filter(Report.report_id == report_id).first()
            if report:
                report.status = status
                if error:
                    report.error_message = error
                if status == "completed":
                    report.completed_at = datetime.utcnow()
                db.commit()

    async def _send_report_notifications(
        self,
        report_id: str,
        user_id: str,
        product_name: str,
        report_path: str
    ):
        """
        发送报告完成通知（短信 + 邮件）

        Args:
            report_id: 报告 ID
            user_id: 用户 ID
            product_name: 产品名称
            report_path: 报告文件路径
        """
        try:
            # 导入服务
            from services.sms_service import get_sms_service
            from services.email_service import get_email_service
            from database.models import User, Report

            # 获取用户信息和报告完成时间
            completed_at = None
            session_id = None
            with get_db_context() as db:
                user = db.query(User).filter(User.user_id == user_id).first()
                if not user:
                    print(f"⚠️ 用户不存在，跳过通知: {user_id}")
                    return

                username = user.username or "用户"
                phone = user.phone_number
                email = user.email

                # 获取报告的完成时间和会话ID
                if report_id:
                    report = db.query(Report).filter(Report.report_id == report_id).first()
                    if report:
                        if report.completed_at:
                            completed_at = report.completed_at
                        session_id = report.session_id

            # ⭐ 构建报告访问URL（使用会话ID和报告ID）
            if session_id and report_id:
                # 指向聊天界面的报告详情
                report_url = f"http://127.0.0.1:8001/?session={session_id}#report-{report_id}"
            else:
                # 后备方案：直接链接HTML文件
                report_filename = os.path.basename(report_path)
                report_url = f"http://127.0.0.1:8001/reports/{report_filename}"

            # 1. 发送短信通知
            if phone:
                sms_service = get_sms_service()
                success, message = sms_service.send_report_ready_notification(
                    phone=phone,
                    product_name=product_name
                )
                if success:
                    print(f"✅ 短信通知已发送: {phone}")
                else:
                    print(f"⚠️ 短信通知发送失败: {message}")
            else:
                print(f"⚠️ 用户未绑定手机号，跳过短信通知: {username}")

            # 2. 发送邮件通知
            if email:
                email_service = get_email_service()
                if email_service.is_configured():
                    success, message = email_service.send_report_ready_notification(
                        to_email=email,
                        username=username,
                        product_name=product_name,
                        report_url=report_url,
                        completed_at=completed_at
                    )
                    if success:
                        print(f"✅ 邮件通知已发送: {email}")
                    else:
                        print(f"⚠️ 邮件通知发送失败: {message}")
                else:
                    print("⚠️ 邮件服务未配置，跳过邮件通知")
            else:
                print(f"⚠️ 用户未设置邮箱，跳过邮件通知: {username}")

        except Exception as e:
            print(f"❌ 发送通知时发生错误: {e}")
            # 不抛出异常，避免影响报告生成流程

    async def _refund_user_credits(self, user_id: str, credits_amount: int):
        """
        退还用户积分（报告生成失败时调用）

        Args:
            user_id: 用户 ID
            credits_amount: 要退还的积分数量
        """
        with get_db_context() as db:
            usage = db.query(UserUsage).filter(UserUsage.user_id == user_id).first()
            if usage and usage.used_credits >= credits_amount:
                usage.used_credits -= credits_amount
                db.commit()
                print(f"♻️ 用户 {user_id} 积分已退还: {credits_amount} 积分, 剩余: {usage.remaining_credits}/{usage.total_credits}")

    def get_task_status(self, report_id: str) -> Optional[dict]:
        """
        获取报告生成状态（实时）

        Args:
            report_id: 报告 ID

        Returns:
            Optional[dict]: 状态信息
        """
        return self._task_statuses.get(report_id)

    def get_all_tasks(self) -> dict:
        """
        获取所有任务（用于管理后台）

        Returns:
            dict: 任务队列信息
        """
        # 计算队列位置
        all_statuses = []
        position = 1

        for report_id, status in self._task_statuses.items():
            if status["status"] == "queued":
                status["queue_position"] = position
                position += 1
            all_statuses.append(status)

        return {
            "current_task": self._current_task,
            "queue_size": self._queue.qsize(),
            "is_processing": self._is_processing,
            "all_statuses": all_statuses
        }

    async def stop(self):
        """停止队列处理器"""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass


# 全局实例
report_queue = ReportQueue()
