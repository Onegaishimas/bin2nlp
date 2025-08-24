"""
Session and temporary data management using PostgreSQL + File Storage.

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
from ..core.utils import validate_binary_file_content, detect_file_format
from ..models.shared.enums import FileFormat
from ..storage.file_storage import get_file_storage


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
    allowed_formats: List[FileFormat]  # CHANGED: Use FileFormat enum instead of extensions
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
    PostgreSQL + File Storage session and temporary file management system.
    
    Features:
    - Upload session tracking with pre-signed URLs
    - Temporary file metadata storage in PostgreSQL
    - Automatic expiration and cleanup
    - Session status tracking and progress updates
    - Background cleanup tasks
    - File access tracking and statistics
    - Tag-based file organization
    """
    
    # Default TTL values (in seconds)
    DEFAULT_UPLOAD_SESSION_TTL = 3600  # 1 hour
    DEFAULT_TEMP_FILE_TTL = 86400  # 24 hours
    MAX_TEMP_FILE_TTL = 604800  # 7 days
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize session manager.
        
        Args:
            settings: Application settings
        """
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)
        
        # Configuration
        self.max_sessions_per_user = 10
        self.max_temp_files_per_user = 50
        self.cleanup_interval_seconds = 300  # 5 minutes
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def _get_database(self):
        """Get database connection."""
        from ..database.connection import get_database
        return await get_database()
    
    async def _get_storage(self):
        """Get file storage client."""
        return await get_file_storage()
    
    async def create_upload_session(
        self,
        filename: str,
        file_size: int,
        content_type: str,
        api_key_id: Optional[str] = None,
        max_file_size: Optional[int] = None,
        allowed_formats: Optional[List[FileFormat]] = None,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UploadSession:
        """
        Create a new upload session with Magika-based validation (ADR STANDARDIZED).
        
        Args:
            filename: Original filename
            file_size: Expected file size in bytes
            content_type: MIME content type
            api_key_id: API key identifier
            max_file_size: Maximum allowed file size
            allowed_formats: List of allowed FileFormat enums (replaces extensions)
            ttl_seconds: Session TTL in seconds
            metadata: Additional session metadata
            
        Returns:
            UploadSession object
            
        Raises:
            CacheException: If session creation fails
        """
        try:
            db = await self._get_database()
            current_time = time.time()
            
            # Generate session and upload IDs
            session_id = str(uuid.uuid4())
            upload_id = f"upload_{int(current_time)}_{uuid.uuid4().hex[:8]}"
            
            # Set defaults
            ttl = ttl_seconds or self.DEFAULT_UPLOAD_SESSION_TTL
            expires_at = current_time + ttl
            max_size = max_file_size or getattr(self.settings, 'MAX_FILE_SIZE_MB', 100) * 1024 * 1024
            formats = allowed_formats or [FileFormat.PE, FileFormat.ELF, FileFormat.MACHO, FileFormat.RAW]
            
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
                allowed_formats=formats,
                metadata=metadata or {}
            )
            
            # Validate session limits
            if api_key_id:
                await self._enforce_session_limits(api_key_id)
            
            # Store session in PostgreSQL sessions table
            await db.execute("""
                INSERT INTO sessions (
                    id, session_data, api_key_id, expires_at, created_at
                ) VALUES (
                    :session_id, :session_data, :api_key_id, :expires_at, NOW()
                )
            """, {
                "session_id": session_id,
                "session_data": json.dumps(upload_session.to_dict()),
                "api_key_id": api_key_id,
                "expires_at": datetime.fromtimestamp(expires_at)
            })
            
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
            db = await self._get_database()
            
            # Get session from PostgreSQL
            result = await db.fetch_one("""
                SELECT session_data, expires_at 
                FROM sessions 
                WHERE id = :session_id AND expires_at > NOW()
            """, {"session_id": session_id})
            
            if not result:
                return None
            
            session_dict = json.loads(result['session_data'])
            upload_session = UploadSession.from_dict(session_dict)
            
            # Double-check expiration (defensive programming)
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
            db = await self._get_database()
            
            # Get current session data
            result = await db.fetch_one("""
                SELECT session_data FROM sessions 
                WHERE id = :session_id AND expires_at > NOW()
            """, {"session_id": session_id})
            
            if not result:
                return False
            
            session_dict = json.loads(result['session_data'])
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
            
            # Store updated session in PostgreSQL
            await db.execute("""
                UPDATE sessions 
                SET session_data = :session_data 
                WHERE id = :session_id
            """, {
                "session_id": session_id,
                "session_data": json.dumps(upload_session.to_dict())
            })
            
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
            db = await self._get_database()
            
            # Delete session from PostgreSQL
            rows_deleted = await db.execute("""
                DELETE FROM sessions WHERE id = :session_id
            """, {"session_id": session_id})
            
            success = rows_deleted > 0
            
            if success:
                self.logger.debug(
                    "Upload session deleted",
                    extra={"session_id": session_id}
                )
            
            return success
            
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
            db = await self._get_database()
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
            
            # Store file metadata in PostgreSQL
            await db.execute("""
                INSERT INTO temp_files (
                    id, filename, stored_path, file_size, file_hash,
                    content_type, upload_session_id, api_key_id, 
                    expires_at, tags, created_at
                ) VALUES (
                    :file_id, :filename, :stored_path, :file_size, :file_hash,
                    :content_type, :upload_session_id, :api_key_id,
                    :expires_at, :tags, NOW()
                )
            """, {
                "file_id": file_id,
                "filename": original_filename,
                "stored_path": stored_path,
                "file_size": file_size,
                "file_hash": file_hash,
                "content_type": content_type,
                "upload_session_id": upload_session_id,
                "api_key_id": api_key_id,
                "expires_at": datetime.fromtimestamp(expires_at),
                "tags": json.dumps(list(tags or set()))
            })
            
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
            db = await self._get_database()
            
            # Get temp file from PostgreSQL
            result = await db.fetch_one("""
                SELECT filename, stored_path, file_size, file_hash,
                       content_type, upload_session_id, api_key_id,
                       access_count, last_accessed, tags,
                       EXTRACT(epoch FROM created_at) as created_at,
                       EXTRACT(epoch FROM expires_at) as expires_at
                FROM temp_files 
                WHERE id = :file_id AND expires_at > NOW()
            """, {"file_id": file_id})
            
            if not result:
                return None
            
            # Create TempFileMetadata from database result
            temp_file = TempFileMetadata(
                file_id=file_id,
                original_filename=result['filename'],
                stored_path=result['stored_path'],
                file_size=result['file_size'],
                file_hash=result['file_hash'],
                content_type=result['content_type'],
                upload_session_id=result['upload_session_id'],
                api_key_id=result['api_key_id'],
                created_at=result['created_at'],
                expires_at=result['expires_at'],
                access_count=result['access_count'] or 0,
                last_accessed=result['last_accessed'],
                tags=set(json.loads(result['tags'] or '[]'))
            )
            
            # Check if expired (defensive programming)
            if temp_file.is_expired():
                await self.delete_temp_file(file_id)
                return None
            
            # Update access statistics
            if update_access:
                await db.execute("""
                    UPDATE temp_files 
                    SET access_count = access_count + 1, last_accessed = NOW()
                    WHERE id = :file_id
                """, {"file_id": file_id})
                
                temp_file.access_count += 1
                temp_file.last_accessed = time.time()
            
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
            db = await self._get_database()
            
            # Delete temp file from PostgreSQL
            rows_deleted = await db.execute("""
                DELETE FROM temp_files WHERE id = :file_id
            """, {"file_id": file_id})
            
            success = rows_deleted > 0
            
            if success:
                self.logger.debug(
                    "Temporary file deleted",
                    extra={"file_id": file_id}
                )
            
            return success
            
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
            db = await self._get_database()
            
            # Find files by hash from PostgreSQL
            results = await db.fetch_all("""
                SELECT id FROM temp_files 
                WHERE file_hash = :file_hash AND expires_at > NOW()
            """, {"file_hash": file_hash})
            
            return [row['id'] for row in results]
            
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
            db = await self._get_database()
            
            # Delete expired sessions from PostgreSQL
            cleaned_count = await db.execute("""
                DELETE FROM sessions WHERE expires_at < NOW()
            """)
            
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
            db = await self._get_database()
            
            # Delete expired temp files from PostgreSQL
            cleaned_count = await db.execute("""
                DELETE FROM temp_files WHERE expires_at < NOW()
            """)
            
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
            db = await self._get_database()
            
            # Get current counts from PostgreSQL
            session_count = await db.fetch_val("""
                SELECT COUNT(*) FROM sessions WHERE expires_at > NOW()
            """)
            
            temp_files_count = await db.fetch_val("""
                SELECT COUNT(*) FROM temp_files WHERE expires_at > NOW()
            """)
            
            return {
                'active_upload_sessions': session_count or 0,
                'stored_temp_files': temp_files_count or 0,
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
                
                # Update stats (simplified for PostgreSQL implementation)
                if sessions_cleaned > 0 or files_cleaned > 0:
                    pass  # Could implement stats table if needed
                
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
            db = await self._get_database()
            
            session_count = await db.fetch_val("""
                SELECT COUNT(*) FROM sessions 
                WHERE api_key_id = :api_key_id AND expires_at > NOW()
            """, {"api_key_id": api_key_id})
            
            if session_count and session_count >= self.max_sessions_per_user:
                raise CacheException(f"Maximum sessions per user exceeded: {session_count}/{self.max_sessions_per_user}")
            
        except CacheException:
            raise
        except Exception:
            pass  # Don't fail session creation due to limit check errors
    
    async def _enforce_temp_file_limits(self, api_key_id: str) -> None:
        """Enforce temporary file limits per user."""
        try:
            db = await self._get_database()
            
            file_count = await db.fetch_val("""
                SELECT COUNT(*) FROM temp_files 
                WHERE api_key_id = :api_key_id AND expires_at > NOW()
            """, {"api_key_id": api_key_id})
            
            if file_count and file_count >= self.max_temp_files_per_user:
                raise CacheException(f"Maximum temp files per user exceeded: {file_count}/{self.max_temp_files_per_user}")
            
        except CacheException:
            raise
        except Exception:
            pass  # Don't fail operations due to limit check errors
    
    async def validate_uploaded_file(self, session_id: str, file_content: bytes) -> Dict[str, Any]:
        """
        Validate uploaded file content using Magika (ADR STANDARDIZED).
        
        This method replaces extension-based validation with ML-based detection.
        
        Args:
            session_id: Upload session ID
            file_content: Raw file content bytes
            
        Returns:
            Dictionary with validation results
            
        Raises:
            CacheException: If validation fails or session not found
        """
        try:
            # Get upload session
            session = await self.get_upload_session(session_id)
            if not session:
                raise CacheException(f"Upload session not found: {session_id}")
            
            # Use Magika to validate file content
            is_binary, detected_type, file_format = validate_binary_file_content(
                file_content, 
                session.filename
            )
            
            # Check if detected format is allowed
            format_allowed = file_format in session.allowed_formats
            
            # Check file size
            size_ok = len(file_content) <= session.max_file_size
            
            validation_result = {
                'session_id': session_id,
                'filename': session.filename,
                'file_size': len(file_content),
                'detected_type': detected_type,
                'detected_format': file_format,
                'is_binary': is_binary,
                'format_allowed': format_allowed,
                'size_ok': size_ok,
                'allowed_formats': [fmt.value for fmt in session.allowed_formats],
                'max_file_size': session.max_file_size,
                'validation_passed': is_binary and format_allowed and size_ok,
                'validation_method': 'magika',
                'validation_timestamp': time.time()
            }
            
            if not validation_result['validation_passed']:
                errors = []
                if not is_binary:
                    errors.append(f"File is not a binary executable (detected: {detected_type})")
                if not format_allowed:
                    errors.append(f"Format {file_format.value} not allowed (allowed: {[f.value for f in session.allowed_formats]})")
                if not size_ok:
                    errors.append(f"File size {len(file_content)} exceeds limit {session.max_file_size}")
                
                validation_result['errors'] = errors
            
            return validation_result
            
        except CacheException:
            raise
        except Exception as e:
            raise CacheException(f"File validation failed: {str(e)}")