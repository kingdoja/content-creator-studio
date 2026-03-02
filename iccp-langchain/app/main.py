"""
FastAPI应用入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.config import settings
from app.api.v1 import chat, content, knowledge, memory, observability, wx_auth
from app.auth import routes as auth_routes
from app.db.init_db import init_db
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

    phase_start = time.perf_counter()
    await init_db()
    phase_ms["init_db"] = int((time.perf_counter() - phase_start) * 1000)
    phase_ms["total_startup"] = int((time.perf_counter() - started_at) * 1000)
    logger.info("startup timings(ms)=%s", phase_ms)
    yield


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

# 注册路由
app.include_router(content.router, prefix="/api/v1/content", tags=["content"])
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
