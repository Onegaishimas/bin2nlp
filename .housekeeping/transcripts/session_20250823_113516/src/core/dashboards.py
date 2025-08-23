"""
Operational Dashboards and Alerts System

Provides dashboard generation, alerting rules, and monitoring integration
for production deployment observability.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math

from .logging import get_logger
from .metrics import get_metrics_collector, get_performance_summary, OperationType
from .circuit_breaker import get_circuit_breaker_manager, CircuitState
from .config import get_settings


logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status states."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"


@dataclass
class Alert:
    """Individual alert definition."""
    id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "status": self.status.value,
            "triggered_at": self.triggered_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "context": self.context
        }


@dataclass
class DashboardMetric:
    """Dashboard metric with current value and trend."""
    name: str
    current_value: Union[int, float, str]
    unit: str
    status: str  # "healthy", "warning", "critical"
    trend: Optional[str] = None  # "up", "down", "stable"
    description: Optional[str] = None
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metric to dictionary."""
        return {
            "name": self.name,
            "current_value": self.current_value,
            "unit": self.unit,
            "status": self.status,
            "trend": self.trend,
            "description": self.description,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical
        }


@dataclass
class DashboardPanel:
    """Dashboard panel containing related metrics."""
    id: str
    title: str
    description: str
    metrics: List[DashboardMetric]
    chart_type: str = "gauge"  # "gauge", "line", "bar", "table"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert panel to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "chart_type": self.chart_type,
            "metrics": [metric.to_dict() for metric in self.metrics]
        }


@dataclass
class OperationalDashboard:
    """Complete operational dashboard."""
    id: str
    title: str
    description: str
    panels: List[DashboardPanel]
    refresh_interval: int = 30  # seconds
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert dashboard to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "refresh_interval": self.refresh_interval,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "panels": [panel.to_dict() for panel in self.panels]
        }


class AlertManager:
    """Manages alerts and alert rules."""
    
    def __init__(self):
        """Initialize alert manager."""
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.max_history_size = 1000
        
    def check_performance_alerts(self) -> List[Alert]:
        """Check for performance-related alerts."""
        alerts = []
        
        # Check decompilation performance
        decompilation_summary = get_performance_summary(OperationType.DECOMPILATION, 15)
        if decompilation_summary.get("total_operations", 0) > 0:
            avg_duration = decompilation_summary["duration_stats"]["avg_ms"]
            success_rate = decompilation_summary["success_rate"]
            
            # Alert if average decompilation time > 30 seconds
            if avg_duration > 30000:
                alerts.append(self._create_alert(
                    "decompilation_slow",
                    "Slow Decompilation Performance",
                    f"Average decompilation time is {avg_duration/1000:.1f}s (threshold: 30s)",
                    AlertSeverity.HIGH,
                    {"avg_duration_ms": avg_duration, "threshold_ms": 30000}
                ))
            
            # Alert if success rate < 90%
            if success_rate < 90:
                alerts.append(self._create_alert(
                    "decompilation_failures",
                    "High Decompilation Failure Rate",
                    f"Decompilation success rate is {success_rate:.1f}% (threshold: 90%)",
                    AlertSeverity.HIGH,
                    {"success_rate": success_rate, "threshold": 90}
                ))
        
        # Check LLM performance
        llm_summary = get_performance_summary(OperationType.LLM_REQUEST, 15)
        if llm_summary.get("total_operations", 0) > 0:
            avg_duration = llm_summary["duration_stats"]["avg_ms"]
            success_rate = llm_summary["success_rate"]
            
            # Alert if average LLM response time > 15 seconds
            if avg_duration > 15000:
                alerts.append(self._create_alert(
                    "llm_slow",
                    "Slow LLM Response Performance",
                    f"Average LLM response time is {avg_duration/1000:.1f}s (threshold: 15s)",
                    AlertSeverity.MEDIUM,
                    {"avg_duration_ms": avg_duration, "threshold_ms": 15000}
                ))
            
            # Alert if success rate < 95%
            if success_rate < 95:
                alerts.append(self._create_alert(
                    "llm_failures",
                    "High LLM Failure Rate",
                    f"LLM success rate is {success_rate:.1f}% (threshold: 95%)",
                    AlertSeverity.MEDIUM,
                    {"success_rate": success_rate, "threshold": 95}
                ))
        
        return alerts
    
    def check_circuit_breaker_alerts(self) -> List[Alert]:
        """Check for circuit breaker alerts."""
        alerts = []
        
        manager = get_circuit_breaker_manager()
        circuit_stats = manager.get_circuit_stats()
        
        for circuit_name, circuit_info in circuit_stats.items():
            state = circuit_info["state"]
            stats = circuit_info["stats"]
            
            # Alert if circuit breaker is open
            if state == CircuitState.OPEN.value:
                alerts.append(self._create_alert(
                    f"circuit_open_{circuit_name}",
                    f"Circuit Breaker Open: {circuit_name}",
                    f"Circuit breaker '{circuit_name}' is open due to failures. Service may be degraded.",
                    AlertSeverity.CRITICAL,
                    {
                        "circuit_name": circuit_name,
                        "failure_count": stats.failed_requests,
                        "success_rate": stats.get_success_rate()
                    }
                ))
            
            # Alert if success rate < 80% with sufficient requests
            elif stats.total_requests >= 10 and stats.get_success_rate() < 80:
                alerts.append(self._create_alert(
                    f"circuit_degraded_{circuit_name}",
                    f"Circuit Performance Degraded: {circuit_name}",
                    f"Circuit '{circuit_name}' has {stats.get_success_rate():.1f}% success rate",
                    AlertSeverity.MEDIUM,
                    {
                        "circuit_name": circuit_name,
                        "success_rate": stats.get_success_rate(),
                        "total_requests": stats.total_requests
                    }
                ))
        
        return alerts
    
    def check_system_resource_alerts(self) -> List[Alert]:
        """Check for system resource alerts."""
        alerts = []
        
        collector = get_metrics_collector()
        current_metrics = collector.get_current_metrics()
        
        # Check counter growth rates (simplified)
        counters = current_metrics.get("counters", {})
        
        # Alert if error counters are growing
        for counter_name, count in counters.items():
            if "failure" in counter_name.lower() or "error" in counter_name.lower():
                if count > 50:  # More than 50 failures
                    alerts.append(self._create_alert(
                        f"high_error_count_{counter_name}",
                        f"High Error Count: {counter_name}",
                        f"Error counter '{counter_name}' has reached {count} failures",
                        AlertSeverity.HIGH,
                        {"counter_name": counter_name, "count": count, "threshold": 50}
                    ))
        
        return alerts
    
    def _create_alert(
        self, 
        alert_id: str, 
        name: str, 
        description: str, 
        severity: AlertSeverity,
        context: Dict[str, Any]
    ) -> Alert:
        """Create or update an alert."""
        # Check if alert already exists
        if alert_id in self.active_alerts:
            existing_alert = self.active_alerts[alert_id]
            # Update context but keep same trigger time
            existing_alert.context.update(context)
            existing_alert.description = description  # Update description in case values changed
            return existing_alert
        else:
            # Create new alert
            alert = Alert(
                id=alert_id,
                name=name,
                description=description,
                severity=severity,
                status=AlertStatus.ACTIVE,
                triggered_at=datetime.utcnow(),
                context=context
            )
            self.active_alerts[alert_id] = alert
            
            logger.warning(
                "New alert triggered",
                alert_id=alert_id,
                alert_name=name,
                severity=severity.value,
                description=description
            )
            
            return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            
            # Move to history
            self.alert_history.append(alert)
            del self.active_alerts[alert_id]
            
            # Limit history size
            if len(self.alert_history) > self.max_history_size:
                self.alert_history = self.alert_history[-self.max_history_size//2:]
            
            logger.info(
                "Alert resolved",
                alert_id=alert_id,
                alert_name=alert.name,
                duration_minutes=(alert.resolved_at - alert.triggered_at).total_seconds() / 60
            )
            
            return True
        return False
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an active alert."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            
            logger.info(
                "Alert acknowledged",
                alert_id=alert_id,
                acknowledged_by=acknowledged_by
            )
            
            return True
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of alert status."""
        active_alerts = list(self.active_alerts.values())
        
        severity_counts = {severity.value: 0 for severity in AlertSeverity}
        for alert in active_alerts:
            severity_counts[alert.severity.value] += 1
        
        return {
            "total_active": len(active_alerts),
            "severity_breakdown": severity_counts,
            "oldest_alert": min(active_alerts, key=lambda a: a.triggered_at).triggered_at.isoformat() if active_alerts else None,
            "newest_alert": max(active_alerts, key=lambda a: a.triggered_at).triggered_at.isoformat() if active_alerts else None,
            "total_history": len(self.alert_history)
        }


class DashboardGenerator:
    """Generates operational dashboards from system metrics."""
    
    def __init__(self, alert_manager: AlertManager):
        """Initialize dashboard generator."""
        self.alert_manager = alert_manager
    
    def generate_overview_dashboard(self) -> OperationalDashboard:
        """Generate main system overview dashboard."""
        panels = []
        
        # System Health Panel
        panels.append(self._create_system_health_panel())
        
        # Performance Panel
        panels.append(self._create_performance_panel())
        
        # Circuit Breaker Panel
        panels.append(self._create_circuit_breaker_panel())
        
        # Alerts Panel
        panels.append(self._create_alerts_panel())
        
        return OperationalDashboard(
            id="system_overview",
            title="bin2nlp System Overview",
            description="Main operational dashboard showing system health, performance, and alerts",
            panels=panels,
            refresh_interval=30
        )
    
    def generate_performance_dashboard(self) -> OperationalDashboard:
        """Generate detailed performance dashboard."""
        panels = []
        
        # Decompilation Performance
        panels.append(self._create_decompilation_performance_panel())
        
        # LLM Performance
        panels.append(self._create_llm_performance_panel())
        
        # Request Throughput
        panels.append(self._create_throughput_panel())
        
        return OperationalDashboard(
            id="performance_detailed",
            title="bin2nlp Performance Metrics",
            description="Detailed performance metrics for decompilation and LLM operations",
            panels=panels,
            refresh_interval=15
        )
    
    def _create_system_health_panel(self) -> DashboardPanel:
        """Create system health panel."""
        metrics = []
        
        collector = get_metrics_collector()
        current_metrics = collector.get_current_metrics()
        
        # Total operations
        total_operations = sum(
            count for name, count in current_metrics.get("counters", {}).items()
            if "total" in name.lower()
        )
        
        metrics.append(DashboardMetric(
            name="Total Operations",
            current_value=total_operations,
            unit="count",
            status="healthy",
            description="Total number of operations processed"
        ))
        
        # Active alerts
        active_alerts = len(self.alert_manager.get_active_alerts())
        alert_status = "healthy" if active_alerts == 0 else ("warning" if active_alerts < 5 else "critical")
        
        metrics.append(DashboardMetric(
            name="Active Alerts",
            current_value=active_alerts,
            unit="count",
            status=alert_status,
            threshold_warning=1,
            threshold_critical=5,
            description="Number of active system alerts"
        ))
        
        # Circuit breaker health
        manager = get_circuit_breaker_manager()
        circuit_stats = manager.get_circuit_stats()
        
        healthy_circuits = sum(1 for info in circuit_stats.values() if info["is_available"])
        total_circuits = len(circuit_stats)
        
        circuit_health_pct = (healthy_circuits / total_circuits * 100) if total_circuits > 0 else 100
        circuit_status = "healthy" if circuit_health_pct >= 90 else ("warning" if circuit_health_pct >= 70 else "critical")
        
        metrics.append(DashboardMetric(
            name="Circuit Breaker Health",
            current_value=f"{circuit_health_pct:.0f}%",
            unit="percent",
            status=circuit_status,
            threshold_warning=90,
            threshold_critical=70,
            description=f"{healthy_circuits}/{total_circuits} circuits available"
        ))
        
        return DashboardPanel(
            id="system_health",
            title="System Health",
            description="Overall system health indicators",
            metrics=metrics,
            chart_type="gauge"
        )
    
    def _create_performance_panel(self) -> DashboardPanel:
        """Create performance overview panel."""
        metrics = []
        
        # Decompilation performance
        decomp_summary = get_performance_summary(OperationType.DECOMPILATION, 60)
        if decomp_summary.get("total_operations", 0) > 0:
            avg_duration = decomp_summary["duration_stats"]["avg_ms"] / 1000
            success_rate = decomp_summary["success_rate"]
            
            duration_status = "healthy" if avg_duration <= 10 else ("warning" if avg_duration <= 30 else "critical")
            success_status = "healthy" if success_rate >= 95 else ("warning" if success_rate >= 90 else "critical")
            
            metrics.append(DashboardMetric(
                name="Avg Decompilation Time",
                current_value=f"{avg_duration:.1f}s",
                unit="seconds",
                status=duration_status,
                threshold_warning=10,
                threshold_critical=30,
                description="Average decompilation processing time"
            ))
            
            metrics.append(DashboardMetric(
                name="Decompilation Success Rate",
                current_value=f"{success_rate:.1f}%",
                unit="percent",
                status=success_status,
                threshold_warning=90,
                threshold_critical=95,
                description="Percentage of successful decompilation operations"
            ))
        
        # LLM performance
        llm_summary = get_performance_summary(OperationType.LLM_REQUEST, 60)
        if llm_summary.get("total_operations", 0) > 0:
            avg_duration = llm_summary["duration_stats"]["avg_ms"] / 1000
            success_rate = llm_summary["success_rate"]
            
            duration_status = "healthy" if avg_duration <= 5 else ("warning" if avg_duration <= 15 else "critical")
            success_status = "healthy" if success_rate >= 98 else ("warning" if success_rate >= 95 else "critical")
            
            metrics.append(DashboardMetric(
                name="Avg LLM Response Time",
                current_value=f"{avg_duration:.1f}s",
                unit="seconds",
                status=duration_status,
                threshold_warning=5,
                threshold_critical=15,
                description="Average LLM response time"
            ))
            
            metrics.append(DashboardMetric(
                name="LLM Success Rate",
                current_value=f"{success_rate:.1f}%",
                unit="percent",
                status=success_status,
                threshold_warning=95,
                threshold_critical=98,
                description="Percentage of successful LLM requests"
            ))
        
        return DashboardPanel(
            id="performance_overview",
            title="Performance Overview",
            description="Key performance metrics",
            metrics=metrics,
            chart_type="gauge"
        )
    
    def _create_circuit_breaker_panel(self) -> DashboardPanel:
        """Create circuit breaker status panel."""
        metrics = []
        
        manager = get_circuit_breaker_manager()
        circuit_stats = manager.get_circuit_stats()
        
        for circuit_name, info in circuit_stats.items():
            state = info["state"]
            stats = info["stats"]
            
            status_map = {
                "closed": "healthy",
                "half_open": "warning", 
                "open": "critical"
            }
            
            status = status_map.get(state, "unknown")
            success_rate = stats.get_success_rate()
            
            metrics.append(DashboardMetric(
                name=f"{circuit_name} Status",
                current_value=f"{state} ({success_rate:.1f}%)",
                unit="state",
                status=status,
                description=f"Circuit breaker state and success rate"
            ))
        
        return DashboardPanel(
            id="circuit_breakers",
            title="Circuit Breaker Status",
            description="Status of all circuit breakers",
            metrics=metrics,
            chart_type="table"
        )
    
    def _create_alerts_panel(self) -> DashboardPanel:
        """Create alerts panel."""
        metrics = []
        
        alert_summary = self.alert_manager.get_alert_summary()
        
        # Total active alerts
        total_active = alert_summary["total_active"]
        alert_status = "healthy" if total_active == 0 else ("warning" if total_active < 5 else "critical")
        
        metrics.append(DashboardMetric(
            name="Active Alerts",
            current_value=total_active,
            unit="count",
            status=alert_status,
            description="Total number of active alerts"
        ))
        
        # Critical alerts
        critical_count = alert_summary["severity_breakdown"]["critical"]
        critical_status = "healthy" if critical_count == 0 else "critical"
        
        metrics.append(DashboardMetric(
            name="Critical Alerts",
            current_value=critical_count,
            unit="count",
            status=critical_status,
            description="Number of critical severity alerts"
        ))
        
        return DashboardPanel(
            id="alerts_summary",
            title="Alert Summary",
            description="Current alert status",
            metrics=metrics,
            chart_type="gauge"
        )
    
    def _create_decompilation_performance_panel(self) -> DashboardPanel:
        """Create detailed decompilation performance panel."""
        metrics = []
        
        summary = get_performance_summary(OperationType.DECOMPILATION, 60)
        if summary.get("total_operations", 0) > 0:
            stats = summary["duration_stats"]
            
            metrics.extend([
                DashboardMetric(
                    name="Min Duration",
                    current_value=f"{stats['min_ms']/1000:.1f}s",
                    unit="seconds",
                    status="healthy"
                ),
                DashboardMetric(
                    name="Max Duration", 
                    current_value=f"{stats['max_ms']/1000:.1f}s",
                    unit="seconds",
                    status="healthy"
                ),
                DashboardMetric(
                    name="P90 Duration",
                    current_value=f"{stats['p90_ms']/1000:.1f}s",
                    unit="seconds",
                    status="healthy"
                ),
                DashboardMetric(
                    name="P99 Duration",
                    current_value=f"{stats['p99_ms']/1000:.1f}s",
                    unit="seconds",
                    status="healthy"
                )
            ])
        
        return DashboardPanel(
            id="decompilation_detailed",
            title="Decompilation Performance Details",
            description="Detailed decompilation timing statistics",
            metrics=metrics,
            chart_type="bar"
        )
    
    def _create_llm_performance_panel(self) -> DashboardPanel:
        """Create detailed LLM performance panel."""
        metrics = []
        
        summary = get_performance_summary(OperationType.LLM_REQUEST, 60)
        if summary.get("total_operations", 0) > 0:
            stats = summary["duration_stats"]
            
            metrics.extend([
                DashboardMetric(
                    name="Min Response Time",
                    current_value=f"{stats['min_ms']/1000:.1f}s",
                    unit="seconds",
                    status="healthy"
                ),
                DashboardMetric(
                    name="Max Response Time",
                    current_value=f"{stats['max_ms']/1000:.1f}s", 
                    unit="seconds",
                    status="healthy"
                ),
                DashboardMetric(
                    name="P90 Response Time",
                    current_value=f"{stats['p90_ms']/1000:.1f}s",
                    unit="seconds",
                    status="healthy"
                ),
                DashboardMetric(
                    name="P99 Response Time",
                    current_value=f"{stats['p99_ms']/1000:.1f}s",
                    unit="seconds", 
                    status="healthy"
                )
            ])
        
        return DashboardPanel(
            id="llm_detailed",
            title="LLM Performance Details",
            description="Detailed LLM response timing statistics",
            metrics=metrics,
            chart_type="bar"
        )
    
    def _create_throughput_panel(self) -> DashboardPanel:
        """Create throughput metrics panel."""
        metrics = []
        
        collector = get_metrics_collector()
        current_metrics = collector.get_current_metrics()
        
        # Calculate approximate throughput based on counters
        # This is simplified - in production you'd want time-based calculations
        counters = current_metrics.get("counters", {})
        
        decomp_total = sum(count for name, count in counters.items() 
                          if "decompilation" in name.lower() and "total" in name.lower())
        llm_total = sum(count for name, count in counters.items()
                       if "llm" in name.lower() and ("total" in name.lower() or "success" in name.lower()))
        
        metrics.extend([
            DashboardMetric(
                name="Total Decompilations",
                current_value=decomp_total,
                unit="count",
                status="healthy",
                description="Total decompilation operations"
            ),
            DashboardMetric(
                name="Total LLM Requests",
                current_value=llm_total,
                unit="count", 
                status="healthy",
                description="Total LLM requests processed"
            )
        ])
        
        return DashboardPanel(
            id="throughput",
            title="System Throughput",
            description="Operation counts and throughput metrics",
            metrics=metrics,
            chart_type="line"
        )


# Global instances
_alert_manager = AlertManager()
_dashboard_generator = DashboardGenerator(_alert_manager)


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    return _alert_manager


def get_dashboard_generator() -> DashboardGenerator:
    """Get the global dashboard generator instance."""
    return _dashboard_generator


async def run_alert_checks() -> List[Alert]:
    """Run all alert checks and return triggered alerts."""
    alert_manager = get_alert_manager()
    
    all_alerts = []
    
    # Check different alert categories
    all_alerts.extend(alert_manager.check_performance_alerts())
    all_alerts.extend(alert_manager.check_circuit_breaker_alerts())
    all_alerts.extend(alert_manager.check_system_resource_alerts())
    
    return all_alerts


def generate_prometheus_metrics() -> str:
    """
    Generate Prometheus-format metrics for external monitoring.
    
    Returns:
        Prometheus metrics in text format
    """
    collector = get_metrics_collector()
    current_metrics = collector.get_current_metrics()
    
    lines = []
    lines.append("# HELP bin2nlp_info Information about bin2nlp service")
    lines.append("# TYPE bin2nlp_info gauge")
    lines.append('bin2nlp_info{version="1.0.0",service="bin2nlp"} 1')
    lines.append("")
    
    # Export counters
    lines.append("# HELP bin2nlp_operations_total Total number of operations")
    lines.append("# TYPE bin2nlp_operations_total counter")
    
    for name, value in current_metrics.get("counters", {}).items():
        # Clean metric name for Prometheus
        clean_name = name.lower().replace(" ", "_").replace("-", "_")
        # Extract labels from metric name if present (simplified)
        if "[" in clean_name and "]" in clean_name:
            base_name = clean_name.split("[")[0]
            label_part = clean_name.split("[")[1].split("]")[0]
            labels = ",".join(label_part.split(","))
            lines.append(f'bin2nlp_{base_name}{{{labels}}} {value}')
        else:
            lines.append(f'bin2nlp_{clean_name} {value}')
    
    lines.append("")
    
    # Export gauges
    lines.append("# HELP bin2nlp_current_value Current gauge values")
    lines.append("# TYPE bin2nlp_current_value gauge")
    
    for name, value in current_metrics.get("gauges", {}).items():
        clean_name = name.lower().replace(" ", "_").replace("-", "_")
        if "[" in clean_name and "]" in clean_name:
            base_name = clean_name.split("[")[0]
            label_part = clean_name.split("[")[1].split("]")[0]
            labels = ",".join(label_part.split(","))
            lines.append(f'bin2nlp_{base_name}{{{labels}}} {value}')
        else:
            lines.append(f'bin2nlp_{clean_name} {value}')
    
    return "\n".join(lines)