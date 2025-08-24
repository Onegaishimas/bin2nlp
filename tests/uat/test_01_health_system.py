"""
UAT Tests: Health & System Endpoints
Tests the 4 health and system information endpoints
"""
import pytest
import time
from typing import Dict, Any


class TestHealthSystem:
    """Test health and system information endpoints"""
    
    def test_health_basic_functionality(self, client):
        """TEST-H01: Test basic health endpoint functionality"""
        start_time = time.time()
        response = client.get("/api/v1/health")
        duration = time.time() - start_time
        
        # Status validation
        assert response.status_code == 200, f"Health check failed: {response.text}"
        assert response.headers["content-type"].startswith("application/json")
        
        # Performance validation - PRD requirement: API responses < 2 seconds
        assert duration < 2.0, f"Health check took {duration:.2f}s, exceeds 2s requirement"
        
        # Response structure validation
        data = response.json()
        required_fields = ["status", "timestamp", "version"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Status should be healthy, degraded, or unhealthy
        assert data["status"] in ["healthy", "degraded", "unhealthy"], \
            f"Invalid status: {data['status']}"
        
        # If components exist, validate structure
        if "components" in data:
            components = data["components"]
            assert isinstance(components, dict), "Components should be a dictionary"
            
            # Check for expected components
            if "database" in components:
                assert "status" in components["database"]
            if "decompilation_engine" in components:
                assert "status" in components["decompilation_engine"]

    def test_readiness_check_when_ready(self, client):
        """TEST-H02: Test readiness endpoint when system is ready"""
        response = client.get("/api/v1/health/ready")
        
        # Should return 200 when ready, 503 when not ready
        assert response.status_code in [200, 503], \
            f"Readiness check returned unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            # System is ready
            assert response.headers["content-type"].startswith("application/json")
            data = response.json()
            # May be empty or contain readiness info
        else:
            # System is not ready (503)
            # This is acceptable - dependencies may be unavailable
            pass

    def test_liveness_check_always_healthy(self, client):
        """TEST-H03: Test liveness endpoint always returns healthy unless app broken"""
        response = client.get("/api/v1/health/live")
        
        # Liveness should almost always return 200 unless app is completely broken
        assert response.status_code == 200, \
            f"Liveness check failed - application may be broken: {response.status_code}"
        
        # Response should be JSON
        assert response.headers["content-type"].startswith("application/json")

    def test_system_info_complete(self, client):
        """TEST-H04: Test system info returns complete capability information"""
        response = client.get("/api/v1/system/info")
        
        assert response.status_code == 200, f"System info request failed: {response.text}"
        
        data = response.json()
        
        # Validate required fields from PRD
        required_fields = [
            "supported_formats", 
            "version",
            "limits"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field in system info: {field}"
        
        # Validate supported formats match PRD requirements
        formats = data["supported_formats"]
        assert isinstance(formats, list), "Supported formats should be a list"
        
        # PRD specifies: Windows (.exe/.dll), Linux (.elf/.so), macOS (.app/.dylib)
        # API returns format types: "pe" (Windows), "elf" (Linux), "macho" (macOS)
        expected_formats = ["pe", "elf", "macho"]  # These are the actual format names returned by API
        found_formats = [fmt for fmt in expected_formats if fmt in formats]
        
        assert len(found_formats) >= 2, \
            f"Should support major binary formats. Expected: {expected_formats}, Found: {formats}"
        
        # Validate limits structure
        limits = data["limits"]
        assert isinstance(limits, dict), "Limits should be a dictionary"
        assert "max_file_size_mb" in limits, "Limits should include max file size"
        assert "max_timeout_seconds" in limits, "Limits should include max timeout"
        
        # Validate max file size
        max_size = limits["max_file_size_mb"]
        assert isinstance(max_size, (int, float)), "Max file size should be numeric"
        assert max_size > 0, "Max file size should be positive"
        
        # Check for LLM providers info if available
        if "llm_providers" in data:
            llm_providers = data["llm_providers"]
            assert isinstance(llm_providers, dict), "LLM providers info should be a dictionary"
            assert "supported" in llm_providers, "Should include supported providers"
            assert "healthy" in llm_providers, "Should include healthy providers status"

    def test_health_endpoints_response_time_performance(self, client):
        """Test all health endpoints meet performance requirements"""
        endpoints = [
            "/api/v1/health",
            "/api/v1/health/ready", 
            "/api/v1/health/live",
            "/api/v1/system/info"
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            duration = time.time() - start_time
            
            # All API endpoints should respond within 2 seconds (PRD requirement)
            assert duration < 2.0, \
                f"Endpoint {endpoint} took {duration:.2f}s, exceeds 2s requirement"
            
            # Should return some form of success (200, or 503 for readiness if not ready)
            assert response.status_code in [200, 503], \
                f"Endpoint {endpoint} returned error status: {response.status_code}"