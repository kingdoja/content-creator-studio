"""
Agent 系统：以 LangGraph 为唯一执行入口，Router 提供 Agent 实例与建议。
"""
# 新架构导入
from .router_v2 import AgentRouterV2
from .graph import (
    ContentCreationState,
    build_content_creation_graph,
    get_content_creation_graph,
)
from .analyzer import analyze_task
from .react_agent import ReActAgent
from .reflection_agent import ReflectionAgent
from .simple_agent import SimpleAgent

# 向后兼容：使用新路由器作为默认
AgentRouter = AgentRouterV2

# 旧架构导入（向后兼容）
try:
    from ._legacy.plan_solve_agent import PlanSolveAgent
    from ._legacy.rag_agent import RAGAgent
    from ._legacy.routing import select_agent_name
except ImportError:
    # 如果旧模块不存在，使用占位符
    PlanSolveAgent = None
    RAGAgent = None
    select_agent_name = None

# 全局路由器实例（向后兼容）
_router_instance = None

def get_agent_router():
    """获取全局路由器实例（向后兼容）"""
    global _router_instance
    if _router_instance is None:
        _router_instance = AgentRouterV2()
    return _router_instance

__all__ = [
    "AgentRouter",
    "AgentRouterV2",
    "get_agent_router",
    "ContentCreationState",
    "build_content_creation_graph",
    "get_content_creation_graph",
    "analyze_task",
    "select_agent_name",
    "ReActAgent",
    "ReflectionAgent",
    "SimpleAgent",
    # 旧架构（已废弃）
    "PlanSolveAgent",
    "RAGAgent",
]
