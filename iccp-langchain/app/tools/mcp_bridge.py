"""
MCP 桥接工具（可选）
通过 HTTP 网关将工具调用转发到 MCP 服务，避免业务 Agent 直接耦合 MCP 协议细节。
"""
from typing import Dict, Any, Optional
import httpx

from app.tools.base import BaseTool, ToolResult
from app.config import settings


class MCPBridgeTool(BaseTool):
    """将当前工具调用桥接到 MCP 网关。"""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        mcp_tool: str,
        mcp_server: Optional[str] = None,
        input_arg_key: str = "query",
        static_args: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.name = name
        self.description = description
        self.mcp_tool = mcp_tool
        self.mcp_server = mcp_server or settings.MCP_DEFAULT_SERVER or ""
        self.input_arg_key = input_arg_key
        self.static_args = static_args or {}

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        gateway = (settings.MCP_GATEWAY_URL or "").strip()
        if not gateway:
            return ToolResult(success=False, error="未配置 MCP_GATEWAY_URL，无法调用 MCP 工具")
        if not self.mcp_server:
            return ToolResult(success=False, error="未配置 mcp_server，无法调用 MCP 工具")

        dynamic_value = params.get(self.input_arg_key)
        arguments = {**self.static_args}
        if dynamic_value is not None:
            arguments[self.input_arg_key] = dynamic_value
        else:
            # 回退：直接合并入参，便于 JSON 结构化调用
            arguments.update(params)

        payload = {
            "server": self.mcp_server,
            "toolName": self.mcp_tool,
            "arguments": arguments,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{gateway.rstrip('/')}/tools/call", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            return ToolResult(success=False, error=f"MCP 调用失败: {exc}")

        return ToolResult(
            success=True,
            data=data,
            metadata={"provider": "mcp", "server": self.mcp_server, "tool": self.mcp_tool},
        )

    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                self.input_arg_key: {
                    "type": "string",
                    "description": f"MCP 工具 {self.mcp_tool} 的主输入参数",
                }
            },
            "required": [self.input_arg_key],
        }
