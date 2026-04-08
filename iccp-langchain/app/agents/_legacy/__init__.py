"""
Legacy agents module - DEPRECATED

This module contains deprecated agent implementations that have been replaced
by the new architecture. These are kept for backward compatibility only.

Deprecated agents:
- plan_solve_agent.py -> Merged into reflection_agent.py
- rag_agent.py -> Replaced by KnowledgeSearchTool
- router.py -> Replaced by router_v2.py
- routing.py -> Replaced by analyzer.py + strategies.py

To use the new architecture, set USE_NEW_ARCHITECTURE=true in your .env file.

See docs/渐进式迁移指南.md for migration instructions.
"""
import warnings

warnings.warn(
    "The _legacy module is deprecated and will be removed in a future version. "
    "Please migrate to the new architecture by setting USE_NEW_ARCHITECTURE=true. "
    "See docs/渐进式迁移指南.md for details.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
from ._legacy.plan_solve_agent import *  # noqa: F401, F403
from ._legacy.rag_agent import *  # noqa: F401, F403
from ._legacy.router import *  # noqa: F401, F403
from ._legacy.routing import *  # noqa: F401, F403
