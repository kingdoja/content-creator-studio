"""
工具基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import json

class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    sources: List[str] = []
    metadata: Dict[str, Any] = {}

class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self):
        self.name = self.__class__.__name__.replace("Tool", "").lower()
        self.description = ""
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        """执行工具"""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """返回工具的JSON Schema（用于LangChain）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameters_schema()
        }
    
    @abstractmethod
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """返回参数schema"""
        pass
    
    def to_langchain_tool(self):
        """转换为LangChain Tool对象。
        LangChain ReAct Agent 调用工具时传入一个字符串（Action Input），
        必须接受该 positional argument。
        """
        from langchain.tools import Tool
        import asyncio
        import threading

        def _run_in_new_loop(coro):
            result_box = {"result": None, "error": None}

            def _target():
                try:
                    result_box["result"] = asyncio.run(coro)
                except Exception as exc:
                    result_box["error"] = exc

            thread = threading.Thread(target=_target, daemon=True)
            thread.start()
            thread.join(timeout=120)
            if thread.is_alive():
                raise TimeoutError(f"工具 {self.name} 执行超时")
            if result_box["error"] is not None:
                raise result_box["error"]
            return result_box["result"]

        def _format_observation(result: ToolResult) -> str:
            """将工具结果格式化为给 Agent 的 Observation，避免整份 data 原样 str() 导致过长、重复占用 token。"""
            if not result.success or result.data is None:
                return f"错误: {result.error}" if result.error else "完成"
            data = result.data
            if self.name == "web_search" and isinstance(data, dict):
                # 紧凑格式：只保留 query、每条 title/url 及 content 截断，避免 5 条全文塞满上下文
                query = data.get("query", "")
                results = data.get("results") or []
                total = data.get("total_results", len(results))
                max_content_chars = 500  # 每条 content 最多字符数
                lines = [f"查询: {query}", f"共 {total} 条结果:"]
                for i, r in enumerate(results[:10], 1):  # 最多 10 条
                    title = (r.get("title") or "")[:120]
                    url = r.get("url") or ""
                    content = (r.get("content") or str(r.get("raw_content") or ""))
                    if len(content) > max_content_chars:
                        content = content[:max_content_chars] + "..."
                    lines.append(f"{i}. [{title}]({url})\n   {content}")
                return "\n\n".join(lines)
            if self.name == "fact_check" and isinstance(data, dict):
                return str(data)[:2000] if len(str(data)) > 2000 else str(data)
            s = str(data)
            return s[:4000] + "..." if len(s) > 4000 else s

        def _infer_primary_key() -> str:
            """从 schema 推断主输入参数，避免写死 query/claim。"""
            schema = self._get_parameters_schema() or {}
            required = schema.get("required") or []
            if required:
                return required[0]
            properties = schema.get("properties") or {}
            for key in ("query", "claim", "input", "text"):
                if key in properties:
                    return key
            return "query"

        def _parse_input(input_str: str) -> Dict[str, Any]:
            """兼容两种 Action Input：普通字符串 或 JSON 对象字符串。"""
            cleaned = (input_str or "").strip()
            if not cleaned:
                return {}
            if cleaned.startswith("{") and cleaned.endswith("}"):
                try:
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    # 非严格 JSON 时回退到字符串模式
                    pass
            return {_infer_primary_key(): input_str}

        def _run(input_str: str) -> str:
            params = _parse_input(input_str)
            try:
                asyncio.get_running_loop()
                # 当前线程已有运行中的事件循环时，避免阻塞同 loop 造成死锁，改为新线程新 loop 执行。
                result = _run_in_new_loop(self.execute(params))
            except RuntimeError:
                result = asyncio.run(self.execute(params))
            if result.success:
                return _format_observation(result)
            return f"错误: {result.error}"
        
        return Tool(
            name=self.name,
            description=self.description,
            func=_run
        )
