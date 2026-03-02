from fastapi import APIRouter

from app.config import settings


router = APIRouter()


@router.get("/status")
async def observability_status():
    enabled = bool(settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY)
    return {
        "success": True,
        "langsmith": {
            "enabled": enabled,
            "project": settings.LANGCHAIN_PROJECT,
        },
    }
