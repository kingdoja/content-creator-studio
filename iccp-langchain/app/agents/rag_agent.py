from typing import Any, Dict
from datetime import datetime

from sqlalchemy import func, select

import asyncio
from app.config import settings
from app.db.session import AsyncSessionLocal
from app.llm.client import get_llm_client
from app.memory import get_memory_manager
from app.models.knowledge import KnowledgeChunk
from app.rag.knowledge_service import knowledge_service


class MemoryRAGAgent:
    def __init__(self) -> None:
        self.name = "rag"
        self.description = "RAG Agent：先检索知识库，再基于检索上下文生成内容。"
        self.llm_client = get_llm_client()

    async def execute(self, task: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        query = self._build_query(task)
        context = context or {}
        model_override = (context.get("llm_model_override") or "").strip() or None
        user_id = (context.get("user_id") or "anonymous").strip() or "anonymous"
        memory_contexts = list(context.get("recalled_memories") or [])
        session_context = ""
        preferences = context.get("user_preferences") or {}

        async with AsyncSessionLocal() as db:
            count = await db.scalar(select(func.count()).select_from(KnowledgeChunk))
            if not count:
                return {
                    "success": False,
                    "content": "",
                    "agent": self.name,
                    "tools_used": [],
                    "iterations": 1,
                    "error": "知识库为空，请先上传资料",
                }

            contexts = await knowledge_service.search(db, query=query, top_k=4)
            if not memory_contexts:
                try:
                    memory_contexts = await asyncio.wait_for(
                        get_memory_manager().recall(
                            db,
                            query=query,
                            user_id=user_id,
                            memory_types=["episodic", "semantic", "procedural"],
                            top_k=3,
                        ),
                        timeout=max(1, settings.MEMORY_RECALL_TIMEOUT_SECONDS),
                    )
                except asyncio.TimeoutError:
                    memory_contexts = []
            session_id = context.get("session_id")
            if session_id:
                history = await get_memory_manager().get_session_history(
                    db, session_id=session_id, limit=6
                )
                if history:
                    session_context = "\n".join(
                        [f"{item.get('role', 'user')}: {item.get('content', '')}" for item in history]
                    )
            if not preferences:
                preferences = await get_memory_manager().get_preferences(db, user_id=user_id)

        context_text = "\n\n".join(
            [
                (
                    f"[{idx + 1}] 来源：{item['document_title']}\n"
                    f"综合相关度：{item['score']}\n"
                    f"语义相关度：{item.get('semantic_score', item['score'])}\n"
                    f"时间新鲜度：{item.get('recency_score', 'n/a')}\n"
                    f"文档时间：{item.get('document_created_at') or '未知'}\n"
                    f"片段：{item['content']}"
                )
                for idx, item in enumerate(contexts)
            ]
        )
        memory_text = "\n\n".join(
            [
                f"[{idx + 1}] 来源模块：{item.get('source_module', '')}\n片段：{item.get('content', '')}"
                for idx, item in enumerate(memory_contexts)
            ]
        )
        pref_text = "；".join([f"{k}={v.get('value', '')}" for k, v in (preferences or {}).items()]) or "无"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prompt = f"""你是一个基于知识库生成内容的犀利助手。要求：说话直接，先给结论再给依据，敢下判断，不说废话。
仅基于给定资料回答，资料不够就直接说"资料不足，无法给出可靠判断"，不要编造。
当前本地时间：{now}。
如果用户问题涉及最新动态/当前状态，必须检查资料时效；资料未标注时间或明显过旧时，要明确提示“信息可能过期”，并避免把旧信息当作当前事实。

任务信息：
- 板块：{task.get('category', 'lifestyle')}
- 主题：{task.get('topic', '')}
- 篇幅：{task.get('length', 'medium')}
- 风格：{task.get('style', 'professional')}
- 额外要求：{task.get('requirements') or '无'}

检索到的知识片段：
{context_text}

相关长期记忆（可作为辅助上下文，注意甄别时效）：
{memory_text or '无'}

当前会话最近消息：
{session_context or '无'}

用户偏好：
{pref_text}

输出要求：开门见山给结论，每个观点要有资料支撑，结尾增加"资料引用"小节列出使用到的来源标题。"""

        content = await self.llm_client.achat(
            [{"role": "user", "content": prompt}],
            temperature=0.6,
            model=model_override,
        )
        return {
            "success": True,
            "content": content,
            "agent": self.name,
            "tools_used": ["knowledge_search"] + (["memory_recall"] if memory_contexts else []),
            "iterations": 1,
            "metadata": {"retrieval": contexts, "memory_recall": memory_contexts},
        }

    @staticmethod
    def _build_query(task: Dict[str, Any]) -> str:
        topic = task.get("topic", "")
        requirements = task.get("requirements") or ""
        return f"{topic}\n{requirements}".strip()


RAGAgent = MemoryRAGAgent
