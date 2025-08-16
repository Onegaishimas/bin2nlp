"""
Unit tests for rate limiter system.

Tests sliding window rate limiting, burst allowance, quota tracking,
and rate limit statistics with mocked Redis operations.
"""

import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.cache.rate_limiter import RateLimiter, RateLimitResult, RateLimitConfig
from src.cache.base import RedisClient
from src.core.config import Settings, SecuritySettings
from src.core.exceptions import RateLimitException


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client for rate limiter testing."""
    redis_mock = AsyncMock(spec=RedisClient)
    redis_mock._client = AsyncMock()
    
    # Mock Redis operations
    redis_mock._client.eval = AsyncMock()
    redis_mock._client.hincrby = AsyncMock(return_value=1)
    redis_mock._client.hset = AsyncMock(return_value=1)
    redis_mock._client.hgetall = AsyncMock(return_value={})
    redis_mock._client.zadd = AsyncMock(return_value=1)
    redis_mock._client.zrange = AsyncMock(return_value=[])
    redis_mock._client.zrem = AsyncMock(return_value=1)
    redis_mock._client.zcard = AsyncMock(return_value=0)
    redis_mock._client.expire = AsyncMock(return_value=True)
    redis_mock._client.sadd = AsyncMock(return_value=1)
    redis_mock._client.srem = AsyncMock(return_value=1)
    redis_mock._client.scard = AsyncMock(return_value=0)
    redis_mock._client.smembers = AsyncMock(return_value=set())
    
    # Mock pipeline operations
    redis_mock.pipeline = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.execute = AsyncMock(return_value=[True, True])
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=None)
    redis_mock.pipeline.return_value = mock_pipeline
    
    # Mock get/set/delete operations
    redis_mock.get = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    
    return redis_mock


@pytest.fixture
def mock_settings():
    """Create mock settings for rate limiter testing."""
    settings = MagicMock(spec=Settings)
    settings.security = MagicMock(spec=SecuritySettings)
    settings.security.default_rate_limit_per_minute = 60
    settings.security.default_rate_limit_per_day = 10000
    
    # Mock get_rate_limits method
    settings.get_rate_limits = MagicMock(return_value={
        "basic": {
            "per_minute": 10,
            "per_hour": 100,
            "per_day": 1000,
            "burst": 5
        },
        "standard": {
            "per_minute": 60,
            "per_hour": 3600,
            "per_day": 10000,
            "burst": 20
        },
        "premium": {
            "per_minute": 300,
            "per_hour": 5000,
            "per_day": 50000,
            "burst": 50
        },
        "enterprise": {
            "per_minute": 1000,
            "per_hour": 20000,
            "per_day": 200000,
            "burst": 100
        }
    })
    
    return settings


@pytest.fixture
def rate_limiter(mock_redis_client, mock_settings):
    """Create RateLimiter instance with mocked dependencies."""
    limiter = RateLimiter(redis_client=mock_redis_client, settings=mock_settings)
    return limiter


class TestRateLimitResult:
    """Test cases for RateLimitResult named tuple."""
    
    def test_rate_limit_result_creation(self):
        """Test RateLimitResult creation and access."""
        result = RateLimitResult(
            allowed=True,
            current_usage=25,
            limit=100,
            remaining=75,
            reset_time=time.time() + 60,
            retry_after_seconds=None
        )
        
        assert result.allowed is True
        assert result.current_usage == 25
        assert result.limit == 100
        assert result.remaining == 75
        assert result.retry_after_seconds is None
    
    def test_rate_limit_result_blocked(self):
        """Test RateLimitResult for blocked request."""
        result = RateLimitResult(
            allowed=False,
            current_usage=100,
            limit=100,
            remaining=0,
            reset_time=time.time() + 60,
            retry_after_seconds=60
        )
        
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after_seconds == 60


class TestRateLimitConfig:
    """Test cases for RateLimitConfig dataclass."""
    
    def test_rate_limit_config_creation(self):
        """Test RateLimitConfig creation and serialization."""
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=1000,
            requests_per_day=10000,
            burst_allowance=25,
            window_size_seconds=60
        )
        
        assert config.requests_per_minute == 100
        assert config.burst_allowance == 25
        
        # Test serialization
        config_dict = config.to_dict()
        assert config_dict["requests_per_minute"] == 100
        assert config_dict["burst_allowance"] == 25


class TestRateLimiter:
    """Test cases for RateLimiter class."""
    
    def test_rate_limiter_initialization(self, mock_redis_client, mock_settings):
        """Test RateLimiter initialization."""
        limiter = RateLimiter(redis_client=mock_redis_client, settings=mock_settings)
        
        assert limiter.redis_client == mock_redis_client
        assert limiter.settings == mock_settings
        assert len(limiter.WINDOWS) == 3  # minute, hour, day
        assert "standard" in limiter.rate_limit_configs
        assert limiter.default_config.requests_per_minute == 60
    
    def test_load_rate_limit_configs(self, mock_redis_client, mock_settings):
        """Test loading rate limit configurations from settings."""
        limiter = RateLimiter(redis_client=mock_redis_client, settings=mock_settings)
        
        assert "basic" in limiter.rate_limit_configs
        assert "standard" in limiter.rate_limit_configs
        assert "premium" in limiter.rate_limit_configs
        assert "enterprise" in limiter.rate_limit_configs
        
        basic_config = limiter.rate_limit_configs["basic"]
        assert basic_config.requests_per_minute == 10
        assert basic_config.burst_allowance == 5
    
    def test_get_config_for_tier(self, rate_limiter):
        """Test getting configuration for specific tiers."""
        basic_config = rate_limiter._get_config_for_tier("basic")
        assert basic_config.requests_per_minute == 10
        
        premium_config = rate_limiter._get_config_for_tier("premium")
        assert premium_config.requests_per_minute == 300
        
        # Unknown tier should return default
        unknown_config = rate_limiter._get_config_for_tier("unknown")
        assert unknown_config == rate_limiter.default_config
    
    @pytest.mark.asyncio
    async def test_get_window_usage_empty(self, rate_limiter, mock_redis_client):
        """Test getting window usage for empty window."""
        # Mock empty window
        mock_redis_client._client.eval.return_value = 0
        
        usage = await rate_limiter._get_window_usage(
            identifier="test_user",
            window_name="minute",
            window_seconds=60,
            current_time=time.time()
        )
        
        assert usage == 0
    
    @pytest.mark.asyncio
    async def test_get_window_usage_with_requests(self, rate_limiter, mock_redis_client):
        """Test getting window usage with existing requests."""
        # Mock window with requests
        mock_redis_client._client.eval.return_value = 15
        
        usage = await rate_limiter._get_window_usage(
            identifier="test_user",
            window_name="minute",
            window_seconds=60,
            current_time=time.time()
        )
        
        assert usage == 15
    
    @pytest.mark.asyncio
    async def test_check_burst_allowance_available(self, rate_limiter, mock_redis_client):
        """Test burst allowance check with allowance available."""
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=1000,
            requests_per_day=10000,
            burst_allowance=50
        )
        
        # Mock burst allowance available
        mock_redis_client._client.eval.return_value = 1  # Allowed
        
        result = await rate_limiter._check_burst_allowance("test_user", config, 1)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_burst_allowance_exceeded(self, rate_limiter, mock_redis_client):
        """Test burst allowance check with allowance exceeded."""
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=1000,
            requests_per_day=10000,
            burst_allowance=50
        )
        
        # Mock burst allowance exceeded
        mock_redis_client._client.eval.return_value = 0  # Not allowed
        
        result = await rate_limiter._check_burst_allowance("test_user", config, 10)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter, mock_redis_client):
        """Test rate limit check that allows request."""
        # Mock low usage in all windows
        mock_redis_client._client.eval.return_value = 5  # Low usage
        
        result = await rate_limiter.check_rate_limit(
            identifier="test_user",
            tier="standard",
            cost=1
        )
        
        assert result.allowed is True
        assert result.remaining > 0
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked(self, rate_limiter, mock_redis_client):
        """Test rate limit check that blocks request."""
        # Mock high usage exceeding limit
        mock_redis_client._client.eval.side_effect = [100, 0]  # High usage, no burst allowance
        
        # Mock calculate retry after
        mock_redis_client._client.zrange.return_value = [(b"request", 1234567890)]
        
        result = await rate_limiter.check_rate_limit(
            identifier="test_user",
            tier="basic",  # Lower limits
            cost=1
        )
        
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after_seconds is not None
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_burst_saves(self, rate_limiter, mock_redis_client):
        """Test rate limit check where burst allowance saves the request."""
        # Mock usage at limit, but burst allowance available
        mock_redis_client._client.eval.side_effect = [60, 1]  # At limit, burst available
        
        result = await rate_limiter.check_rate_limit(
            identifier="test_user",
            tier="standard",
            cost=1
        )
        
        assert result.allowed is True
    
    @pytest.mark.asyncio
    async def test_record_request(self, rate_limiter, mock_redis_client):
        """Test recording a request in time windows."""
        await rate_limiter._record_request("test_user", 1, time.time())
        
        # Should add to all window types
        assert mock_redis_client._client.zadd.call_count >= len(rate_limiter.WINDOWS)
        mock_redis_client._client.expire.assert_called()
    
    @pytest.mark.asyncio
    async def test_calculate_retry_after_with_requests(self, rate_limiter, mock_redis_client):
        """Test retry-after calculation with existing requests."""
        # Mock oldest request timestamp
        oldest_time = time.time() - 30  # 30 seconds ago
        mock_redis_client._client.zrange.return_value = [(b"request", oldest_time)]
        
        retry_after = await rate_limiter._calculate_retry_after(
            identifier="test_user",
            window_name="minute",
            window_seconds=60,
            current_time=time.time(),
            limit=100
        )
        
        assert retry_after > 0
        assert retry_after <= 60
    
    @pytest.mark.asyncio
    async def test_calculate_retry_after_empty_window(self, rate_limiter, mock_redis_client):
        """Test retry-after calculation with empty window."""
        # Mock empty window
        mock_redis_client._client.zrange.return_value = []
        
        retry_after = await rate_limiter._calculate_retry_after(
            identifier="test_user",
            window_name="minute",
            window_seconds=60,
            current_time=time.time(),
            limit=100
        )
        
        assert retry_after == 60  # Default fallback
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self, rate_limiter, mock_redis_client):
        """Test getting rate limit status for an identifier."""
        # Mock window usage
        mock_redis_client._client.eval.return_value = 25
        
        # Mock burst allowance data
        burst_data = {"usage": 5, "last_reset": time.time()}
        mock_redis_client.get.return_value = json.dumps(burst_data)
        
        status = await rate_limiter.get_rate_limit_status("test_user", "standard")
        
        assert "identifier" in status
        assert "tier" in status
        assert "windows" in status
        assert "burst_allowance" in status
        assert "minute" in status["windows"]
        assert "hour" in status["windows"]
        assert "day" in status["windows"]
        assert status["burst_allowance"]["used"] == 5
    
    @pytest.mark.asyncio
    async def test_reset_rate_limit(self, rate_limiter, mock_redis_client):
        """Test resetting rate limits for an identifier."""
        result = await rate_limiter.reset_rate_limit("test_user")
        
        assert result is True
        # Should delete from all window keys
        mock_redis_client.delete.assert_called()
        # Should remove from blocked set
        mock_redis_client._client.srem.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_blocked_identifiers(self, rate_limiter, mock_redis_client):
        """Test getting list of blocked identifiers."""
        # Mock blocked identifiers
        mock_redis_client._client.smembers.return_value = {"user1", "user2"}
        
        # Mock status for each user
        async def mock_get_status(identifier, tier="standard"):
            return {
                "identifier": identifier,
                "tier": tier,
                "windows": {"minute": {"usage_percent": 100}},
                "timestamp": time.time()
            }
        
        rate_limiter.get_rate_limit_status = mock_get_status
        
        blocked_list = await rate_limiter.get_blocked_identifiers()
        
        assert len(blocked_list) == 2
        assert all("identifier" in item for item in blocked_list)
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_data(self, rate_limiter, mock_redis_client):
        """Test cleanup of expired rate limit data."""
        count = await rate_limiter.cleanup_expired_data()
        
        assert count >= 0
        # Should update cleanup timestamp
        mock_redis_client._client.hset.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_stats(self, rate_limiter, mock_redis_client):
        """Test getting rate limiter statistics."""
        # Mock statistics
        mock_redis_client._client.hgetall.return_value = {
            "allowed": "1000",
            "blocked": "50",
            "resets": "5"
        }
        mock_redis_client._client.scard.return_value = 10  # Currently blocked
        
        stats = await rate_limiter.get_rate_limit_stats()
        
        assert "total_requests" in stats
        assert "allowed_requests" in stats
        assert "blocked_requests" in stats
        assert "block_rate_percent" in stats
        assert "currently_blocked_identifiers" in stats
        assert stats["allowed_requests"] == 1000
        assert stats["blocked_requests"] == 50
        assert stats["currently_blocked_identifiers"] == 10
        assert stats["block_rate_percent"] == 4.76  # 50/1050 * 100
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self, rate_limiter, mock_redis_client):
        """Test error handling in rate limit operations."""
        # Mock Redis failure
        mock_redis_client._client.eval.side_effect = Exception("Redis connection lost")
        
        # Should fail open (allow request) on Redis errors
        result = await rate_limiter.check_rate_limit("test_user", "standard")
        
        assert result.allowed is True  # Fails open
        assert result.limit == 9999999  # Fallback limit
    
    @pytest.mark.asyncio
    async def test_multiple_time_windows(self, rate_limiter, mock_redis_client):
        """Test that all time windows are checked."""
        # Mock different usage levels for different windows
        usage_values = [30, 500, 5000]  # minute, hour, day
        mock_redis_client._client.eval.side_effect = usage_values
        
        result = await rate_limiter.check_rate_limit("test_user", "standard", 1)
        
        # Should check all three windows
        assert mock_redis_client._client.eval.call_count == 3
    
    @pytest.mark.asyncio
    async def test_weighted_requests(self, rate_limiter, mock_redis_client):
        """Test rate limiting with weighted request costs."""
        # Mock low usage
        mock_redis_client._client.eval.return_value = 50
        
        # High-cost request
        result = await rate_limiter.check_rate_limit(
            identifier="test_user",
            tier="standard",
            cost=20  # High cost
        )
        
        # Should still be allowed if within limits
        assert result.current_usage > 50  # Should account for cost


class TestRateLimiterIntegration:
    """Integration-style tests for rate limiter workflows."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_progression(self, rate_limiter, mock_redis_client):
        """Test progression from allowed to blocked to reset."""
        identifier = "test_user"
        
        # Start with low usage - should be allowed
        mock_redis_client._client.eval.return_value = 5
        result1 = await rate_limiter.check_rate_limit(identifier, "basic", 1)
        assert result1.allowed is True
        
        # Increase to near limit - should still be allowed
        mock_redis_client._client.eval.return_value = 9
        result2 = await rate_limiter.check_rate_limit(identifier, "basic", 1)
        assert result2.allowed is True
        
        # Exceed limit, no burst - should be blocked
        mock_redis_client._client.eval.side_effect = [10, 0]  # At limit, no burst
        mock_redis_client._client.zrange.return_value = [(b"req", time.time())]
        result3 = await rate_limiter.check_rate_limit(identifier, "basic", 1)
        assert result3.allowed is False
        
        # Reset the user
        await rate_limiter.reset_rate_limit(identifier)
        
        # Should be allowed again
        mock_redis_client._client.eval.return_value = 0
        mock_redis_client._client.eval.side_effect = None
        result4 = await rate_limiter.check_rate_limit(identifier, "basic", 1)
        assert result4.allowed is True
    
    @pytest.mark.asyncio
    async def test_different_tiers_different_limits(self, rate_limiter, mock_redis_client):
        """Test that different tiers have different limits."""
        # Same usage level
        usage = 50
        mock_redis_client._client.eval.return_value = usage
        
        # Basic tier - should be blocked (limit is 10/minute)
        mock_redis_client._client.eval.side_effect = [50, 0]  # Over limit, no burst
        result_basic = await rate_limiter.check_rate_limit("user1", "basic", 1)
        assert result_basic.allowed is False
        
        # Premium tier - should be allowed (limit is 300/minute)
        mock_redis_client._client.eval.side_effect = None
        mock_redis_client._client.eval.return_value = usage
        result_premium = await rate_limiter.check_rate_limit("user2", "premium", 1)
        assert result_premium.allowed is True
    
    @pytest.mark.asyncio
    async def test_burst_allowance_workflow(self, rate_limiter, mock_redis_client):
        """Test burst allowance saves requests during spikes."""
        identifier = "bursty_user"
        
        # At rate limit but burst available
        mock_redis_client._client.eval.side_effect = [60, 1]  # At limit, burst available
        result = await rate_limiter.check_rate_limit(identifier, "standard", 5)
        assert result.allowed is True
        
        # Burst now used up
        mock_redis_client._client.eval.side_effect = [60, 0]  # At limit, no burst
        mock_redis_client._client.zrange.return_value = [(b"req", time.time())]
        result = await rate_limiter.check_rate_limit(identifier, "standard", 1)
        assert result.allowed is False
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, rate_limiter, mock_redis_client):
        """Test that statistics are properly tracked."""
        # Mock allowed request
        mock_redis_client._client.eval.return_value = 10
        await rate_limiter.check_rate_limit("user1", "standard", 1)
        
        # Should update allowed stats
        mock_redis_client._client.hincrby.assert_called_with(
            rate_limiter.RATE_LIMIT_STATS_KEY, "allowed", 1
        )
        
        # Mock blocked request
        mock_redis_client._client.eval.side_effect = [100, 0]  # Over limit, no burst
        mock_redis_client._client.zrange.return_value = [(b"req", time.time())]
        await rate_limiter.check_rate_limit("user2", "standard", 1)
        
        # Should update blocked stats and add to blocked set
        mock_redis_client._client.sadd.assert_called()
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_same_user(self, rate_limiter, mock_redis_client):
        """Test handling concurrent requests from same user."""
        # Mock window usage that changes with each call (simulating concurrent updates)
        usage_progression = [45, 46, 47, 48, 49]
        mock_redis_client._client.eval.side_effect = usage_progression
        
        # Multiple concurrent checks
        tasks = []
        for i in range(5):
            task = rate_limiter.check_rate_limit(f"user_{i}", "standard", 1)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All should be allowed (under limit)
        assert all(result.allowed for result in results)
    
    @pytest.mark.asyncio
    async def test_rate_limit_headers_calculation(self, rate_limiter, mock_redis_client):
        """Test calculation of rate limit headers for API responses."""
        # Mock current usage
        mock_redis_client._client.eval.return_value = 25
        
        result = await rate_limiter.check_rate_limit("test_user", "standard", 1)
        
        assert result.allowed is True
        assert result.current_usage == 26  # 25 + 1 (cost)
        assert result.remaining > 0
        assert result.reset_time > time.time()
        
        # These would typically be used to set HTTP headers:
        # X-RateLimit-Limit: result.limit
        # X-RateLimit-Remaining: result.remaining  
        # X-RateLimit-Reset: result.reset_time