"""
测试进度更新功能
验证数据库进度是否正确更新
"""

import time
from database.connection import get_db_context, init_db
from database.models import Report, User, UserUsage

def test_progress_update():
    """测试进度更新到数据库"""

    # 初始化数据库
    init_db()

    # 创建测试用户和报告
    with get_db_context() as db:
        # 查找或创建测试用户
        test_user = db.query(User).filter(User.username == "test_user").first()
        if not test_user:
            from auth.security import hash_password
            test_user = User(
                username="test_user",
                email="test@example.com",
                hashed_password=hash_password("test123"),
                is_active=True
            )
            db.add(test_user)
            db.flush()

            # 创建配额记录
            usage = UserUsage(
                user_id=test_user.user_id,
                total_quota=100,
                used_count=0
            )
            db.add(usage)
            db.commit()

        # 创建测试报告
        test_report = Report(
            user_id=test_user.user_id,
            session_id="test_session_123",
            title="测试报告 - 进度更新验证",
            report_path="",
            status="generating",
            progress=0
        )
        db.add(test_report)
        db.commit()
        db.refresh(test_report)

        report_id = test_report.report_id
        print(f"✅ 创建测试报告: {report_id}")
        print(f"   初始进度: {test_report.progress}%\n")

    # 测试进度更新
    print("📊 开始测试进度更新...\n")

    from background_tasks import BackgroundTaskQueue
    task_queue = BackgroundTaskQueue()

    # 模拟不同阶段的进度
    test_stages = [
        (5, "阶段 1 开始: 搜索候选列表"),
        (10, "阶段 1 完成"),
        (15, "阶段 2: 获取详细信息 (10%)"),
        (30, "阶段 2: 获取详细信息 (40%)"),
        (45, "阶段 2: 获取详细信息 (70%)"),
        (60, "阶段 2 完成"),
        (70, "阶段 3: 生成报告 (25%)"),
        (85, "阶段 3: 生成报告 (65%)"),
        (95, "阶段 3: 生成报告 (90%)"),
        (100, "阶段 3 完成"),
    ]

    for progress, description in test_stages:
        print(f"🔄 {description}")
        task_queue._update_report_progress(report_id, progress)

        # 验证数据库
        with get_db_context() as db:
            report = db.query(Report).filter(Report.report_id == report_id).first()
            if report:
                actual_progress = report.progress
                status = "✅" if actual_progress == progress else "❌"
                print(f"   {status} 数据库进度: {actual_progress}% (预期: {progress}%)\n")
            else:
                print(f"   ❌ 无法找到报告\n")

        time.sleep(0.5)  # 模拟处理延迟

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)

    # 显示最终结果
    with get_db_context() as db:
        report = db.query(Report).filter(Report.report_id == report_id).first()
        if report:
            print(f"\n最终报告状态:")
            print(f"  报告 ID: {report.report_id}")
            print(f"  状态: {report.status}")
            print(f"  进度: {report.progress}%")
            print(f"  创建时间: {report.created_at}")

            # 清理测试数据（可选）
            cleanup = input("\n是否删除测试数据? (y/n): ").strip().lower()
            if cleanup == 'y':
                db.delete(report)
                db.commit()
                print("✅ 测试数据已删除")
        else:
            print("❌ 无法找到最终报告")


if __name__ == "__main__":
    test_progress_update()
