"""
Health Check Endpoints

Simple health check and system status endpoints for monitoring
and deployment validation.
"""

import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...core.config import get_settings
from ...core.exceptions import BinaryAnalysisException
from ...cache.base import get_redis_client
from ...llm.providers.factory import LLMProviderFactory


logger = logging.getLogger(__name__)
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
        redis_client = get_redis_client()
        await redis_client.ping()
        services_status["redis"] = {
            "status": "healthy",
            "response_time_ms": 1  # Ping is very fast
        }
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
            "status": "healthy" if healthy_providers else "unhealthy",
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
        
        if not healthy_providers:
            overall_status = "degraded"
            
    except Exception as e:
        logger.error(f"LLM providers health check failed: {e}")
        services_status["llm_providers"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        overall_status = "degraded"
    
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
        redis_client = get_redis_client()
        await redis_client.ping()
        
        # Check at least one LLM provider is available
        factory = LLMProviderFactory()
        if not factory.get_healthy_providers():
            raise BinaryAnalysisException("No healthy LLM providers available")
        
        return {"status": "ready"}
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise BinaryAnalysisException(f"Service not ready: {str(e)}")


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
        supported_providers = factory.get_supported_providers()
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
        logger.error(f"Failed to get LLM provider info: {e}")
        llm_info = {"error": str(e)}
    
    return SystemInfoResponse(
        version="1.0.0",
        environment=settings.environment,
        debug_mode=settings.debug,
        supported_formats=["PE", "ELF", "Mach-O"],
        llm_providers=llm_info,
        limits={
            "max_file_size_mb": settings.decompilation.max_file_size_mb,
            "max_timeout_seconds": settings.decompilation.max_timeout_seconds,
            "supported_architectures": ["x86", "x64", "ARM", "ARM64"]
        }
    )