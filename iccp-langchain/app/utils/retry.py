"""
重试机制和错误处理工具

提供装饰器和工具函数用于自动重试失败的操作，支持指数退避和自定义重试策略。
"""
import asyncio
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Optional
import time
import random

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """重试失败错误"""
    def __init__(self, message: str, last_exception: Exception, attempts: int):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
    jitter: bool = True
):
    """
    异步函数重试装饰器
    
    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟时间（秒）
        backoff: 退避倍数
        max_delay: 最大延迟时间（秒）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
        jitter: 是否添加随机抖动
    
    Example:
        @retry_async(max_attempts=3, delay=1.0, backoff=2.0)
        async def call_api():
            response = await client.post(...)
            return response
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {attempt} attempts: {e}",
                            extra={"attempts": attempt, "error": str(e)}
                        )
                        raise RetryError(
                            f"Failed after {attempt} attempts",
                            last_exception,
                            attempt
                        )
                    
                    # 计算延迟时间
                    wait_time = min(current_delay, max_delay)
                    if jitter:
                        wait_time = wait_time * (0.5 + random.random())
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {wait_time:.2f}s: {e}",
                        extra={"attempt": attempt, "wait_time": wait_time, "error": str(e)}
                    )
                    
                    # 调用重试回调
                    if on_retry:
                        try:
                            await on_retry(attempt, e, wait_time)
                        except Exception as callback_error:
                            logger.error(f"Retry callback failed: {callback_error}")
                    
                    # 等待后重试
                    await asyncio.sleep(wait_time)
                    current_delay *= backoff
            
            # 理论上不会到这里
            raise RetryError(
                f"Failed after {max_attempts} attempts",
                last_exception,
                max_attempts
            )
        
        return wrapper
    return decorator


def retry_sync(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
    jitter: bool = True
):
    """
    同步函数重试装饰器
    
    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟时间（秒）
        backoff: 退避倍数
        max_delay: 最大延迟时间（秒）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
        jitter: 是否添加随机抖动
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {attempt} attempts: {e}",
                            extra={"attempts": attempt, "error": str(e)}
                        )
                        raise RetryError(
                            f"Failed after {attempt} attempts",
                            last_exception,
                            attempt
                        )
                    
                    # 计算延迟时间
                    wait_time = min(current_delay, max_delay)
                    if jitter:
                        wait_time = wait_time * (0.5 + random.random())
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {wait_time:.2f}s: {e}",
                        extra={"attempt": attempt, "wait_time": wait_time, "error": str(e)}
                    )
                    
                    # 调用重试回调
                    if on_retry:
                        try:
                            on_retry(attempt, e, wait_time)
                        except Exception as callback_error:
                            logger.error(f"Retry callback failed: {callback_error}")
                    
                    # 等待后重试
                    time.sleep(wait_time)
                    current_delay *= backoff
            
            # 理论上不会到这里
            raise RetryError(
                f"Failed after {max_attempts} attempts",
                last_exception,
                max_attempts
            )
        
        return wrapper
    return decorator


class CircuitBreaker:
    """
    熔断器模式实现
    
    当错误率超过阈值时，自动熔断，避免雪崩效应。
    
    Example:
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        
        @breaker.call
        async def call_external_service():
            ...
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    def call(self, func: Callable) -> Callable:
        """装饰器形式"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self._call_async(func, *args, **kwargs)
        
        return wrapper
    
    async def _call_async(self, func: Callable, *args, **kwargs):
        """执行调用"""
        # 检查熔断器状态
        if self.state == "open":
            if time.time() - self.last_failure_time < self.timeout:
                raise Exception("Circuit breaker is OPEN")
            else:
                self.state = "half_open"
                logger.info("Circuit breaker entering HALF_OPEN state")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """成功时的处理"""
        self.failure_count = 0
        if self.state == "half_open":
            self.state = "closed"
            logger.info("Circuit breaker entering CLOSED state")
    
    def _on_failure(self):
        """失败时的处理"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker entering OPEN state after {self.failure_count} failures"
            )
    
    def reset(self):
        """重置熔断器"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        logger.info("Circuit breaker reset to CLOSED state")


# 常见的异常分类
class TemporaryError(Exception):
    """临时错误，应该重试"""
    pass


class PermanentError(Exception):
    """永久错误，不应该重试"""
    pass


class RateLimitError(TemporaryError):
    """速率限制错误"""
    pass


class TimeoutError(TemporaryError):
    """超时错误"""
    pass


class NetworkError(TemporaryError):
    """网络错误"""
    pass


# 便捷的重试配置
RETRY_CONFIG_AGGRESSIVE = {
    "max_attempts": 5,
    "delay": 0.5,
    "backoff": 2.0,
    "max_delay": 30.0
}

RETRY_CONFIG_MODERATE = {
    "max_attempts": 3,
    "delay": 1.0,
    "backoff": 2.0,
    "max_delay": 60.0
}

RETRY_CONFIG_CONSERVATIVE = {
    "max_attempts": 2,
    "delay": 2.0,
    "backoff": 3.0,
    "max_delay": 120.0
}
