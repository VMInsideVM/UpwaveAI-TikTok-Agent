"""
测试手机号认证功能
验证配置和基本功能
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from services.sms_service import SMSService, get_sms_service
from database.connection import get_db_context
from database.models import User, SMSVerification


def test_sms_service_config():
    """测试SMS服务配置"""
    print("=" * 60)
    print("测试 SMS 服务配置")
    print("=" * 60)

    service = get_sms_service()

    print("\n✅ SMS 服务初始化成功")
    print(f"  - 阿里云 AccessKey ID: {os.getenv('ALIYUN_ACCESS_KEY_ID', 'NOT SET')[:10]}...")
    print(f"  - 短信签名: {os.getenv('ALIYUN_SMS_SIGN_NAME', 'NOT SET')}")
    print(f"  - 注册模板: {os.getenv('SMS_TEMPLATE_REGISTER', 'NOT SET')}")
    print(f"  - 重置密码模板: {os.getenv('SMS_TEMPLATE_RESET_PASSWORD', 'NOT SET')}")

    # 测试验证码生成
    code = service.generate_code()
    print(f"\n✅ 验证码生成测试:")
    print(f"  - 生成的验证码: {code}")
    print(f"  - 验证码长度: {len(code)} 位")
    print(f"  - 是否全为数字: {code.isdigit()}")

    # 测试手机号验证
    test_phones = [
        ("13800138000", True),
        ("15912345678", True),
        ("12345678901", False),  # 第二位不是3-9
        ("138001380", False),     # 长度不够
        ("1380013800a", False),   # 包含字母
    ]

    print(f"\n✅ 手机号格式验证测试:")
    for phone, expected in test_phones:
        result = service.validate_phone_format(phone)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {phone}: {result} (期望: {expected})")

    print("\n" + "=" * 60)


def test_database_structure():
    """测试数据库结构"""
    print("\n" + "=" * 60)
    print("测试数据库结构")
    print("=" * 60)

    with get_db_context() as db:
        # 检查 users 表
        user_count = db.query(User).count()
        print(f"\n✅ Users 表:")
        print(f"  - 现有用户数: {user_count}")

        # 检查是否有用户有 phone_number
        phone_users = db.query(User).filter(User.phone_number != None).count()
        print(f"  - 已绑定手机号的用户: {phone_users}")

        # 检查 sms_verifications 表
        sms_count = db.query(SMSVerification).count()
        print(f"\n✅ SMS Verifications 表:")
        print(f"  - 验证码记录数: {sms_count}")

    print("\n" + "=" * 60)


def test_api_endpoints_exist():
    """测试API端点是否存在"""
    print("\n" + "=" * 60)
    print("测试 API 端点")
    print("=" * 60)

    try:
        from api.auth import router

        # 获取所有路由
        routes = []
        for route in router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = list(route.methods)
                routes.append((methods[0] if methods else 'N/A', route.path))

        print("\n✅ 认证相关端点:")

        # 检查SMS相关端点
        sms_endpoints = [
            "POST /api/auth/send-sms-code",
            "POST /api/auth/register-phone",
            "POST /api/auth/login-phone",
            "POST /api/auth/reset-password",
            "POST /api/auth/change-phone",
        ]

        for endpoint in sms_endpoints:
            method, path = endpoint.split(' ')
            found = any(r[1] == path.replace('/api/auth', '') and method in str(r[0]) for r in routes)
            status = "✅" if found else "❌"
            print(f"  {status} {endpoint}")

        # 显示所有端点
        print("\n所有认证端点:")
        for method, path in sorted(routes):
            print(f"  - {method} /api/auth{path}")

    except Exception as e:
        print(f"❌ 加载 API 端点失败: {e}")

    print("\n" + "=" * 60)


def main():
    """主测试函数"""
    print("\n" + "🧪" * 30)
    print("手机号认证功能测试套件")
    print("🧪" * 30 + "\n")

    try:
        # 1. 测试SMS服务配置
        test_sms_service_config()

        # 2. 测试数据库结构
        test_database_structure()

        # 3. 测试API端点
        test_api_endpoints_exist()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成!")
        print("=" * 60)
        print("\n📝 下一步:")
        print("  1. 启动 FastAPI 服务: python chatbot_api.py")
        print("  2. 使用 Postman/curl 测试 API 端点")
        print("  3. 发送真实短信验证（需要手机号）")
        print()

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
