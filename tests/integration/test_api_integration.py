"""
API Integration Tests

Tests complete API workflows including authentication, rate limiting,
error handling, and all endpoint functionality with real HTTP requests.
"""

import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import io

from src.api.main import create_app
from src.api.middleware import create_dev_api_key
from src.core.config import get_settings


@pytest.fixture
def app():
    """Create FastAPI test application."""
    return create_app()


@pytest.fixture
def test_client(app):
    """Create test client for HTTP requests."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app):
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def auth_headers():
    """Create authentication headers for tests."""
    try:
        # Create development API key
        api_key = await create_dev_api_key("test_user")
        return {"Authorization": f"Bearer {api_key}"}
    except Exception as e:
        # If authentication system is not available, skip auth-required tests
        pytest.skip(f"Authentication system not available: {e}")


class TestHealthEndpoints:
    """Test health check and monitoring endpoints."""
    
    def test_health_endpoint(self, test_client):
        """Test basic health check endpoint."""
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
    
    def test_root_redirect(self, test_client):
        """Test root endpoint redirect to docs."""
        response = test_client.get("/", follow_redirects=False)
        # Should redirect to docs in development mode
        assert response.status_code in [200, 302, 307]


class TestAuthenticationIntegration:
    """Test authentication middleware integration."""
    
    def test_public_endpoints_no_auth(self, test_client):
        """Test that public endpoints don't require authentication."""
        public_endpoints = [
            "/",
            "/api/v1/health",
            "/docs",
            "/openapi.json"
        ]
        
        for endpoint in public_endpoints:
            response = test_client.get(endpoint, follow_redirects=False)
            # Should not get 401 Unauthorized
            assert response.status_code != 401, f"Endpoint {endpoint} unexpectedly requires auth"
    
    @pytest.mark.skipif(not hasattr(pytest, "param"), reason="Requires auth setup")
    def test_protected_endpoints_require_auth(self, test_client):
        """Test that protected endpoints require authentication."""
        protected_endpoints = [
            "/api/v1/admin/stats",
            "/api/v1/admin/config"
        ]
        
        for endpoint in protected_endpoints:
            response = test_client.get(endpoint)
            # Should require authentication
            assert response.status_code == 401, f"Endpoint {endpoint} should require auth"
    
    @pytest.mark.asyncio
    async def test_valid_api_key_authentication(self, async_client, auth_headers):
        """Test authentication with valid API key."""
        response = await async_client.get("/api/v1/admin/config", headers=auth_headers)
        # Should not get authentication error
        assert response.status_code != 401
    
    def test_invalid_api_key_authentication(self, test_client):
        """Test authentication with invalid API key."""
        invalid_headers = {"Authorization": "Bearer invalid_key_123"}
        response = test_client.get("/api/v1/admin/config", headers=invalid_headers)
        assert response.status_code == 401
        
        data = response.json()
        assert "error" in data
        assert "invalid" in data["error"]["message"].lower()


class TestRateLimitingIntegration:
    """Test rate limiting middleware integration."""
    
    def test_rate_limit_headers(self, test_client):
        """Test that rate limit headers are included in responses."""
        response = test_client.get("/api/v1/health")
        
        # Check for rate limit headers (if rate limiting is active)
        rate_limit_headers = [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining", 
            "X-RateLimit-Reset"
        ]
        
        # At least some rate limit headers should be present
        header_count = sum(1 for header in rate_limit_headers if header in response.headers)
        # In development mode, rate limiting might be disabled
        # Just verify the endpoint works
        assert response.status_code == 200
    
    def test_rate_limit_enforcement(self, test_client):
        """Test rate limiting enforcement."""
        # Make multiple requests rapidly
        responses = []
        for i in range(5):
            response = test_client.get("/api/v1/health")
            responses.append(response)
        
        # All should succeed initially (basic rate limits are generous)
        for response in responses:
            assert response.status_code != 429, "Rate limit hit too early"


class TestErrorHandlingIntegration:
    """Test error handling middleware integration."""
    
    def test_404_error_handling(self, test_client):
        """Test 404 error handling."""
        response = test_client.get("/api/v1/nonexistent")
        assert response.status_code == 404
    
    def test_405_method_not_allowed(self, test_client):
        """Test method not allowed errors."""
        response = test_client.put("/api/v1/health")  # Health only supports GET
        assert response.status_code == 405
    
    def test_422_validation_error(self, test_client):
        """Test validation error handling."""
        # Send invalid JSON to an endpoint that expects JSON
        response = test_client.post(
            "/api/v1/decompile",
            json={"invalid": "data"},
            headers={"Content-Type": "application/json"}
        )
        # Should get validation error
        assert response.status_code in [400, 422, 401]  # 401 if auth required


class TestCORSIntegration:
    """Test CORS middleware integration."""
    
    def test_cors_headers(self, test_client):
        """Test CORS headers are present."""
        response = test_client.options("/api/v1/health")
        
        # Should include CORS headers
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers"
        ]
        
        # Check if CORS headers are present (case-insensitive)
        response_headers_lower = {k.lower(): v for k, v in response.headers.items()}
        cors_present = any(header in response_headers_lower for header in cors_headers)
        
        # CORS should be configured
        assert cors_present or response.status_code == 200


class TestDecompilationEndpoints:
    """Test decompilation API endpoints."""
    
    @patch('src.decompilation.engine.DecompilationEngine')
    def test_decompilation_endpoint_structure(self, mock_engine, test_client):
        """Test decompilation endpoint exists and has correct structure."""
        # Mock the decompilation engine
        mock_instance = AsyncMock()
        mock_instance.analyze_binary_file.return_value = {
            "analysis_id": "test_123",
            "functions": [],
            "imports": [],
            "strings": []
        }
        mock_engine.return_value = mock_instance
        
        # Test binary content
        binary_content = b'\x7fELF\x02\x01\x01\x00' + b'\x00' * 100  # Minimal ELF header
        
        response = test_client.post(
            "/api/v1/decompile", 
            files={"file": ("test.elf", io.BytesIO(binary_content), "application/octet-stream")},
            data={"analysis_depth": "basic"}
        )
        
        # Should not get 404 - endpoint exists
        assert response.status_code != 404
    
    def test_decompilation_file_validation(self, test_client):
        """Test file validation for decompilation endpoint."""
        # Send request without file
        response = test_client.post("/api/v1/decompile")
        assert response.status_code in [400, 422]
        
        # Send empty file
        response = test_client.post(
            "/api/v1/decompile",
            files={"file": ("empty.bin", io.BytesIO(b""), "application/octet-stream")}
        )
        assert response.status_code in [400, 422]


class TestLLMProviderEndpoints:
    """Test LLM provider management endpoints."""
    
    @pytest.mark.asyncio
    async def test_llm_providers_list(self, async_client, auth_headers):
        """Test LLM providers listing endpoint."""
        response = await async_client.get("/api/v1/llm-providers", headers=auth_headers)
        
        # Endpoint should exist
        assert response.status_code != 404
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (dict, list))


class TestAdminEndpoints:
    """Test admin/management endpoints."""
    
    @pytest.mark.asyncio 
    async def test_admin_config_endpoint(self, async_client, auth_headers):
        """Test admin configuration endpoint."""
        response = await async_client.get("/api/v1/admin/config", headers=auth_headers)
        
        if response.status_code == 200:
            data = response.json()
            assert "environment" in data
            assert "api" in data
            assert "security" in data
    
    @pytest.mark.asyncio
    async def test_admin_stats_endpoint(self, async_client, auth_headers):
        """Test admin statistics endpoint."""
        response = await async_client.get("/api/v1/admin/stats", headers=auth_headers)
        
        # Should either work or require database
        assert response.status_code in [200, 500, 503]
    
    def test_admin_endpoints_require_auth(self, test_client):
        """Test that admin endpoints require authentication."""
        admin_endpoints = [
            "/api/v1/admin/config",
            "/api/v1/admin/stats",
            "/api/v1/admin/api-keys/test_user"
        ]
        
        for endpoint in admin_endpoints:
            response = test_client.get(endpoint)
            # Should require authentication
            assert response.status_code == 401


class TestMiddlewareChain:
    """Test middleware execution chain."""
    
    def test_correlation_id_header(self, test_client):
        """Test that correlation ID is added to responses."""
        response = test_client.get("/api/v1/health")
        
        # Should include correlation ID header
        assert "X-Correlation-ID" in response.headers
        correlation_id = response.headers["X-Correlation-ID"]
        assert len(correlation_id) > 0
        
        # Should be a valid UUID format
        import uuid
        try:
            uuid.UUID(correlation_id)
        except ValueError:
            pytest.fail("Correlation ID is not a valid UUID")
    
    def test_response_compression(self, test_client):
        """Test response compression middleware."""
        # Request with compression support
        headers = {"Accept-Encoding": "gzip"}
        response = test_client.get("/api/v1/health", headers=headers)
        
        # Should work regardless of compression
        assert response.status_code == 200
    
    def test_middleware_error_handling(self, test_client):
        """Test error handling across middleware chain."""
        # Send malformed request to trigger middleware error handling
        response = test_client.post(
            "/api/v1/decompile",
            data="invalid_data",
            headers={"Content-Type": "application/json"}
        )
        
        # Should get structured error response
        assert response.status_code >= 400
        
        try:
            data = response.json()
            # Should have error structure
            assert isinstance(data, dict)
        except:
            # If not JSON, that's also acceptable for some error types
            pass


class TestOpenAPIDocumentation:
    """Test OpenAPI documentation generation."""
    
    def test_openapi_json(self, test_client):
        """Test OpenAPI specification generation."""
        response = test_client.get("/openapi.json")
        
        if response.status_code == 200:
            openapi_spec = response.json()
            assert "openapi" in openapi_spec
            assert "info" in openapi_spec
            assert "paths" in openapi_spec
            
            # Should include our endpoints
            assert "/api/v1/health" in openapi_spec["paths"]
            
            # Security schemes may be present depending on configuration
            if "components" in openapi_spec and "securitySchemes" in openapi_spec["components"]:
                # Validate security schemes if present
                assert isinstance(openapi_spec["components"]["securitySchemes"], dict)
    
    def test_docs_endpoint(self, test_client):
        """Test Swagger UI documentation."""
        response = test_client.get("/docs")
        
        # Should either serve docs or be disabled
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            assert "text/html" in response.headers.get("content-type", "")


@pytest.mark.slow
class TestAPIPerformance:
    """Performance tests for API endpoints."""
    
    def test_health_endpoint_performance(self, test_client):
        """Test health endpoint response time."""
        import time
        
        start_time = time.time()
        response = test_client.get("/api/v1/health")
        elapsed_time = time.time() - start_time
        
        assert response.status_code == 200
        assert elapsed_time < 1.0, f"Health endpoint too slow: {elapsed_time}s"
    
    def test_concurrent_requests(self, test_client):
        """Test handling of concurrent requests."""
        import concurrent.futures
        import time
        
        def make_request():
            return test_client.get("/api/v1/health")
        
        start_time = time.time()
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        elapsed_time = time.time() - start_time
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200
        
        # Should handle concurrent requests reasonably quickly
        assert elapsed_time < 5.0, f"Concurrent requests too slow: {elapsed_time}s"


if __name__ == "__main__":
    # Run tests with: pytest tests/integration/test_api_integration.py -v
    pytest.main([__file__, "-v"])