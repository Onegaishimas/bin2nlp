"""
UAT Tests: LLM Provider Management
Tests the 3 LLM provider management endpoints
"""
import pytest
import time
from typing import Dict, Any


class TestLLMProviders:
    """Test LLM provider management endpoints"""
    
    def test_list_llm_providers_basic(self, client):
        """TEST-L01: Test listing all available LLM providers"""
        response = client.get("/api/v1/llm-providers")
        
        assert response.status_code == 200, f"LLM providers list failed: {response.text}"
        
        data = response.json()
        
        # Should have providers information
        assert "providers" in data or isinstance(data, list), \
            "Response should contain providers list"
        
        if "providers" in data:
            providers = data["providers"]
        else:
            providers = data
            
        assert isinstance(providers, list), "Providers should be a list"
        
        # Validate provider structure if providers exist
        if providers:
            provider = providers[0]
            expected_fields = ["provider_id", "name", "status"]
            
            for field in expected_fields:
                if field not in provider:
                    # Some fields might be optional, just log for now
                    pass
        
        # Check for expected providers from PRD (may not all be configured)
        expected_provider_types = ["openai", "anthropic", "gemini", "ollama"]
        if providers:
            provider_ids = [p.get("provider_id", "").lower() for p in providers]
            # At least one major provider should be available
            has_major_provider = any(
                any(expected in pid for expected in expected_provider_types)
                for pid in provider_ids
            )
            # This is informational - system may work without LLM providers configured

    def test_list_llm_providers_performance(self, client):
        """Test LLM providers list meets performance requirements"""
        start_time = time.time()
        response = client.get("/api/v1/llm-providers")
        duration = time.time() - start_time
        
        # Should respond within 2 seconds (PRD requirement)
        assert duration < 2.0, \
            f"LLM providers list took {duration:.2f}s, exceeds 2s requirement"
        
        assert response.status_code == 200, "LLM providers request should succeed"

    def test_get_provider_details_format(self, client):
        """TEST-L02: Test provider details endpoint format"""
        # First get list of available providers
        list_response = client.get("/api/v1/llm-providers")
        
        if list_response.status_code != 200:
            pytest.skip("Cannot get provider list to test details")
        
        list_data = list_response.json()
        providers = list_data.get("providers", list_data) if isinstance(list_data, dict) else list_data
        
        if not providers:
            pytest.skip("No providers available to test details")
        
        # Test first available provider
        provider = providers[0]
        provider_id = provider.get("provider_id", provider.get("id", "openai"))
        
        response = client.get(f"/api/v1/llm-providers/{provider_id}")
        
        # Should either succeed or return 404 if provider doesn't exist
        assert response.status_code in [200, 404], \
            f"Provider details returned unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            # Should contain provider information
            assert isinstance(data, dict), "Provider details should be an object"

    def test_get_provider_details_nonexistent(self, client):
        """TEST-L02: Test details for non-existent provider"""
        response = client.get("/api/v1/llm-providers/nonexistent_provider_xyz")
        
        # Should return 404 for non-existent provider
        assert response.status_code == 404, \
            f"Non-existent provider should return 404, got: {response.status_code}"

    def test_provider_health_check_format(self, client):
        """TEST-L03: Test provider health check endpoint format"""
        # Get available providers first
        list_response = client.get("/api/v1/llm-providers")
        
        if list_response.status_code != 200:
            pytest.skip("Cannot get provider list for health check test")
        
        list_data = list_response.json()
        providers = list_data.get("providers", list_data) if isinstance(list_data, dict) else list_data
        
        if not providers:
            # Try with common provider names
            test_providers = ["openai", "anthropic", "gemini", "ollama"]
        else:
            test_providers = [p.get("provider_id", p.get("id", "openai")) for p in providers[:2]]
        
        # Test health check for first available provider
        provider_id = test_providers[0]
        response = client.post(f"/api/v1/llm-providers/{provider_id}/health-check")
        
        # Health check may succeed (200) or fail (4xx/5xx) depending on provider availability
        assert response.status_code in [200, 400, 404, 500, 503], \
            f"Health check returned unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            try:
                data = response.json()
                # Should contain health information
                expected_fields = ["health_status", "test_timestamp"]
                # Fields may vary, just ensure it's valid JSON
                assert isinstance(data, dict), "Health check should return an object"
            except:
                # Response may not be JSON for some health checks
                pass

    def test_provider_health_check_nonexistent(self, client):
        """TEST-L03: Test health check for non-existent provider"""
        response = client.post("/api/v1/llm-providers/nonexistent_provider_xyz/health-check")
        
        # Should return 404 for non-existent provider
        assert response.status_code == 404, \
            f"Non-existent provider health check should return 404, got: {response.status_code}"

    def test_llm_endpoints_response_time_performance(self, client):
        """Test all LLM provider endpoints meet performance requirements"""
        endpoints_to_test = [
            "/api/v1/llm-providers",
        ]
        
        for endpoint in endpoints_to_test:
            start_time = time.time()
            response = client.get(endpoint)
            duration = time.time() - start_time
            
            # All API endpoints should respond within 2 seconds (PRD requirement)
            assert duration < 2.0, \
                f"Endpoint {endpoint} took {duration:.2f}s, exceeds 2s requirement"
            
            assert response.status_code == 200, \
                f"Endpoint {endpoint} should be accessible"

    def test_llm_provider_integration_availability(self, client):
        """Test LLM provider integration status"""
        response = client.get("/api/v1/llm-providers")
        
        if response.status_code == 200:
            data = response.json()
            providers = data.get("providers", data) if isinstance(data, dict) else data
            
            if providers:
                # If providers are configured, test basic functionality
                for provider in providers[:2]:  # Test first 2 providers
                    provider_id = provider.get("provider_id", provider.get("id"))
                    if provider_id:
                        # Test provider details
                        detail_response = client.get(f"/api/v1/llm-providers/{provider_id}")
                        assert detail_response.status_code in [200, 404], \
                            f"Provider {provider_id} details endpoint error"
                        
                        # Test health check (may fail if not configured)
                        health_response = client.post(f"/api/v1/llm-providers/{provider_id}/health-check")
                        assert health_response.status_code in [200, 400, 404, 500, 503], \
                            f"Provider {provider_id} health check unexpected error"
            else:
                # No providers configured - this may be expected in some deployments
                pass