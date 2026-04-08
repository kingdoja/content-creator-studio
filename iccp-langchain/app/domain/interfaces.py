"""
Abstract interfaces for the domain layer.
These define contracts that infrastructure implementations must satisfy.
Requirements: 4.3
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.models import ContentTask, ContentResult, TaskAnalysis, UserContext


@dataclass
class ExecutionContext:
    """Runtime context passed to agents during execution."""
    user_context: UserContext
    session_id: str | None = None
    trace_id: str | None = None


class BaseAgent(ABC):
    """Abstract base for all content creation agents."""

    name: str
    description: str

    @abstractmethod
    async def execute(
        self,
        task: ContentTask,
        context: ExecutionContext,
    ) -> ContentResult:
        """Execute the content creation task and return a result."""
        ...


class RoutingStrategy(ABC):
    """Abstract strategy for agent routing decisions."""

    @abstractmethod
    def matches(self, analysis: TaskAnalysis) -> bool:
        """Return True if this strategy applies to the given task analysis."""
        ...

    @abstractmethod
    def agent_name(self) -> str:
        """Return the name of the agent this strategy routes to."""
        ...
