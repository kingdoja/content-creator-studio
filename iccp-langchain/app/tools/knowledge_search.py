"""
KnowledgeSearchTool - wraps RAG retrieval as a LangChain-compatible tool.

Encapsulates the knowledge-base search logic previously embedded in rag_agent.py,
exposing it as a reusable tool that ReActAgent and ReflectionAgent can register.

Requirements: 1.1
"""
from __future__ import annotations

from typing import Any, Dict

from app.tools.base import BaseTool, ToolResult


class KnowledgeSearchTool(BaseTool):
    """Search the knowledge base and return formatted knowledge snippets."""

    def __init__(self) -> None:
        super().__init__()
        self.name = "knowledge_search"
        self.description = (
            "搜索知识库，返回与查询最相关的知识片段。"
            "输入：查询字符串。输出：格式化的知识片段文本，包含来源标题和相关度。"
            "当任务需要基于已上传资料回答时使用此工具。"
        )

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Search the knowledge base for the given query.

        Params:
            query (str): The search query string.
            top_k (int, optional): Number of results to return (default 4).
        """
        query = (params.get("query") or "").strip()
        if not query:
            return ToolResult(success=False, error="query 参数不能为空")

        top_k = int(params.get("top_k") or 4)

        try:
            from sqlalchemy import func, select

            from app.db.session import AsyncSessionLocal
            from app.models.knowledge import KnowledgeChunk
            from app.rag.knowledge_service import knowledge_service

            async with AsyncSessionLocal() as db:
                count = await db.scalar(select(func.count()).select_from(KnowledgeChunk))
                if not count:
                    return ToolResult(
                        success=False,
                        error="知识库为空，请先上传资料",
                    )

                results = await knowledge_service.search(db, query=query, top_k=top_k)

            if not results:
                return ToolResult(
                    success=True,
                    data="未找到相关知识片段",
                    metadata={"count": 0},
                )

            formatted = self._format_results(results)
            return ToolResult(
                success=True,
                data=formatted,
                sources=[r.get("document_title", "") for r in results],
                metadata={"count": len(results), "raw": results},
            )

        except Exception as exc:
            return ToolResult(success=False, error=f"知识库检索失败: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_results(results: list[dict]) -> str:
        """Format retrieval results into a readable text block."""
        lines: list[str] = []
        for idx, item in enumerate(results, start=1):
            lines.append(
                f"[{idx}] 来源：{item.get('document_title', '未知')}\n"
                f"综合相关度：{item.get('score', 0)}\n"
                f"语义相关度：{item.get('semantic_score', item.get('score', 0))}\n"
                f"文档时间：{item.get('document_created_at') or '未知'}\n"
                f"片段：{item.get('content', '')}"
            )
        return "\n\n".join(lines)

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询字符串",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认 4",
                    "default": 4,
                },
            },
            "required": ["query"],
        }
