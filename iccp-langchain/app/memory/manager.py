from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.consolidator import MemoryConsolidator
from app.memory.retriever import MemoryRetriever
from app.memory.store import MemoryStore
from app.memory.summarizer import MemorySummarizer
from app.models.memory import MemoryEntry


class MemoryManager:
    def __init__(self) -> None:
        self.store = MemoryStore()
        self.summarizer = MemorySummarizer()
        self.retriever = MemoryRetriever(self.store)
        self.consolidator = MemoryConsolidator()

    async def create_session(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        module: str = "chat",
        title: str = "新会话",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        session = await self.store.create_session(
            db, user_id=user_id, module=module, title=title, metadata=metadata
        )
        return self._session_to_dict(session)

    async def list_sessions(
        self, db: AsyncSession, *, user_id: str, module: str = "chat", limit: int = 20
    ) -> list[dict[str, Any]]:
        sessions = await self.store.list_sessions(db, user_id=user_id, module=module, limit=limit)
        return [self._session_to_dict(s) for s in sessions]

    async def get_session(self, db: AsyncSession, *, session_id: str) -> dict[str, Any] | None:
        session = await self.store.get_session(db, session_id=session_id)
        return self._session_to_dict(session) if session else None

    async def add_message(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        message = await self.store.add_message(
            db,
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata=metadata,
        )
        return self._message_to_dict(message)

    async def get_session_history(
        self, db: AsyncSession, *, session_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        messages = await self.store.get_session_messages(db, session_id=session_id, limit=limit)
        return [self._message_to_dict(m) for m in messages]

    async def recall(
        self,
        db: AsyncSession,
        *,
        query: str,
        user_id: str,
        memory_types: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        return await self.retriever.recall(
            db,
            user_id=user_id,
            query=query,
            memory_types=memory_types,
            top_k=top_k,
        )

    async def close_session(self, db: AsyncSession, *, session_id: str) -> dict[str, Any] | None:
        session = await self.store.get_session(db, session_id=session_id)
        if not session:
            return None
        history = await self.get_session_history(db, session_id=session_id, limit=200)
        summary = await self.summarizer.summarize_messages(history) if history else ""
        session.summary = summary
        session.is_active = False
        session.updated_at = datetime.utcnow()
        await db.commit()

        if summary:
            await self.store.create_memory_entry(
                db,
                user_id=session.user_id,
                memory_type="episodic",
                source_module=session.module,
                source_id=session.id,
                content=summary,
                importance=0.6,
                tags=[session.module, "session_summary"],
            )
            await self.consolidate(db, user_id=session.user_id)
        return self._session_to_dict(session)

    async def delete_session(self, db: AsyncSession, *, session_id: str) -> bool:
        return await self.store.delete_session(db, session_id=session_id)

    async def consolidate(self, db: AsyncSession, *, user_id: str) -> dict[str, Any]:
        return await self.consolidator.consolidate(db, user_id=user_id)

    async def link_memories(
        self,
        db: AsyncSession,
        *,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relation: str = "related_to",
        strength: float = 0.5,
    ) -> dict[str, Any]:
        link = await self.store.create_memory_link(
            db,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation=relation,
            strength=strength,
        )
        return {
            "id": link.id,
            "source_type": link.source_type,
            "source_id": link.source_id,
            "target_type": link.target_type,
            "target_id": link.target_id,
            "relation": link.relation,
            "strength": link.strength,
            "created_at": link.created_at.isoformat() if link.created_at else "",
        }

    async def get_related_memories(
        self,
        db: AsyncSession,
        *,
        source_type: str,
        source_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        links = await self.store.list_memory_links(
            db,
            source_type=source_type,
            source_id=source_id,
            target_type="memory_entry",
            limit=limit,
        )
        if not links:
            return []

        target_ids = [item.target_id for item in links]
        rows = (
            await db.execute(select(MemoryEntry).where(MemoryEntry.id.in_(target_ids)))
        ).scalars().all()
        row_map = {row.id: row for row in rows}
        result: list[dict[str, Any]] = []
        for link in links:
            entry = row_map.get(link.target_id)
            if not entry:
                continue
            result.append(
                {
                    "link_id": link.id,
                    "relation": link.relation,
                    "strength": link.strength,
                    "memory": {
                        "id": entry.id,
                        "memory_type": entry.memory_type,
                        "source_module": entry.source_module,
                        "source_id": entry.source_id,
                        "content": entry.content,
                        "importance": entry.importance,
                        "created_at": entry.created_at.isoformat() if entry.created_at else "",
                    },
                }
            )
        return result

    async def update_preference(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        key: str,
        value: str,
        confidence: float = 0.6,
    ) -> None:
        await self.store.upsert_preference(
            db, user_id=user_id, key=key, value=value, confidence=confidence
        )

    async def get_preferences(self, db: AsyncSession, *, user_id: str) -> dict[str, Any]:
        return await self.store.get_preferences(db, user_id=user_id)

    async def list_memory_entries(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        memory_type: str | None = None,
        source_module: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = await self.store.list_memory_entries(
            db,
            user_id=user_id,
            memory_type=memory_type,
            source_module=source_module,
            created_from=created_from,
            created_to=created_to,
            offset=offset,
            limit=limit,
        )
        return [
            {
                "id": item.id,
                "user_id": item.user_id,
                "memory_type": item.memory_type,
                "source_module": item.source_module,
                "source_id": item.source_id,
                "content": item.content,
                "importance": item.importance,
                "access_count": item.access_count,
                "created_at": item.created_at.isoformat() if item.created_at else "",
                "last_accessed_at": item.last_accessed_at.isoformat() if item.last_accessed_at else "",
            }
            for item in rows
        ]

    async def get_memory_entry(
        self,
        db: AsyncSession,
        *,
        entry_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        item = await self.store.get_memory_entry(db, entry_id=entry_id, user_id=user_id)
        if not item:
            return None
        return {
            "id": item.id,
            "user_id": item.user_id,
            "memory_type": item.memory_type,
            "source_module": item.source_module,
            "source_id": item.source_id,
            "content": item.content,
            "importance": item.importance,
            "access_count": item.access_count,
            "created_at": item.created_at.isoformat() if item.created_at else "",
            "last_accessed_at": item.last_accessed_at.isoformat() if item.last_accessed_at else "",
        }

    async def count_memory_entries(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        memory_type: str | None = None,
        source_module: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> int:
        return await self.store.count_memory_entries(
            db,
            user_id=user_id,
            memory_type=memory_type,
            source_module=source_module,
            created_from=created_from,
            created_to=created_to,
        )

    async def delete_memory_entry(self, db: AsyncSession, *, entry_id: str, user_id: str) -> bool:
        return await self.store.delete_memory_entry(db, entry_id=entry_id, user_id=user_id)

    async def memory_stats(self, db: AsyncSession, *, user_id: str) -> dict[str, Any]:
        return await self.store.memory_stats(db, user_id=user_id)

    @staticmethod
    def _session_to_dict(session: Any) -> dict[str, Any]:
        return {
            "id": session.id,
            "user_id": session.user_id,
            "title": session.title,
            "module": session.module,
            "summary": session.summary,
            "is_active": session.is_active,
            "created_at": session.created_at.isoformat() if session.created_at else "",
            "updated_at": session.updated_at.isoformat() if session.updated_at else "",
        }

    @staticmethod
    def _message_to_dict(message: Any) -> dict[str, Any]:
        return {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "message_type": message.message_type,
            "created_at": message.created_at.isoformat() if message.created_at else "",
        }


_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
