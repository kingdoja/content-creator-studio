from typing import Any
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.content import ContentRecord

ALLOWED_COMPARE_AGENTS = {"react", "reflection", "plan_solve", "rag", "simple"}


def validate_category_or_raise(category: str, categories: dict[str, Any]) -> None:
    if category not in categories:
        raise HTTPException(
            status_code=400,
            detail=f"无效的板块: {category}。支持的板块: {list(categories.keys())}",
        )


def build_content_task_payload(request: Any, merged_requirements: str) -> dict[str, Any]:
    return {
        "category": request.category,
        "topic": request.topic,
        "requirements": merged_requirements,
        "length": request.length,
        "style": request.style,
        "force_simple": request.force_simple,
    }


def build_refine_task_payload(request: Any) -> dict[str, Any]:
    return {
        "category": request.category,
        "topic": request.topic,
        "requirements": request.requirements,
        "length": request.length,
        "style": request.style,
    }


def build_evaluate_response(*, content: str, topic: str, scorer: Any) -> dict[str, Any]:
    return {"success": True, "evaluation": scorer(content, topic=topic)}


def select_compare_agents_or_raise(agents: list[str]) -> list[str]:
    selected_agents = [agent for agent in agents if agent in ALLOWED_COMPARE_AGENTS]
    if not selected_agents:
        raise HTTPException(status_code=400, detail="agents 不能为空，且需在 react/reflection/plan_solve/rag/simple 中选择")
    return selected_agents


def build_compare_task_payload(request: Any) -> dict[str, Any]:
    return {
        "category": request.category,
        "topic": request.topic,
        "requirements": request.requirements,
        "length": request.length,
        "style": request.style,
    }


def build_compare_result_item(*, agent_name: str, run_result: dict[str, Any], topic: str, scorer: Any) -> dict[str, Any]:
    evaluation = scorer(run_result.get("content", ""), topic=topic)
    return {
        "agent": agent_name,
        "success": run_result.get("success", False),
        "content": run_result.get("content", ""),
        "tools_used": run_result.get("tools_used", []),
        "iterations": run_result.get("iterations", 0),
        "error": run_result.get("error"),
        "evaluation": evaluation,
    }


def pick_compare_winner(results: list[dict[str, Any]]) -> str | None:
    if not results:
        return None
    return max(results, key=lambda item: item["evaluation"]["total_score"])["agent"]


async def run_compare_agents(
    *,
    request: Any,
    agent_router: Any,
    scorer: Any,
) -> tuple[list[dict[str, Any]], str | None]:
    selected_agents = select_compare_agents_or_raise(request.agents)
    task = build_compare_task_payload(request)
    mapping = {
        "react": agent_router.react_agent,
        "reflection": agent_router.reflection_agent,
        "plan_solve": agent_router.plan_solve_agent,
        "rag": agent_router.rag_agent,
        "simple": agent_router.simple_agent,
    }
    results: list[dict[str, Any]] = []
    for agent_name in selected_agents:
        run_result = await mapping[agent_name].execute(task, {})
        results.append(
            build_compare_result_item(
                agent_name=agent_name,
                run_result=run_result,
                topic=request.topic,
                scorer=scorer,
            )
        )
    return results, pick_compare_winner(results)


async def prepare_content_generation_context(
    *,
    request: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base_requirements = (request.requirements or "").strip()
    now = datetime.now()
    time_context = (
        f"[时间上下文]\n"
        f"- 当前本地时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- 当前年份：{now.year}\n"
        f"- 如果任务涉及“最新/近期/当前/今天”，必须优先使用实时检索结果，"
        f"并明确标注“信息时间点”；若无法检索到当期信息，必须明确说明。"
    )
    merged_requirements = f"{base_requirements}\n\n{time_context}".strip()
    task = build_content_task_payload(request, merged_requirements)
    return task, []


def build_content_response_dict(final_state: dict[str, Any]) -> dict[str, Any]:
    """Build a flat response dict from the graph's final state.

    Supports both the new domain-object state (result: ContentResult) and
    the legacy flat-field state shape (backward compat with tests/old callers).
    """
    result = final_state.get("result")
    if result is not None and hasattr(result, "success"):
        # New domain-object state
        analysis = final_state.get("analysis")
        analysis_dict: dict[str, Any] | None = None
        if analysis is not None and hasattr(analysis, "task_type"):
            analysis_dict = {
                "complexity": analysis.complexity,
                "task_type": analysis.task_type,
                "requires_knowledge": analysis.requires_knowledge,
                "requires_real_time_data": analysis.requires_real_time_data,
                "requires_reflection": analysis.requires_reflection,
                "estimated_iterations": analysis.estimated_iterations,
            }
        return {
            "success": result.success,
            "content": result.content,
            "agent": result.agent,
            "tools_used": list(result.tools_used),
            "iterations": result.iterations,
            "agent_selected": result.agent,
            "task_analysis": analysis_dict,
            "quality_gate_passed": final_state.get("quality_passed"),
            "quality_gate_reason": None,
            "execution_trace": final_state.get("execution_trace", []),
            "error": result.error,
        }
    # Legacy flat-field state (tests, old callers)
    return {
        "success": final_state.get("success", False),
        "content": final_state.get("content", ""),
        "agent": final_state.get("agent", ""),
        "tools_used": final_state.get("tools_used", []),
        "iterations": final_state.get("iterations", 0),
        "agent_selected": final_state.get("agent_selected"),
        "task_analysis": final_state.get("task_analysis"),
        "quality_gate_passed": final_state.get("quality_gate_passed"),
        "quality_gate_reason": final_state.get("quality_gate_reason"),
        "execution_trace": final_state.get("execution_trace", []),
        "error": final_state.get("error"),
    }


async def persist_content_record(
    *,
    db: AsyncSession,
    user_id: str,
    category: str,
    topic: str,
    result: dict[str, Any],
) -> None:
    if not result.get("success") or not result.get("content"):
        return
    db.add(
        ContentRecord(
            user_id=user_id,
            category=category,
            topic=topic,
            agent=(result.get("agent") or ""),
            content=(result.get("content") or ""),
            tools_used=",".join(result.get("tools_used", []) or []),
            iterations=int(result.get("iterations", 0) or 0),
        )
    )
    await db.commit()


async def persist_refine_record(
    *,
    db: AsyncSession,
    user_id: str,
    request: Any,
    result: dict[str, Any],
    stream_mode: bool = False,
) -> None:
    if not result.get("success") or not result.get("content"):
        return
    tools = list(result.get("tools_used", []) or [])
    if stream_mode:
        tools.append("refine_stream")
    db.add(
        ContentRecord(
            user_id=user_id,
            category=request.category,
            topic=f"[Refine] {request.topic}",
            agent=(result.get("agent") or "reflection"),
            content=(result.get("content") or ""),
            tools_used=",".join(tools),
            iterations=int(result.get("iterations", 0) or 0),
        )
    )
    await db.commit()


def build_refine_stream_complete_payload(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": result.get("success", False),
        "content": result.get("content", ""),
        "agent": result.get("agent", "reflection"),
        "tools_used": result.get("tools_used", []),
        "iterations": result.get("iterations", 0),
        "execution_trace": result.get("metadata", {}).get("reflection_rounds", []),
        "error": result.get("error"),
    }
