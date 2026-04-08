"""
FastAPI应用入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.config import settings
from app.api.v1 import chat, content, knowledge, memory, observability, wx_auth
from app.api.v1 import video as video_router
from app.auth import routes as auth_routes
from app.db.init_db import init_db
from app.domain.errors import AppError, ErrorCode
from app.observability import configure_langsmith
import logging
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    started_at = time.perf_counter()
    phase_ms = {}

    phase_start = time.perf_counter()
    status = configure_langsmith()
    phase_ms["configure_langsmith"] = int((time.perf_counter() - phase_start) * 1000)
    logger.info("LangSmith tracing enabled=%s project=%s", status["enabled"], status["project"])

    # 验证路由配置（Requirements: 7.5）
    phase_start = time.perf_counter()
    _validate_routing_config_on_startup()
    phase_ms["validate_routing_config"] = int((time.perf_counter() - phase_start) * 1000)

    phase_start = time.perf_counter()
    await init_db()
    phase_ms["init_db"] = int((time.perf_counter() - phase_start) * 1000)
    phase_ms["total_startup"] = int((time.perf_counter() - started_at) * 1000)
    logger.info("startup timings(ms)=%s", phase_ms)
    yield


def _validate_routing_config_on_startup() -> None:
    """
    在应用启动时验证路由配置文件。
    若配置文件存在但格式错误，则抛出 ConfigurationError 阻止启动。
    若配置文件不存在，则使用内置默认策略并记录日志（不阻止启动）。
    Requirements: 7.5
    """
    from pathlib import Path

    from app.config.routing_config import ConfigurationError, load_routing_config

    config_path = Path(__file__).parent / "config" / "routing_config.yaml"
    if not config_path.exists():
        logger.info("路由配置文件未找到，使用内置默认策略: %s", config_path)
        return

    try:
        load_routing_config(config_path)
        logger.info("路由配置验证通过: %s", config_path)
    except ConfigurationError as exc:
        logger.error("路由配置验证失败，应用启动中止: %s", exc)
        raise


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description="基于LangChain的多Agent内容创作平台",
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务（前端页面）
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    @app.get("/")
    async def index():
        """返回前端页面"""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "前端页面未找到，请访问 /docs 查看API文档"}

# ---------------------------------------------------------------------------
# Global exception handlers — convert all errors to AppError JSON format
# Requirements: 5.1
# ---------------------------------------------------------------------------

@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Handle domain AppError — return structured error response."""
    return JSONResponse(
        status_code=400,
        content=exc.to_dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors — return AppError-formatted response."""
    return JSONResponse(
        status_code=422,
        content={
            "error_code": ErrorCode.VALIDATION_ERROR,
            "message": "请求参数验证失败",
            "detail": str(exc),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler — wrap unexpected exceptions in AppError format."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": ErrorCode.UNKNOWN_ERROR,
            "message": "服务器内部错误",
            "detail": str(exc),
        },
    )


# 注册路由
app.include_router(content.router, prefix="/api/v1/content", tags=["content"])
app.include_router(video_router.router, prefix="/api/v1/content", tags=["video"])

# 新增：流式输出和监控路由
from app.api.v1 import streaming, metrics
app.include_router(streaming.router, prefix="/api/v1", tags=["streaming"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(wx_auth.router, prefix="/api/v1/auth", tags=["auth-wx"])
app.include_router(observability.router, prefix="/api/v1/observability", tags=["observability"])

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
