"""
Unit tests for session management system.

Tests upload session tracking, temporary file metadata, expiration handling,
and background cleanup with mocked Redis and time-based scenarios.
"""

import asyncio
import json
import time
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.cache.session import (
    SessionManager, UploadSession, TempFileMetadata, SessionStatus
)
from src.cache.base import RedisClient
from src.core.config import Settings
from src.core.exceptions import CacheException


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client for session manager testing."""
    redis_mock = AsyncMock(spec=RedisClient)
    redis_mock._client = AsyncMock()
    
    # Mock Redis operations
    redis_mock._client.zadd = AsyncMock(return_value=1)
    redis_mock._client.zrem = AsyncMock(return_value=1)
    redis_mock._client.zcard = AsyncMock(return_value=0)
    redis_mock._client.zrangebyscore = AsyncMock(return_value=[])
    redis_mock._client.sadd = AsyncMock(return_value=1)
    redis_mock._client.srem = AsyncMock(return_value=1)
    redis_mock._client.smembers = AsyncMock(return_value=set())
    redis_mock._client.scard = AsyncMock(return_value=0)
    redis_mock._client.hincrby = AsyncMock(return_value=1)
    redis_mock._client.hset = AsyncMock(return_value=1)
    redis_mock._client.hgetall = AsyncMock(return_value={})
    redis_mock._client.expire = AsyncMock(return_value=True)
    
    # Mock get/set/delete operations
    redis_mock.get = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    
    return redis_mock


@pytest.fixture
def mock_settings():
    """Create mock settings for session manager testing."""
    settings = MagicMock(spec=Settings)
    settings.get_max_file_size_bytes = MagicMock(return_value=100 * 1024 * 1024)  # 100MB
    return settings


@pytest.fixture
def session_manager(mock_redis_client, mock_settings):
    """Create SessionManager instance with mocked dependencies."""
    manager = SessionManager(redis_client=mock_redis_client, settings=mock_settings)
    return manager


@pytest.fixture
def sample_upload_session():
    """Create sample upload session for testing."""
    current_time = time.time()
    return UploadSession(
        session_id="session_123",
        api_key_id="api_key_456",
        upload_id="upload_789",
        presigned_url="https://storage.example.com/upload_789",
        filename="test.exe",
        file_size=2048,
        content_type="application/octet-stream",
        status=SessionStatus.CREATED,
        created_at=current_time,
        expires_at=current_time + 3600,
        max_file_size=100 * 1024 * 1024,
        allowed_extensions=[".exe", ".dll", ".so"],
        metadata={"source": "api", "user": "test_user"}
    )


@pytest.fixture
def sample_temp_file():
    """Create sample temporary file metadata for testing."""
    current_time = time.time()
    return TempFileMetadata(
        file_id="file_123",
        original_filename="sample.exe",
        stored_path="/tmp/stored_file_123",
        file_size=4096,
        file_hash="abc123def456",
        content_type="application/x-executable",
        upload_session_id="session_123",
        api_key_id="api_key_456",
        created_at=current_time,
        expires_at=current_time + 86400,  # 24 hours
        tags={"binary", "analysis"}
    )


class TestSessionStatus:
    """Test cases for SessionStatus enum."""
    
    def test_session_status_values(self):
        """Test SessionStatus enum values."""
        assert SessionStatus.CREATED == "created"
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.UPLOADING == "uploading"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.EXPIRED == "expired"
        assert SessionStatus.CANCELLED == "cancelled"


class TestUploadSession:
    """Test cases for UploadSession dataclass."""
    
    def test_upload_session_creation(self, sample_upload_session):
        """Test UploadSession creation and properties."""
        session = sample_upload_session
        
        assert session.session_id == "session_123"
        assert session.filename == "test.exe"
        assert session.status == SessionStatus.CREATED
        assert not session.is_expired()
        assert session.ttl_seconds() > 0
    
    def test_upload_session_serialization(self, sample_upload_session):
        """Test UploadSession serialization and deserialization."""
        session = sample_upload_session
        
        # Test serialization
        session_dict = session.to_dict()
        assert isinstance(session_dict, dict)
        assert session_dict["session_id"] == "session_123"
        assert session_dict["status"] == "created"
        
        # Test deserialization
        restored_session = UploadSession.from_dict(session_dict)
        assert restored_session.session_id == session.session_id
        assert restored_session.status == session.status
        assert isinstance(restored_session.status, SessionStatus)
    
    def test_upload_session_expired(self):
        """Test expired upload session detection."""
        current_time = time.time()
        expired_session = UploadSession(
            session_id="expired_123",
            api_key_id=None,
            upload_id="upload_expired",
            presigned_url="https://example.com/expired",
            filename="expired.exe",
            file_size=1024,
            content_type="application/octet-stream",
            status=SessionStatus.CREATED,
            created_at=current_time - 7200,  # 2 hours ago
            expires_at=current_time - 3600,  # 1 hour ago (expired)
            max_file_size=1024 * 1024,
            allowed_extensions=[".exe"],
            metadata={}
        )
        
        assert expired_session.is_expired()
        assert expired_session.ttl_seconds() == 0


class TestTempFileMetadata:
    """Test cases for TempFileMetadata dataclass."""
    
    def test_temp_file_creation(self, sample_temp_file):
        """Test TempFileMetadata creation and properties."""
        temp_file = sample_temp_file
        
        assert temp_file.file_id == "file_123"
        assert temp_file.original_filename == "sample.exe"
        assert temp_file.file_size == 4096
        assert not temp_file.is_expired()
        assert "binary" in temp_file.tags
    
    def test_temp_file_serialization(self, sample_temp_file):
        """Test TempFileMetadata serialization and deserialization."""
        temp_file = sample_temp_file
        
        # Test serialization
        file_dict = temp_file.to_dict()
        assert isinstance(file_dict, dict)
        assert file_dict["file_id"] == "file_123"
        assert isinstance(file_dict["tags"], list)
        
        # Test deserialization
        restored_file = TempFileMetadata.from_dict(file_dict)
        assert restored_file.file_id == temp_file.file_id
        assert restored_file.tags == temp_file.tags
        assert isinstance(restored_file.tags, set)
    
    def test_temp_file_expired(self):
        """Test expired temporary file detection."""
        current_time = time.time()
        expired_file = TempFileMetadata(
            file_id="expired_file",
            original_filename="expired.exe",
            stored_path="/tmp/expired",
            file_size=1024,
            file_hash="expired_hash",
            content_type="application/octet-stream",
            upload_session_id=None,
            api_key_id=None,
            created_at=current_time - 86400,  # 1 day ago
            expires_at=current_time - 3600,   # 1 hour ago (expired)
            tags=set()
        )
        
        assert expired_file.is_expired()


class TestSessionManager:
    """Test cases for SessionManager class."""
    
    def test_session_manager_initialization(self, mock_redis_client, mock_settings):
        """Test SessionManager initialization."""
        manager = SessionManager(redis_client=mock_redis_client, settings=mock_settings)
        
        assert manager.redis_client == mock_redis_client
        assert manager.settings == mock_settings
        assert manager.DEFAULT_UPLOAD_SESSION_TTL == 3600
        assert manager.DEFAULT_TEMP_FILE_TTL == 86400
        assert manager.max_sessions_per_user == 10
    
    @pytest.mark.asyncio
    async def test_create_upload_session_success(self, session_manager, mock_redis_client):
        """Test successful upload session creation."""
        with patch('uuid.uuid4') as mock_uuid, patch('time.time') as mock_time:
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="session_123")
            mock_time.return_value = 1234567890
            
            session = await session_manager.create_upload_session(
                filename="test.exe",
                file_size=2048,
                content_type="application/octet-stream",
                api_key_id="api_key_456"
            )
            
            assert session.session_id == "session_123"
            assert session.filename == "test.exe"
            assert session.status == SessionStatus.CREATED
            
            # Verify Redis operations
            mock_redis_client.set.assert_called()
            mock_redis_client._client.zadd.assert_called()
            mock_redis_client._client.sadd.assert_called()
    
    @pytest.mark.asyncio
    async def test_create_upload_session_custom_params(self, session_manager, mock_redis_client):
        """Test upload session creation with custom parameters."""
        with patch('uuid.uuid4') as mock_uuid, patch('time.time') as mock_time:
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="custom_123")
            mock_time.return_value = 1234567890
            
            session = await session_manager.create_upload_session(
                filename="custom.exe",
                file_size=4096,
                content_type="application/x-executable",
                api_key_id="custom_api",
                max_file_size=50 * 1024 * 1024,  # 50MB
                allowed_extensions=[".exe", ".bin"],
                ttl_seconds=7200,  # 2 hours
                metadata={"source": "custom", "priority": "high"}
            )
            
            assert session.max_file_size == 50 * 1024 * 1024
            assert ".bin" in session.allowed_extensions
            assert session.metadata["priority"] == "high"
            
            # Verify custom TTL used
            call_args = mock_redis_client.set.call_args
            assert call_args[1]["ex"] == 7200
    
    @pytest.mark.asyncio
    async def test_get_upload_session_success(self, session_manager, mock_redis_client, sample_upload_session):
        """Test successful upload session retrieval."""
        # Mock session data in Redis
        session_data = sample_upload_session.to_dict()
        mock_redis_client.get.return_value = session_data
        
        session = await session_manager.get_upload_session("session_123")
        
        assert session is not None
        assert session.session_id == "session_123"
        assert session.filename == "test.exe"
    
    @pytest.mark.asyncio
    async def test_get_upload_session_not_found(self, session_manager, mock_redis_client):
        """Test upload session retrieval for non-existent session."""
        mock_redis_client.get.return_value = None
        
        session = await session_manager.get_upload_session("nonexistent")
        
        assert session is None
    
    @pytest.mark.asyncio
    async def test_get_upload_session_expired(self, session_manager, mock_redis_client):
        """Test upload session retrieval for expired session."""
        current_time = time.time()
        expired_session_data = {
            "session_id": "expired_123",
            "api_key_id": None,
            "upload_id": "upload_expired",
            "presigned_url": "https://example.com/expired",
            "filename": "expired.exe",
            "file_size": 1024,
            "content_type": "application/octet-stream",
            "status": "created",
            "created_at": current_time - 7200,
            "expires_at": current_time - 3600,  # Expired
            "max_file_size": 1024 * 1024,
            "allowed_extensions": [".exe"],
            "metadata": {}
        }
        mock_redis_client.get.return_value = expired_session_data
        
        session = await session_manager.get_upload_session("expired_123")
        
        assert session is None  # Should return None for expired session
        # Should trigger deletion
        mock_redis_client.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_update_upload_session_success(self, session_manager, mock_redis_client, sample_upload_session):
        """Test successful upload session update."""
        # Mock existing session
        session_data = sample_upload_session.to_dict()
        mock_redis_client.get.return_value = session_data
        
        result = await session_manager.update_upload_session(
            session_id="session_123",
            status=SessionStatus.UPLOADING,
            upload_progress=50,
            current_stage="processing"
        )
        
        assert result is True
        mock_redis_client.set.assert_called()
        
        # Verify updated data was stored
        call_args = mock_redis_client.set.call_args[0][1]  # Second argument (data)
        if isinstance(call_args, str):
            updated_data = json.loads(call_args)
        else:
            updated_data = call_args
        assert updated_data["status"] == "uploading"
        assert updated_data["upload_progress"] == 50
    
    @pytest.mark.asyncio
    async def test_update_upload_session_not_found(self, session_manager, mock_redis_client):
        """Test updating non-existent upload session."""
        mock_redis_client.get.return_value = None
        
        result = await session_manager.update_upload_session(
            session_id="nonexistent",
            status=SessionStatus.COMPLETED
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_upload_session_success(self, session_manager, mock_redis_client, sample_upload_session):
        """Test successful upload session deletion."""
        # Mock existing session
        session_data = sample_upload_session.to_dict()
        mock_redis_client.get.return_value = session_data
        
        result = await session_manager.delete_upload_session("session_123")
        
        assert result is True
        mock_redis_client.delete.assert_called()
        mock_redis_client._client.zrem.assert_called()
        mock_redis_client._client.srem.assert_called()
    
    @pytest.mark.asyncio
    async def test_store_temp_file_success(self, session_manager, mock_redis_client):
        """Test successful temporary file storage."""
        with patch('uuid.uuid4') as mock_uuid, patch('time.time') as mock_time:
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="file_123")
            mock_time.return_value = 1234567890
            
            file_id = await session_manager.store_temp_file(
                original_filename="test.exe",
                stored_path="/tmp/test_123",
                file_size=4096,
                file_hash="abc123def456",
                content_type="application/x-executable",
                upload_session_id="session_123",
                api_key_id="api_key_456",
                tags={"binary", "analysis"}
            )
            
            assert file_id == "file_123"
            
            # Verify Redis operations
            mock_redis_client.set.assert_called()
            mock_redis_client._client.zadd.assert_called()
            mock_redis_client._client.sadd.assert_called()
    
    @pytest.mark.asyncio
    async def test_store_temp_file_custom_ttl(self, session_manager, mock_redis_client):
        """Test temporary file storage with custom TTL."""
        with patch('uuid.uuid4') as mock_uuid, patch('time.time') as mock_time:
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="file_456")
            mock_time.return_value = 1234567890
            
            custom_ttl = 172800  # 2 days
            file_id = await session_manager.store_temp_file(
                original_filename="long_term.exe",
                stored_path="/tmp/long_term_456",
                file_size=8192,
                file_hash="def456ghi789",
                content_type="application/octet-stream",
                ttl_seconds=custom_ttl
            )
            
            assert file_id == "file_456"
            
            # Verify custom TTL was used
            call_args = mock_redis_client.set.call_args
            assert call_args[1]["ex"] == custom_ttl
    
    @pytest.mark.asyncio
    async def test_get_temp_file_success(self, session_manager, mock_redis_client, sample_temp_file):
        """Test successful temporary file retrieval."""
        # Mock temp file data
        file_data = sample_temp_file.to_dict()
        mock_redis_client.get.return_value = file_data
        
        temp_file = await session_manager.get_temp_file("file_123")
        
        assert temp_file is not None
        assert temp_file.file_id == "file_123"
        assert temp_file.original_filename == "sample.exe"
        assert temp_file.access_count == 1  # Should increment on access
    
    @pytest.mark.asyncio
    async def test_get_temp_file_no_access_update(self, session_manager, mock_redis_client, sample_temp_file):
        """Test temporary file retrieval without access update."""
        # Mock temp file data
        file_data = sample_temp_file.to_dict()
        mock_redis_client.get.return_value = file_data
        
        temp_file = await session_manager.get_temp_file("file_123", update_access=False)
        
        assert temp_file is not None
        assert temp_file.access_count == 0  # Should not increment
    
    @pytest.mark.asyncio
    async def test_get_temp_file_expired(self, session_manager, mock_redis_client):
        """Test temporary file retrieval for expired file."""
        current_time = time.time()
        expired_file_data = {
            "file_id": "expired_file",
            "original_filename": "expired.exe",
            "stored_path": "/tmp/expired",
            "file_size": 1024,
            "file_hash": "expired_hash",
            "content_type": "application/octet-stream",
            "upload_session_id": None,
            "api_key_id": None,
            "created_at": current_time - 86400,
            "expires_at": current_time - 3600,  # Expired
            "access_count": 0,
            "last_accessed": None,
            "tags": []
        }
        mock_redis_client.get.return_value = expired_file_data
        
        temp_file = await session_manager.get_temp_file("expired_file")
        
        assert temp_file is None  # Should return None for expired file
        # Should trigger deletion
        mock_redis_client.delete.assert_called()
    
    @pytest.mark.asyncio
    async def test_delete_temp_file_success(self, session_manager, mock_redis_client, sample_temp_file):
        """Test successful temporary file deletion."""
        # Mock existing temp file
        file_data = sample_temp_file.to_dict()
        mock_redis_client.get.return_value = file_data
        
        result = await session_manager.delete_temp_file("file_123")
        
        assert result is True
        mock_redis_client.delete.assert_called()
        mock_redis_client._client.zrem.assert_called()
        mock_redis_client._client.srem.assert_called()
    
    @pytest.mark.asyncio
    async def test_find_files_by_hash(self, session_manager, mock_redis_client):
        """Test finding files by hash for deduplication."""
        # Mock files with same hash
        mock_redis_client._client.smembers.return_value = {"file_1", "file_2", "file_3"}
        
        # Mock get_temp_file to return valid files for some IDs
        async def mock_get_temp_file(file_id, update_access=True):
            if file_id in ["file_1", "file_3"]:
                return TempFileMetadata(
                    file_id=file_id,
                    original_filename=f"{file_id}.exe",
                    stored_path=f"/tmp/{file_id}",
                    file_size=1024,
                    file_hash="same_hash",
                    content_type="application/octet-stream",
                    upload_session_id=None,
                    api_key_id=None,
                    created_at=time.time(),
                    expires_at=time.time() + 3600,
                    tags=set()
                )
            return None  # file_2 is expired/invalid
        
        session_manager.get_temp_file = mock_get_temp_file
        
        files = await session_manager.find_files_by_hash("same_hash")
        
        # Should only return valid files (file_1 and file_3)
        assert len(files) == 2
        assert "file_1" in files
        assert "file_3" in files
        assert "file_2" not in files  # Expired/invalid
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_manager, mock_redis_client):
        """Test cleanup of expired upload sessions."""
        # Mock expired sessions
        mock_redis_client._client.zrangebyscore.return_value = [
            "expired_session_1", "expired_session_2"
        ]
        
        # Mock delete session method
        session_manager.delete_upload_session = AsyncMock(return_value=True)
        
        count = await session_manager.cleanup_expired_sessions()
        
        assert count == 2
        assert session_manager.delete_upload_session.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_temp_files(self, session_manager, mock_redis_client):
        """Test cleanup of expired temporary files."""
        # Mock expired temp files
        mock_redis_client._client.zrangebyscore.return_value = [
            "expired_file_1", "expired_file_2", "expired_file_3"
        ]
        
        # Mock delete temp file method
        session_manager.delete_temp_file = AsyncMock(return_value=True)
        
        count = await session_manager.cleanup_expired_temp_files()
        
        assert count == 3
        assert session_manager.delete_temp_file.call_count == 3
    
    @pytest.mark.asyncio
    async def test_get_session_stats(self, session_manager, mock_redis_client):
        """Test session statistics retrieval."""
        # Mock statistics
        mock_redis_client._client.hgetall.return_value = {
            "sessions_created": "100",
            "sessions_deleted": "80",
            "temp_files_stored": "150",
            "temp_files_deleted": "120",
            "cleanup_runs": "10"
        }
        
        # Mock current counts
        mock_redis_client._client.zcard.side_effect = [20, 30]  # active sessions, temp files
        
        stats = await session_manager.get_session_stats()
        
        assert "active_upload_sessions" in stats
        assert "stored_temp_files" in stats
        assert stats["active_upload_sessions"] == 20
        assert stats["stored_temp_files"] == 30
        assert stats["sessions_created"] == 100
        assert stats["temp_files_stored"] == 150
    
    @pytest.mark.asyncio
    async def test_cleanup_task_lifecycle(self, session_manager):
        """Test background cleanup task lifecycle."""
        # Start cleanup task
        await session_manager.start_cleanup_task()
        assert session_manager._cleanup_task is not None
        assert not session_manager._cleanup_task.done()
        
        # Starting again should not create new task
        old_task = session_manager._cleanup_task
        await session_manager.start_cleanup_task()
        assert session_manager._cleanup_task == old_task
        
        # Stop cleanup task
        await session_manager.stop_cleanup_task()
        assert session_manager._cleanup_task.cancelled()
    
    @pytest.mark.asyncio
    async def test_error_handling_redis_failure(self, session_manager, mock_redis_client):
        """Test error handling when Redis operations fail."""
        # Mock Redis failure
        mock_redis_client.set.side_effect = Exception("Redis connection lost")
        
        with pytest.raises(CacheException, match="Failed to create upload session"):
            await session_manager.create_upload_session(
                filename="test.exe",
                file_size=1024,
                content_type="application/octet-stream"
            )
    
    @pytest.mark.asyncio
    async def test_session_limits_enforcement(self, session_manager, mock_redis_client):
        """Test enforcement of session limits per user."""
        # Mock user already at session limit
        mock_redis_client._client.scard.return_value = 10  # At limit
        
        with pytest.raises(CacheException, match="Maximum sessions per user exceeded"):
            await session_manager.create_upload_session(
                filename="test.exe",
                file_size=1024,
                content_type="application/octet-stream",
                api_key_id="limited_user"
            )


class TestSessionManagerTimeBasedScenarios:
    """Time-based test scenarios for session management."""
    
    @pytest.mark.asyncio
    async def test_session_expiration_timeline(self, session_manager, mock_redis_client):
        """Test session expiration over time."""
        base_time = 1234567890
        
        with patch('time.time') as mock_time:
            # Create session at base time
            mock_time.return_value = base_time
            mock_uuid_patcher = patch('uuid.uuid4')
            with mock_uuid_patcher as mock_uuid:
                mock_uuid.return_value = MagicMock()
                mock_uuid.return_value.__str__ = MagicMock(return_value="time_test_session")
                
                session = await session_manager.create_upload_session(
                    filename="time_test.exe",
                    file_size=1024,
                    content_type="application/octet-stream",
                    ttl_seconds=3600  # 1 hour
                )
                
                assert session.expires_at == base_time + 3600
            
            # Check session 30 minutes later - should still be valid
            mock_time.return_value = base_time + 1800  # 30 minutes later
            session_data = session.to_dict()
            mock_redis_client.get.return_value = session_data
            
            retrieved_session = await session_manager.get_upload_session("time_test_session")
            assert retrieved_session is not None
            assert not retrieved_session.is_expired()
            
            # Check session 2 hours later - should be expired
            mock_time.return_value = base_time + 7200  # 2 hours later
            
            retrieved_session = await session_manager.get_upload_session("time_test_session")
            assert retrieved_session is None  # Should be None due to expiration
    
    @pytest.mark.asyncio
    async def test_temp_file_access_tracking(self, session_manager, mock_redis_client):
        """Test temporary file access tracking over time."""
        base_time = 1234567890
        
        # Create temp file
        temp_file = TempFileMetadata(
            file_id="access_test_file",
            original_filename="access_test.exe",
            stored_path="/tmp/access_test",
            file_size=2048,
            file_hash="access_test_hash",
            content_type="application/octet-stream",
            upload_session_id=None,
            api_key_id=None,
            created_at=base_time,
            expires_at=base_time + 86400,  # 24 hours
            access_count=0,
            last_accessed=None,
            tags=set()
        )
        
        with patch('time.time') as mock_time:
            # First access at base time
            mock_time.return_value = base_time
            temp_file_data = temp_file.to_dict()
            mock_redis_client.get.return_value = temp_file_data
            
            accessed_file = await session_manager.get_temp_file("access_test_file")
            assert accessed_file.access_count == 1
            assert accessed_file.last_accessed == base_time
            
            # Second access 1 hour later
            mock_time.return_value = base_time + 3600
            temp_file_data["access_count"] = 1
            temp_file_data["last_accessed"] = base_time
            mock_redis_client.get.return_value = temp_file_data
            
            accessed_file = await session_manager.get_temp_file("access_test_file")
            assert accessed_file.access_count == 2
            assert accessed_file.last_accessed == base_time + 3600
    
    @pytest.mark.asyncio
    async def test_cleanup_timing(self, session_manager, mock_redis_client):
        """Test cleanup operation timing and effectiveness."""
        base_time = 1234567890
        
        with patch('time.time') as mock_time:
            mock_time.return_value = base_time
            
            # Mock expired and active sessions
            expired_sessions = ["expired_1", "expired_2"]
            expired_files = ["expired_file_1", "expired_file_2", "expired_file_3"]
            
            # Mock the cleanup queries to return expired items
            mock_redis_client._client.zrangebyscore.side_effect = [
                expired_sessions,  # Expired sessions query
                expired_files      # Expired files query
            ]
            
            # Mock successful deletions
            session_manager.delete_upload_session = AsyncMock(return_value=True)
            session_manager.delete_temp_file = AsyncMock(return_value=True)
            
            # Run cleanup
            session_count = await session_manager.cleanup_expired_sessions()
            file_count = await session_manager.cleanup_expired_temp_files()
            
            assert session_count == 2
            assert file_count == 3
            
            # Verify cleanup queries used current time
            call_args_list = mock_redis_client._client.zrangebyscore.call_args_list
            for call_args in call_args_list:
                # Should query from 0 to current time (base_time)
                assert call_args[0][1] == 0  # Min score
                assert call_args[0][2] == base_time  # Max score (current time)
    
    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, session_manager, mock_redis_client):
        """Test concurrent session operations with time progression."""
        base_time = 1234567890
        
        with patch('time.time') as mock_time, patch('uuid.uuid4') as mock_uuid:
            mock_time.return_value = base_time
            
            # Create multiple sessions concurrently
            session_ids = []
            tasks = []
            
            for i in range(5):
                mock_uuid.return_value = MagicMock()
                mock_uuid.return_value.__str__ = MagicMock(return_value=f"concurrent_session_{i}")
                
                task = session_manager.create_upload_session(
                    filename=f"concurrent_test_{i}.exe",
                    file_size=1024 * (i + 1),
                    content_type="application/octet-stream",
                    api_key_id=f"api_key_{i}"
                )
                tasks.append(task)
                session_ids.append(f"concurrent_session_{i}")
            
            # Execute all creation tasks
            sessions = await asyncio.gather(*tasks)
            
            assert len(sessions) == 5
            assert all(session.created_at == base_time for session in sessions)
            
            # Simulate time passing and update some sessions
            mock_time.return_value = base_time + 1800  # 30 minutes later
            
            update_tasks = []
            for i in range(3):  # Update first 3 sessions
                session_data = sessions[i].to_dict()
                mock_redis_client.get.return_value = session_data
                
                task = session_manager.update_upload_session(
                    session_id=session_ids[i],
                    status=SessionStatus.UPLOADING,
                    upload_progress=50
                )
                update_tasks.append(task)
            
            # Execute all update tasks
            update_results = await asyncio.gather(*update_tasks)
            assert all(result is True for result in update_results)
    
    @pytest.mark.asyncio
    async def test_ttl_extension_scenario(self, session_manager, mock_redis_client):
        """Test scenario where session TTL needs to be extended."""
        base_time = 1234567890
        
        with patch('time.time') as mock_time, patch('uuid.uuid4') as mock_uuid:
            # Create session with short TTL
            mock_time.return_value = base_time
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="ttl_test_session")
            
            session = await session_manager.create_upload_session(
                filename="ttl_test.exe",
                file_size=1024,
                content_type="application/octet-stream",
                ttl_seconds=1800  # 30 minutes
            )
            
            assert session.expires_at == base_time + 1800
            
            # 25 minutes later, session is still valid but close to expiry
            mock_time.return_value = base_time + 1500
            assert session.ttl_seconds() == 300  # 5 minutes remaining
            
            # Create new session with same file (simulating re-upload)
            # This would typically extend the effective TTL
            mock_uuid.return_value.__str__ = MagicMock(return_value="ttl_extended_session")
            
            extended_session = await session_manager.create_upload_session(
                filename="ttl_test.exe",  # Same file
                file_size=1024,
                content_type="application/octet-stream",
                ttl_seconds=3600,  # 1 hour
                api_key_id="same_user"
            )
            
            # New session should have extended expiry
            assert extended_session.expires_at == base_time + 1500 + 3600