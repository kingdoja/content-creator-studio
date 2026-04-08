"""
VideoAppService — 视频生成应用服务。

封装视频生成的完整业务逻辑，包括记忆上下文构建和记忆持久化。
将原 content.py 中的 _build_video_memory_context 和 _persist_video_generation_memory
迁移到此服务，实现 API 层与业务逻辑的解耦。
Requirements: 8.1, 6.1
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.memory import get_memory_manager
from app.services.video_generator import (
    create_story_video_task,
    generate_story_video,
    query_story_video_task,
    VideoGenerationError,
)

logger = logging.getLogger(__name__)


class VideoAppService:
    """Application service for video generation workflows.

    Encapsulates:
    - Memory context retrieval for video generation
    - Story video generation (sync and async task modes)
    - Memory persistence after successful generation
    - Session message persistence
    """

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    async def build_video_memory_context(
        self,
        db: AsyncSession,
        *,
        input_text: str,
        user_id: str,
        use_memory: bool,
        memory_top_k: int,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Recall relevant memories and format them as context text.

        Returns:
            Tuple of (formatted context string, raw recalled list).
            Returns ("", []) when use_memory is False or recall fails.
        """
        if not use_memory:
            return "", []

        manager = get_memory_manager()
        try:
            recalled = await asyncio.wait_for(
                manager.recall(
                    db,
                    query=input_text,
                    user_id=user_id or "anonymous",
                    memory_types=["episodic", "semantic", "procedural"],
                    top_k=max(1, min(memory_top_k, 10)),
                ),
                timeout=max(1, settings.MEMORY_RECALL_TIMEOUT_SECONDS),
            )
        except asyncio.TimeoutError:
            recalled = []

        if not recalled:
            return "", []

        lines = []
        for idx, item in enumerate(recalled):
            lines.append(
                f"[{idx + 1}] 来源={item.get('source_module', '')} 类型={item.get('memory_type', '')}\n"
                f"{item.get('content', '')}"
            )
        return "\n\n".join(lines), recalled

    async def persist_video_generation_memory(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        session_id: Optional[str],
        input_text: str,
        genre: str,
        mood: str,
        storyline: str,
        provider: Optional[str],
        model: Optional[str],
        task_id: Optional[str],
        recalled: list[dict[str, Any]],
    ) -> None:
        """Persist video generation result to memory system.

        Saves an episodic memory entry, updates user preferences, and
        links recalled memories to the new entry.
        """
        manager = get_memory_manager()
        source_id = ((task_id or session_id or str(uuid4())) or str(uuid4()))[:36]
        summary = (
            f"视频主题：{input_text}\n"
            f"类型：{genre}；情绪：{mood}\n"
            f"剧情摘要：{(storyline or '')[:800]}\n"
            f"模型：{model or '-'}；提供商：{provider or '-'}"
        ).strip()

        saved_entry = await manager.store.create_memory_entry(
            db,
            user_id=user_id,
            memory_type="episodic",
            source_module="video",
            source_id=source_id,
            content=summary,
            importance=0.68,
            tags=["video_generation", genre, mood],
        )
        await manager.update_preference(
            db,
            user_id=user_id,
            key="preferred_video_genre",
            value=genre,
            confidence=0.62,
        )
        await manager.update_preference(
            db,
            user_id=user_id,
            key="preferred_video_mood",
            value=mood,
            confidence=0.62,
        )
        for item in recalled[:8]:
            source_memory_id = item.get("id")
            if not source_memory_id:
                continue
            await manager.link_memories(
                db,
                source_type="memory_entry",
                source_id=str(source_memory_id),
                target_type="memory_entry",
                target_id=saved_entry.id,
                relation="contextual_support",
                strength=float(item.get("score") or 0.6),
            )

    # ------------------------------------------------------------------
    # Video generation workflows
    # ------------------------------------------------------------------

    async def generate_video(
        self,
        db: AsyncSession,
        payload: dict[str, Any],
        user_id: str,
        session_id: Optional[str],
        use_memory: bool,
        memory_top_k: int,
    ) -> dict[str, Any]:
        """Synchronous video generation (waits for completion).

        Builds memory context, generates video, persists memory, and returns result.
        """
        memory_context_text, recalled = await self.build_video_memory_context(
            db,
            input_text=payload.get("input_text", ""),
            user_id=user_id,
            use_memory=use_memory,
            memory_top_k=memory_top_k,
        )
        payload = dict(payload)
        payload["memory_context_text"] = memory_context_text

        result = await generate_story_video(payload)
        result["memory_recalled_count"] = len(recalled)
        result["memory_recalled"] = recalled

        if result.get("success") and result.get("storyline"):
            await self.persist_video_generation_memory(
                db,
                user_id=user_id,
                session_id=session_id,
                input_text=payload.get("input_text", ""),
                genre=payload.get("genre") or "sci-fi",
                mood=payload.get("mood") or "epic",
                storyline=result.get("storyline", ""),
                provider=result.get("provider"),
                model=result.get("model"),
                task_id=result.get("task_id"),
                recalled=recalled,
            )
        return result

    async def start_video_task(
        self,
        db: AsyncSession,
        payload: dict[str, Any],
        user_id: str,
        session_id: Optional[str],
        use_memory: bool,
        memory_top_k: int,
    ) -> dict[str, Any]:
        """Async video task creation (returns task_id for polling).

        Builds memory context, submits task, persists session messages and memory.
        """
        memory_context_text, recalled = await self.build_video_memory_context(
            db,
            input_text=payload.get("input_text", ""),
            user_id=user_id,
            use_memory=use_memory,
            memory_top_k=memory_top_k,
        )
        payload = dict(payload)
        payload["memory_context_text"] = memory_context_text

        result = await create_story_video_task(payload)
        result["memory_recalled_count"] = len(recalled)
        result["memory_recalled"] = recalled

        if session_id and result.get("storyline"):
            await self._persist_session_messages(
                db,
                session_id=session_id,
                user_id=user_id,
                input_text=payload.get("input_text", ""),
                result=result,
                recalled=recalled,
            )

        if result.get("success") and result.get("storyline"):
            await self.persist_video_generation_memory(
                db,
                user_id=user_id,
                session_id=session_id,
                input_text=payload.get("input_text", ""),
                genre=payload.get("genre") or "sci-fi",
                mood=payload.get("mood") or "epic",
                storyline=result.get("storyline", ""),
                provider=result.get("provider"),
                model=result.get("model"),
                task_id=result.get("task_id"),
                recalled=recalled,
            )
        return result

    async def get_video_task_status(
        self, task_id: str, provider: str = "seedance"
    ) -> dict[str, Any]:
        """Query the status of an async video generation task."""
        return await query_story_video_task(task_id=task_id, provider=provider)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _persist_session_messages(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        user_id: str,
        input_text: str,
        result: dict[str, Any],
        recalled: list[dict[str, Any]],
    ) -> None:
        """Persist user/assistant messages to the session if it belongs to the user."""
        manager = get_memory_manager()
        try:
            session = await manager.get_session(db, session_id=session_id)
            if session and session.get("user_id") == user_id:
                await manager.add_message(
                    db,
                    session_id=session_id,
                    role="user",
                    content=input_text,
                    message_type="task",
                    metadata={"module": "video"},
                )
                await manager.add_message(
                    db,
                    session_id=session_id,
                    role="assistant",
                    content=result.get("storyline", ""),
                    message_type="result",
                    metadata={
                        "module": "video",
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "memory_recalled_count": len(recalled),
                    },
                )
        except Exception as exc:
            logger.warning("VideoAppService._persist_session_messages failed: %s", exc)
