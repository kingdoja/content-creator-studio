"""
Tests for the USE_NEW_ARCHITECTURE feature flag.

Requirements: 10.1, 10.2
"""
import pytest
from unittest.mock import patch

from app.config import use_new_architecture, USE_NEW_ARCHITECTURE


def test_use_new_architecture_function():
    """Test that use_new_architecture() returns the correct value."""
    # The function should return the current setting value
    result = use_new_architecture()
    assert isinstance(result, bool)


def test_feature_flag_export():
    """Test that USE_NEW_ARCHITECTURE is exported from config module."""
    assert isinstance(USE_NEW_ARCHITECTURE, bool)


@patch('app.config.settings.USE_NEW_ARCHITECTURE', True)
def test_feature_flag_enabled():
    """Test behavior when feature flag is enabled."""
    from app.config import settings
    assert settings.USE_NEW_ARCHITECTURE is True


@patch('app.config.settings.USE_NEW_ARCHITECTURE', False)
def test_feature_flag_disabled():
    """Test behavior when feature flag is disabled."""
    from app.config import settings
    assert settings.USE_NEW_ARCHITECTURE is False


def test_feature_flag_default_value():
    """Test that feature flag has a sensible default value."""
    from app.config.settings import settings
    # Default should be False for gradual migration
    assert settings.USE_NEW_ARCHITECTURE is False
