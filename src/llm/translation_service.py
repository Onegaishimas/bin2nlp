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
        # No persistent providers - create on demand from request parameters
    
    def _create_provider_from_config(self, llm_config: Dict[str, Any]):
        """Create a provider instance from request configuration."""
        provider_id = llm_config.get("llm_provider", "openai")
        
        # Get required parameters from request
        api_key = llm_config.get("llm_api_key")
        endpoint_url = llm_config.get("llm_endpoint_url")
        model_name = llm_config.get("llm_model")
        
        # Fall back to environment defaults if not provided in request
        if not api_key or not endpoint_url or not model_name:
            from ..core.config import get_settings
            import os
            
            try:
                settings = get_settings()
                api_key = api_key or (settings.llm.openai_api_key.get_secret_value() if settings.llm.openai_api_key else None)
                endpoint_url = endpoint_url or settings.llm.openai_base_url
                model_name = model_name or settings.llm.openai_default_model
            except Exception:
                # Fallback to environment variables
                api_key = api_key or os.getenv("LLM_OPENAI_API_KEY")
                endpoint_url = endpoint_url or os.getenv("LLM_OPENAI_BASE_URL")
                model_name = model_name or os.getenv("LLM_OPENAI_DEFAULT_MODEL")
        
        if not all([api_key, endpoint_url, model_name]):
            raise ValueError(f"Missing required LLM configuration: api_key={bool(api_key)}, endpoint_url={bool(endpoint_url)}, model={bool(model_name)}")
        
        logger.info(f"Creating {provider_id} provider with endpoint: {endpoint_url}, model: {model_name}")
        
        # Create provider configuration
        if provider_id == "openai":
            config = LLMConfig(
                provider_id=LLMProviderType.OPENAI,
                api_key=api_key,
                default_model=model_name,
                endpoint_url=endpoint_url,
                max_tokens=4000,
                temperature=0.1,
                timeout_seconds=30
            )
            return OpenAIProvider(config)
        elif provider_id == "anthropic":
            config = LLMConfig(
                provider_id=LLMProviderType.ANTHROPIC,
                api_key=api_key,
                default_model=model_name,
                endpoint_url=endpoint_url,
                max_tokens=4000,
                temperature=0.1,
                timeout_seconds=30
            )
            return AnthropicProvider(config)
        elif provider_id == "gemini":
            config = LLMConfig(
                provider_id=LLMProviderType.GEMINI,
                api_key=api_key,
                default_model=model_name,
                endpoint_url=endpoint_url,
                max_tokens=4000,
                temperature=0.1,
                timeout_seconds=30
            )
            return GeminiProvider(config)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_id}")
    
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
        # Create provider on-demand from request configuration
        if not llm_config or not llm_config.get("llm_provider"):
            logger.warning("No LLM provider specified in request")
            return decompilation_result
        
        logger.info(f"Starting LLM translation for decompilation {decompilation_result.decompilation_id}")
        
        # Track overall translation metrics
        async with time_async_operation(
            OperationType.LLM_REQUEST,
            "complete_translation",
            decompilation_id=decompilation_result.decompilation_id,
            provider_count=1  # Single on-demand provider per request
        ):
            increment_counter("llm_translation_requests", 1)
            
            try:
                # Create provider from request configuration
                provider = self._create_provider_from_config(llm_config)
                await provider.initialize()
                provider_id = llm_config.get("llm_provider")
                
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
                            "pseudocode": getattr(func, 'pseudocode', None),
                            "decompiled_code": getattr(func, 'decompiled_code', None),
                            "calls_to": getattr(func, 'calls_to', []),
                            "calls_from": getattr(func, 'calls_from', []),
                            "variables": getattr(func, 'variables', []),
                            "imports_used": getattr(func, 'imports_used', []),
                            "strings_referenced": getattr(func, 'strings_referenced', [])
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
                
                # Return both the original result and the translation data separately
                logger.info(f"Completed LLM translation: {len(translated_functions)} functions translated")
                increment_counter("llm_translation_success", 1)
                
                # Store translation data for return
                if translated_functions:
                    translation_data = {
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
                    logger.info(f"Created translation data with {len(translation_data['functions'])} functions")
                    # Return a tuple: (decompilation_result, translation_data)
                    return decompilation_result, translation_data
                else:
                    logger.warning("No translated functions to return")
                    return decompilation_result, None
                
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
                "format": getattr(decompilation_result, 'binary_format', 'Unknown'),
                "architecture": getattr(decompilation_result, 'architecture', 'Unknown'), 
                "file_size": getattr(decompilation_result, 'file_size_bytes', 0)
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
        """Get list of supported LLM providers."""
        return ["openai", "anthropic", "gemini"]
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of translation service (providers created on-demand)."""
        return {
            "status": "healthy",
            "message": "Translation service ready - providers created on-demand from requests",
            "supported_providers": ["openai", "anthropic", "gemini"]
        }


# Global instance
_translation_service = TranslationServiceOrchestrator()


async def get_translation_service() -> TranslationServiceOrchestrator:
    """Get the global translation service instance."""
    return _translation_service