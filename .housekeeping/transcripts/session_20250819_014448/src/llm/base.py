"""
Base LLM Provider Interface

Abstract base class and configuration models for multi-LLM provider integration.
Defines the unified interface that all provider implementations must follow.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr, field_validator, ConfigDict
import httpx

from ..core.exceptions import BinaryAnalysisException
from ..core.metrics import time_async_operation, OperationType, increment_counter
from ..core.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
from ..models.decompilation.results import (
    FunctionTranslation, 
    ImportTranslation, 
    StringTranslation, 
    OverallSummary,
    LLMProviderMetadata
)


class LLMProviderType(str, Enum):
    """Supported LLM provider types."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    GEMINI = "gemini"


class TranslationOperationType(str, Enum):
    """Types of translation operations."""
    FUNCTION_TRANSLATION = "function_translation"
    IMPORT_EXPLANATION = "import_explanation"
    STRING_INTERPRETATION = "string_interpretation"
    OVERALL_SUMMARY = "overall_summary"


class LLMProviderException(BinaryAnalysisException):
    """Base exception for LLM provider errors."""
    
    def __init__(self, message: str, provider_id: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.provider_id = provider_id
        self.error_code = error_code
        self.timestamp = datetime.utcnow()


class LLMRateLimitException(LLMProviderException):
    """Raised when provider rate limits are exceeded."""
    
    def __init__(self, provider_id: str, retry_after: Optional[int] = None):
        super().__init__(f"Rate limit exceeded for {provider_id}", provider_id, "RATE_LIMIT")
        self.retry_after = retry_after


class LLMCostLimitException(LLMProviderException):
    """Raised when user cost limits would be exceeded."""
    
    def __init__(self, provider_id: str, estimated_cost: float, limit: float):
        super().__init__(
            f"Cost limit would be exceeded: ${estimated_cost:.2f} > ${limit:.2f}",
            provider_id,
            "COST_LIMIT"
        )
        self.estimated_cost = estimated_cost
        self.limit = limit


class LLMAuthenticationException(LLMProviderException):
    """Raised when API authentication fails."""
    
    def __init__(self, provider_id: str, details: Optional[str] = None):
        message = f"Authentication failed for {provider_id}"
        if details:
            message += f": {details}"
        super().__init__(message, provider_id, "AUTH_FAILED")


class LLMServiceUnavailableException(LLMProviderException):
    """Raised when LLM service is unavailable."""
    
    def __init__(self, provider_id: str, details: Optional[str] = None):
        message = f"Service unavailable for {provider_id}"
        if details:
            message += f": {details}"
        super().__init__(message, provider_id, "SERVICE_UNAVAILABLE")


class LLMConfig(BaseModel):
    """
    Configuration for LLM provider integration.
    
    Contains provider-specific settings, API credentials, and usage limits.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "provider_id": "openai",
                    "api_key": "sk-...",
                    "default_model": "gpt-4",
                    "endpoint_url": None,
                    "temperature": 0.1,
                    "max_tokens": 2048,
                    "timeout_seconds": 30,
                    "daily_spend_limit": 100.0,
                    "monthly_spend_limit": 1000.0
                }
            ]
        }
    )
    
    provider_id: LLMProviderType = Field(
        description="LLM provider identifier"
    )
    
    api_key: SecretStr = Field(
        description="API key for authentication"
    )
    
    default_model: str = Field(
        description="Default model to use for translations"
    )
    
    endpoint_url: Optional[str] = Field(
        default=None,
        description="Custom API endpoint URL (for OpenAI-compatible providers)"
    )
    
    organization: Optional[str] = Field(
        default=None,
        description="Organization ID (OpenAI specific)"
    )
    
    # Model parameters
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for text generation"
    )
    
    max_tokens: int = Field(
        default=2048,
        ge=100,
        le=8192,
        description="Maximum tokens for response generation"
    )
    
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout in seconds"
    )
    
    # Rate limiting
    requests_per_minute: int = Field(
        default=60,
        ge=1,
        le=10000,
        description="Maximum requests per minute"
    )
    
    tokens_per_minute: int = Field(
        default=40000,
        ge=1000,
        le=500000,
        description="Maximum tokens per minute"
    )
    
    # Cost controls
    daily_spend_limit: float = Field(
        default=100.0,
        ge=0.0,
        description="Daily spending limit in USD"
    )
    
    monthly_spend_limit: float = Field(
        default=1000.0,
        ge=0.0,
        description="Monthly spending limit in USD"
    )
    
    cost_alert_thresholds: List[float] = Field(
        default=[25.0, 50.0, 75.0],
        description="Cost alert thresholds as percentages of limits"
    )
    
    # Provider-specific settings
    provider_specific: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration options"
    )
    
    @field_validator('endpoint_url')
    @classmethod
    def validate_endpoint_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate endpoint URL format."""
        if v is None:
            return v
            
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Endpoint URL must start with http:// or https://")
        
        return v
    
    @field_validator('cost_alert_thresholds')
    @classmethod
    def validate_thresholds(cls, v: List[float]) -> List[float]:
        """Validate cost alert thresholds."""
        if not v:
            return []
        
        # Ensure all values are between 0 and 100
        for threshold in v:
            if not (0.0 <= threshold <= 100.0):
                raise ValueError("Cost alert thresholds must be between 0 and 100")
        
        # Sort and remove duplicates
        return sorted(list(set(v)))


class ProviderHealthStatus(BaseModel):
    """Health status information for an LLM provider."""
    
    provider_id: str = Field(description="Provider identifier")
    is_healthy: bool = Field(description="Whether provider is healthy")
    within_rate_limits: bool = Field(description="Whether within rate limits")
    api_latency_ms: Optional[float] = Field(default=None, description="API latency in milliseconds")
    cost_per_token: Optional[float] = Field(default=None, description="Current cost per token")
    available_models: List[str] = Field(default_factory=list, description="Available models")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="Last health check timestamp")
    error_message: Optional[str] = Field(default=None, description="Error message if unhealthy")


class TranslationRequest(BaseModel):
    """Request for LLM translation operation."""
    
    operation_type: TranslationOperationType = Field(description="Type of translation operation")
    content: str = Field(description="Content to translate")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context for translation")
    model_override: Optional[str] = Field(default=None, description="Override default model")
    temperature_override: Optional[float] = Field(default=None, description="Override default temperature")
    max_tokens_override: Optional[int] = Field(default=None, description="Override default max tokens")


class TranslationResponse(BaseModel):
    """Response from LLM translation operation."""
    
    request_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique request identifier")
    success: bool = Field(description="Whether translation succeeded")
    result: Optional[Union[FunctionTranslation, ImportTranslation, StringTranslation, OverallSummary]] = Field(
        default=None, 
        description="Translation result"
    )
    provider_metadata: LLMProviderMetadata = Field(description="Provider metadata")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    processing_time_ms: int = Field(description="Total processing time in milliseconds")


class LLMProvider(ABC):
    """
    Abstract base class for all LLM provider implementations.
    
    Defines the unified interface that all providers must implement for
    binary decompilation translation tasks.
    """
    
    def __init__(self, config: LLMConfig):
        """Initialize the provider with configuration."""
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        self._last_health_check: Optional[ProviderHealthStatus] = None
        
        # Initialize circuit breaker for this provider
        circuit_config = CircuitBreakerConfig(
            failure_threshold=3,  # Open circuit after 3 failures
            success_threshold=2,  # Close circuit after 2 successes in half-open
            timeout_seconds=30.0, # Try half-open after 30 seconds
            health_check_interval=60.0,  # Health check every minute
            health_check_timeout=10.0    # 10 second health check timeout
        )
        self.circuit_breaker = get_circuit_breaker(
            name=f"llm_provider_{self.get_provider_id()}",
            config=circuit_config,
            health_check_func=self._circuit_health_check
        )
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider and its HTTP client."""
        pass
    
    async def _circuit_health_check(self) -> bool:
        """
        Circuit breaker health check - calls provider health_check and returns bool.
        
        Returns:
            True if provider is healthy, False otherwise
        """
        try:
            health_status = await self.health_check()
            return health_status.is_healthy and health_status.within_rate_limits
        except Exception:
            return False
    
    async def _protected_call(self, operation_name: str, func, *args, **kwargs):
        """
        Execute LLM provider operation with circuit breaker protection.
        
        Args:
            operation_name: Name of the operation for logging
            func: The function to call
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            Result of the function call
            
        Raises:
            CircuitBreakerException: If circuit breaker is open
            LLMProviderException: If the operation fails
        """
        async with self.circuit_breaker.call():
            return await func(*args, **kwargs)
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup provider resources and connections."""
        pass
    
    @abstractmethod
    async def translate_function(
        self, 
        function_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> FunctionTranslation:
        """
        Translate assembly function to natural language explanation.
        
        Args:
            function_data: Dictionary containing function information
                - name: Function name
                - address: Memory address
                - size: Function size in bytes
                - assembly_code: Assembly code
                - decompiled_code: Pseudo-C code if available
                - calls_to: List of called functions
                - variables: List of variables/parameters
            context: Additional context for translation
                - file_info: File metadata
                - imports: List of imports
                - strings: List of strings
                - other_functions: Information about other functions
        
        Returns:
            FunctionTranslation object with natural language explanation
            
        Raises:
            LLMProviderException: On translation failure
        """
        pass
    
    @abstractmethod
    async def explain_imports(
        self, 
        import_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ImportTranslation]:
        """
        Explain purpose and usage of imported functions.
        
        Args:
            import_list: List of import dictionaries
                - library: Library name (DLL, SO, etc.)
                - function: Function name
                - address: Import address if available
                - ordinal: Ordinal number if applicable
            context: Additional context for analysis
                - file_info: File metadata
                - usage_patterns: How imports are used
        
        Returns:
            List of ImportTranslation objects with explanations
            
        Raises:
            LLMProviderException: On translation failure
        """
        pass
    
    @abstractmethod
    async def interpret_strings(
        self, 
        string_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[StringTranslation]:
        """
        Interpret extracted strings with usage context.
        
        Args:
            string_list: List of string dictionaries
                - content: String content
                - address: Memory address
                - size: String size
                - encoding: Character encoding
                - context: Usage context if available
            context: Additional context for interpretation
                - file_info: File metadata
                - function_references: Functions that use the strings
        
        Returns:
            List of StringTranslation objects with interpretations
            
        Raises:
            LLMProviderException: On translation failure
        """
        pass
    
    @abstractmethod
    async def generate_overall_summary(
        self, 
        decompilation_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> OverallSummary:
        """
        Generate comprehensive program summary.
        
        Args:
            decompilation_data: Complete decompilation information
                - file_info: File metadata
                - functions: Function information
                - imports: Import information
                - strings: String information
                - analysis_results: Any additional analysis
            context: Additional context for summary
                - user_focus: Areas of particular interest
                - security_emphasis: Whether to emphasize security analysis
        
        Returns:
            OverallSummary object with program analysis
            
        Raises:
            LLMProviderException: On translation failure
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> ProviderHealthStatus:
        """
        Check provider availability and API status.
        
        Returns:
            ProviderHealthStatus with current health information
        """
        pass
    
    @abstractmethod
    def get_cost_estimate(self, token_count: int, operation_type: TranslationOperationType) -> float:
        """
        Calculate estimated cost for given token count and operation.
        
        Args:
            token_count: Number of tokens to process
            operation_type: Type of translation operation
            
        Returns:
            Estimated cost in USD
        """
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in given text using provider's tokenization.
        
        Args:
            text: Text to tokenize
            
        Returns:
            Number of tokens
        """
        pass
    
    def get_provider_id(self) -> str:
        """Get provider identifier."""
        return self.config.provider_id
    
    def get_default_model(self) -> str:
        """Get default model name."""
        return self.config.default_model
    
    def is_within_rate_limits(self) -> bool:
        """Check if provider is within rate limits."""
        if self._last_health_check:
            return self._last_health_check.within_rate_limits
        return True  # Assume okay if no health check data
    
    def get_last_health_status(self) -> Optional[ProviderHealthStatus]:
        """Get last health check status."""
        return self._last_health_check
    
    async def validate_request(self, request: TranslationRequest) -> None:
        """
        Validate translation request before processing.
        
        Args:
            request: Translation request to validate
            
        Raises:
            LLMProviderException: If request is invalid
        """
        if not request.content or not request.content.strip():
            raise LLMProviderException("Empty content for translation", self.get_provider_id(), "INVALID_REQUEST")
        
        # Estimate token count and cost
        token_count = self.count_tokens(request.content)
        estimated_cost = self.get_cost_estimate(token_count, request.operation_type)
        
        # Check cost limits (simplified - in practice would check against usage tracker)
        if estimated_cost > self.config.daily_spend_limit:
            raise LLMCostLimitException(
                self.get_provider_id(),
                estimated_cost,
                self.config.daily_spend_limit
            )
    
    def _create_provider_metadata(
        self, 
        model: str, 
        tokens_used: int, 
        processing_time_ms: int,
        cost_estimate: Optional[float] = None
    ) -> LLMProviderMetadata:
        """Create provider metadata object."""
        return LLMProviderMetadata(
            provider=self.get_provider_id(),
            model=model,
            tokens_used=tokens_used,
            processing_time_ms=processing_time_ms,
            api_version=None,  # Override in specific providers
            custom_endpoint=self.config.endpoint_url,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            cost_estimate_usd=cost_estimate
        )