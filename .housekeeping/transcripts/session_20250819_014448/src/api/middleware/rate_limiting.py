"""
Rate Limiting Middleware

Advanced rate limiting with support for different tiers, burst limits,
and LLM provider quota management.
"""

import logging
import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ...core.config import get_settings
from ...cache.base import get_redis_client
from .auth import get_current_user

logger = logging.getLogger(__name__)


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
    Sliding window rate limiter with Redis backend.
    
    Provides more accurate rate limiting than fixed window
    and supports burst allowances.
    """
    
    def __init__(self):
        self.redis = None
        self.settings = get_settings()
    
    async def _get_redis(self):
        """Get Redis client, initializing if needed."""
        if self.redis is None:
            try:
                self.redis = await get_redis_client()
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
                return None
        return self.redis
    
    async def check_rate_limit(
        self,
        identifier: str,
        window_seconds: int,
        max_requests: int,
        burst_allowance: int = 0
    ) -> Tuple[bool, int, Dict[str, int]]:
        """
        Check if request is within rate limits.
        
        Args:
            identifier: Unique identifier for rate limiting (user_id, IP, etc.)
            window_seconds: Time window in seconds
            max_requests: Maximum requests allowed in window
            burst_allowance: Additional requests allowed for burst traffic
            
        Returns:
            Tuple of (allowed, retry_after_seconds, stats)
        """
        now = time.time()
        window_start = now - window_seconds
        
        # Redis key for this rate limit window
        key = f"rate_limit:{identifier}:{window_seconds}"
        
        # Get Redis client and use pipeline for atomic operations
        redis = await self._get_redis()
        if redis is None:
            # Redis not available - allow request but log warning
            logger.warning("Rate limiting disabled: Redis not available")
            return True, 0, {
                "current": 0,
                "limit": max_requests,
                "burst_allowance": burst_allowance,
                "window_seconds": window_seconds,
                "remaining": max_requests,
                "warning": "rate_limiting_disabled"
            }
        
        pipe = await redis.pipeline()
        
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Count current requests in window
        pipe.zcard(key)
        
        # Execute pipeline
        results = await pipe.execute()
        current_count = results[1]
        
        # Check if within limits (including burst)
        effective_limit = max_requests + burst_allowance
        
        if current_count >= effective_limit:
            # Calculate retry after based on oldest request in window
            oldest_requests = await redis.zrange(key, 0, 0, withscores=True)
            if oldest_requests:
                oldest_time = oldest_requests[0][1]
                retry_after = int(window_seconds - (now - oldest_time)) + 1
            else:
                retry_after = window_seconds
            
            return False, retry_after, {
                "current": current_count,
                "limit": max_requests,
                "burst_allowance": burst_allowance,
                "window_seconds": window_seconds
            }
        
        # Add current request to window
        await redis.zadd(key, {str(now): now})
        
        # Set expiry on key (cleanup)
        await redis.expire(key, window_seconds + 60)
        
        return True, 0, {
            "current": current_count + 1,
            "limit": max_requests,
            "burst_allowance": burst_allowance,
            "window_seconds": window_seconds,
            "remaining": effective_limit - current_count - 1
        }
    
    async def get_rate_limit_status(
        self,
        identifier: str,
        window_seconds: int
    ) -> Dict[str, int]:
        """
        Get current rate limit status without consuming a request.
        
        Args:
            identifier: Rate limit identifier
            window_seconds: Time window in seconds
            
        Returns:
            Dictionary with current status
        """
        now = time.time()
        window_start = now - window_seconds
        key = f"rate_limit:{identifier}:{window_seconds}"
        
        # Get Redis client
        redis = await self._get_redis()
        if redis is None:
            # Redis not available - return default status
            return {
                "current": 0,
                "reset_at": int(now + window_seconds),
                "window_seconds": window_seconds,
                "warning": "rate_limiting_disabled"
            }
        
        # Clean expired entries and count current
        await redis.zremrangebyscore(key, 0, window_start)
        current_count = await redis.zcard(key)
        
        # Get window reset time
        oldest_requests = await redis.zrange(key, 0, 0, withscores=True)
        reset_time = int(now + window_seconds)
        if oldest_requests:
            oldest_time = oldest_requests[0][1]
            reset_time = int(oldest_time + window_seconds)
        
        return {
            "current": current_count,
            "reset_at": reset_time,
            "window_seconds": window_seconds
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
                burst_allowance=limit_config.get("burst_allowance", 0)
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
                window_seconds=primary_limit["window_seconds"]
            )
            
            response.headers.update({
                "X-RateLimit-Limit": str(primary_limit["max_requests"]),
                "X-RateLimit-Remaining": str(
                    max(0, primary_limit["max_requests"] - limit_stats["current"])
                ),
                "X-RateLimit-Reset": str(limit_stats["reset_at"]),
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
    
    Manages provider-specific rate limits and token usage.
    """
    
    def __init__(self):
        self.redis = None
        self.settings = get_settings()
    
    async def _get_redis(self):
        """Get Redis client, initializing if needed."""
        if self.redis is None:
            try:
                self.redis = await get_redis_client()
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
                return None
        return self.redis
    
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
        now = int(time.time())
        
        # Check requests per minute
        req_key = f"llm_rate:{user_id}:{provider_id}:requests:60"
        req_count = await self._get_window_count(req_key, now, 60)
        
        if req_count >= self.settings.llm.requests_per_minute:
            return False, "LLM requests per minute limit exceeded", {
                "requests_used": req_count,
                "requests_limit": self.settings.llm.requests_per_minute
            }
        
        # Check tokens per minute
        if estimated_tokens > 0:
            token_key = f"llm_rate:{user_id}:{provider_id}:tokens:60"
            token_count = await self._get_window_count(token_key, now, 60)
            
            if token_count + estimated_tokens > self.settings.llm.tokens_per_minute:
                return False, "LLM tokens per minute limit exceeded", {
                    "tokens_used": token_count,
                    "tokens_limit": self.settings.llm.tokens_per_minute,
                    "estimated_tokens": estimated_tokens
                }
        
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
        now = int(time.time())
        
        # Record request
        req_key = f"llm_rate:{user_id}:{provider_id}:requests:60"
        await self._increment_window(req_key, now, 60)
        
        # Record token usage
        if tokens_used > 0:
            token_key = f"llm_rate:{user_id}:{provider_id}:tokens:60"
            await self._increment_window(token_key, now, 60, tokens_used)
    
    async def _get_window_count(self, key: str, now: int, window_seconds: int) -> int:
        """Get current count in sliding window."""
        window_start = now - window_seconds
        
        # Clean expired entries and count
        await self.redis.zremrangebyscore(key, 0, window_start)
        return await self.redis.zcard(key)
    
    async def _increment_window(
        self,
        key: str,
        now: int,
        window_seconds: int,
        increment: int = 1
    ) -> None:
        """Add to sliding window counter."""
        # Add current usage
        await self.redis.zadd(key, {f"{now}:{increment}": now})
        
        # Set expiry
        await self.redis.expire(key, window_seconds + 60)
    
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
        stats = {}
        providers = [provider_id] if provider_id else self.settings.llm.enabled_providers
        
        for provider in providers:
            now = int(time.time())
            
            # Get current usage
            req_key = f"llm_rate:{user_id}:{provider}:requests:60"
            token_key = f"llm_rate:{user_id}:{provider}:tokens:60"
            
            requests_used = await self._get_window_count(req_key, now, 60)
            tokens_used = await self._get_window_count(token_key, now, 60)
            
            stats[provider] = {
                "requests_used": requests_used,
                "requests_limit": self.settings.llm.requests_per_minute,
                "requests_remaining": max(0, self.settings.llm.requests_per_minute - requests_used),
                "tokens_used": tokens_used,
                "tokens_limit": self.settings.llm.tokens_per_minute,
                "tokens_remaining": max(0, self.settings.llm.tokens_per_minute - tokens_used)
            }
        
        return stats


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
        burst_allowance=tier_limits.get("burst", 0) // 2
    )
    
    if not allowed:
        raise RateLimitExceeded(retry_after=retry_after, limit_type=endpoint_type)