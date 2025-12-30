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
        如果用户最新的会话是空的（没有消息），则复用该会话

        Args:
            user_id: 用户 ID
            title: 会话标题

        Returns:
            str: 会话 ID
        """
        with get_db_context() as db:
            # 1. 检查最新的会话是否为空
            latest_session = db.query(ChatSession).filter(
                ChatSession.user_id == user_id
            ).order_by(ChatSession.created_at.desc()).first()

            if latest_session:
                # 检查消息数量
                message_count = db.query(Message).filter(
                    Message.session_id == latest_session.session_id
                ).count()

                if message_count == 0:
                    print(f"♻️ 复用已存在的空会话: {latest_session.session_id}")
                    # 更新 update_at 以便它浮动到最上面
                    latest_session.updated_at = datetime.utcnow()
                    db.commit()
                    return latest_session.session_id

            # 2. 如果没有空会话，创建新的
            session = ChatSession(
                user_id=user_id,
                title=title
            )

            print(f"🆕 创建会话对象，UUID: {session.session_id}")

            db.add(session)
            db.commit()
            db.refresh(session)

            print(f"💾 会话已保存到数据库: {session.session_id}")

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

        # 获取会话的 user_id 和 username
        user_info = self._get_session_user_info(session_id)
        user_id = user_info.get('user_id') if user_info else None
        username = user_info.get('username') if user_info else None

        # 创建新 Agent 实例，传递 user_id, session_id 和 username
        agent = TikTokInfluencerAgent(
            user_id=user_id,
            session_id=session_id,
            username=username
        )

        # 加载历史消息
        history = self.get_session_history(session_id, limit=50)
        for msg in history:
            agent.chat_history.append((msg["role"], msg["content"]))

        # 缓存
        self._agent_cache[session_id] = agent

        return agent

    def _get_session_user_info(self, session_id: str) -> Optional[Dict]:
        """获取会话对应的用户信息（user_id 和 username）"""
        try:
            with get_db_context() as db:
                session = db.query(ChatSession).filter(
                    ChatSession.session_id == session_id
                ).first()

                if not session:
                    return None

                # 获取用户信息
                user = db.query(User).filter(User.user_id == session.user_id).first()

                return {
                    'user_id': session.user_id,
                    'username': user.username if user else None
                }
        except Exception as e:
            print(f"❌ 获取会话用户信息失败: {e}")
            return None

    def _get_session_user_id(self, session_id: str) -> Optional[str]:
        """获取会话对应的用户 ID（保留向后兼容）"""
        info = self._get_session_user_info(session_id)
        return info.get('user_id') if info else None

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
        offset: int = 0,
        include_empty: bool = False  # 新增参数：是否包含空会话
    ) -> List[dict]:
        """
        获取用户的所有会话

        Args:
            user_id: 用户 ID
            limit: 限制数量
            offset: 偏移量
            include_empty: 是否包含没有消息的空会话（默认False,不包含）

        Returns:
            List[dict]: 会话列表
        """
        from sqlalchemy import exists, and_
        
        with get_db_context() as db:
            query = db.query(ChatSession).filter(
                ChatSession.user_id == user_id
            )

            # 如果不包含空会话，在 SQL 层面过滤
            if not include_empty:
                stmt = exists().where(Message.session_id == ChatSession.session_id)
                query = query.filter(stmt)

            sessions = query.order_by(
                ChatSession.updated_at.desc()
            ).offset(offset).limit(limit).all()

            result = []
            for session in sessions:
                # 获取消息数量
                message_count = db.query(Message).filter(
                    Message.session_id == session.session_id
                ).count()

                # 获取最后一条消息
                last_message = db.query(Message).filter(
                    Message.session_id == session.session_id
                ).order_by(
                    Message.created_at.desc()
                ).first()

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
        from database.models import Report

        with get_db_context() as db:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()

            if not session:
                return False

            # 删除缓存的 Agent
            if session_id in self._agent_cache:
                del self._agent_cache[session_id]

            # 先删除关联的报告（避免外键约束冲突）
            reports = db.query(Report).filter(
                Report.session_id == session_id
            ).all()

            if reports:
                print(f"🗑️ 删除 {len(reports)} 个关联报告")
                for report in reports:
                    db.delete(report)

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
                print(f"⚠️ 会话 {session_id} 不存在于数据库")
                return False

            has_access = session.user_id == user_id
            if not has_access:
                print(f"⚠️ 权限不匹配: 会话所有者={session.user_id}, 请求用户={user_id}")

            return has_access

    def update_session_title(self, session_id: str, title: str) -> bool:
        """
        更新会话标题

        Args:
            session_id: 会话 ID
            title: 新标题

        Returns:
            bool: 是否成功
        """
        with get_db_context() as db:
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()

            if not session:
                print(f"⚠️ 更新标题失败: 会话 {session_id} 不存在")
                return False

            session.title = title
            db.commit()
            print(f"✅ 会话标题已更新: {session_id} -> {title}")
            return True

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

    def generate_smart_title(self, session_id: str) -> Optional[str]:
        """
        基于对话历史智能生成会话标题（自动处理重复标题）

        Args:
            session_id: 会话 ID

        Returns:
            str: 生成的标题，失败返回 None
        """
        try:
            # 获取会话的前几条消息
            history = self.get_session_history(session_id, limit=10)

            if len(history) < 2:
                # 对话太短，无法生成有意义的标题
                return None

            # 构建对话摘要（用户消息和助手的前几条回复）
            conversation_summary = []
            for msg in history[:6]:  # 只取前6条消息
                role_label = "用户" if msg["role"] == "user" else "助手"
                content = msg["content"][:200]  # 限制长度
                conversation_summary.append(f"{role_label}: {content}")

            summary_text = "\n".join(conversation_summary)

            # 使用 LLM 生成标题
            from langchain_openai import ChatOpenAI
            from dotenv import load_dotenv
            import os

            load_dotenv()

            llm = ChatOpenAI(
                model=os.getenv("OPENAI_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                openai_api_base=os.getenv("OPENAI_BASE_URL"),
                temperature=0.3,
                max_tokens=50
            )

            prompt = f"""请为以下对话生成一个简洁的标题（5-15个字），标题应该概括对话的核心内容。

对话内容：
{summary_text}

要求：
1. 标题要简洁明了，5-15个字
2. 突出商品名称或核心需求
3. 不要包含"对话"、"聊天"等词语
4. 只返回标题文本，不要任何其他内容

标题："""

            response = llm.invoke(prompt)
            base_title = response.content.strip()

            # 清理标题（移除引号、冒号等）
            base_title = base_title.replace('"', '').replace("'", '').replace(':', '').replace('：', '').strip()

            # 长度限制
            if len(base_title) > 30:
                base_title = base_title[:30] + "..."

            if not base_title:
                return None

            # 检查是否有相同标题，添加区分
            final_title = self._make_title_unique(session_id, base_title)

            return final_title

        except Exception as e:
            print(f"⚠️ 智能生成标题失败: {e}")
            return None

    def _make_title_unique(self, current_session_id: str, base_title: str) -> str:
        """
        确保标题唯一，如果有重复则添加序号或时间戳

        Args:
            current_session_id: 当前会话ID（不与自己比较）
            base_title: 基础标题

        Returns:
            str: 唯一的标题
        """
        try:
            with get_db_context() as db:
                # 获取当前会话的用户ID
                current_session = db.query(ChatSession).filter(
                    ChatSession.session_id == current_session_id
                ).first()

                if not current_session:
                    return base_title

                user_id = current_session.user_id

                # 查找该用户的所有会话标题（排除当前会话）
                existing_sessions = db.query(ChatSession).filter(
                    ChatSession.user_id == user_id,
                    ChatSession.session_id != current_session_id
                ).all()

                existing_titles = [s.title for s in existing_sessions]

                # 如果没有重复，直接返回
                if base_title not in existing_titles:
                    return base_title

                # 有重复，尝试添加序号
                # 先检查是否已经有带序号的标题
                import re
                pattern = re.compile(rf"^{re.escape(base_title)}\s*\((\d+)\)$")

                max_number = 1
                for title in existing_titles:
                    match = pattern.match(title)
                    if match:
                        num = int(match.group(1))
                        max_number = max(max_number, num + 1)
                    elif title == base_title:
                        # 原始标题已存在，从(2)开始
                        max_number = max(max_number, 2)

                # 生成新标题
                unique_title = f"{base_title} ({max_number})"

                print(f"🔄 标题重复，已添加序号: {base_title} → {unique_title}")

                return unique_title

        except Exception as e:
            print(f"⚠️ 生成唯一标题失败: {e}")
            # 失败时使用时间戳作为后备方案
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M")
            return f"{base_title} {timestamp}"

    def auto_update_title_if_needed(self, session_id: str):
        """
        如果会话标题仍为默认值且对话已有一定长度，自动生成智能标题

        Args:
            session_id: 会话 ID
        """
        try:
            with get_db_context() as db:
                session = db.query(ChatSession).filter(
                    ChatSession.session_id == session_id
                ).first()

                if not session:
                    return

                # 检查是否需要更新标题
                # 1. 当前标题是默认值（"新对话"）
                # 2. 会话有足够的消息（至少4条：2轮对话）
                if session.title == "新对话":
                    message_count = db.query(Message).filter(
                        Message.session_id == session_id
                    ).count()

                    if message_count >= 4:
                        # 尝试生成智能标题
                        new_title = self.generate_smart_title(session_id)

                        if new_title:
                            session.title = new_title
                            db.commit()
                            print(f"✅ 自动更新会话标题: {new_title}")

        except Exception as e:
            print(f"⚠️ 自动更新标题失败: {e}")


# 全局单例
session_manager = SessionManagerDB()
