"""
视频生成 API — 剧情润色与文生视频端点。

端点函数只做请求验证、调用 VideoAppService、序列化响应。
业务逻辑全部委托给 VideoAppService。
Requirements: 8.1, 6.1
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_optional_current_user, resolve_scoped_user_id
from app.db.session import get_db_session
from app.models.user import User
from app.services.video_app_service import VideoAppService
from app.services.video_generator import VideoGenerationError
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

_video_service = VideoAppService()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StoryVideoRequest(BaseModel):
    """剧情润色 + 文生视频请求"""
    input_text: str = Field(..., min_length=1, max_length=1500, description="标题或段落输入")
    genre: Optional[str] = Field("sci-fi", description="剧情类型")
    mood: Optional[str] = Field("epic", description="情绪基调")
    duration_seconds: Optional[int] = Field(8, description="时长，单位秒")
    aspect_ratio: Optional[str] = Field("16:9", description="画面比例")
    model: Optional[str] = Field(None, description="视频模型")
    provider: Optional[str] = Field(None, description="视频模型提供商")
    extra_requirements: Optional[str] = Field(None, description="额外要求")
    resolution: Optional[str] = Field("720p", description="分辨率: 480p/720p/1080p")
    watermark: Optional[bool] = Field(False, description="是否加水印")
    camera_fixed: Optional[bool] = Field(False, description="是否固定机位")
    seed: Optional[int] = Field(None, description="随机种子")
    generate_audio: Optional[bool] = Field(None, description="是否生成音频（1.5 pro 支持）")
    return_last_frame: Optional[bool] = Field(None, description="是否返回尾帧图")
    execution_expires_after: Optional[int] = Field(None, description="任务超时阈值（秒）")
    draft: Optional[bool] = Field(None, description="是否开启 draft 模式")
    callback_url: Optional[str] = Field(None, description="任务状态回调地址")
    user_id: Optional[str] = Field("anonymous", description="会话用户标识")
    session_id: Optional[str] = Field(None, description="绑定会话ID（可选）")
    use_memory: Optional[bool] = Field(False, description="是否启用长期记忆增强")
    memory_top_k: Optional[int] = Field(4, ge=1, le=10, description="记忆召回条数")


class StoryVideoResponse(BaseModel):
    """剧情润色 + 文生视频响应"""
    success: bool
    storyline: str
    video_prompt: str
    video_url: Optional[str] = None
    task_id: Optional[str] = None
    status: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    progress_percent: Optional[int] = None
    memory_recalled_count: Optional[int] = None
    memory_recalled: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class StoryVideoTaskStatusResponse(BaseModel):
    """剧情视频任务状态响应"""
    success: bool
    task_id: str
    status: str
    progress_percent: int
    video_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    error: Optional[str] = None
    updated_at: Optional[int] = None
    created_at: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate-story-video", response_model=StoryVideoResponse)
async def create_story_video(
    request: StoryVideoRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    """根据输入文本先润色剧情，再调用文生视频模型生成视频（同步等待）"""
    try:
        user_id = resolve_scoped_user_id(request.user_id, current_user)
        result = await _video_service.generate_video(
            db,
            payload=request.model_dump(),
            user_id=user_id,
            session_id=request.session_id,
            use_memory=bool(request.use_memory),
            memory_top_k=request.memory_top_k or 4,
        )
        return StoryVideoResponse(**result)
    except VideoGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("剧情视频生成失败: %s", e)
        raise HTTPException(status_code=500, detail=f"剧情视频生成失败: {str(e)}")


@router.post("/generate-story-video/start", response_model=StoryVideoResponse)
async def start_story_video_task(
    request: StoryVideoRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    """创建剧情视频任务（先润色剧情，再提交 Seedance 任务，异步轮询）"""
    try:
        user_id = resolve_scoped_user_id(request.user_id, current_user)
        result = await _video_service.start_video_task(
            db,
            payload=request.model_dump(),
            user_id=user_id,
            session_id=request.session_id,
            use_memory=bool(request.use_memory),
            memory_top_k=request.memory_top_k or 4,
        )
        return StoryVideoResponse(**result)
    except VideoGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("创建剧情视频任务失败: %s", e)
        raise HTTPException(status_code=500, detail=f"创建剧情视频任务失败: {str(e)}")


@router.get("/generate-story-video/tasks/{task_id}", response_model=StoryVideoTaskStatusResponse)
async def get_story_video_task_status(task_id: str, provider: Optional[str] = "seedance"):
    """查询剧情视频任务状态（用于前端轮询进度）"""
    try:
        result = await _video_service.get_video_task_status(
            task_id=task_id, provider=provider or "seedance"
        )
        return StoryVideoTaskStatusResponse(**result)
    except VideoGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("查询剧情视频任务失败: %s", e)
        raise HTTPException(status_code=500, detail=f"查询剧情视频任务失败: {str(e)}")
