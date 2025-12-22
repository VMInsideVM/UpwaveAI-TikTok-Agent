
"""
Token Tracking Service
用于追踪和记录 LangChain/LangSmith 的 Token 消耗
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from database.connection import get_db_context
from database.models import TokenUsage, UserUsage, User

logger = logging.getLogger(__name__)

class TokenTrackingCallbackHandler(BaseCallbackHandler):
    """
    自定义回调处理器，用于捕获 LLM Token 使用情况并保存到数据库
    """
    
    def __init__(self, user_id: str, session_id: Optional[str] = None):
        self.user_id = user_id
        self.session_id = session_id
        
    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> Any:
        """LLM 开始运行时调用"""
        pass

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> Any:
        """LLM 结束运行时调用（成功）"""
        try:
            # 提取 Token 使用信息
            # OpenAI/LangChain 通常在 llm_output['token_usage'] 中返回
            if not response.llm_output:
                return

            token_usage = response.llm_output.get("token_usage", {})
            if not token_usage:
                # 尝试从 generation info 中获取 (有些模型返回位置不同)
                # 但通常 llm_output 是标准位置
                return

            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)
            model_name = response.llm_output.get("model_name", "unknown")

            if total_tokens > 0:
                self._save_token_usage(prompt_tokens, completion_tokens, total_tokens, model_name)
                
        except Exception as e:
            logger.error(f"❌ 保存 Token 使用记录失败: {e}", exc_info=True)

    def _save_token_usage(self, prompt_tokens: int, completion_tokens: int, total_tokens: int, model_name: str):
        """保存到数据库"""
        try:
            with get_db_context() as db:
                # 1. 记录详细日志
                usage_record = TokenUsage(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    model_name=model_name,
                    created_at=datetime.utcnow()
                )
                db.add(usage_record)
                
                # 2. 更新用户总消耗
                user_usage = db.query(UserUsage).filter(UserUsage.user_id == self.user_id).first()
                if user_usage:
                    # 确保字段不是 None
                    if user_usage.total_tokens_used is None:
                        user_usage.total_tokens_used = 0
                    user_usage.total_tokens_used += total_tokens
                else:
                    # 如果不存在 usage 记录，创建一个（理论上应该已有）
                    user_usage = UserUsage(
                        user_id=self.user_id,
                        total_tokens_used=total_tokens
                    )
                    db.add(user_usage)
                
                db.commit()
                print(f"💰 Token 消耗已记录: {total_tokens} (Prompt: {prompt_tokens}, Completion: {completion_tokens})")
                
        except Exception as e:
            print(f"❌ 数据库写入 Token 失败: {e}")
