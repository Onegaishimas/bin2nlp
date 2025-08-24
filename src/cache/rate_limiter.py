"""
Rate limiting system using PostgreSQL for API request throttling.

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
from ..storage.file_storage import get_file_storage


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
    PostgreSQL-based rate limiter with sliding window algorithm and burst allowance.
    
    Features:
    - Sliding window rate limiting using PostgreSQL atomic operations
    - Multiple time windows (minute, hour, day)
    - Burst allowance for temporary spikes
    - Per-API-key and per-IP rate limiting
    - Rate limit statistics and monitoring
    - Configurable limits per tier
    - Automatic cleanup of expired data
    """
    
    # Time windows
    WINDOWS = {
        'minute': 60,
        'hour': 3600,
        'day': 86400
    }
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize rate limiter.
        
        Args:
            settings: Application settings
        """
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)
        
        # Load rate limit configurations from settings
        self.rate_limit_configs = self._load_rate_limit_configs()
        
        # Default configuration
        self.default_config = RateLimitConfig(
            requests_per_minute=getattr(self.settings, 'DEFAULT_RATE_LIMIT_PER_MINUTE', 100),
            requests_per_hour=getattr(self.settings, 'DEFAULT_RATE_LIMIT_PER_MINUTE', 100) * 60,
            requests_per_day=getattr(self.settings, 'DEFAULT_RATE_LIMIT_PER_DAY', 10000),
            burst_allowance=20,
            window_size_seconds=60
        )
    
    async def _get_database(self):
        """Get database connection."""
        from ..database.connection import get_database
        return await get_database()
    
    def _load_rate_limit_configs(self) -> Dict[str, RateLimitConfig]:
        """Load rate limit configurations from settings."""
        configs = {}
        
        # Basic tier configurations from environment variables
        tiers = {
            'basic': {
                'per_minute': getattr(self.settings, 'RATE_LIMIT_BASIC_PER_MINUTE', 10),
                'per_hour': getattr(self.settings, 'RATE_LIMIT_BASIC_PER_MINUTE', 10) * 60,
                'per_day': getattr(self.settings, 'RATE_LIMIT_BASIC_PER_DAY', 600),
                'burst': 5
            },
            'standard': {
                'per_minute': getattr(self.settings, 'RATE_LIMIT_STANDARD_PER_MINUTE', 60),
                'per_hour': getattr(self.settings, 'RATE_LIMIT_STANDARD_PER_MINUTE', 60) * 60,
                'per_day': getattr(self.settings, 'RATE_LIMIT_STANDARD_PER_DAY', 3600),
                'burst': 20
            },
            'premium': {
                'per_minute': getattr(self.settings, 'RATE_LIMIT_PREMIUM_PER_MINUTE', 300),
                'per_hour': getattr(self.settings, 'RATE_LIMIT_PREMIUM_PER_MINUTE', 300) * 60,
                'per_day': getattr(self.settings, 'RATE_LIMIT_PREMIUM_PER_DAY', 18000),
                'burst': 50
            },
            'enterprise': {
                'per_minute': getattr(self.settings, 'RATE_LIMIT_ENTERPRISE_PER_MINUTE', 1000),
                'per_hour': getattr(self.settings, 'RATE_LIMIT_ENTERPRISE_PER_MINUTE', 1000) * 60,
                'per_day': getattr(self.settings, 'RATE_LIMIT_ENTERPRISE_PER_DAY', 60000),
                'burst': 100
            }
        }
        
        for tier, limits in tiers.items():
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
            db = await self._get_database()
            current_time = time.time()
            
            # Get configuration for this tier
            config = self._get_config_for_tier(tier)
            
            # Check each time window using PostgreSQL atomic operations
            for window_name, window_seconds in self.WINDOWS.items():
                limit = getattr(config, f'requests_per_{window_name}')
                
                # Use PostgreSQL stored procedure for atomic rate limit check and update
                result = await db.fetch_one("""
                    SELECT check_rate_limit(
                        :identifier, :window_name, :window_seconds, 
                        :limit, :cost, NOW()
                    ) as allowed
                """, {
                    "identifier": identifier,
                    "window_name": window_name,
                    "window_seconds": window_seconds,
                    "limit": limit,
                    "cost": cost
                })
                
                # If this window rejects the request, check burst allowance
                if not result['allowed']:
                    # Check burst allowance
                    if not await self._check_burst_allowance(identifier, config, cost):
                        # Get current usage for response
                        usage = await self._get_window_usage(
                            identifier, window_name, window_seconds, current_time
                        )
                        
                        retry_after = await self._calculate_retry_after(
                            identifier, window_name, window_seconds, current_time, limit
                        )
                        
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
                            reset_time=current_time + window_seconds,
                            retry_after_seconds=retry_after
                        )
            
            # All windows passed, record the request
            await self._record_request(identifier, cost, current_time)
            
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
            db = await self._get_database()
            
            # Get current usage from PostgreSQL rate_limits table
            window_start = current_time - window_seconds
            
            usage = await db.fetch_val("""
                SELECT COALESCE(SUM(request_count), 0)
                FROM rate_limits 
                WHERE identifier = :identifier 
                AND window_type = :window_name
                AND created_at > NOW() - INTERVAL '%s seconds'
            """ % window_seconds, {
                "identifier": identifier,
                "window_name": window_name
            })
            
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
            db = await self._get_database()
            
            # Simplified burst allowance check using PostgreSQL
            # Get current burst usage from the database
            current_time = time.time()
            window_start = current_time - config.window_size_seconds
            
            burst_usage = await db.fetch_val("""
                SELECT COALESCE(SUM(request_count), 0)
                FROM rate_limits 
                WHERE identifier = :identifier 
                AND window_type = 'burst'
                AND created_at > NOW() - INTERVAL '%s seconds'
            """ % config.window_size_seconds, {
                "identifier": identifier
            })
            
            burst_usage = int(burst_usage or 0)
            
            if burst_usage + cost <= config.burst_allowance:
                # Record burst usage
                await db.execute("""
                    INSERT INTO rate_limits (identifier, window_type, request_count, created_at)
                    VALUES (:identifier, 'burst', :cost, NOW())
                """, {
                    "identifier": identifier,
                    "cost": cost
                })
                return True
            
            return False
            
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
            db = await self._get_database()
            
            # Record request for each time window
            for window_name in self.WINDOWS:
                await db.execute("""
                    INSERT INTO rate_limits (identifier, window_type, request_count, created_at)
                    VALUES (:identifier, :window_type, :cost, NOW())
                """, {
                    "identifier": identifier,
                    "window_type": window_name,
                    "cost": cost
                })
                
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
            db = await self._get_database()
            
            # Get the oldest request in the current window
            oldest_request = await db.fetch_one("""
                SELECT created_at 
                FROM rate_limits 
                WHERE identifier = :identifier 
                AND window_type = :window_name
                AND created_at > NOW() - INTERVAL '%s seconds'
                ORDER BY created_at ASC
                LIMIT 1
            """ % window_seconds, {
                "identifier": identifier,
                "window_name": window_name
            })
            
            if oldest_request:
                oldest_time = oldest_request['created_at'].timestamp()
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
            db = await self._get_database()
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
            db = await self._get_database()
            
            # Delete all rate limit entries for this identifier
            rows_deleted = await db.execute("""
                DELETE FROM rate_limits WHERE identifier = :identifier
            """, {"identifier": identifier})
            
            success = rows_deleted > 0
            
            if success:
                self.logger.info(
                    "Rate limit reset",
                    extra={"identifier": identifier[:16] + "..."}
                )
            
            return success
            
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
            # Simplified implementation - return empty list for now
            # Could be enhanced with a blocked_identifiers table if needed
            return []
            
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
            db = await self._get_database()
            
            # Clean up expired rate limit entries (older than 24 hours)
            cleaned_count = await db.execute("""
                DELETE FROM rate_limits 
                WHERE created_at < NOW() - INTERVAL '24 hours'
            """)
            
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
            db = await self._get_database()
            
            # Get basic stats from PostgreSQL
            total_requests = await db.fetch_val("""
                SELECT COUNT(*) FROM rate_limits
            """) or 0
            
            return {
                'total_requests': total_requests,
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
    
