"""
SMTP 连接测试脚本
测试阿里云企业邮箱连接
"""
import smtplib
import os
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

print("=" * 60)
print("SMTP 连接测试")
print("=" * 60)
print(f"服务器: {SMTP_SERVER}")
print(f"端口: {SMTP_PORT}")
print(f"用户名: {SMTP_USERNAME}")
print(f"密码: {'*' * len(SMTP_PASSWORD) if SMTP_PASSWORD else '未设置'}")
print()

try:
    print("正在连接 SMTP 服务器...")

    if SMTP_PORT == 465:
        # SSL 连接
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        print("✅ SSL 连接成功")
    else:
        # STARTTLS 连接
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        print("✅ STARTTLS 连接成功")

    print()
    print("正在登录...")

    # 尝试登录
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    print("✅ 登录成功！")

    # 关闭连接
    server.quit()
    print()
    print("=" * 60)
    print("✅ 测试通过！邮件服务配置正确")
    print("=" * 60)

except smtplib.SMTPAuthenticationError as e:
    print(f"❌ 认证失败: {e}")
    print()
    print("可能的原因:")
    print("1. 用户名或密码错误")
    print("2. 需要使用授权码而不是密码")
    print("3. 阿里云企业邮箱可能需要在管理后台开启 SMTP 权限")
    print("4. 密码可能包含特殊字符需要转义")

except smtplib.SMTPException as e:
    print(f"❌ SMTP 错误: {e}")

except Exception as e:
    print(f"❌ 连接错误: {e}")
    print()
    print("可能的原因:")
    print("1. 服务器地址或端口错误")
    print("2. 网络连接问题")
    print("3. 防火墙阻止连接")
