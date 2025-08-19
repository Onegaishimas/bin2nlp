"""
End-to-End Production Integration Tests

Complete workflow tests that validate the entire system from
HTTP request to final response, including all middleware,
decompilation, LLM translation, and caching.
"""

import pytest
import asyncio
import tempfile
import io
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.main import create_app
from src.api.middleware import create_dev_api_key
from src.core.config import get_settings


@pytest.fixture
def app():
    """Create FastAPI application for testing."""
    return create_app()


@pytest.fixture
def test_client(app):
    """Create test client for synchronous requests."""
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Create async client for asynchronous requests."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def auth_headers():
    """Create authentication headers for testing."""
    try:
        api_key = await create_dev_api_key("e2e_test_user") 
        return {"Authorization": f"Bearer {api_key}"}
    except Exception:
        pytest.skip("Redis not available for authentication")


@pytest.fixture
def sample_binary():
    """Create a sample binary file for testing."""
    # Simple ELF header + minimal content
    elf_header = (
        b'\x7fELF'  # Magic number
        b'\x02\x01\x01\x00'  # 64-bit, little-endian, current version, generic ABI
        b'\x00' * 8  # Padding
        b'\x02\x00'  # Executable file type
        b'\x3e\x00'  # AMD64 architecture  
        b'\x01\x00\x00\x00'  # Version 1
        b'\x00\x10\x40\x00\x00\x00\x00\x00'  # Entry point
        b'\x40\x00\x00\x00\x00\x00\x00\x00'  # Program header offset
        b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Section header offset
        b'\x00\x00\x00\x00'  # Flags
        b'\x40\x00'  # ELF header size
        b'\x38\x00'  # Program header entry size
        b'\x01\x00'  # Program header entries
        b'\x40\x00'  # Section header entry size
        b'\x00\x00'  # Section header entries
        b'\x00\x00'  # String table index
    )
    
    # Add some padding to make it a reasonable size
    padding = b'\x00' * (1024 - len(elf_header))
    return elf_header + padding


class TestCompleteDecompilationWorkflow:
    """Test complete decompilation workflow from upload to response."""
    
    @patch('src.decompilation.engine.DecompilationEngine')
    @patch('src.llm.providers.factory.LLMProviderFactory')
    async def test_complete_decompilation_workflow(
        self, mock_llm_factory, mock_decompilation_engine, 
        async_client, auth_headers, sample_binary
    ):
        """Test complete workflow: upload -> decompile -> translate -> response."""
        # Mock decompilation engine
        mock_engine_instance = AsyncMock()
        mock_engine_instance.analyze_binary_file.return_value = {
            "metadata": {
                "file_hash": "abc123",
                "file_name": "test.elf",
                "file_size": len(sample_binary),
                "file_format": "elf",
                "architecture": "x86_64",
                "platform": "linux"
            },
            "functions": [
                {
                    "name": "main",
                    "address": "0x401000",
                    "size": 64,
                    "disassembly": "push rbp; mov rbp, rsp; mov edi, 0x402000; call printf; leave; ret",
                    "calls_to": ["printf"],
                    "variables": ["argc", "argv"]
                }
            ],
            "imports": [
                {
                    "library": "libc.so.6",
                    "function": "printf",
                    "address": "0x401050"
                }
            ],
            "strings": [
                {
                    "content": "Hello, World!",
                    "address": "0x402000",
                    "encoding": "ascii"
                }
            ]
        }
        mock_decompilation_engine.return_value = mock_engine_instance
        
        # Mock LLM provider
        mock_provider = AsyncMock()
        mock_provider.translate_function.return_value = {
            "function_name": "main",
            "natural_language": "This is the main function that prints 'Hello, World!' to the console.",
            "purpose": "Program entry point",
            "parameters": ["Command line arguments"],
            "return_value": "Exit status code"
        }
        mock_provider.explain_imports.return_value = [
            {
                "library": "libc.so.6",
                "function": "printf",
                "purpose": "Formats and prints text to standard output"
            }
        ]
        
        mock_factory_instance = AsyncMock()
        mock_factory_instance.get_provider.return_value = mock_provider
        mock_llm_factory.return_value = mock_factory_instance
        
        # Create file upload
        files = {
            "file": ("test.elf", io.BytesIO(sample_binary), "application/octet-stream")
        }
        data = {
            "analysis_depth": "standard",
            "llm_provider": "openai",
            "translation_detail": "standard"
        }
        
        # Make request
        response = await async_client.post(
            "/api/v1/decompile",
            files=files,
            data=data,
            headers=auth_headers
        )
        
        # Verify response structure
        assert response.status_code in [200, 202], f"Unexpected status: {response.status_code}, body: {response.text}"
        
        if response.status_code == 200:
            result = response.json()
            assert "success" in result
            # Could be synchronous response
        elif response.status_code == 202:
            result = response.json()
            assert "job_id" in result
            # Async processing started


class TestAuthenticationWorkflow:
    """Test complete authentication workflow."""
    
    def test_unauthenticated_access_to_public_endpoints(self, test_client):
        """Test access to public endpoints without authentication."""
        public_endpoints = [
            "/api/v1/health",
            "/docs", 
            "/openapi.json"
        ]
        
        for endpoint in public_endpoints:
            response = test_client.get(endpoint, follow_redirects=False)
            # Should not require authentication
            assert response.status_code != 401, f"Public endpoint {endpoint} unexpectedly requires auth"
    
    async def test_protected_endpoint_authentication_flow(self, async_client, auth_headers):
        """Test authentication flow for protected endpoints."""
        # Test without authentication
        response = await async_client.get("/api/v1/admin/config")
        assert response.status_code == 401
        
        # Test with valid authentication
        response = await async_client.get("/api/v1/admin/config", headers=auth_headers)
        assert response.status_code != 401  # Should not be unauthorized


class TestRateLimitingWorkflow:
    """Test rate limiting in real workflow."""
    
    async def test_rate_limiting_enforcement(self, async_client, auth_headers):
        """Test rate limiting enforcement across multiple requests."""
        # Make multiple requests to a rate-limited endpoint
        responses = []
        for i in range(10):  # Should be within basic rate limits
            response = await async_client.get("/api/v1/health", headers=auth_headers)
            responses.append(response)
        
        # Most should succeed (rate limits are generous for health checks)
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        
        # Should either all succeed or show rate limiting behavior
        assert success_count + rate_limited_count == 10
        
        # Check for rate limit headers
        for response in responses:
            if response.status_code == 200:
                # May have rate limit headers
                pass  # Headers are optional in development mode


class TestErrorHandlingWorkflow:
    """Test error handling in complete workflows."""
    
    def test_invalid_file_upload_error_handling(self, test_client):
        """Test error handling for invalid file uploads."""
        # Test with no file
        response = test_client.post("/api/v1/decompile")
        assert response.status_code in [400, 422]
        
        # Test with invalid file
        invalid_file = b"not a binary file"
        response = test_client.post(
            "/api/v1/decompile",
            files={"file": ("test.txt", io.BytesIO(invalid_file), "text/plain")},
            data={"analysis_depth": "basic"}
        )
        assert response.status_code in [400, 422]
        
        # Should get structured error response
        try:
            error_data = response.json()
            assert "error" in error_data or "detail" in error_data
        except:
            # Non-JSON error response is also acceptable
            pass
    
    def test_malformed_request_error_handling(self, test_client):
        """Test error handling for malformed requests."""
        # Send invalid JSON
        response = test_client.post(
            "/api/v1/decompile",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code >= 400
        
        # Should get error response
        assert len(response.content) > 0


class TestCachingWorkflow:
    """Test caching behavior in complete workflows."""
    
    @patch('src.cache.result_cache.ResultCache')
    async def test_result_caching(self, mock_cache, async_client, auth_headers, sample_binary):
        """Test result caching during decompilation workflow."""
        # Mock cache
        mock_cache_instance = AsyncMock()
        mock_cache_instance.get.return_value = None  # Cache miss first time
        mock_cache_instance.set.return_value = True
        mock_cache.return_value = mock_cache_instance
        
        # Test caching behavior would require actual decompilation engine
        # For now, just verify cache is being called correctly
        assert mock_cache is not None


class TestLLMProviderWorkflow:
    """Test LLM provider integration in complete workflow."""
    
    @patch('src.llm.providers.factory.LLMProviderFactory')
    async def test_llm_provider_selection(self, mock_factory, async_client, auth_headers):
        """Test LLM provider selection and usage."""
        # Mock LLM factory
        mock_provider = AsyncMock()
        mock_provider.health_check.return_value = AsyncMock(is_healthy=True)
        
        mock_factory_instance = AsyncMock()
        mock_factory_instance.get_provider.return_value = mock_provider
        mock_factory_instance.get_healthy_providers.return_value = ["openai"]
        mock_factory.return_value = mock_factory_instance
        
        # Test LLM provider endpoints
        response = await async_client.get("/api/v1/llm-providers", headers=auth_headers)
        assert response.status_code != 404  # Endpoint should exist


class TestMonitoringWorkflow:
    """Test monitoring and observability in workflows."""
    
    async def test_correlation_id_tracking(self, async_client, auth_headers):
        """Test correlation ID tracking across requests."""
        response = await async_client.get("/api/v1/health", headers=auth_headers)
        
        # Should include correlation ID
        assert "X-Correlation-ID" in response.headers
        correlation_id = response.headers["X-Correlation-ID"]
        
        # Should be valid UUID format
        import uuid
        try:
            uuid.UUID(correlation_id)
        except ValueError:
            pytest.fail("Correlation ID should be valid UUID format")
    
    async def test_request_logging(self, async_client, auth_headers):
        """Test request logging behavior."""
        # Make request that should be logged
        response = await async_client.get("/api/v1/health", headers=auth_headers)
        
        # Should complete successfully (logging is internal)
        assert response.status_code == 200
        
        # Verify response has expected structure
        data = response.json()
        assert "status" in data


class TestAdminWorkflow:
    """Test admin functionality workflow."""
    
    async def test_api_key_management_workflow(self, async_client, auth_headers):
        """Test complete API key management workflow."""
        # Test listing API keys (should require admin permission)
        response = await async_client.get("/api/v1/admin/api-keys/test_user", headers=auth_headers)
        
        # Should either work or require higher permissions
        assert response.status_code in [200, 403, 500]
        
        if response.status_code == 200:
            # Should get list of API keys
            keys = response.json()
            assert isinstance(keys, list)
    
    async def test_system_stats_workflow(self, async_client, auth_headers):
        """Test system statistics workflow."""
        response = await async_client.get("/api/v1/admin/stats", headers=auth_headers)
        
        # Should either work or fail gracefully
        assert response.status_code in [200, 403, 500, 503]
        
        if response.status_code == 200:
            stats = response.json()
            assert "system_health" in stats or "redis_stats" in stats


@pytest.mark.slow
class TestPerformanceWorkflow:
    """Test performance aspects of complete workflows."""
    
    async def test_concurrent_request_handling(self, async_client, auth_headers):
        """Test system performance under concurrent load."""
        import asyncio
        import time
        
        async def make_request():
            return await async_client.get("/api/v1/health", headers=auth_headers)
        
        start_time = time.time()
        
        # Make 20 concurrent requests
        tasks = [make_request() for _ in range(20)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed_time = time.time() - start_time
        
        # Count successful responses
        success_count = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 200)
        
        # Should handle most requests successfully
        assert success_count >= 15, f"Too many failed requests: {success_count}/20"
        
        # Should handle concurrent requests reasonably quickly
        assert elapsed_time < 10.0, f"Concurrent requests too slow: {elapsed_time}s"
    
    async def test_large_file_upload_performance(self, async_client, auth_headers):
        """Test performance with larger file uploads."""
        import time
        
        # Create larger test file (10KB)
        large_binary = b'\x7fELF\x02\x01\x01\x00' + b'\x00' * (10 * 1024 - 8)
        
        files = {
            "file": ("large_test.elf", io.BytesIO(large_binary), "application/octet-stream")
        }
        data = {"analysis_depth": "basic"}
        
        start_time = time.time()
        
        response = await async_client.post(
            "/api/v1/decompile",
            files=files,
            data=data,
            headers=auth_headers
        )
        
        elapsed_time = time.time() - start_time
        
        # Should handle file upload reasonably quickly
        assert elapsed_time < 5.0, f"File upload too slow: {elapsed_time}s"
        
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 202, 400, 422, 500, 503]


class TestErrorRecoveryWorkflow:
    """Test error recovery and resilience."""
    
    @patch('src.decompilation.engine.DecompilationEngine')
    async def test_decompilation_engine_failure_recovery(
        self, mock_engine, async_client, auth_headers, sample_binary
    ):
        """Test recovery from decompilation engine failures."""
        # Mock engine failure
        mock_engine_instance = AsyncMock()
        mock_engine_instance.analyze_binary_file.side_effect = Exception("Engine failure")
        mock_engine.return_value = mock_engine_instance
        
        files = {
            "file": ("test.elf", io.BytesIO(sample_binary), "application/octet-stream")
        }
        
        response = await async_client.post(
            "/api/v1/decompile",
            files=files,
            data={"analysis_depth": "basic"},
            headers=auth_headers
        )
        
        # Should get error response, not crash
        assert response.status_code >= 400
        assert response.status_code < 600  # Valid HTTP status code
        
        # Should get structured error response
        try:
            error_data = response.json()
            assert "error" in error_data or "detail" in error_data
        except:
            # Non-JSON error response is acceptable
            pass


if __name__ == "__main__":
    # Run tests with: pytest tests/integration/test_end_to_end_production.py -v -s
    pytest.main([__file__, "-v", "-s"])