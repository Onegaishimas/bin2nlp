"""
Tests for LLM provider error handling, rate limits, and timeout scenarios.

Validates that the system properly handles various failure modes from
LLM providers including API errors, rate limiting, and network issues.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta
import httpx

from src.llm.providers.factory import LLMProviderFactory
from src.llm.providers.openai_provider import OpenAIProvider
from src.llm.providers.anthropic_provider import AnthropicProvider
from src.llm.providers.gemini_provider import GeminiProvider
from src.core.exceptions import *
from tests.fixtures.llm_responses import ERROR_RESPONSES, get_mock_response


class TestLLMErrorHandling:
    """Test LLM provider error handling scenarios."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock LLM provider configuration."""
        return {
            "openai": {
                "api_key": "sk-test123456789",
                "model": "gpt-4",
                "timeout": 30,
                "max_retries": 3
            },
            "anthropic": {
                "api_key": "sk-ant-test123456789",
                "model": "claude-3-sonnet-20240229",
                "timeout": 45,
                "max_retries": 3
            },
            "gemini": {
                "api_key": "test-gemini-key-123",
                "model": "gemini-pro",
                "timeout": 30,
                "max_retries": 2
            }
        }
    
    @pytest.mark.asyncio
    async def test_api_key_validation_errors(self, mock_config):
        """Test handling of invalid API key errors."""
        
        # Test OpenAI invalid key
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            mock_openai_client.return_value.chat.completions.acreate.side_effect = \
                httpx.HTTPStatusError("Incorrect API key provided", 
                                    request=Mock(), response=Mock(status_code=401))
            
            provider = OpenAIProvider(mock_config["openai"])
            
            with pytest.raises(AuthenticationException) as exc_info:
                await provider.translate_function({
                    "name": "test_func",
                    "address": "0x401000",
                    "disassembly": "mov eax, ebx",
                    "decompiled_code": "return x;"
                })
            
            assert "authentication" in str(exc_info.value).lower()
            assert exc_info.value.error_code == "AUTHENTICATION_ERROR"
    
    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, mock_config):
        """Test rate limit error handling and retry logic."""
        
        # Test rate limit with retry-after header
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"retry-after": "60"}
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            mock_openai_client.return_value.chat.completions.acreate.side_effect = \
                httpx.HTTPStatusError("Rate limit exceeded", 
                                    request=Mock(), response=mock_response)
            
            provider = OpenAIProvider(mock_config["openai"])
            
            with pytest.raises(RateLimitException) as exc_info:
                await provider.translate_function({
                    "name": "test_func",
                    "address": "0x401000", 
                    "disassembly": "mov eax, ebx",
                    "decompiled_code": "return x;"
                })
            
            assert exc_info.value.error_code == "RATE_LIMIT_ERROR"
            assert exc_info.value.retry_after == 60
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_config):
        """Test request timeout handling."""
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            mock_openai_client.return_value.chat.completions.acreate.side_effect = \
                asyncio.TimeoutError("Request timed out")
            
            provider = OpenAIProvider(mock_config["openai"])
            
            with pytest.raises(ProcessingException) as exc_info:
                await provider.translate_function({
                    "name": "test_func",
                    "address": "0x401000",
                    "disassembly": "mov eax, ebx", 
                    "decompiled_code": "return x;"
                })
            
            assert "timeout" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_network_connection_errors(self, mock_config):
        """Test network connection error handling."""
        
        with patch('src.llm.providers.anthropic_provider.AsyncAnthropic') as mock_anthropic_client:
            mock_anthropic_client.return_value.messages.create.side_effect = \
                httpx.ConnectError("Connection failed")
            
            provider = AnthropicProvider(mock_config["anthropic"])
            
            with pytest.raises(ProcessingException) as exc_info:
                await provider.translate_function({
                    "name": "test_func",
                    "address": "0x401000",
                    "disassembly": "mov eax, ebx",
                    "decompiled_code": "return x;"
                })
            
            assert "connection" in str(exc_info.value).lower() or "network" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_content_policy_violations(self, mock_config):
        """Test content policy violation handling."""
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {
                "code": "content_policy_violation",
                "message": "Content violates usage policies"
            }
        }
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            mock_openai_client.return_value.chat.completions.acreate.side_effect = \
                httpx.HTTPStatusError("Content policy violation", 
                                    request=Mock(), response=mock_response)
            
            provider = OpenAIProvider(mock_config["openai"])
            
            with pytest.raises(ValidationException) as exc_info:
                await provider.translate_function({
                    "name": "malicious_func",
                    "address": "0x401000",
                    "disassembly": "potentially harmful code",
                    "decompiled_code": "malicious operations"
                })
            
            assert "policy" in str(exc_info.value).lower() or "content" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_server_errors(self, mock_config):
        """Test server error handling (5xx errors)."""
        
        mock_response = Mock()
        mock_response.status_code = 503
        
        with patch('src.llm.providers.gemini_provider.genai.GenerativeModel') as mock_gemini:
            mock_gemini.return_value.generate_content_async.side_effect = \
                Exception("Service temporarily unavailable")
            
            provider = GeminiProvider(mock_config["gemini"])
            
            with pytest.raises(ProcessingException) as exc_info:
                await provider.translate_function({
                    "name": "test_func",
                    "address": "0x401000",
                    "disassembly": "mov eax, ebx",
                    "decompiled_code": "return x;"
                })
            
            assert exc_info.value.error_code == "PROCESSING_ERROR"
    
    @pytest.mark.asyncio
    async def test_retry_logic_with_exponential_backoff(self, mock_config):
        """Test retry logic with exponential backoff."""
        
        call_count = 0
        
        async def mock_api_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # Fail first two attempts
                raise httpx.HTTPStatusError("Temporary error", 
                                          request=Mock(), 
                                          response=Mock(status_code=503))
            else:
                # Succeed on third attempt
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Successful translation"
                mock_response.usage.total_tokens = 150
                return mock_response
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            mock_openai_client.return_value.chat.completions.acreate = mock_api_call
            
            provider = OpenAIProvider(mock_config["openai"])
            
            # Should succeed after retries
            result = await provider.translate_function({
                "name": "test_func",
                "address": "0x401000",
                "disassembly": "mov eax, ebx",
                "decompiled_code": "return x;"
            })
            
            assert result is not None
            assert call_count == 3  # Should have retried 2 times
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_config):
        """Test behavior when max retries are exceeded."""
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            mock_openai_client.return_value.chat.completions.acreate.side_effect = \
                httpx.HTTPStatusError("Persistent error", 
                                    request=Mock(), 
                                    response=Mock(status_code=503))
            
            provider = OpenAIProvider(mock_config["openai"])
            
            with pytest.raises(ProcessingException):
                await provider.translate_function({
                    "name": "test_func",
                    "address": "0x401000",
                    "disassembly": "mov eax, ebx",
                    "decompiled_code": "return x;"
                })
    
    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, mock_config):
        """Test handling of malformed responses from providers."""
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            # Mock a response with missing required fields
            mock_response = Mock()
            mock_response.choices = []  # Empty choices
            mock_response.usage = None
            mock_openai_client.return_value.chat.completions.acreate.return_value = mock_response
            
            provider = OpenAIProvider(mock_config["openai"])
            
            with pytest.raises(ProcessingException) as exc_info:
                await provider.translate_function({
                    "name": "test_func",
                    "address": "0x401000",
                    "disassembly": "mov eax, ebx",
                    "decompiled_code": "return x;"
                })
            
            assert "malformed" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_cost_limit_enforcement(self, mock_config):
        """Test enforcement of cost limits."""
        
        # Set low cost limit
        config_with_limit = mock_config["openai"].copy()
        config_with_limit["daily_spend_limit"] = 1.0  # $1 limit
        config_with_limit["estimated_cost_per_request"] = 2.0  # $2 per request
        
        provider = OpenAIProvider(config_with_limit)
        
        # Mock cost checking to exceed limit
        with patch.object(provider, '_check_cost_limits') as mock_cost_check:
            mock_cost_check.side_effect = ProcessingException(
                "Daily spending limit exceeded",
                error_code="COST_LIMIT_EXCEEDED"
            )
            
            with pytest.raises(ProcessingException) as exc_info:
                await provider.translate_function({
                    "name": "test_func",
                    "address": "0x401000",
                    "disassembly": "mov eax, ebx",
                    "decompiled_code": "return x;"
                })
            
            assert exc_info.value.error_code == "COST_LIMIT_EXCEEDED"
    
    @pytest.mark.asyncio
    async def test_provider_health_check_failures(self, mock_config):
        """Test health check failure scenarios."""
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            mock_openai_client.return_value.chat.completions.create.side_effect = \
                httpx.HTTPStatusError("Service unavailable", 
                                    request=Mock(), 
                                    response=Mock(status_code=503))
            
            provider = OpenAIProvider(mock_config["openai"])
            
            health_status = await provider.health_check()
            
            assert not health_status.is_healthy
            assert "unavailable" in health_status.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_request_error_handling(self, mock_config):
        """Test error handling under concurrent request load."""
        
        error_count = 0
        success_count = 0
        
        async def mock_api_call(*args, **kwargs):
            nonlocal error_count, success_count
            # Simulate 30% error rate under load
            if error_count < 3:  # First 3 calls fail
                error_count += 1
                raise httpx.HTTPStatusError("Temporary overload", 
                                          request=Mock(), 
                                          response=Mock(status_code=429))
            else:
                success_count += 1
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = f"Translation {success_count}"
                mock_response.usage.total_tokens = 100
                return mock_response
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai_client:
            mock_openai_client.return_value.chat.completions.acreate = mock_api_call
            
            provider = OpenAIProvider(mock_config["openai"])
            
            # Make multiple concurrent requests
            tasks = []
            for i in range(10):
                task = provider.translate_function({
                    "name": f"test_func_{i}",
                    "address": f"0x40100{i}",
                    "disassembly": "mov eax, ebx",
                    "decompiled_code": "return x;"
                })
                tasks.append(task)
            
            # Some should succeed, some should fail
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = [r for r in results if not isinstance(r, Exception)]
            error_results = [r for r in results if isinstance(r, Exception)]
            
            assert len(successful_results) > 0
            assert len(error_results) > 0  # Some requests should fail due to rate limiting


class TestProviderFactory:
    """Test provider factory error handling."""
    
    @pytest.mark.asyncio
    async def test_factory_with_invalid_provider(self):
        """Test factory behavior with invalid provider name."""
        
        with pytest.raises(ValidationException) as exc_info:
            await LLMProviderFactory.create_provider(
                "invalid_provider",
                {"api_key": "test", "model": "test"}
            )
        
        assert "invalid_provider" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_factory_with_missing_config(self):
        """Test factory behavior with missing configuration."""
        
        with pytest.raises(ConfigurationException) as exc_info:
            await LLMProviderFactory.create_provider(
                "openai",
                {}  # Missing required config
            )
        
        assert "configuration" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_factory_provider_health_check_integration(self):
        """Test that factory validates provider health."""
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai:
            # Mock unhealthy provider
            mock_openai.return_value.chat.completions.create.side_effect = \
                Exception("Provider unavailable")
            
            config = {
                "api_key": "sk-test123", 
                "model": "gpt-4",
                "timeout": 30
            }
            
            # Factory should detect unhealthy provider
            with pytest.raises(ProcessingException) as exc_info:
                provider = await LLMProviderFactory.create_provider("openai", config)
                await provider.health_check()
            
            assert "health" in str(exc_info.value).lower() or "unavailable" in str(exc_info.value).lower()


class TestErrorRecovery:
    """Test error recovery and fallback mechanisms."""
    
    @pytest.mark.asyncio
    async def test_provider_fallback_on_failure(self):
        """Test fallback to alternative provider on failure."""
        
        # Mock primary provider failure
        primary_config = {"api_key": "sk-test", "model": "gpt-4"}
        fallback_config = {"api_key": "sk-ant-test", "model": "claude-3-sonnet-20240229"}
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai:
            mock_openai.return_value.chat.completions.acreate.side_effect = \
                httpx.HTTPStatusError("Primary provider failed", 
                                    request=Mock(), 
                                    response=Mock(status_code=503))
            
            with patch('src.llm.providers.anthropic_provider.AsyncAnthropic') as mock_anthropic:
                # Mock successful fallback
                mock_response = Mock()
                mock_response.content = [Mock()]
                mock_response.content[0].text = "Fallback translation successful"
                mock_response.usage.input_tokens = 50
                mock_response.usage.output_tokens = 100
                mock_anthropic.return_value.messages.create.return_value = mock_response
                
                # Test fallback logic (would be implemented in service layer)
                try:
                    primary_provider = OpenAIProvider(primary_config)
                    await primary_provider.translate_function({
                        "name": "test_func",
                        "address": "0x401000",
                        "disassembly": "mov eax, ebx",
                        "decompiled_code": "return x;"
                    })
                except ProcessingException:
                    # Fallback to secondary provider
                    fallback_provider = AnthropicProvider(fallback_config)
                    result = await fallback_provider.translate_function({
                        "name": "test_func",
                        "address": "0x401000", 
                        "disassembly": "mov eax, ebx",
                        "decompiled_code": "return x;"
                    })
                    
                    assert result is not None
                    assert "fallback" in result.lower()
    
    @pytest.mark.asyncio
    async def test_partial_failure_handling(self):
        """Test handling of partial failures in batch operations."""
        
        # Mock some requests succeeding and some failing
        call_count = 0
        
        async def mock_api_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Every 3rd call fails
                raise httpx.HTTPStatusError("Intermittent failure", 
                                          request=Mock(), 
                                          response=Mock(status_code=500))
            else:
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = f"Translation {call_count}"
                mock_response.usage.total_tokens = 100
                return mock_response
        
        with patch('src.llm.providers.openai_provider.OpenAI') as mock_openai:
            mock_openai.return_value.chat.completions.acreate = mock_api_call
            
            provider = OpenAIProvider({"api_key": "sk-test", "model": "gpt-4"})
            
            # Process multiple functions
            functions = [
                {"name": f"func_{i}", "address": f"0x40100{i}", 
                 "disassembly": "mov eax, ebx", "decompiled_code": "return x;"}
                for i in range(5)
            ]
            
            results = []
            errors = []
            
            for func in functions:
                try:
                    result = await provider.translate_function(func)
                    results.append(result)
                except Exception as e:
                    errors.append(e)
            
            # Should have some successes and some failures
            assert len(results) > 0
            assert len(errors) > 0
            assert len(results) + len(errors) == len(functions)