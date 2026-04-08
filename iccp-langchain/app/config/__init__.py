# config package
# Re-export settings so that `from app.config import settings` keeps working
# after app/config.py was converted to a package directory.
from app.config.settings import settings  # noqa: F401


def use_new_architecture() -> bool:
    """
    Helper function to check if new architecture is enabled.
    
    Requirements: 10.1, 10.2
    """
    return settings.USE_NEW_ARCHITECTURE


# Export the flag value for convenience
USE_NEW_ARCHITECTURE = settings.USE_NEW_ARCHITECTURE

__all__ = ["settings", "use_new_architecture", "USE_NEW_ARCHITECTURE"]
