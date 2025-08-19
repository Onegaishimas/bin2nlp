"""
Redis Integration Tests

Tests Redis connectivity, operations, and integration with all
cache-dependent components like API keys, rate limiting, and caching.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

from src.cache.base import get_redis_client, RedisConnectionError
from src.api.middleware import APIKeyManager, SlidingWindowRateLimiter, LLMProviderRateLimiter
from src.cache.result_cache import ResultCache
from src.core.config import get_settings


@pytest.fixture
async def redis_client():
    """Get Redis client for testing."""
    try:
        client = await get_redis_client()
        # Test connection
        await client.ping()
        yield client
        # Cleanup: flush test data
        await client.flushdb()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture
async def api_key_manager(redis_client):
    """Get API key manager with Redis client."""
    return APIKeyManager()


@pytest.fixture
async def rate_limiter(redis_client):
    """Get rate limiter with Redis client."""
    return SlidingWindowRateLimiter()


@pytest.fixture
async def llm_rate_limiter(redis_client):
    """Get LLM rate limiter with Redis client."""
    return LLMProviderRateLimiter()


class TestRedisConnectivity:
    """Test basic Redis connectivity and operations."""
    
    async def test_redis_connection(self, redis_client):
        """Test Redis connection is working."""
        response = await redis_client.ping()
        assert response is True
    
    async def test_redis_basic_operations(self, redis_client):
        """Test basic Redis read/write operations."""
        # String operations
        await redis_client.set("test_key", "test_value")
        value = await redis_client.get("test_key")
        assert value == "test_value"
        
        # Hash operations
        await redis_client.hset("test_hash", mapping={"field1": "value1", "field2": "value2"})
        hash_data = await redis_client.hgetall("test_hash")
        assert hash_data == {"field1": "value1", "field2": "value2"}
        
        # List operations
        await redis_client.lpush("test_list", "item1", "item2")
        list_items = await redis_client.lrange("test_list", 0, -1)
        assert "item1" in list_items and "item2" in list_items
        
        # Cleanup
        await redis_client.delete("test_key", "test_hash", "test_list")
    
    async def test_redis_expiration(self, redis_client):
        """Test Redis key expiration functionality."""
        await redis_client.set("expire_test", "value", ex=1)  # 1 second expiry
        
        # Should exist immediately
        value = await redis_client.get("expire_test")
        assert value == "value"
        
        # Wait for expiry
        await asyncio.sleep(1.1)
        value = await redis_client.get("expire_test")
        assert value is None
    
    async def test_redis_info_command(self, redis_client):
        """Test Redis info command for system monitoring."""
        info = await redis_client.info()
        assert isinstance(info, dict)
        assert "redis_version" in info
        assert "connected_clients" in info
        assert "used_memory" in info


class TestAPIKeyRedisIntegration:
    """Test API key management with Redis backend."""
    
    async def test_create_and_validate_api_key(self, api_key_manager):
        """Test API key creation and validation cycle."""
        # Create API key
        api_key, key_id = await api_key_manager.create_api_key(
            user_id="test_user",
            tier="standard",
            permissions=["read", "write"]
        )
        
        assert api_key.startswith("ak_")  # Default prefix
        assert len(key_id) == 16  # 8 bytes hex = 16 chars
        
        # Validate API key
        user_info = await api_key_manager.validate_api_key(api_key)
        assert user_info is not None
        assert user_info["user_id"] == "test_user"
        assert user_info["tier"] == "standard"
        assert "read" in user_info["permissions"]
        assert "write" in user_info["permissions"]
    
    async def test_list_user_keys(self, api_key_manager):
        """Test listing API keys for a user."""
        user_id = "test_user_list"
        
        # Create multiple keys
        key1, _ = await api_key_manager.create_api_key(user_id, "basic", ["read"])
        key2, _ = await api_key_manager.create_api_key(user_id, "premium", ["read", "write"])
        
        # List keys
        keys = await api_key_manager.list_user_keys(user_id)
        assert len(keys) == 2
        
        # Verify key properties
        tiers = [key["tier"] for key in keys]
        assert "basic" in tiers
        assert "premium" in tiers
    
    async def test_invalid_api_key(self, api_key_manager):
        """Test validation of invalid API keys."""
        # Test completely invalid key
        result = await api_key_manager.validate_api_key("invalid_key")
        assert result is None
        
        # Test key with wrong prefix
        result = await api_key_manager.validate_api_key("wrong_prefix_" + "a" * 20)
        assert result is None
        
        # Test properly formatted but non-existent key
        result = await api_key_manager.validate_api_key("ak_" + "a" * 43)
        assert result is None


class TestRateLimitingRedisIntegration:
    """Test rate limiting with Redis backend."""
    
    async def test_sliding_window_rate_limiting(self, rate_limiter):
        """Test sliding window rate limiting implementation."""
        identifier = "test_user"
        window_seconds = 60
        max_requests = 5
        
        # Should allow initial requests
        for i in range(max_requests):
            allowed, retry_after, stats = await rate_limiter.check_rate_limit(
                identifier, window_seconds, max_requests
            )
            assert allowed is True
            assert retry_after == 0
            assert stats["current"] == i + 1
            assert stats["remaining"] >= 0
        
        # Should deny next request
        allowed, retry_after, stats = await rate_limiter.check_rate_limit(
            identifier, window_seconds, max_requests
        )
        assert allowed is False
        assert retry_after > 0
        assert stats["current"] >= max_requests
    
    async def test_rate_limit_burst_allowance(self, rate_limiter):
        """Test burst allowance in rate limiting."""
        identifier = "test_burst_user"
        window_seconds = 60
        max_requests = 3
        burst_allowance = 2
        
        # Should allow requests up to limit + burst
        total_allowed = max_requests + burst_allowance
        for i in range(total_allowed):
            allowed, retry_after, stats = await rate_limiter.check_rate_limit(
                identifier, window_seconds, max_requests, burst_allowance
            )
            assert allowed is True
            assert retry_after == 0
        
        # Should deny beyond limit + burst
        allowed, retry_after, stats = await rate_limiter.check_rate_limit(
            identifier, window_seconds, max_requests, burst_allowance
        )
        assert allowed is False
        assert retry_after > 0
    
    async def test_rate_limit_status_check(self, rate_limiter):
        """Test rate limit status checking."""
        identifier = "status_test_user"
        window_seconds = 60
        
        # Check status before any requests
        status = await rate_limiter.get_rate_limit_status(identifier, window_seconds)
        assert status["current"] == 0
        assert status["window_seconds"] == window_seconds
        
        # Make some requests
        await rate_limiter.check_rate_limit(identifier, window_seconds, 10)
        await rate_limiter.check_rate_limit(identifier, window_seconds, 10)
        
        # Check status after requests
        status = await rate_limiter.get_rate_limit_status(identifier, window_seconds)
        assert status["current"] == 2


class TestLLMRateLimitingRedisIntegration:
    """Test LLM-specific rate limiting with Redis."""
    
    async def test_llm_request_rate_limiting(self, llm_rate_limiter):
        """Test LLM request rate limiting."""
        user_id = "llm_test_user"
        provider_id = "openai"
        
        # Should allow initial requests
        allowed, reason, stats = await llm_rate_limiter.check_llm_rate_limit(
            user_id, provider_id, estimated_tokens=100
        )
        assert allowed is True
        assert reason == ""
        
        # Record usage
        await llm_rate_limiter.record_llm_usage(user_id, provider_id, tokens_used=100)
        
        # Get usage stats
        usage_stats = await llm_rate_limiter.get_llm_usage_stats(user_id, provider_id)
        assert provider_id in usage_stats
        assert usage_stats[provider_id]["requests_used"] >= 1
        assert usage_stats[provider_id]["tokens_used"] >= 100
    
    async def test_llm_token_rate_limiting(self, llm_rate_limiter):
        """Test LLM token-based rate limiting."""
        user_id = "token_test_user"
        provider_id = "anthropic"
        
        settings = get_settings()
        token_limit = settings.llm.tokens_per_minute
        
        # Should allow request within token limit
        allowed, reason, stats = await llm_rate_limiter.check_llm_rate_limit(
            user_id, provider_id, estimated_tokens=token_limit // 2
        )
        assert allowed is True
        
        # Should deny request that exceeds token limit
        allowed, reason, stats = await llm_rate_limiter.check_llm_rate_limit(
            user_id, provider_id, estimated_tokens=token_limit * 2
        )
        assert allowed is False
        assert "tokens per minute" in reason.lower()


class TestResultCacheRedisIntegration:
    """Test result caching with Redis backend."""
    
    async def test_cache_storage_and_retrieval(self, redis_client):
        """Test basic cache operations."""
        cache = ResultCache()
        
        # Store data in cache
        test_data = {
            "analysis_id": "test_123",
            "results": {"functions": 10, "strings": 50},
            "metadata": {"timestamp": datetime.now().isoformat()}
        }
        
        cache_key = "test_analysis:test_123"
        await cache.set(cache_key, test_data, ttl_seconds=300)
        
        # Retrieve data from cache
        cached_data = await cache.get(cache_key)
        assert cached_data is not None
        assert cached_data["analysis_id"] == "test_123"
        assert cached_data["results"]["functions"] == 10
    
    async def test_cache_expiration(self, redis_client):
        """Test cache TTL functionality."""
        cache = ResultCache()
        
        # Store with short TTL
        test_data = {"test": "data"}
        cache_key = "expire_test"
        await cache.set(cache_key, test_data, ttl_seconds=1)
        
        # Should exist immediately
        cached_data = await cache.get(cache_key)
        assert cached_data is not None
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        cached_data = await cache.get(cache_key)
        assert cached_data is None
    
    async def test_cache_stats(self, redis_client):
        """Test cache statistics and monitoring."""
        cache = ResultCache()
        
        # Store some test data
        for i in range(5):
            await cache.set(f"stats_test_{i}", {"data": i})
        
        # Get cache stats
        stats = await cache.get_stats()
        assert isinstance(stats, dict)
        assert "total_keys" in stats or "info" in stats


class TestEndToEndRedisIntegration:
    """Test complete workflows that depend on Redis."""
    
    async def test_authentication_with_rate_limiting_flow(self, api_key_manager, rate_limiter):
        """Test complete auth + rate limiting workflow."""
        # Create API key
        api_key, key_id = await api_key_manager.create_api_key(
            user_id="integration_test_user",
            tier="basic",
            permissions=["read"]
        )
        
        # Validate API key
        user_info = await api_key_manager.validate_api_key(api_key)
        assert user_info is not None
        
        # Test rate limiting for this user
        user_identifier = f"user:{user_info['user_id']}"
        
        # Should allow requests within rate limit
        for i in range(3):  # Basic tier allows more than this
            allowed, _, _ = await rate_limiter.check_rate_limit(
                user_identifier, 60, 10  # 10 requests per minute
            )
            assert allowed is True
    
    async def test_redis_failure_handling(self):
        """Test graceful handling of Redis connection failures."""
        # This test would need to mock Redis failures
        # For now, we'll test that our connection wrapper handles errors gracefully
        try:
            # Attempt to connect to non-existent Redis instance
            from src.cache.base import RedisClient
            client = RedisClient("localhost", 9999)  # Wrong port
            await client.connect()
            assert False, "Should have raised connection error"
        except RedisConnectionError:
            # Expected behavior
            pass


@pytest.mark.slow
class TestRedisPerformance:
    """Performance tests for Redis operations."""
    
    async def test_bulk_api_key_operations(self, api_key_manager):
        """Test performance of bulk API key operations."""
        import time
        
        start_time = time.time()
        
        # Create multiple API keys
        keys_created = []
        for i in range(10):
            api_key, key_id = await api_key_manager.create_api_key(
                user_id=f"perf_test_user_{i}",
                tier="standard"
            )
            keys_created.append((api_key, key_id))
        
        create_time = time.time() - start_time
        
        # Validate all keys
        start_time = time.time()
        for api_key, key_id in keys_created:
            user_info = await api_key_manager.validate_api_key(api_key)
            assert user_info is not None
        
        validate_time = time.time() - start_time
        
        # Performance assertions (adjust based on system)
        assert create_time < 5.0, f"Key creation too slow: {create_time}s"
        assert validate_time < 2.0, f"Key validation too slow: {validate_time}s"
    
    async def test_rate_limit_performance(self, rate_limiter):
        """Test rate limiting performance under load."""
        import time
        
        identifier = "perf_test_user"
        
        start_time = time.time()
        
        # Make many rate limit checks
        for i in range(50):
            await rate_limiter.check_rate_limit(identifier, 60, 100)
        
        elapsed_time = time.time() - start_time
        
        # Should handle 50 checks quickly
        assert elapsed_time < 2.0, f"Rate limiting too slow: {elapsed_time}s"


if __name__ == "__main__":
    # Run tests with: pytest tests/integration/test_redis_integration.py -v
    pytest.main([__file__, "-v"])