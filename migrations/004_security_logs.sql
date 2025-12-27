-- 安全日志和风控表
-- Security Logs and Risk Control Tables

-- 安全事件日志表
CREATE TABLE IF NOT EXISTS security_logs (
    log_id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),
    event_type VARCHAR(50) NOT NULL,  -- 'rate_limit', 'content_violation', 'prompt_injection', 'token_anomaly', 'suspicious_order', 'refund_abuse'
    severity VARCHAR(20) NOT NULL,  -- 'low', 'medium', 'high', 'critical'
    ip_address VARCHAR(45),
    device_fingerprint VARCHAR(64),
    event_details JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- 用户风险评分表
CREATE TABLE IF NOT EXISTS user_risk_scores (
    user_id VARCHAR(36) PRIMARY KEY,
    risk_score INTEGER DEFAULT 0,  -- 0-100，越高越危险
    violation_count INTEGER DEFAULT 0,
    last_violation_at TIMESTAMP,
    is_blocked BOOLEAN DEFAULT FALSE,
    blocked_until TIMESTAMP,
    blocked_reason TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- IP黑名单表
CREATE TABLE IF NOT EXISTS ip_blacklist (
    ip_address VARCHAR(45) PRIMARY KEY,
    reason TEXT NOT NULL,
    blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    created_by VARCHAR(36),
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

-- 设备黑名单表
CREATE TABLE IF NOT EXISTS device_blacklist (
    device_fingerprint VARCHAR(64) PRIMARY KEY,
    reason TEXT NOT NULL,
    blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    created_by VARCHAR(36),
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_security_logs_user ON security_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_security_logs_type ON security_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_security_logs_created ON security_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_user_risk_blocked ON user_risk_scores(is_blocked);
