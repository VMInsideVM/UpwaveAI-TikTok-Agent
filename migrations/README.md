# 数据库迁移说明

## 问题

当您在本地添加了报告分享功能后，VPS 上的数据库结构与新代码不匹配，导致报告加载失败。

## 原因

新功能在 `reports` 表中添加了 4 个新字段：
- `share_mode` - 分享模式 (private/public/password)
- `share_password` - 分享密码（加密存储）
- `share_expires_at` - 分享过期时间
- `share_created_at` - 分享创建时间

VPS 上的旧数据库没有这些字段，导致代码报错。

## 解决方案

在 VPS 上运行数据库迁移脚本。

### 步骤 1: 备份数据库（重要！）

```bash
# 在 VPS 上
cd /root/UpwaveAI-TikTok-Agent
cp chatbot.db chatbot.db.backup.$(date +%Y%m%d_%H%M%S)
```

### 步骤 2: 更新代码

```bash
# 拉取最新代码
git pull origin main

# 或者如果是直接复制的文件
# 确保 migrations/ 文件夹也被复制过来
```

### 步骤 3: 运行迁移脚本

```bash
# 方法 1: 使用默认数据库路径 (chatbot.db)
python migrations/add_report_sharing_fields.py

# 方法 2: 指定数据库路径
python migrations/add_report_sharing_fields.py /path/to/chatbot.db
```

### 步骤 4: 验证迁移

脚本会自动验证迁移结果。您应该看到：

```
✅ 迁移完成! 共添加 4 个字段
✅ 所有字段都已正确添加!
```

### 步骤 5: 重启服务

```bash
# 重启聊天机器人服务
# 如果使用 systemd
sudo systemctl restart chatbot

# 或者如果直接运行
pkill -f chatbot_api.py
python start_chatbot.py
```

## 迁移脚本功能

- ✅ 自动检测数据库结构
- ✅ 只添加缺失的字段（幂等操作）
- ✅ 创建必要的索引
- ✅ 验证迁移结果
- ✅ 安全回滚机制

## 常见问题

### Q: 迁移会删除现有数据吗？
A: 不会。迁移只是添加新字段，不会修改或删除现有数据。

### Q: 可以重复运行迁移脚本吗？
A: 可以。脚本会检查字段是否已存在，已存在的字段会被跳过。

### Q: 如果迁移失败怎么办？
A: 恢复备份：
```bash
cp chatbot.db.backup.YYYYMMDD_HHMMSS chatbot.db
```

### Q: 如何检查当前数据库结构？
A: 使用 SQLite 命令：
```bash
sqlite3 chatbot.db "PRAGMA table_info(reports);"
```

## 技术细节

迁移执行的 SQL 语句：

```sql
-- 添加字段
ALTER TABLE reports ADD COLUMN share_mode VARCHAR(20) DEFAULT 'private' NOT NULL;
ALTER TABLE reports ADD COLUMN share_password VARCHAR(128);
ALTER TABLE reports ADD COLUMN share_expires_at DATETIME;
ALTER TABLE reports ADD COLUMN share_created_at DATETIME;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_reports_share_mode ON reports(share_mode);
CREATE INDEX IF NOT EXISTS idx_reports_share_expires_at ON reports(share_expires_at);
```

## 未来的迁移

如果将来还有数据库结构变更，可以：

1. 创建新的迁移脚本（按时间戳命名）
2. 在 `migrations/` 文件夹中添加脚本
3. 按顺序运行所有未执行的迁移

建议使用版本号管理迁移：
- `001_add_report_sharing_fields.py` ✅ (当前)
- `002_add_xxx_feature.py` (未来)
- `003_add_yyy_feature.py` (未来)
