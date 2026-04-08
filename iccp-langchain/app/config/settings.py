"""
配置管理
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pathlib import Path

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "ICCP LangChain API"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    
    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./iccp.db"
    DATABASE_SYNC_URL: str = "sqlite:///./iccp.db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ADMIN_EMAILS: str = ""
    
    # LLM配置
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    CHAT_FAST_MODEL: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TIMEOUT: int = 60
    LLM_TEMPERATURE: float = 0.7
    IMAGE_MODEL: str = "gpt-image-1"
    VIDEO_PROVIDER: str = "mock"
    VIDEO_MODEL: str = "seedance-v1-pro"
    VIDEO_API_URL: str = ""
    VIDEO_STATUS_URL: str = ""
    VIDEO_TIMEOUT: int = 180
    VIDEO_POLL_INTERVAL: int = 2
    VIDEO_SAVE_LOCAL: bool = True
    SEEDANCE_BASE_URL: str = "https://operator.las.cn-beijing.volces.com"
    SEEDANCE_API_KEY: str = ""
    
    # 工具API
    TAVILY_API_KEY: str = ""
    MCP_ENABLED: bool = False
    MCP_GATEWAY_URL: str = ""
    MCP_DEFAULT_SERVER: str = ""
    MCP_TOOLS_JSON: str = ""

    # RAG配置
    RAG_EMBEDDING_MODEL: str = "text-embedding-3-small"
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 4
    RAG_SEARCH_CANDIDATE_LIMIT: int = 400
    RAG_TIME_WEIGHT_ENABLED: bool = True
    RAG_TIME_WEIGHT_ALPHA: float = 0.25
    RAG_TIME_DECAY_DAYS: int = 180
    RAG_VECTOR_CANDIDATE_MULTIPLIER: int = 5
    RAG_VECTOR_BACKEND: str = "memory"  # memory | milvus
    RAG_MILVUS_COLLECTION: str = "knowledge_chunks"
    RAG_MILVUS_METRIC: str = "IP"
    MEMORY_RECALL_TIMEOUT_SECONDS: int = 6
    MEMORY_RECALL_CANDIDATE_LIMIT: int = 300
    VIDEO_POLISH_TIMEOUT_SECONDS: int = 30
    
    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_BACKEND_URL: str = "redis://localhost:6379/2"
    
    # 限流
    RATE_LIMIT_PER_MINUTE: int = 10

    # 架构迁移特性开关 (Requirements: 10.1, 10.2)
    USE_NEW_ARCHITECTURE: bool = False

    # 微信小程序
    WX_APPID: str = ""
    WX_SECRET: str = ""

    # LangSmith / LangChain tracing
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "iccp-langchain"
    
    # 项目路径
    BASE_DIR: Path = Path(__file__).parent.parent.parent  # iccp-langchain/ root
    PROMPTS_DIR: Path = Path(__file__).parent.parent / "categories" / "prompts"  # app/categories/prompts
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )

settings = Settings()
