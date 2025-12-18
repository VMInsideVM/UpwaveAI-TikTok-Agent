"""
测试短信发送功能
"""
from services.sms_service import get_sms_service

def test_sms():
    """测试发送报告完成通知短信"""
    sms_service = get_sms_service()

    print("=" * 60)
    print("短信服务测试")
    print("=" * 60)
    print("阿里云短信服务配置:")
    print(f"  签名: 杭州升澜智能科技有限公司")
    print(f"  模板: SMS_499100445")
    print()

    # 测试手机号（请替换为真实手机号）
    test_phone = input("请输入测试手机号（11位）: ").strip()

    if not test_phone or len(test_phone) != 11:
        print("❌ 手机号格式错误")
        return

    print()
    print("=" * 60)
    print("开始发送测试短信")
    print("=" * 60)

    # 发送测试短信
    success, message = sms_service.send_report_ready_notification(
        phone=test_phone,
        product_name="口红"
    )

    print()
    print("=" * 60)
    print("发送结果")
    print("=" * 60)
    if success:
        print(f"✅ {message}")
        print(f"📱 短信已发送至: {test_phone}")
        print()
        print("请检查手机是否收到短信")
    else:
        print(f"❌ {message}")
    print("=" * 60)


if __name__ == "__main__":
    test_sms()
