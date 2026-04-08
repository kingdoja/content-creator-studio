"""
内容创作 API — 端点函数只做请求验证、调用 ContentService、序列化响应。
业务逻辑全部委托给 ContentService 和 ContentPipelineService。
视频相关端点已迁移到 app/api/v1/video.py。
Requirements: 8.1, 8.2
"""
import asyncio
import json
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
from app.services.content_service import ContentService, CreateContentRequest, RefineContentRequest
from app.domain.models import ContentTask
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

_content_service = ContentService()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _request_to_content_task(request: ContentRequest) -> ContentTask:
    """Convert ContentRequest DTO to ContentTask domain object."""
    return ContentTask(
        category=request.category,
        topic=request.topic,
        requirements=request.requirements or "",
        length=request.length or "medium",
        style=request.style or "professional",
        force_simple=bool(request.force_simple),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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

        task = _request_to_content_task(request)
        svc_request = CreateContentRequest(
            task=task,
            user_id=user_id,
            session_id=request.session_id,
            use_memory=bool(request.use_memory),
            memory_top_k=request.memory_top_k or 4,
        )
        result = await _content_service.create_content(svc_request)

        response = ContentResponse(
            success=result.success,
            content=result.content,
            agent=result.agent,
            tools_used=list(result.tools_used or []),
            iterations=result.iterations,
            execution_trace=(result.metadata or {}).get("execution_trace"),
            task_analysis=(result.metadata or {}).get("task_analysis"),
            quality_gate_passed=(result.metadata or {}).get("quality_passed"),
            error=result.error,
        )

        await persist_content_record(
            db=db,
            user_id=user_id,
            category=request.category,
            topic=request.topic,
            result={
                "success": result.success,
                "content": result.content,
                "agent": result.agent,
                "tools_used": list(result.tools_used or []),
                "iterations": result.iterations,
                "error": result.error,
            },
        )

        if request.session_id:
            await persist_content_session_messages(
                db=db,
                manager=manager,
                session_id=request.session_id,
                user_id=user_id,
                topic=request.topic,
                content=result.content,
                module="content",
                metadata_extra={
                    "agent": result.agent,
                    "tools_used": list(result.tools_used or []),
                },
            )
        return response

    except HTTPException:
        raise
    except asyncio.CancelledError:
        raise HTTPException(status_code=499, detail="请求已取消或服务正在停止")
    except Exception as e:
        logger.error("内容创建失败: %s", e)
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
                        result_obj = payload.get("result")
                        chunk_content = (
                            result_obj.content
                            if (result_obj and hasattr(result_obj, "content"))
                            else payload.get("content")
                        )
                        if chunk_content:
                            yield _sse("content_chunk", {"content": chunk_content, "node": node_name})
                        yield _sse("node_update", {"node": node_name, "keys": list(payload.keys())})

            final = build_content_response_dict(latest_state)
            yield _sse("complete", {
                "success": final["success"],
                "content": final["content"],
                "agent": final["agent"],
                "tools_used": final["tools_used"],
                "iterations": final["iterations"],
                "execution_trace": final["execution_trace"],
                "error": final["error"],
            })
            await persist_content_record(
                db=db,
                user_id=user_id,
                category=request.category,
                topic=request.topic,
                result=final,
            )
            if request.session_id and final.get("content"):
                await persist_content_session_messages(
                    db=db,
                    manager=manager,
                    session_id=request.session_id,
                    user_id=user_id,
                    topic=request.topic,
                    content=final.get("content", ""),
                    module="content_stream",
                    metadata_extra={
                        "agent": final.get("agent", ""),
                        "tools_used": final.get("tools_used", []),
                    },
                )
        except Exception as e:
            logger.error("流式内容创建失败: %s", e)
            yield _sse("error", {"error": str(e)})

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/categories")
async def get_categories():
    """获取所有板块"""
    return {"categories": [{"id": k, **v} for k, v in CATEGORIES.items()]}


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
        logger.error("获取Agent建议失败: %s", e)
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
        logger.error("封面图生成失败: %s", e)
        raise HTTPException(status_code=500, detail=f"封面图生成失败: {str(e)}")


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
    scoped_user_id = resolve_scoped_user_id(request.user_id, current_user)

    task = ContentTask(
        category=request.category,
        topic=request.topic,
        requirements=request.requirements or "",
        length=request.length or "medium",
        style=request.style or "professional",
    )
    svc_request = RefineContentRequest(
        task=task,
        draft_content=request.draft_content,
        user_id=scoped_user_id,
        max_reflections=2,
    )
    result = await _content_service.refine_content(svc_request)

    await persist_refine_record(
        db=db,
        user_id=scoped_user_id,
        request=request,
        result={
            "success": result.success,
            "content": result.content,
            "agent": result.agent,
            "tools_used": list(result.tools_used or []),
            "iterations": result.iterations,
            "error": result.error,
        },
        stream_mode=False,
    )
    evaluation = score_content(result.content, topic=request.topic)
    return {
        "success": result.success,
        "result": {
            "content": result.content,
            "agent": result.agent,
            "iterations": result.iterations,
            "error": result.error,
        },
        "evaluation": evaluation,
    }


@router.post("/refine/stream")
async def refine_content_stream(
    request: RefineRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    validate_category_or_raise(request.category, CATEGORIES)
    task = build_refine_task_payload(request)
    agent_router = get_agent_router()

    async def event_generator():
        yield _sse("start", {"message": "refine stream started"})
        yield _sse("node_update", {"node": "reflection_start", "keys": ["task", "draft_content"]})
        try:
            result = await agent_router.reflection_agent.execute(
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
            logger.error("流式二次编辑失败: %s", e)
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
            results.append({
                "model": model_name,
                "success": True,
                "content": content,
                "evaluation": evaluation,
            })
        except Exception as e:
            results.append({
                "model": model_name,
                "success": False,
                "content": "",
                "error": str(e),
                "evaluation": {"total_score": 0, "dimensions": {}, "advice": ["模型调用失败"]},
            })

    winner = None
    successful = [item for item in results if item.get("success")]
    if successful:
        winner = max(successful, key=lambda x: x["evaluation"]["total_score"])["model"]

    return {"success": True, "results": results, "winner": winner}
