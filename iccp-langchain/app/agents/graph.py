"""
LangGraph 内容创作编排图（唯一执行入口）
START -> memory_load -> route -> execute(selected) -> quality_gate -> [finalize | reflection_refine] -> finalize -> memory_save -> END

重构要点（Requirements 2.1, 2.2, 3.1, 3.2, 3.3）：
- ContentCreationState 精简为 8 个字段（task, user_context, analysis, next_agent,
  result, quality_passed, refinement_count, execution_trace）
- 节点函数接受和返回领域对象，而非原始字典
- _memory_load_node 通过 ContextBuilder 统一召回记忆（Requirements 3.1, 3.2）
- _memory_save_node 通过 MemoryAppService 统一持久化（Requirements 3.3）
"""
from __future__ import annotations

import logging
from typing import Optional

from langgraph.graph import StateGraph, START, END

from app.domain.interfaces import ExecutionContext
from app.domain.models import ContentTask, ContentResult, TaskAnalysis, UserContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State definition — exactly 8 fields (Requirement 2.2)
# ---------------------------------------------------------------------------

from typing import TypedDict, List


class ContentCreationState(TypedDict, total=False):
    """精简后的图状态，严格限定为 8 个字段。"""
    task: ContentTask                    # 输入任务（领域对象）
    user_context: UserContext            # 用户上下文，含记忆（领域对象）
    analysis: TaskAnalysis               # 路由分析结果（领域对象）
    next_agent: str                      # 路由目标: "simple" | "react" | "reflection"
    result: Optional[ContentResult]      # 执行结果（领域对象）
    quality_passed: bool                 # 质量门控是否通过
    refinement_count: int                # 反思修订次数
    execution_trace: List[str]           # 执行轨迹（调试用）


# ---------------------------------------------------------------------------
# Node: memory_load  (Requirements 3.1, 3.2)
# ---------------------------------------------------------------------------

async def _memory_load_node(state: ContentCreationState) -> dict:
    """通过 ContextBuilder 统一召回记忆，构建 UserContext 领域对象。"""
    from app.services.context_builder import ContextBuilder

    # Accept both ContentTask domain object and legacy raw dict (backward compat)
    raw_task = state["task"]
    if isinstance(raw_task, dict):
        task = ContentTask(
            category=raw_task.get("category", "lifestyle"),
            topic=raw_task.get("topic", ""),
            requirements=raw_task.get("requirements") or "",
            length=raw_task.get("length", "medium"),
            style=raw_task.get("style", "professional"),
            force_simple=bool(raw_task.get("force_simple", False)),
        )
    else:
        task = raw_task

    # user_context may carry bootstrap info (user_id, session_id, use_memory, top_k)
    # Also support legacy flat fields user_id / session_id on state for backward compat
    bootstrap_uc = state.get("user_context")
    if bootstrap_uc is None:
        legacy_user_id = state.get("user_id", "anonymous") or "anonymous"  # type: ignore[attr-defined]
        legacy_session_id = state.get("session_id")  # type: ignore[attr-defined]
        legacy_prefs: dict = {}
        if state.get("use_memory") is not None:  # type: ignore[attr-defined]
            legacy_prefs["use_memory"] = state.get("use_memory")  # type: ignore[attr-defined]
        if state.get("memory_top_k") is not None:  # type: ignore[attr-defined]
            legacy_prefs["memory_top_k"] = state.get("memory_top_k")  # type: ignore[attr-defined]
        if state.get("llm_model_override"):  # type: ignore[attr-defined]
            legacy_prefs["llm_model_override"] = state.get("llm_model_override")  # type: ignore[attr-defined]
        bootstrap: UserContext = UserContext(
            user_id=legacy_user_id,
            session_id=legacy_session_id,
            preferences=legacy_prefs,
        )
    else:
        bootstrap = bootstrap_uc

    prefs = bootstrap.preferences or {}
    use_memory = bool(prefs.get("use_memory", True))
    memory_top_k = int(prefs.get("memory_top_k", 4))

    builder = ContextBuilder(memory_top_k=memory_top_k)
    user_context = await builder.build_user_context(
        user_id=bootstrap.user_id,
        query=task.topic,
        session_id=bootstrap.session_id,
        use_memory=use_memory,
        memory_top_k=memory_top_k,
    )

    # Inject recalled memories into task.requirements as context block
    recalled = list(user_context.recalled_memories)
    task_dict = {
        "category": task.category,
        "topic": task.topic,
        "requirements": task.requirements,
        "length": task.length,
        "style": task.style,
        "force_simple": task.force_simple,
    }
    if recalled and "[相关长期记忆]" not in (task.requirements or ""):
        memory_lines = []
        for idx, item in enumerate(recalled):
            memory_lines.append(
                f"[{idx + 1}] 来源={item.get('source_module', '')} 类型={item.get('memory_type', '')}\n"
                f"{item.get('content', '')}"
            )
        memory_block = "\n\n[相关长期记忆]\n" + "\n\n".join(memory_lines)
        task_dict["requirements"] = ((task.requirements or "").strip() + memory_block).strip()

    enriched_task = ContentTask(
        category=task_dict["category"],
        topic=task_dict["topic"],
        requirements=task_dict["requirements"],
        length=task_dict["length"],
        style=task_dict["style"],
        force_simple=task_dict["force_simple"],
    )

    trace = list(state.get("execution_trace") or [])
    trace.append(f"memory_load:{len(recalled)}")

    return {
        "task": enriched_task,
        "user_context": user_context,
        "execution_trace": trace,
    }


# ---------------------------------------------------------------------------
# Node: route
# ---------------------------------------------------------------------------

def _route_node(state: ContentCreationState) -> dict:
    """分析任务并通过 AgentRouterV2 选择目标 Agent。"""
    from app.agents.router_v2 import get_router_v2

    task: ContentTask = state["task"]
    user_context: UserContext = state.get("user_context") or UserContext(
        user_id="anonymous", session_id=None
    )
    recalled_memories = list(user_context.recalled_memories)
    preferences = user_context.preferences or {}

    preferred_agent_by_type: dict[str, str] = {}
    for key, value in preferences.items():
        if not key.startswith("preferred_agent:"):
            continue
        task_type = key.split(":", 1)[1].strip()
        preferred = (value or {}).get("value")
        if task_type and preferred:
            preferred_agent_by_type[task_type] = str(preferred).strip().lower()

    router = get_router_v2()
    task_dict = {
        "category": task.category,
        "topic": task.topic,
        "requirements": task.requirements,
        "length": task.length,
        "style": task.style,
        "force_simple": task.force_simple,
    }
    next_agent, analysis = router.route_from_task(
        task_dict,
        memory_signals={
            "recalled_count": len(recalled_memories),
            "has_preferences": bool(preferences),
            "memory_modules": [m.get("source_module") for m in recalled_memories if m.get("source_module")],
            "preference_keys": list(preferences.keys()),
            "preferred_agent_by_type": preferred_agent_by_type,
        },
    )

    trace = list(state.get("execution_trace") or [])
    trace.append(f"route:{next_agent}")
    logger.info("LangGraph 路由: analysis=%s, next_agent=%s", analysis, next_agent)

    return {
        "analysis": analysis,
        "next_agent": next_agent,
        "refinement_count": state.get("refinement_count", 0),
        "execution_trace": trace,
    }


# ---------------------------------------------------------------------------
# Node: execute (simple / react / reflection)
# ---------------------------------------------------------------------------

def _build_exec_context(state: ContentCreationState) -> ExecutionContext:
    """Build an ExecutionContext from current state, forwarding agent config via preferences."""
    user_context: UserContext = state.get("user_context") or UserContext(
        user_id="anonymous", session_id=None
    )
    analysis: TaskAnalysis | None = state.get("analysis")
    prefs = dict(user_context.preferences or {})

    if analysis:
        prefs["_max_iterations"] = analysis.estimated_iterations
        prefs["_max_reflections"] = 3
        prefs["_use_planning"] = (
            analysis.task_type == "planning" and analysis.complexity == "high"
        )

    enriched_ctx = UserContext(
        user_id=user_context.user_id,
        session_id=user_context.session_id,
        recalled_memories=user_context.recalled_memories,
        preferences=prefs,
    )
    return ExecutionContext(
        user_context=enriched_ctx,
        session_id=user_context.session_id,
    )


async def _simple_node(state: ContentCreationState) -> dict:
    from app.agents.simple_agent import SimpleAgent

    task: ContentTask = state["task"]
    exec_ctx = _build_exec_context(state)
    result = await SimpleAgent().execute(task, exec_ctx)

    trace = list(state.get("execution_trace") or [])
    trace.append("execute:simple")
    return {"result": result, "execution_trace": trace}


async def _react_node(state: ContentCreationState) -> dict:
    from app.agents.react_agent import ReActAgent

    task: ContentTask = state["task"]
    exec_ctx = _build_exec_context(state)
    result = await ReActAgent().execute(task, exec_ctx)

    trace = list(state.get("execution_trace") or [])
    trace.append("execute:react")
    return {"result": result, "execution_trace": trace}


async def _reflection_node(state: ContentCreationState) -> dict:
    from app.agents.reflection_agent import ReflectionAgent

    task: ContentTask = state["task"]
    exec_ctx = _build_exec_context(state)
    result = await ReflectionAgent().execute(task, exec_ctx)

    trace = list(state.get("execution_trace") or [])
    trace.append("execute:reflection")
    return {"result": result, "execution_trace": trace}


# ---------------------------------------------------------------------------
# Node: quality_gate
# ---------------------------------------------------------------------------

def _quality_gate_node(state: ContentCreationState) -> dict:
    """质量门控：失败/空内容/低质量高复杂任务触发反思修订。"""
    result: ContentResult | None = state.get("result")
    analysis: TaskAnalysis | None = state.get("analysis")
    next_agent = state.get("next_agent", "")

    if result is None or not result.success:
        passed = False
    elif len((result.content or "").strip()) < 90 and analysis and analysis.complexity == "high" and next_agent != "simple":
        passed = False
    elif next_agent == "simple" and len((result.content or "").strip()) < 5:
        passed = False
    elif (
        analysis
        and analysis.requires_real_time_data
        and analysis.complexity == "high"
        and len(result.tools_used) == 0
    ):
        passed = False
    elif (
        analysis
        and analysis.requires_knowledge
        and analysis.complexity == "high"
        and "knowledge_search" not in result.tools_used
    ):
        passed = False
    else:
        passed = True

    trace = list(state.get("execution_trace") or [])
    trace.append(f"quality_gate:{'pass' if passed else 'fail'}")
    return {"quality_passed": passed, "execution_trace": trace}


def _quality_route(state: ContentCreationState) -> str:
    if state.get("quality_passed"):
        return "finalize"
    if state.get("refinement_count", 0) >= 1:
        return "finalize"
    return "reflection_refine"


# ---------------------------------------------------------------------------
# Node: reflection_refine
# ---------------------------------------------------------------------------

async def _reflection_refine_node(state: ContentCreationState) -> dict:
    """基于当前 result 做一次反思增强。"""
    from app.agents.reflection_agent import ReflectionAgent

    task: ContentTask = state["task"]
    result: ContentResult | None = state.get("result")

    exec_ctx = _build_exec_context(state)
    # Pass existing draft via preferences so ReflectionAgent can skip re-generation
    prefs = dict(exec_ctx.user_context.preferences or {})
    prefs["_draft_content"] = result.content if result else ""
    prefs["_max_reflections"] = 2

    enriched_uc = UserContext(
        user_id=exec_ctx.user_context.user_id,
        session_id=exec_ctx.user_context.session_id,
        recalled_memories=exec_ctx.user_context.recalled_memories,
        preferences=prefs,
    )
    refine_ctx = ExecutionContext(
        user_context=enriched_uc,
        session_id=exec_ctx.session_id,
    )

    refined_result = await ReflectionAgent().execute(task, refine_ctx)

    trace = list(state.get("execution_trace") or [])
    trace.append("execute:reflection_refine")
    return {
        "result": refined_result,
        "refinement_count": state.get("refinement_count", 0) + 1,
        "execution_trace": trace,
    }


# ---------------------------------------------------------------------------
# Node: finalize
# ---------------------------------------------------------------------------

def _finalize_node(state: ContentCreationState) -> dict:
    trace = list(state.get("execution_trace") or [])
    trace.append("finalize")
    return {"execution_trace": trace}


# ---------------------------------------------------------------------------
# Node: memory_save  (Requirement 3.3)
# ---------------------------------------------------------------------------

async def _memory_save_node(state: ContentCreationState) -> dict:
    """通过 MemoryAppService 统一持久化记忆，替代内联存储逻辑。"""
    from app.services.memory_app_service import MemoryAppService

    trace = list(state.get("execution_trace") or [])
    result: ContentResult | None = state.get("result")

    if not result or not (result.content or "").strip():
        trace.append("memory_save:skip")
        return {"execution_trace": trace}

    task: ContentTask = state["task"]
    user_context: UserContext = state.get("user_context") or UserContext(
        user_id="anonymous", session_id=None
    )
    analysis: TaskAnalysis | None = state.get("analysis")
    agent_task_type = analysis.task_type if analysis else "general"

    # Attach recalled_memories to result.metadata so MemoryAppService can link them
    metadata = dict(result.metadata or {})
    metadata.setdefault("recalled_memories", list(user_context.recalled_memories))
    enriched_result = ContentResult(
        success=result.success,
        content=result.content,
        agent=result.agent,
        tools_used=result.tools_used,
        iterations=result.iterations,
        error=result.error,
        metadata=metadata,
    )

    try:
        service = MemoryAppService()
        await service.save_result(
            user_id=user_context.user_id,
            task=task,
            result=enriched_result,
            session_id=user_context.session_id,
            agent_task_type=agent_task_type,
        )
        trace.append("memory_save:ok")
    except Exception as exc:
        logger.warning("memory_save failed: %s", exc)
        trace.append("memory_save:fail")

    return {"execution_trace": trace}


# ---------------------------------------------------------------------------
# Routing edge
# ---------------------------------------------------------------------------

def _route_edges(state: ContentCreationState) -> str:
    return state.get("next_agent", "react")


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_content_creation_graph() -> StateGraph:
    """构建精简后的内容创作图（3 个 Agent 节点）。"""
    builder = StateGraph(ContentCreationState)

    builder.add_node("memory_load", _memory_load_node)
    builder.add_node("route", _route_node)
    builder.add_node("simple", _simple_node)
    builder.add_node("react", _react_node)
    builder.add_node("reflection", _reflection_node)
    builder.add_node("quality_gate", _quality_gate_node)
    builder.add_node("reflection_refine", _reflection_refine_node)
    builder.add_node("finalize", _finalize_node)
    builder.add_node("memory_save", _memory_save_node)

    builder.add_edge(START, "memory_load")
    builder.add_edge("memory_load", "route")
    builder.add_conditional_edges(
        "route",
        _route_edges,
        {
            "simple": "simple",
            "react": "react",
            "reflection": "reflection",
        },
    )

    builder.add_edge("simple", "quality_gate")
    builder.add_edge("react", "quality_gate")
    builder.add_edge("reflection", "quality_gate")

    builder.add_conditional_edges(
        "quality_gate",
        _quality_route,
        {
            "finalize": "finalize",
            "reflection_refine": "reflection_refine",
        },
    )
    builder.add_edge("reflection_refine", "finalize")
    builder.add_edge("finalize", "memory_save")
    builder.add_edge("memory_save", END)

    return builder


_content_graph = None


def get_content_creation_graph():
    """获取已编译的内容创作图（单例）"""
    global _content_graph
    if _content_graph is None:
        _content_graph = build_content_creation_graph().compile()
    return _content_graph
