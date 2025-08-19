"""
LLM Provider Endpoints

Endpoints for managing and querying LLM provider availability,
capabilities, and configuration options.
"""


from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends

from ...core.logging import get_logger
from ...llm.providers.factory import LLMProviderFactory
from ...models.api.decompilation import LLMProvidersResponse, LLMProviderInfo


logger = get_logger(__name__)
router = APIRouter()


async def get_llm_factory() -> LLMProviderFactory:
    """Dependency to get initialized LLM provider factory."""
    factory = LLMProviderFactory()
    await factory.initialize()
    return factory


@router.get("/llm-providers", response_model=LLMProvidersResponse)
async def list_llm_providers(
    llm_factory: LLMProviderFactory = Depends(get_llm_factory)
):
    """
    List available LLM providers and their capabilities.
    
    Returns information about all configured LLM providers including
    health status, available models, and cost information.
    """
    try:
        # Get provider information
        supported_providers = llm_factory.get_supported_providers()
        healthy_providers = llm_factory.get_healthy_providers()
        provider_stats = llm_factory.get_provider_stats()
        
        providers_info = []
        
        for provider_id in supported_providers:
            is_healthy = provider_id in healthy_providers
            stats = provider_stats.get(provider_id)
            
            # Get provider capabilities
            capabilities = [
                "function_translation",
                "import_explanation", 
                "string_interpretation",
                "overall_summary"
            ]
            
            # Get available models (would be from actual provider config)
            available_models = {
                "openai": ["gpt-4", "gpt-4-turbo-preview", "gpt-3.5-turbo"],
                "anthropic": ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"],
                "gemini": ["gemini-pro", "gemini-pro-vision", "gemini-flash"]
            }.get(provider_id, [])
            
            # Get approximate costs (per 1K tokens)
            cost_estimates = {
                "openai": 0.03,     # GPT-4 approximate
                "anthropic": 0.015,  # Claude-3 Sonnet approximate  
                "gemini": 0.0005    # Gemini Pro approximate
            }.get(provider_id, None)
            
            # Calculate health score
            health_score = None
            if stats:
                health_score = min(1.0, stats.success_rate / 100.0)
            
            provider_info = LLMProviderInfo(
                provider_id=provider_id,
                name={
                    "openai": "OpenAI GPT",
                    "anthropic": "Anthropic Claude",
                    "gemini": "Google Gemini"
                }.get(provider_id, provider_id.title()),
                status="healthy" if is_healthy else "unhealthy",
                available_models=available_models,
                cost_per_1k_tokens=cost_estimates,
                capabilities=capabilities,
                health_score=health_score
            )
            
            providers_info.append(provider_info)
        
        # Recommend best provider (simple heuristic: healthy + lowest cost)
        recommended_provider = None
        if healthy_providers:
            # Sort by cost (lower is better)
            healthy_with_cost = [
                (pid, {
                    "openai": 0.03,
                    "anthropic": 0.015,
                    "gemini": 0.0005
                }.get(pid, 999))
                for pid in healthy_providers
            ]
            healthy_with_cost.sort(key=lambda x: x[1])
            recommended_provider = healthy_with_cost[0][0]
        
        return LLMProvidersResponse(
            providers=providers_info,
            recommended_provider=recommended_provider,
            total_healthy=len(healthy_providers)
        )
        
    except Exception as e:
        logger.error(f"Failed to list LLM providers: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve LLM provider information")


@router.get("/llm-providers/{provider_id}")
async def get_llm_provider_details(
    provider_id: str,
    llm_factory: LLMProviderFactory = Depends(get_llm_factory)
):
    """
    Get detailed information about a specific LLM provider.
    
    Returns comprehensive information including health status,
    recent performance metrics, and configuration details.
    """
    try:
        # Validate provider exists
        supported_providers = llm_factory.get_supported_providers()
        if provider_id not in supported_providers:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        
        # Get provider stats
        provider_stats = llm_factory.get_provider_stats(provider_id)
        healthy_providers = llm_factory.get_healthy_providers()
        
        is_healthy = provider_id in healthy_providers
        stats = provider_stats.get(provider_id) if provider_stats else None
        
        # Build detailed response
        provider_details = {
            "provider_id": provider_id,
            "name": {
                "openai": "OpenAI GPT",
                "anthropic": "Anthropic Claude", 
                "gemini": "Google Gemini"
            }.get(provider_id, provider_id.title()),
            
            "status": {
                "is_healthy": is_healthy,
                "last_health_check": None,  # Would come from factory
                "consecutive_failures": stats.consecutive_failures if stats else 0,
                "health_check_failures": stats.health_check_failures if stats else 0
            },
            
            "performance": {
                "total_requests": stats.total_requests if stats else 0,
                "successful_requests": stats.successful_requests if stats else 0,
                "failed_requests": stats.failed_requests if stats else 0,
                "success_rate_percent": round(stats.success_rate, 2) if stats else 0,
                "average_latency_ms": round(stats.average_latency_ms, 2) if stats else 0,
                "total_tokens_processed": stats.total_tokens if stats else 0,
                "total_cost_usd": round(stats.total_cost, 2) if stats else 0,
                "last_used": stats.last_used.isoformat() if stats and stats.last_used else None
            },
            
            "capabilities": {
                "supported_operations": [
                    "function_translation",
                    "import_explanation",
                    "string_interpretation", 
                    "overall_summary"
                ],
                "max_context_tokens": {
                    "openai": 128000,      # GPT-4 Turbo
                    "anthropic": 200000,   # Claude-3
                    "gemini": 1000000      # Gemini Pro
                }.get(provider_id, 8192),
                
                "supports_streaming": True,
                "supports_function_calling": provider_id in ["openai"],
                "supports_vision": provider_id in ["openai", "gemini"],
            },
            
            "models": {
                "openai": [
                    {"id": "gpt-4", "name": "GPT-4", "cost_per_1k_tokens": 0.03},
                    {"id": "gpt-4-turbo-preview", "name": "GPT-4 Turbo", "cost_per_1k_tokens": 0.01},
                    {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "cost_per_1k_tokens": 0.002}
                ],
                "anthropic": [
                    {"id": "claude-3-opus-20240229", "name": "Claude-3 Opus", "cost_per_1k_tokens": 0.015},
                    {"id": "claude-3-sonnet-20240229", "name": "Claude-3 Sonnet", "cost_per_1k_tokens": 0.003},
                    {"id": "claude-3-haiku-20240307", "name": "Claude-3 Haiku", "cost_per_1k_tokens": 0.00025}
                ],
                "gemini": [
                    {"id": "gemini-pro", "name": "Gemini Pro", "cost_per_1k_tokens": 0.0005},
                    {"id": "gemini-pro-vision", "name": "Gemini Pro Vision", "cost_per_1k_tokens": 0.0025},
                    {"id": "gemini-flash", "name": "Gemini Flash", "cost_per_1k_tokens": 0.00015}
                ]
            }.get(provider_id, []),
            
            "configuration": {
                "default_model": {
                    "openai": "gpt-4",
                    "anthropic": "claude-3-sonnet-20240229", 
                    "gemini": "gemini-pro"
                }.get(provider_id),
                "default_temperature": 0.1,
                "default_max_tokens": 2048,
                "timeout_seconds": 30
            }
        }
        
        return provider_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provider details for {provider_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve provider details")


@router.post("/llm-providers/{provider_id}/health-check")
async def check_provider_health(
    provider_id: str,
    llm_factory: LLMProviderFactory = Depends(get_llm_factory)
):
    """
    Force a health check for a specific LLM provider.
    
    Triggers an immediate health check and returns the current status.
    Useful for testing provider connectivity and API key validity.
    """
    try:
        # Validate provider exists
        supported_providers = llm_factory.get_supported_providers()
        if provider_id not in supported_providers:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        
        # Get provider instance
        try:
            provider = await llm_factory.get_provider(provider_id)
        except Exception as e:
            return {
                "provider_id": provider_id,
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2024-01-15T10:30:00Z"
            }
        
        # Perform health check
        try:
            health_status = await provider.health_check()
            
            return {
                "provider_id": provider_id,
                "status": "healthy" if health_status.is_healthy else "unhealthy",
                "details": {
                    "is_healthy": health_status.is_healthy,
                    "within_rate_limits": health_status.within_rate_limits,
                    "api_latency_ms": health_status.api_latency_ms,
                    "available_models": health_status.available_models,
                    "cost_per_token": health_status.cost_per_token,
                    "error_message": health_status.error_message
                },
                "timestamp": health_status.last_check.isoformat()
            }
            
        except Exception as e:
            return {
                "provider_id": provider_id,
                "status": "unhealthy", 
                "error": f"Health check failed: {str(e)}",
                "timestamp": "2024-01-15T10:30:00Z"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check health for provider {provider_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform health check")