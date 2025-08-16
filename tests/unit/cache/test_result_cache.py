"""
Unit tests for result cache system.

Tests cache key generation, TTL management, invalidation patterns,
and cache statistics with mocked Redis operations.
"""

import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.cache.result_cache import ResultCache, CacheEntry
from src.cache.base import RedisClient
from src.core.config import Settings, CacheSettings
from src.core.exceptions import CacheException


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client for result cache testing."""
    redis_mock = AsyncMock(spec=RedisClient)
    redis_mock._client = AsyncMock()
    
    # Mock basic Redis operations
    redis_mock._client.sadd = AsyncMock(return_value=1)
    redis_mock._client.srem = AsyncMock(return_value=1)
    redis_mock._client.smembers = AsyncMock(return_value=set())
    redis_mock._client.hincrby = AsyncMock(return_value=1)
    redis_mock._client.hset = AsyncMock(return_value=1)
    redis_mock._client.hgetall = AsyncMock(return_value={})
    
    # Mock pipeline operations
    redis_mock.pipeline = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.execute = AsyncMock(return_value=[True, True, True])
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=None)
    redis_mock.pipeline.return_value = mock_pipeline
    
    # Mock get/set/delete operations
    redis_mock.get = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.info = AsyncMock(return_value={"used_memory": 1024})
    
    return redis_mock


@pytest.fixture
def mock_settings():
    """Create mock settings for result cache testing."""
    settings = MagicMock(spec=Settings)
    settings.cache = MagicMock(spec=CacheSettings)
    settings.cache.analysis_result_ttl_seconds = 86400  # 24 hours
    return settings


@pytest.fixture
def result_cache(mock_redis_client, mock_settings):
    """Create ResultCache instance with mocked dependencies."""
    cache = ResultCache(redis_client=mock_redis_client, settings=mock_settings)
    return cache


@pytest.fixture
def sample_analysis_config():
    """Create sample analysis configuration for testing."""
    return {
        "depth": "standard",
        "timeout_seconds": 300,
        "focus_areas": ["security", "functions"],
        "enable_security_scan": True,
        "max_functions": 10000,
        "max_strings": 50000
    }


@pytest.fixture
def sample_result_data():
    """Create sample analysis result data for testing."""
    return {
        "analysis_id": "analysis_123",
        "file_format": "pe",
        "platform": "windows",
        "success": True,
        "functions": [
            {"name": "main", "address": "0x401000", "size": 256},
            {"name": "helper", "address": "0x401100", "size": 128}
        ],
        "security_findings": {
            "risk_score": 5.5,
            "network_behaviors": ["HTTP requests"],
            "file_operations": ["File creation"]
        },
        "statistics": {
            "total_functions": 2,
            "analysis_duration_seconds": 45.0
        }
    }


class TestCacheEntry:
    """Test cases for CacheEntry dataclass."""
    
    def test_cache_entry_creation(self):
        """Test CacheEntry creation and methods."""
        current_time = time.time()
        cache_entry = CacheEntry(
            key="test_key",
            data={"test": "data"},
            created_at=current_time,
            expires_at=current_time + 3600,
            cache_version="1.0",
            file_hash="abc123",
            config_hash="def456",
            tags={"tag1", "tag2"}
        )
        
        assert cache_entry.key == "test_key"
        assert cache_entry.data == {"test": "data"}
        assert not cache_entry.is_expired()
        assert cache_entry.ttl_seconds() > 0
        assert cache_entry.age_seconds() >= 0
    
    def test_cache_entry_expired(self):
        """Test expired cache entry detection."""
        current_time = time.time()
        cache_entry = CacheEntry(
            key="expired_key",
            data={"test": "data"},
            created_at=current_time - 7200,  # 2 hours ago
            expires_at=current_time - 3600,  # 1 hour ago (expired)
            cache_version="1.0",
            file_hash="abc123",
            config_hash="def456",
            tags=set()
        )
        
        assert cache_entry.is_expired()
        assert cache_entry.ttl_seconds() == 0


class TestResultCache:
    """Test cases for ResultCache class."""
    
    def test_result_cache_initialization(self, mock_redis_client, mock_settings):
        """Test ResultCache initialization."""
        cache = ResultCache(redis_client=mock_redis_client, settings=mock_settings)
        
        assert cache.redis_client == mock_redis_client
        assert cache.settings == mock_settings
        assert cache.default_ttl == 86400
        assert cache.CACHE_VERSION == "1.0"
    
    def test_generate_config_hash(self, result_cache, sample_analysis_config):
        """Test configuration hash generation."""
        hash1 = result_cache._generate_config_hash(sample_analysis_config)
        
        # Same config should produce same hash
        hash2 = result_cache._generate_config_hash(sample_analysis_config)
        assert hash1 == hash2
        
        # Different config should produce different hash
        modified_config = sample_analysis_config.copy()
        modified_config["depth"] = "comprehensive"
        hash3 = result_cache._generate_config_hash(modified_config)
        assert hash1 != hash3
    
    def test_generate_config_hash_normalization(self, result_cache):
        """Test configuration hash normalization."""
        config1 = {
            "depth": "standard",
            "focus_areas": ["security", "functions"],
            "extra_param": "ignored"  # This should be ignored
        }
        
        config2 = {
            "focus_areas": ["functions", "security"],  # Different order
            "depth": "standard",
            "other_param": "also_ignored"  # This should also be ignored
        }
        
        hash1 = result_cache._generate_config_hash(config1)
        hash2 = result_cache._generate_config_hash(config2)
        
        # Should be same due to normalization
        assert hash1 == hash2
    
    def test_generate_cache_key(self, result_cache):
        """Test cache key generation."""
        file_hash = "a" * 64  # SHA-256 hash
        config_hash = "config123"
        
        cache_key = result_cache._generate_cache_key(file_hash, config_hash)
        
        assert "result:" in cache_key
        assert config_hash in cache_key
        assert len(cache_key) <= result_cache.max_key_length
    
    def test_generate_cache_key_long(self, result_cache):
        """Test cache key generation for very long keys."""
        file_hash = "a" * 64
        config_hash = "b" * 200  # Very long config hash
        
        cache_key = result_cache._generate_cache_key(file_hash, config_hash)
        
        # Should be hashed to keep under limit
        assert len(cache_key) <= result_cache.max_key_length
        assert "result:hash:" in cache_key
    
    def test_get_ttl_for_config(self, result_cache):
        """Test TTL calculation based on configuration."""
        # Quick analysis - shorter TTL
        quick_config = {"depth": "quick"}
        quick_ttl = result_cache._get_ttl_for_config(quick_config)
        assert quick_ttl == result_cache.default_ttl * 0.5
        
        # Standard analysis - default TTL
        standard_config = {"depth": "standard"}
        standard_ttl = result_cache._get_ttl_for_config(standard_config)
        assert standard_ttl == result_cache.default_ttl
        
        # Comprehensive analysis - longer TTL
        comprehensive_config = {"depth": "comprehensive"}
        comprehensive_ttl = result_cache._get_ttl_for_config(comprehensive_config)
        assert comprehensive_ttl == result_cache.default_ttl * 2.0
        
        # Deep analysis - longest TTL
        deep_config = {"depth": "deep"}
        deep_ttl = result_cache._get_ttl_for_config(deep_config)
        assert deep_ttl == result_cache.default_ttl * 3.0
    
    def test_extract_tags(self, result_cache, sample_analysis_config):
        """Test tag extraction from configuration."""
        file_hash = "abc123"
        tags = result_cache._extract_tags(file_hash, sample_analysis_config)
        
        assert "depth:standard" in tags
        assert "security_scan" in tags
        assert any("focus:" in tag for tag in tags)
    
    @pytest.mark.asyncio
    async def test_get_cache_hit(self, result_cache, mock_redis_client, sample_result_data):
        """Test successful cache hit."""
        file_hash = "abc123"
        config = {"depth": "standard"}
        
        # Mock cached data
        cached_entry = {
            "data": sample_result_data,
            "cache_version": "1.0",
            "created_at": time.time(),
            "expires_at": time.time() + 3600
        }
        mock_redis_client.get.return_value = cached_entry
        
        result = await result_cache.get(file_hash, config)
        
        assert result == sample_result_data
        mock_redis_client.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_cache_miss(self, result_cache, mock_redis_client):
        """Test cache miss."""
        file_hash = "abc123"
        config = {"depth": "standard"}
        
        # Mock cache miss
        mock_redis_client.get.return_value = None
        
        result = await result_cache.get(file_hash, config)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_version_mismatch(self, result_cache, mock_redis_client, sample_result_data):
        """Test cache version mismatch handling."""
        file_hash = "abc123"
        config = {"depth": "standard"}
        
        # Mock cached data with old version
        cached_entry = {
            "data": sample_result_data,
            "cache_version": "0.9",  # Old version
            "created_at": time.time(),
            "expires_at": time.time() + 3600
        }
        mock_redis_client.get.return_value = cached_entry
        
        result = await result_cache.get(file_hash, config)
        
        assert result is None  # Should be None due to version mismatch
        # Should trigger deletion
        mock_redis_client.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_set_cache_success(self, result_cache, mock_redis_client, sample_result_data, sample_analysis_config):
        """Test successful cache set operation."""
        file_hash = "abc123"
        
        result = await result_cache.set(file_hash, sample_analysis_config, sample_result_data)
        
        assert result is True
        mock_redis_client.set.assert_called()
        
        # Should also add to sets for indexing
        mock_redis_client._client.sadd.assert_called()
    
    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, result_cache, mock_redis_client, sample_result_data):
        """Test cache set with custom TTL."""
        file_hash = "abc123"
        config = {"depth": "standard"}
        custom_ttl = 7200  # 2 hours
        
        result = await result_cache.set(file_hash, config, sample_result_data, ttl_override=custom_ttl)
        
        assert result is True
        # Verify TTL was used in set call
        call_args = mock_redis_client.set.call_args
        assert call_args[1]['ex'] == custom_ttl
    
    @pytest.mark.asyncio
    async def test_delete_cache_entry(self, result_cache, mock_redis_client):
        """Test cache entry deletion."""
        file_hash = "abc123"
        config = {"depth": "standard"}
        
        # Mock existing entry
        cached_entry = {
            "data": {"test": "data"},
            "cache_version": "1.0",
            "tags": ["depth:standard", "security_scan"]
        }
        mock_redis_client.get.return_value = cached_entry
        
        result = await result_cache.delete(file_hash, config)
        
        assert result is True
        mock_redis_client.delete.assert_called()
        # Should also remove from tag sets
        mock_redis_client._client.srem.assert_called()
    
    @pytest.mark.asyncio
    async def test_invalidate_by_file(self, result_cache, mock_redis_client):
        """Test cache invalidation by file hash."""
        file_hash = "abc123"
        
        # Mock cached entries for this file
        mock_redis_client._client.smembers.return_value = ["cache_key_1", "cache_key_2"]
        
        count = await result_cache.invalidate_by_file(file_hash)
        
        assert count == 2
        mock_redis_client.delete.assert_called_with("cache_key_1", "cache_key_2")
    
    @pytest.mark.asyncio
    async def test_invalidate_by_tag(self, result_cache, mock_redis_client):
        """Test cache invalidation by tag."""
        tag = "depth:comprehensive"
        
        # Mock cached entries with this tag
        mock_redis_client._client.smembers.return_value = ["cache_key_1", "cache_key_3"]
        
        count = await result_cache.invalidate_by_tag(tag)
        
        assert count == 2
        mock_redis_client.delete.assert_called_with("cache_key_1", "cache_key_3")
    
    @pytest.mark.asyncio
    async def test_get_cache_info(self, result_cache, mock_redis_client):
        """Test cache entry info retrieval."""
        cache_key = "result:abc123:def456"
        
        # Mock cache entry
        current_time = time.time()
        cached_entry = {
            "created_at": current_time - 3600,  # 1 hour ago
            "expires_at": current_time + 3600,  # 1 hour from now
            "cache_version": "1.0",
            "file_hash": "abc123",
            "config_hash": "def456",
            "tags": ["depth:standard", "security_scan"],
            "access_count": 5,
            "data": {"test": "data"}
        }
        mock_redis_client.get.return_value = cached_entry
        
        info = await result_cache.get_cache_info(cache_key)
        
        assert info is not None
        assert "cache_key" in info
        assert "age_seconds" in info
        assert "ttl_seconds" in info
        assert info["access_count"] == 5
        assert len(info["tags"]) == 2
    
    @pytest.mark.asyncio
    async def test_get_cache_stats(self, result_cache, mock_redis_client):
        """Test cache statistics retrieval."""
        # Mock statistics
        mock_redis_client._client.hgetall.return_value = {
            "hits": "100",
            "misses": "20", 
            "sets": "80",
            "deletes": "5"
        }
        
        stats = await result_cache.get_cache_stats()
        
        assert "hit_ratio_percent" in stats
        assert "total_requests" in stats
        assert stats["hits"] == 100
        assert stats["misses"] == 20
        assert stats["hit_ratio_percent"] == 83.33  # 100/120 * 100
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self, result_cache, mock_redis_client):
        """Test expired cache cleanup."""
        count = await result_cache.cleanup_expired()
        
        # Should update cleanup timestamp
        mock_redis_client._client.hset.assert_called()
        assert count >= 0
    
    @pytest.mark.asyncio
    async def test_error_handling_redis_failure(self, result_cache, mock_redis_client):
        """Test error handling when Redis operations fail."""
        file_hash = "abc123"
        config = {"depth": "standard"}
        
        # Mock Redis failure
        mock_redis_client.get.side_effect = Exception("Redis connection lost")
        
        # Should not raise exception, should return None
        result = await result_cache.get(file_hash, config)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalid_json_handling(self, result_cache, mock_redis_client):
        """Test handling of invalid JSON in cached data."""
        file_hash = "abc123"
        config = {"depth": "standard"}
        
        # Mock invalid JSON
        mock_redis_client.get.return_value = "invalid_json_data"
        
        result = await result_cache.get(file_hash, config)
        
        assert result is None
        # Should trigger deletion of corrupted data
        mock_redis_client.delete.assert_called()


class TestResultCacheIntegration:
    """Integration-style tests for result cache workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_cache_cycle(self, result_cache, mock_redis_client, sample_result_data, sample_analysis_config):
        """Test complete cache cycle: set -> get -> delete."""
        file_hash = "integration_test_hash"
        
        # 1. Set cache entry
        set_result = await result_cache.set(file_hash, sample_analysis_config, sample_result_data)
        assert set_result is True
        
        # Mock the cached data for retrieval
        current_time = time.time()
        cached_entry = {
            "data": sample_result_data,
            "created_at": current_time,
            "expires_at": current_time + 3600,
            "cache_version": "1.0",
            "file_hash": file_hash,
            "config_hash": "test_hash",
            "tags": ["depth:standard", "security_scan"],
            "access_count": 0
        }
        mock_redis_client.get.return_value = cached_entry
        
        # 2. Get cache entry
        get_result = await result_cache.get(file_hash, sample_analysis_config)
        assert get_result == sample_result_data
        
        # 3. Delete cache entry
        delete_result = await result_cache.delete(file_hash, sample_analysis_config)
        assert delete_result is True
    
    @pytest.mark.asyncio
    async def test_cache_with_different_configs(self, result_cache, mock_redis_client, sample_result_data):
        """Test caching same file with different configurations."""
        file_hash = "same_file_hash"
        
        config1 = {"depth": "standard", "focus_areas": ["security"]}
        config2 = {"depth": "comprehensive", "focus_areas": ["functions"]}
        
        # Should create different cache entries
        result1 = await result_cache.set(file_hash, config1, sample_result_data)
        result2 = await result_cache.set(file_hash, config2, sample_result_data)
        
        assert result1 is True
        assert result2 is True
        
        # Should generate different cache keys due to different configs
        hash1 = result_cache._generate_config_hash(config1)
        hash2 = result_cache._generate_config_hash(config2)
        assert hash1 != hash2
    
    @pytest.mark.asyncio
    async def test_invalidation_patterns(self, result_cache, mock_redis_client):
        """Test various cache invalidation patterns."""
        # Mock multiple cache entries
        mock_redis_client._client.smembers.return_value = ["key1", "key2", "key3"]
        
        # Test file-based invalidation
        file_count = await result_cache.invalidate_by_file("test_file_hash")
        assert file_count == 3
        
        # Test tag-based invalidation
        tag_count = await result_cache.invalidate_by_tag("depth:standard")
        assert tag_count == 3
    
    @pytest.mark.asyncio
    async def test_ttl_based_on_analysis_depth(self, result_cache, mock_redis_client, sample_result_data):
        """Test TTL varies based on analysis depth."""
        file_hash = "ttl_test_hash"
        
        # Quick analysis
        quick_config = {"depth": "quick"}
        await result_cache.set(file_hash, quick_config, sample_result_data)
        quick_ttl = result_cache._get_ttl_for_config(quick_config)
        
        # Comprehensive analysis
        comp_config = {"depth": "comprehensive"}
        await result_cache.set(file_hash, comp_config, sample_result_data)
        comp_ttl = result_cache._get_ttl_for_config(comp_config)
        
        # Comprehensive should have longer TTL
        assert comp_ttl > quick_ttl