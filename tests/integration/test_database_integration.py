"""
PostgreSQL + File Storage Integration Tests

Tests database connectivity, operations, and integration with all
storage-dependent components like API keys, rate limiting, and caching.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any

from src.database.connection import get_database, init_database
from src.cache.base import get_file_storage_client
from src.api.middleware import APIKeyManager, SlidingWindowRateLimiter, LLMProviderRateLimiter
from src.cache.result_cache import ResultCache
from src.core.config import get_settings


@pytest.fixture
async def database():
    """Get database connection for testing."""
    try:
        await init_database()
        db = await get_database()
        # Test connection
        result = await db.fetch_one("SELECT 1 as test")
        if not (result and result['test'] == 1):
            pytest.skip("Database connection test failed")
        yield db
        # Cleanup: clear test data
        await db.execute("DELETE FROM api_keys WHERE user_id LIKE 'test_%'")
        await db.execute("DELETE FROM rate_limits WHERE identifier LIKE 'test_%'")
        await db.execute("DELETE FROM cache_metadata WHERE cache_key LIKE 'test_%'")
        await db.execute("DELETE FROM sessions WHERE session_data LIKE '%test_%'")
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture
async def storage_client():
    """Get file storage client for testing."""
    try:
        client = await get_file_storage_client()
        health = await client.health_check()
        if not health:
            pytest.skip("File storage not healthy")
        yield client
        # Cleanup: remove test files
        import os
        import glob
        test_files = glob.glob("/tmp/test_*") + glob.glob("/tmp/storage/test_*")
        for test_file in test_files:
            try:
                if os.path.isfile(test_file):
                    os.remove(test_file)
            except:
                pass
    except Exception as e:
        pytest.skip(f"File storage not available: {e}")


@pytest.fixture
async def api_key_manager(database):
    """Get API key manager with database connection."""
    return APIKeyManager()


@pytest.fixture
async def rate_limiter(database):
    """Get rate limiter with database connection."""
    return SlidingWindowRateLimiter()


@pytest.fixture
async def llm_rate_limiter(database):
    """Get LLM rate limiter with database connection."""
    return LLMProviderRateLimiter()


@pytest.fixture
async def result_cache(database, storage_client):
    """Get result cache with hybrid storage."""
    return ResultCache()


class TestDatabaseIntegration:
    """Test PostgreSQL database integration."""
    
    @pytest.mark.asyncio
    async def test_database_connection(self, database):
        """Test basic database connectivity."""
        result = await database.fetch_one("SELECT version() as version")
        assert result is not None
        assert "PostgreSQL" in result["version"]
    
    @pytest.mark.asyncio
    async def test_database_schema(self, database):
        """Test database schema exists."""
        # Check that required tables exist
        tables = await database.fetch_all("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        table_names = [row["table_name"] for row in tables]
        
        required_tables = [
            "api_keys", "rate_limits", "cache_metadata", 
            "sessions", "jobs", "job_progress"
        ]
        
        for table in required_tables:
            assert table in table_names, f"Required table '{table}' not found"


class TestFileStorageIntegration:
    """Test file storage integration."""
    
    @pytest.mark.asyncio
    async def test_storage_health(self, storage_client):
        """Test file storage health check."""
        health = await storage_client.health_check()
        assert health is True
    
    @pytest.mark.asyncio
    async def test_file_operations(self, storage_client):
        """Test basic file operations."""
        test_key = "test_file_ops"
        test_data = {"message": "Hello, World!", "timestamp": datetime.now().isoformat()}
        
        # Test set
        success = await storage_client.set(test_key, test_data)
        assert success is True
        
        # Test get
        retrieved_data = await storage_client.get(test_key)
        assert retrieved_data is not None
        assert retrieved_data["message"] == "Hello, World!"
        
        # Test delete
        deleted = await storage_client.delete(test_key)
        assert deleted is True
        
        # Verify deletion
        retrieved_after_delete = await storage_client.get(test_key)
        assert retrieved_after_delete is None


class TestAPIKeyManagerIntegration:
    """Test API key manager with database backend."""
    
    @pytest.mark.asyncio
    async def test_create_and_validate_api_key(self, api_key_manager):
        """Test creating and validating API keys."""
        user_id = "test_user_123"
        
        # Create API key
        api_key, key_id = await api_key_manager.create_api_key(
            user_id=user_id,
            tier="standard",
            permissions=["read", "write"]
        )
        
        assert api_key is not None
        assert key_id is not None
        assert api_key.startswith("ak_")
        
        # Validate API key
        user_info = await api_key_manager.validate_api_key(api_key)
        assert user_info is not None
        assert user_info["user_id"] == user_id
        assert user_info["tier"] == "standard"
        assert "read" in user_info["permissions"]
        assert "write" in user_info["permissions"]
    
    @pytest.mark.asyncio
    async def test_list_user_keys(self, api_key_manager):
        """Test listing user API keys."""
        user_id = "test_user_list"
        
        # Create multiple keys
        key1, _ = await api_key_manager.create_api_key(user_id, "basic", ["read"])
        key2, _ = await api_key_manager.create_api_key(user_id, "premium", ["read", "write"])
        
        # List keys
        keys = await api_key_manager.list_user_keys(user_id)
        assert len(keys) == 2
        
        tiers = [key["tier"] for key in keys]
        assert "basic" in tiers
        assert "premium" in tiers


class TestRateLimiterIntegration:
    """Test rate limiter with database backend."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, rate_limiter):
        """Test rate limiting functionality."""
        identifier = "test_rate_limit_user"
        
        # First request should be allowed
        result = await rate_limiter.check_rate_limit(
            identifier=identifier,
            tier="basic",
            cost=1
        )
        assert result.allowed is True
        assert result.current_usage == 1
        
        # Additional requests within limit should be allowed
        for _ in range(4):  # Basic tier typically allows 5 per minute
            result = await rate_limiter.check_rate_limit(
                identifier=identifier,
                tier="basic", 
                cost=1
            )
            assert result.allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_status(self, rate_limiter):
        """Test rate limit status retrieval."""
        identifier = "test_status_user"
        
        # Make a request to initialize
        await rate_limiter.check_rate_limit(identifier, "basic", 1)
        
        # Check status
        status = await rate_limiter.get_rate_limit_status(identifier, "basic")
        assert "current" in status
        assert "remaining" in status
        assert status["current"] > 0


class TestResultCacheIntegration:
    """Test result cache with hybrid storage."""
    
    @pytest.mark.asyncio
    async def test_cache_operations(self, result_cache):
        """Test cache set/get operations."""
        cache_key = "test_cache_integration"
        test_data = {
            "decompilation_results": {"functions": 42, "strings": 123},
            "metadata": {"timestamp": datetime.now().isoformat()}
        }
        
        # Test cache set
        await result_cache.set(cache_key, test_data, ttl_seconds=300)
        
        # Test cache get
        cached_data = await result_cache.get(cache_key)
        assert cached_data is not None
        assert cached_data["decompilation_results"]["functions"] == 42
        assert cached_data["decompilation_results"]["strings"] == 123
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, result_cache):
        """Test cache TTL functionality."""
        cache_key = "test_cache_expiry"
        test_data = {"temporary": "data"}
        
        # Set with very short TTL
        await result_cache.set(cache_key, test_data, ttl_seconds=1)
        
        # Should be available immediately
        cached = await result_cache.get(cache_key)
        assert cached is not None
        
        # Wait for expiration and check
        await asyncio.sleep(2)
        expired = await result_cache.get(cache_key)
        assert expired is None


class TestLLMRateLimiterIntegration:
    """Test LLM rate limiter with database backend."""
    
    @pytest.mark.asyncio
    async def test_llm_rate_limiting(self, llm_rate_limiter):
        """Test LLM provider rate limiting."""
        user_id = "test_llm_user"
        provider_id = "test_provider"
        
        # Check LLM rate limit
        allowed, reason, stats = await llm_rate_limiter.check_llm_rate_limit(
            user_id=user_id,
            provider_id=provider_id,
            estimated_tokens=100
        )
        
        assert allowed is True
        assert reason == ""
        
        # Record usage
        await llm_rate_limiter.record_llm_usage(
            user_id=user_id,
            provider_id=provider_id,
            tokens_used=150
        )
        
        # Get usage stats
        stats = await llm_rate_limiter.get_llm_usage_stats(user_id, provider_id)
        assert provider_id in stats
        assert "requests_used" in stats[provider_id]
        assert "tokens_used" in stats[provider_id]


class TestEndToEndIntegration:
    """Test end-to-end integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_api_workflow(self, api_key_manager, rate_limiter, result_cache):
        """Test complete API request workflow."""
        user_id = "test_e2e_user"
        
        # 1. Create API key
        api_key, _ = await api_key_manager.create_api_key(
            user_id=user_id,
            tier="standard",
            permissions=["read", "write"]
        )
        
        # 2. Validate API key
        user_info = await api_key_manager.validate_api_key(api_key)
        assert user_info["user_id"] == user_id
        
        # 3. Check rate limits
        rate_result = await rate_limiter.check_rate_limit(
            identifier=f"user:{user_id}",
            tier=user_info["tier"],
            cost=1
        )
        assert rate_result.allowed is True
        
        # 4. Cache some results
        cache_key = f"user:{user_id}:results"
        results = {"analysis": "complete", "user": user_id}
        await result_cache.set(cache_key, results, ttl_seconds=600)
        
        # 5. Retrieve cached results
        cached_results = await result_cache.get(cache_key)
        assert cached_results["user"] == user_id
        assert cached_results["analysis"] == "complete"