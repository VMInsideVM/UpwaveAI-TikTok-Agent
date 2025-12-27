"""
充值套餐配置
Credit Recharge Pricing Configuration
"""

# 充值套餐定义
CREDIT_TIERS = {
    "tier_test": {
        "id": "tier_test",
        "price_yuan": 1,
        "price_fen": 100,  # 支付接口使用分为单位
        "credits": 100,
        "name": "测试套餐",
        "description": "仅供测试使用",
        "popular": False,
        "test_only": True  # 标记为测试套餐
    },
    "tier_299": {
        "id": "tier_299",
        "price_yuan": 299,
        "price_fen": 29900,
        "credits": 1000,
        "name": "基础套餐",
        "description": "适合个人用户",
        "popular": False
    },
    "tier_599": {
        "id": "tier_599",
        "price_yuan": 599,
        "price_fen": 59900,
        "credits": 2000,
        "name": "标准套餐",
        "description": "最受欢迎",
        "popular": True
    },
    "tier_999": {
        "id": "tier_999",
        "price_yuan": 999,
        "price_fen": 99900,
        "credits": 4000,
        "name": "专业套餐",
        "description": "适合企业用户",
        "popular": False
    },
    "tier_1799": {
        "id": "tier_1799",
        "price_yuan": 1799,
        "price_fen": 179900,
        "credits": 8000,
        "name": "企业套餐",
        "description": "最大优惠",
        "popular": False
    }
}

# 订单配置
ORDER_EXPIRATION_MINUTES = 15  # 订单过期时间（分钟）
ORDER_EXPIRATION_SECONDS = ORDER_EXPIRATION_MINUTES * 60

# 订单限制
MAX_PENDING_ORDERS_PER_USER = 3  # 每用户最多同时存在的待支付订单数
MAX_ORDERS_PER_HOUR = 5  # 每用户每小时最多创建订单数

# 对话限制
MAX_ROUNDS_PER_SESSION = 50  # 单个会话最多对话轮数
NEW_CONVERSATIONS_PER_1000_CREDITS = 10  # 基准：1000积分对应每天10个新对话


def calculate_max_daily_conversations(user_credits: int) -> int:
    """
    根据用户积分动态计算每天可创建的最大新对话数

    Args:
        user_credits: 用户当前积分

    Returns:
        每天最多可创建的新对话数

    Example:
        1000 积分 = 10 个对话/天
        2000 积分 = 20 个对话/天
        500 积分 = 5 个对话/天
        100 积分 = 1 个对话/天（最少保证1个）
    """
    if user_credits < 100:
        return 1  # 最少保证1个对话

    return max(1, (user_credits // 100) * (NEW_CONVERSATIONS_PER_1000_CREDITS // 10))

# 支付方式
PAYMENT_METHODS = {
    "alipay": {
        "id": "alipay",
        "name": "支付宝",
        "enabled": True
    },
    "wechat": {
        "id": "wechat",
        "name": "微信支付",
        "enabled": True
    }
}


def get_tier_by_id(tier_id: str) -> dict | None:
    """根据ID获取套餐信息"""
    return CREDIT_TIERS.get(tier_id)


def get_all_tiers() -> list:
    """获取所有套餐列表"""
    return list(CREDIT_TIERS.values())


def validate_tier_id(tier_id: str) -> bool:
    """验证套餐ID是否有效"""
    return tier_id in CREDIT_TIERS


def validate_payment_method(method: str) -> bool:
    """验证支付方式是否有效"""
    return method in PAYMENT_METHODS and PAYMENT_METHODS[method]["enabled"]
