"""
性能监控和可观测性模块

提供装饰器和工具函数用于监控系统性能、追踪执行时间和记录关键指标。
"""
import time
import logging
from functools import wraps
from typing import Callable, Any, Optional
from contextlib import asynccontextmanager
import asyncio

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {}
        self.enabled = True
    
    def record_metric(self, name: str, value: float, tags: Optional[dict] = None):
        """记录指标"""
        if not self.enabled:
            return
        
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append({
            "value": value,
            "timestamp": time.time(),
            "tags": tags or {}
        })
    
    def get_metrics(self, name: str) -> list:
        """获取指标"""
        return self.metrics.get(name, [])
    
    def get_average(self, name: str) -> float:
        """获取平均值"""
        metrics = self.get_metrics(name)
        if not metrics:
            return 0.0
        return sum(m["value"] for m in metrics) / len(metrics)
    
    def clear_metrics(self):
        """清空指标"""
        self.metrics.clear()


# 全局监控器实例
monitor = PerformanceMonitor()


def track_performance(
    metric_name: Optional[str] = None,
    log_level: int = logging.INFO,
    tags: Optional[dict] = None
):
    """
    性能追踪装饰器
    
    Args:
        metric_name: 指标名称，默认使用函数名
        log_level: 日志级别
        tags: 额外的标签信息
    
    Example:
        @track_performance(metric_name="content_creation", tags={"agent": "react"})
        async def create_content(task):
            ...
    """
    def decorator(func: Callable) -> Callable:
        name = metric_name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            result = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                duration = time.time() - start_time
                
                # 记录指标
                metric_tags = {
                    **(tags or {}),
                    "success": error is None,
                    "error_type": type(error).__name__ if error else None
                }
                monitor.record_metric(f"{name}.duration", duration, metric_tags)
                
                # 记录日志
                if error:
                    logger.error(
                        f"{name} failed after {duration:.2f}s: {error}",
                        extra={"duration": duration, "tags": metric_tags}
                    )
                else:
                    logger.log(
                        log_level,
                        f"{name} completed in {duration:.2f}s",
                        extra={"duration": duration, "tags": metric_tags}
                    )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = e
                raise
            finally:
                duration = time.time() - start_time
                
                # 记录指标
                metric_tags = {
                    **(tags or {}),
                    "success": error is None,
                    "error_type": type(error).__name__ if error else None
                }
                monitor.record_metric(f"{name}.duration", duration, metric_tags)
                
                # 记录日志
                if error:
                    logger.error(
                        f"{name} failed after {duration:.2f}s: {error}",
                        extra={"duration": duration, "tags": metric_tags}
                    )
                else:
                    logger.log(
                        log_level,
                        f"{name} completed in {duration:.2f}s",
                        extra={"duration": duration, "tags": metric_tags}
                    )
        
        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@asynccontextmanager
async def track_operation(operation_name: str, tags: Optional[dict] = None):
    """
    上下文管理器形式的性能追踪
    
    Example:
        async with track_operation("database_query", tags={"table": "users"}):
            result = await db.query(...)
    """
    start_time = time.time()
    error = None
    
    try:
        yield
    except Exception as e:
        error = e
        raise
    finally:
        duration = time.time() - start_time
        
        metric_tags = {
            **(tags or {}),
            "success": error is None,
            "error_type": type(error).__name__ if error else None
        }
        monitor.record_metric(f"{operation_name}.duration", duration, metric_tags)
        
        if error:
            logger.error(
                f"{operation_name} failed after {duration:.2f}s: {error}",
                extra={"duration": duration, "tags": metric_tags}
            )
        else:
            logger.info(
                f"{operation_name} completed in {duration:.2f}s",
                extra={"duration": duration, "tags": metric_tags}
            )


def count_calls(metric_name: Optional[str] = None):
    """
    调用计数装饰器
    
    Example:
        @count_calls("agent_executions")
        async def execute_agent(task):
            ...
    """
    def decorator(func: Callable) -> Callable:
        name = metric_name or f"{func.__module__}.{func.__name__}.calls"
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitor.record_metric(name, 1)
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            monitor.record_metric(name, 1)
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class MetricsCollector:
    """指标收集器 - 用于收集和导出 Prometheus 格式的指标"""
    
    def __init__(self):
        self.counters = {}
        self.histograms = {}
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[dict] = None):
        """增加计数器"""
        key = self._make_key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value
    
    def observe_histogram(self, name: str, value: float, labels: Optional[dict] = None):
        """记录直方图值"""
        key = self._make_key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
    
    def _make_key(self, name: str, labels: Optional[dict]) -> str:
        """生成指标键"""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def export_prometheus(self) -> str:
        """导出 Prometheus 格式的指标"""
        lines = []
        
        # 导出计数器
        for key, value in self.counters.items():
            lines.append(f"{key} {value}")
        
        # 导出直方图
        for key, values in self.histograms.items():
            if values:
                lines.append(f"{key}_sum {sum(values)}")
                lines.append(f"{key}_count {len(values)}")
                lines.append(f"{key}_avg {sum(values)/len(values)}")
        
        return "\n".join(lines)


# 全局指标收集器
metrics_collector = MetricsCollector()


# 便捷函数
def get_monitor() -> PerformanceMonitor:
    """获取全局监控器实例"""
    return monitor


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器实例"""
    return metrics_collector
