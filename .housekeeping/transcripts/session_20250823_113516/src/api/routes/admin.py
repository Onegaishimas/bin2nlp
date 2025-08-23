"""
Admin and Management API Endpoints

Administrative functions including API key management,
system monitoring, and configuration management.

These endpoints require elevated permissions.
"""


from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ...core.logging import get_logger
from pydantic import BaseModel, Field, field_validator

from ...core.config import get_settings
from ...core.metrics import get_metrics_collector, get_performance_summary, OperationType
from ...core.circuit_breaker import get_circuit_breaker_manager
from ...core.dashboards import (
    get_alert_manager, get_dashboard_generator, run_alert_checks, generate_prometheus_metrics
)
from ...cache.base import get_redis_client
from ..middleware import (
    require_auth,
    require_permission,
    APIKeyManager,
    LLMProviderRateLimiter,
    get_current_user
)

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Pydantic models for API key management
class CreateAPIKeyRequest(BaseModel):
    """Request model for creating new API keys."""
    
    user_id: str = Field(..., min_length=1, max_length=100, description="User identifier")
    tier: str = Field(default="basic", pattern="^(basic|standard|premium|enterprise)$", description="Access tier")
    permissions: List[str] = Field(default=["read"], description="List of permissions")
    expires_days: Optional[int] = Field(default=None, ge=1, le=3650, description="Key expiry in days")
    description: Optional[str] = Field(default=None, max_length=255, description="Key description")
    
    @field_validator('permissions')
    @classmethod
    def validate_permissions(cls, v):
        """Validate that permissions are from allowed list."""
        valid_permissions = {"read", "write", "admin"}
        for perm in v:
            if perm not in valid_permissions:
                raise ValueError(f"Invalid permission '{perm}'. Must be one of: {', '.join(sorted(valid_permissions))}")
        return v


class APIKeyInfo(BaseModel):
    """API key information response."""
    
    key_id: str = Field(..., description="Key identifier")
    user_id: str = Field(..., description="User identifier") 
    tier: str = Field(..., description="Access tier")
    permissions: List[str] = Field(..., description="Permissions list")
    status: str = Field(..., description="Key status")
    created_at: str = Field(..., description="Creation timestamp")
    last_used_at: Optional[str] = Field(None, description="Last usage timestamp")
    expires_at: Optional[str] = Field(None, description="Expiry timestamp")


class APIKeyCreateResponse(BaseModel):
    """Response for API key creation."""
    
    success: bool = Field(..., description="Operation success")
    api_key: str = Field(..., description="Generated API key")
    key_info: APIKeyInfo = Field(..., description="Key information")
    warning: Optional[str] = Field(None, description="Security warnings")


class SystemStatsResponse(BaseModel):
    """System statistics response."""
    
    redis_stats: Dict[str, Any] = Field(..., description="Redis statistics")
    rate_limit_stats: Dict[str, Any] = Field(..., description="Rate limiting statistics")
    api_key_stats: Dict[str, Any] = Field(..., description="API key statistics")
    system_health: Dict[str, Any] = Field(..., description="System health metrics")


# API Key Management Endpoints

@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: dict = Depends(require_permission("admin"))
) -> APIKeyCreateResponse:
    """
    Create a new API key.
    
    Requires admin permission. Creates API keys with specified
    tier and permissions for the target user.
    """
    api_key_manager = APIKeyManager()
    
    try:
        # Create the API key
        api_key, key_id = await api_key_manager.create_api_key(
            user_id=request.user_id,
            tier=request.tier,
            permissions=request.permissions,
            expires_days=request.expires_days
        )
        
        # Get the key info for response
        key_info_list = await api_key_manager.list_user_keys(request.user_id)
        key_info = next((k for k in key_info_list if k["key_id"] == key_id), None)
        
        if not key_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created key information"
            )
        
        # Security warning for high-tier keys
        warning = None
        if request.tier in ["premium", "enterprise"]:
            warning = "High-tier API key created. Ensure secure storage and handling."
        
        logger.info(
            f"API key created by admin {current_user['user_id']} "
            f"for user {request.user_id}, tier: {request.tier}, key_id: {key_id}"
        )
        
        return APIKeyCreateResponse(
            success=True,
            api_key=api_key,
            key_info=APIKeyInfo(**key_info),
            warning=warning
        )
        
    except Exception as e:
        logger.error(f"Failed to create API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


@router.get("/api-keys/{user_id}", response_model=List[APIKeyInfo])
async def list_user_api_keys(
    user_id: str,
    current_user: dict = Depends(require_permission("admin"))
) -> List[APIKeyInfo]:
    """
    List all API keys for a user.
    
    Requires admin permission.
    """
    # Prevent directory traversal attacks
    if any(char in user_id for char in ['/', '\\', '.', ':', '<', '>', '|', '*', '?']):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format"
        )
    
    api_key_manager = APIKeyManager()
    
    try:
        keys_info = await api_key_manager.list_user_keys(user_id)
        return [APIKeyInfo(**key_info) for key_info in keys_info]
    
    except Exception as e:
        logger.error(f"Failed to list API keys for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.delete("/api-keys/{user_id}/{key_id}")
async def revoke_api_key(
    user_id: str,
    key_id: str,
    current_user: dict = Depends(require_permission("admin"))
) -> Dict[str, bool]:
    """
    Revoke an API key.
    
    Requires admin permission.
    """
    # Prevent directory traversal attacks
    if any(char in user_id for char in ['/', '\\', '.', ':', '<', '>', '|', '*', '?']):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format"
        )
    
    if any(char in key_id for char in ['/', '\\', '.', ':', '<', '>', '|', '*', '?']):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key_id format"
        )
    
    api_key_manager = APIKeyManager()
    
    try:
        # Get the key to construct full API key for revocation
        keys_info = await api_key_manager.list_user_keys(user_id)
        target_key = next((k for k in keys_info if k["key_id"] == key_id), None)
        
        if not target_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Use a more direct approach: remove from user's key set and remove key data
        redis = await get_redis_client()
        logger.info(f"Starting deletion process for key_id: {key_id}, user_id: {user_id}")
        
        try:
            # Remove from user's key set first
            removed_count = await redis.srem(f"user_keys:{user_id}", key_id)
            logger.info(f"Removed {removed_count} keys from user_keys:{user_id}")
            
            # Find and remove the actual key data by scanning for this key_id
            # Get all api_key keys and check each one
            all_keys = []
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor=cursor, match="api_key:*")
                # Decode keys if they're bytes
                decoded_keys = [api_key_manager._decode_redis_value(k) for k in keys]
                all_keys.extend(decoded_keys)
                if cursor == 0:
                    break
            
            logger.info(f"Found {len(all_keys)} API keys to check for key_id: {key_id}")
            
            # Check each key for our target key_id
            found_and_deleted = False
            for i, key_name in enumerate(all_keys):
                try:
                    key_data = await redis.hgetall(key_name)
                    if not key_data:
                        logger.debug(f"Key {i}: {key_name} - no data")
                        continue
                    decoded_key_data = {
                        api_key_manager._decode_redis_value(k): api_key_manager._decode_redis_value(v)
                        for k, v in key_data.items()
                    }
                    current_key_id = decoded_key_data.get("key_id")
                    logger.debug(f"Key {i}: {key_name} - key_id: {current_key_id}")
                    
                    if current_key_id == key_id:
                        delete_result = await redis.delete(key_name)
                        logger.info(f"Successfully deleted Redis key: {key_name} (result: {delete_result})")
                        found_and_deleted = True
                        break
                except Exception as e:
                    logger.error(f"Error processing key {key_name}: {e}")
            
            if not found_and_deleted:
                logger.warning(f"Could not find Redis key to delete for key_id: {key_id}")
            
        except Exception as e:
            logger.error(f"Error during key deletion: {e}")
            raise
        
        logger.info(
            f"API key deletion completed by admin {current_user['user_id']}: "
            f"user={user_id}, key_id={key_id}, success={found_and_deleted}"
        )
        
        return {"success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key {key_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}"
        )


# System Monitoring Endpoints

@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    current_user: dict = Depends(require_permission("admin"))
) -> SystemStatsResponse:
    """
    Get comprehensive system statistics.
    
    Requires admin permission.
    """
    try:
        redis = await get_redis_client()
        
        # Redis statistics
        redis_info = await redis.info()
        redis_stats = {
            "connected_clients": redis_info.get("connected_clients", 0),
            "used_memory_human": redis_info.get("used_memory_human", "0B"),
            "keyspace_hits": redis_info.get("keyspace_hits", 0),
            "keyspace_misses": redis_info.get("keyspace_misses", 0),
            "total_commands_processed": redis_info.get("total_commands_processed", 0)
        }
        
        # Rate limiting stats (sample)
        rate_limit_stats = {
            "active_rate_limits": await redis.eval(
                "return #redis.call('keys', 'rate_limit:*')", 0
            ),
            "llm_rate_limits": await redis.eval(
                "return #redis.call('keys', 'llm_rate:*')", 0
            )
        }
        
        # API key stats
        api_key_count = await redis.eval(
            "return #redis.call('keys', 'api_key:*')", 0
        )
        api_key_stats = {
            "total_keys": api_key_count,
            "active_keys": api_key_count  # Simplified - would need more logic for accurate count
        }
        
        # System health
        system_health = {
            "redis_available": True,
            "timestamp": datetime.now().isoformat(),
            "status": "healthy"
        }
        
        return SystemStatsResponse(
            redis_stats=redis_stats,
            rate_limit_stats=rate_limit_stats,
            api_key_stats=api_key_stats,
            system_health=system_health
        )
        
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system statistics: {str(e)}"
        )


@router.get("/rate-limits/{user_id}")
async def get_user_rate_limits(
    user_id: str,
    current_user: dict = Depends(require_permission("admin"))
) -> Dict[str, Any]:
    """
    Get current rate limit status for a user.
    
    Requires admin permission.
    """
    try:
        llm_rate_limiter = LLMProviderRateLimiter()
        
        # Get LLM usage stats
        llm_stats = await llm_rate_limiter.get_llm_usage_stats(user_id)
        
        # Get general rate limit info from Redis
        redis = await get_redis_client()
        user_rate_limits = {}
        
        # Scan for user's rate limit keys
        async for key in redis.scan_iter(match=f"rate_limit:user:{user_id}:*"):
            # Handle both bytes and string responses from Redis (defensive programming)
            if isinstance(key, bytes):
                key_str = key.decode('utf-8')
            else:
                key_str = str(key)  # Ensure it's always a string
            
            key_parts = key_str.split(":")
            if len(key_parts) >= 4:
                limit_type = key_parts[3]
                # Use string version for Redis operations to ensure consistency
                count = await redis.zcard(key_str)
                user_rate_limits[limit_type] = count
        
        return {
            "user_id": user_id,
            "general_rate_limits": user_rate_limits,
            "llm_usage": llm_stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get rate limits for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve rate limit information: {str(e)}"
        )


# Configuration Management

@router.get("/config")
async def get_system_config(
    current_user: dict = Depends(require_permission("admin"))
) -> Dict[str, Any]:
    """
    Get current system configuration (non-sensitive).
    
    Requires admin permission.
    """
    try:
        settings = get_settings()
        
        # Return non-sensitive configuration
        config = {
            "environment": settings.environment,
            "debug": settings.debug,
            "api": {
                "host": settings.api.host,
                "port": settings.api.port,
                "workers": settings.api.workers,
                "cors_origins": settings.api.cors_origins
            },
            "analysis": {
                "max_file_size_mb": settings.analysis.max_file_size_mb,
                "default_timeout_seconds": settings.analysis.default_timeout_seconds,
                "max_timeout_seconds": settings.analysis.max_timeout_seconds,
                "supported_formats": settings.analysis.supported_formats
            },
            "cache": {
                "default_ttl_seconds": settings.cache.default_ttl_seconds,
                "analysis_result_ttl_seconds": settings.cache.analysis_result_ttl_seconds,
                "max_cache_size_mb": settings.cache.max_cache_size_mb
            },
            "security": {
                "default_rate_limit_per_minute": settings.security.default_rate_limit_per_minute,
                "default_rate_limit_per_day": settings.security.default_rate_limit_per_day,
                "enforce_https": settings.security.enforce_https
            },
            "llm": {
                "enabled_providers": settings.llm.enabled_providers,
                "default_provider": settings.llm.default_provider,
                "requests_per_minute": settings.llm.requests_per_minute,
                "tokens_per_minute": settings.llm.tokens_per_minute
            }
        }
        
        return config
        
    except Exception as e:
        logger.error(f"Failed to get system configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve configuration: {str(e)}"
        )


# Development utilities (only available in development)

@router.post("/dev/create-api-key")
async def create_dev_api_key(
    request: Request,
    user_id: str = "dev_user"
) -> Dict[str, str]:
    """
    Create a development API key.
    
    Only available in development/debug mode.
    """
    settings = get_settings()
    
    if settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Development endpoints not available in production"
        )
    
    try:
        from ..middleware import create_dev_api_key
        
        api_key = await create_dev_api_key(user_id)
        
        return {
            "api_key": api_key,
            "user_id": user_id,
            "tier": "enterprise",
            "note": "Development API key - do not use in production"
        }
        
    except Exception as e:
        logger.error(f"Failed to create development API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create development API key: {str(e)}"
        )


# Performance Metrics Endpoints

@router.get("/metrics/current")
async def get_current_metrics(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """
    Get current snapshot of all metrics.
    
    Returns counters, gauges, histograms, and performance data.
    """
    try:
        collector = get_metrics_collector()
        metrics = collector.get_current_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics,
            "status": "active"
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve current metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.get("/metrics/performance")
async def get_performance_metrics(
    request: Request,
    operation_type: Optional[str] = None,
    time_window_minutes: int = 60,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """
    Get performance summary for operations.
    
    Parameters:
    - operation_type: Filter by operation type (decompilation, llm_request, etc.)
    - time_window_minutes: Time window for analysis (default: 60 minutes)
    """
    try:
        # Validate operation type if provided
        op_type = None
        if operation_type:
            try:
                op_type = OperationType(operation_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid operation_type. Valid options: {[op.value for op in OperationType]}"
                )
        
        # Validate time window
        if time_window_minutes < 1 or time_window_minutes > 1440:  # Max 24 hours
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="time_window_minutes must be between 1 and 1440"
            )
        
        summary = get_performance_summary(op_type, time_window_minutes)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "performance_summary": summary,
            "parameters": {
                "operation_type": operation_type,
                "time_window_minutes": time_window_minutes
            }
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Get detailed status of a specific circuit breaker."""
    try:
        manager = get_circuit_breaker_manager()
        circuits = manager.get_all_circuits()
        
        if circuit_name not in circuits:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit breaker '{circuit_name}' not found"
            )
        
        circuit = circuits[circuit_name]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "circuit_name": circuit_name,
            "state": circuit.get_state().value,
            "is_available": circuit.is_available(),
            "stats": circuit.get_stats(),
            "config": {
                "failure_threshold": circuit.config.failure_threshold,
                "success_threshold": circuit.config.success_threshold,
                "timeout_seconds": circuit.config.timeout_seconds,
                "health_check_interval": circuit.config.health_check_interval
            }
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Reset a specific circuit breaker to closed state."""
    try:
        manager = get_circuit_breaker_manager()
        circuits = manager.get_all_circuits()
        
        if circuit_name not in circuits:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit breaker '{circuit_name}' not found"
            )
        
        circuit = circuits[circuit_name]
        await circuit.reset()
        
        logger.info(f"Circuit breaker {circuit_name} manually reset by user {current_user.get('user_id')}")
        
        return {
            "message": f"Circuit breaker '{circuit_name}' has been reset",
            "timestamp": datetime.utcnow().isoformat(),
            "reset_by": current_user.get('user_id')
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Force a circuit breaker to open state."""
    try:
        manager = get_circuit_breaker_manager()
        circuits = manager.get_all_circuits()
        
        if circuit_name not in circuits:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit breaker '{circuit_name}' not found"
            )
        
        circuit = circuits[circuit_name]
        await circuit.force_open()
        
        logger.warning(f"Circuit breaker {circuit_name} manually forced open by user {current_user.get('user_id')}")
        
        return {
            "message": f"Circuit breaker '{circuit_name}' has been forced open",
            "timestamp": datetime.utcnow().isoformat(),
            "forced_by": current_user.get('user_id')
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Perform health checks on all circuit breakers."""
    try:
        manager = get_circuit_breaker_manager()
        health_results = await manager.health_check_all()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health_check_results": health_results,
            "healthy_circuits": sum(1 for result in health_results.values() if result),
            "total_circuits": len(health_results)
        }
        
    except Exception as e:
        logger.error(f"Failed to perform health checks on all circuits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform health checks on all circuits"
        )


# Dashboard and Alerting Endpoints

@router.get("/dashboards/overview")
async def get_overview_dashboard(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Get the main system overview dashboard."""
    try:
        generator = get_dashboard_generator()
        dashboard = generator.generate_overview_dashboard()
        
        return {
            "dashboard": dashboard.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Get detailed performance dashboard."""
    try:
        generator = get_dashboard_generator()
        dashboard = generator.generate_performance_dashboard()
        
        return {
            "dashboard": dashboard.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to generate performance dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate performance dashboard"
        )


@router.get("/alerts")
async def get_all_alerts(
    request: Request,
    include_history: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Get all alerts with optional history."""
    try:
        alert_manager = get_alert_manager()
        
        active_alerts = alert_manager.get_active_alerts()
        alert_summary = alert_manager.get_alert_summary()
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": alert_summary,
            "active_alerts": [alert.to_dict() for alert in active_alerts]
        }
        
        if include_history:
            result["alert_history"] = [alert.to_dict() for alert in alert_manager.alert_history[-50:]]  # Last 50
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to retrieve alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alerts"
        )


@router.post("/alerts/check")
async def run_alert_checks_endpoint(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Manually trigger alert checks."""
    try:
        triggered_alerts = await run_alert_checks()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "alerts_checked": True,
            "triggered_alerts": len(triggered_alerts),
            "new_alerts": [alert.to_dict() for alert in triggered_alerts]
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Acknowledge an active alert."""
    try:
        alert_manager = get_alert_manager()
        user_id = current_user.get('user_id', 'unknown')
        
        success = alert_manager.acknowledge_alert(alert_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert '{alert_id}' not found or not active"
            )
        
        return {
            "message": f"Alert '{alert_id}' acknowledged",
            "acknowledged_by": user_id,
            "timestamp": datetime.utcnow().isoformat()
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
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Manually resolve an active alert."""
    try:
        alert_manager = get_alert_manager()
        
        success = alert_manager.resolve_alert(alert_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Alert '{alert_id}' not found or not active"
            )
        
        return {
            "message": f"Alert '{alert_id}' resolved",
            "resolved_by": current_user.get('user_id', 'unknown'),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve alert {alert_id}"
        )


@router.get("/monitoring/prometheus")
async def get_prometheus_metrics(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Get Prometheus-format metrics for external monitoring integration."""
    try:
        metrics_text = generate_prometheus_metrics()
        
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=metrics_text,
            media_type="text/plain; version=0.0.4; charset=utf-8"
        )
        
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate Prometheus metrics"
        )


@router.get("/monitoring/health-summary")
async def get_health_summary(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
    auth_check = Depends(require_permission(["admin"])),
):
    """Get comprehensive system health summary."""
    try:
        # Get various health indicators
        alert_manager = get_alert_manager()
        circuit_manager = get_circuit_breaker_manager()
        
        alert_summary = alert_manager.get_alert_summary()
        circuit_stats = circuit_manager.get_circuit_stats()
        
        # Performance summaries
        decomp_summary = get_performance_summary(OperationType.DECOMPILATION, 15)
        llm_summary = get_performance_summary(OperationType.LLM_REQUEST, 15)
        
        # Calculate overall health score (0-100)
        health_factors = []
        
        # Alert factor (0-25 points)
        active_alerts = alert_summary["total_active"]
        critical_alerts = alert_summary["severity_breakdown"]["critical"]
        alert_score = max(0, 25 - (active_alerts * 3) - (critical_alerts * 10))
        health_factors.append(("alerts", alert_score, 25))
        
        # Circuit breaker factor (0-25 points)
        total_circuits = len(circuit_stats)
        healthy_circuits = sum(1 for info in circuit_stats.values() if info["is_available"])
        circuit_score = (healthy_circuits / total_circuits * 25) if total_circuits > 0 else 25
        health_factors.append(("circuits", circuit_score, 25))
        
        # Performance factor (0-25 points each for decomp and LLM)
        decomp_score = 25
        if decomp_summary.get("total_operations", 0) > 0:
            success_rate = decomp_summary["success_rate"]
            avg_duration = decomp_summary["duration_stats"]["avg_ms"]
            
            # Reduce score for low success rate
            if success_rate < 95:
                decomp_score -= (95 - success_rate) * 0.5
            
            # Reduce score for slow performance  
            if avg_duration > 10000:  # 10 seconds
                decomp_score -= min(15, (avg_duration - 10000) / 2000)
            
            decomp_score = max(0, decomp_score)
        
        health_factors.append(("decompilation", decomp_score, 25))
        
        llm_score = 25
        if llm_summary.get("total_operations", 0) > 0:
            success_rate = llm_summary["success_rate"]
            avg_duration = llm_summary["duration_stats"]["avg_ms"]
            
            if success_rate < 98:
                llm_score -= (98 - success_rate) * 0.5
            
            if avg_duration > 5000:  # 5 seconds
                llm_score -= min(15, (avg_duration - 5000) / 1000)
            
            llm_score = max(0, llm_score)
        
        health_factors.append(("llm", llm_score, 25))
        
        # Calculate overall health
        total_score = sum(score for _, score, _ in health_factors)
        overall_health = min(100, total_score)
        
        # Determine status
        if overall_health >= 90:
            status = "healthy"
        elif overall_health >= 70:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": {
                "score": round(overall_health, 1),
                "status": status,
                "factors": [
                    {
                        "component": name,
                        "score": round(score, 1),
                        "max_score": max_score,
                        "percentage": round(score / max_score * 100, 1)
                    }
                    for name, score, max_score in health_factors
                ]
            },
            "component_health": {
                "alerts": alert_summary,
                "circuits": {
                    "total": total_circuits,
                    "healthy": healthy_circuits,
                    "health_percentage": round(healthy_circuits / total_circuits * 100, 1) if total_circuits > 0 else 100
                },
                "performance": {
                    "decompilation": {
                        "operations": decomp_summary.get("total_operations", 0),
                        "success_rate": decomp_summary.get("success_rate", 0),
                        "avg_duration_ms": decomp_summary.get("duration_stats", {}).get("avg_ms", 0)
                    },
                    "llm": {
                        "operations": llm_summary.get("total_operations", 0),
                        "success_rate": llm_summary.get("success_rate", 0),
                        "avg_duration_ms": llm_summary.get("duration_stats", {}).get("avg_ms", 0)
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to generate health summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate health summary"
        )


# Bootstrap endpoint for initial setup
@router.post("/bootstrap/create-admin")
async def bootstrap_create_admin():
    """
    Bootstrap endpoint to create the first admin user.
    
    Only works when no admin-tier API keys exist in the system.
    This provides a secure way to create the initial admin user.
    """
    try:
        # Check if admin keys already exist
        redis = await get_redis_client()
        admin_keys = await redis.keys("api_key:*")
        
        # Check if any existing keys have admin permissions
        for key_pattern in admin_keys:
            key_data = await redis.hgetall(key_pattern)
            if key_data and "admin" in key_data.get("permissions", ""):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin users already exist. Use existing admin credentials to create additional users."
                )
        
        # Create bootstrap admin key
        api_key_manager = APIKeyManager()
        api_key, key_id = await api_key_manager.create_api_key(
            user_id="bootstrap_admin",
            tier="enterprise",
            permissions=["read", "write", "admin"]
        )
        
        logger.warning("Bootstrap admin API key created - this should only happen during initial setup")
        
        return {
            "success": True,
            "message": "Bootstrap admin user created successfully",
            "api_key": api_key,
            "key_id": key_id,
            "user_id": "bootstrap_admin",
            "tier": "enterprise",
            "permissions": ["read", "write", "admin"],
            "warning": "This is a one-time bootstrap operation. Save the API key securely!",
            "usage": f'Use this key in the Authorization header: Bearer {api_key}'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create bootstrap admin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bootstrap admin: {str(e)}"
        )