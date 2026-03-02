import json
import math
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryEntry
from app.rag.embeddings import EmbeddingService


class MemoryConsolidator:
    """记忆整合：去重、衰减、强化、压缩。"""

    def __init__(self) -> None:
        self._lambda = 0.05
        self._dedup_threshold = 0.92
        self._prune_threshold = 0.05

    async def consolidate(self, db: AsyncSession, *, user_id: str, limit: int = 300) -> dict[str, Any]:
        stmt = (
            select(MemoryEntry)
            .where(MemoryEntry.user_id == user_id)
            .order_by(desc(MemoryEntry.created_at))
            .limit(max(50, min(limit, 1000)))
        )
        entries = list((await db.execute(stmt)).scalars().all())
        if not entries:
            return {"merged": 0, "pruned": 0, "boosted": 0, "compressed": 0}

        merged = await self._merge_duplicates(db, entries)
        pruned, boosted, compressed = self._decay_boost_and_compress(entries)
        await db.commit()
        return {
            "merged": merged,
            "pruned": pruned,
            "boosted": boosted,
            "compressed": compressed,
        }

    async def _merge_duplicates(self, db: AsyncSession, entries: list[MemoryEntry]) -> int:
        removed_ids: set[str] = set()
        merged_count = 0

        for i, base in enumerate(entries):
            if base.id in removed_ids:
                continue
            for j in range(i + 1, len(entries)):
                other = entries[j]
                if other.id in removed_ids or base.id == other.id:
                    continue
                if base.memory_type != other.memory_type:
                    continue

                similarity = self._similarity(base, other)
                if similarity < self._dedup_threshold:
                    continue

                self._merge_into_base(base, other)
                removed_ids.add(other.id)
                await db.delete(other)
                merged_count += 1

        return merged_count

    def _decay_boost_and_compress(self, entries: list[MemoryEntry]) -> tuple[int, int, int]:
        now = datetime.utcnow()
        pruned = 0
        boosted = 0
        compressed = 0

        for entry in entries:
            if entry.importance is None:
                entry.importance = 0.5
            if entry.access_count is None:
                entry.access_count = 0
            if entry.last_accessed_at is None:
                entry.last_accessed_at = entry.created_at or now

            days = max(0, (now - entry.last_accessed_at).days)
            recency = math.exp(-self._lambda * days)
            score = float(entry.importance) * recency
            if score < self._prune_threshold:
                entry.importance = max(0.0, float(entry.importance) * 0.85)
                pruned += 1

            if entry.access_count > 10 and float(entry.importance) < 0.95:
                entry.importance = min(1.0, float(entry.importance) + 0.1)
                boosted += 1

            if entry.memory_type == "episodic" and len(entry.content or "") > 1200:
                entry.content = self._compress_text(entry.content or "")
                compressed += 1

        return pruned, boosted, compressed

    def _similarity(self, left: MemoryEntry, right: MemoryEntry) -> float:
        left_vec = self._parse_vector(left.embedding_json)
        right_vec = self._parse_vector(right.embedding_json)
        if left_vec and right_vec:
            return float(EmbeddingService.cosine_similarity(left_vec, right_vec))
        return self._keyword_overlap(left.content or "", right.content or "")

    @staticmethod
    def _parse_vector(raw: str | None) -> list[float] | None:
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return [float(x) for x in parsed]
        except Exception:
            return None
        return None

    @staticmethod
    def _keyword_overlap(a: str, b: str) -> float:
        a_tokens = {t for t in a.lower().split() if t}
        b_tokens = {t for t in b.lower().split() if t}
        if not a_tokens or not b_tokens:
            return 0.0
        return len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))

    @staticmethod
    def _merge_into_base(base: MemoryEntry, other: MemoryEntry) -> None:
        base.importance = min(1.0, max(float(base.importance or 0), float(other.importance or 0)))
        base.access_count = int(base.access_count or 0) + int(other.access_count or 0)
        if other.last_accessed_at and (
            not base.last_accessed_at or other.last_accessed_at > base.last_accessed_at
        ):
            base.last_accessed_at = other.last_accessed_at

        base_text = (base.content or "").strip()
        other_text = (other.content or "").strip()
        if other_text and other_text not in base_text:
            if not base_text:
                base.content = other_text
            elif len(base_text) < 800:
                base.content = f"{base_text}\n\n{other_text[:400]}"

    @staticmethod
    def _compress_text(text: str, max_chars: int = 900) -> str:
        text = (text or "").strip()
        if len(text) <= max_chars:
            return text
        head = text[:450].rstrip()
        tail = text[-280:].lstrip()
        return f"{head}\n\n...（中间内容已压缩）...\n\n{tail}"
