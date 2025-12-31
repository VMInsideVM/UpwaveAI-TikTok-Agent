#!/bin/bash

# 服务监控脚本
# 显示服务状态、日志和系统资源

DEPLOY_DIR="/home/upwaveai/UpwaveAI-TikTok-Agent"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

clear

echo -e "${BLUE}====================================${NC}"
echo -e "${BLUE}  UpwaveAI 服务监控面板  ${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""

# 1. 服务状态
echo -e "${GREEN}📊 服务状态${NC}"
echo "-----------------------------------"
supervisorctl status
echo ""

# 2. 系统资源
echo -e "${GREEN}💻 系统资源${NC}"
echo "-----------------------------------"
echo "CPU 使用率:"
top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}'

echo ""
echo "内存使用:"
free -h | grep Mem | awk '{print "  已用: " $3 " / 总计: " $2 " (" int($3/$2 * 100) "%)"}'

echo ""
echo "磁盘使用:"
df -h / | tail -1 | awk '{print "  已用: " $3 " / 总计: " $2 " (" $5 ")"}'
echo ""

# 3. 数据库大小
echo -e "${GREEN}💾 数据库信息${NC}"
echo "-----------------------------------"
if [ -f "$DEPLOY_DIR/chatbot.db" ]; then
    DB_SIZE=$(du -h $DEPLOY_DIR/chatbot.db | cut -f1)
    echo "数据库大小: $DB_SIZE"

    # 统计数据
    USERS=$(sqlite3 $DEPLOY_DIR/chatbot.db "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "N/A")
    SESSIONS=$(sqlite3 $DEPLOY_DIR/chatbot.db "SELECT COUNT(*) FROM chat_sessions;" 2>/dev/null || echo "N/A")
    MESSAGES=$(sqlite3 $DEPLOY_DIR/chatbot.db "SELECT COUNT(*) FROM messages;" 2>/dev/null || echo "N/A")
    REPORTS=$(sqlite3 $DEPLOY_DIR/chatbot.db "SELECT COUNT(*) FROM reports;" 2>/dev/null || echo "N/A")

    echo "用户数: $USERS"
    echo "会话数: $SESSIONS"
    echo "消息数: $MESSAGES"
    echo "报告数: $REPORTS"
else
    echo "数据库文件不存在"
fi
echo ""

# 4. Nginx 状态
echo -e "${GREEN}🌐 Nginx 状态${NC}"
echo "-----------------------------------"
systemctl is-active --quiet nginx && echo "✅ Nginx 运行中" || echo "❌ Nginx 未运行"
echo ""

# 5. 最近错误日志
echo -e "${GREEN}📝 最近错误日志 (最后 10 行)${NC}"
echo "-----------------------------------"
echo -e "${YELLOW}Chatbot API:${NC}"
tail -10 /var/log/supervisor/chatbot-api.err.log 2>/dev/null || echo "无错误日志"
echo ""

echo -e "${YELLOW}Playwright API:${NC}"
tail -10 /var/log/supervisor/playwright-api.err.log 2>/dev/null || echo "无错误日志"
echo ""

# 6. 最近访问日志
echo -e "${GREEN}🔍 最近访问 (最后 5 条)${NC}"
echo "-----------------------------------"
tail -5 /var/log/nginx/agent.upwaveai.com.access.log 2>/dev/null || echo "无访问日志"
echo ""

# 7. 实时日志选项
echo -e "${BLUE}====================================${NC}"
echo "💡 查看实时日志:"
echo "  1) sudo tail -f /var/log/supervisor/chatbot-api.out.log"
echo "  2) sudo tail -f /var/log/supervisor/playwright-api.out.log"
echo "  3) sudo tail -f /var/log/nginx/agent.upwaveai.com.access.log"
echo "  4) sudo tail -f /var/log/nginx/agent.upwaveai.com.error.log"
echo ""

# 8. 快捷操作
echo "🔧 快捷操作:"
echo "  重启服务: sudo supervisorctl restart all"
echo "  重启 Nginx: sudo systemctl restart nginx"
echo "  查看服务: sudo supervisorctl status"
echo -e "${BLUE}====================================${NC}"
