"""
ContextBuilder — 唯一的记忆召回入口。

封装记忆召回、超时降级、偏好加载逻辑，返回 UserContext 领域对象。
Requirements: 3.1, 3.2, 3.4
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.domain.models import UserContext
from app.memory import get_memory_manager

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds a UserContext by recalling memories and loading preferences.

    This is the single entry point for all memory recall operations,
    implementing timeout-based graceful degradation (Requirement 3.4).
    """

    def __init__(
        self,
        recall_timeout: float | None = None,
        memory_top_k: int = 4,
    ) -> None:
        self._recall_timeout = recall_timeout or float(
            max(1, settings.MEMORY_RECALL_TIMEOUT_SECONDS)
        )
        self._memory_top_k = max(1, min(memory_top_k, 10))

    async def build_user_context(
        self,
        user_id: str,
        query: str,
        session_id: str | None = None,
        use_memory: bool = True,
        memory_top_k: int | None = None,
    ) -> UserContext:
        """Recall memories and preferences, returning a UserContext.

        On timeout or any recall error, degrades gracefully to an empty
        context so the caller can continue without memory (Requirement 3.4).

        Args:
            user_id: The user identifier (must be non-empty).
            query: The query string used for semantic memory recall.
            session_id: Optional session identifier.
            use_memory: When False, skips recall and returns empty context.
            memory_top_k: Override the default top-k for this call.

        Returns:
            A frozen UserContext domain object.
        """
        user_id = (user_id or "anonymous").strip() or "anonymous"
        top_k = max(1, min(memory_top_k or self._memory_top_k, 10))

        recalled: list[dict[str, Any]] = []
        preferences: dict[str, Any] = {}

        if use_memory:
            try:
                recalled, preferences = await asyncio.wait_for(
                    self._recall_and_prefs(user_id, query, top_k),
                    timeout=self._recall_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "ContextBuilder: memory recall timed out for user=%s, degrading to empty context",
                    user_id,
                )
            except Exception as exc:
                logger.warning(
                    "ContextBuilder: memory recall failed for user=%s: %s",
                    user_id,
                    exc,
                )

        return UserContext(
            user_id=user_id,
            session_id=session_id,
            recalled_memories=tuple(recalled),
            preferences=preferences,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _recall_and_prefs(
        self,
        user_id: str,
        query: str,
        top_k: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Run recall and preference loading inside a single DB session."""
        manager = get_memory_manager()
        async with AsyncSessionLocal() as db:
            recalled = await manager.recall(
                db,
                query=query,
                user_id=user_id,
                memory_types=["episodic", "semantic", "procedural"],
                top_k=top_k,
            )
            preferences = await manager.get_preferences(db, user_id=user_id)
        return recalled, preferences
