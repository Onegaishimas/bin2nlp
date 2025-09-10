"""
LLM Provider Endpoints

Endpoints for managing and querying LLM provider availability,
capabilities, and configuration options.
"""


from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends

from ...core.logging import get_logger
from ...core.config import get_settings
from ...llm.providers.factory import LLMProviderFactory
from ...llm.base import LLMConfig, LLMProviderType
from ...models.api.decompilation import LLMProvidersResponse, LLMProviderInfo


logger = get_logger(__name__)
router = APIRouter()

# Global factory instance (singleton pattern)
_factory_instance: Optional[LLMProviderFactory] = None


async def get_llm_factory() -> LLMProviderFactory:
    """Dependency to get initialized LLM provider factory (singleton)."""
    global _factory_instance
    
    if _factory_instance is not None:
        return _factory_instance
    
    # Create and configure factory
    factory = LLMProviderFactory()
    settings = get_settings()
    
    # OpenAI Provider (Ollama)
    if settings.llm.openai_api_key:
        openai_config = LLMConfig(
            provider_id=LLMProviderType.OPENAI,
            api_key=settings.llm.openai_api_key,
            default_model=settings.llm.openai_default_model or "gpt-4",
            endpoint_url=settings.llm.openai_base_url,
            max_tokens=settings.llm.default_max_tokens or 4000,
            temperature=settings.llm.default_temperature or 0.1,
            timeout_seconds=settings.llm.request_timeout_seconds or 30
        )
        factory.add_provider(openai_config)
        logger.info(f"Added OpenAI provider with endpoint: {settings.llm.openai_base_url}")
    
    # Anthropic Provider
    if settings.llm.anthropic_api_key:
        anthropic_config = LLMConfig(
            provider_id=LLMProviderType.ANTHROPIC,
            api_key=settings.llm.anthropic_api_key,
            default_model=settings.llm.anthropic_default_model or "claude-3-sonnet-20240229",
            max_tokens=settings.llm.default_max_tokens or 4000,
            temperature=settings.llm.default_temperature or 0.1,
            timeout_seconds=settings.llm.request_timeout_seconds or 30
        )
        factory.add_provider(anthropic_config)
        logger.info("Added Anthropic provider")
    
    # Google Gemini Provider
    if settings.llm.gemini_api_key:
        gemini_config = LLMConfig(
            provider_id=LLMProviderType.GEMINI,
            api_key=settings.llm.gemini_api_key,
            default_model=settings.llm.gemini_default_model or "gemini-pro",
            max_tokens=settings.llm.default_max_tokens or 4000,
            temperature=settings.llm.default_temperature or 0.1,
            timeout_seconds=settings.llm.request_timeout_seconds or 30
        )
        factory.add_provider(gemini_config)
        logger.info("Added Gemini provider")
    
    # Ollama Provider (Local - no API key required, always enabled if in enabled_providers)
    if "ollama" in settings.llm.enabled_providers:
        ollama_config = LLMConfig(
            provider_id=LLMProviderType.OLLAMA,
            api_key="",  # Ollama doesn't require API key
            default_model=settings.llm.ollama_default_model or "llama3.1:8b",
            endpoint_url=settings.llm.ollama_base_url or "http://localhost:11434/v1",
            max_tokens=settings.llm.default_max_tokens or 4000,
            temperature=settings.llm.default_temperature or 0.1,
            timeout_seconds=settings.llm.request_timeout_seconds or 30
        )
        factory.add_provider(ollama_config)
        logger.info(f"Added Ollama provider with endpoint: {settings.llm.ollama_base_url or 'http://localhost:11434/v1'}")
    
    await factory.initialize()
    _factory_instance = factory
    logger.info(f"LLM factory initialized with {len(factory.provider_configs)} providers")
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
                "gemini": ["gemini-pro", "gemini-pro-vision", "gemini-flash"],
                "ollama": ["llama3.1:8b", "codellama:7b", "llama3.2:3b", "mistral:7b"]
            }.get(provider_id, [])
            
            # Get approximate costs (per 1K tokens)
            cost_estimates = {
                "openai": 0.03,     # GPT-4 approximate
                "anthropic": 0.015,  # Claude-3 Sonnet approximate  
                "gemini": 0.0005,    # Gemini Pro approximate
                "ollama": 0.0       # Free local inference
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
                    "gemini": "Google Gemini",
                    "ollama": "Ollama (Local)"
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
                    "gemini": 0.0005,
                    "ollama": 0.0
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
                "gemini": "Google Gemini",
                "ollama": "Ollama (Local)"
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
                    "gemini": 1000000,     # Gemini Pro
                    "ollama": 32768        # Llama models typical context
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
                ],
                "ollama": [
                    {"id": "llama3.1:8b", "name": "Llama 3.1 8B", "cost_per_1k_tokens": 0.0},
                    {"id": "codellama:7b", "name": "Code Llama 7B", "cost_per_1k_tokens": 0.0},
                    {"id": "llama3.2:3b", "name": "Llama 3.2 3B", "cost_per_1k_tokens": 0.0},
                    {"id": "mistral:7b", "name": "Mistral 7B", "cost_per_1k_tokens": 0.0}
                ]
            }.get(provider_id, []),
            
            "configuration": {
                "default_model": {
                    "openai": "gpt-4",
                    "anthropic": "claude-3-sonnet-20240229", 
                    "gemini": "gemini-pro",
                    "ollama": "llama3.1:8b"
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