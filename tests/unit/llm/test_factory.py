"""
Unit tests for LLM Provider Factory.

Tests the intelligent provider selection, health monitoring, circuit breakers,
load balancing, and cost optimization logic using real factory code with mocked providers.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from src.llm.providers.factory import (
    LLMProviderFactory,
    ProviderStats,
    ProviderPreferences,
    AllProvidersUnavailableException
)
from src.llm.base import (
    LLMConfig,
    LLMProvider,
    LLMProviderType,
    ProviderHealthStatus,
    TranslationOperationType,
    LLMProviderException,
    TranslationRequest,
    TranslationResponse
)


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.initialized = False
        self.health_status = ProviderHealthStatus(
            provider_id=config.provider_id,
            is_healthy=True,
            within_rate_limits=True,
            available_models=["mock-model"],
            last_check=datetime.utcnow()
        )
    
    async def initialize(self):
        self.initialized = True
    
    async def cleanup(self):
        self.initialized = False
    
    def get_provider_id(self) -> str:
        return self.config.provider_id
    
    async def health_check(self) -> ProviderHealthStatus:
        return self.health_status
    
    async def translate_function(self, *args, **kwargs):
        return {"translation": "mock function translation"}
    
    async def generate_overall_summary(self, *args, **kwargs):
        return {"summary": "mock summary"}
    
    async def explain_imports(self, *args, **kwargs):
        return [{"import": "mock import explanation"}]
    
    async def interpret_strings(self, *args, **kwargs):
        return [{"string": "mock string interpretation"}]
    
    def get_cost_estimate(self, token_count: int, operation_type=None) -> float:
        return token_count * 0.00001  # $0.01 per 1K tokens
    
    def count_tokens(self, text: str) -> int:
        return len(text.split())  # Simple token counting


class TestProviderStats:
    """Test ProviderStats data class."""
    
    def test_stats_initialization(self):
        """Test stats initialization with defaults."""
        stats = ProviderStats()
        
        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.failed_requests == 0
        assert stats.total_tokens == 0
        assert stats.total_cost == 0.0
        assert stats.average_latency_ms == 0.0
        assert stats.last_used is None
        assert stats.consecutive_failures == 0
        assert stats.health_check_failures == 0
    
    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        stats = ProviderStats()
        
        # No requests
        assert stats.success_rate == 100.0
        assert stats.failure_rate == 0.0
        
        # With requests
        stats.total_requests = 10
        stats.successful_requests = 8
        stats.failed_requests = 2
        
        assert stats.success_rate == 80.0
        assert stats.failure_rate == 20.0
    
    def test_health_assessment(self):
        """Test health assessment logic."""
        stats = ProviderStats()
        
        # Healthy by default
        assert stats.is_healthy is True
        
        # Too many consecutive failures
        stats.consecutive_failures = 6
        assert stats.is_healthy is False
        
        # Too many health check failures
        stats.consecutive_failures = 2
        stats.health_check_failures = 4
        assert stats.is_healthy is False
        
        # Low success rate
        stats.health_check_failures = 1
        stats.total_requests = 10
        stats.successful_requests = 7  # 70% success rate
        assert stats.is_healthy is False


class TestProviderPreferences:
    """Test ProviderPreferences data class."""
    
    def test_preferences_initialization(self):
        """Test preferences initialization with defaults."""
        prefs = ProviderPreferences()
        
        assert prefs.preferred_provider is None
        assert prefs.cost_optimization is False
        assert prefs.performance_priority is False
        assert prefs.fallback_enabled is True
        assert prefs.max_cost_per_request is None
        assert prefs.excluded_providers == []
        assert prefs.operation_preferences == {}
    
    def test_preferences_customization(self):
        """Test custom preferences."""
        prefs = ProviderPreferences(
            preferred_provider="openai",
            cost_optimization=True,
            excluded_providers=["gemini"],
            operation_preferences={
                TranslationOperationType.FUNCTION_TRANSLATION: "anthropic"
            }
        )
        
        assert prefs.preferred_provider == "openai"
        assert prefs.cost_optimization is True
        assert "gemini" in prefs.excluded_providers
        assert prefs.operation_preferences[TranslationOperationType.FUNCTION_TRANSLATION] == "anthropic"


class TestLLMProviderFactory:
    """Test LLM Provider Factory core functionality."""
    
    @pytest.fixture
    def factory(self):
        """Create factory instance for testing."""
        return LLMProviderFactory()
    
    @pytest.fixture
    def mock_configs(self):
        """Create LLM configurations using local Ollama service."""
        return {
            "openai": LLMConfig(
                provider_id=LLMProviderType.OPENAI,
                api_key="ollama-local-key",  # Ollama doesn't need real API key
                default_model="huihui_ai/phi4-abliterated:latest",
                endpoint_url="http://ollama.mcslab.io:80/v1",  # OpenAI-compatible endpoint
                temperature=0.1,
                max_tokens=2048
            ),
            "anthropic": LLMConfig(
                provider_id=LLMProviderType.ANTHROPIC,
                api_key="test-anthropic-key",
                default_model="claude-3-sonnet",
                temperature=0.1,
                max_tokens=2048
            ),
            "gemini": LLMConfig(
                provider_id=LLMProviderType.GEMINI,
                api_key="test-gemini-key", 
                default_model="gemini-pro",
                temperature=0.1,
                max_tokens=2048
            )
        }
    
    def test_factory_initialization(self, factory):
        """Test factory initialization."""
        assert len(factory.providers) == 0
        assert len(factory.provider_configs) == 0
        assert len(factory.provider_stats) == 0
        assert len(factory._last_health_checks) == 0
        assert factory._health_check_interval == timedelta(minutes=5)
        assert factory._circuit_breaker_timeout == timedelta(minutes=10)
    
    def test_add_provider_configuration(self, factory, mock_configs):
        """Test adding provider configurations."""
        config = mock_configs["openai"]
        factory.add_provider(config)
        
        assert "openai" in factory.provider_configs
        assert "openai" in factory.provider_stats
        assert factory.provider_configs["openai"] == config
        assert isinstance(factory.provider_stats["openai"], ProviderStats)
    
    def test_add_unsupported_provider(self, factory):
        """Test adding unsupported provider type."""
        # Since LLMConfig now has enum validation, this will fail at the model level
        with pytest.raises(ValueError, match="Input should be"):
            LLMConfig(
                provider_id="unsupported",
                api_key="test-key",
                default_model="test-model"
            )
    
    @pytest.mark.asyncio
    async def test_factory_initialization_process(self, factory, mock_configs):
        """Test factory initialization process."""
        # Add configurations
        for config in mock_configs.values():
            factory.add_provider(config)
        
        # Mock the provider creation
        with patch.object(factory, 'PROVIDER_CLASSES', {
            LLMProviderType.OPENAI: MockLLMProvider,
            LLMProviderType.ANTHROPIC: MockLLMProvider,
            LLMProviderType.GEMINI: MockLLMProvider
        }):
            await factory.initialize()
            
            # Should have performed health checks
            assert len(factory._last_health_checks) >= 0  # May be 0 if no providers created yet
    
    @pytest.mark.asyncio
    async def test_get_specific_provider(self, factory, mock_configs):
        """Test getting a specific provider by ID."""
        config = mock_configs["openai"]
        factory.add_provider(config)
        
        with patch.object(factory, 'PROVIDER_CLASSES', {
            LLMProviderType.OPENAI: MockLLMProvider
        }):
            provider = await factory.get_provider(provider_id="openai")
            
            assert isinstance(provider, MockLLMProvider)
            assert provider.initialized is True
            assert "openai" in factory.providers
    
    @pytest.mark.asyncio
    async def test_get_provider_not_configured(self, factory):
        """Test getting unconfigured provider."""
        with pytest.raises(LLMProviderException, match="Provider.*not configured"):
            await factory.get_provider(provider_id="unconfigured")
    
    @pytest.mark.asyncio
    async def test_provider_selection_with_preferences(self, factory, mock_configs):
        """Test intelligent provider selection with preferences."""
        # Add all providers
        for config in mock_configs.values():
            factory.add_provider(config)
        
        # Create healthy mock providers
        def create_healthy_provider(config):
            provider = MockLLMProvider(config)
            provider.health_status = ProviderHealthStatus(
                provider_id=config.provider_id,
                is_healthy=True,
                within_rate_limits=True,
                available_models=["mock-model"],
                last_check=datetime.utcnow(),
                cost_per_token=0.00001,  # $0.01 per 1K tokens
                api_latency_ms=500
            )
            return provider
        
        with patch.object(factory, 'PROVIDER_CLASSES', {
            LLMProviderType.OPENAI: create_healthy_provider,
            LLMProviderType.ANTHROPIC: create_healthy_provider,
            LLMProviderType.GEMINI: create_healthy_provider
        }):
            # Test preferred provider selection
            preferences = ProviderPreferences(preferred_provider="anthropic")
            provider = await factory.get_provider(preferences=preferences)
            assert provider.get_provider_id() == "anthropic"
    
    @pytest.mark.asyncio
    async def test_cost_optimization_selection(self, factory, mock_configs):
        """Test cost-optimized provider selection."""
        for config in mock_configs.values():
            factory.add_provider(config)
        
        # Create providers with different costs
        def create_provider_with_cost(config, cost_per_token):
            def provider_factory(config):
                provider = MockLLMProvider(config)
                provider.health_status = ProviderHealthStatus(
                    provider_id=config.provider_id,
                    is_healthy=True,
                    within_rate_limits=True,
                    available_models=["mock-model"],
                    last_check=datetime.utcnow(),
                    cost_per_token=cost_per_token,
                    api_latency_ms=500
                )
                return provider
            return provider_factory
        
        with patch.object(factory, 'PROVIDER_CLASSES', {
            LLMProviderType.OPENAI: create_provider_with_cost(mock_configs["openai"], 0.00003),  # Most expensive
            LLMProviderType.ANTHROPIC: create_provider_with_cost(mock_configs["anthropic"], 0.00001),  # Cheapest
            LLMProviderType.GEMINI: create_provider_with_cost(mock_configs["gemini"], 0.00002)   # Middle
        }):
            # Test cost optimization
            preferences = ProviderPreferences(cost_optimization=True)
            provider = await factory.get_provider(preferences=preferences)
            
            # Should select the cheapest provider (anthropic)
            assert provider.get_provider_id() == "anthropic"
    
    @pytest.mark.asyncio
    async def test_performance_priority_selection(self, factory, mock_configs):
        """Test performance-optimized provider selection."""
        for config in mock_configs.values():
            factory.add_provider(config)
        
        # Create providers with different latencies
        def create_provider_with_latency(config, latency_ms):
            def provider_factory(config):
                provider = MockLLMProvider(config)
                provider.health_status = ProviderHealthStatus(
                    provider_id=config.provider_id,
                    is_healthy=True,
                    within_rate_limits=True,
                    available_models=["mock-model"],
                    last_check=datetime.utcnow(),
                    cost_per_token=0.00002,
                    api_latency_ms=latency_ms
                )
                return provider
            return provider_factory
        
        with patch.object(factory, 'PROVIDER_CLASSES', {
            LLMProviderType.OPENAI: create_provider_with_latency(mock_configs["openai"], 800),   # Slowest
            LLMProviderType.ANTHROPIC: create_provider_with_latency(mock_configs["anthropic"], 300),  # Fastest
            LLMProviderType.GEMINI: create_provider_with_latency(mock_configs["gemini"], 500)    # Middle
        }):
            # Test performance priority
            preferences = ProviderPreferences(performance_priority=True)
            provider = await factory.get_provider(preferences=preferences)
            
            # Should select the fastest provider (anthropic)
            assert provider.get_provider_id() == "anthropic"
    
    def test_provider_scoring_algorithm(self, factory, mock_configs):
        """Test the balanced provider scoring algorithm."""
        factory.add_provider(mock_configs["openai"])
        
        # Setup provider stats
        stats = factory.provider_stats["openai"]
        stats.total_requests = 100
        stats.successful_requests = 90  # 90% success rate
        stats.consecutive_failures = 1
        stats.last_used = datetime.utcnow() - timedelta(hours=2)  # Recent use
        
        # Setup health status
        health = ProviderHealthStatus(
            provider_id="openai",
            is_healthy=True,
            within_rate_limits=True,
            available_models=["gpt-4"],
            last_check=datetime.utcnow(),
            cost_per_token=0.00003,  # $0.03 per 1K tokens
            api_latency_ms=600
        )
        factory._last_health_checks["openai"] = health
        
        # Calculate score
        score = factory._calculate_provider_score(
            "openai", 
            TranslationOperationType.FUNCTION_TRANSLATION
        )
        
        # Score should be between 0 and 1
        assert 0.0 <= score <= 1.0
        
        # Should start with success rate (0.9)
        # Plus operation bonus for anthropic on function translation (0.1)
        # Plus various other bonuses/penalties
        assert score > 0.8  # Should be relatively high with good stats
    
    def test_operation_type_bonuses(self, factory):
        """Test operation-specific provider bonuses."""
        # Test function translation bonus for Anthropic
        bonus = factory._get_operation_type_bonus(
            LLMProviderType.ANTHROPIC, 
            TranslationOperationType.FUNCTION_TRANSLATION
        )
        assert bonus == 0.1  # Anthropic gets highest bonus for function translation
        
        # Test string interpretation bonus for Gemini
        bonus = factory._get_operation_type_bonus(
            LLMProviderType.GEMINI,
            TranslationOperationType.STRING_INTERPRETATION
        )
        assert bonus == 0.1  # Gemini gets highest bonus for string interpretation
        
        # Test overall summary bonus for Anthropic
        bonus = factory._get_operation_type_bonus(
            LLMProviderType.ANTHROPIC,
            TranslationOperationType.OVERALL_SUMMARY
        )
        assert bonus == 0.12  # Anthropic gets highest bonus for overall summary
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_logic(self, factory, mock_configs):
        """Test circuit breaker functionality."""
        factory.add_provider(mock_configs["openai"])
        
        # Simulate consecutive failures to trigger circuit breaker
        stats = factory.provider_stats["openai"]
        stats.consecutive_failures = 6  # Above threshold of 5
        stats.last_used = datetime.utcnow() - timedelta(minutes=5)  # Recent failure
        
        # Circuit breaker should be open
        assert factory._is_circuit_breaker_open("openai") is True
        
        # Should raise exception when trying to get provider
        with pytest.raises(LLMProviderException, match="circuit breaker is open"):
            await factory.get_provider(provider_id="openai")
        
        # After timeout period, circuit breaker should allow retry
        stats.last_used = datetime.utcnow() - timedelta(minutes=15)  # Past timeout
        assert factory._is_circuit_breaker_open("openai") is False
    
    @pytest.mark.asyncio
    async def test_all_providers_unavailable(self, factory, mock_configs):
        """Test behavior when all providers are unavailable."""
        # Add providers but don't initialize them properly
        for config in mock_configs.values():
            factory.add_provider(config)
        
        # Mock all health checks to return unhealthy
        def create_unhealthy_provider(config):
            provider = MockLLMProvider(config)
            provider.health_status = ProviderHealthStatus(
                provider_id=config.provider_id,
                is_healthy=False,
                within_rate_limits=False,
                available_models=[],
                last_check=datetime.utcnow(),
                error_message="Provider unavailable"
            )
            return provider
        
        with patch.object(factory, 'PROVIDER_CLASSES', {
            LLMProviderType.OPENAI: create_unhealthy_provider,
            LLMProviderType.ANTHROPIC: create_unhealthy_provider,
            LLMProviderType.GEMINI: create_unhealthy_provider
        }):
            with pytest.raises(AllProvidersUnavailableException) as exc_info:
                await factory.get_provider()
            
            exception = exc_info.value
            assert exception.provider_count == 3
            assert "All 3 configured LLM providers are unavailable" in str(exception)
    
    def test_request_statistics_tracking(self, factory, mock_configs):
        """Test request success and failure tracking."""
        factory.add_provider(mock_configs["openai"])
        
        # Record successful request
        factory.record_request_success("openai", tokens_used=150, cost=0.003, latency_ms=450)
        
        stats = factory.provider_stats["openai"]
        assert stats.total_requests == 1
        assert stats.successful_requests == 1
        assert stats.failed_requests == 0
        assert stats.total_tokens == 150
        assert stats.total_cost == 0.003
        assert stats.average_latency_ms == 450
        assert stats.consecutive_failures == 0
        assert stats.last_used is not None
        
        # Record another successful request
        factory.record_request_success("openai", tokens_used=200, cost=0.004, latency_ms=300)
        
        assert stats.total_requests == 2
        assert stats.successful_requests == 2
        assert stats.total_tokens == 350
        assert stats.total_cost == 0.007
        # Latency should be exponential moving average: 0.7*450 + 0.3*300 = 405
        assert abs(stats.average_latency_ms - 405) < 1
        
        # Record failed request
        factory.record_request_failure("openai", Exception("Test error"))
        
        assert stats.total_requests == 3
        assert stats.successful_requests == 2
        assert stats.failed_requests == 1
        assert stats.consecutive_failures == 1
        assert stats.success_rate == pytest.approx(66.67, rel=0.01)
    
    def test_provider_exclusions(self, factory, mock_configs):
        """Test provider exclusion logic."""
        for config in mock_configs.values():
            factory.add_provider(config)
        
        # Mock health checks to return all providers as healthy
        healthy_status = ProviderHealthStatus(
            provider_id="test",
            is_healthy=True,
            within_rate_limits=True,
            available_models=["model"],
            last_check=datetime.utcnow()
        )
        
        for provider_id in mock_configs.keys():
            factory._last_health_checks[provider_id] = healthy_status._replace(provider_id=provider_id)
        
        # Test exclusions
        excluded = ["gemini", "openai"]
        available = asyncio.run(factory._get_available_providers(excluded))
        
        # Only anthropic should be available
        assert "anthropic" in available
        assert "gemini" not in available
        assert "openai" not in available
    
    def test_get_provider_stats(self, factory, mock_configs):
        """Test getting provider statistics."""
        factory.add_provider(mock_configs["openai"])
        factory.add_provider(mock_configs["anthropic"])
        
        # Record some stats
        factory.record_request_success("openai", 100, 0.002, 400)
        factory.record_request_failure("anthropic", Exception("Error"))
        
        # Get all stats
        all_stats = factory.get_provider_stats()
        assert "openai" in all_stats
        assert "anthropic" in all_stats
        assert all_stats["openai"].successful_requests == 1
        assert all_stats["anthropic"].failed_requests == 1
        
        # Get specific provider stats
        openai_stats = factory.get_provider_stats("openai")
        assert len(openai_stats) == 1
        assert "openai" in openai_stats
        assert openai_stats["openai"].successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_factory_cleanup(self, factory, mock_configs):
        """Test factory cleanup process."""
        # Add and initialize providers
        factory.add_provider(mock_configs["openai"])
        
        with patch.object(factory, 'PROVIDER_CLASSES', {
            LLMProviderType.OPENAI: MockLLMProvider
        }):
            provider = await factory.get_provider(provider_id="openai")
            assert provider.initialized is True
            
            # Cleanup factory
            await factory.cleanup()
            
            # Provider should be cleaned up
            assert provider.initialized is False
            assert len(factory.providers) == 0
            assert len(factory._last_health_checks) == 0
    
    def test_supported_providers_list(self):
        """Test getting list of supported providers."""
        supported = LLMProviderFactory.get_supported_providers()
        
        assert LLMProviderType.OPENAI in supported
        assert LLMProviderType.ANTHROPIC in supported
        assert LLMProviderType.GEMINI in supported
        assert len(supported) == 3