#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移：为 reports 表添加分享功能字段
运行此脚本以升级 VPS 上的数据库结构
"""

import sqlite3
import os

def migrate_database(db_path="chatbot.db"):
    """
    为 reports 表添加分享功能相关字段

    Args:
        db_path: 数据库文件路径，默认为 chatbot.db

    新增字段:
    - share_mode: 分享模式 (private/public/password)
    - share_password: 分享密码
    - share_expires_at: 分享过期时间
    - share_created_at: 分享创建时间
    """
    print(f"🔧 开始迁移数据库: {db_path}")

    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查 reports 表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='reports'
        """)

        if not cursor.fetchone():
            print("❌ reports 表不存在，无需迁移")
            conn.close()
            return False

        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(reports)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        print(f"📊 当前 reports 表字段: {existing_columns}")

        # 需要添加的字段
        new_columns = {
            'share_mode': "VARCHAR(20) DEFAULT 'private' NOT NULL",
            'share_password': "VARCHAR(128)",
            'share_expires_at': "DATETIME",
            'share_created_at': "DATETIME"
        }

        added_count = 0

        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                print(f"➕ 添加字段: {column_name} ({column_type})")

                cursor.execute(f"""
                    ALTER TABLE reports
                    ADD COLUMN {column_name} {column_type}
                """)

                added_count += 1
            else:
                print(f"⏭️  字段已存在，跳过: {column_name}")

        # 为新字段创建索引（如果字段是新添加的）
        if 'share_mode' not in existing_columns:
            print("📇 创建 share_mode 索引...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_share_mode
                ON reports(share_mode)
            """)

        if 'share_expires_at' not in existing_columns:
            print("📇 创建 share_expires_at 索引...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reports_share_expires_at
                ON reports(share_expires_at)
            """)

        # 提交更改
        conn.commit()
        conn.close()

        print(f"✅ 迁移完成! 共添加 {added_count} 个字段")

        return True

    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


def verify_migration(db_path="chatbot.db"):
    """验证迁移是否成功"""
    print(f"\n🔍 验证迁移结果...")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(reports)")
        columns = cursor.fetchall()

        required_fields = ['share_mode', 'share_password', 'share_expires_at', 'share_created_at']
        found_fields = [col[1] for col in columns if col[1] in required_fields]

        print(f"📋 分享功能字段: {found_fields}")

        if len(found_fields) == len(required_fields):
            print("✅ 所有字段都已正确添加!")

            # 显示一条示例记录
            cursor.execute("SELECT report_id, share_mode FROM reports LIMIT 1")
            sample = cursor.fetchone()
            if sample:
                print(f"📄 示例记录: report_id={sample[0]}, share_mode={sample[1]}")
        else:
            missing = set(required_fields) - set(found_fields)
            print(f"⚠️  缺失字段: {missing}")

        conn.close()
        return len(found_fields) == len(required_fields)

    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


if __name__ == "__main__":
    import sys

    # 从命令行参数获取数据库路径，默认为 chatbot.db
    db_path = sys.argv[1] if len(sys.argv) > 1 else "chatbot.db"

    print("=" * 60)
    print("📦 数据库迁移脚本：添加报告分享功能")
    print("=" * 60)
    print()

    # 执行迁移
    success = migrate_database(db_path)

    if success:
        # 验证迁移
        verify_migration(db_path)

        print()
        print("=" * 60)
        print("🎉 迁移完成! 可以重启服务了")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ 迁移失败，请检查错误信息")
        print("=" * 60)
        sys.exit(1)
