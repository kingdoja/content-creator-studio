"""
路由策略实现（策略模式）。
每个策略封装一条路由规则，替代 routing.py 中的 if-else 链。
Requirements: 1.2, 1.4
"""
from __future__ import annotations

from app.domain.interfaces import RoutingStrategy
from app.domain.models import TaskAnalysis


class SimpleQAStrategy(RoutingStrategy):
    """匹配简单问答和闲聊场景，路由到 SimpleAgent。"""

    def matches(self, analysis: TaskAnalysis) -> bool:
        return analysis.task_type == "simple_qa"

    def agent_name(self) -> str:
        return "simple"


class KnowledgeStrategy(RoutingStrategy):
    """匹配需要知识库检索的场景，路由到 ReActAgent（携带 KnowledgeSearchTool）。"""

    def matches(self, analysis: TaskAnalysis) -> bool:
        return analysis.requires_knowledge

    def agent_name(self) -> str:
        return "react"


class RealtimeStrategy(RoutingStrategy):
    """匹配需要实时数据的场景，路由到 ReActAgent（携带搜索工具）。"""

    def matches(self, analysis: TaskAnalysis) -> bool:
        return analysis.requires_real_time_data

    def agent_name(self) -> str:
        return "react"


class HighQualityStrategy(RoutingStrategy):
    """匹配需要高质量/深度反思的场景，路由到 ReflectionAgent。"""

    def matches(self, analysis: TaskAnalysis) -> bool:
        return analysis.requires_reflection and analysis.complexity == "high"

    def agent_name(self) -> str:
        return "reflection"


class MediumReflectionStrategy(RoutingStrategy):
    """匹配中等复杂度但仍需反思的场景，路由到 ReflectionAgent。"""

    def matches(self, analysis: TaskAnalysis) -> bool:
        return analysis.requires_reflection and analysis.complexity == "medium"

    def agent_name(self) -> str:
        return "reflection"


class DefaultStrategy(RoutingStrategy):
    """兜底策略，始终匹配，路由到 ReActAgent。"""

    def matches(self, analysis: TaskAnalysis) -> bool:
        return True

    def agent_name(self) -> str:
        return "react"


# 按优先级排列的默认策略列表（第一个匹配的策略胜出）
DEFAULT_STRATEGIES: list[RoutingStrategy] = [
    SimpleQAStrategy(),
    KnowledgeStrategy(),
    RealtimeStrategy(),
    HighQualityStrategy(),
    MediumReflectionStrategy(),
    DefaultStrategy(),
]
