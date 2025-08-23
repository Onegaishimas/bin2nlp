"""
LLM Translation Service Orchestrator

Coordinates the integration between decompilation results and LLM translation,
handling provider selection, context preparation, and result merging.
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import LLMConfig, LLMProviderType
from .providers.openai_provider import OpenAIProvider
from .providers.anthropic_provider import AnthropicProvider
from .providers.gemini_provider import GeminiProvider
from .prompts.manager import ContextualPromptManager
from ..models.decompilation.results import (
    FunctionTranslation, ImportTranslation, StringTranslation, OverallSummary,
    DecompilationResult, LLMProviderMetadata
)
from ..core.logging import get_logger
from ..core.metrics import increment_counter, time_async_operation, OperationType

logger = get_logger(__name__)


class TranslationServiceOrchestrator:
    """
    Main orchestrator for LLM translation services.
    
    Handles provider selection, context preparation, translation coordination,
    and result merging for decompilation analysis.
    """
    
    def __init__(self):
        self.prompt_manager = ContextualPromptManager()
        self._providers: Dict[str, Any] = {}
        self._initialized = False
    
    async def initialize(self, llm_config: Optional[Dict[str, Any]] = None):
        """Initialize available LLM providers based on configuration."""
        if self._initialized:
            return
        
        logger.info("Initializing LLM Translation Service")
        
        # Import settings to get environment variables
        from ..core.config import get_settings
        settings = get_settings()
        
        # Initialize providers based on available configurations
        # Check if OpenAI/Ollama configuration is available
        provider_requested = llm_config and llm_config.get("llm_provider") == "openai"
        
        # Check for OpenAI config in LLM settings
        llm_openai_key = settings.llm.openai_api_key.get_secret_value() if settings.llm.openai_api_key else None
        llm_openai_url = settings.llm.openai_base_url
        llm_openai_model = settings.llm.openai_default_model
        
        env_has_openai_config = bool(llm_openai_key) and bool(llm_openai_url)
        
        if provider_requested or env_has_openai_config:
            try:
                # Use environment variables as defaults, with llm_config overrides
                api_key = (llm_config.get("llm_api_key") if llm_config else None) or llm_openai_key
                endpoint_url = (llm_config.get("llm_endpoint_url") if llm_config else None) or llm_openai_url
                model_name = (llm_config.get("llm_model") if llm_config else None) or llm_openai_model
                
                logger.info(f"Initializing OpenAI provider with endpoint: {endpoint_url}")
                logger.info(f"Using model: {model_name}")
                logger.info(f"API key configured: {'Yes' if api_key else 'No'}")
                
                config = LLMConfig(
                    provider_id=LLMProviderType.OPENAI,
                    api_key=api_key,
                    default_model=model_name,
                    endpoint_url=endpoint_url,
                    max_tokens=4000,
                    temperature=0.1,
                    timeout_seconds=30
                )
                
                provider = OpenAIProvider(config)
                await provider.initialize()
                self._providers["openai"] = provider
                logger.info("Initialized OpenAI provider (Ollama) successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI provider: {e}")
        else:
            logger.warning("No OpenAI/Ollama configuration found - neither via llm_config nor environment variables")
        
        # TODO: Add other providers (Anthropic, Gemini) when configured
        
        self._initialized = True
        logger.info(f"Translation service initialized with {len(self._providers)} providers")
    
    async def translate_decompilation_result(
        self,
        decompilation_result: DecompilationResult,
        llm_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> DecompilationResult:
        """
        Translate a complete decompilation result using LLM providers.
        
        Args:
            decompilation_result: The original decompilation result
            llm_config: LLM configuration from API request
            context: Additional context for translation
            
        Returns:
            Enhanced decompilation result with LLM translations
        """
        if not self._initialized:
            await self.initialize(llm_config)
        
        if not self._providers:
            logger.warning("No LLM providers available for translation")
            return decompilation_result
        
        logger.info(f"Starting LLM translation for decompilation {decompilation_result.decompilation_id}")
        
        # Track overall translation metrics
        async with time_async_operation(
            OperationType.LLM_REQUEST,
            "complete_translation",
            decompilation_id=decompilation_result.decompilation_id,
            provider_count=len(self._providers)
        ):
            increment_counter("llm_translation_requests", 1)
            
            try:
                # Select provider based on configuration
                provider_id = llm_config.get("llm_provider", "openai")
                provider = self._providers.get(provider_id)
                
                if not provider:
                    logger.error(f"Requested provider '{provider_id}' not available")
                    return decompilation_result
                
                # Prepare translation context
                translation_context = self._prepare_translation_context(
                    decompilation_result, llm_config, context
                )
                
                # Translate functions (if any)
                translated_functions = []
                for func in decompilation_result.functions:
                    try:
                        function_data = {
                            "name": func.name,
                            "address": func.address,
                            "size": func.size,
                            "assembly_code": func.assembly_code,
                            "pseudocode": func.pseudocode
                        }
                        
                        translation = await provider.translate_function(
                            function_data=function_data,
                            context=translation_context
                        )
                        translated_functions.append(translation)
                        
                    except Exception as e:
                        logger.error(f"Failed to translate function {func.name}: {e}")
                        continue
                
                # TODO: Translate imports and strings when we have more data
                
                # Create enhanced result
                enhanced_result = decompilation_result.model_copy()
                
                # Add translation metadata
                if translated_functions:
                    # For now, store in a simple format - we'll enhance this later
                    enhanced_result.metadata = enhanced_result.metadata or {}
                    enhanced_result.metadata["llm_translations"] = {
                        "functions": [
                            {
                                "function_name": t.function_name,
                                "description": t.natural_language_description,
                                "confidence": t.confidence_score
                            }
                            for t in translated_functions
                        ],
                        "provider": provider_id,
                        "translation_time": datetime.utcnow().isoformat()
                    }
                
                logger.info(f"Completed LLM translation: {len(translated_functions)} functions translated")
                increment_counter("llm_translation_success", 1)
                return enhanced_result
                
            except Exception as e:
                logger.error(f"Translation failed: {e}")
                increment_counter("llm_translation_failures", 1)
                return decompilation_result
    
    def _prepare_translation_context(
        self,
        decompilation_result: DecompilationResult,
        llm_config: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare context information for LLM translation."""
        translation_context = {
            "binary_info": {
                "format": decompilation_result.binary_format,
                "architecture": decompilation_result.architecture,
                "file_size": decompilation_result.file_size_bytes
            },
            "analysis_summary": {
                "function_count": len(decompilation_result.functions),
                "import_count": len(decompilation_result.imports),
                "string_count": len(decompilation_result.strings)
            },
            "translation_settings": {
                "quality_level": llm_config.get("translation_detail", "standard"),
                "analysis_depth": llm_config.get("analysis_depth", "standard")
            }
        }
        
        # Add additional context if provided
        if context:
            translation_context.update(context)
        
        return translation_context
    
    async def get_available_providers(self) -> List[str]:
        """Get list of available LLM providers."""
        return list(self._providers.keys())
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all initialized providers."""
        if not self._initialized:
            return {"status": "not_initialized", "providers": {}}
        
        provider_health = {}
        for provider_id, provider in self._providers.items():
            try:
                health = await provider.health_check()
                provider_health[provider_id] = {
                    "healthy": health.is_healthy,
                    "response_time_ms": health.api_latency_ms
                }
            except Exception as e:
                provider_health[provider_id] = {
                    "healthy": False,
                    "error": str(e)
                }
        
        healthy_count = sum(1 for h in provider_health.values() if h.get("healthy", False))
        
        return {
            "status": "healthy" if healthy_count > 0 else "degraded",
            "total_providers": len(self._providers),
            "healthy_providers": healthy_count,
            "providers": provider_health
        }


# Global instance
_translation_service = TranslationServiceOrchestrator()


async def get_translation_service() -> TranslationServiceOrchestrator:
    """Get the global translation service instance."""
    return _translation_service