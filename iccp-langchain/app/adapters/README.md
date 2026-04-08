# Adapters Module

This module provides adapters for gradual migration between old and new architecture.

## Overview

The adapters enable a smooth transition from the old dict-based interface to the new domain object interface without breaking existing code.

## Components

### LegacyAgentAdapter

Wraps a new-style Agent (accepting domain objects) and exposes the old dict-based interface.

**Usage:**

```python
from app.adapters.legacy_adapter import LegacyAgentAdapter
from app.agents.simple_agent import SimpleAgent

# Create new-style agent
agent = SimpleAgent()

# Wrap with adapter
adapter = LegacyAgentAdapter(agent)

# Use old interface
result = await adapter.execute(task_dict, context_dict)
```

### Feature Flag: USE_NEW_ARCHITECTURE

Controls which architecture path is used throughout the application.

**Configuration:**

```bash
# In .env file
USE_NEW_ARCHITECTURE=false  # Use legacy architecture (default)
USE_NEW_ARCHITECTURE=true   # Use new architecture
```

**Usage in code:**

```python
from app.config import USE_NEW_ARCHITECTURE, use_new_architecture

if USE_NEW_ARCHITECTURE:
    # New architecture path
    pass
else:
    # Legacy architecture path
    pass
```

## Interface Comparison

### Old Interface (Dict-based)

```python
async def execute(
    self,
    task: Dict[str, Any],
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ...
```

**Pros:**
- Flexible
- Easy to add new fields
- No strict schema

**Cons:**
- No type checking
- Easy to make typos
- No IDE autocomplete
- Runtime errors for missing keys

### New Interface (Domain Objects)

```python
async def execute(
    self,
    task: ContentTask,
    context: ExecutionContext,
) -> ContentResult:
    ...
```

**Pros:**
- Full type checking
- IDE autocomplete
- Immutable (frozen dataclasses)
- Clear contracts
- Compile-time error detection

**Cons:**
- Less flexible
- Requires schema changes for new fields

## Migration Path

### Phase 1: Coexistence (Current)

- `USE_NEW_ARCHITECTURE=false`
- New features use new architecture
- Old features use old architecture
- Adapters bridge the gap

### Phase 2: Canary Deployment

- `USE_NEW_ARCHITECTURE=true` in test
- Monitor metrics
- Gradual rollout (10% → 50% → 100%)

### Phase 3: Complete Migration

- All traffic on new architecture
- Remove old code after 1-2 cycles
- Remove adapters
- Remove feature flag

## Testing

Run adapter tests:

```bash
# Full test suite (requires dependencies)
pytest tests/test_legacy_adapter.py -v

# Simple standalone test
python test_adapter_simple.py
```

## Examples

See `examples/adapter_usage_example.py` for comprehensive usage examples.

## Related Documentation

- [Gradual Migration Guide](../../docs/渐进式迁移指南.md)
- [Architecture Design](../../.kiro/specs/architecture-refactoring/design.md)
- [Requirements](../../.kiro/specs/architecture-refactoring/requirements.md)

## Requirements

This module implements:
- Requirement 10.1: Adapter for old/new interface compatibility
- Requirement 10.2: Feature flag for architecture control
