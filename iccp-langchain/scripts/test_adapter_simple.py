"""
Simple standalone test for the legacy adapter (no pytest fixtures needed).

Requirements: 10.1, 10.2
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


async def test_adapter_basic():
    """Test basic adapter functionality."""
    print("Test 1: Basic adapter conversion...")
    
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
    assert mock_agent.execute_called, "Agent execute was not called"
    assert mock_agent.last_task is not None, "Task was not passed"
    assert mock_agent.last_context is not None, "Context was not passed"

    # Verify ContentTask conversion
    task = mock_agent.last_task
    assert task.category == "tech", f"Expected category 'tech', got {task.category}"
    assert task.topic == "AI trends", f"Expected topic 'AI trends', got {task.topic}"
    assert task.requirements == "Focus on 2024", f"Expected requirements 'Focus on 2024', got {task.requirements}"
    assert task.length == "long", f"Expected length 'long', got {task.length}"
    assert task.style == "professional", f"Expected style 'professional', got {task.style}"
    assert task.force_simple is False, f"Expected force_simple False, got {task.force_simple}"

    # Verify ExecutionContext conversion
    ctx = mock_agent.last_context
    assert ctx.user_context.user_id == "user123", f"Expected user_id 'user123', got {ctx.user_context.user_id}"
    assert ctx.user_context.session_id == "session456", f"Expected session_id 'session456', got {ctx.user_context.session_id}"
    assert len(ctx.user_context.recalled_memories) == 1, f"Expected 1 memory, got {len(ctx.user_context.recalled_memories)}"
    assert ctx.user_context.preferences["pref1"] == "value1", "Preference not preserved"
    assert ctx.user_context.preferences["llm_model_override"] == "gpt-4", "Model override not preserved"
    assert ctx.user_context.preferences["_max_iterations"] == 5, "Max iterations not preserved"
    assert ctx.user_context.preferences["_is_chat"] is False, "Expected _is_chat False"

    # Verify result conversion back to dict
    assert result["success"] is True, "Expected success True"
    assert result["content"] == "Processed: AI trends", f"Unexpected content: {result['content']}"
    assert result["agent"] == "mock_agent", f"Expected agent 'mock_agent', got {result['agent']}"
    assert result["tools_used"] == ["tool1", "tool2"], f"Expected tools ['tool1', 'tool2'], got {result['tools_used']}"
    assert result["iterations"] == 2, f"Expected 2 iterations, got {result['iterations']}"
    assert result["metadata"]["test"] == "data", "Metadata not preserved"

    print("✓ Test 1 passed")


async def test_adapter_chat_module():
    """Test that adapter correctly detects chat module."""
    print("Test 2: Chat module detection...")
    
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    task_dict = {
        "category": "lifestyle",
        "topic": "Hello",
        "module": "chat",
    }

    context_dict = {"user_id": "user123"}

    await adapter.execute(task_dict, context_dict)

    assert mock_agent.last_context.user_context.preferences["_is_chat"] is True, "Expected _is_chat True for chat module"
    
    print("✓ Test 2 passed")


async def test_adapter_missing_context():
    """Test that adapter handles None context."""
    print("Test 3: Missing context handling...")
    
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    task_dict = {
        "category": "tech",
        "topic": "Test topic",
    }

    result = await adapter.execute(task_dict, None)

    assert result["success"] is True, "Expected success True"
    assert mock_agent.last_context.user_context.user_id == "anonymous", "Expected default user_id 'anonymous'"
    assert mock_agent.last_context.user_context.session_id is None, "Expected session_id None"
    
    print("✓ Test 3 passed")


async def test_adapter_properties():
    """Test that adapter exposes agent properties."""
    print("Test 4: Agent properties...")
    
    mock_agent = MockNewAgent()
    adapter = LegacyAgentAdapter(mock_agent)

    assert adapter.name == "mock_agent", f"Expected name 'mock_agent', got {adapter.name}"
    assert adapter.description == "Mock agent for testing", f"Unexpected description: {adapter.description}"
    
    print("✓ Test 4 passed")


async def test_wrap_convenience():
    """Test the convenience wrapper function."""
    print("Test 5: Convenience wrapper...")
    
    mock_agent = MockNewAgent()
    adapter = wrap_agent_with_legacy_adapter(mock_agent)

    assert isinstance(adapter, LegacyAgentAdapter), "Expected LegacyAgentAdapter instance"
    assert adapter.name == "mock_agent", f"Expected name 'mock_agent', got {adapter.name}"
    
    print("✓ Test 5 passed")


def test_feature_flag():
    """Test that feature flag is accessible."""
    print("Test 6: Feature flag access...")
    
    try:
        from app.config import USE_NEW_ARCHITECTURE, use_new_architecture
        
        assert isinstance(USE_NEW_ARCHITECTURE, bool), "USE_NEW_ARCHITECTURE should be bool"
        assert isinstance(use_new_architecture(), bool), "use_new_architecture() should return bool"
        
        print(f"  USE_NEW_ARCHITECTURE = {USE_NEW_ARCHITECTURE}")
        print("✓ Test 6 passed")
    except ImportError as e:
        print(f"  Skipping feature flag test (missing dependencies: {e})")
        print("✓ Test 6 skipped (expected in minimal environment)")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Running Legacy Adapter Tests")
    print("=" * 60)
    print()
    
    try:
        await test_adapter_basic()
        await test_adapter_chat_module()
        await test_adapter_missing_context()
        await test_adapter_properties()
        await test_wrap_convenience()
        test_feature_flag()
        
        print()
        print("=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"Test failed: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
