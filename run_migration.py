"""
数据库迁移脚本: 从配额制改为积分制
执行此脚本前请先备份数据库!
"""
import sqlite3
import os
from datetime import datetime

# 数据库路径
DB_PATH = "chatbot.db"
BACKUP_DIR = "migrations/backups"

def backup_database():
    """备份数据库"""
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        return False

    # 创建备份目录
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # 生成备份文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"chatbot_backup_{timestamp}.db")

    # 复制数据库文件
    import shutil
    shutil.copy2(DB_PATH, backup_path)

    print(f"✅ 数据库已备份到: {backup_path}")
    return True

def run_migration():
    """执行迁移"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("\n🔄 开始执行数据库迁移...")

        # 1. 检查当前表结构
        print("\n📊 检查当前表结构...")
        cursor.execute("PRAGMA table_info(user_usage)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        print(f"当前字段: {column_names}")

        # 检查是否已经迁移过
        if 'total_credits' in column_names:
            print("⚠️  数据库已经是新的积分结构，无需再次迁移")
            return

        if 'total_quota' not in column_names:
            print("⚠️  未找到 total_quota 字段，数据库结构异常")
            return

        # 2. 查看迁移前的数据
        print("\n📋 迁移前的数据样本:")
        cursor.execute("SELECT user_id, total_quota, used_count FROM user_usage LIMIT 5")
        before_data = cursor.fetchall()
        for row in before_data:
            print(f"  用户: {row[0][:8]}... | 配额: {row[1]} | 已使用: {row[2]}")

        # 3. 备份原表
        print("\n💾 创建备份表...")
        cursor.execute("DROP TABLE IF EXISTS user_usage_backup")
        cursor.execute("CREATE TABLE user_usage_backup AS SELECT * FROM user_usage")
        backup_count = cursor.execute("SELECT COUNT(*) FROM user_usage_backup").fetchone()[0]
        print(f"  已备份 {backup_count} 条记录")

        # 4. 重建表结构
        print("\n🔨 重建表结构...")
        cursor.execute("DROP TABLE user_usage")
        cursor.execute("""
            CREATE TABLE user_usage (
                usage_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                total_credits INTEGER NOT NULL DEFAULT 300,
                used_credits INTEGER NOT NULL DEFAULT 0,
                last_reset_date TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("CREATE INDEX idx_user_usage_user_id ON user_usage(user_id)")
        print("  ✓ 新表结构已创建")

        # 5. 迁移数据
        print("\n📦 迁移数据...")
        cursor.execute("""
            INSERT INTO user_usage (usage_id, user_id, total_credits, used_credits, last_reset_date)
            SELECT
                usage_id,
                user_id,
                total_quota * 300 AS total_credits,
                used_count * 300 AS used_credits,
                last_reset_date
            FROM user_usage_backup
        """)
        migrated_count = cursor.rowcount
        print(f"  ✓ 已迁移 {migrated_count} 条记录")

        # 6. 验证迁移结果
        print("\n✅ 迁移后的数据样本:")
        cursor.execute("""
            SELECT user_id, total_credits, used_credits,
                   (total_credits - used_credits) as remaining_credits
            FROM user_usage LIMIT 5
        """)
        after_data = cursor.fetchall()
        for row in after_data:
            print(f"  用户: {row[0][:8]}... | 总积分: {row[1]} | 已使用: {row[2]} | 剩余: {row[3]}")

        # 7. 统计信息
        print("\n📊 迁移统计:")
        cursor.execute("SELECT COUNT(*) FROM user_usage")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(total_credits) FROM user_usage")
        total_credits = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(used_credits) FROM user_usage")
        used_credits = cursor.fetchone()[0] or 0

        print(f"  总用户数: {total_users}")
        print(f"  总积分池: {total_credits}")
        print(f"  已使用积分: {used_credits}")
        print(f"  剩余积分: {total_credits - used_credits}")

        # 8. 提交事务
        conn.commit()
        print("\n✅ 迁移成功完成!")
        print("\n💡 提示:")
        print("  - 备份表 'user_usage_backup' 已保留，可用于回滚")
        print("  - 如需删除备份表，请手动执行: DROP TABLE user_usage_backup")

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        print("正在回滚...")
        conn.rollback()

        # 尝试恢复
        try:
            cursor.execute("DROP TABLE IF EXISTS user_usage")
            cursor.execute("CREATE TABLE user_usage AS SELECT * FROM user_usage_backup")
            cursor.execute("CREATE INDEX idx_user_usage_user_id ON user_usage(user_id)")
            conn.commit()
            print("✅ 已回滚到原始状态")
        except Exception as rollback_error:
            print(f"❌ 回滚失败: {rollback_error}")
            print("⚠️  请从备份文件手动恢复数据库!")

    finally:
        conn.close()

def main():
    """主函数"""
    print("=" * 60)
    print("数据库迁移: 配额制 → 积分制")
    print("=" * 60)

    # 检查数据库文件
    if not os.path.exists(DB_PATH):
        print(f"❌ 数据库文件不存在: {DB_PATH}")
        print("提示: 如果是首次运行，请先启动服务创建数据库")
        return

    # 备份数据库
    print("\n📦 正在备份数据库...")
    if not backup_database():
        return

    # 确认执行
    print("\n⚠️  警告: 此操作将修改数据库结构!")
    print("请确保:")
    print("  1. 已经备份了数据库")
    print("  2. 已经停止了所有服务")
    print("  3. 了解迁移的影响")

    response = input("\n是否继续? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ 已取消迁移")
        return

    # 执行迁移
    run_migration()

    print("\n" + "=" * 60)
    print("迁移完成! 现在可以启动服务了")
    print("=" * 60)

if __name__ == "__main__":
    main()
