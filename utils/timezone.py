"""
时区工具模块
Timezone Utilities

统一系统时间处理，使用东八区（中国标准时间 UTC+8）
"""
from datetime import datetime, timedelta, timezone


# 东八区时区对象
CHINA_TZ = timezone(timedelta(hours=8))


def now() -> datetime:
    """
    获取当前东八区时间（带时区信息）

    Returns:
        datetime: 当前东八区时间
    """
    return datetime.now(CHINA_TZ)


def now_naive() -> datetime:
    """
    获取当前东八区时间（不带时区信息，用于数据库存储）

    Returns:
        datetime: 当前东八区时间（naive datetime）
    """
    return datetime.now(CHINA_TZ).replace(tzinfo=None)


def today_start() -> datetime:
    """
    获取今日0点（东八区，不带时区信息）

    Returns:
        datetime: 今日0点时间
    """
    return now_naive().replace(hour=0, minute=0, second=0, microsecond=0)


def today_end() -> datetime:
    """
    获取今日23:59:59（东八区，不带时区信息）

    Returns:
        datetime: 今日结束时间
    """
    return now_naive().replace(hour=23, minute=59, second=59, microsecond=999999)


def utc_to_china(utc_time: datetime) -> datetime:
    """
    将UTC时间转换为东八区时间

    Args:
        utc_time: UTC时间（可以带或不带时区信息）

    Returns:
        datetime: 东八区时间（不带时区信息）
    """
    if utc_time.tzinfo is None:
        # 假设是UTC时间
        utc_time = utc_time.replace(tzinfo=timezone.utc)

    china_time = utc_time.astimezone(CHINA_TZ)
    return china_time.replace(tzinfo=None)


def china_to_utc(china_time: datetime) -> datetime:
    """
    将东八区时间转换为UTC时间

    Args:
        china_time: 东八区时间（可以带或不带时区信息）

    Returns:
        datetime: UTC时间（不带时区信息）
    """
    if china_time.tzinfo is None:
        # 假设是东八区时间
        china_time = china_time.replace(tzinfo=CHINA_TZ)

    utc_time = china_time.astimezone(timezone.utc)
    return utc_time.replace(tzinfo=None)


# 兼容旧代码的别名
def get_china_time() -> datetime:
    """获取当前东八区时间（不带时区信息）"""
    return now_naive()


if __name__ == "__main__":
    # 测试代码
    print("当前东八区时间（带时区）:", now())
    print("当前东八区时间（不带时区）:", now_naive())
    print("今日0点:", today_start())
    print("今日结束:", today_end())

    # 测试转换
    utc_now = datetime.utcnow()
    print(f"\nUTC时间: {utc_now}")
    print(f"转换为东八区: {utc_to_china(utc_now)}")

    china_now = now_naive()
    print(f"\n东八区时间: {china_now}")
    print(f"转换为UTC: {china_to_utc(china_now)}")
