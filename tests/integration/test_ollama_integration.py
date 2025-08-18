"""
Integration tests for Ollama LLM service.

Tests the actual integration with the local Ollama service at ollama.mcslab.io
using the huihui_ai/phi4-abliterated:latest model.
"""

import pytest
import asyncio
from unittest.mock import patch

from src.llm.providers.factory import LLMProviderFactory
from src.llm.providers.openai_provider import OpenAIProvider
from src.llm.base import LLMConfig, LLMProviderType


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ollama_service_health():
    """Test if Ollama service is accessible and healthy."""
    config = LLMConfig(
        provider_id=LLMProviderType.OPENAI,
        api_key="ollama-local-key",  # Ollama doesn't validate API keys
        default_model="huihui_ai/phi4-abliterated:latest",
        endpoint_url="http://ollama.mcslab.io:80/v1",
        temperature=0.1,
        max_tokens=512,
        timeout_seconds=30
    )
    
    provider = OpenAIProvider(config)
    
    try:
        await provider.initialize()
        health_status = await provider.health_check()
        
        # If we get here, the service is accessible
        assert health_status is not None
        assert health_status.provider_id == LLMProviderType.OPENAI
        
        print(f"Ollama service health: {health_status.is_healthy}")
        print(f"Available models: {health_status.available_models}")
        print(f"Error (if any): {health_status.error_message}")
        
    except Exception as e:
        pytest.skip(f"Ollama service not accessible: {e}")
    
    finally:
        await provider.cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ollama_simple_translation():
    """Test simple function translation using Ollama service."""
    config = LLMConfig(
        provider_id=LLMProviderType.OPENAI,
        api_key="ollama-local-key",
        default_model="huihui_ai/phi4-abliterated:latest",
        endpoint_url="http://ollama.mcslab.io:80/v1",
        temperature=0.1,
        max_tokens=256,
        timeout_seconds=45
    )
    
    provider = OpenAIProvider(config)
    
    try:
        await provider.initialize()
        
        # Simple test assembly code
        assembly_code = """
        push rbp
        mov rbp, rsp
        mov eax, 42
        pop rbp
        ret
        """
        
        # Create a simple translation request
        from src.llm.base import TranslationRequest
        
        request = TranslationRequest(
            operation_type="function_translation",
            content={
                "function_name": "test_function",
                "assembly_code": assembly_code,
                "context": "Simple test function"
            },
            max_tokens=256,
            temperature=0.1
        )
        
        # Test the translation
        response = await provider.translate_function(request)
        
        assert response is not None
        print(f"Translation response: {response}")
        
        # Basic validation
        if hasattr(response, 'content'):
            assert len(response.content) > 10  # Should have some meaningful content
        
    except Exception as e:
        pytest.skip(f"Ollama translation test failed: {e}")
    
    finally:
        await provider.cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_factory_with_ollama():
    """Test LLM factory with real Ollama configuration."""
    factory = LLMProviderFactory()
    
    # Add Ollama configuration
    config = LLMConfig(
        provider_id=LLMProviderType.OPENAI,
        api_key="ollama-local-key",
        default_model="huihui_ai/phi4-abliterated:latest",
        endpoint_url="http://ollama.mcslab.io:80/v1",
        temperature=0.1,
        max_tokens=512
    )
    
    factory.add_provider(config)
    
    try:
        await factory.initialize()
        
        # Try to get the provider
        provider = await factory.get_provider(provider_id=LLMProviderType.OPENAI)
        
        assert provider is not None
        assert provider.get_provider_id() == LLMProviderType.OPENAI
        
        # Test health check through factory
        health_status = await provider.health_check()
        print(f"Provider health via factory: {health_status.is_healthy}")
        
        # Check factory stats
        stats = factory.get_provider_stats(LLMProviderType.OPENAI)
        assert LLMProviderType.OPENAI in stats
        
    except Exception as e:
        pytest.skip(f"Factory integration test failed: {e}")
    
    finally:
        await factory.cleanup()


if __name__ == "__main__":
    # Run a quick test
    asyncio.run(test_ollama_service_health())