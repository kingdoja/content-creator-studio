from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.store import MemoryStore


class MemoryRetriever:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def recall(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        query: str,
        memory_types: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        return await self.store.recall_memories(
            db,
            user_id=user_id,
            query=query,
            memory_types=memory_types,
            top_k=top_k,
        )
