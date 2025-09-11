"""
Ollama Provider Implementation

Dedicated provider for Ollama local LLM instances using OpenAI-compatible API.
Optimized for local deployment with appropriate defaults and error handling.
"""

import asyncio
import json
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx
from openai import AsyncOpenAI, APIError, RateLimitError, AuthenticationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..base import (
    LLMProvider, 
    LLMConfig, 
    LLMProviderException, 
    LLMRateLimitException, 
    LLMAuthenticationException,
    LLMServiceUnavailableException,
    ProviderHealthStatus,
    TranslationOperationType
)
from ...core.metrics import time_async_operation, OperationType, increment_counter
from ...models.decompilation.results import (
    FunctionTranslation, 
    ImportTranslation, 
    StringTranslation, 
    OverallSummary,
    LLMProviderMetadata
)


class OllamaProvider(LLMProvider):
    """
    Ollama provider implementation for local LLM inference.
    
    Provides optimized defaults for local Ollama deployment with appropriate
    timeouts, error handling, and cost considerations (free local inference).
    """
    
    # Default models commonly available in Ollama
    DEFAULT_MODELS = {
        "code": "codellama:7b",
        "analysis": "llama3.1:8b", 
        "explanation": "llama3.1:8b",
        "summary": "llama3.1:8b",
        "fallback": "llama3.2:3b"
    }
    
    # Common Ollama endpoints
    DEFAULT_ENDPOINTS = {
        "local": "http://localhost:11434/v1",
        "docker": "http://ollama:11434/v1"
    }
    
    def __init__(self, config: LLMConfig):
        """Initialize Ollama provider with configuration."""
        super().__init__(config)
        self.openai_client: Optional[AsyncOpenAI] = None
        self._available_models: List[str] = []
        self._token_count_cache: Dict[str, int] = {}
        
        # Set Ollama-specific defaults if not provided
        if not config.endpoint_url:
            config.endpoint_url = self.DEFAULT_ENDPOINTS["local"]
            
        # Ollama doesn't require API keys, use placeholder if empty
        if not config.api_key.get_secret_value() or config.api_key.get_secret_value() == "":
            from pydantic import SecretStr
            config.api_key = SecretStr("ollama-no-auth-required")
    
    async def initialize(self) -> None:
        """Initialize the Ollama client and discover available models."""
        try:
            # Initialize OpenAI-compatible client for Ollama
            self.openai_client = AsyncOpenAI(
                api_key=self.config.api_key.get_secret_value(),
                base_url=self.config.endpoint_url,
                timeout=self.config.timeout_seconds,
                max_retries=2,  # Fewer retries for local server
            )
            
            # Discover available models
            await self._discover_models()
            
            increment_counter("ollama_provider_initialized")
            
        except Exception as e:
            raise LLMProviderException(
                f"Failed to initialize Ollama provider: {str(e)}",
                "ollama",
                "INITIALIZATION_FAILED"
            )
    
    async def cleanup(self) -> None:
        """Cleanup Ollama provider resources."""
        if self.openai_client:
            await self.openai_client.close()
        self._available_models.clear()
        self._token_count_cache.clear()
    
    async def _discover_models(self) -> None:
        """Discover available models from Ollama instance."""
        try:
            # Try to get models list from Ollama
            models_response = await self.openai_client.models.list()
            self._available_models = [model.id for model in models_response.data]
            
            # If no models found, use common defaults
            if not self._available_models:
                self._available_models = list(self.DEFAULT_MODELS.values())
                
        except Exception as e:
            # Fall back to default models if discovery fails
            self._available_models = list(self.DEFAULT_MODELS.values())
            # Don't raise error - this is non-critical
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((APIError, httpx.RequestError))
    )
    async def translate_function(
        self, 
        function_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> FunctionTranslation:
        """Translate assembly function using Ollama."""
        
        start_time = time.time()
        
        try:
            # Select best model for code analysis
            model = self._select_model_for_task("code")
            
            # Build prompt for function translation
            prompt = self._build_function_prompt(function_data, context)
            
            # Make API call with circuit breaker protection
            response = await self._protected_call(
                "translate_function",
                self._make_completion_request,
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert reverse engineer analyzing binary code. Provide clear, detailed explanations of assembly code functionality."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            # Parse response into structured format
            result = self._parse_function_response(response, function_data)
            
            increment_counter("ollama_function_translation_success")
            
            return result
            
        except Exception as e:
            increment_counter("ollama_function_translation_error") 
            raise LLMProviderException(
                f"Function translation failed: {str(e)}",
                "ollama",
                "TRANSLATION_FAILED"
            )
    
    async def explain_imports(
        self, 
        import_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ImportTranslation]:
        """Explain imports using Ollama."""
        
        if not import_list:
            return []
        
        try:
            model = self._select_model_for_task("analysis")
            
            results = []
            for import_data in import_list:
                prompt = self._build_import_prompt(import_data, context)
                
                response = await self._protected_call(
                    "explain_import",
                    self._make_completion_request,
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an expert in Windows/Linux API analysis. Explain what imported functions do and their security implications."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=512  # Shorter responses for imports
                )
                
                result = self._parse_import_response(response, import_data)
                results.append(result)
            
            increment_counter("ollama_import_explanation_success")
            return results
            
        except Exception as e:
            increment_counter("ollama_import_explanation_error")
            raise LLMProviderException(
                f"Import explanation failed: {str(e)}",
                "ollama", 
                "EXPLANATION_FAILED"
            )
    
    async def interpret_strings(
        self, 
        string_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[StringTranslation]:
        """Interpret strings using Ollama."""
        
        if not string_list:
            return []
        
        try:
            model = self._select_model_for_task("analysis")
            
            results = []
            for string_data in string_list:
                prompt = self._build_string_prompt(string_data, context)
                
                response = await self._protected_call(
                    "interpret_string",
                    self._make_completion_request,
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are analyzing strings found in binary files. Explain their likely purpose and context."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.config.temperature,
                    max_tokens=256  # Short responses for strings
                )
                
                result = self._parse_string_response(response, string_data)
                results.append(result)
            
            increment_counter("ollama_string_interpretation_success")
            return results
            
        except Exception as e:
            increment_counter("ollama_string_interpretation_error")
            raise LLMProviderException(
                f"String interpretation failed: {str(e)}",
                "ollama",
                "INTERPRETATION_FAILED"
            )
    
    async def generate_overall_summary(
        self, 
        decompilation_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> OverallSummary:
        """Generate comprehensive summary using Ollama."""
        
        try:
            model = self._select_model_for_task("summary")
            
            prompt = self._build_summary_prompt(decompilation_data, context)
            
            response = await self._protected_call(
                "generate_summary",
                self._make_completion_request,
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert malware analyst. Provide a comprehensive summary of binary analysis results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            result = self._parse_summary_response(response, decompilation_data)
            
            increment_counter("ollama_summary_generation_success")
            return result
            
        except Exception as e:
            increment_counter("ollama_summary_generation_error")
            raise LLMProviderException(
                f"Summary generation failed: {str(e)}",
                "ollama",
                "SUMMARY_FAILED"
            )
    
    async def health_check(self) -> ProviderHealthStatus:
        """Check Ollama service health and available models."""
        
        start_time = time.time()
        
        try:
            # Test basic connectivity
            models_response = await self.openai_client.models.list()
            available_models = [model.id for model in models_response.data]
            
            # Test a simple completion to verify functionality
            try:
                test_response = await self.openai_client.chat.completions.create(
                    model=available_models[0] if available_models else "llama3.2:3b",
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=10,
                    timeout=5.0
                )
                is_functional = bool(test_response.choices)
            except Exception:
                is_functional = False
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ProviderHealthStatus(
                provider_id="ollama",
                is_healthy=is_functional and len(available_models) > 0,
                within_rate_limits=True,  # No rate limits for local Ollama
                api_latency_ms=latency_ms,
                cost_per_token=0.0,  # Free local inference
                available_models=available_models,
                last_check=datetime.utcnow(),
                error_message=None if is_functional else "Ollama service not responding properly"
            )
            
        except Exception as e:
            return ProviderHealthStatus(
                provider_id="ollama",
                is_healthy=False,
                within_rate_limits=False,
                api_latency_ms=None,
                cost_per_token=0.0,
                available_models=[],
                last_check=datetime.utcnow(),
                error_message=f"Ollama health check failed: {str(e)}"
            )
    
    def get_cost_estimate(self, token_count: int, operation_type: TranslationOperationType) -> float:
        """Ollama is free - always return 0."""
        return 0.0
    
    def count_tokens(self, text: str) -> int:
        """Estimate tokens for Ollama (similar to GPT tokenization)."""
        # Simple approximation: ~4 characters per token
        # Cache results for performance
        if text in self._token_count_cache:
            return self._token_count_cache[text]
        
        # Rough estimate based on text length
        token_count = max(1, len(text) // 4)
        
        # Cache result (limit cache size)
        if len(self._token_count_cache) < 1000:
            self._token_count_cache[text] = token_count
        
        return token_count
    
    def _select_model_for_task(self, task_type: str) -> str:
        """Select appropriate model based on task type."""
        if not self._available_models:
            return self.config.default_model
        
        # Try task-specific model first
        preferred_model = self.DEFAULT_MODELS.get(task_type)
        if preferred_model and preferred_model in self._available_models:
            return preferred_model
        
        # Fall back to configured default
        if self.config.default_model in self._available_models:
            return self.config.default_model
        
        # Fall back to first available model
        return self._available_models[0]
    
    async def _make_completion_request(self, **kwargs) -> Any:
        """Make a chat completion request to Ollama."""
        return await self.openai_client.chat.completions.create(**kwargs)
    
    def _build_function_prompt(self, function_data: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """Build prompt for function analysis."""
        name = function_data.get("name", "unknown")
        address = function_data.get("address", "unknown")
        assembly_code = function_data.get("assembly_code", "")
        
        prompt = f"""Analyze this assembly function and explain what it does:

Function: {name}
Address: {address}
Size: {function_data.get('size', 0)} bytes

Assembly Code:
{assembly_code[:2000]}  # Limit to prevent token overflow

Please provide:
1. A clear explanation of what this function does
2. Key operations and logic flow
3. Any notable patterns or behaviors
4. Potential purpose or role in the program

Keep the explanation technical but accessible."""
        
        return prompt
    
    def _build_import_prompt(self, import_data: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """Build prompt for import analysis."""
        library = import_data.get("library_name", "unknown")
        function = import_data.get("function_name", "unknown")
        
        return f"""Explain this imported function:

Library: {library}
Function: {function}

Please provide:
1. What this function does
2. Common use cases
3. Any security implications
4. Whether it's commonly used in malware

Keep it concise but informative."""
    
    def _build_string_prompt(self, string_data: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """Build prompt for string analysis."""
        content = string_data.get("value", "")
        
        return f"""Analyze this string found in a binary:

String: "{content}"
Size: {string_data.get('size', 0)} bytes

What might this string be used for? Consider:
1. Configuration data
2. Error messages
3. File paths
4. Network resources
5. Other purposes

Provide a brief analysis."""
    
    def _build_summary_prompt(self, decompilation_data: Dict[str, Any], context: Optional[Dict[str, Any]]) -> str:
        """Build prompt for overall summary."""
        file_info = decompilation_data.get("file_info", {})
        functions = decompilation_data.get("functions", [])
        imports = decompilation_data.get("imports", [])
        
        return f"""Analyze this binary and provide a comprehensive summary:

File Information:
- Format: {file_info.get('format', 'unknown')}
- Size: {file_info.get('size', 0)} bytes
- Functions: {len(functions)}
- Imports: {len(imports)}

Based on the decompilation data, provide:
1. Overall purpose and behavior
2. Key functionality
3. Notable patterns
4. Potential classification
5. Security assessment

Focus on high-level insights."""
    
    def _parse_function_response(self, response: Any, function_data: Dict[str, Any]) -> FunctionTranslation:
        """Parse Ollama response into FunctionTranslation."""
        explanation = response.choices[0].message.content if response.choices else "Translation unavailable"
        
        # Create provider metadata
        provider_metadata = LLMProviderMetadata(
            provider="ollama",
            model=self.config.default_model,
            tokens_used=self._estimate_tokens(explanation),
            processing_time_ms=100,  # Approximate for local inference
            api_version="v1",
            cost_estimate=0.0,  # Free local inference
            timestamp=datetime.utcnow()
        )
        
        return FunctionTranslation(
            function_name=function_data.get("name", "unknown"),
            address=function_data.get("address", "0x0"),
            size=function_data.get("size", 0),
            assembly_code=function_data.get("assembly_code"),
            natural_language_description=explanation,
            parameters_explanation="",  # Optional field
            return_value_explanation="",  # Optional field
            security_analysis="",  # Optional field
            confidence_score=0.8,  # Default confidence for local model
            llm_provider=provider_metadata
        )
    
    def _parse_import_response(self, response: Any, import_data: Dict[str, Any]) -> ImportTranslation:
        """Parse Ollama response into ImportTranslation."""
        explanation = response.choices[0].message.content if response.choices else "Explanation unavailable"
        
        return ImportTranslation(
            library_name=import_data.get("library_name", "unknown"),
            function_name=import_data.get("function_name", "unknown"),
            purpose_explanation=explanation,
            common_use_cases=[],
            security_implications="",
            risk_level="unknown"
        )
    
    def _parse_string_response(self, response: Any, string_data: Dict[str, Any]) -> StringTranslation:
        """Parse Ollama response into StringTranslation."""
        interpretation = response.choices[0].message.content if response.choices else "Interpretation unavailable"
        
        return StringTranslation(
            string_content=string_data.get("value", ""),
            string_address=string_data.get("address", "unknown"),
            interpretation=interpretation,
            likely_purpose="unknown",
            encoding_info=string_data.get("encoding", "ascii"),
            context_references=[]
        )
    
    def _parse_summary_response(self, response: Any, decompilation_data: Dict[str, Any]) -> OverallSummary:
        """Parse Ollama response into OverallSummary."""
        summary_text = response.choices[0].message.content if response.choices else "Summary unavailable"
        
        return OverallSummary(
            executive_summary=summary_text,
            technical_analysis="",
            behavior_analysis="", 
            security_assessment="",
            recommendations=[],
            confidence_score=0.8
        )
    
    def _estimate_tokens(self, text: str) -> int:
        """Quick token estimation for metrics."""
        return max(1, len(text) // 4)