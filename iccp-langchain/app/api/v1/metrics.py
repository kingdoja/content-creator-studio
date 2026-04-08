"""
监控和指标 API 端点
"""
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from app.observability.monitor import get_monitor, get_metrics_collector
from app.utils.cache import get_global_cache, get_content_cache
from app.auth.dependencies import get_optional_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/performance")
async def get_performance_metrics(user=Depends(get_optional_current_user)):
    """
    获取性能指标
    
    返回系统性能监控数据，包括各个操作的执行时间统计。
    """
    monitor = get_monitor()
    
    # 获取所有指标
    all_metrics = {}
    for name, metrics in monitor.metrics.items():
        if metrics:
            values = [m["value"] for m in metrics]
            all_metrics[name] = {
                "count": len(values),
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "recent": values[-10:]  # 最近10次
            }
    
    return {
        "metrics": all_metrics,
        "enabled": monitor.enabled
    }


@router.get("/cache")
async def get_cache_stats(user=Depends(get_optional_current_user)):
    """
    获取缓存统计
    
    返回缓存使用情况，包括命中率、大小等。
    """
    global_cache = get_global_cache()
    content_cache = get_content_cache()
    
    return {
        "global_cache": await global_cache.get_stats(),
        "content_cache": await content_cache.get_stats()
    }


@router.post("/cache/clear")
async def clear_cache(user=Depends(get_optional_current_user)):
    """
    清空缓存
    
    清空所有缓存数据。需要管理员权限。
    """
    global_cache = get_global_cache()
    content_cache = get_content_cache()
    
    await global_cache.clear()
    await content_cache.clear()
    
    return {"message": "Cache cleared successfully"}


@router.get("/prometheus", response_class=PlainTextResponse)
async def get_prometheus_metrics():
    """
    获取 Prometheus 格式的指标
    
    返回可被 Prometheus 抓取的指标数据。
    """
    collector = get_metrics_collector()
    return collector.export_prometheus()


@router.get("/health")
async def health_check():
    """
    健康检查
    
    返回系统健康状态。
    """
    return {
        "status": "healthy",
        "version": "2.0.0",
        "architecture": "strategy-routed-parallel-multi-agent"
    }


@router.get("/stats")
async def get_system_stats(user=Depends(get_optional_current_user)):
    """
    获取系统统计信息
    
    返回系统整体运行状态和统计数据。
    """
    monitor = get_monitor()
    global_cache = get_global_cache()
    content_cache = get_content_cache()
    
    # 计算总体统计
    total_operations = sum(
        len(metrics) for metrics in monitor.metrics.values()
    )
    
    return {
        "total_operations": total_operations,
        "cache_stats": {
            "global": await global_cache.get_stats(),
            "content": await content_cache.get_stats()
        },
        "architecture": {
            "type": "strategy-routed-parallel-multi-agent",
            "agents": ["SimpleAgent", "ReActAgent", "ReflectionAgent"],
            "routing": "strategy-based"
        }
    }
