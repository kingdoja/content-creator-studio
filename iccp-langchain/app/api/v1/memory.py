from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    get_optional_current_user,
    is_admin_user,
    resolve_scoped_user_id,
)
from app.config import settings
from app.db.session import get_db_session
from app.memory import get_memory_manager
from app.models.user import User


router = APIRouter()


class MemoryLinkRequest(BaseModel):
    source_type: str = Field(..., min_length=1, max_length=32)
    source_id: str = Field(..., min_length=1, max_length=36)
    target_type: str = Field(..., min_length=1, max_length=32)
    target_id: str = Field(..., min_length=1, max_length=36)
    relation: str = Field("related_to", min_length=1, max_length=32)
    strength: float = Field(0.5, ge=0.0, le=1.0)


class UpdatePreferenceRequest(BaseModel):
    user_id: str = Field(default="anonymous", max_length=64)
    key: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., min_length=1, max_length=2000)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)


def _normalize_memory_types(memory_types: Optional[str]) -> list[str] | None:
    if not memory_types:
        return None
    values = [item.strip() for item in memory_types.split(",") if item.strip()]
    return values or None


def _assert_admin(current_user: User) -> None:
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可访问该接口")


@router.get("/recall")
async def recall_memories(
    query: str,
    user_id: str = "anonymous",
    memory_types: Optional[str] = None,
    top_k: int = 5,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    query = (query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    recalled = await manager.recall(
        db,
        query=query,
        user_id=scoped_user_id,
        memory_types=_normalize_memory_types(memory_types),
        top_k=max(1, min(top_k, 20)),
    )
    return {"success": True, "items": recalled}


@router.get("/entries")
async def list_memory_entries(
    user_id: str = "anonymous",
    memory_type: Optional[str] = None,
    source_module: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    try:
        created_from_dt = datetime.fromisoformat(created_from) if created_from else None
        created_to_dt = datetime.fromisoformat(created_to) if created_to else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"时间格式错误: {exc}") from exc

    entries = await manager.list_memory_entries(
        db,
        user_id=scoped_user_id,
        memory_type=memory_type,
        source_module=source_module,
        created_from=created_from_dt,
        created_to=created_to_dt,
        offset=offset,
        limit=limit,
    )
    total = await manager.count_memory_entries(
        db,
        user_id=scoped_user_id,
        memory_type=memory_type,
        source_module=source_module,
        created_from=created_from_dt,
        created_to=created_to_dt,
    )
    return {
        "success": True,
        "entries": entries,
        "pagination": {
            "total": total,
            "offset": max(0, offset),
            "limit": max(1, min(limit, 200)),
            "has_more": max(0, offset) + max(1, min(limit, 200)) < total,
        },
    }


@router.delete("/entries/{entry_id}")
async def delete_memory_entry(
    entry_id: str,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    deleted = await manager.delete_memory_entry(
        db, entry_id=entry_id, user_id=scoped_user_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="记忆条目不存在")
    return {"success": True, "deleted": True}


@router.get("/entries/{entry_id}")
async def get_memory_entry(
    entry_id: str,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    entry = await manager.get_memory_entry(
        db, entry_id=entry_id, user_id=scoped_user_id
    )
    if not entry:
        raise HTTPException(status_code=404, detail="记忆条目不存在")
    return {"success": True, "entry": entry}


@router.get("/stats")
async def memory_stats(
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    stats = await manager.memory_stats(db, user_id=scoped_user_id)
    return {"success": True, "stats": stats}


@router.get("/config")
async def memory_config(current_user: User = Depends(get_current_user)):
    _assert_admin(current_user)
    return {
        "success": True,
        "config": {
            "memory_recall_timeout_seconds": settings.MEMORY_RECALL_TIMEOUT_SECONDS,
            "video_polish_timeout_seconds": settings.VIDEO_POLISH_TIMEOUT_SECONDS,
        },
    }


@router.post("/links")
async def create_memory_link(
    request: MemoryLinkRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    _assert_admin(current_user)
    manager = get_memory_manager()
    link = await manager.link_memories(
        db,
        source_type=request.source_type,
        source_id=request.source_id,
        target_type=request.target_type,
        target_id=request.target_id,
        relation=request.relation,
        strength=request.strength,
    )
    return {"success": True, "link": link}


@router.get("/related")
async def get_related_memories(
    source_type: str,
    source_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    _assert_admin(current_user)
    manager = get_memory_manager()
    related = await manager.get_related_memories(
        db,
        source_type=source_type,
        source_id=source_id,
        limit=limit,
    )
    return {"success": True, "items": related}


@router.get("/links")
async def list_memory_links(
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    relation: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    _assert_admin(current_user)
    manager = get_memory_manager()
    rows = await manager.store.list_memory_links(
        db,
        source_type=(source_type or None),
        source_id=(source_id or None),
        target_type=(target_type or None),
        target_id=(target_id or None),
        relation=(relation or None),
        limit=max(1, min(limit, 200)),
    )
    items = [
        {
            "id": row.id,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "relation": row.relation,
            "strength": row.strength,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]
    return {"success": True, "items": items}


@router.put("/preferences")
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
    return {"success": True}


@router.get("/preferences")
async def get_preferences(
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    manager = get_memory_manager()
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    prefs = await manager.get_preferences(db, user_id=scoped_user_id)
    return {"success": True, "preferences": prefs}
