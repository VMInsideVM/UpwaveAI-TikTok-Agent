"""
数据库迁移脚本：添加双进度条字段

添加以下字段到 reports 表:
- scraping_progress: 爬取进度 (0-100)
- scraping_eta: 爬取预计剩余时间（秒）
- report_progress: 报告生成进度 (0-100)
- report_eta: 报告生成预计剩余时间（秒）
"""

import os
from sqlalchemy import create_engine, Column, Integer, inspect, text
from sqlalchemy.orm import sessionmaker
from database.models import Base, Report
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def migrate():
    """执行数据库迁移"""

    # 创建数据库引擎
    db_path = os.getenv("DATABASE_URL", "sqlite:///./chatbot.db")
    engine = create_engine(db_path)

    # 检查当前表结构
    inspector = inspect(engine)
    existing_columns = [col['name'] for col in inspector.get_columns('reports')]

    print("🔍 当前 reports 表字段:")
    for col in existing_columns:
        print(f"   - {col}")

    # 需要添加的新字段
    new_fields = ['scraping_progress', 'scraping_eta', 'report_progress', 'report_eta']
    missing_fields = [field for field in new_fields if field not in existing_columns]

    if not missing_fields:
        print("\n✅ 所有字段已存在，无需迁移")
        return

    print(f"\n📝 需要添加的字段: {', '.join(missing_fields)}")

    # SQLite 不支持 ALTER TABLE ADD COLUMN with default，需要手动添加
    with engine.connect() as conn:
        try:
            if 'scraping_progress' in missing_fields:
                print("➕ 添加字段: scraping_progress")
                conn.execute(text("ALTER TABLE reports ADD COLUMN scraping_progress INTEGER DEFAULT 0"))

            if 'scraping_eta' in missing_fields:
                print("➕ 添加字段: scraping_eta")
                conn.execute(text("ALTER TABLE reports ADD COLUMN scraping_eta INTEGER"))

            if 'report_progress' in missing_fields:
                print("➕ 添加字段: report_progress")
                conn.execute(text("ALTER TABLE reports ADD COLUMN report_progress INTEGER DEFAULT 0"))

            if 'report_eta' in missing_fields:
                print("➕ 添加字段: report_eta")
                conn.execute(text("ALTER TABLE reports ADD COLUMN report_eta INTEGER"))

            conn.commit()
            print("\n✅ 数据库迁移成功！")

        except Exception as e:
            print(f"\n❌ 迁移失败: {e}")
            conn.rollback()
            raise

    # 验证迁移结果
    inspector = inspect(engine)
    updated_columns = [col['name'] for col in inspector.get_columns('reports')]

    print("\n🎉 迁移后的 reports 表字段:")
    for col in updated_columns:
        print(f"   - {col}")

if __name__ == "__main__":
    print("="*60)
    print("数据库迁移：添加双进度条字段")
    print("="*60)

    migrate()
