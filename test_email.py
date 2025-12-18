"""
测试邮件发送功能
"""
from services.email_service import get_email_service

def test_email():
    """测试发送报告完成通知邮件"""
    email_service = get_email_service()

    print("=" * 60)
    print("邮件服务配置检查")
    print("=" * 60)
    print(f"SMTP 服务器: {email_service.smtp_server}")
    print(f"SMTP 端口: {email_service.smtp_port}")
    print(f"发件人邮箱: {email_service.from_address}")
    print(f"发件人名称: {email_service.from_name}")
    print(f"配置状态: {'✅ 已配置' if email_service.is_configured() else '❌ 未配置'}")
    print()

    if not email_service.is_configured():
        print("❌ 邮件服务未配置，请检查 .env 文件")
        return

    print("=" * 60)
    print("开始发送测试邮件")
    print("=" * 60)

    # 发送测试邮件
    success, message = email_service.send_report_ready_notification(
        to_email="lgldppst@qq.com",
        username="测试用户",
        product_name="口红",
        report_url="http://127.0.0.1:8001/reports/test_report_20250618.html"
    )

    print()
    print("=" * 60)
    print("发送结果")
    print("=" * 60)
    if success:
        print(f"✅ {message}")
        print(f"📧 邮件已发送至: lgldppst@qq.com")
        print()
        print("请检查收件箱（可能在垃圾邮件中）")
    else:
        print(f"❌ {message}")
    print("=" * 60)


if __name__ == "__main__":
    test_email()
