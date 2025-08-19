"""
LLM Provider Factory

Factory class for creating, managing, and selecting LLM providers with fallback logic,
load balancing, and intelligent provider selection based on cost, performance, and availability.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from ..base import (
    LLMProvider,
    LLMConfig,
    LLMProviderType,
    LLMProviderException,
    ProviderHealthStatus,
    TranslationOperationType
)
from ...core.logging import get_logger
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider

logger = get_logger(__name__)


@dataclass
class ProviderStats:
    """Statistics and metrics for a provider."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    average_latency_ms: float = 0.0
    last_used: Optional[datetime] = None
    consecutive_failures: int = 0
    health_check_failures: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        return 100.0 - self.success_rate
    
    @property
    def is_healthy(self) -> bool:
        """Check if provider appears healthy based on stats."""
        return (
            self.consecutive_failures < 5 and 
            self.health_check_failures < 3 and
            self.success_rate >= 80.0
        )


@dataclass 
class ProviderPreferences:
    """User preferences for LLM provider selection."""
    preferred_provider: Optional[str] = None
    cost_optimization: bool = False
    performance_priority: bool = False
    fallback_enabled: bool = True
    max_cost_per_request: Optional[float] = None
    excluded_providers: List[str] = field(default_factory=list)
    operation_preferences: Dict[str, str] = field(default_factory=dict)  # operation_type -> preferred_provider


class AllProvidersUnavailableException(LLMProviderException):
    """Raised when all configured providers are unavailable."""
    
    def __init__(self, provider_count: int, last_errors: Dict[str, str]):
        super().__init__(
            f"All {provider_count} configured LLM providers are unavailable",
            "factory",
            "ALL_PROVIDERS_DOWN"
        )
        self.provider_count = provider_count
        self.last_errors = last_errors


class LLMProviderFactory:
    """
    Factory for creating and managing LLM provider instances with intelligent
    selection, failover, load balancing, and cost optimization.
    """
    
    # Provider class mappings
    PROVIDER_CLASSES = {
        LLMProviderType.OPENAI: OpenAIProvider,
        LLMProviderType.ANTHROPIC: AnthropicProvider,
        LLMProviderType.GEMINI: GeminiProvider
    }
    
    def __init__(self):
        """Initialize the provider factory."""
        self.providers: Dict[str, LLMProvider] = {}
        self.provider_configs: Dict[str, LLMConfig] = {}
        self.provider_stats: Dict[str, ProviderStats] = {}
        self._last_health_checks: Dict[str, ProviderHealthStatus] = {}
        self._health_check_interval = timedelta(minutes=5)
        self._circuit_breaker_timeout = timedelta(minutes=10)
        
    async def initialize(self) -> None:
        """Initialize factory and perform initial health checks."""
        logger.info(f"Initializing LLM provider factory with {len(self.providers)} providers")
        
        # Perform initial health checks for all providers
        await self._perform_health_checks()
        
        logger.info(f"Factory initialization complete. Healthy providers: {len(self.get_healthy_providers())}")
    
    async def cleanup(self) -> None:
        """Cleanup all provider resources."""
        logger.info("Cleaning up LLM provider factory")
        
        for provider in self.providers.values():
            try:
                await provider.cleanup()
            except Exception as e:
                logger.warning(f"Error cleaning up provider {provider.get_provider_id()}: {e}")
        
        self.providers.clear()
        self.provider_configs.clear()
        self._last_health_checks.clear()
    
    def add_provider(self, config: LLMConfig) -> None:
        """Add a provider configuration to the factory."""
        provider_id = config.provider_id
        
        if provider_id not in self.PROVIDER_CLASSES:
            raise ValueError(f"Unsupported provider type: {provider_id}")
        
        # Store configuration
        self.provider_configs[provider_id] = config
        
        # Initialize stats if not exists
        if provider_id not in self.provider_stats:
            self.provider_stats[provider_id] = ProviderStats()
        
        logger.info(f"Added provider configuration: {provider_id}")
    
    async def get_provider(
        self, 
        provider_id: Optional[str] = None,
        operation_type: Optional[TranslationOperationType] = None,
        preferences: Optional[ProviderPreferences] = None
    ) -> LLMProvider:
        """
        Get a provider instance with intelligent selection.
        
        Args:
            provider_id: Specific provider to use (bypasses selection logic)
            operation_type: Type of operation for optimized provider selection
            preferences: User preferences for provider selection
            
        Returns:
            LLM provider instance ready for use
            
        Raises:
            AllProvidersUnavailableException: If no providers are available
            LLMProviderException: If provider creation fails
        """
        if provider_id:
            return await self._get_specific_provider(provider_id)
        
        return await self._select_optimal_provider(operation_type, preferences or ProviderPreferences())
    
    async def _get_specific_provider(self, provider_id: str) -> LLMProvider:
        """Get a specific provider by ID."""
        if provider_id not in self.provider_configs:
            raise LLMProviderException(f"Provider {provider_id} not configured", "factory", "PROVIDER_NOT_FOUND")
        
        # Check if provider instance exists and is healthy
        if provider_id in self.providers:
            provider = self.providers[provider_id]
            
            # Check circuit breaker status
            if self._is_circuit_breaker_open(provider_id):
                raise LLMProviderException(
                    f"Provider {provider_id} circuit breaker is open",
                    "factory",
                    "CIRCUIT_BREAKER_OPEN"
                )
            
            return provider
        
        # Create new provider instance
        return await self._create_provider(provider_id)
    
    async def _select_optimal_provider(
        self, 
        operation_type: Optional[TranslationOperationType],
        preferences: ProviderPreferences
    ) -> LLMProvider:
        """Select the optimal provider based on preferences and current conditions."""
        
        # Get available providers
        available_providers = await self._get_available_providers(preferences.excluded_providers)
        
        if not available_providers:
            raise AllProvidersUnavailableException(
                len(self.provider_configs),
                {pid: self._last_health_checks[pid].error_message or "Unknown error" 
                 for pid in self.provider_configs.keys() 
                 if pid in self._last_health_checks and not self._last_health_checks[pid].is_healthy}
            )
        
        # Apply operation-specific preferences
        if operation_type and operation_type in preferences.operation_preferences:
            preferred_provider = preferences.operation_preferences[operation_type]
            if preferred_provider in available_providers:
                return await self._get_specific_provider(preferred_provider)
        
        # Apply general preferences
        if preferences.preferred_provider and preferences.preferred_provider in available_providers:
            return await self._get_specific_provider(preferences.preferred_provider)
        
        # Select based on optimization strategy
        if preferences.cost_optimization:
            selected_provider = self._select_lowest_cost_provider(available_providers, operation_type)
        elif preferences.performance_priority:
            selected_provider = self._select_fastest_provider(available_providers)
        else:
            selected_provider = self._select_balanced_provider(available_providers, operation_type)
        
        return await self._get_specific_provider(selected_provider)
    
    async def _get_available_providers(self, excluded: List[str]) -> List[str]:
        """Get list of currently available (healthy) providers."""
        await self._perform_health_checks()
        
        available = []
        for provider_id in self.provider_configs.keys():
            if provider_id in excluded:
                continue
            
            # Check circuit breaker
            if self._is_circuit_breaker_open(provider_id):
                continue
            
            # Check health status
            if provider_id in self._last_health_checks:
                health = self._last_health_checks[provider_id]
                if health.is_healthy and health.within_rate_limits:
                    available.append(provider_id)
        
        return available
    
    def _select_lowest_cost_provider(
        self, 
        available_providers: List[str], 
        operation_type: Optional[TranslationOperationType]
    ) -> str:
        """Select provider with lowest estimated cost."""
        if not available_providers:
            raise AllProvidersUnavailableException(0, {})
        
        best_provider = available_providers[0]
        lowest_cost = float('inf')
        
        for provider_id in available_providers:
            health = self._last_health_checks.get(provider_id)
            if health and health.cost_per_token:
                cost = health.cost_per_token
                if cost < lowest_cost:
                    lowest_cost = cost
                    best_provider = provider_id
        
        logger.info(f"Selected cost-optimized provider: {best_provider} (cost: ${lowest_cost:.6f}/token)")
        return best_provider
    
    def _select_fastest_provider(self, available_providers: List[str]) -> str:
        """Select provider with lowest latency."""
        if not available_providers:
            raise AllProvidersUnavailableException(0, {})
        
        best_provider = available_providers[0]
        lowest_latency = float('inf')
        
        for provider_id in available_providers:
            health = self._last_health_checks.get(provider_id)
            if health and health.api_latency_ms:
                latency = health.api_latency_ms
                if latency < lowest_latency:
                    lowest_latency = latency
                    best_provider = provider_id
        
        logger.info(f"Selected performance-optimized provider: {best_provider} (latency: {lowest_latency:.1f}ms)")
        return best_provider
    
    def _select_balanced_provider(
        self, 
        available_providers: List[str], 
        operation_type: Optional[TranslationOperationType]
    ) -> str:
        """Select provider using balanced scoring algorithm."""
        if not available_providers:
            raise AllProvidersUnavailableException(0, {})
        
        best_provider = available_providers[0]
        best_score = -1.0
        
        for provider_id in available_providers:
            score = self._calculate_provider_score(provider_id, operation_type)
            if score > best_score:
                best_score = score
                best_provider = provider_id
        
        logger.info(f"Selected balanced provider: {best_provider} (score: {best_score:.2f})")
        return best_provider
    
    def _calculate_provider_score(
        self, 
        provider_id: str, 
        operation_type: Optional[TranslationOperationType]
    ) -> float:
        """Calculate composite score for provider selection."""
        stats = self.provider_stats.get(provider_id, ProviderStats())
        health = self._last_health_checks.get(provider_id)
        
        # Base score from success rate
        score = stats.success_rate / 100.0  # 0.0 - 1.0
        
        # Penalty for consecutive failures
        failure_penalty = min(0.3, stats.consecutive_failures * 0.1)
        score -= failure_penalty
        
        # Bonus for low latency (if available)
        if health and health.api_latency_ms:
            latency_bonus = max(0.0, (1000 - health.api_latency_ms) / 1000) * 0.2
            score += latency_bonus
        
        # Cost factor (lower cost = higher score)
        if health and health.cost_per_token:
            # Normalize cost bonus (assuming max cost of $0.1/1K tokens)
            cost_bonus = max(0.0, (0.0001 - health.cost_per_token) / 0.0001) * 0.1
            score += cost_bonus
        
        # Recency bonus (recently used providers get slight preference)
        if stats.last_used:
            hours_since_use = (datetime.utcnow() - stats.last_used).total_seconds() / 3600
            recency_bonus = max(0.0, (24 - hours_since_use) / 24) * 0.05
            score += recency_bonus
        
        # Provider-specific bonuses based on operation type
        if operation_type:
            score += self._get_operation_type_bonus(provider_id, operation_type)
        
        return max(0.0, min(1.0, score))  # Clamp to 0-1 range
    
    def _get_operation_type_bonus(self, provider_id: str, operation_type: TranslationOperationType) -> float:
        """Get provider-specific bonus based on operation type."""
        bonuses = {
            TranslationOperationType.FUNCTION_TRANSLATION: {
                LLMProviderType.ANTHROPIC: 0.1,  # Claude excels at detailed analysis
                LLMProviderType.OPENAI: 0.05,
                LLMProviderType.GEMINI: 0.03
            },
            TranslationOperationType.IMPORT_EXPLANATION: {
                LLMProviderType.ANTHROPIC: 0.08,  # Good at security analysis
                LLMProviderType.OPENAI: 0.06,
                LLMProviderType.GEMINI: 0.04
            },
            TranslationOperationType.STRING_INTERPRETATION: {
                LLMProviderType.GEMINI: 0.1,     # Good at pattern recognition
                LLMProviderType.OPENAI: 0.06,
                LLMProviderType.ANTHROPIC: 0.04
            },
            TranslationOperationType.OVERALL_SUMMARY: {
                LLMProviderType.ANTHROPIC: 0.12,  # Excellent at comprehensive analysis
                LLMProviderType.OPENAI: 0.08,
                LLMProviderType.GEMINI: 0.06
            }
        }
        
        return bonuses.get(operation_type, {}).get(provider_id, 0.0)
    
    async def _create_provider(self, provider_id: str) -> LLMProvider:
        """Create and initialize a new provider instance."""
        if provider_id not in self.provider_configs:
            raise LLMProviderException(f"Provider {provider_id} not configured", "factory", "PROVIDER_NOT_FOUND")
        
        config = self.provider_configs[provider_id]
        provider_class = self.PROVIDER_CLASSES[config.provider_id]
        
        try:
            # Create provider instance
            provider = provider_class(config)
            await provider.initialize()
            
            # Store instance
            self.providers[provider_id] = provider
            
            logger.info(f"Created and initialized provider: {provider_id}")
            return provider
            
        except Exception as e:
            # Update stats
            stats = self.provider_stats[provider_id]
            stats.consecutive_failures += 1
            
            logger.error(f"Failed to create provider {provider_id}: {e}")
            raise LLMProviderException(
                f"Failed to create provider {provider_id}: {str(e)}",
                "factory",
                "PROVIDER_CREATION_FAILED"
            )
    
    async def _perform_health_checks(self) -> None:
        """Perform health checks on all configured providers."""
        current_time = datetime.utcnow()
        
        # Only check if enough time has passed
        check_needed = []
        for provider_id in self.provider_configs.keys():
            last_check = self._last_health_checks.get(provider_id)
            if not last_check or (current_time - last_check.last_check) > self._health_check_interval:
                check_needed.append(provider_id)
        
        if not check_needed:
            return
        
        # Perform health checks in parallel
        tasks = []
        for provider_id in check_needed:
            if provider_id in self.providers:
                task = self._check_provider_health(provider_id)
                tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_provider_health(self, provider_id: str) -> None:
        """Check health of a specific provider."""
        provider = self.providers.get(provider_id)
        if not provider:
            return
        
        try:
            health_status = await provider.health_check()
            self._last_health_checks[provider_id] = health_status
            
            # Update stats
            stats = self.provider_stats[provider_id]
            if health_status.is_healthy:
                stats.consecutive_failures = 0
                stats.health_check_failures = 0
            else:
                stats.health_check_failures += 1
            
        except Exception as e:
            logger.warning(f"Health check failed for provider {provider_id}: {e}")
            
            # Update failure stats
            stats = self.provider_stats[provider_id]
            stats.health_check_failures += 1
            stats.consecutive_failures += 1
            
            # Create failed health status
            self._last_health_checks[provider_id] = ProviderHealthStatus(
                provider_id=provider_id,
                is_healthy=False,
                within_rate_limits=False,
                available_models=[],
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
    
    def _is_circuit_breaker_open(self, provider_id: str) -> bool:
        """Check if circuit breaker is open for a provider."""
        stats = self.provider_stats.get(provider_id, ProviderStats())
        
        # Open circuit if too many consecutive failures
        if stats.consecutive_failures >= 5:
            # Check if enough time has passed to try again
            if stats.last_used:
                time_since_last_use = datetime.utcnow() - stats.last_used
                return time_since_last_use < self._circuit_breaker_timeout
            return True
        
        return False
    
    def record_request_success(
        self, 
        provider_id: str, 
        tokens_used: int, 
        cost: float, 
        latency_ms: int
    ) -> None:
        """Record successful request statistics."""
        stats = self.provider_stats[provider_id]
        stats.total_requests += 1
        stats.successful_requests += 1
        stats.total_tokens += tokens_used
        stats.total_cost += cost
        stats.last_used = datetime.utcnow()
        stats.consecutive_failures = 0  # Reset failure counter
        
        # Update rolling average latency
        if stats.average_latency_ms == 0:
            stats.average_latency_ms = latency_ms
        else:
            # Exponential moving average
            stats.average_latency_ms = 0.7 * stats.average_latency_ms + 0.3 * latency_ms
    
    def record_request_failure(self, provider_id: str, error: Exception) -> None:
        """Record failed request statistics."""
        stats = self.provider_stats[provider_id]
        stats.total_requests += 1
        stats.failed_requests += 1
        stats.consecutive_failures += 1
        stats.last_used = datetime.utcnow()
        
        logger.warning(f"Request failed for provider {provider_id}: {error}")
    
    def get_provider_stats(self, provider_id: Optional[str] = None) -> Dict[str, ProviderStats]:
        """Get statistics for one or all providers."""
        if provider_id:
            return {provider_id: self.provider_stats.get(provider_id, ProviderStats())}
        return self.provider_stats.copy()
    
    def get_healthy_providers(self) -> List[str]:
        """Get list of currently healthy provider IDs."""
        healthy = []
        for provider_id in self.provider_configs.keys():
            if not self._is_circuit_breaker_open(provider_id):
                health = self._last_health_checks.get(provider_id)
                if health and health.is_healthy:
                    healthy.append(provider_id)
        return healthy
    
    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Get list of supported provider types."""
        return list(cls.PROVIDER_CLASSES.keys())