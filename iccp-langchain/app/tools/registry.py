"""
工具注册表
"""
from typing import Dict, List, Optional
from app.tools.base import BaseTool
from app.tools.web_search import WebSearchTool
from app.tools.fact_check import FactCheckTool
from app.tools.mcp_bridge import MCPBridgeTool
from app.config import settings
from langchain.tools import Tool
import logging
import json

logger = logging.getLogger(__name__)

class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._langchain_tools: List[Tool] = []
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        # 注册自定义工具
        web_search = WebSearchTool()
        fact_check = FactCheckTool()
        
        self.register(web_search)
        self.register(fact_check)
        self._register_mcp_tools()

    def _register_mcp_tools(self):
        """按配置注册 MCP 桥接工具（可选能力，默认关闭）。"""
        if not settings.MCP_ENABLED:
            return

        raw_config = (settings.MCP_TOOLS_JSON or "").strip()
        if not raw_config:
            logger.info("MCP_ENABLED=true，但 MCP_TOOLS_JSON 为空，跳过 MCP 工具注册")
            return

        try:
            items = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            logger.warning("MCP_TOOLS_JSON 解析失败，跳过 MCP 工具注册: %s", exc)
            return

        if not isinstance(items, list):
            logger.warning("MCP_TOOLS_JSON 必须是 JSON 数组，当前类型=%s", type(items).__name__)
            return

        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            mcp_tool = item.get("mcp_tool")
            if not name or not mcp_tool:
                logger.warning("跳过 MCP 工具：缺少 name 或 mcp_tool。配置=%s", item)
                continue
            bridge_tool = MCPBridgeTool(
                name=name,
                description=item.get("description", f"MCP 工具：{mcp_tool}"),
                mcp_tool=mcp_tool,
                mcp_server=item.get("server") or settings.MCP_DEFAULT_SERVER,
                input_arg_key=item.get("input_arg_key", "query"),
                static_args=item.get("static_args") if isinstance(item.get("static_args"), dict) else {},
            )
            self.register(bridge_tool)
    
    def register(self, tool: BaseTool):
        """注册工具"""
        self._tools[tool.name] = tool
        # 同时注册为LangChain Tool
        langchain_tool = tool.to_langchain_tool()
        self._langchain_tools.append(langchain_tool)
        logger.info(f"注册工具: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def get_langchain_tools(self) -> List[Tool]:
        """获取所有LangChain工具"""
        return self._langchain_tools
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())

# 全局实例
_tool_registry: Optional[ToolRegistry] = None

def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
