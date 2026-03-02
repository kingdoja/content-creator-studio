"""
内容创作 API：唯一执行入口为 LangGraph 编排（route → simple | react | reflection | plan_solve | rag）
"""
import asyncio
import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents import get_content_creation_graph, get_agent_router
from app.auth.dependencies import get_current_user, get_optional_current_user, resolve_scoped_user_id
from app.categories.loader import prompt_loader
from app.categories.config import CATEGORIES
from app.config import settings
from app.db.session import get_db_session
from app.evaluation import score_content
from app.llm.client import LLMClient
from app.memory import get_memory_manager
from app.models.content import ContentRecord
from app.prompting import prompt_optimizer
from app.services.cover_generator import generate_cover_image, CoverGenerationError
from app.models.user import User
from app.services.content_pipeline_service import (
    build_evaluate_response,
    build_refine_stream_complete_payload,
    build_refine_task_payload,
    build_content_response_dict,
    persist_content_record,
    persist_refine_record,
    prepare_content_generation_context,
    run_compare_agents,
    validate_category_or_raise,
)
from app.services.content_session_service import persist_content_session_messages
from app.services.video_generator import (
    create_story_video_task,
    generate_story_video,
    query_story_video_task,
    VideoGenerationError,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ContentRequest(BaseModel):
    """内容创作请求"""
    category: str = Field(..., description="内容板块")
    topic: str = Field(..., min_length=1, max_length=500, description="主题")
    requirements: Optional[str] = Field(None, description="额外要求")
    length: Optional[str] = Field("medium", description="内容长度: short/medium/long")
    style: Optional[str] = Field("professional", description="风格: casual/professional")
    force_simple: Optional[bool] = Field(False, description="是否强制使用 simpleagent")
    user_id: Optional[str] = Field("anonymous", description="会话用户标识")
    session_id: Optional[str] = Field(None, description="绑定会话ID（可选）")
    use_memory: Optional[bool] = Field(False, description="写作模块已停用：该参数保留仅为兼容")
    memory_top_k: Optional[int] = Field(4, ge=1, le=10, description="写作模块已停用：该参数保留仅为兼容")

class ContentResponse(BaseModel):
    """内容创作响应"""
    success: bool
    content: str
    agent: str
    tools_used: List[str]
    iterations: int
    agent_selected: Optional[str] = None
    task_analysis: Optional[Dict[str, Any]] = None
    quality_gate_passed: Optional[bool] = None
    quality_gate_reason: Optional[str] = None
    execution_trace: Optional[List[str]] = None
    error: Optional[str] = None


class CoverRequest(BaseModel):
    """标题封面图生成请求"""
    title: str = Field(..., min_length=1, max_length=200, description="文章标题")
    category: Optional[str] = Field(None, description="内容板块")
    style: Optional[str] = Field("cinematic", description="视觉风格")
    tone: Optional[str] = Field("bright", description="色调风格")
    size: Optional[str] = Field("1536x1024", description="图片尺寸")
    quality: Optional[str] = Field("high", description="生成质量")
    avoid_text: bool = Field(True, description="是否避免画面文字")


class CoverResponse(BaseModel):
    """标题封面图生成响应"""
    success: bool
    image_url: Optional[str] = None
    prompt_used: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None


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


class CompareRequest(BaseModel):
    category: str = Field(..., description="内容板块")
    topic: str = Field(..., min_length=1, max_length=500, description="主题")
    requirements: Optional[str] = Field(None, description="额外要求")
    length: Optional[str] = Field("medium", description="内容长度")
    style: Optional[str] = Field("professional", description="风格")
    agents: List[str] = Field(default_factory=lambda: ["react", "reflection"])


class EvaluateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)


class RefineRequest(BaseModel):
    category: str = Field(..., description="内容板块")
    topic: str = Field(..., min_length=1, max_length=500, description="主题")
    draft_content: str = Field(..., min_length=1, description="当前草稿")
    requirements: Optional[str] = Field(None, description="额外要求")
    length: Optional[str] = Field("medium", description="内容长度")
    style: Optional[str] = Field("professional", description="风格")
    user_id: Optional[str] = Field("anonymous", description="会话用户标识")


class CompareModelsRequest(BaseModel):
    category: str = Field(..., description="内容板块")
    topic: str = Field(..., min_length=1, max_length=500, description="主题")
    requirements: Optional[str] = Field(None, description="额外要求")
    length: Optional[str] = Field("medium", description="内容长度")
    style: Optional[str] = Field("professional", description="风格")
    models: List[str] = Field(default_factory=lambda: ["gpt-4", "gpt-4o-mini"])


class ContentHistoryItem(BaseModel):
    id: str
    category: str
    topic: str
    agent: str
    iterations: int
    created_at: str


class ContentHistoryResponse(BaseModel):
    success: bool
    items: List[ContentHistoryItem]


class ContentDetailResponse(BaseModel):
    success: bool
    item: Optional[Dict[str, Any]] = None


class PromptTemplateUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, description="新的板块 prompt 内容")


async def _build_video_memory_context(
    db: AsyncSession,
    *,
    input_text: str,
    user_id: str,
    use_memory: bool,
    memory_top_k: int,
) -> tuple[str, list[dict[str, Any]]]:
    if not use_memory:
        return "", []

    manager = get_memory_manager()
    try:
        recalled = await asyncio.wait_for(
            manager.recall(
                db,
                query=input_text,
                user_id=user_id or "anonymous",
                memory_types=["episodic", "semantic", "procedural"],
                top_k=max(1, min(memory_top_k, 10)),
            ),
            timeout=max(1, settings.MEMORY_RECALL_TIMEOUT_SECONDS),
        )
    except asyncio.TimeoutError:
        recalled = []
    if not recalled:
        return "", []

    lines = []
    for idx, item in enumerate(recalled):
        lines.append(
            f"[{idx + 1}] 来源={item.get('source_module', '')} 类型={item.get('memory_type', '')}\n"
            f"{item.get('content', '')}"
        )
    return "\n\n".join(lines), recalled


async def _persist_video_generation_memory(
    db: AsyncSession,
    *,
    user_id: str,
    session_id: Optional[str],
    input_text: str,
    genre: str,
    mood: str,
    storyline: str,
    provider: Optional[str],
    model: Optional[str],
    task_id: Optional[str],
    recalled: list[dict[str, Any]],
) -> None:
    manager = get_memory_manager()
    source_id = ((task_id or session_id or str(uuid4())) or str(uuid4()))[:36]
    summary = (
        f"视频主题：{input_text}\n"
        f"类型：{genre}；情绪：{mood}\n"
        f"剧情摘要：{(storyline or '')[:800]}\n"
        f"模型：{model or '-'}；提供商：{provider or '-'}"
    ).strip()
    saved_entry = await manager.store.create_memory_entry(
        db,
        user_id=user_id,
        memory_type="episodic",
        source_module="video",
        source_id=source_id,
        content=summary,
        importance=0.68,
        tags=["video_generation", genre, mood],
    )
    await manager.update_preference(
        db,
        user_id=user_id,
        key="preferred_video_genre",
        value=genre,
        confidence=0.62,
    )
    await manager.update_preference(
        db,
        user_id=user_id,
        key="preferred_video_mood",
        value=mood,
        confidence=0.62,
    )
    for item in recalled[:8]:
        source_memory_id = item.get("id")
        if not source_memory_id:
            continue
        await manager.link_memories(
            db,
            source_type="memory_entry",
            source_id=str(source_memory_id),
            target_type="memory_entry",
            target_id=saved_entry.id,
            relation="contextual_support",
            strength=float(item.get("score") or 0.6),
        )


@router.post("/create", response_model=ContentResponse)
async def create_content(
    request: ContentRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    """创建内容"""
    try:
        validate_category_or_raise(request.category, CATEGORIES)
        
        user_id = resolve_scoped_user_id(request.user_id, current_user)
        manager = get_memory_manager()
        task, _ = await prepare_content_generation_context(request=request)
        
        # 由 LangGraph 编排：route → react | reflection | plan_solve
        graph = get_content_creation_graph()
        final_state = await graph.ainvoke(
            {
                "task": task,
                "user_id": user_id,
                "session_id": request.session_id,
            }
        )
        
        response_data = build_content_response_dict(final_state)
        response = ContentResponse(**response_data)
        await persist_content_record(
            db=db,
            user_id=user_id,
            category=request.category,
            topic=request.topic,
            result=response_data,
        )

        if request.session_id:
            await persist_content_session_messages(
                db=db,
                manager=manager,
                session_id=request.session_id,
                user_id=user_id,
                topic=request.topic,
                content=response.content,
                module="content",
                metadata_extra={
                    "agent": response.agent,
                    "tools_used": response.tools_used,
                },
            )
        return response
        
    except HTTPException:
        raise
    except asyncio.CancelledError:
        # 常见于服务关闭（Ctrl+C）或客户端断开连接时，中断正在进行的 LLM/工具调用。
        # 这里尽量把错误语义说清楚，避免前端只看到 500。
        raise HTTPException(status_code=499, detail="请求已取消或服务正在停止")
    except Exception as e:
        logger.error(f"内容创建失败: {e}")
        raise HTTPException(status_code=500, detail=f"内容创建失败: {str(e)}")


@router.get("/history", response_model=ContentHistoryResponse)
async def get_content_history(
    limit: int = 8,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    safe_limit = max(1, min(limit, 50))
    stmt = (
        select(ContentRecord)
        .where(ContentRecord.user_id == scoped_user_id)
        .order_by(ContentRecord.created_at.desc())
        .limit(safe_limit)
    )
    records = (await db.execute(stmt)).scalars().all()
    items = [
        ContentHistoryItem(
            id=record.id,
            category=record.category,
            topic=record.topic,
            agent=record.agent,
            iterations=record.iterations,
            created_at=record.created_at.isoformat() if record.created_at else "",
        )
        for record in records
    ]
    return ContentHistoryResponse(success=True, items=items)


@router.get("/record/{record_id}", response_model=ContentDetailResponse)
async def get_content_detail(
    record_id: str,
    user_id: str = "anonymous",
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    scoped_user_id = resolve_scoped_user_id(user_id, current_user)
    stmt = select(ContentRecord).where(
        ContentRecord.id == record_id,
        ContentRecord.user_id == scoped_user_id,
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="内容记录不存在")
    return ContentDetailResponse(
        success=True,
        item={
            "id": record.id,
            "category": record.category,
            "topic": record.topic,
            "agent": record.agent,
            "content": record.content,
            "tools_used": [item for item in (record.tools_used or "").split(",") if item],
            "iterations": record.iterations,
            "created_at": record.created_at.isoformat() if record.created_at else "",
        },
    )


@router.post("/create/stream")
async def create_content_stream(
    request: ContentRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    validate_category_or_raise(request.category, CATEGORIES)

    user_id = resolve_scoped_user_id(request.user_id, current_user)
    manager = get_memory_manager()
    task, _ = await prepare_content_generation_context(request=request)
    graph = get_content_creation_graph()

    async def event_generator():
        latest_state: Dict[str, Any] = {}
        yield _sse("start", {"message": "stream started"})
        try:
            async for update in graph.astream(
                {
                    "task": task,
                    "user_id": user_id,
                    "session_id": request.session_id,
                },
                stream_mode="updates",
            ):
                for node_name, payload in update.items():
                    if isinstance(payload, dict):
                        latest_state.update(payload)
                        if payload.get("content"):
                            yield _sse("content_chunk", {"content": payload.get("content", ""), "node": node_name})
                        yield _sse("node_update", {"node": node_name, "keys": list(payload.keys())})
            yield _sse(
                "complete",
                {
                    "success": latest_state.get("success", False),
                    "content": latest_state.get("content", ""),
                    "agent": latest_state.get("agent", ""),
                    "tools_used": latest_state.get("tools_used", []),
                    "iterations": latest_state.get("iterations", 0),
                    "execution_trace": latest_state.get("execution_trace", []),
                    "error": latest_state.get("error"),
                },
            )
            await persist_content_record(
                db=db,
                user_id=user_id,
                category=request.category,
                topic=request.topic,
                result=latest_state,
            )
            if request.session_id and latest_state.get("content"):
                await persist_content_session_messages(
                    db=db,
                    manager=manager,
                    session_id=request.session_id,
                    user_id=user_id,
                    topic=request.topic,
                    content=latest_state.get("content", ""),
                    module="content_stream",
                    metadata_extra={
                        "agent": latest_state.get("agent", ""),
                        "tools_used": latest_state.get("tools_used", []),
                    },
                )
        except Exception as e:
            logger.error(f"流式内容创建失败: {e}")
            yield _sse("error", {"error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/categories")
async def get_categories():
    """获取所有板块"""
    return {
        "categories": [
            {"id": k, **v} for k, v in CATEGORIES.items()
        ]
    }


@router.get("/categories/{category_id}/prompt")
async def get_category_prompt(category_id: str, current_user: User = Depends(get_current_user)):
    validate_category_or_raise(category_id, CATEGORIES)
    prompt = prompt_loader.load_prompt(category_id)
    return {"success": True, "category_id": category_id, "content": prompt}


@router.put("/categories/{category_id}/prompt")
async def update_category_prompt(
    category_id: str,
    request: PromptTemplateUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    validate_category_or_raise(category_id, CATEGORIES)
    try:
        updated = prompt_loader.save_prompt(category_id, request.content)
        return {"success": True, "category_id": category_id, "content": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/suggest-agent")
async def suggest_agent(request: ContentRequest, current_user: User = Depends(get_current_user)):
    """获取 Agent 选择建议（与 LangGraph 路由逻辑一致）"""
    try:
        task = {
            "category": request.category,
            "topic": request.topic,
            "requirements": request.requirements,
            "length": request.length,
            "style": request.style,
            "force_simple": request.force_simple,
        }
        
        agent_router = get_agent_router()
        suggestion = agent_router.get_suggestion(task)
        
        return suggestion
        
    except Exception as e:
        logger.error(f"获取Agent建议失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取建议失败: {str(e)}")


@router.post("/generate-cover", response_model=CoverResponse)
async def generate_cover(request: CoverRequest):
    """根据标题生成封面图"""
    try:
        result = await generate_cover_image(request.model_dump())
        return CoverResponse(**result)
    except CoverGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"封面图生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"封面图生成失败: {str(e)}")


@router.post("/generate-story-video", response_model=StoryVideoResponse)
async def create_story_video(
    request: StoryVideoRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    """根据输入文本先润色剧情，再调用文生视频模型生成视频"""
    try:
        user_id = resolve_scoped_user_id(request.user_id, current_user)
        memory_context_text, recalled = await _build_video_memory_context(
            db,
            input_text=request.input_text,
            user_id=user_id,
            use_memory=bool(request.use_memory),
            memory_top_k=request.memory_top_k or 4,
        )
        payload = request.model_dump()
        payload["memory_context_text"] = memory_context_text
        result = await generate_story_video(payload)
        result["memory_recalled_count"] = len(recalled)
        result["memory_recalled"] = recalled
        if result.get("success") and result.get("storyline"):
            await _persist_video_generation_memory(
                db,
                user_id=user_id,
                session_id=request.session_id,
                input_text=request.input_text,
                genre=request.genre or "sci-fi",
                mood=request.mood or "epic",
                storyline=result.get("storyline", ""),
                provider=result.get("provider"),
                model=result.get("model"),
                task_id=result.get("task_id"),
                recalled=recalled,
            )
        return StoryVideoResponse(**result)
    except VideoGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"剧情视频生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"剧情视频生成失败: {str(e)}")


@router.post("/generate-story-video/start", response_model=StoryVideoResponse)
async def start_story_video_task(
    request: StoryVideoRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User | None = Depends(get_optional_current_user),
):
    """创建剧情视频任务（先润色剧情，再提交 Seedance 任务）"""
    try:
        user_id = resolve_scoped_user_id(request.user_id, current_user)
        memory_context_text, recalled = await _build_video_memory_context(
            db,
            input_text=request.input_text,
            user_id=user_id,
            use_memory=bool(request.use_memory),
            memory_top_k=request.memory_top_k or 4,
        )
        payload = request.model_dump()
        payload["memory_context_text"] = memory_context_text
        result = await create_story_video_task(payload)
        result["memory_recalled_count"] = len(recalled)
        result["memory_recalled"] = recalled

        if request.session_id and result.get("storyline"):
            manager = get_memory_manager()
            session = await manager.get_session(db, session_id=request.session_id)
            if session and session.get("user_id") == user_id:
                await manager.add_message(
                    db,
                    session_id=request.session_id,
                    role="user",
                    content=request.input_text,
                    message_type="task",
                    metadata={"module": "video"},
                )
                await manager.add_message(
                    db,
                    session_id=request.session_id,
                    role="assistant",
                    content=result.get("storyline", ""),
                    message_type="result",
                    metadata={
                        "module": "video",
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "memory_recalled_count": len(recalled),
                    },
                )
        if result.get("success") and result.get("storyline"):
            await _persist_video_generation_memory(
                db,
                user_id=user_id,
                session_id=request.session_id,
                input_text=request.input_text,
                genre=request.genre or "sci-fi",
                mood=request.mood or "epic",
                storyline=result.get("storyline", ""),
                provider=result.get("provider"),
                model=result.get("model"),
                task_id=result.get("task_id"),
                recalled=recalled,
            )
        return StoryVideoResponse(**result)
    except VideoGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建剧情视频任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建剧情视频任务失败: {str(e)}")


@router.get("/generate-story-video/tasks/{task_id}", response_model=StoryVideoTaskStatusResponse)
async def get_story_video_task_status(task_id: str, provider: Optional[str] = "seedance"):
    """查询剧情视频任务状态（用于前端轮询进度）"""
    try:
        result = await query_story_video_task(task_id=task_id, provider=provider or "seedance")
        return StoryVideoTaskStatusResponse(**result)
    except VideoGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"查询剧情视频任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询剧情视频任务失败: {str(e)}")


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/evaluate")
async def evaluate_content(request: EvaluateRequest, current_user: User = Depends(get_current_user)):
    return build_evaluate_response(content=request.content, topic=request.topic, scorer=score_content)


@router.post("/compare")
async def compare_agents(request: CompareRequest, current_user: User = Depends(get_current_user)):
    validate_category_or_raise(request.category, CATEGORIES)
    results, winner = await run_compare_agents(
        request=request,
        agent_router=get_agent_router(),
        scorer=score_content,
    )
    return {"success": True, "results": results, "winner": winner}


@router.post("/refine")
async def refine_content(
    request: RefineRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    validate_category_or_raise(request.category, CATEGORIES)
    task = build_refine_task_payload(request)
    router = get_agent_router()
    result = await router.reflection_agent.execute(
        task,
        context={"draft_content": request.draft_content, "max_reflections": 2},
    )
    scoped_user_id = resolve_scoped_user_id(request.user_id, current_user)
    await persist_refine_record(
        db=db,
        user_id=scoped_user_id,
        request=request,
        result=result,
        stream_mode=False,
    )
    evaluation = score_content(result.get("content", ""), topic=request.topic)
    return {"success": result.get("success", False), "result": result, "evaluation": evaluation}


@router.post("/refine/stream")
async def refine_content_stream(
    request: RefineRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    validate_category_or_raise(request.category, CATEGORIES)
    task = build_refine_task_payload(request)
    router = get_agent_router()

    async def event_generator():
        yield _sse("start", {"message": "refine stream started"})
        yield _sse("node_update", {"node": "reflection_start", "keys": ["task", "draft_content"]})
        try:
            result = await router.reflection_agent.execute(
                task,
                context={"draft_content": request.draft_content, "max_reflections": 2},
            )
            scoped_user_id = resolve_scoped_user_id(request.user_id, current_user)
            await persist_refine_record(
                db=db,
                user_id=scoped_user_id,
                request=request,
                result=result,
                stream_mode=True,
            )
            if result.get("content"):
                yield _sse("content_chunk", {"content": result.get("content", ""), "node": "reflection_complete"})
            yield _sse("node_update", {"node": "reflection_complete", "keys": list(result.keys())})
            yield _sse("complete", build_refine_stream_complete_payload(result))
        except Exception as e:
            logger.error(f"流式二次编辑失败: {e}")
            yield _sse("error", {"error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/compare-models")
async def compare_models(request: CompareModelsRequest, current_user: User = Depends(get_current_user)):
    validate_category_or_raise(request.category, CATEGORIES)

    task = {
        "category": request.category,
        "topic": request.topic,
        "requirements": request.requirements,
        "length": request.length,
        "style": request.style,
    }
    pkg = prompt_optimizer.build_package(task, mode="default")

    results = []
    for model_name in request.models:
        model_name = model_name.strip()
        if not model_name:
            continue
        try:
            llm = LLMClient(model=model_name)
            content = await llm.achat(
                [
                    {"role": "system", "content": pkg.system_prompt},
                    {"role": "user", "content": pkg.user_prompt},
                ],
                temperature=0.7,
            )
            evaluation = score_content(content, topic=request.topic)
            results.append(
                {
                    "model": model_name,
                    "success": True,
                    "content": content,
                    "evaluation": evaluation,
                }
            )
        except Exception as e:
            results.append(
                {
                    "model": model_name,
                    "success": False,
                    "content": "",
                    "error": str(e),
                    "evaluation": {"total_score": 0, "dimensions": {}, "advice": ["模型调用失败"]},
                }
            )

    winner = None
    successful = [item for item in results if item.get("success")]
    if successful:
        winner = max(successful, key=lambda x: x["evaluation"]["total_score"])["model"]

    return {"success": True, "results": results, "winner": winner}
