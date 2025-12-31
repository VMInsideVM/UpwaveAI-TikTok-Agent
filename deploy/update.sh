#!/bin/bash

# 项目更新脚本
# 用于更新代码并重启服务

set -e

DEPLOY_USER="upwaveai"
DEPLOY_DIR="/home/$DEPLOY_USER/UpwaveAI-TikTok-Agent"

echo "🔄 开始更新项目..."

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 root 用户运行此脚本"
    echo "使用命令: sudo bash update.sh"
    exit 1
fi

# 1. 停止服务
echo "⏸️  停止服务..."
supervisorctl stop chatbot-api
supervisorctl stop playwright-api

# 2. 备份数据库
echo "💾 备份数据库..."
BACKUP_DIR="/home/$DEPLOY_USER/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cp $DEPLOY_DIR/chatbot.db $BACKUP_DIR/chatbot_backup_$DATE.db
echo "✅ 数据库已备份: chatbot_backup_$DATE.db"

# 3. 更新代码
echo "📥 更新代码..."
cd $DEPLOY_DIR

# 方式1: 从 Git 拉取
if [ -d ".git" ]; then
    su - $DEPLOY_USER -c "cd $DEPLOY_DIR && git pull origin main"
else
    echo "⚠️  未检测到 Git 仓库，请手动上传代码"
    read -p "代码已更新，按回车继续..."
fi

# 4. 更新依赖
echo "📦 更新依赖..."
su - $DEPLOY_USER -c "cd $DEPLOY_DIR && source .venv/bin/activate && pip install -r requirements.txt"

# 5. 清理缓存
echo "🧹 清理 Python 缓存..."
find $DEPLOY_DIR -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find $DEPLOY_DIR -name "*.pyc" -delete 2>/dev/null || true

# 6. 数据库迁移（如果有）
echo "🔄 检查数据库迁移..."
# 如果使用 Alembic，取消注释以下行
# su - $DEPLOY_USER -c "cd $DEPLOY_DIR && source .venv/bin/activate && alembic upgrade head"

# 7. 重启服务
echo "▶️  重启服务..."
supervisorctl start chatbot-api
supervisorctl start playwright-api

# 等待服务启动
sleep 3

# 8. 检查服务状态
echo ""
echo "📊 服务状态:"
supervisorctl status

# 9. 测试服务
echo ""
echo "🧪 测试服务..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/health)

if [ "$HTTP_CODE" == "200" ]; then
    echo "✅ 服务运行正常！"
else
    echo "⚠️  服务返回: $HTTP_CODE"
    echo "请查看日志: sudo tail -f /var/log/supervisor/chatbot-api.err.log"
fi

echo ""
echo "🎉 更新完成！"
echo ""
echo "💡 提示:"
echo "  - 查看日志: sudo tail -f /var/log/supervisor/chatbot-api.out.log"
echo "  - 回滚备份: cp $BACKUP_DIR/chatbot_backup_$DATE.db $DEPLOY_DIR/chatbot.db"
