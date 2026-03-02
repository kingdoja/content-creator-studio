"""
网络搜索工具（使用LangChain + Tavily）
"""
from typing import Dict, Any
from datetime import datetime
from app.tools.base import BaseTool, ToolResult
from app.config import settings
import httpx
import logging

logger = logging.getLogger(__name__)

# 视为“未配置”的 Tavily Key（占位符或明显无效）
TAVILY_KEY_PLACEHOLDERS = ("", "your-tavily-api-key", "your_api_key_here")


class WebSearchTool(BaseTool):
    """网络搜索工具"""
    
    def __init__(self):
        super().__init__()
        self.name = "web_search"
        self.description = "搜索网络上的最新信息和数据。适用于需要实时信息、统计数据、新闻等的场景。"
        key = (settings.TAVILY_API_KEY or "").strip()
        self.api_key = key if key and key not in TAVILY_KEY_PLACEHOLDERS else None
    
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行搜索"""
        query = params.get("query", "")
        max_results = params.get("max_results", 5)
        
        if not query:
            return ToolResult(
                success=False,
                error="缺少查询参数 query"
            )
        
        # 对时效性查询自动增强时间约束，减少命中陈旧信息的概率。
        query = self._enhance_query_for_freshness(query)

        # 有有效 Key 时先试 Tavily；失败则试 DuckDuckGo
        if self.api_key:
            result = await self._search_tavily(query, max_results)
            if result.success:
                return result
            logger.warning("Tavily 返回错误，改用 DuckDuckGo: %s", result.error)
        
        result = await self._search_duckduckgo(query, max_results)
        if result.success:
            return result
        # DuckDuckGo 也失败（国内常见：超时/无法访问）时，返回“搜索不可用”的占位结果，
        # 让 Agent 能继续基于已有知识生成内容，而不是一直重试报错
        logger.warning("DuckDuckGo 不可用（%s），返回占位结果以便继续生成", result.error)
        return self._search_unavailable_fallback(query)
    
    async def _search_tavily(self, query: str, max_results: int) -> ToolResult:
        """使用Tavily搜索"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic"
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                sources = [r.get("url", "") for r in results]
                
                return ToolResult(
                    success=True,
                    data={
                        "query": query,
                        "results": results,
                        "total_results": len(results)
                    },
                    sources=sources,
                    metadata={
                        "provider": "tavily",
                        "search_time": data.get("search_time", 0)
                    }
                )
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                return ToolResult(success=False, error=f"Tavily API Key 无效或未授权: {e.response.status_code}")
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=str(e))
    
    def _search_unavailable_fallback(self, query: str) -> ToolResult:
        """搜索不可用时的占位结果，让 Agent 能继续生成内容"""
        return ToolResult(
            success=True,
            data={
                "query": query,
                "results": [],
                "total_results": 0,
                "message": "网络搜索暂时不可用（超时或网络限制）。请基于模型已有知识撰写内容，并在文中说明未使用实时检索。"
            },
            sources=[],
            metadata={"provider": "none", "reason": "search_unavailable"}
        )

    def _enhance_query_for_freshness(self, query: str) -> str:
        q = (query or "").strip()
        if not q:
            return q
        q_lower = q.lower()
        freshness_markers = [
            "最新", "最近", "今日", "今天", "本周", "本月", "本季度", "今年", "实时",
            "动态", "近况", "current", "latest", "today", "recent", "news",
        ]
        needs_freshness = any(marker in q_lower for marker in freshness_markers)
        if not needs_freshness:
            return q
        now = datetime.now()
        # 仅追加轻量时间锚点，不改写用户原意。
        return f"{q} {now.year}年 {now.month}月 最新"

    async def _search_duckduckgo(self, query: str, max_results: int) -> ToolResult:
        """使用DuckDuckGo搜索（备用）；国内环境常超时"""
        try:
            from duckduckgo_search import DDGS
            
            with DDGS() as ddgs:
                results = []
                sources = []
                
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", "")
                    })
                    sources.append(r.get("href", ""))
                
                return ToolResult(
                    success=True,
                    data={
                        "query": query,
                        "results": results,
                        "total_results": len(results)
                    },
                    sources=sources,
                    metadata={"provider": "duckduckgo"}
                )
        except ImportError:
            return ToolResult(
                success=False,
                error="DuckDuckGo搜索需要安装: pip install duckduckgo-search"
            )
        except Exception as e:
            # 超时、连接失败等（国内访问 duckduckgo 常见）
            return ToolResult(success=False, error=str(e))
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """返回参数schema"""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数",
                    "default": 5
                }
            },
            "required": ["query"]
        }
