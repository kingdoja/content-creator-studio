import asyncio
import time
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


def build_memory_block(recalled: list[dict[str, Any]]) -> str:
    if not recalled:
        return ""
    memory_lines = []
    for idx, item in enumerate(recalled):
        memory_lines.append(
            f"[{idx + 1}] 来源={item.get('source_module', '')} 类型={item.get('memory_type', '')}\n"
            f"{item.get('content', '')}"
        )
    return "\n\n[相关长期记忆]\n" + "\n\n".join(memory_lines)


def build_session_history_block(
    history: list[dict[str, Any]],
    *,
    current_user_content: str,
    max_items: int = 8,
    max_chars_per_message: int = 280,
) -> str:
    """把同会话最近几轮问答转换为提示词上下文。"""
    if not history:
        return ""
    dialog = [m for m in history if m.get("role") in {"user", "assistant"}]
    if not dialog:
        return ""
    # 当前用户消息已经作为 topic 单独传入，避免在上下文里重复一次。
    if (
        dialog
        and dialog[-1].get("role") == "user"
        and (dialog[-1].get("content") or "").strip() == current_user_content.strip()
    ):
        dialog = dialog[:-1]
    if not dialog:
        return ""
    recent = dialog[-max_items:]
    lines: list[str] = []
    for item in recent:
        role = "用户" if item.get("role") == "user" else "助手"
        content = (item.get("content") or "").strip().replace("\n", " ")
        if len(content) > max_chars_per_message:
            content = content[:max_chars_per_message] + "..."
        if content:
            lines.append(f"{role}：{content}")
    if not lines:
        return ""
    return (
        "\n\n[同会话最近对话]\n"
        + "\n".join(lines)
        + "\n\n请结合以上同会话上下文回答当前问题，不要与历史答案自相矛盾。"
    )


async def load_owned_session_or_403(
    *,
    db: AsyncSession,
    manager: Any,
    session_id: str,
    user_id: str,
) -> dict[str, Any]:
    session = await manager.get_session(db, session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="会话不属于当前用户")
    return session


async def append_chat_user_message(
    *,
    db: AsyncSession,
    manager: Any,
    session_id: str,
    user_content: str,
) -> None:
    await manager.add_message(
        db,
        session_id=session_id,
        role="user",
        content=user_content,
        message_type="text",
    )
    await _auto_rename_session_if_needed(db, manager, session_id, user_content)


async def _auto_rename_session_if_needed(
    db: AsyncSession, manager: Any, session_id: str, user_content: str
) -> None:
    """如果会话标题仍是默认的'新会话'，用第一条用户消息生成摘要标题。"""
    session = await manager.get_session(db, session_id=session_id)
    if not session:
        return
    current_title = session.get("title", "") if isinstance(session, dict) else getattr(session, "title", "")
    if current_title and current_title != "新会话":
        return
    summary = user_content.strip().replace("\n", " ")
    if len(summary) > 20:
        summary = summary[:20] + "..."
    await _update_session_title(db, session_id, summary)


async def _update_session_title(db: AsyncSession, session_id: str, title: str) -> None:
    from app.models.memory import ConversationSession
    session_obj = await db.get(ConversationSession, session_id)
    if session_obj:
        session_obj.title = title
        await db.commit()


async def prepare_chat_generation_context(
    *,
    db: AsyncSession,
    manager: Any,
    request: Any,
    session_id: str,
    user_id: str,
    user_content: str,
    timings_ms: dict[str, int],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], str]:
    recalled: list[dict[str, Any]] = []
    if request.use_memory:
        recall_started_at = time.perf_counter()
        try:
            recalled = await asyncio.wait_for(
                manager.recall(
                    db,
                    query=user_content,
                    user_id=user_id,
                    memory_types=["episodic", "semantic", "procedural"],
                    top_k=request.memory_top_k,
                ),
                timeout=max(1, settings.MEMORY_RECALL_TIMEOUT_SECONDS),
            )
        except asyncio.TimeoutError:
            recalled = []
        timings_ms["memory_recall"] = int((time.perf_counter() - recall_started_at) * 1000)
    prefs = await manager.get_preferences(db, user_id=user_id)

    history_started_at = time.perf_counter()
    session_history = await manager.get_session_history(db, session_id=session_id, limit=20)
    timings_ms["session_history"] = int((time.perf_counter() - history_started_at) * 1000)

    prompt_requirements = (request.requirements or "").strip()
    session_history_block = build_session_history_block(
        session_history,
        current_user_content=user_content,
    )
    memory_block = build_memory_block(recalled)
    merged_requirements = "\n".join(
        part for part in [prompt_requirements, session_history_block, memory_block] if part
    ).strip()

    length = request.length
    style = request.style
    force_simple = request.force_simple

    if not force_simple and _is_simple_message(user_content):
        force_simple = True
        length = "short"
        style = "casual"

    task = {
        "module": "chat",
        "category": request.category,
        "topic": user_content,
        "requirements": merged_requirements,
        "length": length,
        "style": style,
        "force_simple": force_simple,
    }
    llm_model_override = (settings.CHAT_FAST_MODEL or "").strip()
    return task, recalled, prefs, llm_model_override


def _is_simple_message(text: str) -> bool:
    """检测是否为简单消息（纯闲聊、打招呼等），用于自动降级到快速路径。
    注意：包含行动请求（帮我做/写/想/分析、具体、方案、设计等）的消息不算简单消息。
    """
    t = text.strip()
    tl = t.lower()

    action_signals = [
        "帮我", "帮忙", "具体", "详细", "方案", "设计", "规划", "分析",
        "写一", "做一", "想一", "列一", "给我", "生成", "创建", "总结",
        "怎么做", "怎么实现", "如何实现", "步骤", "流程", "计划",
    ]
    if any(k in tl for k in action_signals):
        return False

    if len(t) <= 10:
        return True

    greeting_only = [
        "嗨", "你好", "hi", "hello", "hey", "谢谢", "thanks", "再见", "bye",
        "哈哈", "ok", "好的", "嗯", "对", "是的", "哦",
    ]
    if len(t) <= 20 and any(k in tl for k in greeting_only):
        return True

    if len(t) <= 50 and any(k in tl for k in ["什么是", "是什么", "含义", "解释一下", "简单说"]):
        return True

    return False


async def persist_chat_result(
    *,
    db: AsyncSession,
    manager: Any,
    session_id: str,
    user_id: str,
    assistant_content: str,
    agent: str | None,
    tools_used: list[str],
    quality_gate_passed: bool | None,
    recalled: list[dict[str, Any]],
    style: str,
    category: str,
) -> None:
    await manager.add_message(
        db,
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        message_type="result",
        metadata={
            "agent": agent,
            "tools_used": tools_used,
            "quality_gate_passed": quality_gate_passed,
        },
    )
    if recalled:
        await manager.add_message(
            db,
            session_id=session_id,
            role="system",
            content=f"召回记忆 {len(recalled)} 条",
            message_type="memory_recall",
        )

    await manager.update_preference(
        db,
        user_id=user_id,
        key="default_style",
        value=style,
        confidence=0.65,
    )
    await manager.update_preference(
        db,
        user_id=user_id,
        key="favorite_category",
        value=category,
        confidence=0.65,
    )


def build_chat_response_payload(
    *,
    success: bool,
    session_id: str,
    assistant_content: str,
    agent: str | None,
    tools_used: list[str],
    iterations: int,
    error: str | None,
    timings_ms: dict[str, int],
    recalled: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "success": success,
        "session_id": session_id,
        "assistant": {
            "content": assistant_content,
            "agent": agent,
            "tools_used": tools_used,
            "iterations": iterations,
            "error": error,
            "timings_ms": timings_ms,
        },
        "memory": {
            "used": bool(recalled),
            "recalled_count": len(recalled),
            "recalled": recalled,
        },
    }
