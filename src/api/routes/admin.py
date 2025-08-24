"""
Admin and Management API Endpoints

Administrative functions for system monitoring,
metrics, and configuration management.

Note: All endpoints are now open access - no authentication required.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status

from ...core.logging import get_logger
from ...core.config import get_settings
from ...core.metrics import get_metrics_collector, get_performance_summary, OperationType
from ...core.circuit_breaker import get_circuit_breaker_manager
from ...core.dashboards import (
    get_alert_manager, get_dashboard_generator, run_alert_checks, generate_prometheus_metrics
)
from ...database.connection import get_database
# Rate limiting middleware removed - no longer needed

logger = get_logger(__name__)

# Create router
router = APIRouter()


# System Monitoring Endpoints

@router.get("/metrics/current")
async def get_current_metrics(
    request: Request,
):
    """Get current system metrics and performance data."""
    try:
        collector = get_metrics_collector()
        metrics = collector.get_current_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics,
            "system_info": {
                "uptime_seconds": metrics.get("uptime_seconds", 0),
                "total_requests": metrics.get("total_requests", 0),
                "active_connections": metrics.get("active_connections", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve current metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve current metrics"
        )


@router.get("/metrics/performance")
async def get_performance_metrics(
    request: Request,
    operation_type: Optional[str] = None,
    time_window_minutes: int = 60,
):
    """Get detailed performance metrics for operations."""
    try:
        if operation_type:
            try:
                op_type = OperationType(operation_type)
                summary = get_performance_summary(op_type, time_window_minutes)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid operation type: {operation_type}"
                )
        else:
            summary = get_performance_summary(None, time_window_minutes)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "performance_summary": summary,
            "operation_type": operation_type,
            "time_window_minutes": time_window_minutes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve performance metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance metrics"
        )


@router.get("/metrics/decompilation")
async def get_decompilation_metrics(
    request: Request,
    time_window_minutes: int = 60,
):
    """Get detailed decompilation performance metrics."""
    try:
        summary = get_performance_summary(OperationType.DECOMPILATION, time_window_minutes)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "decompilation_performance": summary,
            "time_window_minutes": time_window_minutes
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve decompilation metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve decompilation metrics"
        )


@router.get("/metrics/llm")
async def get_llm_metrics(
    request: Request,
    time_window_minutes: int = 60,
):
    """Get detailed LLM provider performance metrics."""
    try:
        summary = get_performance_summary(OperationType.LLM_REQUEST, time_window_minutes)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "llm_performance": summary,
            "time_window_minutes": time_window_minutes
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve LLM metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve LLM metrics"
        )


# Circuit Breaker Management Endpoints

@router.get("/circuit-breakers")
async def get_all_circuit_breakers(
    request: Request,
):
    """Get status of all circuit breakers."""
    try:
        manager = get_circuit_breaker_manager()
        circuit_stats = manager.get_circuit_stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "circuit_breakers": circuit_stats,
            "total_circuits": len(circuit_stats)
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve circuit breaker status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve circuit breaker status"
        )


@router.get("/circuit-breakers/{circuit_name}")
async def get_circuit_breaker_status(
    circuit_name: str,
    request: Request,
):
    """Get detailed status for a specific circuit breaker."""
    try:
        manager = get_circuit_breaker_manager()
        circuit_status = manager.get_circuit_status(circuit_name)
        
        if circuit_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit breaker '{circuit_name}' not found"
            )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "circuit_name": circuit_name,
            "status": circuit_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve circuit breaker status for {circuit_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve circuit breaker status for {circuit_name}"
        )


@router.post("/circuit-breakers/{circuit_name}/reset")
async def reset_circuit_breaker(
    circuit_name: str,
    request: Request,
):
    """Reset a specific circuit breaker to closed state."""
    try:
        manager = get_circuit_breaker_manager()
        success = manager.reset_circuit_breaker(circuit_name)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit breaker '{circuit_name}' not found"
            )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "circuit_name": circuit_name,
            "action": "reset",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker {circuit_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset circuit breaker {circuit_name}"
        )


@router.post("/circuit-breakers/{circuit_name}/force-open")
async def force_open_circuit_breaker(
    circuit_name: str,
    request: Request,
):
    """Force a circuit breaker to open state (for testing)."""
    try:
        manager = get_circuit_breaker_manager()
        success = manager.force_open_circuit_breaker(circuit_name)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit breaker '{circuit_name}' not found"
            )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "circuit_name": circuit_name,
            "action": "force_open",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to force open circuit breaker {circuit_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to force open circuit breaker {circuit_name}"
        )


@router.get("/circuit-breakers/health-check/all")
async def health_check_all_circuits(
    request: Request,
):
    """Run health checks on all circuit breakers."""
    try:
        manager = get_circuit_breaker_manager()
        health_results = manager.health_check_all()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health_check_results": health_results,
            "total_healthy": sum(1 for result in health_results.values() if result.get("healthy", False)),
            "total_circuits": len(health_results)
        }
        
    except Exception as e:
        logger.error(f"Failed to run health checks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run health checks on circuit breakers"
        )


# Dashboard Endpoints

@router.get("/dashboards/overview")
async def get_overview_dashboard(
    request: Request,
):
    """Get comprehensive system overview dashboard."""
    try:
        generator = get_dashboard_generator()
        dashboard_data = generator.generate_overview_dashboard()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "dashboard": dashboard_data
        }
        
    except Exception as e:
        logger.error(f"Failed to generate overview dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate overview dashboard"
        )


@router.get("/dashboards/performance")
async def get_performance_dashboard(
    request: Request,
):
    """Get performance-focused dashboard."""
    try:
        generator = get_dashboard_generator()
        dashboard_data = generator.generate_performance_dashboard()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "dashboard": dashboard_data
        }
        
    except Exception as e:
        logger.error(f"Failed to generate performance dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate performance dashboard"
        )


# Alert Management Endpoints

@router.get("/alerts")
async def get_all_alerts(
    request: Request,
    include_history: bool = False,
):
    """Get all active alerts and optionally historical data."""
    try:
        manager = get_alert_manager()
        alerts = manager.get_all_alerts(include_history=include_history)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "alerts": alerts,
            "include_history": include_history,
            "total_active": len([a for a in alerts if a.get("status") == "active"]),
            "total_alerts": len(alerts)
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts"
        )


@router.post("/alerts/check")
async def run_alert_checks_endpoint(
    request: Request,
):
    """Manually trigger alert checking process."""
    try:
        results = await run_alert_checks()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "alert_check_results": results,
            "alerts_generated": len(results.get("new_alerts", [])),
            "alerts_resolved": len(results.get("resolved_alerts", []))
        }
        
    except Exception as e:
        logger.error(f"Failed to run alert checks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run alert checks"
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    request: Request,
):
    """Acknowledge a specific alert."""
    try:
        manager = get_alert_manager()
        success = manager.acknowledge_alert(alert_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert '{alert_id}' not found"
            )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "alert_id": alert_id,
            "action": "acknowledged",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge alert {alert_id}"
        )


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    request: Request,
):
    """Resolve a specific alert."""
    try:
        manager = get_alert_manager()
        success = manager.resolve_alert(alert_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert '{alert_id}' not found"
            )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "alert_id": alert_id,
            "action": "resolved",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve alert {alert_id}"
        )


# Monitoring and Health Endpoints

@router.get("/monitoring/prometheus")
async def get_prometheus_metrics(
    request: Request,
):
    """Get metrics in Prometheus format."""
    try:
        metrics = generate_prometheus_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "format": "prometheus",
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate Prometheus metrics"
        )


@router.get("/monitoring/health-summary")
async def get_health_summary(
    request: Request,
):
    """Get comprehensive system health summary."""
    try:
        # Get circuit breaker health
        manager = get_circuit_breaker_manager()
        circuit_health = manager.health_check_all()
        
        # Get alert status
        alert_manager = get_alert_manager()
        active_alerts = alert_manager.get_active_alerts()
        
        # Get metrics summary
        collector = get_metrics_collector()
        metrics = collector.get_current_metrics()
        
        health_summary = {
            "overall_status": "healthy",  # Will be determined by checks
            "circuit_breakers": {
                "total": len(circuit_health),
                "healthy": sum(1 for h in circuit_health.values() if h.get("healthy", False)),
                "status": "healthy" if all(h.get("healthy", False) for h in circuit_health.values()) else "degraded"
            },
            "alerts": {
                "active_count": len(active_alerts),
                "status": "healthy" if len(active_alerts) == 0 else "warning"
            },
            "metrics": {
                "uptime_seconds": metrics.get("uptime_seconds", 0),
                "total_requests": metrics.get("total_requests", 0),
                "error_rate": metrics.get("error_rate_percent", 0)
            }
        }
        
        # Determine overall status
        if health_summary["alerts"]["status"] == "warning" or health_summary["circuit_breakers"]["status"] == "degraded":
            health_summary["overall_status"] = "degraded"
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health_summary": health_summary
        }
        
    except Exception as e:
        logger.error(f"Failed to generate health summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate health summary"
        )