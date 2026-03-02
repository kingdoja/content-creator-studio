"""
工具系统
"""
from .base import BaseTool, ToolResult
from .web_search import WebSearchTool
from .fact_check import FactCheckTool
from .mcp_bridge import MCPBridgeTool
from .registry import ToolRegistry, get_tool_registry

__all__ = [
    "BaseTool",
    "ToolResult",
    "WebSearchTool",
    "FactCheckTool",
    "MCPBridgeTool",
    "ToolRegistry",
    "get_tool_registry",
]
