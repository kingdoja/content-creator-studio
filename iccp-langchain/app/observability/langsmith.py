import os
from typing import Dict

from app.config import settings


def configure_langsmith() -> Dict[str, str | bool]:
    enabled = bool(settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY)
    if enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    return {
        "enabled": enabled,
        "project": settings.LANGCHAIN_PROJECT,
    }
