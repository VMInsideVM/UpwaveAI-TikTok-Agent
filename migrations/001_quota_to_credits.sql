-- 数据库迁移: 从配额制改为积分制
-- 创建时间: 2025-12-18
-- 说明: 将 user_usage 表的字段从 quota 改为 credits

-- 1. 重命名字段 (SQLite 不支持直接重命名列，需要重建表)
-- 备份原表
CREATE TABLE IF NOT EXISTS user_usage_backup AS SELECT * FROM user_usage;

-- 删除原表
DROP TABLE IF EXISTS user_usage;

-- 创建新表结构
CREATE TABLE user_usage (
    usage_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    total_credits INTEGER NOT NULL DEFAULT 300,  -- 总积分（从 total_quota 改名）
    used_credits INTEGER NOT NULL DEFAULT 0,     -- 已使用积分（从 used_count 改名）
    last_reset_date TIMESTAMP,                   -- 保留字段
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_user_usage_user_id ON user_usage(user_id);

-- 2. 迁移数据（将旧的配额数据转换为积分）
-- 策略：1次配额 = 300积分（可查询10个达人）
INSERT INTO user_usage (usage_id, user_id, total_credits, used_credits, last_reset_date)
SELECT
    usage_id,
    user_id,
    total_quota * 300 AS total_credits,  -- 1次 = 300积分
    used_count * 300 AS used_credits,    -- 已使用次数也按300积分换算
    last_reset_date
FROM user_usage_backup;

-- 3. 验证迁移
SELECT COUNT(*) as total_users FROM user_usage;
SELECT
    user_id,
    total_credits,
    used_credits,
    (total_credits - used_credits) as remaining_credits
FROM user_usage
LIMIT 5;

-- 4. 清理备份表（可选，保留以防回滚）
-- DROP TABLE IF EXISTS user_usage_backup;

COMMIT;
