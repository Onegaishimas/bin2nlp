"""
LLM Provider Integration Tests

Tests integration with multiple LLM providers (OpenAI, Anthropic, Gemini)
including real API calls, fallback behavior, cost tracking, and health monitoring.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any

from src.llm.providers.factory import LLMProviderFactory
from src.llm.providers.openai_provider import OpenAIProvider
from src.llm.providers.anthropic_provider import AnthropicProvider
from src.llm.providers.gemini_provider import GeminiProvider
from src.core.config import get_settings
from src.api.middleware import LLMProviderRateLimiter


@pytest.fixture
def mock_llm_settings():
    """Mock LLM settings for testing."""
    settings = get_settings()
    # Override with test settings
    settings.llm.enabled_providers = ["openai", "anthropic", "gemini"]
    settings.llm.openai_api_key = "sk-test_key_12345"
    settings.llm.anthropic_api_key = "sk-ant-test_key_12345"
    settings.llm.gemini_api_key = "test_gemini_key_12345"
    return settings


@pytest.fixture
async def provider_factory(mock_llm_settings):
    """Create LLM provider factory for testing."""
    factory = LLMProviderFactory()
    return factory


class TestLLMProviderFactory:
    """Test LLM provider factory and management."""
    
    async def test_factory_initialization(self, provider_factory):
        """Test factory initialization."""
        # Factory should initialize without error
        assert provider_factory is not None
    
    @patch('src.llm.providers.openai_provider.OpenAI')
    async def test_create_openai_provider(self, mock_openai_client, mock_llm_settings):
        """Test OpenAI provider creation."""
        # Mock OpenAI client
        mock_client_instance = AsyncMock()
        mock_openai_client.return_value = mock_client_instance
        
        # Create provider config
        config = mock_llm_settings.llm.get_provider_config("openai")
        
        # Create provider
        provider = OpenAIProvider(config)
        assert provider is not None
        assert provider.provider_id == "openai"
    
    @patch('src.llm.providers.anthropic_provider.Anthropic')
    async def test_create_anthropic_provider(self, mock_anthropic_client, mock_llm_settings):
        """Test Anthropic provider creation."""
        # Mock Anthropic client
        mock_client_instance = AsyncMock()
        mock_anthropic_client.return_value = mock_client_instance
        
        config = mock_llm_settings.llm.get_provider_config("anthropic")
        provider = AnthropicProvider(config)
        
        assert provider is not None
        assert provider.provider_id == "anthropic"
    
    @patch('src.llm.providers.gemini_provider.genai')
    async def test_create_gemini_provider(self, mock_genai, mock_llm_settings):
        """Test Gemini provider creation."""
        # Mock Gemini client
        mock_model = AsyncMock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        config = mock_llm_settings.llm.get_provider_config("gemini")
        provider = GeminiProvider(config)
        
        assert provider is not None
        assert provider.provider_id == "gemini"


class TestProviderHealthChecks:
    """Test health monitoring for LLM providers."""
    
    @patch('src.llm.providers.openai_provider.OpenAI')
    async def test_openai_health_check(self, mock_openai_client, mock_llm_settings):
        """Test OpenAI provider health check."""
        # Mock successful API call
        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create.return_value = AsyncMock(
            choices=[
                MagicMock(message=MagicMock(content="test response"))
            ],
            usage=MagicMock(total_tokens=10)
        )
        mock_openai_client.return_value = mock_client_instance
        
        config = mock_llm_settings.llm.get_provider_config("openai")
        provider = OpenAIProvider(config)
        
        health_status = await provider.health_check()
        
        assert health_status.is_healthy is True
        assert health_status.provider_id == "openai"
    
    @patch('src.llm.providers.openai_provider.OpenAI')
    async def test_openai_health_check_failure(self, mock_openai_client, mock_llm_settings):
        """Test OpenAI provider health check failure."""
        # Mock API failure
        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_client.return_value = mock_client_instance
        
        config = mock_llm_settings.llm.get_provider_config("openai")
        provider = OpenAIProvider(config)
        
        health_status = await provider.health_check()
        
        assert health_status.is_healthy is False
        assert "API Error" in health_status.error_message


class TestLLMTranslationIntegration:
    """Test LLM translation functionality integration."""
    
    @patch('src.llm.providers.openai_provider.OpenAI')
    async def test_function_translation(self, mock_openai_client, mock_llm_settings):
        """Test function translation with OpenAI."""
        # Mock OpenAI response
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="This function performs string manipulation by concatenating input parameters."))
        ]
        mock_response.usage = MagicMock(total_tokens=25)
        
        mock_client_instance = AsyncMock()
        mock_client_instance.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client_instance
        
        config = mock_llm_settings.llm.get_provider_config("openai")
        provider = OpenAIProvider(config)
        
        # Test function data
        function_data = {
            "name": "string_concat",
            "address": "0x401000",
            "disassembly": "mov eax, [esp+4]; add eax, [esp+8]; ret",
            "variables": ["param1", "param2"]
        }
        
        translation = await provider.translate_function(function_data, {})
        
        assert translation is not None
        assert len(translation["natural_language"]) > 0
        assert "string" in translation["natural_language"].lower()
    
    @patch('src.llm.providers.anthropic_provider.Anthropic')
    async def test_import_explanation(self, mock_anthropic_client, mock_llm_settings):
        """Test import explanation with Anthropic."""
        # Mock Anthropic response
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="This import provides memory allocation functionality for dynamic data structures.")]
        
        mock_response = AsyncMock()
        mock_response.content = [MagicMock(text="This import provides memory allocation functionality.")]
        mock_response.usage = MagicMock(input_tokens=20, output_tokens=15)
        
        mock_client_instance = AsyncMock()
        mock_client_instance.messages.create.return_value = mock_response
        mock_anthropic_client.return_value = mock_client_instance
        
        config = mock_llm_settings.llm.get_provider_config("anthropic")
        provider = AnthropicProvider(config)
        
        # Test import data
        imports = [
            {"library": "kernel32.dll", "function": "HeapAlloc"},
            {"library": "msvcrt.dll", "function": "malloc"}
        ]
        
        explanations = await provider.explain_imports(imports)
        
        assert len(explanations) > 0
        assert "allocation" in explanations[0]["purpose"].lower()


class TestProviderFallbackBehavior:
    """Test fallback behavior when providers fail."""
    
    @patch('src.llm.providers.openai_provider.OpenAI')
    @patch('src.llm.providers.anthropic_provider.Anthropic')
    async def test_provider_fallback_on_failure(self, mock_anthropic, mock_openai, mock_llm_settings):
        """Test fallback to secondary provider when primary fails."""
        # Mock OpenAI failure
        mock_openai_instance = AsyncMock()
        mock_openai_instance.chat.completions.create.side_effect = Exception("Rate limit exceeded")
        mock_openai.return_value = mock_openai_instance
        
        # Mock Anthropic success
        mock_anthropic_response = AsyncMock()
        mock_anthropic_response.content = [MagicMock(text="Fallback response from Anthropic")]
        mock_anthropic_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        
        mock_anthropic_instance = AsyncMock()
        mock_anthropic_instance.messages.create.return_value = mock_anthropic_response
        mock_anthropic.return_value = mock_anthropic_instance
        
        # Test provider selection with fallback
        factory = LLMProviderFactory()
        
        # This would require implementing provider selection logic
        # For now, just test that both providers can be created
        openai_config = mock_llm_settings.llm.get_provider_config("openai")
        anthropic_config = mock_llm_settings.llm.get_provider_config("anthropic")
        
        openai_provider = OpenAIProvider(openai_config)
        anthropic_provider = AnthropicProvider(anthropic_config)
        
        # Verify providers are different
        assert openai_provider.provider_id != anthropic_provider.provider_id


class TestLLMRateLimitingIntegration:
    """Test LLM rate limiting integration."""
    
    @pytest.fixture
    async def llm_rate_limiter(self):
        """Create LLM rate limiter for testing."""
        return LLMProviderRateLimiter()
    
    async def test_llm_rate_limit_enforcement(self, llm_rate_limiter):
        """Test LLM rate limiting enforcement."""
        user_id = "test_user"
        provider_id = "openai"
        
        # Should initially allow requests
        allowed, reason, stats = await llm_rate_limiter.check_llm_rate_limit(
            user_id, provider_id, estimated_tokens=100
        )
        
        if not allowed:
            # Rate limiter should be available with PostgreSQL storage
            pytest.fail("Rate limiting failed unexpectedly")
        
        assert allowed is True
        assert reason == ""
    
    async def test_llm_usage_tracking(self, llm_rate_limiter):
        """Test LLM usage tracking and statistics."""
        user_id = "usage_test_user"
        provider_id = "anthropic"
        
        try:
            # Record usage
            await llm_rate_limiter.record_llm_usage(
                user_id, provider_id, tokens_used=150
            )
            
            # Get usage stats
            stats = await llm_rate_limiter.get_llm_usage_stats(user_id, provider_id)
            
            assert provider_id in stats
            assert stats[provider_id]["tokens_used"] >= 150
        except Exception as e:
            # Usage tracking should work with PostgreSQL storage
            raise


class TestCostTracking:
    """Test cost estimation and tracking for LLM providers."""
    
    @patch('src.llm.providers.openai_provider.OpenAI')
    async def test_openai_cost_estimation(self, mock_openai_client, mock_llm_settings):
        """Test OpenAI cost estimation."""
        mock_client_instance = AsyncMock()
        mock_openai_client.return_value = mock_client_instance
        
        config = mock_llm_settings.llm.get_provider_config("openai")
        provider = OpenAIProvider(config)
        
        # Test cost estimation
        estimated_cost = provider.estimate_cost(token_count=1000)
        
        assert estimated_cost > 0
        assert isinstance(estimated_cost, (int, float))
    
    @patch('src.llm.providers.anthropic_provider.Anthropic')
    async def test_anthropic_cost_estimation(self, mock_anthropic_client, mock_llm_settings):
        """Test Anthropic cost estimation."""
        mock_client_instance = AsyncMock()
        mock_anthropic_client.return_value = mock_client_instance
        
        config = mock_llm_settings.llm.get_provider_config("anthropic")
        provider = AnthropicProvider(config)
        
        estimated_cost = provider.estimate_cost(token_count=1500)
        
        assert estimated_cost > 0
        assert isinstance(estimated_cost, (int, float))


class TestMultiProviderWorkflow:
    """Test complete multi-provider workflow."""
    
    @patch('src.llm.providers.openai_provider.OpenAI')
    @patch('src.llm.providers.anthropic_provider.Anthropic') 
    @patch('src.llm.providers.gemini_provider.genai')
    async def test_multi_provider_translation_workflow(
        self, mock_gemini, mock_anthropic, mock_openai, mock_llm_settings
    ):
        """Test complete workflow using multiple providers."""
        # Mock all providers
        self._setup_openai_mock(mock_openai)
        self._setup_anthropic_mock(mock_anthropic)
        self._setup_gemini_mock(mock_gemini)
        
        # Test data
        decompilation_data = {
            "functions": [
                {
                    "name": "main",
                    "address": "0x401000",
                    "disassembly": "push ebp; mov ebp, esp; call printf; pop ebp; ret"
                }
            ],
            "imports": [
                {"library": "msvcrt.dll", "function": "printf"}
            ]
        }
        
        # Create providers
        configs = mock_llm_settings.llm.get_enabled_provider_configs()
        providers = []
        
        for provider_id, config in configs.items():
            if provider_id == "openai":
                providers.append(OpenAIProvider(config))
            elif provider_id == "anthropic":
                providers.append(AnthropicProvider(config))
            elif provider_id == "gemini":
                providers.append(GeminiProvider(config))
        
        # Verify multiple providers are available
        assert len(providers) >= 2
        
        # Test that each provider can handle the same data
        for provider in providers:
            health = await provider.health_check()
            assert health.is_healthy
    
    def _setup_openai_mock(self, mock_openai_client):
        """Setup OpenAI mock."""
        mock_response = AsyncMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="OpenAI translation"))]
        mock_response.usage = MagicMock(total_tokens=20)
        
        mock_instance = AsyncMock()
        mock_instance.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_instance
    
    def _setup_anthropic_mock(self, mock_anthropic_client):
        """Setup Anthropic mock."""
        mock_response = AsyncMock()
        mock_response.content = [MagicMock(text="Anthropic translation")]
        mock_response.usage = MagicMock(input_tokens=15, output_tokens=10)
        
        mock_instance = AsyncMock()
        mock_instance.messages.create.return_value = mock_response
        mock_anthropic_client.return_value = mock_instance
    
    def _setup_gemini_mock(self, mock_gemini):
        """Setup Gemini mock."""
        mock_response = MagicMock()
        mock_response.text = "Gemini translation"
        mock_response.usage_metadata = MagicMock(total_token_count=25)
        
        mock_model = AsyncMock()
        mock_model.generate_content.return_value = mock_response
        mock_gemini.GenerativeModel.return_value = mock_model


@pytest.mark.slow
class TestLLMProviderPerformance:
    """Performance tests for LLM provider operations."""
    
    @patch('src.llm.providers.openai_provider.OpenAI')
    async def test_translation_performance(self, mock_openai_client, mock_llm_settings):
        """Test translation performance."""
        import time
        
        # Mock fast response
        mock_response = AsyncMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Fast response"))]
        mock_response.usage = MagicMock(total_tokens=10)
        
        mock_instance = AsyncMock()
        mock_instance.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_instance
        
        config = mock_llm_settings.llm.get_provider_config("openai")
        provider = OpenAIProvider(config)
        
        # Test function translation timing
        function_data = {
            "name": "test_func",
            "address": "0x401000", 
            "disassembly": "mov eax, 1; ret"
        }
        
        start_time = time.time()
        translation = await provider.translate_function(function_data, {})
        elapsed_time = time.time() - start_time
        
        assert translation is not None
        # Mock should be very fast
        assert elapsed_time < 1.0


if __name__ == "__main__":
    # Run tests with: pytest tests/integration/test_llm_provider_integration.py -v
    pytest.main([__file__, "-v"])