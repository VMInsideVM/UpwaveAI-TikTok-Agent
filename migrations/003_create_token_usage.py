"""
数据库迁移：创建 TokenUsage 表并更新 UserUsage 表
"""
from sqlalchemy import create_engine, text, inspect
import os
import sys

# 添加项目根目录到 python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import TokenUsage, Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chatbot.db")
# 确保使用绝对路径
if "sqlite:///" in DATABASE_URL and not os.path.isabs(DATABASE_URL.replace("sqlite:///", "")):
    db_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "chatbot.db"))
    DATABASE_URL = f"sqlite:///{db_path}"

print(f"Dataset URL: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)

def run_migration():
    print("🔧 开始 Token Usage 迁移...")

    # 1. 创建 TokenUsage 表
    print("📝 检查并创建 TokenUsage 表...")
    inspector = inspect(engine)
    if not inspector.has_table("token_usage"):
        TokenUsage.__table__.create(engine)
        print("✅ TokenUsage 表创建成功")
    else:
        print("⏭️ TokenUsage 表已存在，跳过创建")

    # 2. 更新 UserUsage 表
    print("📝 检查 UserUsage 表字段...")
    with engine.connect() as conn:
        try:
            # 检查字段是否存在
            columns = [col['name'] for col in inspector.get_columns("user_usage")]
            
            if 'total_tokens_used' not in columns:
                print("➕ 添加 total_tokens_used 字段到 user_usage 表...")
                conn.execute(text("ALTER TABLE user_usage ADD COLUMN total_tokens_used INTEGER DEFAULT 0 NOT NULL"))
                print("✅ 字段添加成功")
            else:
                print("⏭️ total_tokens_used 字段已存在，跳过")
                
            conn.commit()
        except Exception as e:
            print(f"❌ 更新 UserUsage 表失败: {e}")
            conn.rollback()

    print("✅ 迁移完成！")

if __name__ == "__main__":
    run_migration()
