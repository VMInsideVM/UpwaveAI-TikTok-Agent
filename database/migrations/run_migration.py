"""执行数据库迁移 - 添加报告分享功能字段"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import text
from database.connection import get_db_context


def run_migration():
    """执行报告分享字段迁移"""
    with get_db_context() as db:
        print("[INFO] Starting database migration: Adding report sharing fields...")

        try:
            # 添加字段（SQLite每次只能添加一个字段）
            print("[INFO] Adding share_mode column...")
            db.execute(text("ALTER TABLE reports ADD COLUMN share_mode VARCHAR(20) NOT NULL DEFAULT 'private'"))

            print("[INFO] Adding share_password column...")
            db.execute(text("ALTER TABLE reports ADD COLUMN share_password VARCHAR(128)"))

            print("[INFO] Adding share_expires_at column...")
            db.execute(text("ALTER TABLE reports ADD COLUMN share_expires_at DATETIME"))

            print("[INFO] Adding share_created_at column...")
            db.execute(text("ALTER TABLE reports ADD COLUMN share_created_at DATETIME"))

            # 创建索引
            print("[INFO] Creating indexes...")
            db.execute(text("CREATE INDEX ix_reports_share_mode ON reports(share_mode)"))
            db.execute(text("CREATE INDEX ix_reports_share_expires_at ON reports(share_expires_at)"))

            db.commit()
            print("[SUCCESS] Database migration completed!")
            print("")
            print("New fields added:")
            print("  - share_mode: VARCHAR(20) [private/public/password]")
            print("  - share_password: VARCHAR(128) [encrypted]")
            print("  - share_expires_at: DATETIME")
            print("  - share_created_at: DATETIME")
            return True

        except Exception as e:
            db.rollback()
            print(f"[ERROR] Migration failed: {e}")
            return False


def rollback_migration():
    """回滚迁移"""
    with get_db_context() as db:
        print("[INFO] Rolling back database migration...")

        try:
            # 删除索引
            db.execute(text("DROP INDEX IF EXISTS ix_reports_share_expires_at"))
            db.execute(text("DROP INDEX IF EXISTS ix_reports_share_mode"))

            # 删除字段
            db.execute(text("""
                ALTER TABLE reports
                DROP COLUMN share_created_at,
                DROP COLUMN share_expires_at,
                DROP COLUMN share_password,
                DROP COLUMN share_mode
            """))

            db.commit()
            print("[SUCCESS] Migration rolled back successfully")
            return True

        except Exception as e:
            db.rollback()
            print(f"[ERROR] Rollback failed: {e}")
            return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        success = rollback_migration()
    else:
        success = run_migration()

    sys.exit(0 if success else 1)
