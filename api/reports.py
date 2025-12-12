"""
Reports API Endpoints
报告管理 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import json

from database.connection import get_db
from database.models import Report, User, UserUsage, ChatSession
from auth.dependencies import get_current_user, get_current_admin_user, get_user_from_token_param
from background.report_queue import report_queue

router = APIRouter(prefix="/api/reports", tags=["报告"])


# ==================== Pydantic Models ====================

class GenerateReportRequest(BaseModel):
    """生成报告请求"""
    session_id: str


class ReportListItem(BaseModel):
    """报告列表项"""
    report_id: str
    title: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    estimated_time: Optional[int]
    progress: Optional[int]
    error_message: Optional[str]


class ReportStatusResponse(BaseModel):
    """报告状态响应"""
    report_id: str
    status: str
    progress: int
    estimated_time_remaining: Optional[int]
    error: Optional[str]
    queue_position: Optional[int]


# ==================== API Endpoints ====================

@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_report(
    request: GenerateReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    触发报告生成（后台任务）

    Steps:
    1. 验证用户拥有该会话
    2. 检查使用配额
    3. 从会话元数据提取 JSON 文件路径
    4. 创建 Report 记录
    5. 加入后台队列
    """
    session_id = request.session_id

    # 1. 验证会话所有权
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在"
        )

    if session.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此会话"
        )

    # 2. 检查配额
    usage = db.query(UserUsage).filter(UserUsage.user_id == current_user.user_id).first()

    if not usage:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户配额记录不存在"
        )

    if usage.remaining_quota <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"使用次数已用完（已使用 {usage.used_count}/{usage.total_quota}），请联系管理员增加配额"
        )

    # 3. 从会话元数据提取 JSON 文件路径
    meta_data = session.meta_data or {}
    json_file_path = meta_data.get("json_file_path")
    product_name = meta_data.get("product_name", "未命名产品")

    if not json_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会话中没有数据文件路径，请先完成数据收集"
        )

    # 检查文件是否存在
    if not os.path.exists(json_file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据文件不存在: {json_file_path}"
        )

    # 4. 创建 Report 记录
    new_report = Report(
        user_id=current_user.user_id,
        session_id=session_id,
        title=f"{product_name} - 达人推荐报告",
        report_path="",  # 将在生成完成后更新
        status="queued"
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    # 5. 立即扣除配额（失败时会自动退还）
    usage.used_count += 1
    db.commit()
    print(f"✅ 用户 {current_user.user_id} 配额已预扣: {usage.used_count}/{usage.total_quota}")

    # 6. 加入后台队列
    await report_queue.enqueue_report(
        report_id=new_report.report_id,
        user_id=current_user.user_id,
        session_id=session_id,
        json_file_path=json_file_path,
        product_name=product_name
    )

    return {
        "report_id": new_report.report_id,
        "message": "报告生成任务已加入队列",
        "status": "queued",
        "remaining_quota": usage.remaining_quota  # 已扣除后的剩余
    }


@router.get("", response_model=List[ReportListItem])
async def list_user_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    offset: int = 0
):
    """
    列出当前用户的所有报告
    """
    reports = db.query(Report).filter(
        Report.user_id == current_user.user_id
    ).order_by(
        Report.created_at.desc()
    ).offset(offset).limit(limit).all()

    result = []
    for report in reports:
        # 获取实时进度
        task_status = report_queue.get_task_status(report.report_id)
        progress = task_status.get("progress", 0) if task_status else 0

        result.append(ReportListItem(
            report_id=report.report_id,
            title=report.title,
            status=report.status,
            created_at=report.created_at,
            completed_at=report.completed_at,
            estimated_time=report.estimated_time,
            progress=progress,
            error_message=report.error_message
        ))

    return result


@router.get("/{report_id}/view")
async def view_report(
    report_id: str,
    token: Optional[str] = None,
    current_user: User = Depends(get_user_from_token_param),
    db: Session = Depends(get_db)
):
    """
    查看报告HTML文件（访问控制）

    支持通过 URL 参数传递 token（用于在新窗口打开）
    也支持通过 Authorization 头传递 token

    只有报告所有者或管理员可以访问
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    # 访问控制
    if report.user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此报告"
        )

    # 检查报告状态
    if report.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"报告尚未完成，当前状态: {report.status}"
        )

    # 检查文件是否存在
    if not report.report_path or not os.path.exists(report.report_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告文件不存在"
        )

    # 将绝对路径转换为静态文件URL
    # 例如: output/reports/20251212_204820/report.html -> /reports/20251212_204820/report.html
    try:
        # 提取相对于 output/reports/ 的路径
        reports_base = "output/reports"
        if reports_base in report.report_path:
            relative_path = report.report_path.split(reports_base)[1].replace("\\", "/")
            static_url = f"/reports{relative_path}"

            print(f"📄 重定向到报告: {static_url}")

            # 返回重定向（浏览器会直接显示HTML，不会下载）
            return RedirectResponse(url=static_url, status_code=302)
        else:
            # 如果路径不符合预期，仍使用FileResponse
            print(f"⚠️ 报告路径不符合预期格式，使用FileResponse: {report.report_path}")
            return FileResponse(
                report.report_path,
                media_type="text/html"
            )
    except Exception as e:
        print(f"❌ 处理报告路径失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"无法访问报告文件: {str(e)}"
        )


@router.get("/{report_id}")
async def get_report_detail(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取报告详情（JSON格式）

    只有报告所有者或管理员可以访问
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    # 访问控制
    if report.user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此报告"
        )

    # 检查文件是否存在
    file_exists = False
    if report.report_path and report.status == "completed":
        file_exists = os.path.exists(report.report_path)

    print(f"📄 获取报告详情: {report_id}, status={report.status}, file_exists={file_exists}")

    # 返回JSON格式的报告详情
    return {
        "report_id": report.report_id,
        "title": report.title,
        "status": report.status,
        "file_path": report.report_path,
        "file_exists": file_exists,
        "error_message": report.error_message,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
        "message": "报告详情获取成功"
    }


@router.get("/{report_id}/status", response_model=ReportStatusResponse)
async def get_report_status(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    轮询报告生成状态
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    # 访问控制
    if report.user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此报告"
        )

    # 从队列获取实时状态
    task_status = report_queue.get_task_status(report_id)

    if task_status:
        progress = task_status.get("progress", 0)
        queue_position = task_status.get("queue_position")
    else:
        progress = 100 if report.status == "completed" else 0
        queue_position = None

    # 计算预计剩余时间
    estimated_time_remaining = None
    if report.status == "generating" and report.estimated_time:
        elapsed = (datetime.utcnow() - report.created_at).total_seconds()
        estimated_time_remaining = max(0, report.estimated_time - int(elapsed))

    return ReportStatusResponse(
        report_id=report.report_id,
        status=report.status,
        progress=progress,
        estimated_time_remaining=estimated_time_remaining,
        error=report.error_message,
        queue_position=queue_position
    )


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除报告（仅所有者或管理员）
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    # 访问控制
    if report.user_id != current_user.user_id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此报告"
        )

    # 删除文件
    if report.report_path and os.path.exists(report.report_path):
        try:
            os.remove(report.report_path)
        except Exception as e:
            print(f"⚠️ 删除报告文件失败: {e}")

    # 删除数据库记录
    db.delete(report)
    db.commit()

    return {"message": "报告已删除"}
