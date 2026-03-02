from importlib import import_module
from typing import Any

__all__ = ["knowledge_service", "KnowledgeService"]


def __getattr__(name: str) -> Any:
    # 延迟导入，避免 memory <-> rag 在模块初始化阶段循环依赖。
    if name in {"knowledge_service", "KnowledgeService"}:
        module = import_module("app.rag.knowledge_service")
        return getattr(module, name)
    raise AttributeError(f"module 'app.rag' has no attribute '{name}'")
