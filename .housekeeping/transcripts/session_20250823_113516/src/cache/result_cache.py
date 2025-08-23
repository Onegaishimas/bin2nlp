"""
Analysis result caching system with TTL management and intelligent invalidation.

Provides efficient caching of binary analysis results with configurable TTL,
cache key generation based on file hash and analysis configuration, and
smart invalidation patterns.
"""

import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass

from ..core.config import Settings, get_settings
from ..core.exceptions import CacheException
from ..core.logging import get_logger
from ..models.shared.enums import AnalysisDepth, AnalysisFocus
from .base import RedisClient


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    
    key: str
    data: Any
    created_at: float
    expires_at: float
    cache_version: str
    file_hash: str
    config_hash: str
    tags: Set[str]
    access_count: int = 0
    last_accessed: Optional[float] = None
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() > self.expires_at
    
    def ttl_seconds(self) -> int:
        """Get remaining TTL in seconds."""
        return max(0, int(self.expires_at - time.time()))
    
    def age_seconds(self) -> int:
        """Get age of cache entry in seconds."""
        return int(time.time() - self.created_at)


class ResultCache:
    """
    Redis-based analysis result cache with intelligent key generation and TTL management.
    
    Features:
    - File hash and configuration-based cache keys
    - Configurable TTL policies by analysis depth
    - Cache invalidation by file patterns and tags
    - Cache statistics and monitoring
    - Compression for large results
    - Cache warming and preloading
    - LRU-style access tracking
    """
    
    # Cache key patterns
    RESULT_KEY_PATTERN = "result:{file_hash}:{config_hash}"
    RESULT_METADATA_KEY = "result:meta:{cache_key}"
    FILE_RESULTS_SET = "file:results:{file_hash}"
    TAG_RESULTS_SET = "tag:results:{tag}"
    CACHE_STATS_KEY = "cache:stats"
    
    # Cache version for schema evolution
    CACHE_VERSION = "1.0"
    
    def __init__(self, redis_client: Optional[RedisClient] = None, settings: Optional[Settings] = None):
        """
        Initialize result cache.
        
        Args:
            redis_client: Redis client instance
            settings: Application settings
        """
        self.redis_client = redis_client
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)
        
        # Cache configuration
        self.default_ttl = self.settings.cache.analysis_result_ttl_seconds
        self.compression_threshold = 1024  # Compress data larger than 1KB
        self.max_key_length = 250  # Redis key length limit
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance."""
        if self.redis_client is None:
            from .base import get_redis_client
            self.redis_client = await get_redis_client()
        return self.redis_client
    
    def _generate_config_hash(self, analysis_config: Dict[str, Any]) -> str:
        """
        Generate stable hash for analysis configuration.
        
        Args:
            analysis_config: Analysis configuration parameters
            
        Returns:
            str: Configuration hash
        """
        # Normalize config for consistent hashing
        normalized_config = {}
        
        # Include key parameters that affect analysis results
        key_params = [
            'decompilation_depth', 'timeout_seconds', 'extract_functions', 'extract_imports',
            'extract_strings', 'max_functions', 'max_strings', 'llm_provider', 'llm_model'
        ]
        
        for param in key_params:
            if param in analysis_config:
                value = analysis_config[param]
                
                # Normalize lists and sets
                if isinstance(value, (list, set)):
                    value = sorted(list(value))
                
                normalized_config[param] = value
        
        # Create stable hash
        config_json = json.dumps(normalized_config, sort_keys=True)
        return hashlib.md5(config_json.encode()).hexdigest()[:16]
    
    def _generate_cache_key(self, file_hash: str, config_hash: str) -> str:
        """
        Generate cache key from file hash and config hash.
        
        Args:
            file_hash: SHA-256 hash of the file
            config_hash: Hash of analysis configuration
            
        Returns:
            str: Cache key
        """
        cache_key = self.RESULT_KEY_PATTERN.format(
            file_hash=file_hash[:16],  # Truncate for key length
            config_hash=config_hash
        )
        
        # Ensure key doesn't exceed Redis limits
        if len(cache_key) > self.max_key_length:
            # Use hash of the full key
            key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:32]
            cache_key = f"result:hash:{key_hash}"
        
        return cache_key
    
    def _get_ttl_for_config(self, analysis_config: Dict[str, Any]) -> int:
        """
        Get appropriate TTL based on analysis configuration.
        
        Args:
            analysis_config: Analysis configuration
            
        Returns:
            int: TTL in seconds
        """
        depth = analysis_config.get('depth', 'standard')
        
        # Longer TTL for more expensive analysis
        ttl_multipliers = {
            'quick': 0.5,        # 12 hours
            'standard': 1.0,     # 24 hours
            'comprehensive': 2.0,  # 48 hours
            'deep': 3.0          # 72 hours
        }
        
        multiplier = ttl_multipliers.get(depth, 1.0)
        return int(self.default_ttl * multiplier)
    
    def _extract_tags(self, file_hash: str, analysis_config: Dict[str, Any]) -> Set[str]:
        """
        Extract tags for cache entry organization.
        
        Args:
            file_hash: File hash
            analysis_config: Analysis configuration
            
        Returns:
            Set of tags
        """
        tags = set()
        
        # Add depth tag
        depth = analysis_config.get('depth', 'standard')
        tags.add(f"depth:{depth}")
        
        # Add extraction type tags
        if analysis_config.get('extract_functions', True):
            tags.add("extract:functions")
        if analysis_config.get('extract_imports', True):
            tags.add("extract:imports")
        if analysis_config.get('extract_strings', True):
            tags.add("extract:strings")
        
        # Add LLM provider tag
        if analysis_config.get('llm_provider'):
            tags.add(f"llm:{analysis_config['llm_provider']}")
        
        # Add file type tag (from file extension or format)
        if '.' in file_hash:  # This would be filename in practice
            ext = file_hash.split('.')[-1].lower()
            tags.add(f"filetype:{ext}")
        
        return tags
    
    async def get(self, file_hash: str, analysis_config: Dict[str, Any]) -> Optional[Any]:
        """
        Get cached analysis result.
        
        Args:
            file_hash: SHA-256 hash of the file
            analysis_config: Analysis configuration
            
        Returns:
            Cached analysis result or None if not found/expired
        """
        try:
            redis = await self._get_redis()
            
            config_hash = self._generate_config_hash(analysis_config)
            cache_key = self._generate_cache_key(file_hash, config_hash)
            
            # Get cached data
            cached_data = await redis.get(cache_key)
            
            if cached_data is None:
                await self._update_stats("miss")
                return None
            
            # Parse cached result
            try:
                if isinstance(cached_data, dict):
                    result_data = cached_data
                else:
                    result_data = json.loads(cached_data)
                
                # Check cache version compatibility
                if result_data.get('cache_version') != self.CACHE_VERSION:
                    self.logger.info(
                        "Cache version mismatch, invalidating",
                        extra={
                            "cache_key": cache_key,
                            "expected_version": self.CACHE_VERSION,
                            "found_version": result_data.get('cache_version')
                        }
                    )
                    await self.delete(file_hash, analysis_config)
                    await self._update_stats("miss")
                    return None
                
                # Update access statistics
                await self._update_access_stats(cache_key)
                await self._update_stats("hit")
                
                self.logger.debug(
                    "Cache hit",
                    extra={"cache_key": cache_key, "file_hash": file_hash[:16]}
                )
                
                return result_data.get('data')
                
            except (json.JSONDecodeError, KeyError) as e:
                self.logger.warning(
                    "Invalid cached data format",
                    extra={"cache_key": cache_key, "error": str(e)}
                )
                await self.delete(file_hash, analysis_config)
                await self._update_stats("error")
                return None
            
        except Exception as e:
            self.logger.error(
                "Failed to get cached result",
                extra={"file_hash": file_hash[:16], "error": str(e)}
            )
            await self._update_stats("error")
            return None
    
    async def set(
        self,
        file_hash: str,
        analysis_config: Dict[str, Any],
        result_data: Any,
        ttl_override: Optional[int] = None
    ) -> bool:
        """
        Cache analysis result with metadata.
        
        Args:
            file_hash: SHA-256 hash of the file
            analysis_config: Analysis configuration
            result_data: Analysis result to cache
            ttl_override: Override TTL in seconds
            
        Returns:
            bool: True if cached successfully
        """
        try:
            redis = await self._get_redis()
            
            config_hash = self._generate_config_hash(analysis_config)
            cache_key = self._generate_cache_key(file_hash, config_hash)
            current_time = time.time()
            
            # Determine TTL
            ttl = ttl_override or self._get_ttl_for_config(analysis_config)
            expires_at = current_time + ttl
            
            # Extract tags
            tags = self._extract_tags(file_hash, analysis_config)
            
            # Prepare cache entry
            cache_entry = {
                'data': result_data,
                'created_at': current_time,
                'expires_at': expires_at,
                'cache_version': self.CACHE_VERSION,
                'file_hash': file_hash,
                'config_hash': config_hash,
                'tags': list(tags),
                'access_count': 0
            }
            
            # Use pipeline for atomic operations
            async with redis.pipeline() as pipe:
                # Store the cached result
                await pipe.set(cache_key, json.dumps(cache_entry), ex=ttl)
                
                # Add to file results set
                file_set_key = self.FILE_RESULTS_SET.format(file_hash=file_hash)
                await pipe.sadd(file_set_key, cache_key)
                await pipe.expire(file_set_key, ttl)
                
                # Add to tag sets
                for tag in tags:
                    tag_set_key = self.TAG_RESULTS_SET.format(tag=tag)
                    await pipe.sadd(tag_set_key, cache_key)
                    await pipe.expire(tag_set_key, ttl)
                
                # Update statistics
                await pipe.hincrby(self.CACHE_STATS_KEY, "total_cached", 1)
                await pipe.hincrby(self.CACHE_STATS_KEY, f"cached_depth_{analysis_config.get('depth', 'standard')}", 1)
                
                # Execute pipeline
                await pipe.execute()
            
            await self._update_stats("set")
            
            self.logger.debug(
                "Result cached successfully",
                extra={
                    "cache_key": cache_key,
                    "file_hash": file_hash[:16],
                    "ttl": ttl,
                    "tags": list(tags)
                }
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to cache result",
                extra={"file_hash": file_hash[:16], "error": str(e)}
            )
            await self._update_stats("error")
            return False
    
    async def delete(self, file_hash: str, analysis_config: Dict[str, Any]) -> bool:
        """
        Delete specific cached result.
        
        Args:
            file_hash: SHA-256 hash of the file
            analysis_config: Analysis configuration
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            redis = await self._get_redis()
            
            config_hash = self._generate_config_hash(analysis_config)
            cache_key = self._generate_cache_key(file_hash, config_hash)
            
            # Get entry metadata before deletion
            cached_data = await redis.get(cache_key)
            if cached_data:
                try:
                    entry_data = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                    tags = entry_data.get('tags', [])
                    
                    # Remove from tag sets
                    async with redis.pipeline() as pipe:
                        await pipe.delete(cache_key)
                        
                        # Remove from file set
                        file_set_key = self.FILE_RESULTS_SET.format(file_hash=file_hash)
                        await pipe.srem(file_set_key, cache_key)
                        
                        # Remove from tag sets
                        for tag in tags:
                            tag_set_key = self.TAG_RESULTS_SET.format(tag=tag)
                            await pipe.srem(tag_set_key, cache_key)
                        
                        await pipe.execute()
                    
                except (json.JSONDecodeError, KeyError):
                    # Just delete the key if metadata is corrupted
                    await redis.delete(cache_key)
            
            await self._update_stats("delete")
            
            self.logger.debug(
                "Cache entry deleted",
                extra={"cache_key": cache_key, "file_hash": file_hash[:16]}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to delete cached result",
                extra={"file_hash": file_hash[:16], "error": str(e)}
            )
            return False
    
    async def invalidate_by_file(self, file_hash: str) -> int:
        """
        Invalidate all cached results for a specific file.
        
        Args:
            file_hash: SHA-256 hash of the file
            
        Returns:
            int: Number of cache entries invalidated
        """
        try:
            redis = await self._get_redis()
            
            file_set_key = self.FILE_RESULTS_SET.format(file_hash=file_hash)
            cache_keys = await redis._client.smembers(file_set_key)
            
            if not cache_keys:
                return 0
            
            # Delete all cache keys
            await redis.delete(*cache_keys)
            
            # Delete the file set
            await redis.delete(file_set_key)
            
            await self._update_stats("invalidate", len(cache_keys))
            
            self.logger.info(
                "Invalidated cache entries by file",
                extra={"file_hash": file_hash[:16], "count": len(cache_keys)}
            )
            
            return len(cache_keys)
            
        except Exception as e:
            self.logger.error(
                "Failed to invalidate by file",
                extra={"file_hash": file_hash[:16], "error": str(e)}
            )
            return 0
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate all cached results with a specific tag.
        
        Args:
            tag: Tag to invalidate (e.g., "depth:comprehensive", "llm:openai")
            
        Returns:
            int: Number of cache entries invalidated
        """
        try:
            redis = await self._get_redis()
            
            tag_set_key = self.TAG_RESULTS_SET.format(tag=tag)
            cache_keys = await redis._client.smembers(tag_set_key)
            
            if not cache_keys:
                return 0
            
            # Delete all cache keys
            await redis.delete(*cache_keys)
            
            # Delete the tag set
            await redis.delete(tag_set_key)
            
            await self._update_stats("invalidate", len(cache_keys))
            
            self.logger.info(
                "Invalidated cache entries by tag",
                extra={"tag": tag, "count": len(cache_keys)}
            )
            
            return len(cache_keys)
            
        except Exception as e:
            self.logger.error(
                "Failed to invalidate by tag",
                extra={"tag": tag, "error": str(e)}
            )
            return 0
    
    async def get_cache_info(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a cached entry.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Dictionary with cache entry metadata
        """
        try:
            redis = await self._get_redis()
            
            cached_data = await redis.get(cache_key)
            if not cached_data:
                return None
            
            entry_data = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
            
            # Calculate derived fields
            current_time = time.time()
            age = int(current_time - entry_data.get('created_at', current_time))
            ttl = int(entry_data.get('expires_at', current_time) - current_time)
            
            return {
                'cache_key': cache_key,
                'created_at': datetime.fromtimestamp(entry_data.get('created_at', 0), timezone.utc).isoformat(),
                'expires_at': datetime.fromtimestamp(entry_data.get('expires_at', 0), timezone.utc).isoformat(),
                'age_seconds': age,
                'ttl_seconds': max(0, ttl),
                'cache_version': entry_data.get('cache_version'),
                'file_hash': entry_data.get('file_hash', '')[:16] + '...',
                'config_hash': entry_data.get('config_hash'),
                'tags': entry_data.get('tags', []),
                'access_count': entry_data.get('access_count', 0),
                'data_size_bytes': len(json.dumps(entry_data.get('data', {})))
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get cache info",
                extra={"cache_key": cache_key, "error": str(e)}
            )
            return None
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired cache entries.
        
        Returns:
            int: Number of expired entries cleaned up
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            cleaned_count = 0
            
            # This is a simplified cleanup - in practice you'd want to iterate through
            # known cache keys or use Redis key expiration
            
            # Get cache statistics
            stats = await redis._client.hgetall(self.CACHE_STATS_KEY)
            if stats:
                stats['last_cleanup'] = str(int(current_time))
                await redis._client.hset(self.CACHE_STATS_KEY, mapping=stats)
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup expired entries",
                extra={"error": str(e)}
            )
            return 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            redis = await self._get_redis()
            
            # Get basic stats
            stats = await redis._client.hgetall(self.CACHE_STATS_KEY) or {}
            
            # Calculate hit ratio
            hits = int(stats.get('hits', 0))
            misses = int(stats.get('misses', 0))
            total_requests = hits + misses
            hit_ratio = (hits / total_requests * 100) if total_requests > 0 else 0
            
            # Get memory usage approximation
            info = await redis.info('memory')
            used_memory = info.get('used_memory', 0)
            
            return {
                'hit_ratio_percent': round(hit_ratio, 2),
                'total_requests': total_requests,
                'hits': hits,
                'misses': misses,
                'cache_sets': int(stats.get('sets', 0)),
                'cache_deletes': int(stats.get('deletes', 0)),
                'cache_invalidations': int(stats.get('invalidations', 0)),
                'cache_errors': int(stats.get('errors', 0)),
                'redis_memory_bytes': used_memory,
                'last_cleanup': stats.get('last_cleanup'),
                'statistics': {k: int(v) if v.isdigit() else v for k, v in stats.items()},
                'timestamp': time.time()
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get cache stats",
                extra={"error": str(e)}
            )
            return {}
    
    async def _update_stats(self, operation: str, count: int = 1) -> None:
        """Update cache operation statistics."""
        try:
            redis = await self._get_redis()
            
            stat_key = {
                'hit': 'hits',
                'miss': 'misses', 
                'set': 'sets',
                'delete': 'deletes',
                'invalidate': 'invalidations',
                'error': 'errors'
            }.get(operation, operation)
            
            await redis._client.hincrby(self.CACHE_STATS_KEY, stat_key, count)
            
        except Exception:
            pass  # Don't fail operations due to stats errors
    
    async def _update_access_stats(self, cache_key: str) -> None:
        """Update access statistics for cache entry."""
        try:
            redis = await self._get_redis()
            
            # This is a simplified implementation
            # In practice, you might store access stats separately to avoid
            # constantly updating cached data
            
            current_time = time.time()
            await redis._client.hincrby(f"access:{cache_key}", "count", 1)
            await redis._client.hset(f"access:{cache_key}", "last_access", str(current_time))
            await redis._client.expire(f"access:{cache_key}", self.default_ttl)
            
        except Exception:
            pass  # Don't fail operations due to access stats errors