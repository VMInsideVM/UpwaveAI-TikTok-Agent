"""
修复管理员账户脚本
Fix Admin Account Script
"""
from database.connection import get_db_context, hash_password
from database.models import User, UserUsage
import os
from dotenv import load_dotenv

load_dotenv()

def fix_admin_account():
    """修复或重置管理员账户"""

    admin_username = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
    admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "***REMOVED***")
    admin_email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@fastmoss.com")

    with get_db_context() as db:
        # 查找管理员账户
        admin_user = db.query(User).filter(User.username == admin_username).first()

        if not admin_user:
            print(f"❌ 未找到管理员账户 '{admin_username}'")
            print("请先运行 start_chatbot.py 创建管理员账户")
            return

        print(f"✅ 找到管理员账户: {admin_username}")

        # 重置密码
        print(f"🔧 重置密码为: {admin_password}")
        admin_user.hashed_password = hash_password(admin_password)

        # 确保管理员标志
        admin_user.is_admin = True
        admin_user.is_active = True
        admin_user.is_verified = True

        # 检查并修复积分记录
        usage = db.query(UserUsage).filter(
            UserUsage.user_id == admin_user.user_id
        ).first()

        if usage:
            print(f"✅ 找到积分记录")
            # 确保使用正确的字段名
            usage.total_credits = 999999
            usage.used_credits = 0
            print(f"🔧 重置积分: 999999")
        else:
            print(f"⚠️  积分记录不存在，创建新记录")
            usage = UserUsage(
                user_id=admin_user.user_id,
                total_credits=999999,
                used_credits=0
            )
            db.add(usage)

        db.commit()

        print("\n" + "=" * 60)
        print("✅ 管理员账户修复成功！")
        print("=" * 60)
        print(f"用户名: {admin_username}")
        print(f"密码: {admin_password}")
        print(f"邮箱: {admin_email}")
        print(f"积分: 999999 (无限)")
        print("=" * 60)
        print("\n现在可以使用上述凭据登录管理后台了！")


if __name__ == "__main__":
    print("🔧 开始修复管理员账户...\n")
    fix_admin_account()
