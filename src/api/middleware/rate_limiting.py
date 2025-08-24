"""
Rate Limiting Middleware

Advanced rate limiting with support for different tiers, burst limits,
and LLM provider quota management.
"""

import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ...core.config import get_settings
from ...core.logging import get_logger
from ...cache.rate_limiter import RateLimiter
from .auth import get_current_user

logger = get_logger(__name__)


class RateLimitExceeded(HTTPException):
    """Custom exception for rate limit violations."""
    
    def __init__(self, retry_after: int, limit_type: str = "requests"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )
        self.retry_after = retry_after
        self.limit_type = limit_type


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter with PostgreSQL backend.
    
    Provides more accurate rate limiting than fixed window
    and supports burst allowances.
    """
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.settings = get_settings()
    
    async def check_rate_limit(
        self,
        identifier: str,
        window_seconds: int,
        max_requests: int,
        burst_allowance: int = 0,
        tier: str = "basic"
    ) -> Tuple[bool, int, Dict[str, int]]:
        """
        Check if request is within rate limits using PostgreSQL rate limiter.
        
        Args:
            identifier: Unique identifier for rate limiting (user_id, IP, etc.)
            window_seconds: Time window in seconds
            max_requests: Maximum requests allowed in window
            burst_allowance: Additional requests allowed for burst traffic
            tier: User tier for rate limiting
            
        Returns:
            Tuple of (allowed, retry_after_seconds, stats)
        """
        try:
            # Use our new PostgreSQL-based rate limiter
            result = await self.rate_limiter.check_rate_limit(
                identifier=identifier,
                tier=tier,
                cost=1  # Each request costs 1 unit
            )
            
            if result.allowed:
                return True, 0, {
                    "current": result.current_usage,
                    "limit": result.limit,
                    "burst_allowance": burst_allowance,
                    "window_seconds": window_seconds,
                    "remaining": result.remaining
                }
            else:
                return False, result.retry_after_seconds or window_seconds, {
                    "current": result.current_usage,
                    "limit": result.limit,
                    "burst_allowance": burst_allowance,
                    "window_seconds": window_seconds,
                    "remaining": 0
                }
                
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Fail open - allow request when rate limiter fails
            return True, 0, {
                "current": 0,
                "limit": max_requests,
                "burst_allowance": burst_allowance,
                "window_seconds": window_seconds,
                "remaining": max_requests,
                "warning": "rate_limiting_error"
            }
    
    async def get_rate_limit_status(
        self,
        identifier: str,
        tier: str = "basic"
    ) -> Dict[str, int]:
        """
        Get current rate limit status without consuming a request.
        
        Args:
            identifier: Rate limit identifier
            tier: User tier for rate limiting
            
        Returns:
            Dictionary with current status
        """
        try:
            # Use our PostgreSQL rate limiter to get status
            status = await self.rate_limiter.get_rate_limit_status(
                identifier=identifier,
                tier=tier
            )
            return status
        except Exception as e:
            logger.error(f"Error getting rate limit status: {e}")
            now = time.time()
            return {
                "current": 0,
                "reset_at": int(now + 60),
                "window_seconds": 60,
                "warning": "rate_limiting_error"
            }


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits based on user tier and endpoint.
    
    Supports different limits for different endpoints and user tiers.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = SlidingWindowRateLimiter()
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health and documentation endpoints
        if self._is_exempt_endpoint(request.url.path):
            return await call_next(request)
        
        # Get user info or use IP-based limiting for unauthenticated requests
        user = get_current_user(request)
        if user:
            identifier = f"user:{user['user_id']}"
            tier = user.get("tier", "basic")
        else:
            identifier = f"ip:{self._get_client_ip(request)}"
            tier = "anonymous"
        
        # Get rate limits for user tier and endpoint
        limits = self._get_rate_limits(tier, request.url.path, request.method)
        
        # Check each applicable rate limit
        for limit_config in limits:
            allowed, retry_after, stats = await self.rate_limiter.check_rate_limit(
                identifier=f"{identifier}:{limit_config['name']}",
                window_seconds=limit_config["window_seconds"],
                max_requests=limit_config["max_requests"],
                burst_allowance=limit_config.get("burst_allowance", 0),
                tier=tier
            )
            
            if not allowed:
                # Log rate limit violation
                logger.warning(
                    f"Rate limit exceeded",
                    extra={
                        "identifier": identifier,
                        "tier": tier,
                        "limit_type": limit_config["name"],
                        "path": request.url.path,
                        "method": request.method,
                        "stats": stats
                    }
                )
                
                raise RateLimitExceeded(
                    retry_after=retry_after,
                    limit_type=limit_config["name"]
                )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        if limits:
            primary_limit = limits[0]  # Use first (most restrictive) limit for headers
            limit_stats = await self.rate_limiter.get_rate_limit_status(
                identifier=f"{identifier}:{primary_limit['name']}",
                tier=tier
            )
            
            # Extract window stats for the primary limit's window
            window_name = "minute"  # Default to minute window for headers
            if "windows" in limit_stats and window_name in limit_stats["windows"]:
                window_stats = limit_stats["windows"][window_name]
                response.headers.update({
                    "X-RateLimit-Limit": str(window_stats["limit"]),
                    "X-RateLimit-Remaining": str(window_stats["remaining"]),
                    "X-RateLimit-Reset": str(int(window_stats["reset_at"])),
                    "X-RateLimit-Window": str(primary_limit["window_seconds"])
                })
            else:
                # Fallback if rate limit status is empty
                response.headers.update({
                    "X-RateLimit-Limit": str(primary_limit["max_requests"]),
                    "X-RateLimit-Remaining": str(primary_limit["max_requests"]),
                    "X-RateLimit-Reset": str(int(time.time() + primary_limit["window_seconds"])),
                    "X-RateLimit-Window": str(primary_limit["window_seconds"])
                })
        
        return response
    
    def _get_rate_limits(self, tier: str, path: str, method: str) -> list:
        """
        Get applicable rate limits for tier and endpoint.
        
        Args:
            tier: User tier or 'anonymous'
            path: Request path
            method: HTTP method
            
        Returns:
            List of rate limit configurations
        """
        # Base rate limits by tier
        tier_limits = self.settings.get_rate_limits().get(tier, 
            self.settings.get_rate_limits()["basic"]
        )
        
        limits = []
        
        # Per-minute limit
        limits.append({
            "name": "per_minute",
            "window_seconds": 60,
            "max_requests": tier_limits["per_minute"],
            "burst_allowance": tier_limits.get("burst", 0)
        })
        
        # Per-hour limit for heavy endpoints
        if self._is_heavy_endpoint(path):
            limits.append({
                "name": "per_hour_heavy",
                "window_seconds": 3600,
                "max_requests": tier_limits["per_hour"] // 4,  # Reduced for heavy endpoints
                "burst_allowance": 0
            })
        
        # Per-day limit
        limits.append({
            "name": "per_day",
            "window_seconds": 86400,
            "max_requests": tier_limits["per_day"],
            "burst_allowance": 0
        })
        
        # Special limits for file uploads
        if method == "POST" and ("analyze" in path or "decompile" in path):
            upload_limit = max(5, tier_limits["per_minute"] // 4)  # Reduced for uploads
            limits.append({
                "name": "uploads_per_minute",
                "window_seconds": 60,
                "max_requests": upload_limit,
                "burst_allowance": 2
            })
        
        # LLM provider-specific limits (if applicable)
        if "llm" in path or "translate" in path:
            llm_limit = max(10, tier_limits["per_minute"] // 2)  # LLM requests are expensive
            limits.append({
                "name": "llm_per_minute",
                "window_seconds": 60,
                "max_requests": llm_limit,
                "burst_allowance": 0
            })
        
        return limits
    
    def _is_exempt_endpoint(self, path: str) -> bool:
        """Check if endpoint should be exempt from rate limiting."""
        exempt_paths = [
            "/health",
            "/api/v1/health", 
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico"
        ]
        
        return path in exempt_paths or path.startswith("/static/")
    
    def _is_heavy_endpoint(self, path: str) -> bool:
        """Check if endpoint is resource-intensive."""
        heavy_endpoints = [
            "/api/v1/analyze",
            "/api/v1/decompile",
            "/api/v1/translate"
        ]
        
        return any(heavy in path for heavy in heavy_endpoints)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address for IP-based rate limiting."""
        # Check forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"


class LLMProviderRateLimiter:
    """
    Specialized rate limiter for LLM provider API calls.
    
    Manages provider-specific rate limits and token usage using PostgreSQL.
    """
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.settings = get_settings()
    
    async def check_llm_rate_limit(
        self,
        user_id: str,
        provider_id: str,
        estimated_tokens: int = 0
    ) -> Tuple[bool, str, Dict[str, int]]:
        """
        Check rate limits for LLM provider usage.
        
        Args:
            user_id: User identifier
            provider_id: LLM provider (openai, anthropic, etc.)
            estimated_tokens: Estimated token usage
            
        Returns:
            Tuple of (allowed, reason_if_denied, usage_stats)
        """
        try:
            # Check requests per minute using the PostgreSQL rate limiter
            req_identifier = f"llm_rate:{user_id}:{provider_id}:requests"
            result = await self.rate_limiter.check_rate_limit(
                identifier=req_identifier,
                tier="llm",  # Use special LLM tier
                cost=1
            )
            
            if not result.allowed:
                return False, "LLM requests per minute limit exceeded", {
                    "requests_used": result.current_usage,
                    "requests_limit": result.limit
                }
            
            # Check tokens per minute if estimated_tokens provided
            if estimated_tokens > 0:
                token_identifier = f"llm_rate:{user_id}:{provider_id}:tokens"
                token_result = await self.rate_limiter.check_rate_limit(
                    identifier=token_identifier,
                    tier="llm",
                    cost=estimated_tokens
                )
                
                if not token_result.allowed:
                    return False, "LLM tokens per minute limit exceeded", {
                        "tokens_used": token_result.current_usage,
                        "tokens_limit": token_result.limit,
                        "estimated_tokens": estimated_tokens
                    }
            
            return True, "", {}
            
        except Exception as e:
            logger.error(f"Error checking LLM rate limit: {e}")
            # Fail open - allow request when rate limiter fails
            return True, "", {}
    
    async def record_llm_usage(
        self,
        user_id: str,
        provider_id: str,
        tokens_used: int = 0
    ) -> None:
        """
        Record LLM provider usage for rate limiting.
        
        Args:
            user_id: User identifier
            provider_id: LLM provider
            tokens_used: Actual tokens consumed
        """
        try:
            # Record request
            req_identifier = f"llm_rate:{user_id}:{provider_id}:requests"
            await self.rate_limiter.check_rate_limit(
                identifier=req_identifier,
                tier="llm",
                cost=1
            )
            
            # Record token usage
            if tokens_used > 0:
                token_identifier = f"llm_rate:{user_id}:{provider_id}:tokens"
                await self.rate_limiter.check_rate_limit(
                    identifier=token_identifier,
                    tier="llm",
                    cost=tokens_used
                )
                
        except Exception as e:
            logger.error(f"Error recording LLM usage: {e}")
    
    async def get_llm_usage_stats(
        self,
        user_id: str,
        provider_id: str = None
    ) -> Dict[str, Dict[str, int]]:
        """
        Get current LLM usage statistics.
        
        Args:
            user_id: User identifier
            provider_id: Specific provider or None for all providers
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            stats = {}
            providers = [provider_id] if provider_id else getattr(self.settings.llm, 'enabled_providers', ['openai'])
            
            for provider in providers:
                # Get request usage stats
                req_identifier = f"llm_rate:{user_id}:{provider}:requests"
                req_status = await self.rate_limiter.get_rate_limit_status(
                    identifier=req_identifier,
                    tier="llm"
                )
                
                # Get token usage stats
                token_identifier = f"llm_rate:{user_id}:{provider}:tokens"
                token_status = await self.rate_limiter.get_rate_limit_status(
                    identifier=token_identifier,
                    tier="llm"
                )
                
                stats[provider] = {
                    "requests_used": req_status.get("current", 0),
                    "requests_limit": getattr(self.settings.llm, 'requests_per_minute', 60),
                    "requests_remaining": req_status.get("remaining", 0),
                    "tokens_used": token_status.get("current", 0),
                    "tokens_limit": getattr(self.settings.llm, 'tokens_per_minute', 60000),
                    "tokens_remaining": token_status.get("remaining", 0)
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting LLM usage stats: {e}")
            return {}


# Convenience function for endpoint-specific rate limiting
async def check_endpoint_rate_limit(request: Request, endpoint_type: str = "standard") -> None:
    """
    Check rate limits for specific endpoint types.
    
    Args:
        request: FastAPI request object
        endpoint_type: Type of endpoint (standard, heavy, llm, upload)
        
    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    rate_limiter = SlidingWindowRateLimiter()
    user = get_current_user(request)
    
    if user:
        identifier = f"user:{user['user_id']}"
        tier = user.get("tier", "basic")
    else:
        identifier = f"ip:{request.client.host if request.client else 'unknown'}"
        tier = "anonymous"
    
    # Get limits for tier
    tier_limits = get_settings().get_rate_limits().get(tier, 
        get_settings().get_rate_limits()["basic"])
    
    # Endpoint-specific limits
    if endpoint_type == "heavy":
        limit = tier_limits["per_minute"] // 2
        window = 60
    elif endpoint_type == "llm":
        limit = max(5, tier_limits["per_minute"] // 4)
        window = 60
    elif endpoint_type == "upload":
        limit = max(3, tier_limits["per_minute"] // 6)
        window = 60
    else:  # standard
        limit = tier_limits["per_minute"]
        window = 60
    
    allowed, retry_after, stats = await rate_limiter.check_rate_limit(
        identifier=f"{identifier}:{endpoint_type}",
        window_seconds=window,
        max_requests=limit,
        burst_allowance=tier_limits.get("burst", 0) // 2,
        tier=tier
    )
    
    if not allowed:
        raise RateLimitExceeded(retry_after=retry_after, limit_type=endpoint_type)