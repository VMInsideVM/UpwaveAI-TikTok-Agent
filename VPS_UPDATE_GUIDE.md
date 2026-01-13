# VPS 更新部署指南

## 问题

在 VPS 上更新代码后，报告列表加载失败，错误可能是：
- `no such column: reports.share_mode`
- 报告列表显示空白或加载失败

## 原因

本地添加了报告分享功能，数据库结构发生变更，但 VPS 上的数据库还是旧结构。

## 解决方案（3 种方法）

### 🚀 方法 1: 一键迁移（推荐）

最简单快速的方法：

```bash
# 在 VPS 上
cd /root/UpwaveAI-TikTok-Agent

# 更新代码
git pull origin main

# 运行一键迁移脚本
bash migrate.sh
```

脚本会自动：
1. 备份数据库
2. 运行迁移
3. 验证结果

### 🔍 方法 2: 先检查再迁移

如果不确定是否需要迁移，先诊断：

```bash
# 1. 检查数据库结构
python check_db.py

# 如果显示"需要运行数据库迁移"，则执行：
# 2. 运行迁移
python migrations/add_report_sharing_fields.py

# 3. 再次检查验证
python check_db.py
```

### 🛠️ 方法 3: 手动执行 SQL

如果您熟悉 SQL，可以直接执行：

```bash
sqlite3 chatbot.db <<EOF
-- 添加分享功能字段
ALTER TABLE reports ADD COLUMN share_mode VARCHAR(20) DEFAULT 'private' NOT NULL;
ALTER TABLE reports ADD COLUMN share_password VARCHAR(128);
ALTER TABLE reports ADD COLUMN share_expires_at DATETIME;
ALTER TABLE reports ADD COLUMN share_created_at DATETIME;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_reports_share_mode ON reports(share_mode);
CREATE INDEX IF NOT EXISTS idx_reports_share_expires_at ON reports(share_expires_at);

-- 验证
PRAGMA table_info(reports);
EOF
```

## 完整部署流程

### 步骤 1: SSH 连接到 VPS

```bash
ssh root@your-vps-ip
```

### 步骤 2: 停止服务

```bash
cd /root/UpwaveAI-TikTok-Agent

# 如果使用 systemd
sudo systemctl stop chatbot

# 或者直接 kill 进程
pkill -f chatbot_api.py
pkill -f playwright_api.py
```

### 步骤 3: 备份数据库（重要！）

```bash
# 创建带时间戳的备份
cp chatbot.db chatbot.db.backup.$(date +%Y%m%d_%H%M%S)

# 查看备份
ls -lh chatbot.db.backup.*
```

### 步骤 4: 更新代码

```bash
# 拉取最新代码
git pull origin main

# 或者如果您是手动上传文件
# 确保这些新文件都在 VPS 上:
# - migrations/add_report_sharing_fields.py
# - migrations/README.md
# - migrate.sh
# - check_db.py
# - VPS_UPDATE_GUIDE.md
```

### 步骤 5: 检查环境

```bash
# 确保虚拟环境激活
source .venv/bin/activate

# 检查 Python 版本
python --version

# 检查必要的包
pip list | grep -E "sqlalchemy|pydantic"
```

### 步骤 6: 运行数据库迁移

```bash
# 方式 A: 一键脚本（推荐）
bash migrate.sh

# 方式 B: Python 脚本
python migrations/add_report_sharing_fields.py

# 方式 C: 先诊断再迁移
python check_db.py
# 如果需要迁移，再运行:
python migrations/add_report_sharing_fields.py
```

### 步骤 7: 验证迁移

```bash
# 检查数据库结构
python check_db.py

# 应该看到:
# ✅ share_mode
# ✅ share_password
# ✅ share_expires_at
# ✅ share_created_at
```

### 步骤 8: 重启服务

```bash
# 如果使用 systemd
sudo systemctl start chatbot
sudo systemctl status chatbot

# 或者直接启动
# 先启动 Playwright API
python start_api.py &

# 再启动 Chatbot API
python start_chatbot.py &

# 查看进程
ps aux | grep python
```

### 步骤 9: 测试功能

```bash
# 测试 API 是否正常
curl http://localhost:8001/api/health

# 检查日志
tail -f logs/chatbot.log  # 如果有日志文件
```

### 步骤 10: 在浏览器测试

访问您的网站，测试：
1. ✅ 报告列表是否正常加载
2. ✅ 分享按钮是否显示
3. ✅ 分享功能是否正常工作

## 常见问题排查

### 问题 1: 迁移脚本找不到

```bash
# 检查文件是否存在
ls -la migrations/add_report_sharing_fields.py

# 如果不存在，重新下载或从本地上传
```

### 问题 2: 权限问题

```bash
# 给脚本添加执行权限
chmod +x migrate.sh
chmod +x migrations/add_report_sharing_fields.py

# 检查数据库文件权限
ls -la chatbot.db
```

### 问题 3: 数据库被锁定

```bash
# 检查是否有进程在使用数据库
lsof chatbot.db

# 如果有，停止相关进程
pkill -f chatbot
pkill -f playwright
```

### 问题 4: 迁移失败

```bash
# 恢复备份
cp chatbot.db.backup.YYYYMMDD_HHMMSS chatbot.db

# 检查错误日志
python migrations/add_report_sharing_fields.py 2>&1 | tee migration.log
```

### 问题 5: 服务启动失败

```bash
# 检查端口是否被占用
netstat -tuln | grep -E "8000|8001"

# 查看详细错误
python start_chatbot.py

# 检查 .env 配置
cat .env | grep -E "DATABASE|TOKEN"
```

## 回滚方案

如果更新后出现严重问题：

```bash
# 1. 停止服务
sudo systemctl stop chatbot
# 或
pkill -f chatbot

# 2. 恢复数据库备份
cp chatbot.db.backup.YYYYMMDD_HHMMSS chatbot.db

# 3. 回滚代码（如果需要）
git log --oneline -5  # 查看最近提交
git reset --hard <旧的commit-hash>

# 4. 重启服务
sudo systemctl start chatbot
```

## 验证清单

部署完成后，确认以下项目：

- [ ] 数据库备份已创建
- [ ] 迁移脚本运行成功
- [ ] `check_db.py` 显示所有字段存在
- [ ] 服务成功启动
- [ ] 报告列表正常加载
- [ ] 分享功能可以使用
- [ ] 日志没有报错

## 性能优化建议

迁移后，可选的优化：

```bash
# 1. 分析数据库（重建统计信息）
sqlite3 chatbot.db "ANALYZE;"

# 2. 清理数据库
sqlite3 chatbot.db "VACUUM;"

# 3. 检查索引
sqlite3 chatbot.db "SELECT * FROM sqlite_master WHERE type='index';"
```

## 联系支持

如果遇到无法解决的问题：

1. 保存错误日志
2. 保存数据库备份
3. 记录操作步骤
4. 联系技术支持

---

**重要提示**：
- 务必在操作前备份数据库
- 建议在低峰期进行迁移
- 测试环境先验证再上生产
