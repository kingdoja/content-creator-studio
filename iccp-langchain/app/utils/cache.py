"""
缓存工具模块

提供多种缓存策略，包括内存缓存、LRU缓存和基于哈希的内容缓存。
"""
import hashlib
import json
import time
import logging
from functools import wraps
from typing import Callable, Any, Optional, Dict
from collections import OrderedDict
import asyncio

logger = logging.getLogger(__name__)


class CacheEntry:
    """缓存条目"""
    def __init__(self, value: Any, ttl: Optional[float] = None):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.hits = 0
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def touch(self):
        """更新访问计数"""
        self.hits += 1


class MemoryCache:
    """
    内存缓存实现
    
    支持 TTL（过期时间）和最大容量限制。
    
    Example:
        cache = MemoryCache(max_size=1000, default_ttl=3600)
        cache.set("key", "value", ttl=600)
        value = cache.get("key")
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[float] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                return None
            
            if entry.is_expired():
                del self._cache[key]
                logger.debug(f"Cache expired: {key}")
                return None
            
            entry.touch()
            logger.debug(f"Cache hit: {key} (hits: {entry.hits})")
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值"""
        async with self._lock:
            # 检查容量
            if len(self._cache) >= self.max_size and key not in self._cache:
                # 移除最旧的条目
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Cache evicted: {oldest_key}")
            
            ttl = ttl if ttl is not None else self.default_ttl
            self._cache[key] = CacheEntry(value, ttl)
            logger.debug(f"Cache set: {key} (ttl: {ttl})")
    
    async def delete(self, key: str):
        """删除缓存值"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache deleted: {key}")
    
    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    async def get_stats(self) -> dict:
        """获取缓存统计信息"""
        async with self._lock:
            total_hits = sum(entry.hits for entry in self._cache.values())
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "total_hits": total_hits,
                "keys": list(self._cache.keys())
            }


class LRUCache:
    """
    LRU（最近最少使用）缓存实现
    
    Example:
        cache = LRUCache(max_size=100)
        cache.set("key", "value")
        value = cache.get("key")
    """
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            if key not in self._cache:
                return None
            
            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            logger.debug(f"LRU cache hit: {key}")
            return self._cache[key]
    
    async def set(self, key: str, value: Any):
        """设置缓存值"""
        async with self._lock:
            if key in self._cache:
                # 更新并移到末尾
                self._cache.move_to_end(key)
            else:
                # 检查容量
                if len(self._cache) >= self.max_size:
                    # 移除最旧的（第一个）
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    logger.debug(f"LRU cache evicted: {oldest_key}")
            
            self._cache[key] = value
            logger.debug(f"LRU cache set: {key}")
    
    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            logger.info("LRU cache cleared")


def generate_cache_key(*args, **kwargs) -> str:
    """
    生成缓存键
    
    基于函数参数生成唯一的缓存键。
    
    Args:
        *args: 位置参数
        **kwargs: 关键字参数
    
    Returns:
        str: MD5 哈希值
    """
    # 将参数转换为可序列化的格式
    key_data = {
        "args": [str(arg) for arg in args],
        "kwargs": {k: str(v) for k, v in sorted(kwargs.items())}
    }
    
    # 生成 JSON 字符串
    key_str = json.dumps(key_data, sort_keys=True)
    
    # 计算 MD5 哈希
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(
    cache: MemoryCache,
    ttl: Optional[float] = None,
    key_prefix: str = "",
    key_func: Optional[Callable] = None
):
    """
    缓存装饰器
    
    Args:
        cache: 缓存实例
        ttl: 过期时间（秒）
        key_prefix: 缓存键前缀
        key_func: 自定义键生成函数
    
    Example:
        cache = MemoryCache()
        
        @cached(cache, ttl=3600, key_prefix="content:")
        async def create_content(task):
            # 耗时操作
            return result
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = generate_cache_key(*args, **kwargs)
            
            cache_key = f"{key_prefix}{cache_key}"
            
            # 尝试从缓存获取
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.info(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_value
            
            # 执行函数
            logger.info(f"Cache miss for {func.__name__}: {cache_key}")
            result = await func(*args, **kwargs)
            
            # 存入缓存
            await cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


class ContentCache:
    """
    内容缓存
    
    专门用于缓存生成的内容，基于内容特征生成缓存键。
    
    Example:
        cache = ContentCache()
        
        # 生成缓存键
        key = cache.generate_key(
            category="tech",
            topic="AI发展",
            style="professional"
        )
        
        # 存储
        await cache.set(key, content, ttl=3600)
        
        # 获取
        content = await cache.get(key)
    """
    
    def __init__(self, max_size: int = 500, default_ttl: float = 3600):
        self._cache = MemoryCache(max_size=max_size, default_ttl=default_ttl)
    
    def generate_key(self, **kwargs) -> str:
        """
        生成内容缓存键
        
        Args:
            **kwargs: 内容特征（category, topic, style, length等）
        
        Returns:
            str: 缓存键
        """
        # 排序并序列化
        key_str = json.dumps(kwargs, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[str]:
        """获取缓存的内容"""
        return await self._cache.get(key)
    
    async def set(self, key: str, content: str, ttl: Optional[float] = None):
        """缓存内容"""
        await self._cache.set(key, content, ttl=ttl)
    
    async def delete(self, key: str):
        """删除缓存"""
        await self._cache.delete(key)
    
    async def clear(self):
        """清空缓存"""
        await self._cache.clear()
    
    async def get_stats(self) -> dict:
        """获取统计信息"""
        return await self._cache.get_stats()


# 全局缓存实例
_global_cache = MemoryCache(max_size=1000, default_ttl=3600)
_content_cache = ContentCache(max_size=500, default_ttl=3600)


def get_global_cache() -> MemoryCache:
    """获取全局缓存实例"""
    return _global_cache


def get_content_cache() -> ContentCache:
    """获取内容缓存实例"""
    return _content_cache
