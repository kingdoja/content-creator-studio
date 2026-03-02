from typing import Any

from app.llm.client import get_llm_client


class MemorySummarizer:
    def __init__(self) -> None:
        self.llm = get_llm_client()

    async def summarize_messages(self, messages: list[dict[str, Any]]) -> str:
        if not messages:
            return ""
        chat_text = "\n".join(
            [f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages]
        )
        prompt = f"""请把以下对话总结为简洁摘要（120-220字），包含：
1) 核心话题
2) 关键结论
3) 用户偏好/约束（如果有）
4) 后续可延续的问题（如果有）

对话：
{chat_text}
"""
        return await self.llm.achat([{"role": "user", "content": prompt}], temperature=0.3)
