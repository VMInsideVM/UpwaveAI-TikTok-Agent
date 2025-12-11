"""
Database-Backed Session Manager
数据库支持的会话管理器（替换内存版本）
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid

from database.connection import get_db_context
from database.models import ChatSession, Message, User
from agent import TikTokInfluencerAgent


class SessionManagerDB:
    """数据库支持的会话管理器"""

    def __init__(self):
        # 内存缓存 Agent 实例（用于性能）
        self._agent_cache: Dict[str, TikTokInfluencerAgent] = {}

    def create_session(self, user_id: str, title: str = "新对话") -> str:
        """
        创建新会话

        Args:
            user_id: 用户 ID
            title: 会话标题

        Returns:
            str: 会话 ID
        """
        with get_db_context() as db:
            session = ChatSession(
                user_id=user_id,
                title=title
            )

            db.add(session)
            db.commit()
            db.refresh(session)

            return session.session_id

    def get_agent(self, session_id: str) -> TikTokInfluencerAgent:
        """
        获取会话的 Agent 实例

        Args:
            session_id: 会话 ID

        Returns:
            TikTokInfluencerAgent: Agent 实例
        """
        # 从缓存获取
        if session_id in self._agent_cache:
            return self._agent_cache[session_id]

        # 创建新 Agent 实例
        agent = TikTokInfluencerAgent()

        # 加载历史消息
        history = self.get_session_history(session_id, limit=50)
        for msg in history:
            agent.chat_history.append((msg["role"], msg["content"]))

        # 缓存
        self._agent_cache[session_id] = agent

        return agent

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        attachments: Optional[dict] = None,
        metadata: Optional[dict] = None
    ):
        """
        保存消息到数据库

        Args:
            session_id: 会话 ID
            role: 角色（user/assistant）
            content: 消息内容
            message_type: 消息类型
            attachments: 附件信息
            metadata: 元数据
        """
        with get_db_context() as db:
            message = Message(
                session_id=session_id,
                role=role,
                content=content,
                message_type=message_type,
                attachments=attachments,
                meta_data=metadata
            )

            db.add(message)

            # 更新会话的 updated_at
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()

            if session:
                session.updated_at = datetime.utcnow()

            db.commit()

    def get_session_history(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """
        获取会话历史

        Args:
            session_id: 会话 ID
            limit: 限制数量
            offset: 偏移量

        Returns:
            List[dict]: 消息列表
        """
        with get_db_context() as db:
            messages = db.query(Message).filter(
                Message.session_id == session_id
            ).order_by(
                Message.created_at
            ).offset(offset).limit(limit).all()

            return [
                {
                    "message_id": msg.message_id,
                    "role": msg.role,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "created_at": msg.created_at.isoformat(),
                    "attachments": msg.attachments,
                    "metadata": msg.meta_data
                }
                for msg in messages
            ]

    def get_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[dict]:
        """
        获取用户的所有会话

        Args:
            user_id: 用户 ID
            limit: 限制数量
            offset: 偏移量

        Returns:
            List[dict]: 会话列表
        """
        with get_db_context() as db:
            sessions = db.query(ChatSession).filter(
                ChatSession.user_id == user_id
            ).order_by(
                ChatSession.updated_at.desc()
            ).offset(offset).limit(limit).all()

            result = []
            for session in sessions:
                # 获取最后一条消息
                last_message = db.query(Message).filter(
                    Message.session_id == session.session_id
                ).order_by(
                    Message.created_at.desc()
                ).first()

                # 计算消息数量
                message_count = db.query(Message).filter(
                    Message.session_id == session.session_id
                ).count()

                result.append({
                    "session_id": session.session_id,
                    "title": session.title,
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "message_count": message_count,
                    "last_message": last_message.content[:100] if last_message else None
                })

            return result

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否成功
        """
        with get_db_context() as db:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()

            if not session:
                return False

            # 删除缓存的 Agent
            if session_id in self._agent_cache:
                del self._agent_cache[session_id]

            # 删除会话（级联删除消息）
            db.delete(session)
            db.commit()

            return True

    def verify_session_access(self, session_id: str, user_id: str) -> bool:
        """
        验证用户是否有权访问会话

        Args:
            session_id: 会话 ID
            user_id: 用户 ID

        Returns:
            bool: 是否有权访问
        """
        with get_db_context() as db:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()

            if not session:
                return False

            return session.user_id == user_id

    def update_session_title(self, session_id: str, title: str):
        """
        更新会话标题

        Args:
            session_id: 会话 ID
            title: 新标题
        """
        with get_db_context() as db:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()

            if session:
                session.title = title
                db.commit()

    def update_session_metadata(self, session_id: str, metadata: dict):
        """
        更新会话元数据

        Args:
            session_id: 会话 ID
            metadata: 元数据
        """
        with get_db_context() as db:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()

            if session:
                session.meta_data = metadata
                db.commit()

    def cleanup_inactive_sessions(self, days: int = 30):
        """
        清理不活跃的会话（从缓存中）

        Args:
            days: 天数阈值
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        with get_db_context() as db:
            inactive_sessions = db.query(ChatSession).filter(
                ChatSession.updated_at < cutoff_date
            ).all()

            # 从缓存中删除
            for session in inactive_sessions:
                if session.session_id in self._agent_cache:
                    del self._agent_cache[session.session_id]

        print(f"✅ 已清理 {len(inactive_sessions)} 个不活跃会话的缓存")


# 全局单例
session_manager = SessionManagerDB()
