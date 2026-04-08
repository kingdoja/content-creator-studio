"""
Unified error model and error code constants.
Requirements: 5.1
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

class ErrorCode:
    INVALID_CATEGORY = "INVALID_CATEGORY"
    AGENT_EXECUTION_FAILED = "AGENT_EXECUTION_FAILED"
    MEMORY_TIMEOUT = "MEMORY_TIMEOUT"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    KNOWLEDGE_EMPTY = "KNOWLEDGE_EMPTY"
    CONFIG_INVALID = "CONFIG_INVALID"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# ---------------------------------------------------------------------------
# Unified error model
# ---------------------------------------------------------------------------

@dataclass
class AppError(Exception):
    """Unified application error with a machine-readable code and human-readable message."""
    error_code: str
    message: str
    detail: str | None = None

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict for API responses."""
        result: dict = {"error_code": self.error_code, "message": self.message}
        if self.detail is not None:
            result["detail"] = self.detail
        return result
