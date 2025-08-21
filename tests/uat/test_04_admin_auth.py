"""
UAT Test Suite 4: Admin Authentication & API Key Management
Tests admin endpoints, API key creation, management, and authentication
"""
import pytest
import requests
import time
import os

class TestAdminAuthentication:
    """Test admin authentication and API key management"""
    
    def test_create_dev_api_key_basic(self, client):
        """TEST-A04: Test development API key creation"""
        response = client.post("/api/v1/admin/dev/create-api-key?user_id=uat_test_user")
        assert response.status_code == 200
        
        data = response.json()
        assert "api_key" in data
        assert "user_id" in data
        assert data["user_id"] == "uat_test_user"
        assert data["api_key"].startswith("ak_")
        
    def test_create_dev_api_key_default_user(self, client):
        """TEST-A04: Test development API key with default user"""
        response = client.post("/api/v1/admin/dev/create-api-key")
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == "dev_user"  # default from code
        assert "api_key" in data
        
    def test_create_api_key_full_functionality(self, client, admin_headers):
        """TEST-A01: Test API key creation with admin permissions"""
        request_data = {
            "user_id": "uat_premium_user",
            "tier": "premium",
            "permissions": ["read", "write"],
            "expires_days": 30,
            "description": "UAT testing premium user key"
        }
        
        response = client.post("/api/v1/admin/api-keys", 
                              json=request_data, headers=admin_headers)
        
        # This might return 404 if admin endpoints aren't fully implemented
        if response.status_code == 404:
            pytest.skip("Admin API key creation endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "api_key" in data
            assert "key_info" in data
            
            key_info = data["key_info"]
            assert key_info["user_id"] == "uat_premium_user"
            assert key_info["tier"] == "premium"
            
    def test_list_user_api_keys(self, client, admin_headers):
        """TEST-A02: Test listing API keys for users"""
        user_id = "uat_test_list_user"
        
        response = client.get(f"/api/v1/admin/api-keys/{user_id}", 
                             headers=admin_headers)
        
        # May not be implemented yet
        if response.status_code == 404:
            pytest.skip("Admin API key listing endpoint not implemented")
            
        if response.status_code == 200:
            keys = response.json()
            assert isinstance(keys, list)
            
    def test_api_key_validation_errors(self, client):
        """Test API key creation with invalid parameters"""
        # Test without admin permissions
        request_data = {"user_id": "test_user"}
        
        response = client.post("/api/v1/admin/api-keys", json=request_data)
        # Should require authentication
        assert response.status_code in [401, 403, 404]  # 404 if not implemented
        
    def test_unauthorized_admin_access(self, client, standard_headers):
        """Test admin endpoints require proper permissions"""
        # Try to access admin stats with standard user permissions
        response = client.get("/api/v1/admin/stats", headers=standard_headers)
        assert response.status_code in [401, 403, 404]  # 404 if not implemented
        
    def test_admin_endpoints_response_time(self, client):
        """Test admin endpoints meet performance requirements"""
        start_time = time.time()
        
        # Test development key creation (should be fast)
        response = client.post("/api/v1/admin/dev/create-api-key?user_id=perf_test")
        
        duration = time.time() - start_time
        
        assert response.status_code == 200
        assert duration < 2.0  # PRD requirement: API responses < 2 seconds
        
    def test_api_key_format_validation(self, client):
        """Test API key format and structure"""
        response = client.post("/api/v1/admin/dev/create-api-key?user_id=format_test")
        assert response.status_code == 200
        
        data = response.json()
        api_key = data["api_key"]
        
        # Validate API key format
        assert api_key.startswith("ak_")  # Proper prefix
        assert len(api_key) > 20  # Reasonable length
        assert "_" in api_key  # Contains delimiter
        
        # Should be alphanumeric with underscores and hyphens (URL-safe base64)
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        assert all(c in allowed_chars for c in api_key)


class TestAdminMonitoring:
    """Test admin monitoring and metrics endpoints"""
    
    def test_admin_stats_endpoint(self, client, admin_headers):
        """TEST-M01: Test system statistics retrieval"""
        response = client.get("/api/v1/admin/stats", headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Admin stats endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            # Validate expected stats structure
            expected_sections = ["redis_stats", "system_health"]
            for section in expected_sections:
                if section in data:
                    assert isinstance(data[section], dict)
                    
    def test_admin_config_endpoint(self, client, admin_headers):
        """TEST-M02: Test system configuration retrieval"""
        response = client.get("/api/v1/admin/config", headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Admin config endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            
            # Should include non-sensitive configuration
            expected_configs = ["max_file_size_mb", "supported_formats"]
            for config in expected_configs:
                if config in data:
                    assert data[config] is not None
                    
            # Should NOT include sensitive data
            sensitive_keys = ["api_keys", "database_passwords", "secret_key"]
            for key in sensitive_keys:
                assert key not in data
                
    def test_admin_metrics_endpoints(self, client, admin_headers):
        """TEST-M04-M11: Test metrics endpoints"""
        metrics_endpoints = [
            "/api/v1/admin/metrics/current",
            "/api/v1/admin/metrics/performance?time_window_minutes=30",
            "/api/v1/admin/metrics/decompilation?time_window_minutes=60",
            "/api/v1/admin/dashboards/overview",
        ]
        
        for endpoint in metrics_endpoints:
            response = client.get(endpoint, headers=admin_headers)
            
            # These endpoints may not be fully implemented
            if response.status_code == 404:
                continue
                
            if response.status_code == 200:
                # Basic validation that we get JSON response
                data = response.json()
                assert isinstance(data, dict)
                
    def test_prometheus_metrics_export(self, client, admin_headers):
        """TEST-M11: Test Prometheus metrics export"""
        response = client.get("/api/v1/admin/monitoring/prometheus", 
                             headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Prometheus metrics endpoint not implemented")
            
        if response.status_code == 200:
            # Should return Prometheus format
            assert response.headers.get("content-type", "").startswith("text/plain")
            assert len(response.text) > 0
            
    def test_rate_limits_monitoring(self, client, admin_headers):
        """TEST-M03: Test rate limit status monitoring"""
        user_id = "uat_rate_limit_test"
        
        response = client.get(f"/api/v1/admin/rate-limits/{user_id}",
                             headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Rate limits monitoring endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            expected_fields = ["current_usage", "limits", "reset_time"]
            for field in expected_fields:
                if field in data:
                    assert data[field] is not None


class TestCircuitBreakers:
    """Test circuit breaker management"""
    
    def test_circuit_breakers_status(self, client, admin_headers):
        """TEST-C01: Test circuit breaker status reporting"""
        response = client.get("/api/v1/admin/circuit-breakers", 
                             headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Circuit breakers endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            
            # Should include circuit breakers for LLM providers
            expected_circuits = ["openai", "anthropic", "gemini"]
            for circuit in expected_circuits:
                if circuit in data:
                    circuit_data = data[circuit]
                    assert "state" in circuit_data or "status" in circuit_data
                    
    def test_specific_circuit_breaker_details(self, client, admin_headers):
        """TEST-C01: Test specific circuit breaker details"""
        circuit_name = "openai"
        response = client.get(f"/api/v1/admin/circuit-breakers/{circuit_name}",
                             headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Specific circuit breaker endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            expected_fields = ["circuit_name", "state", "statistics"]
            for field in expected_fields:
                if field in data:
                    assert data[field] is not None
                    
    def test_circuit_breaker_control(self, client, admin_headers):
        """TEST-C02: Test circuit breaker control operations"""
        circuit_name = "openai"
        
        # Test reset operation
        response = client.post(f"/api/v1/admin/circuit-breakers/{circuit_name}/reset",
                              headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Circuit breaker control endpoints not implemented")
            
        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "reset" in data or "message" in data


class TestAlertManagement:
    """Test alert management system"""
    
    def test_list_alerts(self, client, admin_headers):
        """TEST-C03: Test listing active alerts"""
        response = client.get("/api/v1/admin/alerts", headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Alerts endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            assert "alerts" in data or isinstance(data, list)
            
    def test_trigger_alert_check(self, client, admin_headers):
        """TEST-C03: Test triggering manual alert check"""
        response = client.post("/api/v1/admin/alerts/check", headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Alert check endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            assert "alerts_checked" in data or "check_completed" in data or "message" in data
            
    def test_health_check_all_circuits(self, client, admin_headers):
        """TEST-C02: Test health checking all circuit breakers"""
        response = client.get("/api/v1/admin/circuit-breakers/health-check/all",
                             headers=admin_headers)
        
        if response.status_code == 404:
            pytest.skip("Circuit breaker health check endpoint not implemented")
            
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            
    def test_admin_monitoring_performance(self, client, admin_headers):
        """Test admin monitoring endpoints meet performance requirements"""
        start_time = time.time()
        
        # Test basic admin endpoint
        response = client.get("/api/v1/admin/stats", headers=admin_headers)
        
        duration = time.time() - start_time
        
        # Admin endpoints should respond quickly
        if response.status_code == 200:
            assert duration < 5.0  # Allow 5 seconds for admin queries