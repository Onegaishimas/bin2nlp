"""
Session and temporary data management using Redis.

Provides upload session tracking, temporary file metadata storage,
pre-signed URL management, and automatic cleanup of expired data.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum

from ..core.config import Settings, get_settings
from ..core.exceptions import CacheException
from ..core.logging import get_logger
from .base import RedisClient


class SessionStatus(str, Enum):
    """Session status enumeration."""
    
    CREATED = "created"
    ACTIVE = "active"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class UploadSession:
    """Upload session information."""
    
    session_id: str
    api_key_id: Optional[str]
    upload_id: str
    presigned_url: str
    filename: str
    file_size: int
    content_type: str
    status: SessionStatus
    created_at: float
    expires_at: float
    max_file_size: int
    allowed_extensions: List[str]
    metadata: Dict[str, Any]
    upload_progress: int = 0
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return time.time() > self.expires_at
    
    def ttl_seconds(self) -> int:
        """Get remaining TTL in seconds."""
        return max(0, int(self.expires_at - time.time()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UploadSession':
        """Create from dictionary."""
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = SessionStatus(data['status'])
        return cls(**data)


@dataclass
class TempFileMetadata:
    """Temporary file metadata."""
    
    file_id: str
    original_filename: str
    stored_path: str
    file_size: int
    file_hash: str
    content_type: str
    upload_session_id: Optional[str]
    api_key_id: Optional[str]
    created_at: float
    expires_at: float
    access_count: int = 0
    last_accessed: Optional[float] = None
    tags: Set[str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.tags is None:
            self.tags = set()
    
    def is_expired(self) -> bool:
        """Check if file metadata is expired."""
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['tags'] = list(self.tags)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TempFileMetadata':
        """Create from dictionary."""
        if 'tags' in data and isinstance(data['tags'], list):
            data['tags'] = set(data['tags'])
        return cls(**data)


class SessionManager:
    """
    Redis-based session and temporary file management system.
    
    Features:
    - Upload session tracking with pre-signed URLs
    - Temporary file metadata storage
    - Automatic expiration and cleanup
    - Session status tracking and progress updates
    - Background cleanup tasks
    - File access tracking and statistics
    - Tag-based file organization
    """
    
    # Redis key patterns
    UPLOAD_SESSION_KEY = "session:upload:{session_id}"
    TEMP_FILE_KEY = "tempfile:{file_id}"
    USER_SESSIONS_SET = "user:sessions:{api_key_id}"
    ACTIVE_SESSIONS_SET = "sessions:active"
    TEMP_FILES_SET = "tempfiles:all"
    FILE_BY_HASH_KEY = "file:hash:{file_hash}"
    SESSION_STATS_KEY = "session:stats"
    
    # Default TTL values (in seconds)
    DEFAULT_UPLOAD_SESSION_TTL = 3600  # 1 hour
    DEFAULT_TEMP_FILE_TTL = 86400  # 24 hours
    MAX_TEMP_FILE_TTL = 604800  # 7 days
    
    def __init__(self, redis_client: Optional[RedisClient] = None, settings: Optional[Settings] = None):
        """
        Initialize session manager.
        
        Args:
            redis_client: Redis client instance
            settings: Application settings
        """
        self.redis_client = redis_client
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)
        
        # Configuration
        self.max_sessions_per_user = 10
        self.max_temp_files_per_user = 50
        self.cleanup_interval_seconds = 300  # 5 minutes
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance."""
        if self.redis_client is None:
            from .base import get_redis_client
            self.redis_client = await get_redis_client()
        return self.redis_client
    
    async def create_upload_session(
        self,
        filename: str,
        file_size: int,
        content_type: str,
        api_key_id: Optional[str] = None,
        max_file_size: Optional[int] = None,
        allowed_extensions: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UploadSession:
        """
        Create a new upload session.
        
        Args:
            filename: Original filename
            file_size: Expected file size in bytes
            content_type: MIME content type
            api_key_id: API key identifier
            max_file_size: Maximum allowed file size
            allowed_extensions: List of allowed file extensions
            ttl_seconds: Session TTL in seconds
            metadata: Additional session metadata
            
        Returns:
            UploadSession object
            
        Raises:
            CacheException: If session creation fails
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            
            # Generate session and upload IDs
            session_id = str(uuid.uuid4())
            upload_id = f"upload_{int(current_time)}_{uuid.uuid4().hex[:8]}"
            
            # Set defaults
            ttl = ttl_seconds or self.DEFAULT_UPLOAD_SESSION_TTL
            expires_at = current_time + ttl
            max_size = max_file_size or self.settings.get_max_file_size_bytes()
            extensions = allowed_extensions or ['.exe', '.dll', '.so', '.bin', '.elf']
            
            # Generate pre-signed URL (placeholder - would integrate with storage service)
            presigned_url = f"https://storage.example.com/upload/{upload_id}"
            
            # Create upload session
            upload_session = UploadSession(
                session_id=session_id,
                api_key_id=api_key_id,
                upload_id=upload_id,
                presigned_url=presigned_url,
                filename=filename,
                file_size=file_size,
                content_type=content_type,
                status=SessionStatus.CREATED,
                created_at=current_time,
                expires_at=expires_at,
                max_file_size=max_size,
                allowed_extensions=extensions,
                metadata=metadata or {}
            )
            
            # Validate session limits
            if api_key_id:
                await self._enforce_session_limits(api_key_id)
            
            # Store session in Redis
            session_key = self.UPLOAD_SESSION_KEY.format(session_id=session_id)
            await redis.set(session_key, json.dumps(upload_session.to_dict()), ex=ttl)
            
            # Add to active sessions set
            await redis._client.zadd(
                self.ACTIVE_SESSIONS_SET,
                {session_id: expires_at}
            )
            
            # Add to user sessions set if API key provided
            if api_key_id:
                user_sessions_key = self.USER_SESSIONS_SET.format(api_key_id=api_key_id)
                await redis._client.sadd(user_sessions_key, session_id)
                await redis._client.expire(user_sessions_key, ttl)
            
            # Update statistics
            await self._update_stats("sessions_created")
            
            self.logger.info(
                "Upload session created",
                extra={
                    "session_id": session_id,
                    "upload_id": upload_id,
                    "filename": filename,
                    "api_key_id": api_key_id,
                    "expires_in_seconds": ttl
                }
            )
            
            return upload_session
            
        except Exception as e:
            self.logger.error(
                "Failed to create upload session",
                extra={"filename": filename, "error": str(e)}
            )
            raise CacheException(f"Failed to create upload session: {e}")
    
    async def get_upload_session(self, session_id: str) -> Optional[UploadSession]:
        """
        Get upload session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            UploadSession object or None if not found
        """
        try:
            redis = await self._get_redis()
            
            session_key = self.UPLOAD_SESSION_KEY.format(session_id=session_id)
            session_data = await redis.get(session_key)
            
            if not session_data:
                return None
            
            session_dict = json.loads(session_data) if isinstance(session_data, str) else session_data
            upload_session = UploadSession.from_dict(session_dict)
            
            # Check if expired
            if upload_session.is_expired():
                await self.delete_upload_session(session_id)
                return None
            
            return upload_session
            
        except Exception as e:
            self.logger.error(
                "Failed to get upload session",
                extra={"session_id": session_id, "error": str(e)}
            )
            return None
    
    async def update_upload_session(
        self,
        session_id: str,
        status: Optional[SessionStatus] = None,
        upload_progress: Optional[int] = None,
        completed_at: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update upload session status and progress.
        
        Args:
            session_id: Session identifier
            status: New session status
            upload_progress: Upload progress percentage (0-100)
            completed_at: Completion timestamp
            error_message: Error message if applicable
            
        Returns:
            bool: True if updated successfully
        """
        try:
            redis = await self._get_redis()
            
            session_key = self.UPLOAD_SESSION_KEY.format(session_id=session_id)
            session_data = await redis.get(session_key)
            
            if not session_data:
                return False
            
            session_dict = json.loads(session_data) if isinstance(session_data, str) else session_data
            upload_session = UploadSession.from_dict(session_dict)
            
            # Update fields
            if status is not None:
                upload_session.status = status
            if upload_progress is not None:
                upload_session.upload_progress = max(0, min(100, upload_progress))
            if completed_at is not None:
                upload_session.completed_at = completed_at
            if error_message is not None:
                upload_session.error_message = error_message
            
            # Store updated session
            ttl = upload_session.ttl_seconds()
            await redis.set(session_key, json.dumps(upload_session.to_dict()), ex=ttl)
            
            self.logger.debug(
                "Upload session updated",
                extra={
                    "session_id": session_id,
                    "status": status.value if status else None,
                    "progress": upload_progress
                }
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to update upload session",
                extra={"session_id": session_id, "error": str(e)}
            )
            return False
    
    async def delete_upload_session(self, session_id: str) -> bool:
        """
        Delete upload session and cleanup associated data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            redis = await self._get_redis()
            
            # Get session to find associated data
            upload_session = await self.get_upload_session(session_id)
            
            # Delete session key
            session_key = self.UPLOAD_SESSION_KEY.format(session_id=session_id)
            await redis.delete(session_key)
            
            # Remove from active sessions set
            await redis._client.zrem(self.ACTIVE_SESSIONS_SET, session_id)
            
            # Remove from user sessions set if applicable
            if upload_session and upload_session.api_key_id:
                user_sessions_key = self.USER_SESSIONS_SET.format(api_key_id=upload_session.api_key_id)
                await redis._client.srem(user_sessions_key, session_id)
            
            await self._update_stats("sessions_deleted")
            
            self.logger.debug(
                "Upload session deleted",
                extra={"session_id": session_id}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to delete upload session",
                extra={"session_id": session_id, "error": str(e)}
            )
            return False
    
    async def store_temp_file(
        self,
        original_filename: str,
        stored_path: str,
        file_size: int,
        file_hash: str,
        content_type: str,
        upload_session_id: Optional[str] = None,
        api_key_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None
    ) -> str:
        """
        Store temporary file metadata.
        
        Args:
            original_filename: Original filename
            stored_path: Path where file is stored
            file_size: File size in bytes
            file_hash: SHA-256 hash of file content
            content_type: MIME content type
            upload_session_id: Associated upload session ID
            api_key_id: API key identifier
            ttl_seconds: TTL in seconds
            tags: File tags for organization
            
        Returns:
            str: File ID
            
        Raises:
            CacheException: If storage fails
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            
            # Generate file ID
            file_id = str(uuid.uuid4())
            
            # Set TTL
            ttl = min(ttl_seconds or self.DEFAULT_TEMP_FILE_TTL, self.MAX_TEMP_FILE_TTL)
            expires_at = current_time + ttl
            
            # Create temp file metadata
            temp_file = TempFileMetadata(
                file_id=file_id,
                original_filename=original_filename,
                stored_path=stored_path,
                file_size=file_size,
                file_hash=file_hash,
                content_type=content_type,
                upload_session_id=upload_session_id,
                api_key_id=api_key_id,
                created_at=current_time,
                expires_at=expires_at,
                tags=tags or set()
            )
            
            # Validate temp file limits
            if api_key_id:
                await self._enforce_temp_file_limits(api_key_id)
            
            # Store file metadata
            file_key = self.TEMP_FILE_KEY.format(file_id=file_id)
            await redis.set(file_key, json.dumps(temp_file.to_dict()), ex=ttl)
            
            # Add to global temp files set
            await redis._client.zadd(
                self.TEMP_FILES_SET,
                {file_id: expires_at}
            )
            
            # Index by file hash for deduplication
            hash_key = self.FILE_BY_HASH_KEY.format(file_hash=file_hash)
            await redis._client.sadd(hash_key, file_id)
            await redis._client.expire(hash_key, ttl)
            
            await self._update_stats("temp_files_stored")
            
            self.logger.info(
                "Temporary file stored",
                extra={
                    "file_id": file_id,
                    "filename": original_filename,
                    "file_size": file_size,
                    "file_hash": file_hash[:16] + "...",
                    "ttl_seconds": ttl
                }
            )
            
            return file_id
            
        except Exception as e:
            self.logger.error(
                "Failed to store temp file",
                extra={"filename": original_filename, "error": str(e)}
            )
            raise CacheException(f"Failed to store temp file: {e}")
    
    async def get_temp_file(self, file_id: str, update_access: bool = True) -> Optional[TempFileMetadata]:
        """
        Get temporary file metadata.
        
        Args:
            file_id: File identifier
            update_access: Whether to update access statistics
            
        Returns:
            TempFileMetadata object or None if not found
        """
        try:
            redis = await self._get_redis()
            
            file_key = self.TEMP_FILE_KEY.format(file_id=file_id)
            file_data = await redis.get(file_key)
            
            if not file_data:
                return None
            
            file_dict = json.loads(file_data) if isinstance(file_data, str) else file_data
            temp_file = TempFileMetadata.from_dict(file_dict)
            
            # Check if expired
            if temp_file.is_expired():
                await self.delete_temp_file(file_id)
                return None
            
            # Update access statistics
            if update_access:
                temp_file.access_count += 1
                temp_file.last_accessed = time.time()
                
                # Update in Redis
                ttl = temp_file.ttl_seconds()
                await redis.set(file_key, json.dumps(temp_file.to_dict()), ex=ttl)
            
            return temp_file
            
        except Exception as e:
            self.logger.error(
                "Failed to get temp file",
                extra={"file_id": file_id, "error": str(e)}
            )
            return None
    
    async def delete_temp_file(self, file_id: str) -> bool:
        """
        Delete temporary file metadata and cleanup.
        
        Args:
            file_id: File identifier
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            redis = await self._get_redis()
            
            # Get file metadata first
            temp_file = await self.get_temp_file(file_id, update_access=False)
            
            # Delete file metadata
            file_key = self.TEMP_FILE_KEY.format(file_id=file_id)
            await redis.delete(file_key)
            
            # Remove from temp files set
            await redis._client.zrem(self.TEMP_FILES_SET, file_id)
            
            # Remove from hash index
            if temp_file:
                hash_key = self.FILE_BY_HASH_KEY.format(file_hash=temp_file.file_hash)
                await redis._client.srem(hash_key, file_id)
            
            await self._update_stats("temp_files_deleted")
            
            self.logger.debug(
                "Temporary file deleted",
                extra={"file_id": file_id}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to delete temp file",
                extra={"file_id": file_id, "error": str(e)}
            )
            return False
    
    async def find_files_by_hash(self, file_hash: str) -> List[str]:
        """
        Find temporary files by hash (deduplication).
        
        Args:
            file_hash: SHA-256 file hash
            
        Returns:
            List of file IDs with matching hash
        """
        try:
            redis = await self._get_redis()
            
            hash_key = self.FILE_BY_HASH_KEY.format(file_hash=file_hash)
            file_ids = await redis._client.smembers(hash_key)
            
            # Filter out expired files
            valid_file_ids = []
            for file_id in file_ids:
                if await self.get_temp_file(file_id, update_access=False):
                    valid_file_ids.append(file_id)
            
            return valid_file_ids
            
        except Exception as e:
            self.logger.error(
                "Failed to find files by hash",
                extra={"file_hash": file_hash[:16] + "...", "error": str(e)}
            )
            return []
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired upload sessions.
        
        Returns:
            int: Number of sessions cleaned up
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            cleaned_count = 0
            
            # Get expired sessions from sorted set
            expired_sessions = await redis._client.zrangebyscore(
                self.ACTIVE_SESSIONS_SET, 0, current_time
            )
            
            for session_id in expired_sessions:
                await self.delete_upload_session(session_id)
                cleaned_count += 1
            
            if cleaned_count > 0:
                self.logger.info(
                    "Cleaned up expired upload sessions",
                    extra={"cleaned_count": cleaned_count}
                )
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup expired sessions",
                extra={"error": str(e)}
            )
            return 0
    
    async def cleanup_expired_temp_files(self) -> int:
        """
        Clean up expired temporary files.
        
        Returns:
            int: Number of temp files cleaned up
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            cleaned_count = 0
            
            # Get expired temp files from sorted set
            expired_files = await redis._client.zrangebyscore(
                self.TEMP_FILES_SET, 0, current_time
            )
            
            for file_id in expired_files:
                await self.delete_temp_file(file_id)
                cleaned_count += 1
            
            if cleaned_count > 0:
                self.logger.info(
                    "Cleaned up expired temp files",
                    extra={"cleaned_count": cleaned_count}
                )
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup expired temp files",
                extra={"error": str(e)}
            )
            return 0
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """
        Get session management statistics.
        
        Returns:
            Dictionary with session statistics
        """
        try:
            redis = await self._get_redis()
            
            # Get basic stats
            stats = await redis._client.hgetall(self.SESSION_STATS_KEY) or {}
            
            # Get current counts
            active_sessions = await redis._client.zcard(self.ACTIVE_SESSIONS_SET)
            temp_files = await redis._client.zcard(self.TEMP_FILES_SET)
            
            return {
                'active_upload_sessions': active_sessions,
                'stored_temp_files': temp_files,
                'sessions_created': int(stats.get('sessions_created', 0)),
                'sessions_deleted': int(stats.get('sessions_deleted', 0)),
                'temp_files_stored': int(stats.get('temp_files_stored', 0)),
                'temp_files_deleted': int(stats.get('temp_files_deleted', 0)),
                'cleanup_runs': int(stats.get('cleanup_runs', 0)),
                'last_cleanup': stats.get('last_cleanup'),
                'timestamp': time.time()
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get session stats",
                extra={"error": str(e)}
            )
            return {}
    
    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self.logger.info("Session cleanup task started")
    
    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Session cleanup task stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup task loop."""
        while True:
            try:
                # Cleanup expired sessions and temp files
                sessions_cleaned = await self.cleanup_expired_sessions()
                files_cleaned = await self.cleanup_expired_temp_files()
                
                # Update stats
                if sessions_cleaned > 0 or files_cleaned > 0:
                    await self._update_stats("cleanup_runs")
                    
                    redis = await self._get_redis()
                    await redis._client.hset(
                        self.SESSION_STATS_KEY,
                        "last_cleanup",
                        str(int(time.time()))
                    )
                
                # Wait for next cleanup cycle
                await asyncio.sleep(self.cleanup_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    "Cleanup task error",
                    extra={"error": str(e)}
                )
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _enforce_session_limits(self, api_key_id: str) -> None:
        """Enforce session limits per user."""
        try:
            redis = await self._get_redis()
            
            user_sessions_key = self.USER_SESSIONS_SET.format(api_key_id=api_key_id)
            session_count = await redis._client.scard(user_sessions_key)
            
            if session_count >= self.max_sessions_per_user:
                raise CacheException(f"Maximum sessions per user exceeded: {session_count}/{self.max_sessions_per_user}")
            
        except CacheException:
            raise
        except Exception:
            pass  # Don't fail session creation due to limit check errors
    
    async def _enforce_temp_file_limits(self, api_key_id: str) -> None:
        """Enforce temporary file limits per user."""
        # Implementation would depend on how you want to track per-user file counts
        # This is a simplified version
        pass
    
    async def _update_stats(self, stat_name: str, count: int = 1) -> None:
        """Update session statistics."""
        try:
            redis = await self._get_redis()
            await redis._client.hincrby(self.SESSION_STATS_KEY, stat_name, count)
        except Exception:
            pass  # Don't fail operations due to stats errors