import json
import math
from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.memory import (
    ConversationMessage,
    ConversationSession,
    MemoryEntry,
    MemoryLink,
    UserPreference,
)
from app.rag.embeddings import EmbeddingService


class MemoryStore:
    def __init__(self) -> None:
        self.embedding = EmbeddingService()

    async def create_session(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        module: str = "chat",
        title: str = "新会话",
        metadata: dict[str, Any] | None = None,
    ) -> ConversationSession:
        session = ConversationSession(
            user_id=user_id,
            module=module,
            title=title or "新会话",
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def list_sessions(
        self, db: AsyncSession, *, user_id: str, module: str = "chat", limit: int = 20
    ) -> list[ConversationSession]:
        stmt = (
            select(ConversationSession)
            .where(ConversationSession.user_id == user_id, ConversationSession.module == module)
            .order_by(desc(ConversationSession.updated_at))
            .limit(max(1, min(limit, 100)))
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_session(self, db: AsyncSession, *, session_id: str) -> ConversationSession | None:
        return await db.get(ConversationSession, session_id)

    async def delete_session(self, db: AsyncSession, *, session_id: str) -> bool:
        session = await db.get(ConversationSession, session_id)
        if not session:
            return False
        await db.delete(session)
        await db.commit()
        return True

    async def add_message(
        self,
        db: AsyncSession,
        *,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        db.add(message)
        session = await db.get(ConversationSession, session_id)
        if session:
            session.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(message)
        return message

    async def get_session_messages(
        self, db: AsyncSession, *, session_id: str, limit: int = 50
    ) -> list[ConversationMessage]:
        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(desc(ConversationMessage.created_at))
            .limit(max(1, min(limit, 200)))
        )
        rows = list((await db.execute(stmt)).scalars().all())
        rows.reverse()
        return rows

    async def create_memory_entry(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        memory_type: str,
        source_module: str,
        source_id: str,
        content: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> MemoryEntry:
        embedding = await self.embedding.embed_text(content)
        entry = MemoryEntry(
            user_id=user_id,
            memory_type=memory_type,
            source_module=source_module,
            source_id=source_id,
            content=content,
            importance=max(0.0, min(1.0, float(importance))),
            embedding_json=json.dumps(embedding, ensure_ascii=False) if embedding else None,
            tags_json=json.dumps(tags or [], ensure_ascii=False),
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry

    async def recall_memories(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        query: str,
        memory_types: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id)
        if memory_types:
            stmt = stmt.where(MemoryEntry.memory_type.in_(memory_types))
        candidate_limit = max(50, min(int(settings.MEMORY_RECALL_CANDIDATE_LIMIT or 300), 2000))
        stmt = (
            stmt.order_by(desc(MemoryEntry.last_accessed_at), desc(MemoryEntry.created_at))
            .limit(candidate_limit)
        )
        entries = list((await db.execute(stmt)).scalars().all())
        if not entries:
            return []

        query_embedding = await self.embedding.embed_text(query)
        now = datetime.utcnow()
        scored: list[dict[str, Any]] = []
        for entry in entries:
            relevance = 0.0
            if query_embedding and entry.embedding_json:
                try:
                    vec = json.loads(entry.embedding_json)
                except Exception:
                    vec = None
                if vec:
                    relevance = EmbeddingService.cosine_similarity(query_embedding, vec)
            if relevance <= 0:
                relevance = self._keyword_overlap(query, entry.content)

            # 召回打分：相关性 + 时间衰减 + 重要性 + 访问频率
            last_accessed_at = entry.last_accessed_at or entry.created_at or now
            days_since_access = max(0, (now - last_accessed_at).days)
            recency = math.exp(-0.05 * days_since_access)
            frequency = math.log(int(entry.access_count or 0) + 1) / 5.0
            score = round(
                0.4 * float(relevance)
                + 0.25 * float(recency)
                + 0.2 * float(entry.importance or 0.5)
                + 0.15 * float(frequency),
                4,
            )
            scored.append(
                {
                    "id": entry.id,
                    "memory_type": entry.memory_type,
                    "source_module": entry.source_module,
                    "source_id": entry.source_id,
                    "content": entry.content,
                    "importance": entry.importance,
                    "score": score,
                    "created_at": entry.created_at.isoformat() if entry.created_at else "",
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        selected = scored[: max(1, min(top_k, 20))]
        # 召回后更新访问统计，供后续衰减/强化与排序使用。
        selected_ids = {item["id"] for item in selected}
        for entry in entries:
            if entry.id in selected_ids:
                entry.access_count = int(entry.access_count or 0) + 1
                entry.last_accessed_at = now
        if selected_ids:
            await db.commit()
        return selected

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
    ) -> list[MemoryEntry]:
        stmt = select(MemoryEntry).where(MemoryEntry.user_id == user_id)
        if memory_type:
            stmt = stmt.where(MemoryEntry.memory_type == memory_type)
        if source_module:
            stmt = stmt.where(MemoryEntry.source_module == source_module)
        if created_from:
            stmt = stmt.where(MemoryEntry.created_at >= created_from)
        if created_to:
            stmt = stmt.where(MemoryEntry.created_at <= created_to)
        stmt = (
            stmt.order_by(desc(MemoryEntry.created_at))
            .offset(max(0, offset))
            .limit(max(1, min(limit, 200)))
        )
        return list((await db.execute(stmt)).scalars().all())

    async def get_memory_entry(
        self,
        db: AsyncSession,
        *,
        entry_id: str,
        user_id: str,
    ) -> MemoryEntry | None:
        stmt = select(MemoryEntry).where(MemoryEntry.id == entry_id, MemoryEntry.user_id == user_id)
        return (await db.execute(stmt)).scalar_one_or_none()

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
        stmt = select(func.count()).select_from(MemoryEntry).where(MemoryEntry.user_id == user_id)
        if memory_type:
            stmt = stmt.where(MemoryEntry.memory_type == memory_type)
        if source_module:
            stmt = stmt.where(MemoryEntry.source_module == source_module)
        if created_from:
            stmt = stmt.where(MemoryEntry.created_at >= created_from)
        if created_to:
            stmt = stmt.where(MemoryEntry.created_at <= created_to)
        result = await db.scalar(stmt)
        return int(result or 0)

    async def delete_memory_entry(self, db: AsyncSession, *, entry_id: str, user_id: str) -> bool:
        stmt = select(MemoryEntry).where(MemoryEntry.id == entry_id, MemoryEntry.user_id == user_id)
        entry = (await db.execute(stmt)).scalar_one_or_none()
        if not entry:
            return False
        await db.execute(delete(MemoryEntry).where(MemoryEntry.id == entry_id))
        await db.commit()
        return True

    async def memory_stats(self, db: AsyncSession, *, user_id: str) -> dict[str, Any]:
        total = await db.scalar(
            select(func.count()).select_from(MemoryEntry).where(MemoryEntry.user_id == user_id)
        )
        episodic = await db.scalar(
            select(func.count())
            .select_from(MemoryEntry)
            .where(MemoryEntry.user_id == user_id, MemoryEntry.memory_type == "episodic")
        )
        semantic = await db.scalar(
            select(func.count())
            .select_from(MemoryEntry)
            .where(MemoryEntry.user_id == user_id, MemoryEntry.memory_type == "semantic")
        )
        procedural = await db.scalar(
            select(func.count())
            .select_from(MemoryEntry)
            .where(MemoryEntry.user_id == user_id, MemoryEntry.memory_type == "procedural")
        )
        return {
            "total": int(total or 0),
            "episodic": int(episodic or 0),
            "semantic": int(semantic or 0),
            "procedural": int(procedural or 0),
        }

    async def get_preferences(self, db: AsyncSession, *, user_id: str) -> dict[str, Any]:
        rows = (
            await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
        ).scalars().all()
        data: dict[str, Any] = {}
        for item in rows:
            data[item.preference_key] = {
                "value": item.preference_value,
                "confidence": item.confidence,
            }
        return data

    async def upsert_preference(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        key: str,
        value: str,
        confidence: float = 0.6,
    ) -> None:
        stmt = select(UserPreference).where(
            UserPreference.user_id == user_id, UserPreference.preference_key == key
        )
        pref = (await db.execute(stmt)).scalar_one_or_none()
        if pref:
            pref.preference_value = value
            pref.confidence = max(pref.confidence, confidence)
            pref.updated_at = datetime.utcnow()
        else:
            db.add(
                UserPreference(
                    user_id=user_id,
                    preference_key=key,
                    preference_value=value,
                    confidence=max(0.0, min(1.0, confidence)),
                )
            )
        await db.commit()

    async def create_memory_link(
        self,
        db: AsyncSession,
        *,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relation: str = "related_to",
        strength: float = 0.5,
    ) -> MemoryLink:
        stmt = select(MemoryLink).where(
            MemoryLink.source_type == source_type,
            MemoryLink.source_id == source_id,
            MemoryLink.target_type == target_type,
            MemoryLink.target_id == target_id,
            MemoryLink.relation == relation,
        )
        existed = (await db.execute(stmt)).scalar_one_or_none()
        if existed:
            existed.strength = max(float(existed.strength or 0), float(strength or 0))
            await db.commit()
            await db.refresh(existed)
            return existed

        link = MemoryLink(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relation=relation,
            strength=max(0.0, min(1.0, float(strength))),
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return link

    async def list_memory_links(
        self,
        db: AsyncSession,
        *,
        source_type: str | None = None,
        source_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        relation: str | None = None,
        limit: int = 50,
    ) -> list[MemoryLink]:
        stmt = select(MemoryLink)
        if source_type:
            stmt = stmt.where(MemoryLink.source_type == source_type)
        if source_id:
            stmt = stmt.where(MemoryLink.source_id == source_id)
        if target_type:
            stmt = stmt.where(MemoryLink.target_type == target_type)
        if target_id:
            stmt = stmt.where(MemoryLink.target_id == target_id)
        if relation:
            stmt = stmt.where(MemoryLink.relation == relation)
        stmt = stmt.order_by(desc(MemoryLink.created_at)).limit(max(1, min(limit, 200)))
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    def _keyword_overlap(query: str, text: str) -> float:
        q_tokens = {t for t in query.lower().split() if t}
        t_tokens = {t for t in text.lower().split() if t}
        if not q_tokens or not t_tokens:
            return 0.0
        return len(q_tokens & t_tokens) / len(q_tokens)
