#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速诊断数据库结构
检查是否需要迁移
"""

import sqlite3
import os
import sys

def check_database(db_path: str = "chatbot.db"):
    """检查数据库结构"""
    print("=" * 60)
    print("🔍 数据库结构诊断")
    print("=" * 60)
    print()

    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查 reports 表
        cursor.execute("PRAGMA table_info(reports)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        print(f"📊 数据库路径: {db_path}")
        print(f"📋 reports 表字段数: {len(columns)}")
        print()

        # 检查分享功能字段
        required_fields = {
            'share_mode': 'VARCHAR(20)',
            'share_password': 'VARCHAR(128)',
            'share_expires_at': 'DATETIME',
            'share_created_at': 'DATETIME'
        }

        missing_fields = []
        existing_fields = []

        print("🔍 分享功能字段检查:")
        print()

        for field, field_type in required_fields.items():
            if field in columns:
                existing_fields.append(field)
                print(f"  ✅ {field:<20} ({columns[field]})")
            else:
                missing_fields.append(field)
                print(f"  ❌ {field:<20} (缺失)")

        print()
        print("-" * 60)
        print()

        # 统计报告数量
        cursor.execute("SELECT COUNT(*) FROM reports")
        report_count = cursor.fetchone()[0]
        print(f"📊 报告总数: {report_count}")

        # 统计分享状态（如果字段存在）
        if 'share_mode' in columns:
            cursor.execute("""
                SELECT share_mode, COUNT(*) as count
                FROM reports
                GROUP BY share_mode
            """)
            print("\n📊 分享状态分布:")
            for mode, count in cursor.fetchall():
                mode_name = {
                    'private': '不公开',
                    'public': '完全公开',
                    'password': '密码保护'
                }.get(mode, mode)
                print(f"  - {mode_name}: {count}")

        conn.close()

        print()
        print("=" * 60)

        # 判断结论
        if missing_fields:
            print("⚠️  需要运行数据库迁移!")
            print()
            print("缺失字段:", ", ".join(missing_fields))
            print()
            print("运行命令:")
            print("  python migrations/add_report_sharing_fields.py")
            print("或:")
            print("  bash migrate.sh")
            print("=" * 60)
            return False
        else:
            print("✅ 数据库结构正常，无需迁移")
            print("=" * 60)
            return True

    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "chatbot.db"

    result = check_database(db_path)
    sys.exit(0 if result else 1)
