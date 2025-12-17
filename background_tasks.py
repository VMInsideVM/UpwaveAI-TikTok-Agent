"""
后台任务队列系统
用于异步执行达人搜索和报告生成任务
"""

import asyncio
import threading
import uuid
import re
from typing import Dict, List, Optional
from datetime import datetime
import json
from pathlib import Path

# 导入数据库和报告相关模块
from database.connection import get_db_context
from database.models import Report
from sqlalchemy import update


class BackgroundTaskQueue:
    """后台任务队列（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.tasks: Dict[str, Dict] = {}  # task_id -> task_info
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running = False
        self._lock = threading.Lock()

        # 启动工作线程
        self.start_worker()

    def start_worker(self):
        """启动后台工作线程"""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            print("✅ 后台任务队列已启动")

    def _worker_loop(self):
        """工作线程循环，处理队列中的任务"""
        while self.is_running:
            try:
                # 查找待处理的任务
                task_to_process = None
                with self._lock:
                    for task_id, task_info in self.tasks.items():
                        if task_info['status'] == 'queued':
                            task_to_process = (task_id, task_info)
                            break

                if task_to_process:
                    task_id, task_info = task_to_process
                    self._process_task(task_id, task_info)
                else:
                    # 没有任务，等待 1 秒
                    threading.Event().wait(1)

            except Exception as e:
                print(f"❌ 后台任务队列错误: {e}")
                import traceback
                traceback.print_exc()

    def _process_task(self, task_id: str, task_info: Dict):
        """处理单个任务"""
        try:
            # 更新状态为处理中
            with self._lock:
                self.tasks[task_id]['status'] = 'generating'
                self.tasks[task_id]['started_at'] = datetime.now().isoformat()

            # 更新数据库状态
            self._update_report_status(task_info['report_id'], 'generating')

            print(f"🔄 开始处理任务: {task_id} (报告 ID: {task_info['report_id']})")

            # 执行爬取任务
            self._execute_scraping_task(task_info)

            # 标记为完成
            with self._lock:
                self.tasks[task_id]['status'] = 'completed'
                self.tasks[task_id]['completed_at'] = datetime.now().isoformat()

            # 更新数据库状态
            self._update_report_status(task_info['report_id'], 'completed')

            print(f"✅ 任务完成: {task_id}")

        except Exception as e:
            error_msg = str(e)
            print(f"❌ 任务失败: {task_id}, 错误: {error_msg}")

            # 标记为失败
            with self._lock:
                self.tasks[task_id]['status'] = 'failed'
                self.tasks[task_id]['error'] = error_msg
                self.tasks[task_id]['completed_at'] = datetime.now().isoformat()

            # 更新数据库状态
            self._update_report_status(
                task_info['report_id'],
                'failed',
                error_message=error_msg
            )

    def _execute_scraping_task(self, task_info: Dict):
        """
        执行完整的爬取任务流程

        进度分配:
        - 阶段 1: 搜索达人候选列表 (scraping_progress: 0-20%)
        - 阶段 2: 获取达人详细信息 (scraping_progress: 20-100%)
        - 阶段 3: 生成分析报告 (report_progress: 0-100%)
        """
        import os
        import json
        import requests
        from agent_tools import call_api
        import time

        report_id = task_info['report_id']
        stage_start_time = time.time()

        # ==================== 阶段 1: 搜索达人候选列表 (scraping 0-20%) ====================
        print(f"📥 步骤 1/3: 搜索达人候选列表...")
        self._update_scraping_progress(report_id, 5, eta=None)

        # 直接调用 API，绕过工具层的确认检查
        result = call_api(
            "/scrape",
            method="POST",
            data={
                "urls": task_info['urls'],
                "max_pages": task_info['max_pages'],
                "product_name": task_info['product_name']
            },
            timeout=len(task_info['urls']) * task_info['max_pages'] * 30
        )

        # 检查 API 响应
        if not result.get("success"):
            raise Exception("API 返回失败状态")

        candidate_count = result.get("total_rows", 0)
        json_file_path = result.get("filepath", "")

        if candidate_count == 0:
            raise Exception("未能获取达人候选列表（数量为0）")

        if not json_file_path:
            raise Exception("未找到候选列表文件路径")

        print(f"✅ 步骤 1/3 完成: 找到 {candidate_count} 个达人候选")
        self._update_scraping_progress(report_id, 20, eta=None)

        # ==================== 阶段 2: 获取达人详细信息 (scraping 20-100%) ====================
        print(f"📥 步骤 2/3: 获取达人详细信息...")
        stage_start_time = time.time()  # 重置阶段开始时间

        # 直接调用流式 API，捕获进度事件
        from agent_tools import API_BASE_URL

        url = f"{API_BASE_URL}/process_influencer_list_stream"
        params = {
            "json_file_path": json_file_path,
            "cache_days": 3
        }

        processed_count = 0
        stats = None

        try:
            with requests.get(url, params=params, stream=True, timeout=3600) as response:
                response.raise_for_status()

                for line in response.iter_lines(decode_unicode=True):
                    if not line or not line.startswith('data: '):
                        continue

                    event_data = line[6:]
                    event = json.loads(event_data)

                    if event["type"] == "init":
                        total = event["total"]
                        print(f"⏳ 共需处理 {total} 个达人")

                    elif event["type"] == "progress":
                        current = event["current"]
                        total = event["total"]

                        # 映射到 scraping 20-100% 的进度范围
                        # 阶段 2 占 scraping 的 80%，所以：20% + (current/total * 80%)
                        scraping_progress = int(20 + (current / total * 80))

                        # 计算预计剩余时间
                        elapsed = time.time() - stage_start_time
                        if current > 0:
                            avg_time_per_item = elapsed / current
                            remaining_items = total - current
                            eta_seconds = int(avg_time_per_item * remaining_items)
                        else:
                            eta_seconds = None

                        self._update_scraping_progress(report_id, scraping_progress, eta=eta_seconds)

                        # 显示进度条（保留原有的终端输出）
                        percent = int(current / total * 100)
                        bar_len = 30
                        filled = int(bar_len * percent / 100)
                        bar = '█' * filled + '░' * (bar_len - filled)

                        eta_text = f" (预计剩余 {eta_seconds}秒)" if eta_seconds else ""
                        print(f"处理进度: {bar} {percent}% ({current}/{total}){eta_text}")

                    elif event["type"] == "complete":
                        stats = event["stats"]
                        processed_count = stats['total']
                        print(f"✅ 步骤 2/3 完成: 获取了 {processed_count} 个达人的详细信息")
                        self._update_scraping_progress(report_id, 100, eta=0)

                    elif event["type"] == "error":
                        raise Exception(f"处理失败: {event['message']}")

        except requests.exceptions.Timeout:
            raise Exception("处理超时，请稍后重试")
        except requests.exceptions.ConnectionError:
            raise Exception("无法连接到服务，请确认 API 服务已启动")

        # ==================== 阶段 3: 生成分析报告 (report_progress 0-100%) ====================
        print(f"📥 步骤 3/3: 生成分析报告...")
        stage_start_time = time.time()  # 重置阶段开始时间
        self._update_report_agent_progress(report_id, 0, eta=None)

        # 准备报告参数
        report_params = task_info['report_params'].copy()
        report_params['json_filename'] = os.path.basename(json_file_path)

        # 调用 Report Agent（内部会更新 report_progress 0-100%）
        report_html_path = self._generate_report(
            report_id=report_id,
            report_params=report_params,
            stage_start_time=stage_start_time  # 传入开始时间用于ETA计算
        )

        print(f"✅ 步骤 3/3 完成: 报告已生成")
        print(f"📄 报告路径: {report_html_path}")

        # 更新任务信息
        with self._lock:
            self.tasks[task_info['task_id']]['candidate_count'] = candidate_count
            self.tasks[task_info['task_id']]['processed_count'] = processed_count
            self.tasks[task_info['task_id']]['json_file_path'] = json_file_path
            self.tasks[task_info['task_id']]['report_html_path'] = report_html_path
            self.tasks[task_info['task_id']]['result'] = f"成功生成报告: {processed_count} 个达人"

        # 更新数据库报告的文件路径
        if report_html_path:
            self._update_report_file_path(task_info['report_id'], report_html_path)

    def _update_report_status(self, report_id: str, status: str, error_message: Optional[str] = None):
        """更新数据库中报告的状态"""
        try:
            with get_db_context() as db:
                values_dict = {'status': status}
                if error_message:
                    values_dict['error_message'] = error_message

                stmt = update(Report).where(Report.report_id == report_id).values(**values_dict)
                db.execute(stmt)
                db.commit()

        except Exception as e:
            print(f"❌ 更新报告状态失败: {e}")

    def _update_report_file_path(self, report_id: str, file_path: str):
        """更新报告的文件路径"""
        try:
            with get_db_context() as db:
                stmt = update(Report).where(Report.report_id == report_id).values(
                    report_path=file_path,  # ⭐ 修复：使用正确的字段名
                    completed_at=datetime.utcnow()
                )
                db.execute(stmt)
                db.commit()

        except Exception as e:
            print(f"❌ 更新报告文件路径失败: {e}")

    def _update_report_progress(self, report_id: str, progress: int):
        """更新报告生成进度（兼容旧接口）"""
        try:
            with get_db_context() as db:
                # 先查询报告是否存在
                report = db.query(Report).filter(Report.report_id == report_id).first()
                if not report:
                    print(f"⚠️ 报告不存在: {report_id}")
                    return

                # 更新进度
                report.progress = progress
                db.commit()

                # 验证更新
                db.refresh(report)
                print(f"📊 进度已更新到数据库: {progress}% (验证: {report.progress}%)")

        except Exception as e:
            print(f"⚠️ 更新进度失败: {e}")
            import traceback
            traceback.print_exc()

    def _update_scraping_progress(self, report_id: str, progress: int, eta: Optional[int] = None):
        """更新爬取阶段的进度和预计剩余时间"""
        try:
            with get_db_context() as db:
                report = db.query(Report).filter(Report.report_id == report_id).first()
                if not report:
                    print(f"⚠️ 报告不存在: {report_id}")
                    return

                # 更新爬取进度和ETA
                report.scraping_progress = progress
                if eta is not None:
                    report.scraping_eta = eta

                # 同步更新总进度（scraping 占 60%）
                report.progress = int(progress * 0.6)

                db.commit()
                db.refresh(report)

                eta_text = f", ETA: {eta}秒" if eta is not None else ""
                print(f"📊 爬取进度: {progress}%{eta_text}")

        except Exception as e:
            print(f"⚠️ 更新爬取进度失败: {e}")
            import traceback
            traceback.print_exc()

    def _update_report_agent_progress(self, report_id: str, progress: int, eta: Optional[int] = None):
        """更新报告生成阶段的进度和预计剩余时间"""
        try:
            with get_db_context() as db:
                report = db.query(Report).filter(Report.report_id == report_id).first()
                if not report:
                    print(f"⚠️ 报告不存在: {report_id}")
                    return

                # 更新报告生成进度和ETA
                report.report_progress = progress
                if eta is not None:
                    report.report_eta = eta

                # 同步更新总进度（scraping 60% + report 40%）
                report.progress = 60 + int(progress * 0.4)

                db.commit()
                db.refresh(report)

                eta_text = f", ETA: {eta}秒" if eta is not None else ""
                print(f"📊 报告生成进度: {progress}%{eta_text}")

        except Exception as e:
            print(f"⚠️ 更新报告生成进度失败: {e}")
            import traceback
            traceback.print_exc()

    def _generate_report(self, report_id: str, report_params: Dict, stage_start_time: float) -> str:
        """
        调用 Report Agent 生成报告

        Args:
            report_id: 报告 ID
            report_params: 报告参数字典，包含:
                - json_filename: JSON 文件名
                - user_query: 用户查询
                - target_count: 每层推荐数量
                - product_info: 产品信息
            stage_start_time: 阶段开始时间（用于计算ETA）

        Returns:
            report_html_path: 生成的 HTML 报告路径

        进度说明:
            Report Agent 内部使用 0-100% 的进度，直接映射到 report_progress
        """
        try:
            import time
            from report_agent import TikTokInfluencerReportAgent

            # 创建 Report Agent 实例
            report_agent = TikTokInfluencerReportAgent()

            # 创建进度回调函数
            def progress_callback(internal_progress: int):
                """
                Report Agent 的内部进度直接映射到 report_progress (0-100%)
                同时计算并更新 ETA
                """
                # 计算预计剩余时间
                elapsed = time.time() - stage_start_time
                if internal_progress > 0:
                    # 正确计算: 平均每个百分点的时间 * 剩余百分点
                    avg_time_per_percent = elapsed / internal_progress
                    remaining_percent = 100 - internal_progress
                    eta_seconds = int(avg_time_per_percent * remaining_percent)
                else:
                    eta_seconds = None

                self._update_report_agent_progress(report_id, internal_progress, eta=eta_seconds)

            # 调用生成方法，传入进度回调
            report_html_path = report_agent.generate_report(
                json_filename=report_params['json_filename'],
                user_query=report_params['user_query'],
                target_count=report_params['target_count'],
                product_info=report_params['product_info'],
                progress_callback=progress_callback  # ⭐ 传入进度回调（含ETA计算）
            )

            return report_html_path

        except Exception as e:
            print(f"❌ Report Agent 生成报告失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def submit_task(
        self,
        user_id: str,
        product_name: str,
        urls: List[str],
        max_pages: int,
        report_params: Dict,       # ⭐ 新增：报告参数字典
        session_id: Optional[str] = None,  # ⭐ 新增：会话 ID
        report_id: Optional[str] = None
    ) -> str:
        """
        提交新任务到队列

        Args:
            user_id: 用户 ID
            product_name: 商品名称
            urls: 搜索 URL 列表
            max_pages: 最大爬取页数
            report_params: 报告生成参数（user_query, target_count, product_info）
            session_id: 会话 ID（用于创建报告）
            report_id: 报告 ID（如果已创建）

        Returns:
            任务 ID
        """
        task_id = str(uuid.uuid4())

        # 如果没有提供 report_id，创建新报告
        if not report_id:
            report_id = self._create_report(user_id, product_name, session_id)

        task_info = {
            'task_id': task_id,
            'report_id': report_id,
            'user_id': user_id,
            'product_name': product_name,
            'urls': urls,
            'max_pages': max_pages,
            'report_params': report_params,    # ⭐ 存储报告参数
            'status': 'queued',
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'error': None,
            'candidate_count': None,
            'processed_count': None,
            'json_file_path': None,
            'report_html_path': None,
            'result': None
        }

        with self._lock:
            self.tasks[task_id] = task_info

        print(f"📥 新任务已加入队列: {task_id} (报告: {report_id})")

        return task_id

    def _create_report(self, user_id: str, product_name: str, session_id: str = None) -> str:
        """在数据库中创建新报告记录（并扣除用户配额）"""
        try:
            with get_db_context() as db:
                # 如果没有提供 session_id，使用默认值或从数据库获取用户最近的 session
                if not session_id:
                    from database.models import ChatSession
                    recent_session = db.query(ChatSession).filter(
                        ChatSession.user_id == user_id
                    ).order_by(ChatSession.updated_at.desc()).first()
                    session_id = recent_session.session_id if recent_session else None

                if not session_id:
                    raise ValueError("无法找到用户会话")

                # ⭐ 获取会话信息，使用会话标题作为报告标题
                from database.models import ChatSession
                session = db.query(ChatSession).filter(
                    ChatSession.session_id == session_id
                ).first()

                if not session:
                    raise ValueError(f"找不到会话: {session_id}")

                # 使用会话标题作为报告标题（如果是"新对话"则使用产品名称）
                if session.title and session.title != "新对话":
                    report_title = session.title
                else:
                    report_title = f"{product_name} - 达人推荐报告"

                # ⭐ 新增：检查并扣除用户配额
                from database.models import UserUsage
                usage = db.query(UserUsage).filter(
                    UserUsage.user_id == user_id
                ).first()

                if not usage:
                    raise ValueError(f"找不到用户 {user_id} 的配额信息")

                if usage.remaining_quota <= 0:
                    raise ValueError(f"用户配额不足，剩余: {usage.remaining_quota}")

                # 创建报告，使用会话标题
                report = Report(
                    user_id=user_id,
                    session_id=session_id,
                    title=report_title,
                    report_path="",  # 初始为空，后续更新
                    status='queued',
                    meta_data={'product_name': product_name, 'type': 'influencer_search'}
                )
                db.add(report)

                # ⭐ 扣除配额（失败时会自动回滚）
                usage.used_count += 1
                db.commit()
                db.refresh(report)

                print(f"✅ 用户 {user_id} 配额已扣除: {usage.used_count}/{usage.total_quota} (剩余: {usage.remaining_quota})")

                return report.report_id

        except Exception as e:
            print(f"❌ 创建报告失败: {e}")
            import traceback
            traceback.print_exc()
            raise

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        with self._lock:
            return self.tasks.get(task_id)

    def get_report_id(self, task_id: str) -> Optional[str]:
        """获取任务关联的报告 ID"""
        with self._lock:
            task_info = self.tasks.get(task_id)
            return task_info['report_id'] if task_info else None


# 全局单例
task_queue = BackgroundTaskQueue()


if __name__ == "__main__":
    # 测试代码
    print("后台任务队列测试")

    # 提交测试任务
    task_id = task_queue.submit_task(
        user_id="test-user-123",
        product_name="测试商品",
        urls=["https://example.com/search?page=1"],
        max_pages=5
    )

    print(f"任务 ID: {task_id}")

    # 等待一会儿
    import time
    time.sleep(2)

    # 检查状态
    status = task_queue.get_task_status(task_id)
    print(f"任务状态: {status}")
