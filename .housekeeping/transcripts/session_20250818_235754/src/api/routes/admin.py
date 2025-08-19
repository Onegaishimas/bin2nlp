"""
Admin and Management API Endpoints

Administrative functions including API key management,
system monitoring, and configuration management.

These endpoints require elevated permissions.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...core.config import get_settings
from ...cache.base import get_redis_client
from ..middleware import (
    require_auth,
    require_permission,
    APIKeyManager,
    LLMProviderRateLimiter,
    get_current_user
)

logger = logging.getLogger(__name__)

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
        
        # Note: This is a simplified approach. In production, you'd want to store
        # a revocation list or flag rather than trying to reconstruct the key.
        # For now, we'll mark it as revoked in Redis.
        redis = get_redis_client()
        await redis.hset(f"revoked_keys:{key_id}", "revoked_at", datetime.now().isoformat())
        
        logger.info(
            f"API key revoked by admin {current_user['user_id']}: "
            f"user={user_id}, key_id={key_id}"
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
        redis = get_redis_client()
        
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
        redis = get_redis_client()
        user_rate_limits = {}
        
        # Scan for user's rate limit keys
        async for key in redis.scan_iter(match=f"rate_limit:user:{user_id}:*"):
            key_parts = key.split(":")
            if len(key_parts) >= 4:
                limit_type = key_parts[3]
                count = await redis.zcard(key)
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