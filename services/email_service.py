"""
Email Service
邮件发送服务
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# SMTP 配置
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "TikTok 达人推荐系统")
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "")


class EmailService:
    """邮件发送服务"""

    def __init__(self):
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.username = SMTP_USERNAME
        self.password = SMTP_PASSWORD
        self.from_name = EMAIL_FROM_NAME
        self.from_address = EMAIL_FROM_ADDRESS

    def is_configured(self) -> bool:
        """检查邮件服务是否已配置"""
        return bool(self.username and self.password and self.from_address)

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        发送邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_content: HTML 内容
            text_content: 纯文本内容（可选）

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        if not self.is_configured():
            return False, "邮件服务未配置"

        if not to_email:
            return False, "收件人邮箱为空"

        try:
            # 创建邮件
            message = MIMEMultipart('alternative')
            message['From'] = formataddr((self.from_name, self.from_address))
            message['To'] = to_email
            message['Subject'] = Header(subject, 'utf-8')

            # 添加纯文本版本（如果提供）
            if text_content:
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                message.attach(text_part)

            # 添加 HTML 版本
            html_part = MIMEText(html_content, 'html', 'utf-8')
            message.attach(html_part)

            # 连接 SMTP 服务器并发送
            # 根据端口选择连接方式
            if self.smtp_port == 465:
                # 使用 SSL 连接
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.username, self.password)
                    server.send_message(message)
            else:
                # 使用 STARTTLS 连接
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()  # 启用 TLS 加密
                    server.login(self.username, self.password)
                    server.send_message(message)

            print(f"✅ 邮件发送成功: {to_email}")
            return True, "邮件发送成功"

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"邮件服务认证失败: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"   用户名: {self.username}")
            print(f"   服务器: {self.smtp_server}:{self.smtp_port}")
            return False, error_msg

        except smtplib.SMTPException as e:
            error_msg = f"邮件发送失败: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg

        except Exception as e:
            error_msg = f"发送邮件时发生错误: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg

    def send_report_ready_notification(
        self,
        to_email: str,
        username: str,
        product_name: str,
        report_url: str,
        completed_at: Optional[datetime] = None
    ) -> tuple[bool, str]:
        """
        发送报告完成通知邮件

        Args:
            to_email: 收件人邮箱
            username: 用户名
            product_name: 产品名称
            report_url: 报告链接
            completed_at: 报告完成时间（可选，默认使用当前时间）

        Returns:
            tuple[bool, str]: (是否成功, 消息)
        """
        # 格式化完成时间
        if completed_at is None:
            completed_at = datetime.utcnow()

        # 转换为中国时区显示（UTC+8）
        from datetime import timedelta
        china_time = completed_at + timedelta(hours=8)
        formatted_time = china_time.strftime('%Y年%m月%d日 %H:%M:%S')

        subject = f"您的达人推荐报告已生成完成 - {product_name}"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .content {{
            padding: 30px;
        }}
        .content p {{
            line-height: 1.6;
            color: #333;
            margin: 10px 0;
        }}
        .report-info {{
            background-color: #f9fafb;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin: 20px 0;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 6px;
            margin: 20px 0;
            font-weight: 600;
        }}
        .footer {{
            background-color: #f9fafb;
            padding: 20px;
            text-align: center;
            color: #6b7280;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎉 报告生成完成</h1>
        </div>
        <div class="content">
            <p>尊敬的 <strong>{username}</strong>，</p>
            <p>您好！您请求的达人推荐报告已经生成完成。</p>

            <div class="report-info">
                <p><strong>产品名称:</strong> {product_name}</p>
                <p><strong>生成时间:</strong> {formatted_time}</p>
            </div>

            <p>点击下方按钮查看详细报告：</p>
            <a href="{report_url}" class="btn">查看报告</a>

            <p>报告包含了为您精选的 TikTok 达人推荐，以及详细的数据分析和评分。</p>
        </div>
        <div class="footer">
            <p>此邮件由 TikTok 达人推荐系统自动发送，请勿回复</p>
            <p>&copy; 2025 杭州升澜智能科技有限公司</p>
        </div>
    </div>
</body>
</html>
"""

        text_content = f"""
尊敬的 {username}，

您好！您请求的达人推荐报告已经生成完成。

产品名称: {product_name}
生成时间: {formatted_time}

查看报告: {report_url}

报告包含了为您精选的 TikTok 达人推荐，以及详细的数据分析和评分。

---
此邮件由 TikTok 达人推荐系统自动发送，请勿回复
© 2025 杭州升澜智能科技有限公司
"""

        return self.send_email(to_email, subject, html_content, text_content)


# 单例模式
_email_service_instance = None


def get_email_service() -> EmailService:
    """获取邮件服务实例（单例模式）"""
    global _email_service_instance
    if _email_service_instance is None:
        _email_service_instance = EmailService()
    return _email_service_instance


if __name__ == "__main__":
    """测试邮件服务"""
    service = get_email_service()

    print(f"邮件服务配置状态: {service.is_configured()}")

    if service.is_configured():
        # 发送测试邮件
        success, message = service.send_report_ready_notification(
            to_email="test@example.com",
            username="测试用户",
            product_name="测试产品",
            report_url="http://127.0.0.1:8001/reports/test_report.html"
        )
        print(f"发送结果: {message}")
    else:
        print("⚠️ 邮件服务未配置，请在 .env 中设置 SMTP 相关参数")
