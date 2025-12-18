"""
数据库迁移：添加 Token 追踪和速率限制表
"""
from sqlalchemy import create_engine, text, Index
from database.models import TokenUsage, RateLimitRecord, Base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fastmoss.db")
engine = create_engine(DATABASE_URL)

def run_migration():
    print("🔧 开始 Token 追踪迁移...")

    # 步骤 1: 创建新表
    print("📝 创建 TokenUsage 表...")
    TokenUsage.__table__.create(engine, checkfirst=True)

    print("📝 创建 RateLimitRecord 表...")
    RateLimitRecord.__table__.create(engine, checkfirst=True)

    # 步骤 2: 添加索引
    print("📝 创建索引...")
    try:
        idx1 = Index('idx_token_user_created', TokenUsage.user_id, TokenUsage.created_at)
        idx2 = Index('idx_token_session_created', TokenUsage.session_id, TokenUsage.created_at)
        idx3 = Index('idx_rate_limit_composite',
                     RateLimitRecord.user_id,
                     RateLimitRecord.action_type,
                     RateLimitRecord.created_at)
        idx1.create(engine, checkfirst=True)
        idx2.create(engine, checkfirst=True)
        idx3.create(engine, checkfirst=True)
    except Exception as e:
        print(f"⚠️ 索引创建错误（可能已存在）: {e}")

    # 步骤 3: 给 user_usage 表添加 token 配额字段
    print("📝 给 user_usage 表添加 token 配额字段...")
    with engine.connect() as conn:
        try:
            # 检查列是否已存在
            result = conn.execute(text("PRAGMA table_info(user_usage)"))
            columns = [row[1] for row in result.fetchall()]

            if 'total_token_quota' not in columns:
                conn.execute(text("ALTER TABLE user_usage ADD COLUMN total_token_quota INTEGER DEFAULT 100000 NOT NULL"))
                print("✅ 添加了 total_token_quota 字段")
            else:
                print("⏭️ total_token_quota 字段已存在，跳过")

            if 'used_tokens' not in columns:
                conn.execute(text("ALTER TABLE user_usage ADD COLUMN used_tokens INTEGER DEFAULT 0 NOT NULL"))
                print("✅ 添加了 used_tokens 字段")
            else:
                print("⏭️ used_tokens 字段已存在，跳过")

            if 'token_quota_reset_at' not in columns:
                conn.execute(text("ALTER TABLE user_usage ADD COLUMN token_quota_reset_at DATETIME"))
                print("✅ 添加了 token_quota_reset_at 字段")
            else:
                print("⏭️ token_quota_reset_at 字段已存在，跳过")

            conn.commit()
        except Exception as e:
            print(f"⚠️ 字段添加错误: {e}")
            conn.rollback()

    # 步骤 4: 回填现有用户的 token 配额
    print("📝 回填现有用户的 token 配额...")
    with engine.connect() as conn:
        try:
            # 设置默认值（如果是 NULL）
            result = conn.execute(text("""
                UPDATE user_usage
                SET total_token_quota = 100000,
                    used_tokens = 0
                WHERE total_token_quota IS NULL OR used_tokens IS NULL
            """))
            conn.commit()
            print(f"✅ 回填了 {result.rowcount} 条用户记录")
        except Exception as e:
            print(f"⚠️ 回填错误: {e}")
            conn.rollback()

    print("✅ 迁移完成！")

if __name__ == "__main__":
    # 提示用户备份数据库
    print("=" * 80)
    print("⚠️  重要提示：运行迁移前请先备份数据库！")
    print("   备份命令：cp fastmoss.db fastmoss.db.backup_$(date +%Y%m%d_%H%M%S)")
    print("=" * 80)

    response = input("\n是否已经备份数据库？(yes/no): ")
    if response.lower() in ['yes', 'y']:
        run_migration()
    else:
        print("❌ 迁移已取消。请先备份数据库后再运行。")
