"""
流式输出服务

提供流式生成内容的能力，支持实时返回生成进度。
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional
from dataclasses import dataclass

from app.domain.models import ContentTask
from app.llm.client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """流式输出块"""
    content: str
    chunk_type: str  # "start", "content", "end", "error"
    metadata: Optional[dict] = None


class StreamingService:
    """
    流式输出服务
    
    提供流式生成内容的能力，实时返回生成进度。
    
    Example:
        service = StreamingService()
        
        async for chunk in service.create_content_stream(task):
            print(chunk.content, end="", flush=True)
    """
    
    def __init__(self):
        self.llm_client = get_llm_client()
    
    async def create_content_stream(
        self,
        task: ContentTask
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        流式生成内容
        
        Args:
            task: 内容创作任务
        
        Yields:
            StreamChunk: 内容块
        
        Example:
            async for chunk in service.create_content_stream(task):
                if chunk.chunk_type == "content":
                    print(chunk.content, end="")
        """
        try:
            # 发送开始信号
            yield StreamChunk(
                content="",
                chunk_type="start",
                metadata={"task": task.topic}
            )
            
            # 构建 prompt
            prompt = self._build_prompt(task)
            
            # 流式调用 LLM
            async for token in self.llm_client.stream(prompt):
                yield StreamChunk(
                    content=token,
                    chunk_type="content"
                )
            
            # 发送结束信号
            yield StreamChunk(
                content="",
                chunk_type="end",
                metadata={"status": "completed"}
            )
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield StreamChunk(
                content=str(e),
                chunk_type="error",
                metadata={"error_type": type(e).__name__}
            )
    
    async def create_content_stream_with_progress(
        self,
        task: ContentTask
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        带进度的流式生成
        
        包含阶段信息（分析、生成、优化等）
        
        Yields:
            StreamChunk: 内容块，包含进度信息
        """
        try:
            # 阶段 1: 分析任务
            yield StreamChunk(
                content="正在分析任务...\n",
                chunk_type="progress",
                metadata={"stage": "analyzing", "progress": 0.1}
            )
            await asyncio.sleep(0.5)  # 模拟分析时间
            
            # 阶段 2: 生成内容
            yield StreamChunk(
                content="开始生成内容...\n",
                chunk_type="progress",
                metadata={"stage": "generating", "progress": 0.3}
            )
            
            # 流式生成
            prompt = self._build_prompt(task)
            token_count = 0
            
            async for token in self.llm_client.stream(prompt):
                token_count += 1
                yield StreamChunk(
                    content=token,
                    chunk_type="content",
                    metadata={"token_count": token_count}
                )
            
            # 阶段 3: 完成
            yield StreamChunk(
                content="\n生成完成！\n",
                chunk_type="progress",
                metadata={"stage": "completed", "progress": 1.0}
            )
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield StreamChunk(
                content=f"\n错误: {str(e)}\n",
                chunk_type="error",
                metadata={"error_type": type(e).__name__}
            )
    
    def _build_prompt(self, task: ContentTask) -> str:
        """构建 prompt"""
        return f"""请根据以下要求创作内容：

板块：{task.category}
主题：{task.topic}
要求：{task.requirements}
长度：{task.length}
风格：{task.style}

请开始创作："""


class StreamBuffer:
    """
    流式缓冲区
    
    用于缓冲流式输出，支持按行或按块输出。
    
    Example:
        buffer = StreamBuffer(chunk_size=100)
        
        async for chunk in llm_stream:
            buffer.add(chunk)
            if buffer.should_flush():
                yield buffer.flush()
    """
    
    def __init__(self, chunk_size: int = 100, flush_on_newline: bool = True):
        self.chunk_size = chunk_size
        self.flush_on_newline = flush_on_newline
        self._buffer = []
        self._current_size = 0
    
    def add(self, content: str):
        """添加内容到缓冲区"""
        self._buffer.append(content)
        self._current_size += len(content)
    
    def should_flush(self) -> bool:
        """是否应该刷新缓冲区"""
        if self._current_size >= self.chunk_size:
            return True
        
        if self.flush_on_newline:
            return any('\n' in chunk for chunk in self._buffer)
        
        return False
    
    def flush(self) -> str:
        """刷新缓冲区并返回内容"""
        content = ''.join(self._buffer)
        self._buffer.clear()
        self._current_size = 0
        return content
    
    def get_buffered_content(self) -> str:
        """获取缓冲区内容（不清空）"""
        return ''.join(self._buffer)


# 全局流式服务实例
_streaming_service = None


def get_streaming_service() -> StreamingService:
    """获取流式服务实例"""
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = StreamingService()
    return _streaming_service
