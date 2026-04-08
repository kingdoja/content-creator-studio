"""
Domain models for the ICCP content creation platform.
These are pure data objects with no external framework dependencies.
Requirements: 4.2, 4.3
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContentTask:
    """Represents a content creation request."""
    category: str
    topic: str
    requirements: str
    length: str          # short | medium | long
    style: str           # casual | professional
    force_simple: bool = False


@dataclass(frozen=True)
class ContentResult:
    """Represents the result of a content creation task."""
    success: bool
    content: str
    agent: str
    tools_used: tuple[str, ...] = field(default_factory=tuple)
    iterations: int = 1
    error: str | None = None
    metadata: dict | None = None


@dataclass(frozen=True)
class UserContext:
    """Carries user-specific context including recalled memories."""
    user_id: str
    session_id: str | None
    recalled_memories: tuple[dict, ...] = field(default_factory=tuple)
    preferences: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TaskAnalysis:
    """Result of analyzing a content task for routing decisions."""
    complexity: str              # low | medium | high
    task_type: str               # simple_qa | knowledge | realtime | planning | reflection | general
    requires_knowledge: bool
    requires_real_time_data: bool
    requires_reflection: bool
    estimated_iterations: int
