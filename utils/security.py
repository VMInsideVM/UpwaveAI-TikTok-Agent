"""
安全工具模块
Security Utilities
"""
import re
from datetime import datetime, timedelta
from typing import Optional, List
import hashlib


class RateLimiter:
    """内存中的简单限流器（生产环境建议使用Redis）"""

    def __init__(self):
        self._storage = {}  # {key: [(timestamp, count), ...]}

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, Optional[int]]:
        """
        检查是否超过限流

        Args:
            key: 限流键（如IP地址、用户ID）
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）

        Returns:
            (是否允许, 剩余可用次数)
        """
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)

        # 清理过期记录
        if key in self._storage:
            self._storage[key] = [
                (ts, count) for ts, count in self._storage[key]
                if ts > window_start
            ]
        else:
            self._storage[key] = []

        # 计算当前窗口内的请求数
        current_count = sum(count for _, count in self._storage[key])

        if current_count >= max_requests:
            return False, 0

        # 记录本次请求
        self._storage[key].append((now, 1))

        remaining = max_requests - current_count - 1
        return True, remaining

    def cleanup_old_entries(self, max_age_hours: int = 24):
        """清理旧数据"""
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        for key in list(self._storage.keys()):
            self._storage[key] = [
                (ts, count) for ts, count in self._storage[key]
                if ts > cutoff
            ]
            if not self._storage[key]:
                del self._storage[key]


class ContentModerator:
    """内容审核器（本地关键词过滤）"""

    # 敏感词库（示例，实际应该更完善）
    BLOCKED_KEYWORDS = {
        # 政治敏感
        "六四", "法轮功", "天安门",
        # 色情暴力
        "色情", "黄色", "暴力", "血腥",
        # 违法犯罪
        "毒品", "走私", "诈骗", "洗钱", "赌博",
        # 其他
        "自杀", "恐怖主义", "炸弹"
    }

    # Prompt注入检测模式
    PROMPT_INJECTION_PATTERNS = [
        r"忽略.*(?:之前|以上|前面).*(?:指令|规则|要求)",
        r"ignore.*(?:previous|above|prior).*(?:instruction|rule|prompt)",
        r"你现在是.*(?:不再是|改为)",
        r"you are now.*(?:no longer|instead)",
        r"system[:：]\s*",
        r"<\|.*\|>",  # 特殊标记
        r"```.*system.*```",  # 系统提示注入
        r"重置.*(?:角色|身份|设定)",
        r"扮演.*(?:黑客|攻击者)",
    ]

    def check_content(self, text: str) -> tuple[bool, Optional[str]]:
        """
        检查内容是否合规

        Returns:
            (是否通过, 违规原因)
        """
        if not text:
            return True, None

        text_lower = text.lower()

        # 检查敏感词
        for keyword in self.BLOCKED_KEYWORDS:
            if keyword.lower() in text_lower:
                return False, f"内容包含敏感词: {keyword}"

        return True, None

    def detect_prompt_injection(self, text: str) -> tuple[bool, Optional[str]]:
        """
        检测Prompt注入攻击

        Returns:
            (是否检测到注入, 检测原因)
        """
        if not text:
            return False, None

        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True, f"检测到可疑的Prompt注入模式"

        # 检测异常长的单句（可能是注入）
        sentences = re.split(r'[。！？.!?]', text)
        for sentence in sentences:
            if len(sentence) > 500:
                return True, "检测到异常长的句子"

        return False, None


class TokenMonitor:
    """Token消耗监控"""

    def __init__(self):
        self._user_usage = {}  # {user_id: [(timestamp, token_count), ...]}

    def record_usage(self, user_id: str, token_count: int):
        """记录Token使用"""
        now = datetime.utcnow()

        if user_id not in self._user_usage:
            self._user_usage[user_id] = []

        self._user_usage[user_id].append((now, token_count))

        # 只保留最近24小时的记录
        cutoff = now - timedelta(hours=24)
        self._user_usage[user_id] = [
            (ts, count) for ts, count in self._user_usage[user_id]
            if ts > cutoff
        ]

    def check_anomaly(
        self,
        user_id: str,
        current_tokens: int,
        single_threshold: int = 10000,
        hourly_threshold: int = 50000
    ) -> tuple[bool, Optional[str]]:
        """
        检测Token消耗异常

        Args:
            user_id: 用户ID
            current_tokens: 当前请求Token数
            single_threshold: 单次请求阈值
            hourly_threshold: 每小时阈值

        Returns:
            (是否异常, 异常原因)
        """
        # 检查单次消耗
        if current_tokens > single_threshold:
            return True, f"单次对话Token消耗过高: {current_tokens} (阈值: {single_threshold})"

        # 检查小时消耗
        if user_id in self._user_usage:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            hourly_usage = sum(
                count for ts, count in self._user_usage[user_id]
                if ts > hour_ago
            )

            if hourly_usage + current_tokens > hourly_threshold:
                return True, f"每小时Token消耗过高: {hourly_usage + current_tokens} (阈值: {hourly_threshold})"

        return False, None


def get_client_ip(request) -> str:
    """获取客户端真实IP"""
    # 尝试从代理头获取
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # 直接连接IP
    if hasattr(request.client, 'host'):
        return request.client.host

    return "unknown"


def generate_device_fingerprint(request) -> str:
    """生成设备指纹（简化版）"""
    user_agent = request.headers.get("User-Agent", "")
    accept = request.headers.get("Accept", "")
    accept_language = request.headers.get("Accept-Language", "")
    accept_encoding = request.headers.get("Accept-Encoding", "")

    # 组合特征
    fingerprint_data = f"{user_agent}|{accept}|{accept_language}|{accept_encoding}"

    # 生成哈希
    return hashlib.md5(fingerprint_data.encode()).hexdigest()


# 全局实例
rate_limiter = RateLimiter()
content_moderator = ContentModerator()
token_monitor = TokenMonitor()
