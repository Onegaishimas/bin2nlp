"""
Job queue system using Redis for background analysis processing.

Provides priority-based job queuing, atomic job processing, worker assignment,
and status tracking for the binary analysis engine.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator
from dataclasses import dataclass, asdict

from ..core.config import Settings, get_settings
from ..core.exceptions import ProcessingException, CacheException
from ..core.logging import get_logger
from ..models.shared.enums import JobStatus
from .base import RedisClient


@dataclass
class JobMetadata:
    """Job metadata for queue management and tracking."""
    
    job_id: str
    priority: str  # "low", "normal", "high", "urgent"
    file_reference: str
    filename: str
    analysis_config: Dict[str, Any]
    created_at: float
    submitted_by: Optional[str] = None
    callback_url: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobMetadata':
        """Create from dictionary."""
        return cls(**data)


@dataclass 
class JobProgress:
    """Job progress tracking information."""
    
    job_id: str
    status: JobStatus
    progress_percentage: float = 0.0
    current_stage: Optional[str] = None
    worker_id: Optional[str] = None
    started_at: Optional[float] = None
    updated_at: float = 0.0
    estimated_completion_seconds: Optional[int] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobProgress':
        """Create from dictionary."""
        # Handle enum conversion
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = JobStatus(data['status'])
        return cls(**data)


class JobQueue:
    """
    Redis-based job queue with priority support and atomic operations.
    
    Features:
    - Priority-based job queuing (urgent > high > normal > low)
    - Atomic job dequeuing with worker assignment
    - Job status tracking and progress updates
    - Dead letter queue for failed jobs
    - Worker heartbeat monitoring
    - Queue statistics and monitoring
    """
    
    # Queue names by priority
    QUEUE_PRIORITIES = {
        "urgent": 0,
        "high": 1,
        "normal": 2,
        "low": 3
    }
    
    # Redis key patterns
    JOB_QUEUE_KEY = "queue:jobs:{priority}"
    JOB_PROCESSING_KEY = "queue:processing"
    JOB_STATUS_KEY = "job:status:{job_id}"
    JOB_METADATA_KEY = "job:metadata:{job_id}"
    JOB_PROGRESS_KEY = "job:progress:{job_id}"
    WORKER_HEARTBEAT_KEY = "worker:heartbeat:{worker_id}"
    QUEUE_STATS_KEY = "queue:stats"
    DEAD_LETTER_KEY = "queue:dead_letter"
    
    def __init__(self, redis_client: Optional[RedisClient] = None, settings: Optional[Settings] = None):
        """
        Initialize job queue.
        
        Args:
            redis_client: Redis client instance
            settings: Application settings
        """
        self.redis_client = redis_client
        self.settings = settings or get_settings()
        self.logger = get_logger(__name__)
        
        # Queue configuration
        self.job_timeout_seconds = 3600  # 1 hour default
        self.heartbeat_interval = 30  # 30 seconds
        self.worker_timeout = 300  # 5 minutes
        self.max_retries = 3
    
    async def _get_redis(self) -> RedisClient:
        """Get Redis client instance."""
        if self.redis_client is None:
            from .base import get_redis_client
            self.redis_client = await get_redis_client()
        return self.redis_client
    
    async def enqueue_job(
        self,
        file_reference: str,
        filename: str,
        analysis_config: Dict[str, Any],
        priority: str = "normal",
        callback_url: Optional[str] = None,
        submitted_by: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add a job to the priority queue.
        
        Args:
            file_reference: Reference to uploaded file or file hash
            filename: Original filename
            analysis_config: Analysis configuration parameters
            priority: Job priority (urgent, high, normal, low)
            callback_url: Optional webhook URL for completion notification
            submitted_by: API key or user identifier
            correlation_id: Request correlation ID
            metadata: Additional job metadata
            
        Returns:
            str: Job ID
            
        Raises:
            ProcessingException: If job enqueueing fails
        """
        if priority not in self.QUEUE_PRIORITIES:
            raise ProcessingException(
                f"Invalid priority: {priority}",
                queue_name="job_queue",
                processing_stage="enqueue"
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        current_time = time.time()
        
        try:
            redis = await self._get_redis()
            
            # Create job metadata
            job_metadata = JobMetadata(
                job_id=job_id,
                priority=priority,
                file_reference=file_reference,
                filename=filename,
                analysis_config=analysis_config,
                created_at=current_time,
                submitted_by=submitted_by,
                callback_url=callback_url,
                correlation_id=correlation_id,
                metadata=metadata or {}
            )
            
            # Create initial job progress
            job_progress = JobProgress(
                job_id=job_id,
                status=JobStatus.PENDING,
                updated_at=current_time
            )
            
            # Store job data directly (simplified for now)
            # Store job metadata
            await redis.set(
                self.JOB_METADATA_KEY.format(job_id=job_id),
                json.dumps(job_metadata.to_dict()),
                ttl=86400  # 24 hour TTL
            )
            
            # Store job progress
            await redis.set(
                self.JOB_PROGRESS_KEY.format(job_id=job_id),
                json.dumps(job_progress.to_dict()),
                ttl=86400  # 24 hour TTL
            )
            
            # Add to priority queue (use timestamp as score for FIFO within priority)
            await redis._client.zadd(
                self.JOB_QUEUE_KEY.format(priority=priority),
                {job_id: current_time}
            )
            
            # Update queue statistics
            await redis._client.hincrby(self.QUEUE_STATS_KEY, f"queued_{priority}", 1)
            await redis._client.hincrby(self.QUEUE_STATS_KEY, "total_queued", 1)
            
            self.logger.info(
                "Job enqueued successfully",
                extra={
                    "job_id": job_id,
                    "priority": priority,
                    "filename": filename,
                    "correlation_id": correlation_id
                }
            )
            
            return job_id
            
        except Exception as e:
            self.logger.error(
                "Failed to enqueue job",
                extra={
                    "error": str(e),
                    "priority": priority,
                    "filename": filename,
                    "correlation_id": correlation_id
                }
            )
            raise ProcessingException(
                f"Failed to enqueue job: {e}",
                queue_name="job_queue",
                processing_stage="enqueue"
            )
    
    async def dequeue_job(self, worker_id: str, timeout: int = 30) -> Optional[Tuple[str, JobMetadata]]:
        """
        Dequeue the highest priority job atomically.
        
        Args:
            worker_id: Unique worker identifier
            timeout: Blocking timeout in seconds
            
        Returns:
            Tuple of (job_id, job_metadata) or None if no jobs available
            
        Raises:
            ProcessingException: If job dequeuing fails
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            
            # Try each priority level in order
            for priority in sorted(self.QUEUE_PRIORITIES.keys(), key=lambda p: self.QUEUE_PRIORITIES[p]):
                queue_key = self.JOB_QUEUE_KEY.format(priority=priority)
                
                # Use Lua script for atomic dequeue operation
                lua_script = """
                local queue_key = KEYS[1]
                local processing_key = KEYS[2]
                local worker_id = ARGV[1]
                local current_time = tonumber(ARGV[2])
                
                -- Get the oldest job from this priority queue
                local jobs = redis.call('ZRANGE', queue_key, 0, 0, 'WITHSCORES')
                if #jobs == 0 then
                    return nil
                end
                
                local job_id = jobs[1]
                
                -- Remove from queue and add to processing set
                redis.call('ZREM', queue_key, job_id)
                redis.call('HSET', processing_key, job_id, worker_id .. ':' .. current_time)
                
                return job_id
                """
                
                job_id = await redis._client.eval(
                    lua_script,
                    2,
                    queue_key,
                    self.JOB_PROCESSING_KEY,
                    worker_id,
                    current_time
                )
                
                if job_id:
                    # Get job metadata
                    metadata_key = self.JOB_METADATA_KEY.format(job_id=job_id)
                    metadata_json = await redis.get(metadata_key)
                    
                    if not metadata_json:
                        self.logger.error(
                            "Job metadata not found",
                            extra={"job_id": job_id}
                        )
                        # Remove from processing set
                        await redis.delete(f"{self.JOB_PROCESSING_KEY}:{job_id}")
                        continue
                    
                    try:
                        metadata_dict = json.loads(metadata_json)
                        job_metadata = JobMetadata.from_dict(metadata_dict)
                        
                        # Update job progress to processing
                        await self.update_job_progress(
                            job_id=job_id,
                            status=JobStatus.PROCESSING,
                            worker_id=worker_id,
                            started_at=current_time
                        )
                        
                        # Update queue statistics
                        await redis._client.hincrby(self.QUEUE_STATS_KEY, f"queued_{priority}", -1)
                        await redis._client.hincrby(self.QUEUE_STATS_KEY, "processing", 1)
                        
                        self.logger.info(
                            "Job dequeued successfully",
                            extra={
                                "job_id": job_id,
                                "worker_id": worker_id,
                                "priority": priority,
                                "filename": job_metadata.filename
                            }
                        )
                        
                        return job_id, job_metadata
                        
                    except (json.JSONDecodeError, TypeError) as e:
                        self.logger.error(
                            "Failed to parse job metadata",
                            extra={"job_id": job_id, "error": str(e)}
                        )
                        continue
            
            # No jobs available
            return None
            
        except Exception as e:
            self.logger.error(
                "Failed to dequeue job",
                extra={"worker_id": worker_id, "error": str(e)}
            )
            raise ProcessingException(
                f"Failed to dequeue job: {e}",
                worker_id=worker_id,
                queue_name="job_queue",
                processing_stage="dequeue"
            )
    
    async def complete_job(self, job_id: str, worker_id: str) -> bool:
        """
        Mark a job as completed and remove from processing.
        
        Args:
            job_id: Job identifier
            worker_id: Worker that completed the job
            
        Returns:
            bool: True if job was marked as completed
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            
            # Remove from processing set (if it exists)
            processing_info = await redis._client.hget(self.JOB_PROCESSING_KEY, job_id)
            if not processing_info:
                # Job not in processing hash - this is OK for FastAPI BackgroundTasks pattern
                self.logger.info(
                    "Job not in processing hash - likely using BackgroundTasks pattern",
                    extra={"job_id": job_id, "worker_id": worker_id}
                )
            elif not processing_info.startswith(worker_id):
                self.logger.warning(
                    "Job being completed by different worker",
                    extra={"job_id": job_id, "worker_id": worker_id, "processing_worker": processing_info}
                )
                # Still allow completion but log the mismatch
            
            # Update job progress
            await self.update_job_progress(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                progress_percentage=100.0,
                updated_at=current_time
            )
            
            # Remove from processing (if it was there)
            removed_count = await redis._client.hdel(self.JOB_PROCESSING_KEY, job_id)
            
            # Update statistics - only decrement processing if job was actually there
            if removed_count > 0:
                await redis._client.hincrby(self.QUEUE_STATS_KEY, "processing", -1)
            await redis._client.hincrby(self.QUEUE_STATS_KEY, "completed", 1)
            
            self.logger.info(
                "Job completed successfully",
                extra={"job_id": job_id, "worker_id": worker_id}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to complete job",
                extra={"job_id": job_id, "worker_id": worker_id, "error": str(e)}
            )
            return False
    
    async def fail_job(self, job_id: str, worker_id: str, error_message: str) -> bool:
        """
        Mark a job as failed and handle retry logic.
        
        Args:
            job_id: Job identifier
            worker_id: Worker that failed the job
            error_message: Failure reason
            
        Returns:
            bool: True if job was marked as failed
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            
            # Get current job metadata to check retry count
            metadata_key = self.JOB_METADATA_KEY.format(job_id=job_id)
            metadata_json = await redis.get(metadata_key)
            
            if metadata_json:
                metadata_dict = json.loads(metadata_json)
                retry_count = metadata_dict.get('retry_count', 0)
                
                if retry_count < self.max_retries:
                    # Retry the job
                    metadata_dict['retry_count'] = retry_count + 1
                    priority = metadata_dict['priority']
                    
                    # Re-enqueue with delay
                    delay_seconds = (retry_count + 1) * 60  # Exponential backoff
                    
                    await redis.set(metadata_key, json.dumps(metadata_dict))
                    await redis._client.zadd(
                        self.JOB_QUEUE_KEY.format(priority=priority),
                        {job_id: current_time + delay_seconds}
                    )
                    
                    # Update progress
                    await self.update_job_progress(
                        job_id=job_id,
                        status=JobStatus.PENDING,
                        error_message=f"Retry {retry_count + 1}/{self.max_retries}: {error_message}",
                        updated_at=current_time
                    )
                    
                    self.logger.info(
                        "Job queued for retry",
                        extra={
                            "job_id": job_id,
                            "retry_count": retry_count + 1,
                            "delay_seconds": delay_seconds
                        }
                    )
                else:
                    # Max retries reached, mark as failed
                    await self.update_job_progress(
                        job_id=job_id,
                        status=JobStatus.FAILED,
                        error_message=error_message,
                        updated_at=current_time
                    )
                    
                    # Move to dead letter queue
                    await redis._client.lpush(
                        self.DEAD_LETTER_KEY,
                        json.dumps({
                            'job_id': job_id,
                            'failed_at': current_time,
                            'error_message': error_message,
                            'retry_count': retry_count
                        })
                    )
                    
                    await redis._client.hincrby(self.QUEUE_STATS_KEY, "failed", 1)
                    
                    self.logger.error(
                        "Job failed after max retries",
                        extra={"job_id": job_id, "error_message": error_message}
                    )
            
            # Remove from processing
            await redis._client.hdel(self.JOB_PROCESSING_KEY, job_id)
            await redis._client.hincrby(self.QUEUE_STATS_KEY, "processing", -1)
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to fail job",
                extra={"job_id": job_id, "worker_id": worker_id, "error": str(e)}
            )
            return False
    
    async def update_job_progress(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress_percentage: Optional[float] = None,
        current_stage: Optional[str] = None,
        worker_id: Optional[str] = None,
        started_at: Optional[float] = None,
        updated_at: Optional[float] = None,
        estimated_completion_seconds: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update job progress information.
        
        Args:
            job_id: Job identifier
            status: New job status
            progress_percentage: Completion percentage (0-100)
            current_stage: Current processing stage
            worker_id: Worker processing the job
            started_at: Job start timestamp
            updated_at: Update timestamp
            estimated_completion_seconds: Estimated time to completion
            error_message: Error message if applicable
            
        Returns:
            bool: True if progress was updated
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            
            # Get current progress
            progress_key = self.JOB_PROGRESS_KEY.format(job_id=job_id)
            progress_json = await redis.get(progress_key)
            
            if progress_json:
                progress_dict = json.loads(progress_json)
                job_progress = JobProgress.from_dict(progress_dict)
            else:
                job_progress = JobProgress(job_id=job_id, status=JobStatus.PENDING)
            
            # Update fields
            if status is not None:
                job_progress.status = status
            if progress_percentage is not None:
                job_progress.progress_percentage = max(0, min(100, progress_percentage))
            if current_stage is not None:
                job_progress.current_stage = current_stage
            if worker_id is not None:
                job_progress.worker_id = worker_id
            if started_at is not None:
                job_progress.started_at = started_at
            if estimated_completion_seconds is not None:
                job_progress.estimated_completion_seconds = estimated_completion_seconds
            if error_message is not None:
                job_progress.error_message = error_message
            
            job_progress.updated_at = updated_at or current_time
            
            # Store updated progress
            await redis.set(
                progress_key,
                json.dumps(job_progress.to_dict()),
                ttl=86400  # 24 hour TTL
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to update job progress",
                extra={"job_id": job_id, "error": str(e)}
            )
            return False
    
    async def get_job_progress(self, job_id: str) -> Optional[JobProgress]:
        """
        Get current job progress information.
        
        Args:
            job_id: Job identifier
            
        Returns:
            JobProgress object or None if not found
        """
        try:
            redis = await self._get_redis()
            progress_key = self.JOB_PROGRESS_KEY.format(job_id=job_id)
            progress_json = await redis.get(progress_key)
            
            if progress_json:
                progress_dict = json.loads(progress_json)
                return JobProgress.from_dict(progress_dict)
            
            return None
            
        except Exception as e:
            self.logger.error(
                "Failed to get job progress",
                extra={"job_id": job_id, "error": str(e)}
            )
            return None
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics and health information.
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            redis = await self._get_redis()
            
            # Get basic stats
            stats = await redis._client.hgetall(self.QUEUE_STATS_KEY) or {}
            
            # Get queue lengths by priority
            queue_lengths = {}
            for priority in self.QUEUE_PRIORITIES.keys():
                queue_key = self.JOB_QUEUE_KEY.format(priority=priority)
                length = await redis._client.zcard(queue_key)
                queue_lengths[f"queue_{priority}"] = length
            
            # Get processing jobs count
            processing_count = await redis._client.hlen(self.JOB_PROCESSING_KEY)
            
            # Get dead letter queue size
            dead_letter_count = await redis._client.llen(self.DEAD_LETTER_KEY)
            
            return {
                "queue_lengths": queue_lengths,
                "processing_jobs": processing_count,
                "dead_letter_jobs": dead_letter_count,
                "statistics": {
                    k: int(v) if v.isdigit() else v 
                    for k, v in stats.items()
                },
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(
                "Failed to get queue stats",
                extra={"error": str(e)}
            )
            return {}
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a queued or processing job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            bool: True if job was cancelled
        """
        try:
            redis = await self._get_redis()
            
            # Remove from all priority queues
            for priority in self.QUEUE_PRIORITIES.keys():
                queue_key = self.JOB_QUEUE_KEY.format(priority=priority)
                await redis._client.zrem(queue_key, job_id)
            
            # Remove from processing
            await redis._client.hdel(self.JOB_PROCESSING_KEY, job_id)
            
            # Update progress
            await self.update_job_progress(
                job_id=job_id,
                status=JobStatus.CANCELLED,
                updated_at=time.time()
            )
            
            self.logger.info(
                "Job cancelled",
                extra={"job_id": job_id}
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Failed to cancel job",
                extra={"job_id": job_id, "error": str(e)}
            )
            return False
    
    async def cleanup_stale_jobs(self, stale_timeout: int = 3600) -> int:
        """
        Clean up stale processing jobs (worker timeout).
        
        Args:
            stale_timeout: Timeout in seconds for stale jobs
            
        Returns:
            int: Number of stale jobs cleaned up
        """
        try:
            redis = await self._get_redis()
            current_time = time.time()
            cleaned_count = 0
            
            # Get all processing jobs
            processing_jobs = await redis._client.hgetall(self.JOB_PROCESSING_KEY)
            
            for job_id, worker_info in processing_jobs.items():
                try:
                    worker_id, start_time_str = worker_info.split(':', 1)
                    start_time = float(start_time_str)
                    
                    if current_time - start_time > stale_timeout:
                        # Job is stale, requeue it
                        await self.fail_job(
                            job_id=job_id,
                            worker_id=worker_id,
                            error_message=f"Job timeout after {stale_timeout} seconds"
                        )
                        cleaned_count += 1
                        
                except (ValueError, IndexError):
                    # Invalid worker info format, clean it up
                    await redis._client.hdel(self.JOB_PROCESSING_KEY, job_id)
                    cleaned_count += 1
            
            if cleaned_count > 0:
                self.logger.info(
                    "Cleaned up stale jobs",
                    extra={"cleaned_count": cleaned_count}
                )
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup stale jobs",
                extra={"error": str(e)}
            )
            return 0