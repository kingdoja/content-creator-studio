import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_optional_current_user,
    is_admin_user,
    resolve_scoped_user_id,
)
from app.agents.graph import get_content_creation_graph
from app.agents.router import get_agent_router
from app.config import settings
from app.db.session import get_db_session
from app.memory import get_memory_manager
from app.models.user import User
from app.services.chat_session_service import (
    append_chat_user_message,
    build_chat_response_payload,
    load_owned_session_or_403,
    persist_chat_result,
    prepare_chat_generation_context,
)
import time
import logging


router = APIRouter()
logger = logging.getLogger(__name__)


class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="anonymous", max_length=64)
    module: str = Field(default="chat", max_length=32)
    title: str = Field(default="新会话", max_length=255)
    metadata: Optional[dict[str, Any]] = None


class SendMessageRequest(BaseModel):
    user_id: str = Field(default="anonymous", max_length=64)
    content: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(default="ai", max_length=64)
    style: str = Field(default="professional", max_length=32)
    length: str = Field(default="medium", max_length=16)
    requirements: Optional[str] = Field(default="", max_length=1000)
    use_memory: bool = False
    memory_top_k: int = Field(default=4, ge=1, le=10)
    force_simple: bool = False


class UpdatePreferenceRequest(BaseModel):
    user_id: str = Field(default="anonymous", max_length=64)
    key: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., min_length=1, max_length=2000)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(request.user_id, current_user)
    session = await manager.create_session(
        db,
        user_id=scoped_user_id,
        module=request.module.strip() or "chat",
        title=request.title.strip() or "新会话",
        metadata=request.metadata or {},
    )
    return {"success": True, "session": session}


@router.get("/sessions")
async def list_sessions(
    user_id: str = "anonymous",
    module: str = "chat",
    limit: int = 20,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    sessions = await manager.list_sessions(
        db,
        user_id=scoped_user_id,
        module=(module or "chat").strip() or "chat",
        limit=limit,
    )
    return {"success": True, "sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    session = await manager.get_session(db, session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if current_user and session.get("user_id") != current_user.id and not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    return {"success": True, "session": session}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    session = await manager.get_session(db, session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if current_user and session.get("user_id") != current_user.id and not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    messages = await manager.get_session_history(db, session_id=session_id, limit=limit)
    return {"success": True, "messages": messages}


@router.post("/sessions/{session_id}/message")
async def send_session_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    started_at = time.perf_counter()
    timings_ms: dict[str, int] = {}
    manager = get_memory_manager()

    user_id = resolve_scoped_user_id(request.user_id, current_user)
    await load_owned_session_or_403(
        db=db,
        manager=manager,
        session_id=session_id,
        user_id=user_id,
    )

    user_content = request.content.strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    await append_chat_user_message(
        db=db,
        manager=manager,
        session_id=session_id,
        user_content=user_content,
    )

    task, recalled, prefs, llm_model_override = await prepare_chat_generation_context(
        db=db,
        manager=manager,
        request=request,
        session_id=session_id,
        user_id=user_id,
        user_content=user_content,
        timings_ms=timings_ms,
    )
    route_started_at = time.perf_counter()
    result = await get_agent_router().route(
        task,
        context={
            "user_id": user_id,
            "session_id": session_id,
            "llm_model_override": llm_model_override,
            "use_memory": False,
            "recalled_memories": recalled,
            "user_preferences": prefs,
        },
    )
    timings_ms["agent_route"] = int((time.perf_counter() - route_started_at) * 1000)

    assistant_content = result.get("content", "")
    persist_started_at = time.perf_counter()
    await persist_chat_result(
        db=db,
        manager=manager,
        session_id=session_id,
        user_id=user_id,
        assistant_content=assistant_content,
        agent=result.get("agent"),
        tools_used=result.get("tools_used", []),
        quality_gate_passed=result.get("quality_gate_passed"),
        recalled=recalled,
        style=request.style,
        category=request.category,
    )
    timings_ms["persist"] = int((time.perf_counter() - persist_started_at) * 1000)
    timings_ms["total"] = int((time.perf_counter() - started_at) * 1000)
    logger.info(
        "chat session=%s user=%s agent=%s timings_ms=%s",
        session_id,
        user_id,
        result.get("agent"),
        timings_ms,
    )

    return build_chat_response_payload(
        success=result.get("success", False),
        session_id=session_id,
        assistant_content=assistant_content,
        agent=result.get("agent"),
        tools_used=result.get("tools_used", []),
        iterations=result.get("iterations", 0),
        error=result.get("error"),
        timings_ms=timings_ms,
        recalled=recalled,
    )


@router.post("/sessions/{session_id}/message/stream")
async def send_session_message_stream(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    started_at = time.perf_counter()
    timings_ms: dict[str, int] = {}
    manager = get_memory_manager()

    user_id = resolve_scoped_user_id(request.user_id, current_user)
    await load_owned_session_or_403(
        db=db,
        manager=manager,
        session_id=session_id,
        user_id=user_id,
    )

    user_content = request.content.strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    await append_chat_user_message(
        db=db,
        manager=manager,
        session_id=session_id,
        user_content=user_content,
    )

    task, recalled, prefs, llm_model_override = await prepare_chat_generation_context(
        db=db,
        manager=manager,
        request=request,
        session_id=session_id,
        user_id=user_id,
        user_content=user_content,
        timings_ms=timings_ms,
    )
    graph = get_content_creation_graph()

    async def event_generator():
        latest_state: Dict[str, Any] = {}
        yield _sse("start", {"message": "chat stream started"})
        try:
            route_started_at = time.perf_counter()
            async for update in graph.astream(
                {
                    "task": task,
                    "user_id": user_id,
                    "session_id": session_id,
                    "llm_model_override": llm_model_override,
                    "use_memory": False,
                    "memory_top_k": request.memory_top_k,
                    "recalled_memories": recalled,
                    "user_preferences": prefs,
                },
                stream_mode="updates",
            ):
                for node_name, payload in update.items():
                    if isinstance(payload, dict):
                        latest_state.update(payload)
                        if payload.get("content"):
                            yield _sse(
                                "content_chunk",
                                {"content": payload.get("content", ""), "node": node_name},
                            )
                        yield _sse("node_update", {"node": node_name, "keys": list(payload.keys())})
            timings_ms["agent_route"] = int((time.perf_counter() - route_started_at) * 1000)

            assistant_content = latest_state.get("content", "")
            persist_started_at = time.perf_counter()
            await persist_chat_result(
                db=db,
                manager=manager,
                session_id=session_id,
                user_id=user_id,
                assistant_content=assistant_content,
                agent=latest_state.get("agent"),
                tools_used=latest_state.get("tools_used", []),
                quality_gate_passed=latest_state.get("quality_gate_passed"),
                recalled=recalled,
                style=request.style,
                category=request.category,
            )
            timings_ms["persist"] = int((time.perf_counter() - persist_started_at) * 1000)
            timings_ms["total"] = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "chat_stream session=%s user=%s agent=%s timings_ms=%s",
                session_id,
                user_id,
                latest_state.get("agent"),
                timings_ms,
            )
            yield _sse(
                "complete",
                build_chat_response_payload(
                    success=latest_state.get("success", False),
                    session_id=session_id,
                    assistant_content=assistant_content,
                    agent=latest_state.get("agent"),
                    tools_used=latest_state.get("tools_used", []),
                    iterations=latest_state.get("iterations", 0),
                    error=latest_state.get("error"),
                    timings_ms=timings_ms,
                    recalled=recalled,
                ),
            )
        except Exception as e:
            yield _sse("error", {"error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    session = await manager.get_session(db, session_id=session_id)
    if session and current_user and session.get("user_id") != current_user.id and not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="无权关闭该会话")
    session = await manager.close_session(db, session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"success": True, "session": session}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    await load_owned_session_or_403(
        db=db,
        manager=manager,
        session_id=session_id,
        user_id=scoped_user_id,
    )
    ok = await manager.delete_session(db, session_id=session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"success": True, "session_id": session_id}


@router.post("/preferences")
async def update_preference(
    request: UpdatePreferenceRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(request.user_id, current_user)
    await manager.update_preference(
        db,
        user_id=scoped_user_id,
        key=request.key.strip(),
        value=request.value.strip(),
        confidence=request.confidence,
    )
    return {
        "success": True,
        "deprecated": True,
        "use": "/api/v1/memory/preferences",
    }


@router.get("/preferences")
async def get_preferences(
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    prefs = await manager.get_preferences(db, user_id=scoped_user_id)
    return {
        "success": True,
        "preferences": prefs,
        "deprecated": True,
        "use": "/api/v1/memory/preferences",
    }
