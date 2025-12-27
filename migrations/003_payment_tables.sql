-- 充值订单和退款表迁移脚本
-- 创建时间: 2025-12-26

-- =====================================================
-- 1. 创建充值订单表
-- =====================================================
CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(36) PRIMARY KEY,
    order_no VARCHAR(32) UNIQUE NOT NULL,
    user_id VARCHAR(36) NOT NULL,

    -- 套餐信息
    tier_id VARCHAR(20) NOT NULL,
    amount_yuan INTEGER NOT NULL,
    credits INTEGER NOT NULL,

    -- 支付信息
    payment_method VARCHAR(20) NOT NULL,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- 第三方支付信息
    trade_no VARCHAR(64),
    qr_code_url TEXT,

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP,
    expired_at TIMESTAMP,

    -- 元数据
    meta_data JSON,

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 订单索引
CREATE INDEX IF NOT EXISTS idx_orders_order_no ON orders(order_no);
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_payment_status ON orders(payment_status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);

-- =====================================================
-- 2. 创建退款记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS refunds (
    refund_id VARCHAR(36) PRIMARY KEY,
    order_id VARCHAR(36) NOT NULL,

    -- 退款信息
    refund_no VARCHAR(32) UNIQUE NOT NULL,
    refund_amount_yuan INTEGER NOT NULL,
    refund_credits INTEGER NOT NULL,

    -- 状态
    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- 原因和审批
    reason TEXT NOT NULL,
    admin_id VARCHAR(36),

    -- 第三方退款信息
    refund_trade_no VARCHAR(64),
    error_message TEXT,

    -- 时间戳
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,

    -- 元数据
    meta_data JSON,

    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- 退款索引
CREATE INDEX IF NOT EXISTS idx_refunds_refund_no ON refunds(refund_no);
CREATE INDEX IF NOT EXISTS idx_refunds_order_id ON refunds(order_id);
CREATE INDEX IF NOT EXISTS idx_refunds_status ON refunds(status);
CREATE INDEX IF NOT EXISTS idx_refunds_created_at ON refunds(created_at);

-- =====================================================
-- 3. 修改积分变动历史表（添加订单关联）
-- =====================================================
-- 添加 related_order_id 列（如果不存在）
-- SQLite 不支持 ADD COLUMN IF NOT EXISTS，需要用 try-catch 方式或手动检查
ALTER TABLE credit_history ADD COLUMN related_order_id VARCHAR(36) REFERENCES orders(order_id) ON DELETE SET NULL;

-- 注释
-- orders.payment_status 可选值: 'pending'(待支付), 'paid'(已支付), 'cancelled'(已取消), 'refunded'(已退款), 'partial_refunded'(部分退款)
-- orders.payment_method 可选值: 'alipay'(支付宝), 'wechat'(微信支付)
-- orders.tier_id 可选值: 'tier_299', 'tier_599', 'tier_999', 'tier_1799'
-- refunds.status 可选值: 'pending'(待处理), 'processing'(处理中), 'success'(成功), 'failed'(失败)
-- credit_history.change_type 新增值: 'recharge'(充值), 'refund_deduct'(退款扣除)
