"""
Performance Metrics Collection System

Provides comprehensive metrics collection for decompilation operations,
LLM provider performance, and system health monitoring.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from enum import Enum
import json

from .logging import get_logger, time_operation
from .config import get_settings


logger = get_logger(__name__)


class MetricType(str, Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    HISTOGRAM = "histogram" 
    GAUGE = "gauge"
    TIMING = "timing"


class OperationType(str, Enum):
    """Types of operations being measured."""
    DECOMPILATION = "decompilation"
    LLM_REQUEST = "llm_request"
    FILE_UPLOAD = "file_upload"
    CACHE_OPERATION = "cache_operation"
    API_REQUEST = "api_request"


@dataclass
class MetricData:
    """Individual metric data point."""
    name: str
    metric_type: MetricType
    value: Union[int, float]
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics for an operation."""
    operation_type: OperationType
    operation_name: str
    duration_ms: float
    success: bool
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Central metrics collection system with in-memory storage and
    structured logging integration.
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: List[MetricData] = []
        self.performance_metrics: List[PerformanceMetrics] = []
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}
        self._max_metrics_stored = 10000  # Prevent memory growth
        
    def increment_counter(
        self, 
        name: str, 
        value: int = 1, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment a counter metric."""
        full_name = self._build_metric_name(name, tags or {})
        self.counters[full_name] = self.counters.get(full_name, 0) + value
        
        metric = MetricData(
            name=name,
            metric_type=MetricType.COUNTER,
            value=self.counters[full_name],
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )
        self._store_metric(metric)
        
        logger.debug(
            "Counter incremented",
            metric_name=name,
            value=self.counters[full_name],
            increment=value,
            tags=tags or {}
        )
    
    def set_gauge(
        self, 
        name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric value."""
        full_name = self._build_metric_name(name, tags or {})
        self.gauges[full_name] = value
        
        metric = MetricData(
            name=name,
            metric_type=MetricType.GAUGE,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )
        self._store_metric(metric)
        
        logger.debug(
            "Gauge updated",
            metric_name=name,
            value=value,
            tags=tags or {}
        )
    
    def record_histogram(
        self, 
        name: str, 
        value: float, 
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a histogram metric value."""
        full_name = self._build_metric_name(name, tags or {})
        if full_name not in self.histograms:
            self.histograms[full_name] = []
        
        self.histograms[full_name].append(value)
        
        # Keep only recent values to prevent memory growth
        if len(self.histograms[full_name]) > 1000:
            self.histograms[full_name] = self.histograms[full_name][-1000:]
        
        metric = MetricData(
            name=name,
            metric_type=MetricType.HISTOGRAM,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )
        self._store_metric(metric)
        
        logger.debug(
            "Histogram recorded",
            metric_name=name,
            value=value,
            tags=tags or {}
        )
    
    def record_timing(
        self,
        operation_type: OperationType,
        operation_name: str,
        duration_ms: float,
        success: bool = True,
        **metadata
    ) -> None:
        """Record timing information for an operation."""
        perf_metric = PerformanceMetrics(
            operation_type=operation_type,
            operation_name=operation_name,
            duration_ms=duration_ms,
            success=success,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        
        self._store_performance_metric(perf_metric)
        
        # Also record as histogram for statistical analysis
        tags = {
            "operation_type": operation_type.value,
            "operation_name": operation_name,
            "success": str(success).lower()
        }
        self.record_histogram(f"{operation_type.value}_duration_ms", duration_ms, tags)
        
        # Increment counter for operation attempts
        self.increment_counter(f"{operation_type.value}_total", 1, tags)
        
        logger.info(
            "Operation completed",
            operation_type=operation_type.value,
            operation_name=operation_name,
            duration_ms=round(duration_ms, 2),
            success=success,
            **metadata
        )
    
    @asynccontextmanager
    async def time_async_operation(
        self,
        operation_type: OperationType,
        operation_name: str,
        **metadata
    ):
        """Context manager for timing async operations."""
        start_time = time.perf_counter()
        success = True
        error = None
        
        try:
            yield
        except Exception as exc:
            success = False
            error = str(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            final_metadata = dict(metadata)
            if error:
                final_metadata['error'] = error
            
            self.record_timing(
                operation_type=operation_type,
                operation_name=operation_name,
                duration_ms=duration_ms,
                success=success,
                **final_metadata
            )
    
    def get_performance_summary(
        self, 
        operation_type: Optional[OperationType] = None,
        time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get performance summary for operations."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        
        # Filter metrics by time window and operation type
        filtered_metrics = [
            m for m in self.performance_metrics
            if m.timestamp >= cutoff_time and (
                operation_type is None or m.operation_type == operation_type
            )
        ]
        
        if not filtered_metrics:
            return {"message": "No metrics available for the specified criteria"}
        
        # Calculate statistics
        durations = [m.duration_ms for m in filtered_metrics]
        success_count = sum(1 for m in filtered_metrics if m.success)
        total_count = len(filtered_metrics)
        
        summary = {
            "time_window_minutes": time_window_minutes,
            "operation_type": operation_type.value if operation_type else "all",
            "total_operations": total_count,
            "successful_operations": success_count,
            "success_rate": round(success_count / total_count * 100, 2) if total_count > 0 else 0,
            "duration_stats": {
                "min_ms": min(durations),
                "max_ms": max(durations),
                "avg_ms": round(sum(durations) / len(durations), 2),
                "p50_ms": self._calculate_percentile(durations, 50),
                "p90_ms": self._calculate_percentile(durations, 90),
                "p99_ms": self._calculate_percentile(durations, 99)
            }
        }
        
        # Add per-operation breakdown
        operations = {}
        for metric in filtered_metrics:
            op_name = metric.operation_name
            if op_name not in operations:
                operations[op_name] = {
                    "count": 0,
                    "success_count": 0,
                    "durations": []
                }
            
            operations[op_name]["count"] += 1
            if metric.success:
                operations[op_name]["success_count"] += 1
            operations[op_name]["durations"].append(metric.duration_ms)
        
        # Calculate per-operation stats
        for op_name, op_data in operations.items():
            durations = op_data["durations"]
            operations[op_name] = {
                "total_operations": op_data["count"],
                "successful_operations": op_data["success_count"], 
                "success_rate": round(op_data["success_count"] / op_data["count"] * 100, 2),
                "avg_duration_ms": round(sum(durations) / len(durations), 2)
            }
        
        summary["operations"] = operations
        return summary
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current snapshot of all metrics."""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histogram_counts": {k: len(v) for k, v in self.histograms.items()},
            "total_performance_metrics": len(self.performance_metrics),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _build_metric_name(self, name: str, tags: Dict[str, str]) -> str:
        """Build full metric name with tags."""
        if not tags:
            return name
        
        tag_string = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_string}]"
    
    def _store_metric(self, metric: MetricData) -> None:
        """Store metric data with size limits."""
        self.metrics.append(metric)
        
        # Prevent memory growth by keeping only recent metrics
        if len(self.metrics) > self._max_metrics_stored:
            self.metrics = self.metrics[-self._max_metrics_stored:]
    
    def _store_performance_metric(self, metric: PerformanceMetrics) -> None:
        """Store performance metric with size limits."""
        self.performance_metrics.append(metric)
        
        # Prevent memory growth by keeping only recent metrics
        if len(self.performance_metrics) > self._max_metrics_stored:
            self.performance_metrics = self.performance_metrics[-self._max_metrics_stored:]
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile for a list of values."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = (percentile / 100.0) * (len(sorted_values) - 1)
        
        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower_index = int(index)
            upper_index = min(lower_index + 1, len(sorted_values) - 1)
            weight = index - lower_index
            
            return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics_collector


def increment_counter(name: str, value: int = 1, **tags) -> None:
    """Increment a counter metric."""
    _metrics_collector.increment_counter(name, value, tags)


def set_gauge(name: str, value: float, **tags) -> None:
    """Set a gauge metric value."""
    _metrics_collector.set_gauge(name, value, tags)


def record_histogram(name: str, value: float, **tags) -> None:
    """Record a histogram metric value."""
    _metrics_collector.record_histogram(name, value, tags)


def record_timing(
    operation_type: OperationType,
    operation_name: str,
    duration_ms: float,
    success: bool = True,
    **metadata
) -> None:
    """Record timing information for an operation."""
    _metrics_collector.record_timing(
        operation_type, operation_name, duration_ms, success, **metadata
    )


@asynccontextmanager
async def time_async_operation(
    operation_type: OperationType,
    operation_name: str,
    **metadata
):
    """Context manager for timing async operations."""
    async with _metrics_collector.time_async_operation(
        operation_type, operation_name, **metadata
    ):
        yield


def get_performance_summary(
    operation_type: Optional[OperationType] = None,
    time_window_minutes: int = 60
) -> Dict[str, Any]:
    """Get performance summary for operations."""
    return _metrics_collector.get_performance_summary(operation_type, time_window_minutes)


def get_current_metrics() -> Dict[str, Any]:
    """Get current snapshot of all metrics."""
    return _metrics_collector.get_current_metrics()


# Convenience decorators for common operations

def track_decompilation_performance(func):
    """Decorator to track decompilation operation performance."""
    async def wrapper(*args, **kwargs):
        async with time_async_operation(
            OperationType.DECOMPILATION,
            func.__name__,
            function=func.__name__
        ):
            return await func(*args, **kwargs)
    return wrapper


def track_llm_performance(provider_name: str = "unknown"):
    """Decorator to track LLM provider performance."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with time_async_operation(
                OperationType.LLM_REQUEST,
                f"{provider_name}_{func.__name__}",
                provider=provider_name,
                function=func.__name__
            ):
                return await func(*args, **kwargs)
        return wrapper
    return decorator