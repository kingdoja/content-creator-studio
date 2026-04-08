"""
Configuration module for feature flags and architecture migration control.

This module provides easy access to feature flags that control the gradual
migration from old to new architecture.

NOTE: This is a compatibility shim. The actual configuration is now in
app/config/settings.py. This file re-exports settings for backward compatibility.

For new code, prefer importing directly from app.config.settings:
    from app.config.settings import settings

Requirements: 10.1, 10.2
"""
import warnings

# Issue deprecation warning for direct imports from this module
warnings.warn(
    "Importing from app.config is deprecated. "
    "Please use 'from app.config.settings import settings' instead. "
    "This compatibility shim will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

from app.config.settings import settings


def use_new_architecture() -> bool:
    """
    Check if the new architecture should be used.

    Returns:
        True if USE_NEW_ARCHITECTURE feature flag is enabled, False otherwise.
    """
    return settings.USE_NEW_ARCHITECTURE


# Export the feature flag for convenient access
USE_NEW_ARCHITECTURE = settings.USE_NEW_ARCHITECTURE
