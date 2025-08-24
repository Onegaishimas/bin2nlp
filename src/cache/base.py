"""
File-based storage implementation with async operations and expiration management.

Provides the foundational file storage client with JSON serialization, expiration handling,
and comprehensive logging for all cache components.
"""

import asyncio
import json
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Union, Dict, List, AsyncGenerator
import fcntl
import hashlib

from ..core.config import Settings, get_settings
from ..core.exceptions import CacheException, CacheConnectionError, CacheTimeoutError
from ..core.logging import get_logger


class FileStorageClient:
    """
    Async file-based storage client with JSON serialization and expiration management.
    
    Features:
    - File-based key-value storage with directories
    - JSON serialization/deserialization with binary data support
    - TTL-based expiration with background cleanup
    - File locking for thread safety
    - Comprehensive error handling and logging
    - Performance metrics tracking
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize file storage client.
        
        Args:
            settings: Application settings (uses global settings if None)
        """
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)
        
        # Storage configuration
        self.base_path = Path(getattr(self.settings, 'storage_base_path', '/var/lib/app/data'))
        self.default_ttl_hours = getattr(self.settings, 'storage_cache_ttl_hours', 24)
        self.max_file_size_mb = getattr(self.settings, 'storage_max_file_size_mb', 100)
        
        # Create base directory
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Storage state
        self._connected = True  # File storage is always "connected"
        self._last_cleanup = datetime.min
        self._cleanup_interval = 3600  # 1 hour
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Performance metrics
        self._operation_count = 0
        self._error_count = 0
        self._total_response_time = 0.0
        
        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        self.logger.info(
            "File storage initialized",
            extra={
                "base_path": str(self.base_path),
                "default_ttl_hours": self.default_ttl_hours,
                "max_file_size_mb": self.max_file_size_mb
            }
        )
    
    def _get_file_path(self, key: str) -> Path:
        """
        Get file path for a given key.
        
        Args:
            key: Cache key
            
        Returns:
            Path: File path for the key
        """
        # Hash key to create safe filename and avoid long paths
        key_hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
        
        # Create subdirectories based on first two characters of hash
        subdir1 = key_hash[:2]
        subdir2 = key_hash[2:4]
        
        file_dir = self.base_path / subdir1 / subdir2
        file_dir.mkdir(parents=True, exist_ok=True)
        
        return file_dir / f"{key_hash}.json"
    
    def _get_meta_path(self, key: str) -> Path:
        """
        Get metadata file path for a given key.
        
        Args:
            key: Cache key
            
        Returns:
            Path: Metadata file path for the key
        """
        data_path = self._get_file_path(key)
        return data_path.with_suffix('.meta')
    
    async def connect(self) -> None:
        """
        Initialize file storage (no-op for file storage).
        """
        self._connected = True
        self.logger.debug("File storage connect called (no-op)")
    
    async def disconnect(self) -> None:
        """Close file storage and cleanup tasks."""
        self._connected = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("File storage disconnected")
    
    async def health_check(self) -> bool:
        """
        Check file storage health.
        
        Returns:
            bool: Always True for file storage
        """
        try:
            # Test write/read operation
            test_key = "_health_check_test"
            await self.set(test_key, {"test": True}, ttl=1)
            result = await self.get(test_key)
            await self.delete(test_key)
            
            return result is not None and result.get("test") is True
            
        except Exception as e:
            self.logger.warning(
                "File storage health check failed",
                extra={"error": str(e)}
            )
            return False
    
    async def _cleanup_loop(self) -> None:
        """Background task for cleaning up expired files."""
        while self._connected:
            try:
                await self._cleanup_expired_files()
                self._last_cleanup = datetime.utcnow()
                
                # Wait for next cleanup
                await asyncio.sleep(self._cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    "Cleanup loop error",
                    extra={"error": str(e)}
                )
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _cleanup_expired_files(self) -> None:
        """Remove expired files from storage."""
        try:
            current_time = datetime.utcnow()
            expired_count = 0
            
            # Walk through all storage directories
            for root, dirs, files in os.walk(self.base_path):
                for file in files:
                    if file.endswith('.meta'):
                        meta_path = Path(root) / file
                        data_path = meta_path.with_suffix('.json')
                        
                        try:
                            # Read metadata
                            async with self._file_lock(meta_path):
                                if meta_path.exists():
                                    with open(meta_path, 'r') as f:
                                        metadata = json.load(f)
                                    
                                    expires_at = metadata.get('expires_at')
                                    if expires_at:
                                        expiry_time = datetime.fromisoformat(expires_at)
                                        if current_time > expiry_time:
                                            # Remove expired files
                                            if data_path.exists():
                                                data_path.unlink()
                                            meta_path.unlink()
                                            expired_count += 1
                        
                        except Exception as e:
                            self.logger.warning(
                                "Error cleaning up expired file",
                                extra={"file": str(meta_path), "error": str(e)}
                            )
            
            if expired_count > 0:
                self.logger.info(
                    "Cleaned up expired files",
                    extra={"expired_count": expired_count}
                )
        
        except Exception as e:
            self.logger.error(
                "Error during cleanup",
                extra={"error": str(e)}
            )
    
    @asynccontextmanager
    async def _file_lock(self, file_path: Path) -> AsyncGenerator[None, None]:
        """
        Context manager for file locking.
        
        Args:
            file_path: Path to file to lock
        """
        lock_file = None
        try:
            # Create lock file
            lock_file = open(f"{file_path}.lock", 'w')
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                try:
                    Path(f"{file_path}.lock").unlink(missing_ok=True)
                except:
                    pass
    
    @asynccontextmanager
    async def _operation_context(self, operation_name: str) -> AsyncGenerator[None, None]:
        """
        Context manager for operations with error handling and metrics.
        
        Args:
            operation_name: Name of the operation for logging
        """
        if not self._connected:
            raise CacheConnectionError("File storage not connected")
        
        start_time = datetime.utcnow()
        
        try:
            yield
            
            # Update metrics
            self._operation_count += 1
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self._total_response_time += response_time
            
        except OSError as e:
            self._error_count += 1
            self.logger.error(
                f"File system error during {operation_name}",
                extra={"error": str(e)}
            )
            raise CacheConnectionError(f"File system error during {operation_name}: {e}")
            
        except json.JSONDecodeError as e:
            self._error_count += 1
            self.logger.error(
                f"JSON decode error during {operation_name}",
                extra={"error": str(e)}
            )
            raise CacheException(f"JSON decode error during {operation_name}: {e}")
            
        except Exception as e:
            self._error_count += 1
            self.logger.error(
                f"Unexpected error during {operation_name}",
                extra={"error": str(e)}
            )
            raise CacheException(f"Unexpected error during {operation_name}: {e}")
    
    def _serialize_value(self, value: Any) -> str:
        """
        Serialize a value for file storage.
        
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
                return json.dumps(str(value))
    
    def _deserialize_value(self, value: str) -> Any:
        """
        Deserialize a value from file storage.
        
        Args:
            value: Serialized value from file
            
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
    
    async def _is_expired(self, key: str) -> bool:
        """
        Check if a key has expired.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if expired or doesn't exist
        """
        meta_path = self._get_meta_path(key)
        
        if not meta_path.exists():
            return True
        
        try:
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
            
            expires_at = metadata.get('expires_at')
            if not expires_at:
                return False  # No expiration
            
            expiry_time = datetime.fromisoformat(expires_at)
            return datetime.utcnow() > expiry_time
            
        except Exception:
            return True  # Treat as expired on error
    
    # Basic cache operations
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from file storage.
        
        Args:
            key: Cache key
            
        Returns:
            Any: Cached value or None if not found/expired
        """
        async with self._operation_context("get"):
            data_path = self._get_file_path(key)
            
            if not data_path.exists():
                return None
            
            # Check expiration
            if await self._is_expired(key):
                # Clean up expired files
                try:
                    data_path.unlink(missing_ok=True)
                    self._get_meta_path(key).unlink(missing_ok=True)
                except:
                    pass
                return None
            
            async with self._file_lock(data_path):
                try:
                    with open(data_path, 'r') as f:
                        value = f.read()
                    return self._deserialize_value(value)
                except Exception:
                    return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """
        Set a value in file storage.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            nx: Only set if key doesn't exist
            xx: Only set if key exists
            
        Returns:
            bool: True if value was set
        """
        async with self._operation_context("set"):
            data_path = self._get_file_path(key)
            meta_path = self._get_meta_path(key)
            
            # Check nx/xx conditions
            exists = data_path.exists() and not await self._is_expired(key)
            
            if nx and exists:
                return False
            if xx and not exists:
                return False
            
            # Calculate expiration
            expires_at = None
            if ttl is not None:
                expires_at = (datetime.utcnow() + timedelta(seconds=ttl)).isoformat()
            elif not exists:  # New key gets default TTL
                expires_at = (datetime.utcnow() + timedelta(hours=self.default_ttl_hours)).isoformat()
            
            serialized_value = self._serialize_value(value)
            
            # Write data and metadata atomically
            async with self._file_lock(data_path):
                try:
                    # Write data to temporary file first
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, 
                                                   dir=data_path.parent, 
                                                   suffix='.tmp') as tmp_data:
                        tmp_data.write(serialized_value)
                        tmp_data_path = tmp_data.name
                    
                    # Write metadata to temporary file
                    metadata = {
                        'created_at': datetime.utcnow().isoformat(),
                        'expires_at': expires_at,
                        'key': key
                    }
                    
                    with tempfile.NamedTemporaryFile(mode='w', delete=False,
                                                   dir=meta_path.parent,
                                                   suffix='.tmp') as tmp_meta:
                        json.dump(metadata, tmp_meta)
                        tmp_meta_path = tmp_meta.name
                    
                    # Atomic move
                    shutil.move(tmp_data_path, data_path)
                    shutil.move(tmp_meta_path, meta_path)
                    
                    return True
                
                except Exception as e:
                    # Cleanup temporary files on error
                    try:
                        os.unlink(tmp_data_path)
                    except:
                        pass
                    try:
                        os.unlink(tmp_meta_path)
                    except:
                        pass
                    raise
    
    async def delete(self, *keys: str) -> int:
        """
        Delete keys from file storage.
        
        Args:
            *keys: Keys to delete
            
        Returns:
            int: Number of keys deleted
        """
        if not keys:
            return 0
        
        async with self._operation_context("delete"):
            deleted_count = 0
            
            for key in keys:
                data_path = self._get_file_path(key)
                meta_path = self._get_meta_path(key)
                
                async with self._file_lock(data_path):
                    try:
                        data_deleted = False
                        meta_deleted = False
                        
                        if data_path.exists():
                            data_path.unlink()
                            data_deleted = True
                        
                        if meta_path.exists():
                            meta_path.unlink()
                            meta_deleted = True
                        
                        if data_deleted or meta_deleted:
                            deleted_count += 1
                    
                    except Exception as e:
                        self.logger.warning(
                            f"Error deleting key {key}",
                            extra={"error": str(e)}
                        )
            
            return deleted_count
    
    async def exists(self, *keys: str) -> int:
        """
        Check if keys exist in file storage.
        
        Args:
            *keys: Keys to check
            
        Returns:
            int: Number of keys that exist and are not expired
        """
        if not keys:
            return 0
        
        async with self._operation_context("exists"):
            exists_count = 0
            
            for key in keys:
                data_path = self._get_file_path(key)
                
                if data_path.exists() and not await self._is_expired(key):
                    exists_count += 1
            
            return exists_count
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration time for a key.
        
        Args:
            key: Cache key
            seconds: Expiration time in seconds
            
        Returns:
            bool: True if expiration was set
        """
        async with self._operation_context("expire"):
            data_path = self._get_file_path(key)
            meta_path = self._get_meta_path(key)
            
            if not data_path.exists() or await self._is_expired(key):
                return False
            
            async with self._file_lock(data_path):
                try:
                    # Read existing metadata
                    metadata = {}
                    if meta_path.exists():
                        with open(meta_path, 'r') as f:
                            metadata = json.load(f)
                    
                    # Update expiration
                    metadata['expires_at'] = (datetime.utcnow() + timedelta(seconds=seconds)).isoformat()
                    
                    # Write updated metadata
                    with open(meta_path, 'w') as f:
                        json.dump(metadata, f)
                    
                    return True
                
                except Exception:
                    return False
    
    async def ttl(self, key: str) -> int:
        """
        Get time to live for a key.
        
        Args:
            key: Cache key
            
        Returns:
            int: TTL in seconds (-1 if no expiry, -2 if key doesn't exist)
        """
        async with self._operation_context("ttl"):
            data_path = self._get_file_path(key)
            meta_path = self._get_meta_path(key)
            
            if not data_path.exists():
                return -2
            
            if not meta_path.exists():
                return -1  # No expiration set
            
            try:
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
                
                expires_at = metadata.get('expires_at')
                if not expires_at:
                    return -1  # No expiration
                
                expiry_time = datetime.fromisoformat(expires_at)
                current_time = datetime.utcnow()
                
                if current_time > expiry_time:
                    return -2  # Already expired
                
                return int((expiry_time - current_time).total_seconds())
            
            except Exception:
                return -2
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """
        Get keys matching a pattern.
        
        Args:
            pattern: Key pattern (simplified - only * wildcard supported)
            
        Returns:
            List[str]: Matching keys
        """
        async with self._operation_context("keys"):
            matching_keys = []
            
            try:
                # Walk through all storage directories
                for root, dirs, files in os.walk(self.base_path):
                    for file in files:
                        if file.endswith('.meta'):
                            meta_path = Path(root) / file
                            
                            try:
                                with open(meta_path, 'r') as f:
                                    metadata = json.load(f)
                                
                                key = metadata.get('key')
                                if key and not await self._is_expired(key):
                                    # Simple pattern matching (only * wildcard)
                                    if pattern == "*" or pattern in key:
                                        matching_keys.append(key)
                            
                            except Exception:
                                continue
            
            except Exception as e:
                self.logger.error(
                    "Error listing keys",
                    extra={"error": str(e)}
                )
            
            return matching_keys
    
    async def flushdb(self) -> bool:
        """
        Clear all keys from storage.
        
        Returns:
            bool: True if successful
        """
        async with self._operation_context("flushdb"):
            try:
                # Remove all files in storage directory
                if self.base_path.exists():
                    shutil.rmtree(self.base_path)
                    self.base_path.mkdir(parents=True, exist_ok=True)
                
                return True
            
            except Exception as e:
                self.logger.error(
                    "Error flushing storage",
                    extra={"error": str(e)}
                )
                return False
    
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
        
        # Calculate storage usage
        total_size = 0
        file_count = 0
        try:
            for root, dirs, files in os.walk(self.base_path):
                for file in files:
                    file_path = Path(root) / file
                    total_size += file_path.stat().st_size
                    file_count += 1
        except Exception:
            pass
        
        return {
            "connected": self._connected,
            "operation_count": self._operation_count,
            "error_count": self._error_count,
            "average_response_time_seconds": avg_response_time,
            "last_cleanup": self._last_cleanup.isoformat(),
            "storage_stats": {
                "base_path": str(self.base_path),
                "total_size_bytes": total_size,
                "file_count": file_count,
                "default_ttl_hours": self.default_ttl_hours,
                "max_file_size_mb": self.max_file_size_mb
            }
        }
    
    @property
    def is_connected(self) -> bool:
        """Check if file storage is connected."""
        return self._connected


# Global file storage client instance
_file_storage_client: Optional[FileStorageClient] = None


async def get_file_storage_client() -> FileStorageClient:
    """
    Get the global file storage client instance.
    
    Returns:
        FileStorageClient: Global file storage client
    """
    global _file_storage_client
    
    if _file_storage_client is None:
        _file_storage_client = FileStorageClient()
        await _file_storage_client.connect()
    
    return _file_storage_client


async def close_file_storage_client() -> None:
    """Close the global file storage client."""
    global _file_storage_client
    
    if _file_storage_client:
        await _file_storage_client.disconnect()
        _file_storage_client = None


async def init_file_storage_client(settings: Optional[Settings] = None) -> FileStorageClient:
    """
    Initialize the global file storage client.
    
    Args:
        settings: Application settings
        
    Returns:
        FileStorageClient: Initialized file storage client
    """
    global _file_storage_client
    
    if _file_storage_client:
        await _file_storage_client.disconnect()
    
    _file_storage_client = FileStorageClient(settings)
    await _file_storage_client.connect()
    
    return _file_storage_client


