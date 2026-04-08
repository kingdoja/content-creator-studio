"""
配置驱动的路由规则加载器。

支持从 YAML 文件加载路由策略优先级配置，并在启动时验证配置格式。
格式错误时抛出明确的 ConfigurationError。

Requirements: 7.1, 7.5
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 合法的策略名称和 Agent 名称
# ---------------------------------------------------------------------------

VALID_STRATEGY_NAMES: frozenset[str] = frozenset(
    {
        "SimpleQAStrategy",
        "KnowledgeStrategy",
        "RealtimeStrategy",
        "HighQualityStrategy",
        "MediumReflectionStrategy",
        "DefaultStrategy",
    }
)

VALID_AGENT_NAMES: frozenset[str] = frozenset({"simple", "react", "reflection"})

# ---------------------------------------------------------------------------
# 配置数据模型
# ---------------------------------------------------------------------------


@dataclass
class StrategyConfig:
    """单条路由策略配置。"""

    name: str          # 策略类名，如 "SimpleQAStrategy"
    agent: str         # 目标 Agent，如 "simple"
    priority: int      # 优先级，数字越小越先匹配
    enabled: bool = True
    description: str = ""


@dataclass
class RoutingConfig:
    """完整的路由配置，从 YAML 文件加载。"""

    strategies: list[StrategyConfig] = field(default_factory=list)
    # 路由配置文件的来源路径（仅供日志记录）
    source_path: str = "<default>"

    def enabled_strategies_by_priority(self) -> list[StrategyConfig]:
        """返回已启用的策略，按 priority 升序排列。"""
        return sorted(
            [s for s in self.strategies if s.enabled],
            key=lambda s: s.priority,
        )


# ---------------------------------------------------------------------------
# 配置验证
# ---------------------------------------------------------------------------


class ConfigurationError(Exception):
    """路由配置格式错误，在启动时抛出。"""


def _validate_strategy_entry(entry: Any, index: int) -> StrategyConfig:
    """
    验证单条策略配置条目，返回 StrategyConfig。
    格式错误时抛出 ConfigurationError。
    """
    if not isinstance(entry, dict):
        raise ConfigurationError(
            f"strategies[{index}] 必须是字典，实际类型: {type(entry).__name__}"
        )

    # --- 必填字段 ---
    name = entry.get("name")
    if not name:
        raise ConfigurationError(f"strategies[{index}].name 为必填字段")
    if not isinstance(name, str):
        raise ConfigurationError(
            f"strategies[{index}].name 必须是字符串，实际类型: {type(name).__name__}"
        )
    if name not in VALID_STRATEGY_NAMES:
        raise ConfigurationError(
            f"strategies[{index}].name={name!r} 不是合法的策略名称。"
            f"合法值: {sorted(VALID_STRATEGY_NAMES)}"
        )

    agent = entry.get("agent")
    if not agent:
        raise ConfigurationError(f"strategies[{index}].agent 为必填字段")
    if not isinstance(agent, str):
        raise ConfigurationError(
            f"strategies[{index}].agent 必须是字符串，实际类型: {type(agent).__name__}"
        )
    if agent not in VALID_AGENT_NAMES:
        raise ConfigurationError(
            f"strategies[{index}].agent={agent!r} 不是合法的 Agent 名称。"
            f"合法值: {sorted(VALID_AGENT_NAMES)}"
        )

    priority = entry.get("priority")
    if priority is None:
        raise ConfigurationError(f"strategies[{index}].priority 为必填字段")
    if not isinstance(priority, int):
        raise ConfigurationError(
            f"strategies[{index}].priority 必须是整数，实际类型: {type(priority).__name__}"
        )

    # --- 可选字段 ---
    enabled = entry.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigurationError(
            f"strategies[{index}].enabled 必须是布尔值，实际类型: {type(enabled).__name__}"
        )

    description = entry.get("description", "")
    if not isinstance(description, str):
        raise ConfigurationError(
            f"strategies[{index}].description 必须是字符串，实际类型: {type(description).__name__}"
        )

    return StrategyConfig(
        name=name,
        agent=agent,
        priority=priority,
        enabled=enabled,
        description=description,
    )


def _validate_routing_config(raw: Any, source_path: str) -> RoutingConfig:
    """
    验证从 YAML 解析的原始数据，返回 RoutingConfig。
    格式错误时抛出 ConfigurationError。
    """
    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"路由配置文件 {source_path!r} 的顶层结构必须是字典，"
            f"实际类型: {type(raw).__name__}"
        )

    strategies_raw = raw.get("strategies")
    if strategies_raw is None:
        raise ConfigurationError(
            f"路由配置文件 {source_path!r} 缺少必填字段 'strategies'"
        )
    if not isinstance(strategies_raw, list):
        raise ConfigurationError(
            f"路由配置文件 {source_path!r} 的 'strategies' 必须是列表，"
            f"实际类型: {type(strategies_raw).__name__}"
        )
    if len(strategies_raw) == 0:
        raise ConfigurationError(
            f"路由配置文件 {source_path!r} 的 'strategies' 列表不能为空"
        )

    strategies = [
        _validate_strategy_entry(entry, i) for i, entry in enumerate(strategies_raw)
    ]

    # 确保存在兜底策略（DefaultStrategy），防止路由无法命中
    has_default = any(s.name == "DefaultStrategy" and s.enabled for s in strategies)
    if not has_default:
        raise ConfigurationError(
            f"路由配置文件 {source_path!r} 必须包含一条已启用的 DefaultStrategy，"
            "以确保所有请求都能被路由"
        )

    return RoutingConfig(strategies=strategies, source_path=source_path)


# ---------------------------------------------------------------------------
# YAML 加载
# ---------------------------------------------------------------------------


def load_routing_config(config_path: str | Path) -> RoutingConfig:
    """
    从 YAML 文件加载并验证路由配置。

    Args:
        config_path: YAML 配置文件路径。

    Returns:
        验证通过的 RoutingConfig 对象。

    Raises:
        ConfigurationError: 文件不存在、YAML 格式错误或配置内容不合法时抛出。
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError as exc:
        raise ConfigurationError(
            "加载路由配置需要安装 PyYAML：pip install pyyaml"
        ) from exc

    path = Path(config_path)
    if not path.exists():
        raise ConfigurationError(
            f"路由配置文件不存在: {path.resolve()}"
        )
    if not path.is_file():
        raise ConfigurationError(
            f"路由配置路径不是文件: {path.resolve()}"
        )

    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"路由配置文件 {str(path)!r} YAML 解析失败: {exc}"
        ) from exc

    config = _validate_routing_config(raw, str(path))
    logger.info(
        "路由配置加载成功: source=%s strategies=%d enabled=%d",
        config.source_path,
        len(config.strategies),
        len(config.enabled_strategies_by_priority()),
    )
    return config


# ---------------------------------------------------------------------------
# 将 RoutingConfig 转换为 RoutingStrategy 列表
# ---------------------------------------------------------------------------


def build_strategies_from_config(config: RoutingConfig):  # -> list[RoutingStrategy]
    """
    根据 RoutingConfig 构建有序的 RoutingStrategy 实例列表。

    Returns:
        按 priority 升序排列的 RoutingStrategy 列表。
    """
    from app.agents.strategies import (  # local import to avoid circular deps
        DefaultStrategy,
        HighQualityStrategy,
        KnowledgeStrategy,
        MediumReflectionStrategy,
        RealtimeStrategy,
        SimpleQAStrategy,
    )

    _strategy_classes = {
        "SimpleQAStrategy": SimpleQAStrategy,
        "KnowledgeStrategy": KnowledgeStrategy,
        "RealtimeStrategy": RealtimeStrategy,
        "HighQualityStrategy": HighQualityStrategy,
        "MediumReflectionStrategy": MediumReflectionStrategy,
        "DefaultStrategy": DefaultStrategy,
    }

    result = []
    for sc in config.enabled_strategies_by_priority():
        cls = _strategy_classes[sc.name]
        result.append(cls())
    return result
