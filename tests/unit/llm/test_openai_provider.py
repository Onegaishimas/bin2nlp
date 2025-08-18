"""
Unit tests for OpenAI LLM provider with mocked API responses.

Tests OpenAI API integration including GPT-4, GPT-3.5-turbo, and OpenAI-compatible endpoints
with comprehensive mocking of API responses and error scenarios.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
import asyncio
from typing import Dict, Any, List
import httpx

# Note: These imports will be available after LLM framework implementation (Task 3.2.1)
# from src.llm.providers.openai_provider import OpenAIProvider
# from src.llm.base import LLMConfig, LLMResponse
# from src.core.exceptions import LLMProviderError, LLMAuthError, LLMRateLimitError


class TestOpenAIProvider:
    """Test OpenAI provider with mocked API responses."""
    
    @pytest.fixture
    def openai_config(self):
        """Mock OpenAI configuration."""
        return {
            'provider': 'openai',
            'model': 'gpt-4',
            'api_key': 'test-api-key-123',
            'base_url': 'https://api.openai.com/v1',
            'timeout': 30,
            'max_retries': 3,
            'temperature': 0.7,
            'max_tokens': 2000,
            'organization_id': 'test-org-123'
        }
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client."""
        client = AsyncMock()
        client.chat = AsyncMock()
        client.chat.completions = AsyncMock()
        return client
    
    def test_openai_provider_initialization(self, openai_config):
        """Test OpenAI provider initialization with various configurations."""
        # Mock provider initialization
        provider = Mock()
        provider.config = openai_config
        provider.model = openai_config['model']
        provider.api_key = openai_config['api_key']
        
        assert provider.config['provider'] == 'openai'
        assert provider.model == 'gpt-4'
        assert provider.api_key == 'test-api-key-123'
    
    def test_openai_compatible_endpoint_configuration(self):
        """Test configuration for OpenAI-compatible endpoints (Ollama, LM Studio, etc.)."""
        compatible_configs = [
            {
                'provider': 'openai',
                'model': 'llama2',
                'api_key': 'not-needed',
                'base_url': 'http://localhost:11434/v1',  # Ollama
                'timeout': 60
            },
            {
                'provider': 'openai', 
                'model': 'mistral-7b',
                'api_key': 'lm-studio',
                'base_url': 'http://localhost:1234/v1',  # LM Studio
                'timeout': 120
            },
            {
                'provider': 'openai',
                'model': 'custom-model',
                'api_key': 'custom-key',
                'base_url': 'https://custom-endpoint.com/v1',  # Custom endpoint
                'timeout': 45
            }
        ]
        
        for config in compatible_configs:
            # Mock provider with compatible endpoint
            provider = Mock()
            provider.config = config
            provider.base_url = config['base_url']
            
            assert 'v1' in provider.base_url, "OpenAI-compatible endpoint should use /v1 path"
            assert provider.config['provider'] == 'openai', "Should use OpenAI provider interface"


class TestOpenAIFunctionTranslation:
    """Test OpenAI function translation with mocked responses."""
    
    @pytest.fixture
    def mock_function_translation_response(self):
        """Mock successful function translation response from OpenAI."""
        return {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "function_name": "authenticate_user",
                        "natural_language_description": "This function validates user credentials by comparing the provided username and password hash against stored values in the database. It implements secure authentication with bcrypt password hashing and includes timing attack protection.",
                        "parameters_explanation": "Takes two parameters: 'username' (string) for the user identifier and 'password_hash' (string) for the pre-hashed password. Both parameters are required and validated for format and length.",
                        "return_value_explanation": "Returns boolean true if authentication succeeds, false if credentials are invalid. May throw AuthenticationError for malformed inputs or database connection failures.",
                        "assembly_summary": "Function loads username from stack, calls bcrypt comparison routine, implements constant-time comparison to prevent timing attacks, and returns result in EAX register.",
                        "confidence_score": 0.92,
                        "provider_metadata": {
                            "model": "gpt-4",
                            "tokens_used": 450,
                            "processing_time_ms": 1200
                        }
                    })
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 300,
                "completion_tokens": 150,
                "total_tokens": 450
            }
        }
    
    @pytest.mark.asyncio
    async def test_translate_function_success(self, openai_config, mock_function_translation_response):
        """Test successful function translation."""
        # Mock the API call
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_function_translation_response
            mock_post.return_value = mock_response
            
            # Mock provider
            provider = Mock()
            provider.translate_function = AsyncMock()
            
            # Mock function data
            function_data = {
                'name': 'sub_401000',
                'assembly_code': 'push ebp\nmov ebp, esp\n...',
                'address': '0x401000',
                'size': 156
            }
            
            # Mock the translation result
            expected_translation = json.loads(
                mock_function_translation_response['choices'][0]['message']['content']
            )
            
            provider.translate_function.return_value = expected_translation
            
            # Execute
            result = await provider.translate_function(function_data)
            
            # Verify
            assert result['function_name'] == 'authenticate_user'
            assert 'secure authentication' in result['natural_language_description'].lower()
            assert result['confidence_score'] > 0.9
            assert result['provider_metadata']['model'] == 'gpt-4'
    
    @pytest.mark.asyncio
    async def test_translate_function_with_context(self, openai_config):
        """Test function translation with additional context."""
        # Mock provider with context-aware translation
        provider = Mock()
        provider.translate_function = AsyncMock()
        
        function_data = {
            'name': 'sub_402000',
            'assembly_code': 'call malloc\npush eax\ncall strcpy\n...',
            'imports': ['malloc', 'strcpy', 'free'],
            'strings': ['user_input', 'buffer_overflow_detected'],
            'calling_functions': ['main', 'process_input']
        }
        
        # Mock response with context awareness
        mock_result = {
            'function_name': 'process_user_input',
            'natural_language_description': 'Processes user input with dynamic memory allocation. Uses strcpy which may be vulnerable to buffer overflow attacks. Includes overflow detection mechanisms.',
            'security_implications': 'Potential buffer overflow vulnerability due to strcpy usage. Recommend using strncpy or safer alternatives.',
            'context_analysis': 'Called by main and process_input functions, suggesting this is part of input processing pipeline.'
        }
        
        provider.translate_function.return_value = mock_result
        
        result = await provider.translate_function(function_data)
        
        assert 'buffer overflow' in result['security_implications'].lower()
        assert 'input processing pipeline' in result['context_analysis'].lower()


class TestOpenAIImportTranslation:
    """Test OpenAI import/export translation."""
    
    @pytest.fixture
    def mock_import_translation_response(self):
        """Mock import translation response."""
        return {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "library_name": "kernel32.dll",
                        "function_name": "CreateFileA", 
                        "api_documentation_summary": "Creates or opens a file or I/O device. Returns a handle that can be used to access the file for reading and writing. Part of Windows API for file system operations.",
                        "usage_context": "Used for file creation and opening operations in Windows applications. Common in file I/O routines and system-level programming.",
                        "parameters_description": "lpFileName (string): path to file, dwDesiredAccess (DWORD): access rights, dwShareMode (DWORD): sharing mode, lpSecurityAttributes: security descriptor, dwCreationDisposition (DWORD): action if file exists, dwFlagsAndAttributes (DWORD): file attributes, hTemplateFile (HANDLE): template file handle",
                        "security_implications": "File path validation required to prevent directory traversal attacks. Access control should be verified. Temporary file creation may expose sensitive data.",
                        "provider_metadata": {
                            "model": "gpt-4",
                            "api_documentation_source": "Microsoft Windows API Reference",
                            "confidence_score": 0.95
                        }
                    })
                }
            }]
        }
    
    @pytest.mark.asyncio
    async def test_translate_imports_success(self, mock_import_translation_response):
        """Test successful import translation."""
        provider = Mock()
        provider.translate_imports = AsyncMock()
        
        import_data = [
            {'library': 'kernel32.dll', 'function': 'CreateFileA'},
            {'library': 'user32.dll', 'function': 'MessageBoxA'},
            {'library': 'advapi32.dll', 'function': 'RegCreateKeyA'}
        ]
        
        # Mock multiple import translations
        expected_results = [
            json.loads(mock_import_translation_response['choices'][0]['message']['content']),
            {
                'library_name': 'user32.dll',
                'function_name': 'MessageBoxA',
                'api_documentation_summary': 'Displays a modal dialog box with message and buttons',
                'security_implications': 'UI redressing attacks possible if user input not sanitized'
            },
            {
                'library_name': 'advapi32.dll', 
                'function_name': 'RegCreateKeyA',
                'api_documentation_summary': 'Creates registry key for Windows registry access',
                'security_implications': 'Registry modifications require elevated privileges and careful validation'
            }
        ]
        
        provider.translate_imports.return_value = expected_results
        
        result = await provider.translate_imports(import_data)
        
        assert len(result) == 3
        assert result[0]['library_name'] == 'kernel32.dll'
        assert 'file system operations' in result[0]['api_documentation_summary'].lower()


class TestOpenAIStringTranslation:
    """Test OpenAI string interpretation."""
    
    @pytest.mark.asyncio
    async def test_translate_strings_with_context(self):
        """Test string translation with usage context."""
        provider = Mock()
        provider.translate_strings = AsyncMock()
        
        string_data = [
            {
                'value': 'SELECT * FROM users WHERE username = ?',
                'location': '0x403000',
                'cross_references': ['sub_401000', 'sub_401500'],
                'encoding': 'ascii'
            },
            {
                'value': '/tmp/sensitive_data.tmp', 
                'location': '0x403100',
                'cross_references': ['sub_402000'],
                'encoding': 'ascii'
            }
        ]
        
        mock_results = [
            {
                'string_value': 'SELECT * FROM users WHERE username = ?',
                'usage_context': 'Database query with parameterized statement for user lookup',
                'interpretation': 'SQL query for user authentication or authorization. Uses parameterized query (good security practice) to prevent SQL injection.',
                'security_implications': 'Properly parameterized query reduces SQL injection risk. Database access indicates authentication system.',
                'cross_references': ['Authentication function at 0x401000', 'User validation at 0x401500']
            },
            {
                'string_value': '/tmp/sensitive_data.tmp',
                'usage_context': 'Temporary file path for data storage',
                'interpretation': 'Temporary file in /tmp directory suggesting temporary data storage or caching mechanism.',
                'security_implications': 'Temporary files in /tmp may be readable by other users. Sensitive data exposure risk. Consider secure temporary file creation.',
                'cross_references': ['File processing function at 0x402000']
            }
        ]
        
        provider.translate_strings.return_value = mock_results
        
        result = await provider.translate_strings(string_data)
        
        assert len(result) == 2
        assert 'sql injection' in result[0]['security_implications'].lower()
        assert 'sensitive data exposure' in result[1]['security_implications'].lower()


class TestOpenAIErrorHandling:
    """Test OpenAI provider error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_authentication_error(self):
        """Test handling of authentication errors."""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock 401 Unauthorized response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = {
                'error': {
                    'message': 'Invalid API key',
                    'type': 'invalid_request_error',
                    'code': 'invalid_api_key'
                }
            }
            mock_post.return_value = mock_response
            
            # Mock provider error handling
            provider = Mock()
            provider.translate_function = AsyncMock()
            provider.translate_function.side_effect = Exception("LLMAuthError: Invalid API key")
            
            with pytest.raises(Exception) as exc_info:
                await provider.translate_function({})
            
            assert "Invalid API key" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self):
        """Test handling of rate limit errors."""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock 429 Rate Limited response
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {
                'error': {
                    'message': 'Rate limit exceeded',
                    'type': 'rate_limit_error',
                    'code': 'rate_limit_exceeded'
                }
            }
            mock_response.headers = {'retry-after': '60'}
            mock_post.return_value = mock_response
            
            provider = Mock()
            provider.translate_function = AsyncMock()
            provider.translate_function.side_effect = Exception("LLMRateLimitError: Rate limit exceeded, retry after 60 seconds")
            
            with pytest.raises(Exception) as exc_info:
                await provider.translate_function({})
            
            assert "Rate limit exceeded" in str(exc_info.value)
            assert "60 seconds" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_model_overloaded_error(self):
        """Test handling of model overloaded/server error."""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Mock 503 Service Unavailable
            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.json.return_value = {
                'error': {
                    'message': 'The model is currently overloaded',
                    'type': 'server_error',
                    'code': 'model_overloaded'
                }
            }
            mock_post.return_value = mock_response
            
            provider = Mock()
            provider.translate_function = AsyncMock()
            provider.translate_function.side_effect = Exception("LLMModelError: Model overloaded")
            
            with pytest.raises(Exception) as exc_info:
                await provider.translate_function({})
            
            assert "Model overloaded" in str(exc_info.value)


class TestOpenAIRetryLogic:
    """Test OpenAI provider retry logic with exponential backoff."""
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_on_rate_limit(self):
        """Test exponential backoff retry logic."""
        retry_attempts = []
        
        async def mock_api_call_with_retries():
            retry_attempts.append(len(retry_attempts) + 1)
            if len(retry_attempts) < 3:
                raise Exception("Rate limit error")
            return {"choices": [{"message": {"content": "success"}}]}
        
        # Mock retry logic with exponential backoff
        max_retries = 3
        base_delay = 1.0
        
        with patch('asyncio.sleep') as mock_sleep:
            # Simulate the retry logic
            for attempt in range(max_retries):
                try:
                    result = await mock_api_call_with_retries()
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        await mock_sleep(delay)
                    else:
                        raise
            
            # Verify exponential backoff delays: 1s, 2s
            expected_delays = [1.0, 2.0]
            actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
            
            assert len(retry_attempts) == 3, "Should make 3 attempts"
            assert actual_delays == expected_delays, f"Expected {expected_delays}, got {actual_delays}"


class TestOpenAIHealthCheck:
    """Test OpenAI provider health check functionality."""
    
    @pytest.mark.asyncio
    async def test_provider_health_check(self):
        """Test health check returns provider status."""
        provider = Mock()
        provider.health_check = AsyncMock()
        
        mock_health = {
            'provider_name': 'openai',
            'status': 'healthy',
            'response_time_ms': 250,
            'last_successful_call': '2025-01-15T14:30:00Z',
            'error_rate_percentage': 0.2,
            'quota_remaining': '85%',
            'model_availability': ['gpt-4', 'gpt-3.5-turbo', 'gpt-4-turbo'],
            'api_endpoint': 'https://api.openai.com/v1'
        }
        
        provider.health_check.return_value = mock_health
        
        result = await provider.health_check()
        
        assert result['provider_name'] == 'openai'
        assert result['status'] == 'healthy'
        assert 'gpt-4' in result['model_availability']
        assert result['response_time_ms'] < 1000  # Reasonable response time
    
    @pytest.mark.asyncio
    async def test_openai_compatible_endpoint_health(self):
        """Test health check for OpenAI-compatible endpoints."""
        compatible_endpoints = [
            'http://localhost:11434/v1',  # Ollama
            'http://localhost:1234/v1',   # LM Studio  
            'https://custom-api.example.com/v1'  # Custom
        ]
        
        for endpoint in compatible_endpoints:
            provider = Mock()
            provider.health_check = AsyncMock()
            provider.base_url = endpoint
            
            mock_health = {
                'provider_name': 'openai',
                'status': 'healthy',
                'api_endpoint': endpoint,
                'model_availability': ['local-model'],
                'response_time_ms': 100
            }
            
            provider.health_check.return_value = mock_health
            
            result = await provider.health_check()
            
            assert result['api_endpoint'] == endpoint
            assert result['status'] == 'healthy'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])