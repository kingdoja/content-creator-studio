"""
流式输出 API 端点
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.domain.models import ContentTask
from app.services.streaming_service import get_streaming_service, StreamChunk
from app.auth.dependencies import get_optional_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaming", tags=["streaming"])


class StreamRequest(BaseModel):
    """流式请求"""
    category: str
    topic: str
    requirements: str = ""
    length: str = "medium"
    style: str = "professional"


@router.post("/create")
async def create_content_stream(
    request: StreamRequest,
    user=Depends(get_optional_current_user)
):
    """
    流式生成内容
    
    返回 Server-Sent Events (SSE) 格式的流式数据。
    
    Example:
        ```javascript
        const eventSource = new EventSource('/api/v1/streaming/create');
        eventSource.onmessage = (event) => {
            const chunk = JSON.parse(event.data);
            console.log(chunk.content);
        };
        ```
    """
    try:
        # 创建任务
        task = ContentTask(
            category=request.category,
            topic=request.topic,
            requirements=request.requirements,
            length=request.length,
            style=request.style,
            user_id=user.id if user else "anonymous",
            session_id=None
        )
        
        # 获取流式服务
        streaming_service = get_streaming_service()
        
        # 定义生成器
        async def generate():
            try:
                async for chunk in streaming_service.create_content_stream(task):
                    # 转换为 SSE 格式
                    data = {
                        "content": chunk.content,
                        "type": chunk.chunk_type,
                        "metadata": chunk.metadata
                    }
                    yield f"data: {data}\n\n"
            except Exception as e:
                logger.error(f"Stream generation error: {e}")
                error_data = {
                    "content": str(e),
                    "type": "error",
                    "metadata": {"error_type": type(e).__name__}
                }
                yield f"data: {error_data}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to start stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-with-progress")
async def create_content_stream_with_progress(
    request: StreamRequest,
    user=Depends(get_optional_current_user)
):
    """
    带进度的流式生成
    
    包含阶段信息和进度百分比。
    """
    try:
        task = ContentTask(
            category=request.category,
            topic=request.topic,
            requirements=request.requirements,
            length=request.length,
            style=request.style,
            user_id=user.id if user else "anonymous",
            session_id=None
        )
        
        streaming_service = get_streaming_service()
        
        async def generate():
            try:
                async for chunk in streaming_service.create_content_stream_with_progress(task):
                    import json
                    data = json.dumps({
                        "content": chunk.content,
                        "type": chunk.chunk_type,
                        "metadata": chunk.metadata
                    })
                    yield f"data: {data}\n\n"
            except Exception as e:
                logger.error(f"Stream generation error: {e}")
                import json
                error_data = json.dumps({
                    "content": str(e),
                    "type": "error",
                    "metadata": {"error_type": type(e).__name__}
                })
                yield f"data: {error_data}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to start stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))
