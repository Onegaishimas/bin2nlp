"""
Job queue system using PostgreSQL + File Storage for background analysis processing.

Provides priority-based job queuing, atomic job processing, worker assignment,
and status tracking for the binary analysis engine.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import uuid

from ..database.models import JobPriority
from ..models.shared.enums import JobStatus
from ..core.logging import get_logger


@dataclass
class JobMetadata:
    """Job metadata for queue management and tracking."""
    
    job_id: str
    priority: str
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
        return {
            'job_id': self.job_id,
            'priority': self.priority,
            'file_reference': self.file_reference,
            'filename': self.filename,
            'analysis_config': self.analysis_config,
            'created_at': self.created_at,
            'submitted_by': self.submitted_by,
            'callback_url': self.callback_url,
            'correlation_id': self.correlation_id,
            'metadata': self.metadata or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobMetadata':
        """Create from dictionary."""
        return cls(
            job_id=data['job_id'],
            priority=data['priority'],
            file_reference=data['file_reference'],
            filename=data['filename'],
            analysis_config=data['analysis_config'],
            created_at=data['created_at'],
            submitted_by=data.get('submitted_by'),
            callback_url=data.get('callback_url'),
            correlation_id=data.get('correlation_id'),
            metadata=data.get('metadata')
        )


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
        return {
            'job_id': self.job_id,
            'status': self.status.value if isinstance(self.status, JobStatus) else self.status,
            'progress_percentage': self.progress_percentage,
            'current_stage': self.current_stage,
            'worker_id': self.worker_id,
            'started_at': self.started_at,
            'updated_at': self.updated_at,
            'estimated_completion_seconds': self.estimated_completion_seconds,
            'error_message': self.error_message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobProgress':
        """Create from dictionary."""
        # Handle enum conversion
        status = data.get('status')
        if isinstance(status, str):
            status = JobStatus(status)
        
        return cls(
            job_id=data['job_id'],
            status=status,
            progress_percentage=data.get('progress_percentage', 0.0),
            current_stage=data.get('current_stage'),
            worker_id=data.get('worker_id'),
            started_at=data.get('started_at'),
            updated_at=data.get('updated_at', 0.0),
            estimated_completion_seconds=data.get('estimated_completion_seconds'),
            error_message=data.get('error_message')
        )


class JobQueue:
    """
    PostgreSQL + File Storage job queue with priority support and atomic operations.
    
    Uses PostgreSQL for job metadata, queuing, and state management.
    Uses file storage for large result payloads.
    
    Features:
    - Priority-based job queuing (urgent > high > normal > low)
    - Atomic job dequeuing with worker assignment
    - Job status tracking and progress updates
    - Worker heartbeat monitoring
    - Queue statistics and monitoring
    """
    
    # Queue priorities
    QUEUE_PRIORITIES = {
        "urgent": 0,
        "high": 1,
        "normal": 2,
        "low": 3
    }
    
    def __init__(self):
        """Initialize job queue with database backend."""
        # Delayed import to avoid circular dependency
        from ..database.operations import JobQueue as DatabaseJobQueue
        self.db_queue = DatabaseJobQueue()
        self.logger = get_logger(__name__)
        
        # Queue configuration
        self.job_timeout_seconds = 3600  # 1 hour default
        self.heartbeat_interval = 30  # 30 seconds
        self.worker_timeout = 300  # 5 minutes
        self.max_retries = 3
    
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
        """
        return await self.db_queue.enqueue_job(
            file_reference=file_reference,
            filename=filename,
            analysis_config=analysis_config,
            priority=priority,
            callback_url=callback_url,
            submitted_by=submitted_by,
            correlation_id=correlation_id,
            metadata=metadata
        )
    
    async def dequeue_job(self, worker_id: str, timeout: int = 30) -> Optional[Tuple[str, JobMetadata]]:
        """
        Atomically dequeue the next highest priority job.
        
        Args:
            worker_id: Unique worker identifier
            timeout: Timeout in seconds (unused in PostgreSQL implementation)
            
        Returns:
            Tuple of (job_id, JobMetadata) or None if no jobs available
        """
        result = await self.db_queue.dequeue_job(worker_id)
        
        if result is None:
            return None
        
        job_id, job_data = result
        
        # Convert to JobMetadata
        job_metadata = JobMetadata(
            job_id=job_data['job_id'],
            priority=job_data['priority'],
            file_reference=job_data['file_reference'],
            filename=job_data['filename'],
            analysis_config=job_data['analysis_config'],
            created_at=0.0,  # Will be set from database if needed
            metadata=job_data.get('metadata', {})
        )
        
        return job_id, job_metadata
    
    async def complete_job(self, job_id: str, worker_id: str, result_data: Any = None) -> bool:
        """
        Mark job as completed.
        
        Args:
            job_id: Job ID
            worker_id: Worker ID
            result_data: Job result data (optional for compatibility)
            
        Returns:
            True if successful
        """
        # If result_data is provided, store it, otherwise assume it's already stored
        if result_data is not None:
            return await self.db_queue.complete_job(job_id, worker_id, result_data)
        else:
            # Just update status without storing new result data
            return await self.db_queue.complete_job(job_id, worker_id, {})
    
    async def fail_job(self, job_id: str, worker_id: str, error_message: str) -> bool:
        """
        Mark job as failed.
        
        Args:
            job_id: Job ID
            worker_id: Worker ID
            error_message: Error description
            
        Returns:
            True if successful
        """
        return await self.db_queue.fail_job(job_id, worker_id, error_message)
    
    async def update_job_progress(
        self,
        job_id: str,
        worker_id: str,
        progress_percentage: float,
        current_stage: Optional[str] = None,
        estimated_completion_seconds: Optional[int] = None
    ) -> bool:
        """
        Update job progress.
        
        Args:
            job_id: Job ID
            worker_id: Worker ID
            progress_percentage: Progress percentage (0-100)
            current_stage: Current processing stage
            estimated_completion_seconds: Estimated time to completion
            
        Returns:
            True if successful
        """
        return await self.db_queue.update_job_progress(
            job_id=job_id,
            worker_id=worker_id,
            progress_percentage=progress_percentage,
            current_stage=current_stage,
            estimated_completion_seconds=estimated_completion_seconds
        )
    
    async def get_job_progress(self, job_id: str) -> Optional[JobProgress]:
        """
        Get job progress information.
        
        Args:
            job_id: Job ID
            
        Returns:
            JobProgress or None if not found
        """
        job_status = await self.db_queue.get_job_status(job_id)
        
        if not job_status:
            return None
        
        # Convert database result to JobProgress
        return JobProgress(
            job_id=job_id,
            status=JobStatus(job_status['status']),
            progress_percentage=job_status.get('progress_percentage', 0.0),
            current_stage=job_status.get('current_stage'),
            worker_id=job_status.get('worker_id'),
            started_at=job_status.get('started_at'),
            updated_at=job_status.get('updated_at'),
            estimated_completion_seconds=job_status.get('estimated_completion_seconds'),
            error_message=job_status.get('error_message')
        )
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        return await self.db_queue.get_queue_stats()
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or in-progress job.
        
        Args:
            job_id: Job ID
            
        Returns:
            True if successful
        """
        try:
            from ..database.connection import get_database
            
            db = await get_database()
            
            # Only cancel jobs that are pending or in progress
            rows_updated = await db.execute("""
                UPDATE jobs 
                SET status = 'cancelled', 
                    updated_at = NOW()
                WHERE id = :job_id 
                AND status IN ('pending', 'in_progress')
            """, {"job_id": job_id})
            
            return rows_updated > 0
            
        except Exception as e:
            self.logger.error(
                "Failed to cancel job",
                extra={"error": str(e), "job_id": job_id}
            )
            return False
    
    async def cleanup_stale_jobs(self, stale_timeout: int = 3600) -> int:
        """
        Clean up jobs that have been in progress for too long.
        
        Args:
            stale_timeout: Timeout in seconds to consider a job stale
            
        Returns:
            Number of jobs cleaned up
        """
        try:
            from ..database.connection import get_database
            
            db = await get_database()
            
            # Mark stale jobs as failed
            rows_updated = await db.execute("""
                UPDATE jobs 
                SET status = 'failed',
                    error_message = 'Job timed out - worker may have crashed',
                    updated_at = NOW()
                WHERE status = 'in_progress'
                AND started_at < NOW() - INTERVAL '%s seconds'
            """ % stale_timeout)
            
            if rows_updated > 0:
                self.logger.info(
                    "Cleaned up stale jobs",
                    extra={"stale_jobs_count": rows_updated, "timeout_seconds": stale_timeout}
                )
            
            return rows_updated
            
        except Exception as e:
            self.logger.error(
                "Failed to cleanup stale jobs",
                extra={"error": str(e)}
            )
            return 0


