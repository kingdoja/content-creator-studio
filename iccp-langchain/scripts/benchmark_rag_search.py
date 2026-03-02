"""
RAG 检索性能基准（开发自测脚本）

用法：
1) 激活环境并启动数据库可用配置
2) python scripts/benchmark_rag_search.py
"""
import asyncio
import statistics
import time

from app.db.session import AsyncSessionLocal
from app.rag.knowledge_service import knowledge_service


QUERIES = [
    "AI agent 架构设计最佳实践",
    "如何做多轮对话记忆增强",
    "向量检索和关键词检索怎么融合",
    "内容创作流程中的质量门控",
]


async def main() -> None:
    timings_ms: list[float] = []
    async with AsyncSessionLocal() as db:
        for query in QUERIES:
            started = time.perf_counter()
            _ = await knowledge_service.search(db, query=query, top_k=4)
            elapsed = (time.perf_counter() - started) * 1000
            timings_ms.append(elapsed)
            print(f"query={query} elapsed_ms={elapsed:.2f}")

    if not timings_ms:
        print("no timings")
        return

    print("\n=== RAG Search Benchmark ===")
    print(f"count={len(timings_ms)}")
    print(f"avg_ms={statistics.mean(timings_ms):.2f}")
    print(f"p95_ms={max(timings_ms):.2f}")


if __name__ == "__main__":
    asyncio.run(main())
