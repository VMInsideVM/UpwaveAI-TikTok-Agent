"""
会话管理模块
用于管理多个用户的聊天会话，每个会话拥有独立的 Agent 实例
支持持久化聊天记录，支持断线恢复
"""

import uuid
import json
import os
from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
from agent import TikTokInfluencerAgent


class SessionManager:
    """管理多个用户会话的管理器，支持持久化存储"""

    def __init__(self, storage_dir: str = "chat_history"):
        """
        初始化会话管理器

        Args:
            storage_dir: 聊天记录存储目录
        """
        self.sessions: Dict[str, dict] = {}
        self.storage_dir = Path(storage_dir)

        # 创建存储目录
        self.storage_dir.mkdir(exist_ok=True)
        print(f"[SessionManager] 聊天记录存储目录: {self.storage_dir.absolute()}")

    def create_session(self) -> str:
        """
        创建新的聊天会话

        Returns:
            str: 会话 ID
        """
        session_id = str(uuid.uuid4())

        # 创建新的 agent 实例
        agent = TikTokInfluencerAgent()

        # 存储会话信息
        self.sessions[session_id] = {
            'agent': agent,
            'created_at': datetime.now(),
            'last_active': datetime.now()
        }

        print(f"[SessionManager] 创建新会话: {session_id}")
        return session_id

    def get_agent(self, session_id: str) -> Optional[TikTokInfluencerAgent]:
        """
        获取指定会话的 agent 实例

        Args:
            session_id: 会话 ID

        Returns:
            TikTokInfluencerAgent 实例，如果会话不存在则返回 None
        """
        session = self.sessions.get(session_id)
        if session:
            # 更新最后活跃时间
            session['last_active'] = datetime.now()
            return session['agent']
        return None

    def delete_session(self, session_id: str) -> bool:
        """
        删除指定会话

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否成功删除
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f"[SessionManager] 删除会话: {session_id}")
            return True
        return False

    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在

        Args:
            session_id: 会话 ID

        Returns:
            bool: 会话是否存在
        """
        return session_id in self.sessions

    def get_session_info(self, session_id: str) -> Optional[dict]:
        """
        获取会话信息（不包含 agent 实例）

        Args:
            session_id: 会话 ID

        Returns:
            dict: 会话信息，包括创建时间和最后活跃时间
        """
        session = self.sessions.get(session_id)
        if session:
            return {
                'session_id': session_id,
                'created_at': session['created_at'].isoformat(),
                'last_active': session['last_active'].isoformat()
            }
        return None

    def get_all_sessions(self) -> list:
        """
        获取所有会话的信息

        Returns:
            list: 所有会话的信息列表
        """
        return [
            {
                'session_id': sid,
                'created_at': info['created_at'].isoformat(),
                'last_active': info['last_active'].isoformat()
            }
            for sid, info in self.sessions.items()
        ]

    def cleanup_inactive_sessions(self, inactive_hours: int = 24) -> int:
        """
        清理不活跃的会话

        Args:
            inactive_hours: 不活跃小时数阈值

        Returns:
            int: 清理的会话数量
        """
        from datetime import timedelta

        now = datetime.now()
        threshold = timedelta(hours=inactive_hours)

        inactive_sessions = [
            sid for sid, info in self.sessions.items()
            if now - info['last_active'] > threshold
        ]

        for sid in inactive_sessions:
            self.delete_session(sid)

        if inactive_sessions:
            print(f"[SessionManager] 清理了 {len(inactive_sessions)} 个不活跃会话")

        return len(inactive_sessions)

    def _get_history_file_path(self, session_id: str) -> Path:
        """
        获取会话历史文件路径

        Args:
            session_id: 会话 ID

        Returns:
            Path: 历史文件路径
        """
        return self.storage_dir / f"{session_id}.json"

    def save_message(self, session_id: str, role: str, content: str, timestamp: Optional[str] = None) -> bool:
        """
        保存单条聊天消息到持久化存储

        Args:
            session_id: 会话 ID
            role: 角色 (user/assistant/system)
            content: 消息内容
            timestamp: 时间戳 (可选，默认使用当前时间)

        Returns:
            bool: 是否成功保存
        """
        try:
            file_path = self._get_history_file_path(session_id)

            # 读取现有历史
            history = []
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)

            # 添加新消息
            message = {
                'role': role,
                'content': content,
                'timestamp': timestamp or datetime.now().isoformat()
            }
            history.append(message)

            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"[SessionManager] 保存消息失败: {e}")
            return False

    def load_chat_history(self, session_id: str) -> List[dict]:
        """
        加载会话的聊天历史

        Args:
            session_id: 会话 ID

        Returns:
            List[dict]: 聊天历史列表，每条消息包含 role, content, timestamp
        """
        try:
            file_path = self._get_history_file_path(session_id)

            if not file_path.exists():
                return []

            with open(file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)

            print(f"[SessionManager] 加载会话 {session_id} 的历史: {len(history)} 条消息")
            return history

        except Exception as e:
            print(f"[SessionManager] 加载聊天历史失败: {e}")
            return []

    def session_has_history(self, session_id: str) -> bool:
        """
        检查会话是否有保存的历史记录

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否存在历史记录
        """
        file_path = self._get_history_file_path(session_id)
        return file_path.exists()

    def clear_session_history(self, session_id: str) -> bool:
        """
        清除会话的聊天历史文件

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否成功清除
        """
        try:
            file_path = self._get_history_file_path(session_id)
            if file_path.exists():
                file_path.unlink()
                print(f"[SessionManager] 清除会话 {session_id} 的历史记录")
                return True
            return False

        except Exception as e:
            print(f"[SessionManager] 清除历史记录失败: {e}")
            return False


# 全局会话管理器实例
session_manager = SessionManager()


if __name__ == "__main__":
    # 测试代码
    print("测试会话管理器...")

    # 创建会话
    session_id1 = session_manager.create_session()
    print(f"创建会话 1: {session_id1}")

    session_id2 = session_manager.create_session()
    print(f"创建会话 2: {session_id2}")

    # 获取 agent
    agent1 = session_manager.get_agent(session_id1)
    print(f"获取会话 1 的 agent: {agent1 is not None}")

    # 获取会话信息
    info = session_manager.get_session_info(session_id1)
    print(f"会话 1 信息: {info}")

    # 获取所有会话
    all_sessions = session_manager.get_all_sessions()
    print(f"当前共有 {len(all_sessions)} 个会话")

    # 删除会话
    success = session_manager.delete_session(session_id1)
    print(f"删除会话 1: {success}")

    # 检查会话是否存在
    exists = session_manager.session_exists(session_id1)
    print(f"会话 1 是否存在: {exists}")

    print("\n测试完成！")
