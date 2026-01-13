"""
Reports API Endpoints
报告管理 API 端点
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime, timedelta
import os
import json
import re
from passlib.context import CryptContext

from database.connection import get_db
from database.models import Report, User, UserUsage, ChatSession, CreditHistory
from auth.dependencies import get_current_user, get_current_admin_user, get_user_from_token_param, get_user_or_shared_access
from auth.security import create_access_token
from background.report_queue import report_queue

router = APIRouter(prefix="/api/reports", tags=["报告"])

# 从环境变量读取部署配置
BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")  # 例如: "https://upwaveai.com"
BASE_PATH = os.getenv("BASE_PATH", "")  # 例如: "/agent" 或 ""

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_share_url(report_id):
    """生成完整的分享 URL"""
    return f"{BASE_URL}{BASE_PATH}/shared/{report_id}"


# ==================== Pydantic Models ====================

class GenerateReportRequest(BaseModel):
    """生成报告请求"""
    session_id: str
    target_influencer_count: Optional[int] = None  # ⭐ 新增：允许用户指定达人数量（覆盖会话中的值）


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
    # 新增：两个独立的进度条数据
    scraping_progress: Optional[int]
    scraping_eta: Optional[int]
    report_progress: Optional[int]
    report_eta: Optional[int]


class ReportStatusResponse(BaseModel):
    """报告状态响应"""
    report_id: str
    status: str
    progress: int
    estimated_time_remaining: Optional[int]
    error: Optional[str]
    queue_position: Optional[int]
    # 新增：两个独立的进度条数据
    scraping_progress: int
    scraping_eta: Optional[int]
    report_progress: int
    report_eta: Optional[int]


class ReportShareSettingInput(BaseModel):
    """报告分享设置请求"""
    share_mode: str = Field(..., description="分享模式: private/public/password")
    password: Optional[str] = Field(None, description="密码（仅password模式需要）")
    expires_in_days: Optional[int] = Field(None, description="过期天数: 7/30/None(永久)")

    @validator('share_mode')
    def validate_share_mode(cls, v):
        if v not in ["private", "public", "password"]:
            raise ValueError('share_mode必须是: private, public, 或 password')
        return v

    @validator('password')
    def validate_password(cls, v, values):
        if values.get('share_mode') == 'password':
            if not v or len(v) < 6:
                raise ValueError('密码长度至少为6位')
        return v


class SharedReportAccessInput(BaseModel):
    """分享报告访问请求"""
    password: Optional[str] = Field(None, description="密码（password模式需要）")


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

    # 2. 检查积分（需要先读取JSON文件获取达人数量）

    # 3. 从会话元数据提取 JSON 文件路径和用户请求的达人数量
    meta_data = session.meta_data or {}
    json_file_path = meta_data.get("json_file_path")
    product_name = meta_data.get("product_name", "未命名产品")

    # ⭐ 优先使用用户在请求中指定的数量，否则使用会话中保存的数量
    if request.target_influencer_count is not None:
        target_influencer_count = request.target_influencer_count
        print(f"💡 用户在请求中指定达人数量: {target_influencer_count} 个")
    else:
        target_influencer_count = meta_data.get("target_influencer_count")
        if target_influencer_count:
            print(f"💡 使用会话中保存的达人数量: {target_influencer_count} 个")

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

    # 4. 读取JSON文件获取实际可用的达人数量
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        influencer_ids = data.get("data_row_keys", [])
        available_count = len(influencer_ids)

        if available_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="数据文件中没有达人数据"
            )

        print(f"📊 JSON文件中可用的达人数量: {available_count} 个")
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数据文件格式错误"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"读取数据文件失败: {str(e)}"
        )

    # 5. 根据用户请求的达人数量计算所需积分
    CREDITS_PER_INFLUENCER = 100

    # ⭐ 优先使用用户请求的数量，如果没有则使用可用的全部数量
    if target_influencer_count is not None and target_influencer_count > 0:
        # 验证用户请求的数量不超过可用数量
        if target_influencer_count > available_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"请求的达人数量（{target_influencer_count}）超过可用数量（{available_count}），请调整数量"
            )

        influencer_count = target_influencer_count
        print(f"💰 使用用户请求的达人数量计算积分: {influencer_count} 个")
    else:
        # 回退方案：使用JSON文件中的全部数量
        influencer_count = available_count
        print(f"💰 使用JSON文件中的全部达人数量计算积分: {influencer_count} 个")

    # 计算所需积分
    required_credits = influencer_count * CREDITS_PER_INFLUENCER

    # 5. 检查用户积分是否足够
    usage = db.query(UserUsage).filter(UserUsage.user_id == current_user.user_id).first()

    if not usage:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="用户积分记录不存在"
        )

    if usage.remaining_credits < required_credits:
        # 计算用户当前积分能生成多少个达人的报告
        affordable_count = usage.remaining_credits // CREDITS_PER_INFLUENCER

        error_detail = f"积分不足：需要 {required_credits} 积分（{influencer_count} 个达人 × 100），当前剩余 {usage.remaining_credits} 积分"

        # 如果用户有一定积分，提示可以减少达人数量
        if affordable_count > 0 and affordable_count < influencer_count:
            error_detail += f"\n\n💡 建议：您当前积分可以生成 {affordable_count} 个达人的报告。您可以：\n"
            error_detail += f"   1. 调整达人数量为 {affordable_count} 个（需要 {affordable_count * CREDITS_PER_INFLUENCER} 积分）\n"
            error_detail += f"   2. 充值积分后继续生成 {influencer_count} 个达人的报告"
        else:
            error_detail += "\n\n💡 请充值积分后继续"

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail
        )

    # 6. 创建 Report 记录，使用会话标题作为报告标题
    # 如果会话标题是"新对话"，则使用产品名称
    if session.title and session.title != "新对话":
        report_title = session.title
    else:
        report_title = f"{product_name} - 达人推荐报告"

    new_report = Report(
        user_id=current_user.user_id,
        session_id=session_id,
        title=report_title,
        report_path="",  # 将在生成完成后更新
        status="queued",
        meta_data={
            "influencer_count": influencer_count,
            "credits_deducted": required_credits
        }
    )

    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    # 7. 立即扣除积分（失败时会自动退还）
    before_credits = usage.total_credits - usage.used_credits + required_credits  # 扣除前的剩余积分
    usage.used_credits += required_credits
    after_credits = usage.remaining_credits  # 扣除后的剩余积分

    # ⭐ 创建积分变动历史记录
    credit_history = CreditHistory(
        user_id=current_user.user_id,
        change_type='deduct',
        amount=-required_credits,  # 负数表示扣除
        before_credits=before_credits,
        after_credits=after_credits,
        reason=f"生成报告消耗积分（{influencer_count} 个达人）",
        related_report_id=new_report.report_id,
        meta_data={
            "influencer_count": influencer_count,
            "session_id": session_id
        }
    )
    db.add(credit_history)

    db.commit()
    print(f"✅ 用户 {current_user.user_id} 积分已预扣: {required_credits} 积分 ({influencer_count} 个达人), 剩余: {usage.remaining_credits}/{usage.total_credits}")

    # 8. 加入后台队列
    await report_queue.enqueue_report(
        report_id=new_report.report_id,
        user_id=current_user.user_id,
        session_id=session_id,
        json_file_path=json_file_path,
        product_name=product_name,
        credits_deducted=required_credits  # 传递扣除的积分数量，用于失败时退还
    )

    return {
        "report_id": new_report.report_id,
        "message": f"报告生成任务已加入队列（{influencer_count} 个达人，消耗 {required_credits} 积分）",
        "status": "queued",
        "influencer_count": influencer_count,
        "credits_deducted": required_credits,
        "remaining_credits": usage.remaining_credits  # 已扣除后的剩余
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
        # 直接从数据库读取进度（而不是从任务队列）
        progress = report.progress if report.progress is not None else 0
        scraping_progress = report.scraping_progress if report.scraping_progress is not None else 0
        report_progress = report.report_progress if report.report_progress is not None else 0

        # 如果是已完成状态，确保进度是100%
        if report.status == 'completed':
            progress = 100
            scraping_progress = 100
            report_progress = 100

        result.append(ReportListItem(
            report_id=report.report_id,
            title=report.title,
            status=report.status,
            created_at=report.created_at,
            completed_at=report.completed_at,
            estimated_time=report.estimated_time,
            progress=progress,
            error_message=report.error_message,
            scraping_progress=scraping_progress,
            scraping_eta=report.scraping_eta,
            report_progress=report_progress,
            report_eta=report.report_eta
        ))

    return result


@router.get("/{report_id}/view")
async def view_report(
    report_id: str,
    token: Optional[str] = None,
    current_user = Depends(get_user_or_shared_access),
    db: Session = Depends(get_db)
):
    """
    查看报告HTML文件（访问控制）

    支持通过 URL 参数传递 token（用于在新窗口打开）
    也支持通过 Authorization 头传递 token

    支持以下访问方式：
    1. 报告所有者
    2. 管理员
    3. 分享访问（通过分享令牌）
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    # 访问控制（增强版）
    is_shared_access = hasattr(current_user, 'report_id')

    # 1. 管理员：无条件访问
    if hasattr(current_user, 'is_admin') and current_user.is_admin:
        pass  # 允许访问

    # 2. 报告所有者：无条件访问
    elif hasattr(current_user, 'user_id') and current_user.user_id and report.user_id == current_user.user_id:
        pass  # 允许访问

    # 3. 分享访问：检查令牌中的 report_id
    elif is_shared_access and current_user.report_id == report_id:
        pass  # 允许访问

    # 4. 其他情况：拒绝访问
    else:
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

    # 如果是分享访问，添加水印并修复资源路径
    if is_shared_access:
        try:
            with open(report.report_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # 修复图表等资源的相对路径，添加 BASE_PATH 前缀
            # 例如: charts/xxx.png -> /agent/reports/20251212_204820/charts/xxx.png
            reports_base = "output/reports"
            if reports_base in report.report_path:
                # 提取报告目录名 (例如: 20251212_204820)
                report_dir = report.report_path.split(reports_base)[1].split('/')[1].split('\\')[0]

                # 替换 src="charts/ 为 src="/agent/reports/{report_dir}/charts/
                html_content = re.sub(
                    r'src="charts/',
                    f'src="{BASE_PATH}/reports/{report_dir}/charts/',
                    html_content
                )

                # 替换 src='charts/ 为 src='/agent/reports/{report_dir}/charts/
                html_content = re.sub(
                    r"src='charts/",
                    f"src='{BASE_PATH}/reports/{report_dir}/charts/",
                    html_content
                )

            watermark = f"""
    <div class="report-watermark" style="position: fixed; bottom: 10px; right: 10px; opacity: 0.5; font-size: 12px; color: #999; z-index: 9999;">
        报告所有者: {report.user.username}
    </div>
    """

            # 在 </body> 前插入水印
            if '</body>' in html_content:
                html_content = html_content.replace('</body>', f'{watermark}</body>')
            else:
                html_content += watermark

            return HTMLResponse(content=html_content)

        except Exception as e:
            print(f"❌ 添加水印失败: {e}")
            # 降级：直接返回文件
            return FileResponse(report.report_path, media_type="text/html")

    # 将绝对路径转换为静态文件URL
    # 例如: output/reports/20251212_204820/report.html -> /agent/reports/20251212_204820/report.html
    try:
        # 提取相对于 output/reports/ 的路径
        reports_base = "output/reports"
        if reports_base in report.report_path:
            relative_path = report.report_path.split(reports_base)[1].replace("\\", "/")
            static_url = f"{BASE_PATH}/reports{relative_path}"

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

    # 直接从数据库读取进度
    progress = report.progress if report.progress is not None else 0
    scraping_progress = report.scraping_progress if report.scraping_progress is not None else 0
    report_progress = report.report_progress if report.report_progress is not None else 0

    # 如果是已完成状态，确保进度是100%
    if report.status == 'completed':
        progress = 100
        scraping_progress = 100
        report_progress = 100

    # 从队列获取队列位置信息
    task_status = report_queue.get_task_status(report_id)
    queue_position = task_status.get("queue_position") if task_status else None

    # 计算预计剩余时间（兼容旧接口）
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
        queue_position=queue_position,
        scraping_progress=scraping_progress,
        scraping_eta=report.scraping_eta,
        report_progress=report_progress,
        report_eta=report.report_eta
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


# ==================== 报告分享功能 API ====================

@router.post("/{report_id}/share/settings")
async def update_share_settings(
    report_id: str,
    settings: ReportShareSettingInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新报告分享设置

    - 仅报告所有者可以修改分享设置
    - 支持三种模式: private, public, password
    - password 模式需要提供密码
    - 支持设置过期时间
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    # 权限检查：仅所有者可以修改
    if report.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此报告的分享设置"
        )

    # password 模式必须提供密码
    if settings.share_mode == "password" and not settings.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码保护模式需要提供密码"
        )

    # 更新分享设置
    report.share_mode = settings.share_mode
    report.share_created_at = datetime.now()

    # 设置密码（加密存储）
    if settings.share_mode == "password":
        report.share_password = pwd_context.hash(settings.password)
    else:
        report.share_password = None

    # 设置过期时间
    if settings.expires_in_days:
        report.share_expires_at = datetime.now() + timedelta(days=settings.expires_in_days)
    else:
        report.share_expires_at = None

    db.commit()

    return {
        "success": True,
        "message": "分享设置已更新",
        "share_mode": report.share_mode,
        "share_url": generate_share_url(report_id),
        "expires_at": report.share_expires_at.isoformat() if report.share_expires_at else None
    }


@router.get("/{report_id}/share/settings")
async def get_share_settings(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取报告分享设置（仅所有者可查看）
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    if report.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权查看此报告的分享设置"
        )

    return {
        "success": True,
        "share_mode": report.share_mode,
        "has_password": bool(report.share_password),
        "expires_at": report.share_expires_at.isoformat() if report.share_expires_at else None,
        "share_url": generate_share_url(report_id),
        "is_expired": report.share_expires_at < datetime.now() if report.share_expires_at else False
    }


@router.post("/{report_id}/shared")
async def access_shared_report(
    report_id: str,
    access_input: SharedReportAccessInput,
    db: Session = Depends(get_db)
):
    """
    访问分享的报告

    - 无需登录
    - 根据分享模式验证访问权限
    - 返回报告访问令牌（短期有效）
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    # 检查报告状态
    if report.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="报告尚未完成"
        )

    # 检查分享模式
    if report.share_mode == "private":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此报告未分享"
        )

    # 检查过期时间
    if report.share_expires_at and report.share_expires_at < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="分享链接已过期"
        )

    # password 模式验证密码
    if report.share_mode == "password":
        if not access_input.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="需要密码"
            )

        if not pwd_context.verify(access_input.password, report.share_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="密码错误"
            )

    # 生成短期访问令牌（1小时有效）
    access_token = create_access_token(
        data={
            "report_id": report_id,
            "access_type": "shared",
            "share_mode": report.share_mode
        },
        expires_delta=timedelta(hours=1)
    )

    return {
        "success": True,
        "access_token": access_token,
        "report_url": f"{BASE_PATH}/api/reports/{report_id}/view?token={access_token}",
        "owner_username": report.user.username  # 用于水印
    }


@router.get("/{report_id}/shared/preview")
async def preview_shared_report(
    report_id: str,
    db: Session = Depends(get_db)
):
    """
    预览分享报告信息（无需密码）

    - 返回报告标题、创建时间等基本信息
    - 不返回报告内容
    """
    report = db.query(Report).filter(Report.report_id == report_id).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="报告不存在"
        )

    return {
        "success": True,
        "title": report.title,
        "created_at": report.created_at.isoformat(),
        "share_mode": report.share_mode,
        "requires_password": report.share_mode == "password",
        "is_expired": report.share_expires_at < datetime.now() if report.share_expires_at else False,
        "owner_username": report.user.username
    }
