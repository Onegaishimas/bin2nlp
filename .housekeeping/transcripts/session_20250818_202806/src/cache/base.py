"""
Redis client base implementation with connection management and basic operations.

Provides the foundational Redis client with connection pooling, health checks,
retry logic, and basic cache operations for all cache components.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional, Union, Dict, List, AsyncGenerator
from datetime import datetime, timedelta

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import (
    ConnectionError, 
    TimeoutError, 
    RedisError, 
    BusyLoadingError,
    ResponseError
)

from ..core.config import Settings, get_settings
from ..core.exceptions import CacheException, CacheConnectionError, CacheTimeoutError
from ..core.logging import get_logger


class RedisClient:
    """
    Async Redis client with connection pooling, health checks, and error handling.
    
    Features:
    - Connection pooling with automatic retry
    - Health monitoring and reconnection
    - JSON serialization/deserialization
    - Comprehensive error handling
    - Performance metrics
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize Redis client.
        
        Args:
            settings: Application settings (uses global settings if None)
        """
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)
        
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._health_check_task: Optional[asyncio.Task] = None
        
        # Connection state
        self._connected = False
        self._last_health_check = datetime.min
        self._connection_errors = 0
        self._max_connection_errors = 5
        
        # Performance metrics
        self._operation_count = 0
        self._error_count = 0
        self._total_response_time = 0.0
    
    async def connect(self) -> None:
        """
        Establish Redis connection with retry logic.
        
        Raises:
            CacheConnectionError: If connection fails after retries
        """
        if self._connected:
            return
        
        try:
            # Create connection pool with retry configuration
            retry = Retry(
                ExponentialBackoff(cap=10, base=1), 
                retries=3
            )
            
            self._pool = ConnectionPool(
                host=self.settings.database.host,
                port=self.settings.database.port,
                db=self.settings.database.db,
                password=self.settings.database.password,
                username=self.settings.database.username,
                max_connections=self.settings.database.max_connections,
                socket_connect_timeout=self.settings.database.socket_connect_timeout,
                socket_keepalive=self.settings.database.socket_keepalive,
                retry=retry,
                health_check_interval=self.settings.database.health_check_interval
            )
            
            # Create Redis client
            self._client = redis.Redis(
                connection_pool=self._pool,
                decode_responses=True
            )
            
            # Test connection
            await self._client.ping()
            
            self._connected = True
            self._connection_errors = 0
            
            # Start health check task
            self._health_check_task = asyncio.create_task(
                self._health_check_loop()
            )
            
            self.logger.info(
                "Redis connection established",
                extra={
                    "host": self.settings.database.host,
                    "port": self.settings.database.port,
                    "db": self.settings.database.db
                }
            )
            
        except Exception as e:
            self._connected = False
            self._connection_errors += 1
            
            self.logger.error(
                "Failed to connect to Redis",
                extra={
                    "error": str(e),
                    "connection_errors": self._connection_errors,
                    "host": self.settings.database.host,
                    "port": self.settings.database.port
                }
            )
            
            raise CacheConnectionError(f"Redis connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Gracefully close Redis connections."""
        self._connected = False
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Close client and pool
        if self._client:
            await self._client.aclose()
            self._client = None
        
        if self._pool:
            await self._pool.aclose()
            self._pool = None
        
        self.logger.info("Redis connection closed")
    
    async def health_check(self) -> bool:
        """
        Check Redis connection health.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        if not self._connected or not self._client:
            return False
        
        try:
            start_time = datetime.utcnow()
            await self._client.ping()
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            self._last_health_check = datetime.utcnow()
            
            # Log slow responses
            if response_time > 1.0:
                self.logger.warning(
                    "Slow Redis response",
                    extra={"response_time_seconds": response_time}
                )
            
            return True
            
        except Exception as e:
            self.logger.warning(
                "Redis health check failed",
                extra={"error": str(e)}
            )
            return False
    
    async def _health_check_loop(self) -> None:
        """Background task for periodic health checks."""
        while self._connected:
            try:
                healthy = await self.health_check()
                
                if not healthy:
                    self._connection_errors += 1
                    if self._connection_errors >= self._max_connection_errors:
                        self.logger.error(
                            "Too many connection errors, marking as disconnected",
                            extra={"connection_errors": self._connection_errors}
                        )
                        self._connected = False
                        break
                else:
                    self._connection_errors = 0
                
                # Wait for next health check
                await asyncio.sleep(self.settings.database.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    "Health check loop error",
                    extra={"error": str(e)}
                )
                await asyncio.sleep(5)
    
    @asynccontextmanager
    async def _operation_context(self, operation_name: str) -> AsyncGenerator[redis.Redis, None]:
        """
        Context manager for Redis operations with error handling and metrics.
        
        Args:
            operation_name: Name of the operation for logging
            
        Yields:
            Redis client instance
            
        Raises:
            CacheException: On operation failures
        """
        if not self._connected or not self._client:
            raise CacheConnectionError("Redis not connected")
        
        start_time = datetime.utcnow()
        
        try:
            yield self._client
            
            # Update metrics
            self._operation_count += 1
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._total_response_time += response_time
            
        except ConnectionError as e:
            self._error_count += 1
            self.logger.error(
                f"Redis connection error during {operation_name}",
                extra={"error": str(e)}
            )
            raise CacheConnectionError(f"Connection error during {operation_name}: {e}")
            
        except TimeoutError as e:
            self._error_count += 1
            self.logger.error(
                f"Redis timeout during {operation_name}",
                extra={"error": str(e)}
            )
            raise CacheTimeoutError(f"Timeout during {operation_name}: {e}")
            
        except BusyLoadingError as e:
            self._error_count += 1
            self.logger.warning(
                f"Redis busy loading during {operation_name}",
                extra={"error": str(e)}
            )
            raise CacheException(f"Redis busy during {operation_name}: {e}")
            
        except ResponseError as e:
            self._error_count += 1
            self.logger.error(
                f"Redis response error during {operation_name}",
                extra={"error": str(e)}
            )
            raise CacheException(f"Redis error during {operation_name}: {e}")
            
        except Exception as e:
            self._error_count += 1
            self.logger.error(
                f"Unexpected error during {operation_name}",
                extra={"error": str(e)}
            )
            raise CacheException(f"Unexpected error during {operation_name}: {e}")
    
    def _serialize_value(self, value: Any) -> str:
        """
        Serialize a value for Redis storage.
        
        Args:
            value: Value to serialize
            
        Returns:
            str: Serialized value
        """
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value)
        elif isinstance(value, (dict, list, tuple)):
            return json.dumps(value)
        elif isinstance(value, bytes):
            # For binary data, encode as base64
            import base64
            return json.dumps({"__bytes__": base64.b64encode(value).decode('utf-8')})
        else:
            # For other types, try JSON serialization
            try:
                return json.dumps(value, default=str)
            except (TypeError, ValueError):
                return str(value)
    
    def _deserialize_value(self, value: str) -> Any:
        """
        Deserialize a value from Redis storage.
        
        Args:
            value: Serialized value from Redis
            
        Returns:
            Any: Deserialized value
        """
        try:
            data = json.loads(value)
            
            # Handle special case for binary data
            if isinstance(data, dict) and "__bytes__" in data:
                import base64
                return base64.b64decode(data["__bytes__"])
            
            return data
            
        except (json.JSONDecodeError, ValueError):
            # Return as string if not valid JSON
            return value
    
    # Basic cache operations
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from Redis cache.
        
        Args:
            key: Cache key
            
        Returns:
            Any: Cached value or None if not found
        """
        async with self._operation_context("get") as client:
            value = await client.get(key)
            if value is None:
                return None
            return self._deserialize_value(value)
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        Set a value in Redis cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            nx: Only set if key doesn't exist
            xx: Only set if key exists
            
        Returns:
            bool: True if value was set
        """
        async with self._operation_context("set") as client:
            serialized_value = self._serialize_value(value)
            
            result = await client.set(
                key, 
                serialized_value,
                ex=ttl,
                nx=nx,
                xx=xx
            )
            
            return bool(result)
    
    async def delete(self, *keys: str) -> int:
        """
        Delete keys from Redis cache.
        
        Args:
            *keys: Keys to delete
            
        Returns:
            int: Number of keys deleted
        """
        if not keys:
            return 0
        
        async with self._operation_context("delete") as client:
            return await client.delete(*keys)
    
    async def exists(self, *keys: str) -> int:
        """
        Check if keys exist in Redis cache.
        
        Args:
            *keys: Keys to check
            
        Returns:
            int: Number of keys that exist
        """
        if not keys:
            return 0
        
        async with self._operation_context("exists") as client:
            return await client.exists(*keys)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration time for a key.
        
        Args:
            key: Cache key
            seconds: Expiration time in seconds
            
        Returns:
            bool: True if expiration was set
        """
        async with self._operation_context("expire") as client:
            return await client.expire(key, seconds)
    
    async def ttl(self, key: str) -> int:
        """
        Get time to live for a key.
        
        Args:
            key: Cache key
            
        Returns:
            int: TTL in seconds (-1 if no expiry, -2 if key doesn't exist)
        """
        async with self._operation_context("ttl") as client:
            return await client.ttl(key)
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """
        Get keys matching a pattern.
        
        Args:
            pattern: Key pattern (use with caution in production)
            
        Returns:
            List[str]: Matching keys
        """
        async with self._operation_context("keys") as client:
            return await client.keys(pattern)
    
    async def flushdb(self) -> bool:
        """
        Clear all keys from current database.
        
        Returns:
            bool: True if successful
        """
        async with self._operation_context("flushdb") as client:
            result = await client.flushdb()
            return result is True
    
    async def info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """
        Get Redis server information.
        
        Args:
            section: Specific info section
            
        Returns:
            Dict[str, Any]: Server information
        """
        async with self._operation_context("info") as client:
            return await client.info(section)
    
    # Advanced operations
    
    async def pipeline(self):
        """
        Create a Redis pipeline for batch operations.
        
        Returns:
            Redis pipeline object
        """
        if not self._connected or not self._client:
            raise CacheConnectionError("Redis not connected")
        
        return self._client.pipeline()
    
    async def transaction(self, func, *watches, **kwargs):
        """
        Execute a transaction with WATCH/MULTI/EXEC.
        
        Args:
            func: Function to execute in transaction
            *watches: Keys to watch
            **kwargs: Additional arguments
            
        Returns:
            Transaction result
        """
        async with self._operation_context("transaction") as client:
            return await client.transaction(func, *watches, **kwargs)
    
    # Metrics and status
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get client performance statistics.
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        avg_response_time = (
            self._total_response_time / self._operation_count 
            if self._operation_count > 0 else 0
        )
        
        return {
            "connected": self._connected,
            "operation_count": self._operation_count,
            "error_count": self._error_count,
            "connection_errors": self._connection_errors,
            "average_response_time_seconds": avg_response_time,
            "last_health_check": self._last_health_check.isoformat(),
            "pool_stats": {
                "max_connections": self.settings.database.max_connections,
                "created_connections": getattr(self._pool, 'created_connections', 0) if self._pool else 0,
                "available_connections": getattr(self._pool, 'available_connections', 0) if self._pool else 0,
                "in_use_connections": getattr(self._pool, 'in_use_connections', 0) if self._pool else 0,
            }
        }
    
    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected
    
    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        return self.settings.database.url


# Global Redis client instance (will be initialized by the application)
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """
    Get the global Redis client instance.
    
    Returns:
        RedisClient: Global Redis client
        
    Raises:
        CacheConnectionError: If Redis client not initialized
    """
    global _redis_client
    
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    
    return _redis_client


async def close_redis_client() -> None:
    """Close the global Redis client."""
    global _redis_client
    
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None


async def init_redis_client(settings: Optional[Settings] = None) -> RedisClient:
    """
    Initialize the global Redis client.
    
    Args:
        settings: Application settings
        
    Returns:
        RedisClient: Initialized Redis client
    """
    global _redis_client
    
    if _redis_client:
        await _redis_client.disconnect()
    
    _redis_client = RedisClient(settings)
    await _redis_client.connect()
    
    return _redis_client