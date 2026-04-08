"""
AgentRouterV2：基于策略模式的新版路由器。
路由结果严格限定在 {"simple", "react", "reflection"} 三个 Agent。
Requirements: 1.1, 1.4
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.agents.analyzer import analyze_task
from app.agents.strategies import DEFAULT_STRATEGIES
from app.domain.interfaces import RoutingStrategy
from app.domain.models import TaskAnalysis

logger = logging.getLogger(__name__)

# 合法的 Agent 名称集合（Property 1 约束）
VALID_AGENT_NAMES: frozenset[str] = frozenset({"simple", "react", "reflection"})

# 默认路由配置文件路径（相对于项目根目录）
_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "routing_config.yaml"


class AgentRouterV2:
    """
    策略模式路由器。

    按优先级遍历策略列表，第一个 matches() 返回 True 的策略胜出。
    路由结果始终属于 VALID_AGENT_NAMES。

    可通过 from_config() 工厂方法从 YAML 配置文件构建。
    """

    def __init__(self, strategies: list[RoutingStrategy] | None = None) -> None:
        self._strategies = strategies if strategies is not None else list(DEFAULT_STRATEGIES)

    @classmethod
    def from_config(cls, config_path: str | Path | None = None) -> "AgentRouterV2":
        """
        从 YAML 配置文件构建路由器。

        Args:
            config_path: YAML 配置文件路径。为 None 时使用默认路径。

        Returns:
            配置驱动的 AgentRouterV2 实例。

        Raises:
            ConfigurationError: 配置文件不存在或格式错误时在启动时抛出。
        """
        from app.config.routing_config import build_strategies_from_config, load_routing_config

        path = config_path if config_path is not None else _DEFAULT_CONFIG_PATH
        config = load_routing_config(path)
        strategies = build_strategies_from_config(config)
        logger.info("AgentRouterV2 从配置文件构建: %s (%d 条策略)", path, len(strategies))
        return cls(strategies=strategies)

    def route(self, analysis: TaskAnalysis) -> str:
        """
        根据 TaskAnalysis 返回目标 Agent 名称。

        Returns:
            "simple" | "react" | "reflection"
        """
        for strategy in self._strategies:
            if strategy.matches(analysis):
                agent = strategy.agent_name()
                if agent not in VALID_AGENT_NAMES:
                    raise ValueError(
                        f"策略 {type(strategy).__name__} 返回了非法的 agent 名称: {agent!r}。"
                        f"合法值: {VALID_AGENT_NAMES}"
                    )
                return agent
        # 理论上 DefaultStrategy 保证永远不会走到这里
        return "react"

    def route_from_task(
        self,
        task: dict[str, Any],
        memory_signals: dict[str, Any] | None = None,
    ) -> tuple[str, TaskAnalysis]:
        """
        从原始任务字典直接路由，返回 (agent_name, analysis) 元组。
        """
        analysis = analyze_task(task, memory_signals)
        agent_name = self.route(analysis)
        return agent_name, analysis


# 全局单例
_router_v2: AgentRouterV2 | None = None


def get_router_v2() -> AgentRouterV2:
    """
    获取 AgentRouterV2 单例。
    
    首次调用时尝试从配置文件加载，若配置文件不存在或加载失败，
    则使用内置默认策略。
    """
    global _router_v2
    if _router_v2 is None:
        try:
            _router_v2 = AgentRouterV2.from_config()
            logger.info("AgentRouterV2 单例已从配置文件初始化")
        except Exception as exc:
            logger.warning(
                "从配置文件加载路由器失败，使用内置默认策略: %s",
                exc,
            )
            _router_v2 = AgentRouterV2()
    return _router_v2
