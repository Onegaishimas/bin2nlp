"""
API Middleware Components

Custom middleware for error handling, request logging, authentication,
and rate limiting for production deployment.
"""

from .error_handling import ErrorHandlingMiddleware
from .request_logging import RequestLoggingMiddleware
from .auth import (
    AuthenticationMiddleware,
    AuthenticationError,
    APIKeyManager,
    get_current_user,
    require_auth,
    require_permission,
    require_tier,
    api_key_scheme,
    create_dev_api_key
)
from .rate_limiting import (
    RateLimitingMiddleware,
    RateLimitExceeded,
    SlidingWindowRateLimiter,
    LLMProviderRateLimiter,
    check_endpoint_rate_limit
)

__all__ = [
    # Error handling
    "ErrorHandlingMiddleware",
    
    # Request logging
    "RequestLoggingMiddleware",
    
    # Authentication
    "AuthenticationMiddleware",
    "AuthenticationError", 
    "APIKeyManager",
    "get_current_user",
    "require_auth",
    "require_permission",
    "require_tier",
    "api_key_scheme",
    "create_dev_api_key",
    
    # Rate limiting
    "RateLimitingMiddleware",
    "RateLimitExceeded",
    "SlidingWindowRateLimiter", 
    "LLMProviderRateLimiter",
    "check_endpoint_rate_limit"
]