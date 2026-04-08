import logging
import math
from typing import List

import httpx
from langchain_openai import OpenAIEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self._openai = None
        self._embedding_disabled = False
        self._use_direct_api = False

        if settings.OPENAI_API_KEY:
            model_name = settings.RAG_EMBEDDING_MODEL
            # DashScope 的 OpenAI 兼容层常见可用模型为 text-embedding-v3；
            # 当沿用 OpenAI 默认模型名时，自动回退，避免 404。
            if "dashscope.aliyuncs.com" in (settings.LLM_BASE_URL or "") and model_name == "text-embedding-3-small":
                model_name = "text-embedding-v3"
                self._use_direct_api = True  # 使用直接 API 调用避免参数格式问题

            self._model_name = model_name

            if not self._use_direct_api:
                self._openai = OpenAIEmbeddings(
                    model=model_name,
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.LLM_BASE_URL if settings.LLM_BASE_URL != "https://api.openai.com/v1" else None,
                )

    async def embed_text(self, text: str) -> List[float] | None:
        if not text.strip():
            return None

        if self._embedding_disabled:
            return None
            
        try:
            if self._use_direct_api:
                # 直接调用阿里云 DashScope API
                return await self._embed_with_dashscope(text)
            elif self._openai:
                return await self._openai.aembed_query(text)
        except Exception as e:
            # 避免持续请求失败端点导致日志刷屏，失败后自动降级到关键词检索。
            self._embedding_disabled = True
            logger.warning("Embedding endpoint failed, fallback to keyword retrieval: %s", e)
            return None
        
        return None
    
    async def _embed_with_dashscope(self, text: str) -> List[float] | None:
        """直接调用阿里云 DashScope embedding API"""
        url = f"{settings.LLM_BASE_URL}/embeddings"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self._model_name,
            "input": text  # 阿里云期望的是 input 字段，值为字符串
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # 提取 embedding 向量
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
            
            return None

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)
