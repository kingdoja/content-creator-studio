"""
ContentService — 内容创作应用服务。

封装完整的内容创作业务流程，协调 ContextBuilder、LangGraph 编排图和 MemoryAppService。
方法接受领域对象（ContentTask），返回 ContentResult，不接受原始字典或 HTTP 请求对象。
Requirements: 6.1, 6.2, 6.3, 6.4
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.models import ContentTask, ContentResult, UserContext
from app.services.context_builder import ContextBuilder
from app.services.memory_app_service import MemoryAppService

logger = logging.getLogger(__name__)


@dataclass
class CreateContentRequest:
    """Input DTO for content creation (Requirement 8.3)."""
    task: ContentTask
    user_id: str
    session_id: str | None = None
    use_memory: bool = True
    memory_top_k: int = 4


@dataclass
class RefineContentRequest:
    """Input DTO for content refinement (Requirement 8.3)."""
    task: ContentTask
    draft_content: str
    user_id: str
    session_id: str | None = None
    max_reflections: int = 2


class ContentService:
    """Application service that orchestrates the full content creation workflow.

    Coordinates:
    - ContextBuilder  — single memory recall entry point (Requirement 3.1)
    - LangGraph graph — agent orchestration (Requirement 2.1)
    - MemoryAppService — async result persistence (Requirement 3.3)

    All public methods accept domain objects and return ContentResult.
    No raw dicts or HTTP request objects cross this boundary (Requirement 6.2).
    """

    def __init__(
        self,
        context_builder: ContextBuilder | None = None,
        memory_service: MemoryAppService | None = None,
    ) -> None:
        # Dependencies injected via constructor (Requirement 6.4)
        self._context_builder = context_builder or ContextBuilder()
        self._memory_service = memory_service or MemoryAppService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_content(self, request: CreateContentRequest) -> ContentResult:
        """Execute a full content creation workflow.

        Steps:
        1. Enrich task with time context.
        2. Build UserContext via ContextBuilder (memory recall).
        3. Invoke LangGraph orchestrator.
        4. Persist result via MemoryAppService (fire-and-forget).
        5. Return ContentResult domain object.

        Args:
            request: CreateContentRequest carrying the ContentTask and user info.

        Returns:
            ContentResult with success/failure, content, agent, and metadata.
        """
        task = _enrich_task_with_time_context(request.task)
        user_context = await self._context_builder.build_user_context(
            user_id=request.user_id,
            query=task.topic,
            session_id=request.session_id,
            use_memory=request.use_memory,
            memory_top_k=request.memory_top_k,
        )

        result = await self._run_graph(task, user_context)

        # Persist asynchronously — never block the response (Requirement 3.3)
        await self._persist_result(
            user_id=request.user_id,
            task=task,
            result=result,
            session_id=request.session_id,
        )

        return result

    async def refine_content(self, request: RefineContentRequest) -> ContentResult:
        """Refine an existing draft using the ReflectionAgent.

        The draft content is passed via task preferences so the agent can
        skip initial generation and focus on reflection/improvement.

        Args:
            request: RefineContentRequest with the task, draft, and user info.

        Returns:
            ContentResult with the refined content.
        """
        from app.agents.reflection_agent import ReflectionAgent
        from app.domain.interfaces import ExecutionContext

        user_context = await self._context_builder.build_user_context(
            user_id=request.user_id,
            query=request.task.topic,
            session_id=request.session_id,
            use_memory=True,
        )

        # Pass draft via preferences so ReflectionAgent can use it
        prefs = dict(user_context.preferences or {})
        prefs["_draft_content"] = request.draft_content
        prefs["_max_reflections"] = request.max_reflections

        enriched_uc = UserContext(
            user_id=user_context.user_id,
            session_id=user_context.session_id,
            recalled_memories=user_context.recalled_memories,
            preferences=prefs,
        )
        exec_ctx = ExecutionContext(
            user_context=enriched_uc,
            session_id=request.session_id,
        )

        try:
            result = await ReflectionAgent().execute(request.task, exec_ctx)
        except Exception as exc:
            logger.error("ContentService.refine_content failed: %s", exc)
            result = ContentResult(
                success=False,
                content="",
                agent="reflection",
                error=str(exc),
            )

        await self._persist_result(
            user_id=request.user_id,
            task=request.task,
            result=result,
            session_id=request.session_id,
        )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_graph(
        self,
        task: ContentTask,
        user_context: UserContext,
    ) -> ContentResult:
        """Invoke the LangGraph content creation graph and extract ContentResult."""
        from app.agents.graph import get_content_creation_graph

        graph = get_content_creation_graph()
        try:
            final_state = await graph.ainvoke(
                {
                    "task": task,
                    "user_context": user_context,
                }
            )
        except Exception as exc:
            logger.error("ContentService._run_graph failed: %s", exc)
            return ContentResult(
                success=False,
                content="",
                agent="unknown",
                error=str(exc),
            )

        return _extract_result(final_state)

    async def _persist_result(
        self,
        user_id: str,
        task: ContentTask,
        result: ContentResult,
        session_id: str | None,
    ) -> None:
        """Fire-and-forget memory persistence — errors are logged, never raised."""
        try:
            await self._memory_service.save_result(
                user_id=user_id,
                task=task,
                result=result,
                session_id=session_id,
            )
        except Exception as exc:
            logger.warning("ContentService._persist_result failed: %s", exc)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _enrich_task_with_time_context(task: ContentTask) -> ContentTask:
    """Append a time context block to the task requirements."""
    now = datetime.now()
    time_block = (
        "\n\n[时间上下文]\n"
        f"- 当前本地时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 当前年份：{now.year}\n"
        "- 如果任务涉及\u201c最新/近期/当前/今天\u201d，必须优先使用实时检索结果，"
        "并明确标注\u201c信息时间点\u201d；若无法检索到当期信息，必须明确说明。"
    )
    enriched_requirements = ((task.requirements or "").strip() + time_block).strip()
    return ContentTask(
        category=task.category,
        topic=task.topic,
        requirements=enriched_requirements,
        length=task.length,
        style=task.style,
        force_simple=task.force_simple,
    )


def _extract_result(final_state: dict[str, Any]) -> ContentResult:
    """Extract a ContentResult from the LangGraph final state."""
    result = final_state.get("result")
    if result is not None and isinstance(result, ContentResult):
        return result

    # Fallback: build from flat legacy state fields
    return ContentResult(
        success=bool(final_state.get("success", False)),
        content=str(final_state.get("content", "")),
        agent=str(final_state.get("agent", "unknown")),
        tools_used=tuple(final_state.get("tools_used", [])),
        iterations=int(final_state.get("iterations", 1)),
        error=final_state.get("error"),
        metadata={
            "execution_trace": final_state.get("execution_trace", []),
            "task_analysis": final_state.get("analysis"),
            "quality_passed": final_state.get("quality_passed"),
        },
    )
