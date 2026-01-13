#!/bin/bash
# 一键数据库迁移脚本

set -e  # 遇到错误立即退出

echo "======================================================"
echo "    数据库迁移：添加报告分享功能"
echo "======================================================"
echo ""

# 数据库路径
DB_PATH="${1:-chatbot.db}"

# 检查数据库文件是否存在
if [ ! -f "$DB_PATH" ]; then
    echo "❌ 数据库文件不存在: $DB_PATH"
    exit 1
fi

echo "📂 数据库路径: $DB_PATH"
echo ""

# 1. 备份数据库
BACKUP_NAME="chatbot.db.backup.$(date +%Y%m%d_%H%M%S)"
echo "💾 备份数据库..."
cp "$DB_PATH" "$BACKUP_NAME"
echo "✅ 备份完成: $BACKUP_NAME"
echo ""

# 2. 运行迁移脚本
echo "🔧 运行迁移脚本..."
python migrations/add_report_sharing_fields.py "$DB_PATH"
MIGRATION_STATUS=$?

echo ""

# 3. 检查迁移结果
if [ $MIGRATION_STATUS -eq 0 ]; then
    echo "======================================================"
    echo "✅ 迁移成功！"
    echo "======================================================"
    echo ""
    echo "后续步骤："
    echo "1. 重启服务:"
    echo "   sudo systemctl restart chatbot"
    echo "   或: pkill -f chatbot_api.py && python start_chatbot.py"
    echo ""
    echo "2. 如果遇到问题，恢复备份:"
    echo "   cp $BACKUP_NAME $DB_PATH"
    echo ""
else
    echo "======================================================"
    echo "❌ 迁移失败！"
    echo "======================================================"
    echo ""
    echo "请检查错误信息，或恢复备份:"
    echo "   cp $BACKUP_NAME $DB_PATH"
    echo ""
    exit 1
fi
