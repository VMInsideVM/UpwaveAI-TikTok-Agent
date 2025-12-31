#!/bin/bash

# ============================================
# Playwright API 端口 8000 冲突调试脚本
# ============================================

set -e

echo "🔍 开始诊断 Playwright API 端口 8000 冲突问题..."
echo ""

# 1. 检查端口占用情况
echo "======================================"
echo "1️⃣  检查端口 8000 占用情况"
echo "======================================"
echo ""
echo "【使用 lsof 检查】"
sudo lsof -i :8000 || echo "❌ 端口 8000 未被占用（或 lsof 未找到进程）"
echo ""
echo "【使用 netstat 检查】"
sudo netstat -tlnp | grep 8000 || echo "❌ 端口 8000 未被占用"
echo ""

# 2. 检查 Supervisor 配置文件
echo "======================================"
echo "2️⃣  检查 Supervisor 配置文件"
echo "======================================"
echo ""
echo "【查找所有包含 playwright 的配置】"
ls -la /etc/supervisor/conf.d/ | grep -E "(playwright|api)" || echo "未找到相关配置"
echo ""
echo "【检查是否有重复配置】"
find /etc/supervisor/conf.d/ -name "*playwright*" -o -name "*api*"
echo ""

# 3. 检查运行中的进程
echo "======================================"
echo "3️⃣  检查运行中的 Playwright/Uvicorn 进程"
echo "======================================"
echo ""
ps aux | grep -E "playwright_api|uvicorn" | grep -v grep || echo "❌ 未找到相关进程"
echo ""

# 4. 检查 Supervisor 服务状态
echo "======================================"
echo "4️⃣  检查 Supervisor 服务状态"
echo "======================================"
echo ""
sudo supervisorctl status
echo ""

# 5. 查看最近的 Supervisor 日志
echo "======================================"
echo "5️⃣  查看 Supervisor 主日志（最近 30 行）"
echo "======================================"
echo ""
sudo tail -30 /var/log/supervisor/supervisord.log | grep -E "(playwright|ERROR|spawned)" || sudo tail -30 /var/log/supervisor/supervisord.log
echo ""

# 6. 查看 Playwright API 错误日志
echo "======================================"
echo "6️⃣  查看 Playwright API 错误日志（最近 30 行）"
echo "======================================"
echo ""
sudo tail -30 /var/log/supervisor/playwright-api.err.log
echo ""

# 7. 查看 Playwright API 输出日志
echo "======================================"
echo "7️⃣  查看 Playwright API 输出日志（最近 30 行）"
echo "======================================"
echo ""
sudo tail -30 /var/log/supervisor/playwright-api.out.log
echo ""

# 8. 检查 Chrome CDP 是否正常运行
echo "======================================"
echo "8️⃣  检查 Chrome CDP (端口 9224)"
echo "======================================"
echo ""
echo "【检查端口 9224】"
sudo netstat -tlnp | grep 9224 || echo "❌ Chrome CDP 端口 9224 未监听"
echo ""
echo "【检查 Chrome 进程】"
ps aux | grep -E "chromium|chrome" | grep -v grep || echo "❌ 未找到 Chrome 进程"
echo ""

# 9. 建议的修复步骤
echo ""
echo "======================================"
echo "📋 诊断完成！建议的修复步骤："
echo "======================================"
echo ""
echo "如果发现端口被占用，执行以下命令："
echo ""
echo "  # 方案 1: 强制释放端口 8000"
echo "  sudo fuser -k 8000/tcp"
echo "  sudo supervisorctl restart playwright-api"
echo ""
echo "  # 方案 2: 重启所有服务"
echo "  sudo supervisorctl stop all"
echo "  sudo fuser -k 8000/tcp"
echo "  sudo supervisorctl start all"
echo ""
echo "  # 方案 3: 手动启动测试（查看完整错误）"
echo "  sudo supervisorctl stop playwright-api"
echo "  sudo fuser -k 8000/tcp"
echo "  cd /root/UpwaveAI-TikTok-Agent"
echo "  source .venv/bin/activate"
echo "  python playwright_api.py"
echo ""
echo "  # 方案 4: 重新加载 Supervisor 配置"
echo "  sudo supervisorctl stop all"
echo "  sudo supervisorctl reload"
echo "  sudo supervisorctl start all"
echo ""
