"""
Tests for the legacy adapter that bridges old and new architecture.

Requirements: 10.1, 10.2
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.adapters.legacy_adapter import LegacyAgentAdapter, wrap_agent_with_legacy_adapter
from app.domain.interfaces import BaseAgent, ExecutionContext
from app.domain.models import ContentResult, ContentTask, UserContext


class MockNewAgent(BaseAgent):
    """Mock agent implementing the new interface."""

    name = "mock_agent"
    description = "Mock agent for testing"

    def __init__(self):
        self.execute_called = False
        self.last_task = None
        self.last_context = None

    async def execute(
        self,
        task: ContentTask,
        context: ExecutionContext,
    ) -> ContentResult:
        """Mock execute that records calls."""
        self.execute_called = True
        self.last_task = task
        self.last_context = context

        return ContentResult(
            success=True,
            content=f"Processed: {task.topic}",
            agent=self.name,
            tools_used=("tool1", "tool2"),
            iterations=2,
            metadata={"test": "data"},
        )


@pytest.mark.asyncio
async def test_adapter_converts_dict_to_domain_objects():
    """Test that adapter correctly converts dict inputs to domain objects."""
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    task_dict = {
        "category": "tech",
        "topic": "AI trends",
        "requirements": "Focus on 2024",
        "length": "long",
        "style": "professional",
        "force_simple": False,
        "module": "content",
    }

    context_dict = {
        "user_id": "user123",
        "session_id": "session456",
        "recalled_memories": [{"content": "memory1"}],
        "user_preferences": {"pref1": "value1"},
        "llm_model_override": "gpt-4",
        "max_iterations": 5,
    }

    result = await adapter.execute(task_dict, context_dict)

    # Verify the new agent was called
    assert mock_agent.execute_called
    assert mock_agent.last_task is not None
    assert mock_agent.last_context is not None

    # Verify ContentTask conversion
    task = mock_agent.last_task
    assert task.category == "tech"
    assert task.topic == "AI trends"
    assert task.requirements == "Focus on 2024"
    assert task.length == "long"
    assert task.style == "professional"
    assert task.force_simple is False

    # Verify ExecutionContext conversion
    ctx = mock_agent.last_context
    assert ctx.user_context.user_id == "user123"
    assert ctx.user_context.session_id == "session456"
    assert len(ctx.user_context.recalled_memories) == 1
    assert ctx.user_context.preferences["pref1"] == "value1"
    assert ctx.user_context.preferences["llm_model_override"] == "gpt-4"
    assert ctx.user_context.preferences["_max_iterations"] == 5
    assert ctx.user_context.preferences["_is_chat"] is False

    # Verify result conversion back to dict
    assert result["success"] is True
    assert result["content"] == "Processed: AI trends"
    assert result["agent"] == "mock_agent"
    assert result["tools_used"] == ["tool1", "tool2"]
    assert result["iterations"] == 2
    assert result["metadata"]["test"] == "data"


@pytest.mark.asyncio
async def test_adapter_handles_chat_module():
    """Test that adapter correctly detects chat module and sets _is_chat flag."""
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    task_dict = {
        "category": "lifestyle",
        "topic": "Hello",
        "module": "chat",  # This should set _is_chat to True
    }

    context_dict = {"user_id": "user123"}

    await adapter.execute(task_dict, context_dict)

    # Verify _is_chat flag was set
    assert mock_agent.last_context.user_context.preferences["_is_chat"] is True


@pytest.mark.asyncio
async def test_adapter_handles_missing_context():
    """Test that adapter handles None context gracefully."""
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    task_dict = {
        "category": "tech",
        "topic": "Test topic",
    }

    result = await adapter.execute(task_dict, None)

    # Should still work with default values
    assert result["success"] is True
    assert mock_agent.last_context.user_context.user_id == "anonymous"
    assert mock_agent.last_context.user_context.session_id is None


@pytest.mark.asyncio
async def test_adapter_handles_agent_errors():
    """Test that adapter catches and converts agent errors to dict format."""

    class FailingAgent(BaseAgent):
        name = "failing_agent"
        description = "Agent that always fails"

        async def execute(self, task: ContentTask, context: ExecutionContext) -> ContentResult:
            raise ValueError("Intentional test error")

    adapter = LegacyAgentAdapter(FailingAgent())

    task_dict = {"category": "tech", "topic": "Test"}
    result = await adapter.execute(task_dict, {})

    assert result["success"] is False
    assert result["content"] == ""
    assert result["agent"] == "failing_agent"
    assert "Intentional test error" in result["error"]


def test_adapter_exposes_agent_properties():
    """Test that adapter exposes agent name and description."""
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    assert adapter.name == "mock_agent"
    assert adapter.description == "Mock agent for testing"


def test_wrap_agent_convenience_function():
    """Test the convenience wrapper function."""
    mock_agent = MockNewAgent()
    adapter = wrap_agent_with_legacy_adapter(mock_agent)

    assert isinstance(adapter, LegacyAgentAdapter)
    assert adapter.name == "mock_agent"


@pytest.mark.asyncio
async def test_adapter_preserves_all_task_fields():
    """Test that all task fields are correctly preserved through conversion."""
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    task_dict = {
        "category": "finance",
        "topic": "Investment strategies",
        "requirements": "Include risk analysis",
        "length": "short",
        "style": "casual",
        "force_simple": True,
    }

    await adapter.execute(task_dict, {})

    task = mock_agent.last_task
    assert task.category == "finance"
    assert task.topic == "Investment strategies"
    assert task.requirements == "Include risk analysis"
    assert task.length == "short"
    assert task.style == "casual"
    assert task.force_simple is True


@pytest.mark.asyncio
async def test_adapter_handles_empty_requirements():
    """Test that adapter handles empty or None requirements."""
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    # Test with None
    task_dict = {"category": "tech", "topic": "Test", "requirements": None}
    await adapter.execute(task_dict, {})
    assert mock_agent.last_task.requirements == ""

    # Test with empty string
    task_dict = {"category": "tech", "topic": "Test", "requirements": ""}
    await adapter.execute(task_dict, {})
    assert mock_agent.last_task.requirements == ""


@pytest.mark.asyncio
async def test_adapter_converts_result_tuples_to_lists():
    """Test that adapter converts tuple fields to lists for JSON compatibility."""
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    task_dict = {"category": "tech", "topic": "Test"}
    result = await adapter.execute(task_dict, {})

    # tools_used should be a list, not a tuple
    assert isinstance(result["tools_used"], list)
    assert result["tools_used"] == ["tool1", "tool2"]
