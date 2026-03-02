import json
import math
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.memory import get_memory_manager
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.rag.embeddings import EmbeddingService
from app.rag.text_splitter import split_text
from app.rag.vector_index import VectorIndex


class KnowledgeService:
    def __init__(self) -> None:
        self.embedding = EmbeddingService()
        self.vector_index = VectorIndex()

    async def add_document(
        self,
        db: AsyncSession,
        *,
        title: str,
        content: str,
        source_type: str = "text",
        source_uri: str | None = None,
    ) -> Dict[str, Any]:
        title = title.strip()
        content = content.strip()
        if not title or not content:
            raise ValueError("title 和 content 不能为空")

        chunks = split_text(
            content,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        )
        doc = KnowledgeDocument(
            title=title,
            content=content,
            source_type=source_type,
            source_uri=source_uri,
            chunk_count=len(chunks),
        )
        db.add(doc)
        await db.flush()

        chunk_rows: list[KnowledgeChunk] = []
        chunk_embeddings: dict[str, list[float]] = {}
        for idx, chunk in enumerate(chunks):
            embedding = await self.embedding.embed_text(chunk)
            row = KnowledgeChunk(
                document_id=doc.id,
                chunk_index=idx,
                content=chunk,
                embedding_json=json.dumps(embedding, ensure_ascii=False) if embedding else None,
            )
            db.add(row)
            chunk_rows.append(row)
            if embedding:
                chunk_embeddings[str(idx)] = embedding
        await db.flush()

        # 向量索引写入与主流程解耦：失败时回退到 DB 内存检索。
        for row in chunk_rows:
            embedding = chunk_embeddings.get(str(row.chunk_index))
            if not embedding:
                continue
            await self.vector_index.upsert(
                chunk_id=row.id,
                document_id=doc.id,
                embedding=embedding,
            )
        await db.commit()

        # 将知识上传沉淀为 semantic 记忆，供跨模块召回使用。
        try:
            summary = f"知识标题：{doc.title}\n知识摘要：{content[:400]}"
            await get_memory_manager().store.create_memory_entry(
                db,
                user_id="anonymous",
                memory_type="semantic",
                source_module="knowledge",
                source_id=doc.id,
                content=summary,
                importance=0.7,
                tags=[source_type or "text", "knowledge_upload"],
            )
        except Exception:
            # 记忆沉淀失败不影响知识上传主流程。
            pass

        return {
            "id": doc.id,
            "title": doc.title,
            "chunk_count": doc.chunk_count,
            "source_type": doc.source_type,
        }

    async def list_documents(self, db: AsyncSession) -> List[Dict[str, Any]]:
        rows = await db.execute(
            select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
        )
        docs = rows.scalars().all()
        return [
            {
                "id": d.id,
                "title": d.title,
                "source_type": d.source_type,
                "source_uri": d.source_uri,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]

    async def delete_document(self, db: AsyncSession, doc_id: str) -> bool:
        rows = await db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
        doc = rows.scalar_one_or_none()
        if not doc:
            return False
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id))
        await db.delete(doc)
        await db.commit()
        return True

    async def search(self, db: AsyncSession, query: str, top_k: int | None = None) -> List[Dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        top_k = top_k or settings.RAG_TOP_K
        now = datetime.utcnow()

        query_embedding = await self.embedding.embed_text(query)
        vector_candidate_multiplier = max(1, int(settings.RAG_VECTOR_CANDIDATE_MULTIPLIER or 5))
        vector_top_k = max(top_k, min(top_k * vector_candidate_multiplier, 100))
        milvus_hits = await self.vector_index.search(query_embedding=query_embedding, top_k=vector_top_k)
        if milvus_hits:
            hit_chunk_ids = [item["chunk_id"] for item in milvus_hits if item.get("chunk_id")]
            rows = await db.execute(
                select(KnowledgeChunk)
                .options(selectinload(KnowledgeChunk.document))
                .where(KnowledgeChunk.id.in_(hit_chunk_ids))
            )
            chunk_map = {row.id: row for row in rows.scalars().all()}
            ordered_results: List[Dict[str, Any]] = []
            for hit in milvus_hits:
                chunk = chunk_map.get(hit["chunk_id"])
                if not chunk:
                    continue
                semantic_score = self._normalize_semantic_score(hit.get("score", 0.0))
                recency_score = self._recency_score(
                    chunk.document.created_at if chunk.document and chunk.document.created_at else chunk.created_at,
                    now=now,
                )
                final_score = self._blend_semantic_and_recency(semantic_score, recency_score)
                ordered_results.append(
                    {
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "document_title": chunk.document.title if chunk.document else "",
                        "content": chunk.content,
                        "score": round(final_score, 4),
                        "semantic_score": round(semantic_score, 4),
                        "recency_score": round(recency_score, 4),
                        "document_created_at": (
                            chunk.document.created_at.isoformat()
                            if chunk.document and chunk.document.created_at
                            else ""
                        ),
                    }
                )
            if ordered_results:
                ordered_results.sort(key=lambda x: x["score"], reverse=True)
                return ordered_results[:top_k]

        candidate_limit = max(50, min(int(settings.RAG_SEARCH_CANDIDATE_LIMIT or 400), 5000))
        rows = await db.execute(
            select(KnowledgeChunk)
            .options(selectinload(KnowledgeChunk.document))
            .order_by(desc(KnowledgeChunk.created_at))
            .limit(candidate_limit)
        )
        chunks = rows.scalars().all()

        scored: List[Dict[str, Any]] = []
        for chunk in chunks:
            score = 0.0
            if query_embedding and chunk.embedding_json:
                try:
                    vec = json.loads(chunk.embedding_json)
                except Exception:
                    vec = None
                if vec:
                    score = EmbeddingService.cosine_similarity(query_embedding, vec)
            else:
                # 无 embedding 时的降级策略：简单关键词重叠打分
                score = self._keyword_overlap_score(query, chunk.content)
            semantic_score = self._normalize_semantic_score(score)
            recency_score = self._recency_score(
                chunk.document.created_at if chunk.document and chunk.document.created_at else chunk.created_at,
                now=now,
            )
            final_score = self._blend_semantic_and_recency(semantic_score, recency_score)

            scored.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_title": chunk.document.title if chunk.document else "",
                    "content": chunk.content,
                    "score": round(float(final_score), 4),
                    "semantic_score": round(float(semantic_score), 4),
                    "recency_score": round(float(recency_score), 4),
                    "document_created_at": (
                        chunk.document.created_at.isoformat()
                        if chunk.document and chunk.document.created_at
                        else ""
                    ),
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def stats(self, db: AsyncSession) -> Dict[str, Any]:
        doc_count = await db.scalar(select(func.count()).select_from(KnowledgeDocument))
        chunk_count = await db.scalar(select(func.count()).select_from(KnowledgeChunk))
        return {
            "documents": int(doc_count or 0),
            "chunks": int(chunk_count or 0),
        }

    @staticmethod
    def _keyword_overlap_score(query: str, text: str) -> float:
        q_tokens = {t for t in query.lower().split() if t}
        t_tokens = {t for t in text.lower().split() if t}
        if not q_tokens or not t_tokens:
            return 0.0
        overlap = len(q_tokens & t_tokens)
        return overlap / len(q_tokens)

    @staticmethod
    def _normalize_semantic_score(score: float) -> float:
        """统一将不同来源的相似度分数归一到 [0, 1] 区间。"""
        s = float(score or 0.0)
        if -1.0 <= s <= 1.0:
            return max(0.0, min(1.0, (s + 1.0) / 2.0))
        return max(0.0, min(1.0, s))

    @staticmethod
    def _recency_score(created_at: datetime | None, *, now: datetime) -> float:
        """基于文档时间计算新鲜度分数（指数衰减，越新越接近 1）。"""
        if not created_at:
            return 0.3
        age_seconds = max(0.0, (now - created_at).total_seconds())
        age_days = age_seconds / 86400.0
        decay_days = max(1, int(settings.RAG_TIME_DECAY_DAYS or 180))
        return float(math.exp(-age_days / decay_days))

    @staticmethod
    def _blend_semantic_and_recency(semantic_score: float, recency_score: float) -> float:
        if not bool(settings.RAG_TIME_WEIGHT_ENABLED):
            return semantic_score
        alpha = float(settings.RAG_TIME_WEIGHT_ALPHA or 0.25)
        alpha = max(0.0, min(0.7, alpha))
        return (1.0 - alpha) * semantic_score + alpha * recency_score


knowledge_service = KnowledgeService()
