"""
Unit tests for Redis base client.

Tests Redis connection management, basic operations, health checks,
and error handling with mocked Redis.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.cache.base import RedisClient, get_redis_client, close_redis_client, init_redis_client
from src.core.config import Settings, DatabaseSettings
from src.core.exceptions import CacheConnectionError, CacheTimeoutError, CacheException


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.database = MagicMock(spec=DatabaseSettings)
    settings.database.host = "localhost"
    settings.database.port = 6379
    settings.database.db = 0
    settings.database.password = None
    settings.database.username = None
    settings.database.max_connections = 20
    settings.database.socket_connect_timeout = 5.0
    settings.database.socket_keepalive = True
    settings.database.health_check_interval = 30
    settings.database.url = "redis://localhost:6379/0"
    return settings


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.aclose = AsyncMock()
    redis_mock.get = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.exists = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.ttl = AsyncMock(return_value=3600)
    redis_mock.keys = AsyncMock(return_value=[])
    redis_mock.flushdb = AsyncMock(return_value=True)
    redis_mock.info = AsyncMock(return_value={})
    redis_mock.pipeline = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_connection_pool():
    """Create mock connection pool."""
    pool_mock = MagicMock()
    pool_mock.aclose = AsyncMock()
    pool_mock.created_connections = 5
    pool_mock.available_connections = 15
    pool_mock.in_use_connections = 5
    return pool_mock


class TestRedisClient:
    """Test cases for RedisClient class."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_settings):
        """Test RedisClient initialization."""
        client = RedisClient(mock_settings)
        
        assert client.settings == mock_settings
        assert not client.is_connected
        assert client._pool is None
        assert client._client is None
        assert client._operation_count == 0
        assert client._error_count == 0
    
    @pytest.mark.asyncio
    @patch('src.cache.base.redis')
    @patch('src.cache.base.ConnectionPool')
    async def test_connect_success(self, mock_pool_class, mock_redis_module, mock_settings, mock_redis, mock_connection_pool):
        """Test successful Redis connection."""
        mock_pool_class.return_value = mock_connection_pool
        mock_redis_module.Redis.return_value = mock_redis
        
        client = RedisClient(mock_settings)
        await client.connect()
        
        assert client.is_connected
        assert client._pool == mock_connection_pool
        assert client._client == mock_redis
        mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.cache.base.redis')
    @patch('src.cache.base.ConnectionPool')
    async def test_connect_failure(self, mock_pool_class, mock_redis_module, mock_settings, mock_redis, mock_connection_pool):
        """Test Redis connection failure."""
        mock_pool_class.return_value = mock_connection_pool
        mock_redis_module.Redis.return_value = mock_redis
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        client = RedisClient(mock_settings)
        
        with pytest.raises(CacheConnectionError, match="Redis connection failed"):
            await client.connect()
        
        assert not client.is_connected
        assert client._connection_errors == 1
    
    @pytest.mark.asyncio
    async def test_disconnect(self, mock_settings, mock_redis, mock_connection_pool):
        """Test Redis disconnection."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        client._pool = mock_connection_pool
        client._health_check_task = AsyncMock()
        client._health_check_task.cancel = MagicMock()
        
        await client.disconnect()
        
        assert not client.is_connected
        mock_redis.aclose.assert_called_once()
        mock_connection_pool.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_settings, mock_redis):
        """Test successful health check."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        result = await client.health_check()
        
        assert result is True
        mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_settings, mock_redis):
        """Test health check failure."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        mock_redis.ping.side_effect = Exception("Health check failed")
        
        result = await client.health_check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_not_connected(self, mock_settings):
        """Test health check when not connected."""
        client = RedisClient(mock_settings)
        
        result = await client.health_check()
        
        assert result is False
    
    def test_serialize_value_string(self, mock_settings):
        """Test serialization of string values."""
        client = RedisClient(mock_settings)
        
        result = client._serialize_value("test_string")
        assert result == '"test_string"'
    
    def test_serialize_value_dict(self, mock_settings):
        """Test serialization of dictionary values."""
        client = RedisClient(mock_settings)
        
        test_dict = {"key": "value", "number": 42}
        result = client._serialize_value(test_dict)
        
        # Parse back to verify
        parsed = json.loads(result)
        assert parsed == test_dict
    
    def test_serialize_value_list(self, mock_settings):
        """Test serialization of list values."""
        client = RedisClient(mock_settings)
        
        test_list = ["item1", "item2", 42]
        result = client._serialize_value(test_list)
        
        # Parse back to verify
        parsed = json.loads(result)
        assert parsed == test_list
    
    def test_serialize_value_bytes(self, mock_settings):
        """Test serialization of bytes values."""
        client = RedisClient(mock_settings)
        
        test_bytes = b"binary_data"
        result = client._serialize_value(test_bytes)
        
        # Should contain base64 encoded data
        parsed = json.loads(result)
        assert "__bytes__" in parsed
    
    def test_deserialize_value_string(self, mock_settings):
        """Test deserialization of string values."""
        client = RedisClient(mock_settings)
        
        serialized = '"test_string"'
        result = client._deserialize_value(serialized)
        
        assert result == "test_string"
    
    def test_deserialize_value_dict(self, mock_settings):
        """Test deserialization of dictionary values."""
        client = RedisClient(mock_settings)
        
        test_dict = {"key": "value", "number": 42}
        serialized = json.dumps(test_dict)
        result = client._deserialize_value(serialized)
        
        assert result == test_dict
    
    def test_deserialize_value_invalid_json(self, mock_settings):
        """Test deserialization of invalid JSON returns string."""
        client = RedisClient(mock_settings)
        
        invalid_json = "not_valid_json"
        result = client._deserialize_value(invalid_json)
        
        assert result == invalid_json
    
    @pytest.mark.asyncio
    async def test_get_success(self, mock_settings, mock_redis):
        """Test successful get operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.get.return_value = '"test_value"'
        
        result = await client.get("test_key")
        
        assert result == "test_value"
        mock_redis.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_settings, mock_redis):
        """Test get operation when key not found."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.get.return_value = None
        
        result = await client.get("nonexistent_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_not_connected(self, mock_settings):
        """Test get operation when not connected."""
        client = RedisClient(mock_settings)
        
        with pytest.raises(CacheConnectionError, match="Redis not connected"):
            await client.get("test_key")
    
    @pytest.mark.asyncio
    async def test_set_success(self, mock_settings, mock_redis):
        """Test successful set operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.set.return_value = True
        
        result = await client.set("test_key", "test_value", ttl=3600)
        
        assert result is True
        mock_redis.set.assert_called_once_with(
            "test_key", 
            '"test_value"',
            ex=3600,
            nx=False,
            xx=False
        )
    
    @pytest.mark.asyncio
    async def test_set_with_nx(self, mock_settings, mock_redis):
        """Test set operation with NX flag."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.set.return_value = True
        
        result = await client.set("test_key", "test_value", nx=True)
        
        assert result is True
        mock_redis.set.assert_called_once_with(
            "test_key",
            '"test_value"',
            ex=None,
            nx=True,
            xx=False
        )
    
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_settings, mock_redis):
        """Test successful delete operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.delete.return_value = 2
        
        result = await client.delete("key1", "key2")
        
        assert result == 2
        mock_redis.delete.assert_called_once_with("key1", "key2")
    
    @pytest.mark.asyncio
    async def test_delete_no_keys(self, mock_settings, mock_redis):
        """Test delete operation with no keys."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        result = await client.delete()
        
        assert result == 0
        mock_redis.delete.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_exists_success(self, mock_settings, mock_redis):
        """Test successful exists operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.exists.return_value = 1
        
        result = await client.exists("test_key")
        
        assert result == 1
        mock_redis.exists.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_expire_success(self, mock_settings, mock_redis):
        """Test successful expire operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.expire.return_value = True
        
        result = await client.expire("test_key", 3600)
        
        assert result is True
        mock_redis.expire.assert_called_once_with("test_key", 3600)
    
    @pytest.mark.asyncio
    async def test_ttl_success(self, mock_settings, mock_redis):
        """Test successful TTL operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.ttl.return_value = 1800
        
        result = await client.ttl("test_key")
        
        assert result == 1800
        mock_redis.ttl.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_keys_success(self, mock_settings, mock_redis):
        """Test successful keys operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        
        result = await client.keys("test_*")
        
        assert result == ["key1", "key2", "key3"]
        mock_redis.keys.assert_called_once_with("test_*")
    
    @pytest.mark.asyncio
    async def test_flushdb_success(self, mock_settings, mock_redis):
        """Test successful flushdb operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.flushdb.return_value = True
        
        result = await client.flushdb()
        
        assert result is True
        mock_redis.flushdb.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_info_success(self, mock_settings, mock_redis):
        """Test successful info operation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        info_data = {"redis_version": "6.2.0", "used_memory": 1024}
        mock_redis.info.return_value = info_data
        
        result = await client.info("server")
        
        assert result == info_data
        mock_redis.info.assert_called_once_with("server")
    
    @pytest.mark.asyncio
    async def test_pipeline_success(self, mock_settings, mock_redis):
        """Test pipeline creation."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_pipeline = AsyncMock()
        mock_redis.pipeline.return_value = mock_pipeline
        
        result = await client.pipeline()
        
        assert result == mock_pipeline
        mock_redis.pipeline.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pipeline_not_connected(self, mock_settings):
        """Test pipeline when not connected."""
        client = RedisClient(mock_settings)
        
        with pytest.raises(CacheConnectionError, match="Redis not connected"):
            await client.pipeline()
    
    def test_get_stats(self, mock_settings, mock_connection_pool):
        """Test getting client statistics."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._operation_count = 100
        client._error_count = 5
        client._total_response_time = 1.5
        client._pool = mock_connection_pool
        
        stats = client.get_stats()
        
        assert stats["connected"] is True
        assert stats["operation_count"] == 100
        assert stats["error_count"] == 5
        assert stats["average_response_time_seconds"] == 0.015
        assert stats["pool_stats"]["max_connections"] == 20
    
    def test_get_stats_no_operations(self, mock_settings):
        """Test getting stats with no operations."""
        client = RedisClient(mock_settings)
        
        stats = client.get_stats()
        
        assert stats["connected"] is False
        assert stats["operation_count"] == 0
        assert stats["error_count"] == 0
        assert stats["average_response_time_seconds"] == 0
    
    def test_redis_url_property(self, mock_settings):
        """Test Redis URL property."""
        client = RedisClient(mock_settings)
        
        assert client.redis_url == "redis://localhost:6379/0"
    
    @pytest.mark.asyncio
    async def test_operation_context_connection_error(self, mock_settings, mock_redis):
        """Test operation context with connection error."""
        from redis.exceptions import ConnectionError
        
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.get.side_effect = ConnectionError("Connection lost")
        
        with pytest.raises(CacheConnectionError, match="Connection error during get"):
            await client.get("test_key")
    
    @pytest.mark.asyncio
    async def test_operation_context_timeout_error(self, mock_settings, mock_redis):
        """Test operation context with timeout error."""
        from redis.exceptions import TimeoutError
        
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.get.side_effect = TimeoutError("Operation timed out")
        
        with pytest.raises(CacheTimeoutError, match="Timeout during get"):
            await client.get("test_key")
    
    @pytest.mark.asyncio
    async def test_operation_context_redis_error(self, mock_settings, mock_redis):
        """Test operation context with Redis error."""
        from redis.exceptions import ResponseError
        
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.get.side_effect = ResponseError("Redis error")
        
        with pytest.raises(CacheException, match="Redis error during get"):
            await client.get("test_key")
    
    @pytest.mark.asyncio
    async def test_operation_context_generic_error(self, mock_settings, mock_redis):
        """Test operation context with generic error."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        mock_redis.get.side_effect = ValueError("Generic error")
        
        with pytest.raises(CacheException, match="Unexpected error during get"):
            await client.get("test_key")


class TestGlobalRedisClient:
    """Test cases for global Redis client functions."""
    
    @pytest.mark.asyncio
    @patch('src.cache.base._redis_client', None)
    @patch('src.cache.base.RedisClient')
    async def test_get_redis_client_first_time(self, mock_redis_client_class):
        """Test getting Redis client for the first time."""
        mock_client = AsyncMock()
        mock_redis_client_class.return_value = mock_client
        
        result = await get_redis_client()
        
        assert result == mock_client
        mock_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_redis_client(self):
        """Test closing global Redis client."""
        # Set up a mock client
        mock_client = AsyncMock()
        
        with patch('src.cache.base._redis_client', mock_client):
            await close_redis_client()
        
        mock_client.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.cache.base._redis_client', None)
    @patch('src.cache.base.RedisClient')
    async def test_init_redis_client(self, mock_redis_client_class, mock_settings):
        """Test initializing global Redis client."""
        mock_client = AsyncMock()
        mock_redis_client_class.return_value = mock_client
        
        result = await init_redis_client(mock_settings)
        
        assert result == mock_client
        mock_redis_client_class.assert_called_once_with(mock_settings)
        mock_client.connect.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.cache.base.RedisClient')
    async def test_init_redis_client_closes_existing(self, mock_redis_client_class):
        """Test that initializing closes existing client first."""
        # Set up existing client
        existing_client = AsyncMock()
        
        # Set up new client
        new_client = AsyncMock()
        mock_redis_client_class.return_value = new_client
        
        with patch('src.cache.base._redis_client', existing_client):
            result = await init_redis_client()
        
        existing_client.disconnect.assert_called_once()
        assert result == new_client


@pytest.mark.asyncio
class TestRedisClientIntegration:
    """Integration-style tests for RedisClient operations."""
    
    async def test_set_get_delete_cycle(self, mock_settings, mock_redis):
        """Test complete set-get-delete cycle."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        # Set up mock returns
        mock_redis.set.return_value = True
        mock_redis.get.return_value = '"test_value"'
        mock_redis.delete.return_value = 1
        
        # Test set
        set_result = await client.set("test_key", "test_value")
        assert set_result is True
        
        # Test get
        get_result = await client.get("test_key")
        assert get_result == "test_value"
        
        # Test delete
        delete_result = await client.delete("test_key")
        assert delete_result == 1
    
    async def test_complex_data_serialization(self, mock_settings, mock_redis):
        """Test serialization of complex data structures."""
        client = RedisClient(mock_settings)
        client._connected = True
        client._client = mock_redis
        
        complex_data = {
            "string": "value",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"inner": "data"}
        }
        
        # Mock the set operation to capture serialized data
        def mock_set(key, value, **kwargs):
            # Verify we can deserialize what we serialize
            deserialized = client._deserialize_value(value)
            assert deserialized == complex_data
            return True
        
        mock_redis.set.side_effect = mock_set
        
        result = await client.set("complex_key", complex_data)
        assert result is True