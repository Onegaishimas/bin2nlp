"""
Unit tests for API authentication models.

Tests the authentication, API key management, rate limiting, and 
error handling models for the API authentication system.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from src.models.api.auth import (
    APIKeyRequest, APIKeyResponse, APIKeyInfo, RateLimitInfo, 
    ErrorResponse, AuthenticationStatus
)


class TestAPIKeyRequest:
    """Test cases for APIKeyRequest model."""
    
    def test_basic_instantiation(self):
        """Test basic API key request."""
        request = APIKeyRequest(
            name="Test API Key",
            description="API key for testing purposes"
        )
        
        assert request.name == "Test API Key"
        assert request.description == "API key for testing purposes"
        assert request.permissions == ["read", "write"]  # Default permissions
        assert request.rate_limit_tier == "standard"
        assert request.expires_in_days is None
    
    def test_with_custom_permissions(self):
        """Test API key request with custom permissions."""
        request = APIKeyRequest(
            name="Read-only Key",
            description="Limited permissions key",
            permissions=["read"],
            rate_limit_tier="basic"
        )
        
        assert request.permissions == ["read"]
        assert request.rate_limit_tier == "basic"
    
    def test_with_expiry(self):
        """Test API key request with expiry."""
        request = APIKeyRequest(
            name="Temporary Key",
            description="Short-lived key for demo",
            expires_in_days=30,
            rate_limit_tier="premium"
        )
        
        assert request.expires_in_days == 30
        assert request.rate_limit_tier == "premium"
    
    def test_permission_validation(self):
        """Test permission validation."""
        valid_permissions = ["read", "write", "admin"]
        
        # Valid permissions
        request = APIKeyRequest(
            name="Test Key",
            permissions=["read", "write"]
        )
        assert set(request.permissions).issubset(set(valid_permissions))
        
        # Empty permissions should default to read/write
        request = APIKeyRequest(
            name="Default Key",
            permissions=[]
        )
        assert request.permissions == ["read", "write"]
        
        # Invalid permission should raise error
        with pytest.raises(ValueError, match="Invalid permission"):
            APIKeyRequest(
                name="Invalid Key",
                permissions=["invalid_permission"]
            )
    
    def test_rate_limit_tier_validation(self):
        """Test rate limit tier validation."""
        valid_tiers = ["basic", "standard", "premium", "enterprise"]
        
        for tier in valid_tiers:
            request = APIKeyRequest(
                name="Test Key",
                rate_limit_tier=tier
            )
            assert request.rate_limit_tier == tier
        
        # Invalid tier should raise error
        with pytest.raises(ValueError, match="Invalid rate limit tier"):
            APIKeyRequest(
                name="Test Key",
                rate_limit_tier="invalid_tier"
            )
    
    def test_name_validation(self):
        """Test API key name validation."""
        # Valid name
        request = APIKeyRequest(name="Valid API Key Name")
        assert request.name == "Valid API Key Name"
        
        # Name too short
        with pytest.raises(ValueError, match="name must be at least"):
            APIKeyRequest(name="ab")
        
        # Name too long
        with pytest.raises(ValueError, match="name must not exceed"):
            APIKeyRequest(name="a" * 101)
        
        # Empty name
        with pytest.raises(ValueError, match="name cannot be empty"):
            APIKeyRequest(name="")
    
    def test_expiry_validation(self):
        """Test expiry validation."""
        # Valid expiry periods
        valid_days = [1, 30, 90, 365]
        
        for days in valid_days:
            request = APIKeyRequest(
                name="Test Key",
                expires_in_days=days
            )
            assert request.expires_in_days == days
        
        # Negative days should raise error
        with pytest.raises(ValueError, match="expires_in_days must be positive"):
            APIKeyRequest(
                name="Test Key",
                expires_in_days=-1
            )
        
        # Too long expiry should raise error
        with pytest.raises(ValueError, match="expires_in_days cannot exceed"):
            APIKeyRequest(
                name="Test Key",
                expires_in_days=10000
            )


class TestAPIKeyResponse:
    """Test cases for APIKeyResponse model."""
    
    def test_basic_instantiation(self):
        """Test basic API key response."""
        response = APIKeyResponse(
            success=True,
            api_key="ak_1234567890abcdef",
            key_id="key_abc123"
        )
        
        assert response.success is True
        assert response.api_key == "ak_1234567890abcdef"
        assert response.key_id == "key_abc123"
        assert isinstance(response.created_at, datetime)
        assert response.expires_at is None
    
    def test_with_expiry(self):
        """Test API key response with expiry."""
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        response = APIKeyResponse(
            success=True,
            api_key="ak_temporary_key",
            key_id="key_temp123",
            expires_at=expires_at
        )
        
        assert response.expires_at == expires_at
        assert not response.is_expired()
        assert response.days_until_expiry() > 0
    
    def test_with_rate_limit_info(self):
        """Test API key response with rate limit information."""
        rate_limit_info = {
            "tier": "premium",
            "requests_per_minute": 300,
            "requests_per_day": 50000,
            "burst_allowance": 50
        }
        
        response = APIKeyResponse(
            success=True,
            api_key="ak_premium_key",
            key_id="key_premium123",
            rate_limit_info=rate_limit_info
        )
        
        assert response.rate_limit_info == rate_limit_info
        assert response.rate_limit_info["tier"] == "premium"
        assert response.rate_limit_info["requests_per_minute"] == 300
    
    def test_failed_response(self):
        """Test failed API key creation response."""
        response = APIKeyResponse(
            success=False,
            api_key=None,
            key_id=None,
            error_message="Maximum number of API keys reached",
            error_code="MAX_KEYS_EXCEEDED"
        )
        
        assert response.success is False
        assert response.api_key is None
        assert response.key_id is None
        assert response.error_message == "Maximum number of API keys reached"
        assert response.error_code == "MAX_KEYS_EXCEEDED"
    
    def test_security_warnings(self):
        """Test security warning generation."""
        response = APIKeyResponse(
            success=True,
            api_key="ak_example_key",
            key_id="key_example"
        )
        
        warnings = response.get_security_warnings()
        assert isinstance(warnings, list)
        assert any("Store this API key securely" in warning for warning in warnings)


class TestAPIKeyInfo:
    """Test cases for APIKeyInfo model."""
    
    def test_basic_instantiation(self):
        """Test basic API key info."""
        info = APIKeyInfo(
            key_id="key_123",
            name="Production API Key",
            permissions=["read", "write"],
            rate_limit_tier="standard",
            created_at=datetime.now(timezone.utc)
        )
        
        assert info.key_id == "key_123"
        assert info.name == "Production API Key"
        assert info.permissions == ["read", "write"]
        assert info.rate_limit_tier == "standard"
        assert info.is_active is True  # Default
        assert info.expires_at is None
    
    def test_with_usage_statistics(self):
        """Test API key info with usage statistics."""
        info = APIKeyInfo(
            key_id="key_456",
            name="Analytics Key",
            permissions=["read"],
            rate_limit_tier="premium",
            created_at=datetime.now(timezone.utc),
            total_requests=15420,
            requests_today=142,
            last_used_at=datetime.now(timezone.utc) - timedelta(hours=2)
        )
        
        assert info.total_requests == 15420
        assert info.requests_today == 142
        assert info.last_used_at is not None
    
    def test_expiry_status(self):
        """Test expiry status checks."""
        # Active key without expiry
        active_info = APIKeyInfo(
            key_id="key_active",
            name="Active Key",
            permissions=["read"],
            rate_limit_tier="standard",
            created_at=datetime.now(timezone.utc)
        )
        
        assert not active_info.is_expired()
        assert active_info.is_active
        
        # Expired key
        expired_info = APIKeyInfo(
            key_id="key_expired",
            name="Expired Key",
            permissions=["read"],
            rate_limit_tier="standard",
            created_at=datetime.now(timezone.utc) - timedelta(days=100),
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        
        assert expired_info.is_expired()
        assert expired_info.days_since_expiry() > 0
    
    def test_deactivated_key(self):
        """Test deactivated key status."""
        info = APIKeyInfo(
            key_id="key_deactivated",
            name="Deactivated Key",
            permissions=["read"],
            rate_limit_tier="standard",
            created_at=datetime.now(timezone.utc),
            is_active=False,
            deactivated_at=datetime.now(timezone.utc),
            deactivation_reason="Security concern"
        )
        
        assert info.is_active is False
        assert info.deactivated_at is not None
        assert info.deactivation_reason == "Security concern"
    
    def test_usage_analytics(self):
        """Test usage analytics calculation."""
        info = APIKeyInfo(
            key_id="key_analytics",
            name="Analytics Key",
            permissions=["read", "write"],
            rate_limit_tier="premium",
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
            total_requests=30000,
            requests_today=500
        )
        
        analytics = info.get_usage_analytics()
        assert isinstance(analytics, dict)
        assert "daily_average" in analytics
        assert "usage_trend" in analytics
        assert analytics["total_requests"] == 30000


class TestRateLimitInfo:
    """Test cases for RateLimitInfo model."""
    
    def test_basic_instantiation(self):
        """Test basic rate limit info."""
        rate_limit = RateLimitInfo(
            requests_per_minute=100,
            requests_per_day=10000,
            burst_allowance=20
        )
        
        assert rate_limit.requests_per_minute == 100
        assert rate_limit.requests_per_day == 10000
        assert rate_limit.burst_allowance == 20
        assert rate_limit.current_usage == 0
        assert rate_limit.reset_time is None
    
    def test_with_current_usage(self):
        """Test rate limit info with current usage."""
        reset_time = datetime.now(timezone.utc) + timedelta(seconds=60)
        
        rate_limit = RateLimitInfo(
            requests_per_minute=100,
            requests_per_day=10000,
            burst_allowance=20,
            current_usage=75,
            reset_time=reset_time
        )
        
        assert rate_limit.current_usage == 75
        assert rate_limit.reset_time == reset_time
        assert rate_limit.remaining_requests() == 25
        assert rate_limit.seconds_until_reset() > 0
    
    def test_rate_limit_calculations(self):
        """Test rate limit calculation methods."""
        rate_limit = RateLimitInfo(
            requests_per_minute=60,
            requests_per_day=5000,
            current_usage=45
        )
        
        assert rate_limit.remaining_requests() == 15
        assert rate_limit.usage_percentage() == 75.0  # 45/60 * 100
        assert rate_limit.is_near_limit(threshold=0.8) is True  # 75% > 80%
        assert rate_limit.is_exceeded() is False
    
    def test_exceeded_limits(self):
        """Test exceeded rate limits."""
        rate_limit = RateLimitInfo(
            requests_per_minute=100,
            requests_per_day=1000,
            current_usage=105  # Exceeded minute limit
        )
        
        assert rate_limit.is_exceeded() is True
        assert rate_limit.remaining_requests() == 0
        assert rate_limit.usage_percentage() > 100
    
    def test_tier_based_limits(self):
        """Test different rate limit tiers."""
        # Basic tier
        basic_limits = RateLimitInfo.for_tier("basic")
        assert basic_limits.requests_per_minute == 10
        
        # Premium tier
        premium_limits = RateLimitInfo.for_tier("premium")
        assert premium_limits.requests_per_minute == 300
        assert premium_limits.burst_allowance == 50
        
        # Enterprise tier
        enterprise_limits = RateLimitInfo.for_tier("enterprise")
        assert enterprise_limits.requests_per_minute == 1000
    
    def test_header_generation(self):
        """Test rate limit header generation."""
        rate_limit = RateLimitInfo(
            requests_per_minute=100,
            current_usage=30,
            reset_time=datetime.now(timezone.utc) + timedelta(seconds=45)
        )
        
        headers = rate_limit.to_headers()
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "70"


class TestErrorResponse:
    """Test cases for ErrorResponse model."""
    
    def test_basic_instantiation(self):
        """Test basic validation error detail."""
        error = ErrorResponse(
            field="email",
            message="Invalid email format",
            code="INVALID_FORMAT"
        )
        
        assert error.field == "email"
        assert error.message == "Invalid email format"
        assert error.code == "INVALID_FORMAT"
        assert error.invalid_value is None
    
    def test_with_invalid_value(self):
        """Test validation error with invalid value."""
        error = ErrorResponse(
            field="timeout_seconds",
            message="Value must be between 30 and 3600",
            code="OUT_OF_RANGE",
            invalid_value=7200
        )
        
        assert error.invalid_value == 7200
        assert error.field == "timeout_seconds"
    
    def test_nested_field_errors(self):
        """Test validation errors for nested fields."""
        error = ErrorResponse(
            field="config.analysis_depth",
            message="Invalid analysis depth",
            code="INVALID_ENUM_VALUE",
            invalid_value="super_deep"
        )
        
        assert "config.analysis_depth" == error.field
        assert error.is_nested_field()
        assert error.get_parent_field() == "config"
        assert error.get_field_name() == "analysis_depth"
    
    def test_error_severity(self):
        """Test error severity classification."""
        # Critical error
        critical_error = ErrorResponse(
            field="api_key",
            message="API key is required",
            code="REQUIRED_FIELD"
        )
        assert critical_error.get_severity() == "error"
        
        # Warning level
        warning_error = ErrorResponse(
            field="description",
            message="Description is recommended but not required",
            code="OPTIONAL_FIELD_MISSING"
        )
        assert warning_error.get_severity() == "warning"


class TestErrorResponse:
    """Test cases for ErrorResponse model."""
    
    def test_basic_error_response(self):
        """Test basic error response."""
        response = ErrorResponse(
            success=False,
            error_code="INVALID_REQUEST",
            error_message="The request is invalid",
            request_id="req_123456"
        )
        
        assert response.success is False
        assert response.error_code == "INVALID_REQUEST"
        assert response.error_message == "The request is invalid"
        assert response.request_id == "req_123456"
        assert isinstance(response.timestamp, datetime)
    
    def test_validation_error_response(self):
        """Test validation error response."""
        validation_errors = [
            ErrorResponse(
                field="filename",
                message="Filename is required",
                code="REQUIRED_FIELD"
            ),
            ErrorResponse(
                field="file_size",
                message="File size must be positive",
                code="INVALID_VALUE",
                invalid_value=0
            )
        ]
        
        response = ErrorResponse(
            success=False,
            error_code="VALIDATION_FAILED",
            error_message="Request validation failed",
            validation_errors=validation_errors
        )
        
        assert len(response.validation_errors) == 2
        assert response.validation_errors[0].field == "filename"
        assert response.validation_errors[1].invalid_value == 0
    
    def test_rate_limit_error_response(self):
        """Test rate limit error response."""
        rate_limit_info = RateLimitInfo(
            requests_per_minute=100,
            current_usage=100,
            reset_time=datetime.now(timezone.utc) + timedelta(seconds=60)
        )
        
        response = ErrorResponse(
            success=False,
            error_code="RATE_LIMIT_EXCEEDED",
            error_message="Rate limit exceeded",
            rate_limit_info=rate_limit_info,
            retry_after_seconds=60
        )
        
        assert response.rate_limit_info is not None
        assert response.retry_after_seconds == 60
        assert response.rate_limit_info.is_exceeded() is True
    
    def test_error_response_factory_methods(self):
        """Test error response factory methods."""
        # Authentication error
        auth_error = ErrorResponse.authentication_failed("Invalid API key")
        assert auth_error.error_code == "AUTHENTICATION_FAILED"
        assert auth_error.error_message == "Invalid API key"
        
        # Permission error
        perm_error = ErrorResponse.permission_denied("Insufficient permissions")
        assert perm_error.error_code == "PERMISSION_DENIED"
        assert perm_error.error_message == "Insufficient permissions"
        
        # Not found error
        not_found_error = ErrorResponse.not_found("Resource not found")
        assert not_found_error.error_code == "NOT_FOUND"
        assert not_found_error.error_message == "Resource not found"
        
        # Internal server error
        server_error = ErrorResponse.internal_server_error("An unexpected error occurred")
        assert server_error.error_code == "INTERNAL_SERVER_ERROR"
        assert server_error.error_message == "An unexpected error occurred"
    
    def test_error_response_with_documentation_links(self):
        """Test error response with help documentation."""
        response = ErrorResponse(
            success=False,
            error_code="INVALID_FILE_FORMAT",
            error_message="Unsupported file format",
            documentation_url="https://docs.bin2nlp.com/supported-formats",
            suggested_action="Please upload a supported binary format (PE, ELF, Mach-O)"
        )
        
        assert response.documentation_url == "https://docs.bin2nlp.com/supported-formats"
        assert response.suggested_action is not None
        assert "supported binary format" in response.suggested_action


class TestAuthenticationStatus:
    """Test cases for AuthenticationStatus model."""
    
    def test_authenticated_status(self):
        """Test authenticated status."""
        status = AuthenticationStatus(
            is_authenticated=True,
            api_key_id="key_123",
            permissions=["read", "write"],
            rate_limit_tier="premium"
        )
        
        assert status.is_authenticated is True
        assert status.api_key_id == "key_123"
        assert status.permissions == ["read", "write"]
        assert status.rate_limit_tier == "premium"
        assert status.authentication_error is None
    
    def test_unauthenticated_status(self):
        """Test unauthenticated status."""
        status = AuthenticationStatus(
            is_authenticated=False,
            authentication_error="Invalid API key provided"
        )
        
        assert status.is_authenticated is False
        assert status.api_key_id is None
        assert status.permissions == []
        assert status.authentication_error == "Invalid API key provided"
    
    def test_permission_checks(self):
        """Test permission checking methods."""
        status = AuthenticationStatus(
            is_authenticated=True,
            api_key_id="key_456",
            permissions=["read", "write"],
            rate_limit_tier="standard"
        )
        
        assert status.has_permission("read") is True
        assert status.has_permission("write") is True
        assert status.has_permission("admin") is False
        assert status.has_any_permission(["read", "admin"]) is True
        assert status.has_all_permissions(["read", "write"]) is True
        assert status.has_all_permissions(["read", "write", "admin"]) is False
    
    def test_rate_limit_access(self):
        """Test rate limit information access."""
        rate_limits = RateLimitInfo(
            requests_per_minute=100,
            requests_per_day=10000,
            current_usage=25
        )
        
        status = AuthenticationStatus(
            is_authenticated=True,
            api_key_id="key_789",
            permissions=["read"],
            rate_limit_tier="standard",
            current_rate_limits=rate_limits
        )
        
        assert status.current_rate_limits is not None
        assert status.current_rate_limits.remaining_requests() == 75
        assert status.is_near_rate_limit() is False