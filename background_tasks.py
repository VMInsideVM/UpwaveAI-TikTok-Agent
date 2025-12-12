"""
后台任务队列系统
用于异步执行达人搜索和报告生成任务
"""

import asyncio
import threading
import uuid
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
        """执行完整的爬取任务流程"""
        from agent_tools import ScrapeInfluencersTool, ProcessInfluencerListTool

        print(f"📥 步骤 1/3: 搜索达人候选列表...")

        # 步骤 1: 爬取达人候选列表
        scrape_tool = ScrapeInfluencersTool()  # ⭐ 修复：正确的工具名
        result = scrape_tool._run(
            urls=task_info['urls'],
            max_pages=task_info['max_pages'],
            product_name=task_info['product_name']
        )

        # 解析候选列表结果
        import re
        match = re.search(r'成功获取 (\d+) 个达人候选', result)
        if not match:
            raise Exception("未能获取达人候选列表")

        candidate_count = int(match.group(1))

        # 查找 JSON 文件路径
        match = re.search(r'数据已保存到: (.+\.json)', result)
        if not match:
            raise Exception("未找到候选列表文件路径")

        json_file_path = match.group(1)

        print(f"✅ 步骤 1/3 完成: 找到 {candidate_count} 个达人候选")
        print(f"📥 步骤 2/3: 获取达人详细信息...")

        # 步骤 2: 获取达人详细信息
        detail_tool = ProcessInfluencerListTool()
        detail_result = detail_tool._run(
            json_file_path=json_file_path,
            cache_days=3  # 缓存 3 天
        )

        # 解析详细信息结果
        # 尝试多种格式匹配
        match = re.search(r'共处理 (\d+) 个达人', detail_result)
        if not match:
            match = re.search(r'成功获取 (\d+) 个', detail_result)
        if not match:
            match = re.search(r'使用缓存 (\d+) 个', detail_result)

        if not match:
            # 如果只返回 "✅ 处理完成"，可能是全缓存且数量为 0
            if "处理完成" in detail_result or "完成！" in detail_result:
                print(f"⚠️ 步骤 2/3: 详细信息处理完成，但无法获取数量统计")
                processed_count = candidate_count  # 使用候选列表数量作为估计
            else:
                raise Exception(f"获取详细信息失败，无法解析返回结果: {detail_result[:200]}")
        else:
            processed_count = int(match.group(1))

        print(f"✅ 步骤 2/3 完成: 获取了 {processed_count} 个达人的详细信息")
        print(f"📥 步骤 3/3: 生成分析报告...")

        # 步骤 3: 调用 Report Agent 生成报告
        import os

        # 直接使用收集好的参数
        report_params = task_info['report_params'].copy()

        # 添加 JSON 文件名
        report_params['json_filename'] = os.path.basename(json_file_path)

        # 调用 Report Agent
        report_html_path = self._generate_report(
            report_id=task_info['report_id'],
            report_params=report_params
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

        # 更新数据库报告的文件路径（使用 HTML 报告路径）
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

    def _generate_report(self, report_id: str, report_params: Dict) -> str:
        """
        调用 Report Agent 生成报告

        Args:
            report_id: 报告 ID
            report_params: 报告参数字典，包含:
                - json_filename: JSON 文件名
                - user_query: 用户查询
                - target_count: 每层推荐数量
                - product_info: 产品信息

        Returns:
            report_html_path: 生成的 HTML 报告路径
        """
        try:
            from report_agent import TikTokInfluencerReportAgent

            # 创建 Report Agent 实例
            report_agent = TikTokInfluencerReportAgent()

            # 调用生成方法
            report_html_path = report_agent.generate_report(
                json_filename=report_params['json_filename'],
                user_query=report_params['user_query'],
                target_count=report_params['target_count'],
                product_info=report_params['product_info']
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
        """在数据库中创建新报告记录"""
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

                report = Report(
                    user_id=user_id,
                    session_id=session_id,
                    title=f"{product_name} - 达人推荐报告",
                    report_path="",  # 初始为空，后续更新
                    status='queued',
                    meta_data={'product_name': product_name, 'type': 'influencer_search'}
                )
                db.add(report)
                db.commit()
                db.refresh(report)
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
