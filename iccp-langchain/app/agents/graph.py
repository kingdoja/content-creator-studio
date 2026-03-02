"""
LangGraph 内容创作编排图（唯一执行入口）
START -> memory_load -> route -> execute(selected) -> quality_gate -> [finalize | reflection_refine] -> finalize -> memory_save -> END
"""
from typing import Dict, Any, List, Optional, TypedDict
from uuid import uuid4

from langgraph.graph import StateGraph, START, END

from app.agents import routing
from app.agents.router import get_agent_router
from app.config import settings
from app.db.session import AsyncSessionLocal
from app.memory import get_memory_manager
import asyncio
import logging

logger = logging.getLogger(__name__)


class ContentCreationState(TypedDict, total=False):
    """图状态：输入、路由结果、执行结果、质量门控与执行轨迹。"""
    task: Dict[str, Any]
    context: Dict[str, Any]
    analysis: Dict[str, Any]
    next_agent: str  # "react" | "reflection" | "plan_solve" | "rag" | "simple"
    success: bool
    content: str
    agent: str
    tools_used: List[str]
    iterations: int
    error: Optional[str]
    metadata: Optional[Dict[str, Any]]
    agent_selected: str
    task_analysis: Dict[str, Any]
    quality_gate_passed: bool
    quality_gate_reason: str
    execution_trace: List[str]
    refinement_count: int
    user_id: str
    session_id: Optional[str]
    use_memory: bool
    memory_top_k: int
    llm_model_override: str
    recalled_memories: List[Dict[str, Any]]
    user_preferences: Dict[str, Any]


async def _memory_load_node(state: ContentCreationState) -> Dict[str, Any]:
    task = dict(state.get("task") or {})
    user_id = (state.get("user_id") or "anonymous").strip() or "anonymous"
    use_memory = bool(state.get("use_memory", True))
    memory_top_k = int(state.get("memory_top_k", 4) or 4)
    recalled = list(state.get("recalled_memories") or [])
    prefs: Dict[str, Any] = dict(state.get("user_preferences") or {})

    if use_memory and not recalled:
        try:
            manager = get_memory_manager()
            async with AsyncSessionLocal() as db:
                recalled = await asyncio.wait_for(
                    manager.recall(
                        db,
                        query=task.get("topic", ""),
                        user_id=user_id,
                        memory_types=["episodic", "semantic", "procedural"],
                        top_k=max(1, min(memory_top_k, 10)),
                    ),
                    timeout=max(1, settings.MEMORY_RECALL_TIMEOUT_SECONDS),
                )
                prefs = await manager.get_preferences(db, user_id=user_id)
        except Exception as e:
            logger.warning("memory_load recall failed: %s", e)
            recalled = []
            prefs = {}

    if use_memory and recalled and "[相关长期记忆]" not in (task.get("requirements") or ""):
        memory_lines = []
        for idx, item in enumerate(recalled):
            memory_lines.append(
                f"[{idx + 1}] 来源={item.get('source_module', '')} 类型={item.get('memory_type', '')}\n"
                f"{item.get('content', '')}"
            )
        memory_block = "\n\n[相关长期记忆]\n" + "\n\n".join(memory_lines)
        task["requirements"] = ((task.get("requirements") or "").strip() + memory_block).strip()

    trace = list(state.get("execution_trace", []))
    trace.append(f"memory_load:{len(recalled)}")
    return {
        "task": task,
        "recalled_memories": recalled,
        "user_preferences": prefs,
        "user_id": user_id,
        "session_id": state.get("session_id"),
        "use_memory": use_memory,
        "memory_top_k": memory_top_k,
        "llm_model_override": state.get("llm_model_override", ""),
        "execution_trace": trace,
    }


def _route_node(state: ContentCreationState) -> Dict[str, Any]:
    task = state["task"]
    recalled_memories = list(state.get("recalled_memories") or [])
    user_preferences = state.get("user_preferences") or {}
    preferred_agent_by_type: Dict[str, str] = {}
    for key, value in user_preferences.items():
        if not key.startswith("preferred_agent:"):
            continue
        task_type = key.split(":", 1)[1].strip()
        if not task_type:
            continue
        preferred = (value or {}).get("value")
        if preferred:
            preferred_agent_by_type[task_type] = str(preferred).strip().lower()
    analysis = routing.analyze_task(
        task,
        memory_signals={
            "recalled_count": len(recalled_memories),
            "has_preferences": bool(user_preferences),
            "memory_modules": [item.get("source_module") for item in recalled_memories if item.get("source_module")],
            "preference_keys": list(user_preferences.keys()),
            "preferred_agent_by_type": preferred_agent_by_type,
        },
    )
    next_agent = routing.select_agent_name(analysis)
    context = {
        "max_iterations": analysis.get("estimated_iterations", 5),
        "max_reflections": 3,
        "user_id": state.get("user_id", "anonymous"),
        "session_id": state.get("session_id"),
        "llm_model_override": state.get("llm_model_override", ""),
        "recalled_memories": recalled_memories,
        "user_preferences": user_preferences,
    }
    trace = list(state.get("execution_trace", []))
    trace.append(f"route:{next_agent}")
    logger.info("LangGraph 路由: analysis=%s, next_agent=%s", analysis, next_agent)
    return {
        "analysis": analysis,
        "next_agent": next_agent,
        "context": context,
        "execution_trace": trace,
        "refinement_count": state.get("refinement_count", 0),
    }


async def _memory_save_node(state: ContentCreationState) -> Dict[str, Any]:
    trace = list(state.get("execution_trace", []))
    task = state.get("task") or {}
    content = (state.get("content") or "").strip()
    if not content:
        trace.append("memory_save:skip")
        return {"execution_trace": trace}

    user_id = (state.get("user_id") or "anonymous").strip() or "anonymous"
    source_id = (state.get("session_id") or str(uuid4()))[:36]
    summary = f"主题：{task.get('topic', '')}\n输出摘要：{content[:800]}"

    try:
        manager = get_memory_manager()
        async with AsyncSessionLocal() as db:
            saved_entry = await manager.store.create_memory_entry(
                db,
                user_id=user_id,
                memory_type="episodic",
                source_module="content",
                source_id=source_id,
                content=summary,
                importance=0.65,
                tags=[task.get("category", "general"), "content_generation"],
            )

            # 轻量偏好学习：在成功产出后更新可复用偏好。
            if task.get("style"):
                await manager.update_preference(
                    db,
                    user_id=user_id,
                    key="preferred_style",
                    value=str(task.get("style")),
                    confidence=0.65,
                )
            if task.get("length"):
                await manager.update_preference(
                    db,
                    user_id=user_id,
                    key="preferred_length",
                    value=str(task.get("length")),
                    confidence=0.6,
                )
            if task.get("category"):
                await manager.update_preference(
                    db,
                    user_id=user_id,
                    key="preferred_category",
                    value=str(task.get("category")),
                    confidence=0.6,
                )
            if state.get("agent"):
                task_type = (
                    str((state.get("task_analysis") or state.get("analysis") or {}).get("task_type") or "").strip()
                    or "general"
                )
                await manager.update_preference(
                    db,
                    user_id=user_id,
                    key=f"preferred_agent:{task_type}",
                    value=str(state.get("agent")),
                    confidence=0.62,
                )

            # 跨模块关联：把本轮命中的历史记忆关联到新生成记忆，形成可追溯链路。
            for item in (state.get("recalled_memories") or [])[:8]:
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

            # 知识引用追踪：记录内容记忆与被引用知识文档之间的关系。
            retrieval = (state.get("metadata") or {}).get("retrieval") or []
            linked_docs = set()
            for item in retrieval:
                doc_id = item.get("document_id")
                if not doc_id or doc_id in linked_docs:
                    continue
                linked_docs.add(doc_id)
                await manager.link_memories(
                    db,
                    source_type="memory_entry",
                    source_id=saved_entry.id,
                    target_type="knowledge_document",
                    target_id=str(doc_id),
                    relation="knowledge_citation",
                    strength=float(item.get("score") or 0.6),
                )
        trace.append("memory_save:ok")
    except Exception as e:
        logger.warning("memory_save failed: %s", e)
        trace.append("memory_save:fail")

    return {"execution_trace": trace}


async def _react_node(state: ContentCreationState) -> Dict[str, Any]:
    task = state["task"]
    context = state.get("context") or {}
    router = get_agent_router()
    result = await router.react_agent.execute(task, context)
    updates = _result_to_state_updates(result, state.get("analysis"))
    trace = list(state.get("execution_trace", []))
    trace.append("execute:react")
    updates["execution_trace"] = trace
    return updates


async def _reflection_node(state: ContentCreationState) -> Dict[str, Any]:
    task = state["task"]
    context = state.get("context") or {}
    router = get_agent_router()
    result = await router.reflection_agent.execute(task, context)
    updates = _result_to_state_updates(result, state.get("analysis"))
    trace = list(state.get("execution_trace", []))
    trace.append("execute:reflection")
    updates["execution_trace"] = trace
    return updates


async def _plan_solve_node(state: ContentCreationState) -> Dict[str, Any]:
    task = state["task"]
    context = state.get("context") or {}
    router = get_agent_router()
    result = await router.plan_solve_agent.execute(task, context)
    updates = _result_to_state_updates(result, state.get("analysis"))
    trace = list(state.get("execution_trace", []))
    trace.append("execute:plan_solve")
    updates["execution_trace"] = trace
    return updates


async def _rag_node(state: ContentCreationState) -> Dict[str, Any]:
    task = state["task"]
    context = state.get("context") or {}
    router = get_agent_router()
    result = await router.rag_agent.execute(task, context)
    updates = _result_to_state_updates(result, state.get("analysis"))
    trace = list(state.get("execution_trace", []))
    trace.append("execute:rag")
    updates["execution_trace"] = trace
    return updates


async def _simple_node(state: ContentCreationState) -> Dict[str, Any]:
    task = state["task"]
    context = state.get("context") or {}
    router = get_agent_router()
    result = await router.simple_agent.execute(task, context)
    updates = _result_to_state_updates(result, state.get("analysis"))
    trace = list(state.get("execution_trace", []))
    trace.append("execute:simple")
    updates["execution_trace"] = trace
    return updates


def _quality_gate_node(state: ContentCreationState) -> Dict[str, Any]:
    """简单质量门控：失败/空内容/低质量实时任务会触发反思修订。"""
    success = state.get("success", False)
    content = (state.get("content") or "").strip()
    analysis = state.get("analysis") or {}
    tools_used = state.get("tools_used") or []

    if not success:
        passed = False
        reason = "首轮执行失败，进入反思修订"
    elif len(content) < 90 and analysis.get("complexity") == "high" and state.get("next_agent") != "simple":
        passed = False
        reason = "高复杂任务内容过短，进入反思修订"
    elif state.get("next_agent") == "simple" and len(content) < 5:
        passed = False
        reason = "简单问答内容过短，进入反思修订"
    elif (
        analysis.get("requires_real_time_data")
        and analysis.get("complexity") == "high"
        and len(tools_used) == 0
    ):
        passed = False
        reason = "高复杂实时任务未发现工具使用，进入反思修订"
    elif (
        analysis.get("requires_knowledge")
        and analysis.get("complexity") == "high"
        and "knowledge_search" not in tools_used
    ):
        passed = False
        reason = "高复杂知识任务未检索知识库，进入反思修订"
    else:
        passed = True
        reason = "质量门控通过"

    trace = list(state.get("execution_trace", []))
    trace.append(f"quality_gate:{'pass' if passed else 'fail'}")
    return {
        "quality_gate_passed": passed,
        "quality_gate_reason": reason,
        "execution_trace": trace,
    }


def _quality_route(state: ContentCreationState) -> str:
    if state.get("quality_gate_passed"):
        return "finalize"
    if state.get("refinement_count", 0) >= 1:
        return "finalize"
    return "reflection_refine"


async def _reflection_refine_node(state: ContentCreationState) -> Dict[str, Any]:
    """基于当前内容做一次反思增强。"""
    task = state["task"]
    context = dict(state.get("context") or {})
    context["draft_content"] = state.get("content", "")
    context["max_reflections"] = 2

    router = get_agent_router()
    result = await router.reflection_agent.execute(task, context)
    updates = _result_to_state_updates(result, state.get("analysis"))
    trace = list(state.get("execution_trace", []))
    trace.append("execute:reflection_refine")
    updates["execution_trace"] = trace
    updates["refinement_count"] = state.get("refinement_count", 0) + 1
    return updates


def _finalize_node(state: ContentCreationState) -> Dict[str, Any]:
    trace = list(state.get("execution_trace", []))
    trace.append("finalize")
    return {
        "agent_selected": state.get("next_agent", state.get("agent", "")),
        "task_analysis": state.get("analysis", {}),
        "execution_trace": trace,
    }


def _result_to_state_updates(
    result: Dict[str, Any], analysis: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return {
        "success": result.get("success", False),
        "content": result.get("content", ""),
        "agent": result.get("agent", ""),
        "tools_used": result.get("tools_used", []),
        "iterations": result.get("iterations", 0),
        "error": result.get("error"),
        "metadata": result.get("metadata"),
        "agent_selected": result.get("agent_selected", result.get("agent", "")),
        "task_analysis": result.get("task_analysis", analysis),
    }


def _route_edges(state: ContentCreationState) -> str:
    return state["next_agent"]


def build_content_creation_graph() -> StateGraph:
    """构建动态内容创作图。"""
    builder = StateGraph(ContentCreationState)

    builder.add_node("memory_load", _memory_load_node)
    builder.add_node("route", _route_node)
    builder.add_node("react", _react_node)
    builder.add_node("reflection", _reflection_node)
    builder.add_node("plan_solve", _plan_solve_node)
    builder.add_node("rag", _rag_node)
    builder.add_node("simple", _simple_node)
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
            "react": "react",
            "reflection": "reflection",
            "plan_solve": "plan_solve",
            "rag": "rag",
            "simple": "simple",
        },
    )

    builder.add_edge("react", "quality_gate")
    builder.add_edge("reflection", "quality_gate")
    builder.add_edge("plan_solve", "quality_gate")
    builder.add_edge("rag", "quality_gate")
    builder.add_edge("simple", "quality_gate")

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
