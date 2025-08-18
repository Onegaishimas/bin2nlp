"""
Rate limiting system using Redis for API request throttling.

Provides sliding window rate limiting with burst allowance, quota tracking,
and configurable limits per API key and tier.
"""

import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass

from ..core.config import Settings, get_settings
from ..core.exceptions import RateLimitException, CacheException
from ..core.logging import get_logger
from .base import RedisClient


class RateLimitResult(NamedTuple):
    """Result of rate limit check."""
    
    allowed: bool
    current_usage: int
    limit: int
    remaining: int
    reset_time: float
    retry_after_seconds: Optional[int] = None


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a tier or key."""
    
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_allowance: int
    window_size_seconds: int = 60  # Default to 1 minute windows
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            'requests_per_minute': self.requests_per_minute,
            'requests_per_hour': self.requests_per_hour,
            'requests_per_day': self.requests_per_day,
            'burst_allowance': self.burst_allowance,
            'window_size_seconds': self.window_size_seconds
        }


class RateLimiter:
    """
    Redis-based rate limiter with sliding window algorithm and burst allowance.
    
    Features:
    - Sliding window rate limiting using sorted sets
    - Multiple time windows (minute, hour, day)
    - Burst allowance for temporary spikes
    - Per-API-key and per-IP rate limiting
    - Rate limit statistics and monitoring
    - Configurable limits per tier
    - Automatic cleanup of expired data
    """
    
    # Redis key patterns
    RATE_LIMIT_KEY = "ratelimit:{identifier}:{window}"
    BURST_ALLOWANCE_KEY = "burst:{identifier}"
    RATE_LIMIT_STATS_KEY = "ratelimit:stats"
    BLOCKED_KEYS_SET = "ratelimit:blocked"
    
    # Time windows
    WINDOWS = {
        'minute': 60,
        'hour': 3600,
        'day': 86400
    }
    
    def __init__(self, redis_client: Optional[RedisClient] = None, settings: Optional[Settings] = None):
        """
        Initialize rate limiter.
        
        Args:
            redis_client: Redis client instance
            settings: Application settings
        """
        self.redis_client = redis_client
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)
        
        # Load rate limit configurations from settings
        self.rate_limit_configs = self._load_rate_limit_configs()
        
        # Default configuration
        self.default_config = RateLimitConfig(
            requests_per_minute=self.settings.security.default_rate_limit_per_minute,
            requests_per_hour=self.settings.security.default_rate_limit_per_minute * 60,
            requests_per_day=self.settings.security.default_rate_limit_per_day,
            burst_allowance=20,
            window_size_seconds=60
        )
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance."""
        if self.redis_client is None:
            from .base import get_redis_client
            self.redis_client = await get_redis_client()
        return self.redis_client
    
    def _load_rate_limit_configs(self) -> Dict[str, RateLimitConfig]:
        """Load rate limit configurations from settings."""
        configs = {}
        rate_limits = self.settings.get_rate_limits()
        
        for tier, limits in rate_limits.items():
            configs[tier] = RateLimitConfig(
                requests_per_minute=limits['per_minute'],
                requests_per_hour=limits['per_hour'],
                requests_per_day=limits['per_day'],
                burst_allowance=limits['burst']
            )
        
        return configs
    
    def _get_config_for_tier(self, tier: str) -> RateLimitConfig:
        """Get rate limit configuration for a specific tier."""
        return self.rate_limit_configs.get(tier, self.default_config)
    
    async def check_rate_limit(
        self,
        identifier: str,
        tier: str = "standard",
        cost: int = 1
    ) -> RateLimitResult:
        """
        Check if request is within rate limits.
        
        Args:
            identifier: Unique identifier (API key, IP address, etc.)
            tier: Rate limit tier
            cost: Cost of this request (for weighted rate limiting)
            
        Returns:
            RateLimitResult with allow/deny decision and quota info
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            
            # Get configuration for this tier
            config = self._get_config_for_tier(tier)
            
            # Check each time window
            for window_name, window_seconds in self.WINDOWS.items():
                limit = getattr(config, f'requests_per_{window_name}')
                
                # Check current usage in this window
                usage = await self._get_window_usage(
                    identifier, window_name, window_seconds, current_time
                )
                
                # Calculate remaining quota
                remaining = max(0, limit - usage)
                reset_time = current_time + window_seconds
                
                # Check if this request would exceed the limit
                if usage + cost > limit:
                    # Check burst allowance
                    if not await self._check_burst_allowance(identifier, config, cost):
                        # Rate limit exceeded
                        retry_after = await self._calculate_retry_after(
                            identifier, window_name, window_seconds, current_time, limit
                        )
                        
                        await self._update_stats("blocked", identifier, tier)
                        
                        self.logger.warning(
                            f"Rate limit exceeded for {window_name} window",
                            extra={
                                "identifier": identifier[:16] + "...",
                                "tier": tier,
                                "window": window_name,
                                "usage": usage,
                                "limit": limit,
                                "cost": cost
                            }
                        )
                        
                        return RateLimitResult(
                            allowed=False,
                            current_usage=usage,
                            limit=limit,
                            remaining=0,
                            reset_time=reset_time,
                            retry_after_seconds=retry_after
                        )
            
            # All windows passed, record the request
            await self._record_request(identifier, cost, current_time)
            await self._update_stats("allowed", identifier, tier)
            
            # Return result for the most restrictive window (minute)
            minute_usage = await self._get_window_usage(
                identifier, "minute", self.WINDOWS["minute"], current_time
            )
            minute_limit = config.requests_per_minute
            
            return RateLimitResult(
                allowed=True,
                current_usage=minute_usage + cost,
                limit=minute_limit,
                remaining=max(0, minute_limit - minute_usage - cost),
                reset_time=current_time + 60
            )
            
        except Exception as e:
            self.logger.error(
                "Rate limit check failed",
                extra={"identifier": identifier[:16] + "...", "error": str(e)}
            )
            
            # Fail open - allow request if rate limiter fails
            return RateLimitResult(
                allowed=True,
                current_usage=0,
                limit=9999999,
                remaining=9999999,
                reset_time=time.time() + 60
            )
    
    async def _get_window_usage(
        self,
        identifier: str,
        window_name: str,
        window_seconds: int,
        current_time: float
    ) -> int:
        """Get current usage for a time window using sliding window."""
        try:
            redis = await self._get_redis()
            
            rate_limit_key = self.RATE_LIMIT_KEY.format(
                identifier=identifier,
                window=window_name
            )
            
            # Remove expired entries and count current usage
            window_start = current_time - window_seconds
            
            # Use Lua script for atomic operation
            lua_script = """
            local key = KEYS[1]
            local window_start = tonumber(ARGV[1])
            local current_time = tonumber(ARGV[2])
            
            -- Remove expired entries
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            
            -- Count current entries
            local count = redis.call('ZCARD', key)
            
            -- Set expiration for cleanup
            redis.call('EXPIRE', key, math.floor(ARGV[3]))
            
            return count
            """
            
            usage = await redis._client.eval(
                lua_script,
                1,
                rate_limit_key,
                window_start,
                current_time,
                window_seconds
            )
            
            return int(usage or 0)
            
        except Exception as e:
            self.logger.error(
                "Failed to get window usage",
                extra={
                    "identifier": identifier[:16] + "...",
                    "window": window_name,
                    "error": str(e)
                }
            )
            return 0
    
    async def _check_burst_allowance(
        self,
        identifier: str,
        config: RateLimitConfig,
        cost: int
    ) -> bool:
        """Check if burst allowance can cover this request."""
        try:
            redis = await self._get_redis()
            
            burst_key = self.BURST_ALLOWANCE_KEY.format(identifier=identifier)
            
            # Use Lua script for atomic burst allowance check
            lua_script = """
            local burst_key = KEYS[1]
            local burst_limit = tonumber(ARGV[1])
            local cost = tonumber(ARGV[2])
            local current_time = tonumber(ARGV[3])
            local window_size = tonumber(ARGV[4])
            
            -- Get current burst usage
            local burst_data = redis.call('GET', burst_key)
            local burst_usage = 0
            local last_reset = current_time
            
            if burst_data then
                local data = cjson.decode(burst_data)
                burst_usage = data.usage or 0
                last_reset = data.last_reset or current_time
            end
            
            -- Reset burst allowance if window has passed
            if current_time - last_reset > window_size then
                burst_usage = 0
                last_reset = current_time
            end
            
            -- Check if burst allowance can cover this request
            if burst_usage + cost <= burst_limit then
                -- Update burst usage
                local new_data = {
                    usage = burst_usage + cost,
                    last_reset = last_reset
                }
                redis.call('SET', burst_key, cjson.encode(new_data), 'EX', window_size * 2)
                return 1
            else
                return 0
            end
            """
            
            allowed = await redis._client.eval(
                lua_script,
                1,
                burst_key,
                config.burst_allowance,
                cost,
                time.time(),
                config.window_size_seconds
            )
            
            return bool(allowed)
            
        except Exception as e:
            self.logger.error(
                "Burst allowance check failed",
                extra={"identifier": identifier[:16] + "...", "error": str(e)}
            )
            return False
    
    async def _record_request(
        self,
        identifier: str,
        cost: int,
        current_time: float
    ) -> None:
        """Record a request in all time windows."""
        try:
            redis = await self._get_redis()
            
            # Use pipeline for efficiency
            async with redis.pipeline() as pipe:
                for window_name in self.WINDOWS:
                    rate_limit_key = self.RATE_LIMIT_KEY.format(
                        identifier=identifier,
                        window=window_name
                    )
                    
                    # Add request with timestamp as score and unique member
                    request_id = f"{current_time}:{cost}"
                    await pipe.zadd(rate_limit_key, {request_id: current_time})
                    await pipe.expire(rate_limit_key, self.WINDOWS[window_name] * 2)
                
                await pipe.execute()
                
        except Exception as e:
            self.logger.error(
                "Failed to record request",
                extra={"identifier": identifier[:16] + "...", "error": str(e)}
            )
    
    async def _calculate_retry_after(
        self,
        identifier: str,
        window_name: str,
        window_seconds: int,
        current_time: float,
        limit: int
    ) -> int:
        """Calculate when the client can retry (retry-after seconds)."""
        try:
            redis = await self._get_redis()
            
            rate_limit_key = self.RATE_LIMIT_KEY.format(
                identifier=identifier,
                window=window_name
            )
            
            # Get the oldest request in the current window
            oldest_requests = await redis._client.zrange(
                rate_limit_key, 0, 0, withscores=True
            )
            
            if oldest_requests:
                oldest_time = oldest_requests[0][1]
                # Time until the oldest request expires
                retry_after = int((oldest_time + window_seconds) - current_time)
                return max(1, retry_after)
            
            # Default retry after
            return 60
            
        except Exception:
            return 60  # Default 1 minute
    
    async def get_rate_limit_status(
        self,
        identifier: str,
        tier: str = "standard"
    ) -> Dict[str, any]:
        """
        Get current rate limit status for an identifier.
        
        Args:
            identifier: Unique identifier
            tier: Rate limit tier
            
        Returns:
            Dictionary with rate limit status
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            config = self._get_config_for_tier(tier)
            
            status = {
                'identifier': identifier[:16] + "...",
                'tier': tier,
                'windows': {},
                'burst_allowance': {
                    'limit': config.burst_allowance,
                    'used': 0,
                    'remaining': config.burst_allowance
                },
                'timestamp': current_time
            }
            
            # Get status for each window
            for window_name, window_seconds in self.WINDOWS.items():
                limit = getattr(config, f'requests_per_{window_name}')
                usage = await self._get_window_usage(
                    identifier, window_name, window_seconds, current_time
                )
                
                status['windows'][window_name] = {
                    'limit': limit,
                    'used': usage,
                    'remaining': max(0, limit - usage),
                    'reset_at': current_time + window_seconds,
                    'usage_percent': round((usage / limit * 100), 2) if limit > 0 else 0
                }
            
            # Get burst allowance usage
            burst_key = self.BURST_ALLOWANCE_KEY.format(identifier=identifier)
            burst_data_json = await redis.get(burst_key)
            
            if burst_data_json:
                try:
                    burst_data = json.loads(burst_data_json)
                    burst_usage = burst_data.get('usage', 0)
                    status['burst_allowance']['used'] = burst_usage
                    status['burst_allowance']['remaining'] = max(0, config.burst_allowance - burst_usage)
                except json.JSONDecodeError:
                    pass
            
            return status
            
        except Exception as e:
            self.logger.error(
                "Failed to get rate limit status",
                extra={"identifier": identifier[:16] + "...", "error": str(e)}
            )
            return {}
    
    async def reset_rate_limit(self, identifier: str) -> bool:
        """
        Reset rate limits for an identifier (admin function).
        
        Args:
            identifier: Unique identifier to reset
            
        Returns:
            bool: True if reset successfully
        """
        try:
            redis = await self._get_redis()
            
            keys_to_delete = []
            
            # Collect all rate limit keys for this identifier
            for window_name in self.WINDOWS:
                rate_limit_key = self.RATE_LIMIT_KEY.format(
                    identifier=identifier,
                    window=window_name
                )
                keys_to_delete.append(rate_limit_key)
            
            # Add burst allowance key
            burst_key = self.BURST_ALLOWANCE_KEY.format(identifier=identifier)
            keys_to_delete.append(burst_key)
            
            # Delete all keys
            if keys_to_delete:
                await redis.delete(*keys_to_delete)
            
            # Remove from blocked set
            await redis._client.srem(self.BLOCKED_KEYS_SET, identifier)
            
            await self._update_stats("reset", identifier)
            
            self.logger.info(
                "Rate limit reset",
                extra={"identifier": identifier[:16] + "..."}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to reset rate limit",
                extra={"identifier": identifier[:16] + "...", "error": str(e)}
            )
            return False
    
    async def get_blocked_identifiers(self, limit: int = 100) -> List[Dict[str, any]]:
        """
        Get list of currently blocked identifiers.
        
        Args:
            limit: Maximum number of blocked identifiers to return
            
        Returns:
            List of blocked identifier information
        """
        try:
            redis = await self._get_redis()
            
            blocked_identifiers = await redis._client.smembers(self.BLOCKED_KEYS_SET)
            blocked_list = []
            
            for identifier in list(blocked_identifiers)[:limit]:
                status = await self.get_rate_limit_status(identifier)
                if status:
                    blocked_list.append(status)
            
            return blocked_list
            
        except Exception as e:
            self.logger.error(
                "Failed to get blocked identifiers",
                extra={"error": str(e)}
            )
            return []
    
    async def cleanup_expired_data(self, batch_size: int = 1000) -> int:
        """
        Clean up expired rate limit data.
        
        Args:
            batch_size: Number of keys to process in each batch
            
        Returns:
            int: Number of expired entries cleaned up
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            cleaned_count = 0
            
            # This is a simplified cleanup implementation
            # In production, you might want to use Redis keyspace notifications
            # or a more sophisticated cleanup strategy
            
            # Cleanup is largely handled by Redis TTL on individual keys
            # This function mainly updates statistics
            
            stats = await redis._client.hgetall(self.RATE_LIMIT_STATS_KEY)
            if stats:
                stats['last_cleanup'] = str(int(current_time))
                await redis._client.hset(self.RATE_LIMIT_STATS_KEY, mapping=stats)
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup expired data",
                extra={"error": str(e)}
            )
            return 0
    
    async def get_rate_limit_stats(self) -> Dict[str, any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with rate limiter statistics
        """
        try:
            redis = await self._get_redis()
            
            # Get basic stats
            stats = await redis._client.hgetall(self.RATE_LIMIT_STATS_KEY) or {}
            
            # Get blocked identifiers count
            blocked_count = await redis._client.scard(self.BLOCKED_KEYS_SET)
            
            # Calculate derived metrics
            allowed = int(stats.get('allowed', 0))
            blocked = int(stats.get('blocked', 0))
            total_requests = allowed + blocked
            block_rate = (blocked / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'total_requests': total_requests,
                'allowed_requests': allowed,
                'blocked_requests': blocked,
                'block_rate_percent': round(block_rate, 2),
                'currently_blocked_identifiers': blocked_count,
                'reset_operations': int(stats.get('resets', 0)),
                'last_cleanup': stats.get('last_cleanup'),
                'rate_limit_configs': {
                    tier: config.to_dict()
                    for tier, config in self.rate_limit_configs.items()
                },
                'timestamp': time.time()
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get rate limit stats",
                extra={"error": str(e)}
            )
            return {}
    
    async def _update_stats(
        self,
        operation: str,
        identifier: Optional[str] = None,
        tier: Optional[str] = None
    ) -> None:
        """Update rate limiter statistics."""
        try:
            redis = await self._get_redis()
            
            # Update operation count
            await redis._client.hincrby(self.RATE_LIMIT_STATS_KEY, operation, 1)
            
            # Update tier stats if provided
            if tier:
                await redis._client.hincrby(self.RATE_LIMIT_STATS_KEY, f"{operation}_{tier}", 1)
            
            # Add to blocked set if blocked
            if operation == "blocked" and identifier:
                await redis._client.sadd(self.BLOCKED_KEYS_SET, identifier)
                # Set expiration on blocked set member (Redis doesn't support member TTL,
                # so we rely on cleanup or manual removal)
            
        except Exception:
            pass  # Don't fail operations due to stats errors