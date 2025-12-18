"""
手动数据库迁移脚本
添加手机号认证功能

运行方式：python migrations/001_add_phone_auth.py
回滚方式：python migrations/001_add_phone_auth.py downgrade
"""
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from database.connection import DATABASE_URL
from database.models import Base, SMSVerification


def upgrade():
    """升级数据库架构"""
    print("=" * 60)
    print("开始数据库迁移：添加手机号认证功能")
    print("=" * 60)

    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)

    with engine.connect() as conn:
        # 1. 检查并添加 phone_number 列到 users 表
        print("\n[1/4] 检查 users 表的 phone_number 列...")
        columns = [col['name'] for col in inspector.get_columns('users')]

        if 'phone_number' not in columns:
            try:
                conn.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN phone_number VARCHAR(11)
                """))
                conn.commit()
                print("✅ 已添加 phone_number 列")
            except Exception as e:
                print(f"⚠️  添加 phone_number 列失败: {e}")
        else:
            print("✅ phone_number 列已存在，跳过")

        # 2. 检查并添加 phone_change_history 列
        print("\n[2/4] 检查 users 表的 phone_change_history 列...")
        columns = [col['name'] for col in inspector.get_columns('users')]

        if 'phone_change_history' not in columns:
            try:
                conn.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN phone_change_history JSON
                """))
                conn.commit()
                print("✅ 已添加 phone_change_history 列")
            except Exception as e:
                print(f"⚠️  添加 phone_change_history 列失败: {e}")
        else:
            print("✅ phone_change_history 列已存在，跳过")

        # 3. 创建索引（如果不存在）
        print("\n[3/4] 检查 phone_number 索引...")
        indexes = [idx['name'] for idx in inspector.get_indexes('users')]

        if 'ix_users_phone_number' not in indexes:
            try:
                conn.execute(text("""
                    CREATE INDEX ix_users_phone_number ON users(phone_number)
                """))
                conn.commit()
                print("✅ 已创建 phone_number 索引")
            except Exception as e:
                print(f"⚠️  创建索引失败: {e}")
        else:
            print("✅ phone_number 索引已存在，跳过")

    # 4. 创建 sms_verifications 表
    print("\n[4/4] 检查 sms_verifications 表...")
    if 'sms_verifications' not in inspector.get_table_names():
        try:
            Base.metadata.create_all(bind=engine, tables=[SMSVerification.__table__])
            print("✅ 已创建 sms_verifications 表")
        except Exception as e:
            print(f"⚠️  创建 sms_verifications 表失败: {e}")
    else:
        print("✅ sms_verifications 表已存在，跳过")

    print("\n" + "=" * 60)
    print("✅ 数据库迁移完成！")
    print("=" * 60)
    print("\n提示：")
    print("1. 旧用户的 phone_number 为 NULL，可继续使用用户名登录")
    print("2. 新用户必须提供手机号注册")
    print("3. 数据库已支持手机号认证功能")
    print()


def downgrade():
    """回滚迁移（仅删除新增的表）"""
    print("=" * 60)
    print("开始回滚数据库迁移")
    print("=" * 60)

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # 注意：SQLite 不支持 DROP COLUMN，所以只删除新增的表
        print("\n[1/1] 删除 sms_verifications 表...")
        try:
            conn.execute(text("DROP TABLE IF EXISTS sms_verifications"))
            conn.commit()
            print("✅ 已删除 sms_verifications 表")
        except Exception as e:
            print(f"❌ 删除失败: {e}")

    print("\n⚠️  注意：SQLite 不支持删除列，users 表的以下列将保留：")
    print("  - phone_number")
    print("  - phone_change_history")
    print("\n如需完全回滚，请手动备份数据并重建数据库。")
    print("\n" + "=" * 60)
    print("✅ 回滚完成")
    print("=" * 60)


def check_status():
    """检查迁移状态"""
    print("=" * 60)
    print("数据库迁移状态检查")
    print("=" * 60)

    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)

    # 检查 users 表
    print("\n[users 表]")
    if 'users' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('users')]
        print(f"  ✅ 表存在")
        print(f"  - phone_number: {'✅' if 'phone_number' in columns else '❌'}")
        print(f"  - phone_change_history: {'✅' if 'phone_change_history' in columns else '❌'}")

        indexes = [idx['name'] for idx in inspector.get_indexes('users')]
        print(f"  - ix_users_phone_number 索引: {'✅' if 'ix_users_phone_number' in indexes else '❌'}")
    else:
        print("  ❌ 表不存在")

    # 检查 sms_verifications 表
    print("\n[sms_verifications 表]")
    if 'sms_verifications' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('sms_verifications')]
        print(f"  ✅ 表存在")
        print(f"  - 列数: {len(columns)}")
        print(f"  - 关键列: verification_id, phone_number, code, code_type, is_verified")
    else:
        print("  ❌ 表不存在")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "downgrade":
            downgrade()
        elif command == "status":
            check_status()
        else:
            print(f"未知命令: {command}")
            print("可用命令: upgrade (默认), downgrade, status")
    else:
        # 默认执行升级
        upgrade()
