import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class VectorIndex:
    """向量索引抽象：支持 memory 与 milvus 两种后端。"""

    def __init__(self) -> None:
        self.backend = (settings.RAG_VECTOR_BACKEND or "memory").strip().lower()
        self._milvus_ready = False
        self._milvus = None
        if self.backend == "milvus":
            self._init_milvus()

    def _init_milvus(self) -> None:
        try:
            from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=str(settings.MILVUS_PORT),
            )
            collection_name = settings.RAG_MILVUS_COLLECTION
            if not utility.has_collection(collection_name):
                fields = [
                    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=36),
                    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
                ]
                schema = CollectionSchema(fields=fields, description="Knowledge chunk vectors")
                collection = Collection(name=collection_name, schema=schema)
                collection.create_index(
                    field_name="embedding",
                    index_params={
                        "index_type": "HNSW",
                        "metric_type": settings.RAG_MILVUS_METRIC,
                        "params": {"M": 16, "efConstruction": 200},
                    },
                )
            self._milvus = Collection(name=collection_name)
            self._milvus.load()
            self._milvus_ready = True
            logger.info("Milvus vector index enabled: collection=%s", collection_name)
        except Exception as e:
            self._milvus_ready = False
            self.backend = "memory"
            logger.warning("Milvus init failed, fallback to memory backend: %s", e)

    async def upsert(self, *, chunk_id: str, document_id: str, embedding: list[float] | None) -> None:
        if not embedding:
            return
        if self.backend != "milvus" or not self._milvus_ready or not self._milvus:
            return
        try:
            self._milvus.upsert([[chunk_id], [document_id], [embedding]])
        except Exception as e:
            logger.warning("Milvus upsert failed for chunk=%s: %s", chunk_id, e)

    async def search(self, *, query_embedding: list[float] | None, top_k: int) -> list[dict[str, Any]]:
        if not query_embedding:
            return []
        if self.backend != "milvus" or not self._milvus_ready or not self._milvus:
            return []
        try:
            result = self._milvus.search(
                data=[query_embedding],
                anns_field="embedding",
                limit=max(1, min(top_k, 50)),
                output_fields=["chunk_id", "document_id"],
                param={"metric_type": settings.RAG_MILVUS_METRIC, "params": {"ef": 128}},
            )
            hits = []
            for hit in (result[0] if result else []):
                hits.append(
                    {
                        "chunk_id": str(hit.entity.get("chunk_id")),
                        "document_id": str(hit.entity.get("document_id")),
                        "score": round(float(hit.score), 4),
                    }
                )
            return hits
        except Exception as e:
            logger.warning("Milvus search failed, fallback to memory scoring: %s", e)
            return []
