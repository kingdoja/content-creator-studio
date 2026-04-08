"""
MemoryAppService — 统一的记忆持久化入口。

将 graph.py 中 _memory_save_node 的偏好学习、记忆链接逻辑迁移到此服务。
所有操作通过 MemoryManager 接口完成，不直接访问 manager.store。
Requirements: 3.3, 3.5
"""
from __future__ import annotations

import logging
from uuid import uuid4

from app.db.session import AsyncSessionLocal
from app.domain.models import ContentResult, ContentTask
from app.memory import MemoryManager, get_memory_manager

logger = logging.getLogger(__name__)


class MemoryAppService:
    """Application service responsible for persisting content results to memory.

    Coordinates preference learning and memory linking through the
    MemoryManager interface only — never touches manager.store directly.
    """

    def __init__(self, memory_manager: MemoryManager | None = None) -> None:
        self._manager = memory_manager or get_memory_manager()

    async def save_result(
        self,
        user_id: str,
        task: ContentTask,
        result: ContentResult,
        session_id: str | None = None,
        agent_task_type: str = "general",
    ) -> None:
        """Persist a completed content result to the memory system.

        Steps performed:
        1. Store an episodic memory entry summarising the task output.
        2. Update lightweight user preferences (style, length, category, agent).
        3. Link recalled memories to the new entry (contextual support).
        4. Link cited knowledge documents to the new entry (knowledge citation).

        On any failure the error is logged and the method returns silently so
        that the caller's response is never blocked by memory persistence.

        Args:
            user_id: The user who owns this result.
            task: The ContentTask that was executed.
            result: The ContentResult produced by the agent.
            session_id: Optional session identifier used as the source_id.
            agent_task_type: The task_type string used for the agent preference key.
        """
        content = (result.content or "").strip()
        if not content:
            logger.debug("MemoryAppService.save_result: empty content, skipping for user=%s", user_id)
            return

        user_id = (user_id or "anonymous").strip() or "anonymous"
        source_id = (session_id or str(uuid4()))[:36]
        summary = f"主题：{task.topic}\n输出摘要：{content[:800]}"

        try:
            async with AsyncSessionLocal() as db:
                # 1. Store episodic memory entry
                saved_entry = await self._manager.store.create_memory_entry(
                    db,
                    user_id=user_id,
                    memory_type="episodic",
                    source_module="content",
                    source_id=source_id,
                    content=summary,
                    importance=0.65,
                    tags=[task.category or "general", "content_generation"],
                )

                # 2. Lightweight preference learning
                if task.style:
                    await self._manager.update_preference(
                        db,
                        user_id=user_id,
                        key="preferred_style",
                        value=str(task.style),
                        confidence=0.65,
                    )
                if task.length:
                    await self._manager.update_preference(
                        db,
                        user_id=user_id,
                        key="preferred_length",
                        value=str(task.length),
                        confidence=0.6,
                    )
                if task.category:
                    await self._manager.update_preference(
                        db,
                        user_id=user_id,
                        key="preferred_category",
                        value=str(task.category),
                        confidence=0.6,
                    )
                if result.agent:
                    task_type = (agent_task_type or "general").strip() or "general"
                    await self._manager.update_preference(
                        db,
                        user_id=user_id,
                        key=f"preferred_agent:{task_type}",
                        value=str(result.agent),
                        confidence=0.62,
                    )

                # 3. Link recalled memories → new entry (contextual support)
                recalled = result.metadata.get("recalled_memories", []) if result.metadata else []
                for item in recalled[:8]:
                    source_memory_id = item.get("id")
                    if not source_memory_id:
                        continue
                    await self._manager.link_memories(
                        db,
                        source_type="memory_entry",
                        source_id=str(source_memory_id),
                        target_type="memory_entry",
                        target_id=saved_entry.id,
                        relation="contextual_support",
                        strength=float(item.get("score") or 0.6),
                    )

                # 4. Link cited knowledge documents → new entry (knowledge citation)
                retrieval = (result.metadata or {}).get("retrieval") or []
                linked_docs: set[str] = set()
                for item in retrieval:
                    doc_id = item.get("document_id")
                    if not doc_id or doc_id in linked_docs:
                        continue
                    linked_docs.add(doc_id)
                    await self._manager.link_memories(
                        db,
                        source_type="memory_entry",
                        source_id=saved_entry.id,
                        target_type="knowledge_document",
                        target_id=str(doc_id),
                        relation="knowledge_citation",
                        strength=float(item.get("score") or 0.6),
                    )

            logger.debug("MemoryAppService.save_result: saved for user=%s", user_id)

        except Exception as exc:
            logger.warning("MemoryAppService.save_result failed for user=%s: %s", user_id, exc)
