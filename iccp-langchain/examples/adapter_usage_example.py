"""
Example: Using LegacyAgentAdapter for gradual migration.

This example demonstrates how to use the legacy adapter to bridge
old dict-based interfaces with new domain object interfaces.

Requirements: 10.1, 10.2
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


async def example_1_basic_adapter_usage():
    """Example 1: Basic adapter usage with SimpleAgent."""
    print("=" * 60)
    print("Example 1: Basic Adapter Usage")
    print("=" * 60)
    
    from app.adapters.legacy_adapter import wrap_agent_with_legacy_adapter
    from app.agents.simple_agent import SimpleAgent
    
    # Create a new-style agent
    simple_agent = SimpleAgent()
    
    # Wrap it with the legacy adapter
    adapter = wrap_agent_with_legacy_adapter(simple_agent)
    
    # Now you can use the old dict-based interface
    task_dict = {
        "category": "lifestyle",
        "topic": "如何保持健康的生活方式？",
        "requirements": "请给出3-5个实用建议",
        "length": "medium",
        "style": "casual",
    }
    
    context_dict = {
        "user_id": "user123",
        "session_id": "session456",
    }
    
    print("\nCalling agent with old dict interface...")
    result = await adapter.execute(task_dict, context_dict)
    
    print(f"\nResult:")
    print(f"  Success: {result['success']}")
    print(f"  Agent: {result['agent']}")
    print(f"  Content: {result['content'][:100]}...")
    print(f"  Iterations: {result['iterations']}")
    print()


async def example_2_feature_flag_usage():
    """Example 2: Using feature flag to control architecture."""
    print("=" * 60)
    print("Example 2: Feature Flag Usage")
    print("=" * 60)
    
    try:
        from app.config import USE_NEW_ARCHITECTURE, use_new_architecture
        
        print(f"\nCurrent architecture setting:")
        print(f"  USE_NEW_ARCHITECTURE = {USE_NEW_ARCHITECTURE}")
        print(f"  use_new_architecture() = {use_new_architecture()}")
        
        if USE_NEW_ARCHITECTURE:
            print("\n✓ New architecture is ENABLED")
            print("  - Using router_v2.py with strategy pattern")
            print("  - Using domain objects (ContentTask, ExecutionContext)")
            print("  - Using new routing logic")
        else:
            print("\n✓ Legacy architecture is ACTIVE")
            print("  - Using routing.py with if-else chains")
            print("  - Using dict-based interfaces")
            print("  - Using old routing logic")
        
        print("\nTo switch architecture, set in .env:")
        print("  USE_NEW_ARCHITECTURE=true   # Enable new architecture")
        print("  USE_NEW_ARCHITECTURE=false  # Use legacy architecture")
        print()
        
    except ImportError as e:
        print(f"\nSkipping (missing dependencies: {e})")
        print()


async def example_3_router_with_feature_flag():
    """Example 3: Router automatically uses correct architecture."""
    print("=" * 60)
    print("Example 3: Router with Feature Flag")
    print("=" * 60)
    
    from app.agents import get_agent_router
    
    router = get_agent_router()
    
    task_dict = {
        "category": "tech",
        "topic": "人工智能的最新发展趋势",
        "requirements": "需要包含2024年的最新信息",
        "length": "long",
        "style": "professional",
    }
    
    print("\nGetting agent suggestion...")
    suggestion = router.get_suggestion(task_dict)
    
    print(f"\nSuggestion:")
    print(f"  Recommended Agent: {suggestion['recommended']}")
    print(f"  Reason: {suggestion['reason']}")
    print(f"  Analysis: {suggestion['analysis']}")
    print()


async def example_4_direct_comparison():
    """Example 4: Direct comparison of old vs new interface."""
    print("=" * 60)
    print("Example 4: Old vs New Interface Comparison")
    print("=" * 60)
    
    from app.agents.simple_agent import SimpleAgent
    from app.domain.models import ContentTask, UserContext
    from app.domain.interfaces import ExecutionContext
    
    agent = SimpleAgent()
    
    # Old interface (dict-based)
    print("\n1. Old Interface (dict-based):")
    print("-" * 40)
    
    task_dict = {
        "category": "tech",
        "topic": "What is AI?",
        "requirements": "Brief explanation",
        "length": "short",
        "style": "casual",
        "module": "chat",
    }
    
    context_dict = {
        "user_id": "user123",
        "session_id": "session456",
        "recalled_memories": [],
        "user_preferences": {},
    }
    
    print(f"Task type: {type(task_dict)}")
    print(f"Context type: {type(context_dict)}")
    
    result_old = await agent.execute_dict(task_dict, context_dict)
    print(f"Result type: {type(result_old)}")
    print(f"Success: {result_old['success']}")
    
    # New interface (domain objects)
    print("\n2. New Interface (domain objects):")
    print("-" * 40)
    
    task = ContentTask(
        category="tech",
        topic="What is AI?",
        requirements="Brief explanation",
        length="short",
        style="casual",
        force_simple=False,
    )
    
    user_ctx = UserContext(
        user_id="user123",
        session_id="session456",
        recalled_memories=(),
        preferences={"_is_chat": True},
    )
    
    context = ExecutionContext(
        user_context=user_ctx,
        session_id="session456",
    )
    
    print(f"Task type: {type(task)}")
    print(f"Context type: {type(context)}")
    
    result_new = await agent.execute(task, context)
    print(f"Result type: {type(result_new)}")
    print(f"Success: {result_new.success}")
    
    print("\n3. Key Differences:")
    print("-" * 40)
    print("Old Interface:")
    print("  ✓ Uses plain dicts (flexible but error-prone)")
    print("  ✓ No type checking")
    print("  ✓ Easy to pass wrong keys")
    print("  ✓ Returns dict")
    
    print("\nNew Interface:")
    print("  ✓ Uses frozen dataclasses (immutable)")
    print("  ✓ Full type checking")
    print("  ✓ IDE autocomplete support")
    print("  ✓ Returns ContentResult object")
    print()


async def example_5_migration_strategy():
    """Example 5: Gradual migration strategy."""
    print("=" * 60)
    print("Example 5: Gradual Migration Strategy")
    print("=" * 60)
    
    print("\nPhase 1: New/Old Code Coexistence")
    print("-" * 40)
    print("1. Keep USE_NEW_ARCHITECTURE=false")
    print("2. New features use new architecture")
    print("3. Old features continue using old architecture")
    print("4. Use LegacyAgentAdapter for interop")
    
    print("\nPhase 2: Canary Deployment")
    print("-" * 40)
    print("1. Set USE_NEW_ARCHITECTURE=true in test env")
    print("2. Run full test suite")
    print("3. Enable for 10% of production traffic")
    print("4. Monitor error rates and performance")
    print("5. Gradually increase to 100%")
    
    print("\nPhase 3: Complete Migration")
    print("-" * 40)
    print("1. All traffic on new architecture")
    print("2. Keep old code for 1-2 release cycles")
    print("3. Remove old code and adapters")
    print("4. Remove USE_NEW_ARCHITECTURE flag")
    
    print("\nRollback Strategy:")
    print("-" * 40)
    print("If issues occur:")
    print("1. Set USE_NEW_ARCHITECTURE=false")
    print("2. Restart service (or wait for hot reload)")
    print("3. Verify service recovery")
    print("4. Analyze and fix issues")
    print("5. Re-enable when ready")
    print()


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Legacy Adapter Usage Examples")
    print("=" * 60)
    print()
    
    try:
        await example_1_basic_adapter_usage()
        await example_2_feature_flag_usage()
        await example_3_router_with_feature_flag()
        await example_4_direct_comparison()
        await example_5_migration_strategy()
        
        print("=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        print()
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
