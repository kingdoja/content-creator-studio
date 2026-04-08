"""
Legacy Adapter for gradual migration between old and new architecture.

This adapter bridges the gap between:
- Old interface: Agent.execute(task: Dict, context: Dict) -> Dict
- New interface: Agent.execute(task: ContentTask, context: ExecutionContext) -> ContentResult

Requirements: 10.1, 10.2
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.domain.interfaces import BaseAgent, ExecutionContext
from app.domain.models import ContentResult, ContentTask, UserContext

logger = logging.getLogger(__name__)


class LegacyAgentAdapter:
    """
    Adapter that wraps a new-style Agent (accepting domain objects)
    and exposes the old dict-based interface for backward compatibility.
    """

    def __init__(self, agent: BaseAgent):
        """
        Initialize the adapter with a new-style agent.

        Args:
            agent: An agent implementing the new BaseAgent interface
        """
        self.agent = agent
        self._name = agent.name
        self._description = agent.description

    @property
    def name(self) -> str:
        """Return the agent's name."""
        return self._name

    @property
    def description(self) -> str:
        """Return the agent's description."""
        return self._description

    async def execute(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Execute using the old dict-based interface.
        Converts dicts to domain objects, calls the new interface, and converts back.

        Args:
            task: Task dictionary with keys like category, topic, requirements, etc.
            context: Context dictionary with user_id, session_id, recalled_memories, etc.

        Returns:
            Result dictionary with success, content, agent, tools_used, etc.
        """
        try:
            # Convert dict task to ContentTask domain object
            content_task = self._dict_to_content_task(task)

            # Convert dict context to ExecutionContext domain object
            exec_context = self._dict_to_execution_context(task, context)

            # Call the new interface
            result = await self.agent.execute(content_task, exec_context)

            # Convert ContentResult back to dict
            return self._content_result_to_dict(result)

        except Exception as exc:
            logger.error(f"LegacyAgentAdapter.execute failed: {exc}", exc_info=True)
            return {
                "success": False,
                "content": "",
                "agent": self._name,
                "tools_used": [],
                "iterations": 0,
                "error": str(exc),
                "metadata": None,
            }

    @staticmethod
    def _dict_to_content_task(task: Dict[str, Any]) -> ContentTask:
        """Convert a task dict to ContentTask domain object."""
        return ContentTask(
            category=task.get("category", "lifestyle"),
            topic=task.get("topic", ""),
            requirements=task.get("requirements") or "",
            length=task.get("length", "medium"),
            style=task.get("style", "professional"),
            force_simple=task.get("force_simple", False),
        )

    @staticmethod
    def _dict_to_execution_context(
        task: Dict[str, Any],
        context: Dict[str, Any] | None,
    ) -> ExecutionContext:
        """Convert context dict to ExecutionContext domain object."""
        ctx = context or {}

        # Build preferences dict, carrying over legacy flags
        prefs = dict(ctx.get("user_preferences") or {})

        # Detect if this is a chat request (legacy module field)
        is_chat = task.get("module") == "chat"
        prefs["_is_chat"] = is_chat

        # Carry over model override if present
        if ctx.get("llm_model_override"):
            prefs["llm_model_override"] = ctx["llm_model_override"]

        # Carry over max_iterations if present
        if ctx.get("max_iterations"):
            prefs["_max_iterations"] = ctx["max_iterations"]

        # Build UserContext
        user_ctx = UserContext(
            user_id=ctx.get("user_id", "anonymous"),
            session_id=ctx.get("session_id"),
            recalled_memories=tuple(ctx.get("recalled_memories") or []),
            preferences=prefs,
        )

        # Build ExecutionContext
        return ExecutionContext(
            user_context=user_ctx,
            session_id=ctx.get("session_id"),
        )

    @staticmethod
    def _content_result_to_dict(result: ContentResult) -> Dict[str, Any]:
        """Convert ContentResult domain object back to dict."""
        return {
            "success": result.success,
            "content": result.content,
            "agent": result.agent,
            "tools_used": list(result.tools_used),
            "iterations": result.iterations,
            "error": result.error,
            "metadata": result.metadata,
        }


def wrap_agent_with_legacy_adapter(agent: BaseAgent) -> LegacyAgentAdapter:
    """
    Convenience function to wrap a new-style agent with the legacy adapter.

    Args:
        agent: An agent implementing the new BaseAgent interface

    Returns:
        A LegacyAgentAdapter that exposes the old dict-based interface
    """
    return LegacyAgentAdapter(agent)
