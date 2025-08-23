"""
Health Check Endpoints

Simple health check and system status endpoints for monitoring
and deployment validation.
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...core.config import get_settings
from ...core.logging import get_logger
from ...core.exceptions import BinaryAnalysisException
from ...cache.base import get_redis_client
from ...llm.providers.factory import LLMProviderFactory


logger = get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment name")
    services: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    

class SystemInfoResponse(BaseModel):
    """System information response model."""
    
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment name")
    debug_mode: bool = Field(..., description="Debug mode status")
    supported_formats: list = Field(..., description="Supported binary formats")
    llm_providers: Dict[str, Any] = Field(..., description="Available LLM providers")
    limits: Dict[str, Any] = Field(..., description="System limits and quotas")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns system status and component health information.
    Used by load balancers and monitoring systems.
    """
    settings = get_settings()
    services_status = {}
    overall_status = "healthy"
    
    # Check Redis connection
    try:
        redis_client = await get_redis_client()
        is_healthy = await redis_client.health_check()
        if is_healthy:
            services_status["redis"] = {
                "status": "healthy",
                "response_time_ms": 1  # Health check is very fast
            }
        else:
            services_status["redis"] = {
                "status": "unhealthy",
                "error": "Health check failed"
            }
            overall_status = "degraded"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services_status["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_status = "degraded"
    
    # Check LLM providers
    try:
        factory = LLMProviderFactory()
        healthy_providers = factory.get_healthy_providers()
        provider_stats = factory.get_provider_stats()
        
        services_status["llm_providers"] = {
            "status": "healthy" if healthy_providers else "degraded",
            "healthy_count": len(healthy_providers),
            "total_configured": len(factory.provider_configs),
            "providers": {
                provider_id: {
                    "status": "healthy" if provider_id in healthy_providers else "unhealthy",
                    "requests": stats.total_requests,
                    "success_rate": round(stats.success_rate, 2)
                }
                for provider_id, stats in provider_stats.items()
            }
        }
        
        # Don't mark overall status as unhealthy if no providers are configured
        # This allows the system to function without LLM providers for basic operations
        if not healthy_providers and len(factory.provider_configs) > 0:
            overall_status = "degraded"
            
    except Exception as e:
        logger.warning(f"LLM providers health check failed (non-critical): {e}")
        services_status["llm_providers"] = {
            "status": "unavailable",
            "error": str(e),
            "note": "LLM providers not configured or unavailable"
        }
        # Don't mark overall status as degraded for LLM provider issues in basic health check
    
    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        environment=settings.environment,
        services=services_status
    )


@router.get("/health/ready")
async def readiness_check():
    """
    Kubernetes-style readiness check.
    
    Returns 200 if service is ready to accept requests,
    503 if not ready.
    """
    try:
        # Check Redis
        redis_client = await get_redis_client()
        is_healthy = await redis_client.health_check()
        if not is_healthy:
            raise Exception("Redis health check failed")
        
        # Note: We don't require LLM providers for readiness
        # The system can handle basic decompilation without LLM translation
        # This makes the service more resilient to LLM provider issues
        
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        # Use FastAPI HTTPException instead of custom exception for proper error handling
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")


@router.get("/health/live")
async def liveness_check():
    """
    Kubernetes-style liveness check.
    
    Simple check that the service is running.
    Always returns 200 unless the application is completely broken.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/system/info", response_model=SystemInfoResponse)
async def system_info():
    """
    Get system information and capabilities.
    
    Returns information about supported formats, LLM providers,
    system limits, and configuration.
    """
    settings = get_settings()
    
    # Get LLM provider information
    llm_info = {}
    try:
        factory = LLMProviderFactory()
        supported_providers = [str(p) for p in factory.get_supported_providers()]
        healthy_providers = factory.get_healthy_providers()
        
        llm_info = {
            "supported": supported_providers,
            "healthy": healthy_providers,
            "total_configured": len(factory.provider_configs),
            "capabilities": {
                "function_translation": True,
                "import_explanation": True,
                "string_interpretation": True,
                "overall_summary": True
            }
        }
    except Exception as e:
        logger.warning(f"Failed to get LLM provider info (non-critical): {e}")
        # Provide basic LLM info even if providers aren't configured
        llm_info = {
            "supported": ["openai", "anthropic", "gemini"],
            "healthy": [],
            "total_configured": 0,
            "capabilities": {
                "function_translation": True,
                "import_explanation": True,
                "string_interpretation": True,
                "overall_summary": True
            },
            "note": "LLM providers not configured or unavailable"
        }
    
    return SystemInfoResponse(
        version="1.0.0",
        environment=settings.environment,
        debug_mode=settings.debug,
        supported_formats=settings.analysis.supported_formats,
        llm_providers=llm_info,
        limits={
            "max_file_size_mb": settings.analysis.max_file_size_mb,
            "max_timeout_seconds": settings.analysis.max_timeout_seconds,
            "supported_architectures": ["x86", "x64", "ARM", "ARM64"]
        }
    )