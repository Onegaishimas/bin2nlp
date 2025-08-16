"""
Unit tests for job queue system.

Tests job enqueueing, dequeuing, status tracking, and worker management
with mocked Redis operations.
"""

import asyncio
import json
import time
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.cache.job_queue import JobQueue, JobMetadata, JobProgress
from src.cache.base import RedisClient
from src.core.config import Settings
from src.core.exceptions import ProcessingException
from src.models.shared.enums import JobStatus


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client for job queue testing."""
    redis_mock = AsyncMock(spec=RedisClient)
    redis_mock._client = AsyncMock()
    
    # Mock basic Redis operations
    redis_mock._client.zadd = AsyncMock(return_value=1)
    redis_mock._client.zrange = AsyncMock(return_value=[])
    redis_mock._client.zrem = AsyncMock(return_value=1)
    redis_mock._client.zcard = AsyncMock(return_value=0)
    redis_mock._client.zrangebyscore = AsyncMock(return_value=[])
    redis_mock._client.hset = AsyncMock(return_value=1)
    redis_mock._client.hget = AsyncMock(return_value=None)
    redis_mock._client.hgetall = AsyncMock(return_value={})
    redis_mock._client.hdel = AsyncMock(return_value=1)
    redis_mock._client.hlen = AsyncMock(return_value=0)
    redis_mock._client.hincrby = AsyncMock(return_value=1)
    redis_mock._client.llen = AsyncMock(return_value=0)
    redis_mock._client.lpush = AsyncMock(return_value=1)
    redis_mock._client.srem = AsyncMock(return_value=1)
    redis_mock._client.eval = AsyncMock()
    
    # Mock pipeline operations
    redis_mock.pipeline = AsyncMock()
    mock_pipeline = AsyncMock()
    mock_pipeline.watch = AsyncMock()
    mock_pipeline.multi = AsyncMock()
    mock_pipeline.execute = AsyncMock(return_value=[True, True, True, 1, 1])
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=None)
    redis_mock.pipeline.return_value = mock_pipeline
    
    # Mock get/set operations
    redis_mock.get = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    
    return redis_mock


@pytest.fixture
def mock_settings():
    """Create mock settings for job queue testing."""
    settings = MagicMock(spec=Settings)
    settings.security = MagicMock()
    settings.security.default_rate_limit_per_minute = 60
    settings.security.default_rate_limit_per_day = 10000
    return settings


@pytest.fixture
def job_queue(mock_redis_client, mock_settings):
    """Create JobQueue instance with mocked dependencies."""
    queue = JobQueue(redis_client=mock_redis_client, settings=mock_settings)
    return queue


@pytest.fixture
def sample_job_metadata():
    """Create sample job metadata for testing."""
    return {
        "file_reference": "upload_123",
        "filename": "test.exe",
        "analysis_config": {
            "depth": "standard",
            "timeout_seconds": 300,
            "focus_areas": ["security", "functions"]
        },
        "priority": "normal",
        "callback_url": "https://api.client.com/webhooks/analysis",
        "submitted_by": "api_key_123",
        "correlation_id": "corr_456",
        "metadata": {"source": "api", "user": "test_user"}
    }


class TestJobMetadata:
    """Test cases for JobMetadata dataclass."""
    
    def test_job_metadata_creation(self):
        """Test JobMetadata creation and serialization."""
        job_metadata = JobMetadata(
            job_id="job_123",
            priority="high",
            file_reference="upload_456",
            filename="test.exe",
            analysis_config={"depth": "standard"},
            created_at=time.time(),
            submitted_by="api_key_123"
        )
        
        assert job_metadata.job_id == "job_123"
        assert job_metadata.priority == "high"
        assert job_metadata.file_reference == "upload_456"
        
        # Test serialization
        job_dict = job_metadata.to_dict()
        assert isinstance(job_dict, dict)
        assert job_dict["job_id"] == "job_123"
        
        # Test deserialization
        restored = JobMetadata.from_dict(job_dict)
        assert restored.job_id == job_metadata.job_id
        assert restored.priority == job_metadata.priority


class TestJobProgress:
    """Test cases for JobProgress dataclass."""
    
    def test_job_progress_creation(self):
        """Test JobProgress creation and serialization."""
        job_progress = JobProgress(
            job_id="job_123",
            status=JobStatus.PROCESSING,
            progress_percentage=45.5,
            current_stage="function_analysis",
            worker_id="worker_001",
            started_at=time.time(),
            updated_at=time.time()
        )
        
        assert job_progress.job_id == "job_123"
        assert job_progress.status == JobStatus.PROCESSING
        assert job_progress.progress_percentage == 45.5
        
        # Test serialization
        progress_dict = job_progress.to_dict()
        assert isinstance(progress_dict, dict)
        assert progress_dict["status"] == "processing"
        
        # Test deserialization
        restored = JobProgress.from_dict(progress_dict)
        assert restored.job_id == job_progress.job_id
        assert restored.status == job_progress.status
        assert isinstance(restored.status, JobStatus)


class TestJobQueue:
    """Test cases for JobQueue class."""
    
    def test_job_queue_initialization(self, mock_redis_client, mock_settings):
        """Test JobQueue initialization."""
        queue = JobQueue(redis_client=mock_redis_client, settings=mock_settings)
        
        assert queue.redis_client == mock_redis_client
        assert queue.settings == mock_settings
        assert queue.job_timeout_seconds == 3600
        assert queue.max_retries == 3
        assert len(queue.QUEUE_PRIORITIES) == 4
    
    @pytest.mark.asyncio
    async def test_enqueue_job_success(self, job_queue, mock_redis_client, sample_job_metadata):
        """Test successful job enqueueing."""
        # Mock UUID generation
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="job_123")
            
            job_id = await job_queue.enqueue_job(**sample_job_metadata)
            
            assert job_id == "job_123"
            
            # Verify Redis operations
            mock_redis_client._client.zadd.assert_called()
            mock_redis_client.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_enqueue_job_invalid_priority(self, job_queue, sample_job_metadata):
        """Test job enqueueing with invalid priority."""
        sample_job_metadata["priority"] = "invalid_priority"
        
        with pytest.raises(ProcessingException, match="Invalid priority"):
            await job_queue.enqueue_job(**sample_job_metadata)
    
    @pytest.mark.asyncio
    async def test_dequeue_job_success(self, job_queue, mock_redis_client):
        """Test successful job dequeuing."""
        # Mock job available in queue
        mock_redis_client._client.eval.return_value = "job_123"
        
        # Mock job metadata
        job_metadata_dict = {
            "job_id": "job_123",
            "priority": "normal",
            "file_reference": "upload_456",
            "filename": "test.exe",
            "analysis_config": {"depth": "standard"},
            "created_at": time.time()
        }
        mock_redis_client.get.return_value = json.dumps(job_metadata_dict)
        
        result = await job_queue.dequeue_job("worker_001")
        
        assert result is not None
        job_id, job_metadata = result
        assert job_id == "job_123"
        assert isinstance(job_metadata, JobMetadata)
        assert job_metadata.job_id == "job_123"
    
    @pytest.mark.asyncio
    async def test_dequeue_job_empty_queue(self, job_queue, mock_redis_client):
        """Test dequeuing from empty queue."""
        # Mock empty queue
        mock_redis_client._client.eval.return_value = None
        
        result = await job_queue.dequeue_job("worker_001")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_dequeue_job_missing_metadata(self, job_queue, mock_redis_client):
        """Test dequeuing job with missing metadata."""
        # Mock job available but no metadata
        mock_redis_client._client.eval.return_value = "job_123"
        mock_redis_client.get.return_value = None
        
        result = await job_queue.dequeue_job("worker_001")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_complete_job_success(self, job_queue, mock_redis_client):
        """Test successful job completion."""
        # Mock job in processing
        mock_redis_client._client.hget.return_value = "worker_001:1234567890"
        
        result = await job_queue.complete_job("job_123", "worker_001")
        
        assert result is True
        mock_redis_client._client.hdel.assert_called()
        mock_redis_client._client.hincrby.assert_called()
    
    @pytest.mark.asyncio
    async def test_complete_job_not_processing(self, job_queue, mock_redis_client):
        """Test completing job not in processing."""
        # Mock job not in processing
        mock_redis_client._client.hget.return_value = None
        
        result = await job_queue.complete_job("job_123", "worker_001")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_complete_job_wrong_worker(self, job_queue, mock_redis_client):
        """Test completing job with wrong worker."""
        # Mock job assigned to different worker
        mock_redis_client._client.hget.return_value = "worker_002:1234567890"
        
        result = await job_queue.complete_job("job_123", "worker_001")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_fail_job_with_retries(self, job_queue, mock_redis_client):
        """Test failing job with retries available."""
        # Mock job metadata with retry count
        job_metadata_dict = {
            "job_id": "job_123",
            "priority": "normal",
            "retry_count": 1
        }
        mock_redis_client.get.return_value = json.dumps(job_metadata_dict)
        
        result = await job_queue.fail_job("job_123", "worker_001", "Test error")
        
        assert result is True
        # Should be re-queued
        mock_redis_client._client.zadd.assert_called()
    
    @pytest.mark.asyncio
    async def test_fail_job_max_retries(self, job_queue, mock_redis_client):
        """Test failing job with max retries reached."""
        # Mock job metadata with max retries
        job_metadata_dict = {
            "job_id": "job_123",
            "priority": "normal",
            "retry_count": 3
        }
        mock_redis_client.get.return_value = json.dumps(job_metadata_dict)
        
        result = await job_queue.fail_job("job_123", "worker_001", "Test error")
        
        assert result is True
        # Should be moved to dead letter queue
        mock_redis_client._client.lpush.assert_called()
    
    @pytest.mark.asyncio
    async def test_update_job_progress_success(self, job_queue, mock_redis_client):
        """Test successful job progress update."""
        # Mock existing progress
        existing_progress = {
            "job_id": "job_123",
            "status": "pending",
            "progress_percentage": 0.0,
            "updated_at": time.time()
        }
        mock_redis_client.get.return_value = json.dumps(existing_progress)
        
        result = await job_queue.update_job_progress(
            job_id="job_123",
            status=JobStatus.PROCESSING,
            progress_percentage=50.0,
            current_stage="analysis"
        )
        
        assert result is True
        mock_redis_client.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_update_job_progress_new_job(self, job_queue, mock_redis_client):
        """Test updating progress for new job (no existing progress)."""
        # Mock no existing progress
        mock_redis_client.get.return_value = None
        
        result = await job_queue.update_job_progress(
            job_id="job_123",
            status=JobStatus.PROCESSING,
            progress_percentage=25.0
        )
        
        assert result is True
        mock_redis_client.set.assert_called()
    
    @pytest.mark.asyncio
    async def test_get_job_progress_success(self, job_queue, mock_redis_client):
        """Test successful job progress retrieval."""
        # Mock progress data
        progress_data = {
            "job_id": "job_123",
            "status": "processing",
            "progress_percentage": 75.0,
            "current_stage": "security_analysis",
            "worker_id": "worker_001",
            "updated_at": time.time()
        }
        mock_redis_client.get.return_value = json.dumps(progress_data)
        
        result = await job_queue.get_job_progress("job_123")
        
        assert result is not None
        assert isinstance(result, JobProgress)
        assert result.job_id == "job_123"
        assert result.status == JobStatus.PROCESSING
        assert result.progress_percentage == 75.0
    
    @pytest.mark.asyncio
    async def test_get_job_progress_not_found(self, job_queue, mock_redis_client):
        """Test job progress retrieval for non-existent job."""
        mock_redis_client.get.return_value = None
        
        result = await job_queue.get_job_progress("nonexistent_job")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_queue_stats_success(self, job_queue, mock_redis_client):
        """Test successful queue statistics retrieval."""
        # Mock statistics data
        mock_redis_client._client.hgetall.return_value = {
            "total_queued": "100",
            "processing": "5",
            "completed": "90",
            "failed": "5"
        }
        
        # Mock queue lengths
        mock_redis_client._client.zcard.return_value = 10
        mock_redis_client._client.hlen.return_value = 5
        mock_redis_client._client.llen.return_value = 2
        
        stats = await job_queue.get_queue_stats()
        
        assert isinstance(stats, dict)
        assert "queue_lengths" in stats
        assert "processing_jobs" in stats
        assert "dead_letter_jobs" in stats
        assert "statistics" in stats
        assert stats["processing_jobs"] == 5
        assert stats["dead_letter_jobs"] == 2
    
    @pytest.mark.asyncio
    async def test_cancel_job_success(self, job_queue, mock_redis_client):
        """Test successful job cancellation."""
        result = await job_queue.cancel_job("job_123")
        
        assert result is True
        # Should remove from all priority queues
        assert mock_redis_client._client.zrem.call_count >= 1
        # Should remove from processing
        mock_redis_client._client.hdel.assert_called()
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_jobs(self, job_queue, mock_redis_client):
        """Test cleanup of stale processing jobs."""
        # Mock stale job
        old_timestamp = time.time() - 7200  # 2 hours ago
        mock_redis_client._client.hgetall.return_value = {
            "job_123": f"worker_001:{old_timestamp}",
            "job_456": f"worker_002:invalid_format"
        }
        
        cleaned_count = await job_queue.cleanup_stale_jobs(stale_timeout=3600)
        
        assert cleaned_count >= 0
    
    @pytest.mark.asyncio
    async def test_queue_priorities(self, job_queue):
        """Test queue priority ordering."""
        priorities = job_queue.QUEUE_PRIORITIES
        
        assert priorities["urgent"] < priorities["high"]
        assert priorities["high"] < priorities["normal"]
        assert priorities["normal"] < priorities["low"]
    
    @pytest.mark.asyncio
    async def test_job_metadata_validation(self, job_queue):
        """Test job metadata validation during enqueueing."""
        # Test with missing required fields
        with pytest.raises(TypeError):
            await job_queue.enqueue_job(
                # Missing file_reference
                filename="test.exe",
                analysis_config={"depth": "standard"}
            )
    
    @pytest.mark.asyncio
    async def test_concurrent_dequeue_operations(self, job_queue, mock_redis_client):
        """Test that dequeue operations handle concurrency properly."""
        # Mock Lua script execution for atomic dequeue
        mock_redis_client._client.eval.side_effect = ["job_123", None, "job_124"]
        
        # Mock job metadata
        job_metadata_dict = {
            "job_id": "job_123",
            "priority": "normal",
            "file_reference": "upload_456",
            "filename": "test.exe",
            "analysis_config": {"depth": "standard"},
            "created_at": time.time()
        }
        mock_redis_client.get.return_value = json.dumps(job_metadata_dict)
        
        # First worker gets job
        result1 = await job_queue.dequeue_job("worker_001")
        assert result1 is not None
        
        # Second worker gets nothing (job already taken)
        result2 = await job_queue.dequeue_job("worker_002")
        assert result2 is None
    
    @pytest.mark.asyncio
    async def test_error_handling_redis_failure(self, job_queue, mock_redis_client):
        """Test error handling when Redis operations fail."""
        # Mock Redis failure
        mock_redis_client._client.eval.side_effect = Exception("Redis connection lost")
        
        with pytest.raises(ProcessingException, match="Failed to dequeue job"):
            await job_queue.dequeue_job("worker_001")
    
    @pytest.mark.asyncio
    async def test_job_priority_ordering(self, job_queue, mock_redis_client):
        """Test that jobs are dequeued in priority order."""
        # Mock different priority queues with jobs
        def mock_eval(script, num_keys, *args):
            queue_key = args[0]
            if "urgent" in queue_key:
                return "urgent_job"
            elif "high" in queue_key:
                return "high_job"
            elif "normal" in queue_key:
                return "normal_job"
            else:
                return None
        
        mock_redis_client._client.eval.side_effect = mock_eval
        
        # Mock job metadata
        job_metadata_dict = {
            "job_id": "urgent_job",
            "priority": "urgent",
            "file_reference": "upload_123",
            "filename": "urgent.exe",
            "analysis_config": {"depth": "quick"},
            "created_at": time.time()
        }
        mock_redis_client.get.return_value = json.dumps(job_metadata_dict)
        
        result = await job_queue.dequeue_job("worker_001")
        
        # Should get urgent job first
        assert result is not None
        job_id, job_metadata = result
        assert job_id == "urgent_job"
        assert job_metadata.priority == "urgent"


class TestJobQueueIntegration:
    """Integration-style tests for job queue workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_job_lifecycle(self, job_queue, mock_redis_client):
        """Test complete job lifecycle from enqueue to completion."""
        # 1. Enqueue job
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = MagicMock()
            mock_uuid.return_value.__str__ = MagicMock(return_value="job_123")
            
            job_id = await job_queue.enqueue_job(
                file_reference="upload_456",
                filename="test.exe",
                analysis_config={"depth": "standard"},
                priority="normal"
            )
            
            assert job_id == "job_123"
        
        # 2. Dequeue job
        mock_redis_client._client.eval.return_value = "job_123"
        job_metadata_dict = {
            "job_id": "job_123",
            "priority": "normal",
            "file_reference": "upload_456",
            "filename": "test.exe",
            "analysis_config": {"depth": "standard"},
            "created_at": time.time()
        }
        mock_redis_client.get.return_value = json.dumps(job_metadata_dict)
        
        result = await job_queue.dequeue_job("worker_001")
        assert result is not None
        
        # 3. Update progress
        progress_result = await job_queue.update_job_progress(
            job_id="job_123",
            status=JobStatus.PROCESSING,
            progress_percentage=50.0
        )
        assert progress_result is True
        
        # 4. Complete job
        mock_redis_client._client.hget.return_value = "worker_001:1234567890"
        complete_result = await job_queue.complete_job("job_123", "worker_001")
        assert complete_result is True
    
    @pytest.mark.asyncio
    async def test_job_failure_and_retry_cycle(self, job_queue, mock_redis_client):
        """Test job failure and retry workflow."""
        # Initial job metadata with no retries
        job_metadata_dict = {
            "job_id": "job_123",
            "priority": "normal",
            "retry_count": 0
        }
        mock_redis_client.get.return_value = json.dumps(job_metadata_dict)
        
        # First failure - should retry
        result = await job_queue.fail_job("job_123", "worker_001", "Temporary error")
        assert result is True
        
        # Job should be re-queued
        mock_redis_client._client.zadd.assert_called()
        
        # Update metadata to show retry
        job_metadata_dict["retry_count"] = 3  # Max retries reached
        mock_redis_client.get.return_value = json.dumps(job_metadata_dict)
        
        # Final failure - should go to dead letter queue
        result = await job_queue.fail_job("job_123", "worker_001", "Permanent error")
        assert result is True
        
        # Should be moved to dead letter queue
        mock_redis_client._client.lpush.assert_called()
    
    @pytest.mark.asyncio
    async def test_multiple_workers_different_priorities(self, job_queue, mock_redis_client):
        """Test multiple workers handling different priority jobs."""
        # Set up mock to return different jobs for different calls
        call_count = 0
        def mock_eval(script, num_keys, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "urgent_job"
            elif call_count == 2:
                return "normal_job"
            else:
                return None
        
        mock_redis_client._client.eval.side_effect = mock_eval
        
        # Mock metadata for different jobs
        def mock_get(key):
            if "urgent_job" in key:
                return json.dumps({
                    "job_id": "urgent_job",
                    "priority": "urgent",
                    "file_reference": "upload_1",
                    "filename": "urgent.exe",
                    "analysis_config": {"depth": "quick"},
                    "created_at": time.time()
                })
            elif "normal_job" in key:
                return json.dumps({
                    "job_id": "normal_job",
                    "priority": "normal",
                    "file_reference": "upload_2",
                    "filename": "normal.exe",
                    "analysis_config": {"depth": "standard"},
                    "created_at": time.time()
                })
            return None
        
        mock_redis_client.get.side_effect = mock_get
        
        # Worker 1 gets urgent job
        result1 = await job_queue.dequeue_job("worker_001")
        assert result1 is not None
        job_id1, metadata1 = result1
        assert job_id1 == "urgent_job"
        
        # Worker 2 gets normal job
        result2 = await job_queue.dequeue_job("worker_002")
        assert result2 is not None
        job_id2, metadata2 = result2
        assert job_id2 == "normal_job"