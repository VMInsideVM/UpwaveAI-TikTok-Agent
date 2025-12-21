-- 积分变动历史表迁移脚本
-- 创建时间: 2025-12-19

-- 创建积分变动历史表
CREATE TABLE IF NOT EXISTS credit_history (
    history_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    change_type VARCHAR(20) NOT NULL,
    amount INTEGER NOT NULL,
    before_credits INTEGER NOT NULL,
    after_credits INTEGER NOT NULL,
    reason VARCHAR(200),
    related_report_id VARCHAR(36),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSON,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (related_report_id) REFERENCES reports(report_id) ON DELETE SET NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_credit_history_user_id ON credit_history(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_history_change_type ON credit_history(change_type);
CREATE INDEX IF NOT EXISTS idx_credit_history_created_at ON credit_history(created_at);

-- 注释
-- change_type 可选值: 'add'(充值), 'deduct'(扣除), 'refund'(退还)
-- amount: 正数表示增加，负数表示扣除
