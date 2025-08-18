"""
API models for job management endpoints.

Provides request/response models for job creation, status checking,
job listing, and job management operations.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field, ConfigDict
from typing_extensions import Annotated

from ..shared.base import BaseModel
from ..shared.enums import JobStatus, AnalysisDepth, AnalysisFocus, Platform, FileFormat
from ..analysis.serialization import AnalysisModelMixin, validate_string_list


class JobCreationRequest(BaseModel, AnalysisModelMixin):
    """
    Request model for creating a new analysis job.
    
    Used by job management endpoints to queue analysis tasks
    with specific configuration and metadata.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Job Creation Request",
            "description": "Request to create a new analysis job with configuration and scheduling options",
            "examples": [
                {
                    "job_type": "binary_analysis",
                    "file_reference": "upload://abc123def456",
                    "filename": "malware_sample.exe",
                    "priority": "high",
                    "analysis_config": {
                        "analysis_depth": "comprehensive",
                        "focus_areas": ["security", "functions"]
                    },
                    "callback_url": "https://api.example.com/webhook",
                    "metadata": {
                        "source": "threat_intel",
                        "case_id": "TI-2024-001"
                    },
                    "tags": ["malware", "threat-intel"]
                },
                {
                    "job_type": "file_validation",
                    "file_reference": "/uploads/sample.dll",
                    "filename": "library.dll",
                    "priority": "normal",
                    "max_retries": 2,
                    "timeout_seconds": 600,
                    "dependencies": ["job-abc123"],
                    "batch_id": "batch-2024-001"
                }
            ]
        }
    )
    
    job_type: str = Field(
        default="binary_analysis",
        pattern="^(binary_analysis|file_validation|bulk_analysis)$",
        description="Type of job to create"
    )
    
    file_reference: Annotated[str, Field(
        description="Reference to the file to be analyzed. Supports: file://, upload://, http://, https://, or absolute paths",
        examples=["upload://abc123def456", "file:///tmp/sample.exe", "https://example.com/malware.bin"]
    )]
    
    filename: str = Field(
        description="Name of the file being analyzed"
    )
    
    priority: Annotated[str, Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
        description="Job priority level. Higher priority jobs are processed first",
        examples=["low", "normal", "high", "urgent"]
    )]
    
    analysis_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Analysis configuration parameters"
    )
    
    scheduled_time: Optional[datetime] = Field(
        default=None,
        description="Schedule job for future execution"
    )
    
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts"
    )
    
    timeout_seconds: Optional[int] = Field(
        default=None,
        ge=30,
        le=7200,
        description="Job timeout in seconds"
    )
    
    callback_url: Optional[str] = Field(
        default=None,
        description="URL to receive job completion notification"
    )
    
    callback_events: List[str] = Field(
        default_factory=lambda: ["completed", "failed"],
        description="Events that trigger callback notifications"
    )
    
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracking related jobs"
    )
    
    batch_id: Optional[str] = Field(
        default=None,
        description="Batch ID for grouping related jobs"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing and filtering jobs"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the job"
    )
    
    dependencies: List[str] = Field(
        default_factory=list,
        description="List of job IDs this job depends on"
    )
    
    @field_validator('file_reference')
    @classmethod
    def validate_file_reference(cls, v: str) -> str:
        """Validate file reference format."""
        if not v or not v.strip():
            raise ValueError("File reference cannot be empty")
        
        v = v.strip()
        valid_prefixes = ['file://', 'upload://', 'http://', 'https://', '/']
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            if not v.startswith('/'):
                raise ValueError("Invalid file reference format")
        
        return v
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename."""
        v = v.strip()
        if not v:
            raise ValueError("Filename cannot be empty")
        
        if len(v) > 255:
            raise ValueError("Filename too long")
        
        return v
    
    @field_validator('callback_url')
    @classmethod
    def validate_callback_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate callback URL format."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
        
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("Callback URL must start with http:// or https://")
        
        return v
    
    @field_validator('callback_events')
    @classmethod
    def validate_callback_events(cls, v: List[str]) -> List[str]:
        """Validate callback events."""
        valid_events = ['created', 'started', 'progress', 'completed', 'failed', 'cancelled']
        validated = []
        
        for event in v:
            if event in valid_events and event not in validated:
                validated.append(event)
        
        if not validated:
            return ['completed', 'failed']  # Default events
        
        return validated
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        return validate_string_list(v, max_items=20)
    
    @field_validator('dependencies')
    @classmethod
    def validate_dependencies(cls, v: List[str]) -> List[str]:
        """Validate job dependencies."""
        if len(v) > 10:
            raise ValueError("Too many dependencies (max 10)")
        
        validated = []
        for dep in v:
            if isinstance(dep, str) and dep.strip():
                dep_clean = dep.strip()
                if dep_clean not in validated:
                    validated.append(dep_clean)
        
        return validated
    
    @field_validator('scheduled_time')
    @classmethod
    def validate_scheduled_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate scheduled time is in the future."""
        if v is not None and v <= datetime.now():
            raise ValueError("Scheduled time must be in the future")
        
        return v
    
    @computed_field
    @property
    def is_scheduled(self) -> bool:
        """Check if job is scheduled for future execution."""
        return self.scheduled_time is not None
    
    @computed_field
    @property
    def has_dependencies(self) -> bool:
        """Check if job has dependencies."""
        return len(self.dependencies) > 0
    
    @computed_field
    @property
    def is_batch_job(self) -> bool:
        """Check if job is part of a batch."""
        return self.batch_id is not None
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "job_type": self.job_type,
            "filename": self.filename,
            "priority": self.priority,
            "is_scheduled": self.is_scheduled,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "has_dependencies": self.has_dependencies,
            "dependency_count": len(self.dependencies),
            "is_batch_job": self.is_batch_job,
            "batch_id": self.batch_id,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "has_callback": self.callback_url is not None,
            "tag_count": len(self.tags),
            "metadata_fields": len(self.metadata)
        }


class JobStatusResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for job status information.
    
    Returned by job status endpoints to provide current job state,
    progress, and metadata.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Job Status Response",
            "description": "Current status and progress information for an analysis job",
            "examples": [
                {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "processing",
                    "job_type": "binary_analysis",
                    "filename": "malware_sample.exe",
                    "priority": "high",
                    "progress_percentage": 65,
                    "progress_message": "Analyzing security patterns",
                    "created_at": "2024-01-15T14:00:00Z",
                    "started_at": "2024-01-15T14:02:00Z",
                    "estimated_completion": "2024-01-15T14:10:00Z",
                    "retry_count": 0,
                    "worker_id": "worker-01",
                    "queue_position": None
                },
                {
                    "job_id": "660f9511-f3ac-52e5-b827-557766551111",
                    "status": "pending",
                    "job_type": "binary_analysis",
                    "filename": "sample2.exe",
                    "priority": "normal",
                    "progress_percentage": None,
                    "created_at": "2024-01-15T14:05:00Z",
                    "queue_position": 3,
                    "retry_count": 0
                }
            ]
        }
    )
    
    job_id: str = Field(
        description="Unique identifier for the job"
    )
    
    status: JobStatus = Field(
        description="Current job status"
    )
    
    job_type: str = Field(
        description="Type of job"
    )
    
    filename: str = Field(
        description="Name of the file being processed"
    )
    
    priority: str = Field(
        description="Job priority level"
    )
    
    progress_percentage: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Progress percentage (0-100)"
    )
    
    progress_message: Optional[str] = Field(
        default=None,
        description="Human-readable progress description"
    )
    
    created_at: datetime = Field(
        description="Job creation timestamp"
    )
    
    started_at: Optional[datetime] = Field(
        default=None,
        description="Job start timestamp"
    )
    
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Job completion timestamp"
    )
    
    estimated_completion: Optional[datetime] = Field(
        default=None,
        description="Estimated completion time"
    )
    
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts made"
    )
    
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts allowed"
    )
    
    worker_id: Optional[str] = Field(
        default=None,
        description="ID of worker processing the job"
    )
    
    queue_position: Optional[int] = Field(
        default=None,
        description="Position in processing queue"
    )
    
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if job failed"
    )
    
    warning_count: int = Field(
        default=0,
        description="Number of warnings generated"
    )
    
    result_url: Optional[str] = Field(
        default=None,
        description="URL to retrieve job results"
    )
    
    logs_url: Optional[str] = Field(
        default=None,
        description="URL to retrieve job logs"
    )
    
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracking"
    )
    
    batch_id: Optional[str] = Field(
        default=None,
        description="Batch ID if job is part of a batch"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Job tags"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Job metadata"
    )
    
    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if job is currently active."""
        return self.status in [JobStatus.PENDING, JobStatus.PROCESSING]
    
    @computed_field
    @property
    def is_complete(self) -> bool:
        """Check if job is complete (success or failure)."""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]
    
    @computed_field
    @property
    def has_failed(self) -> bool:
        """Check if job has failed."""
        return self.status == JobStatus.FAILED
    
    @computed_field
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate job duration if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return None
    
    @computed_field
    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return (
            self.status == JobStatus.FAILED and 
            self.retry_count < self.max_retries
        )
    
    @computed_field
    @property
    def time_in_queue_seconds(self) -> Optional[float]:
        """Calculate time spent in queue before processing."""
        if self.started_at:
            return (self.started_at - self.created_at).total_seconds()
        else:
            return (datetime.now() - self.created_at).total_seconds()
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "filename": self.filename,
            "priority": self.priority,
            "progress_percentage": self.progress_percentage,
            "is_active": self.is_active,
            "is_complete": self.is_complete,
            "has_failed": self.has_failed,
            "retry_count": self.retry_count,
            "can_retry": self.can_retry,
            "duration_seconds": self.duration_seconds,
            "queue_time_seconds": self.time_in_queue_seconds,
            "worker_id": self.worker_id,
            "created_at": self.created_at.isoformat(),
            "correlation_id": self.correlation_id,
            "batch_id": self.batch_id
        }


class JobListResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for job listing endpoints.
    
    Provides paginated list of jobs with filtering and sorting
    metadata.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Job List Response",
            "description": "Paginated list of jobs with filtering and sorting metadata",
            "examples": [
                {
                    "jobs": [
                        {
                            "job_id": "550e8400-e29b-41d4-a716-446655440000",
                            "status": "completed",
                            "job_type": "binary_analysis",
                            "filename": "sample1.exe",
                            "priority": "high",
                            "created_at": "2024-01-15T14:00:00Z",
                            "completed_at": "2024-01-15T14:05:30Z"
                        },
                        {
                            "job_id": "660f9511-f3ac-52e5-b827-557766551111",
                            "status": "processing",
                            "job_type": "binary_analysis",
                            "filename": "sample2.exe",
                            "priority": "normal",
                            "created_at": "2024-01-15T14:02:00Z",
                            "progress_percentage": 45
                        }
                    ],
                    "total_count": 145,
                    "page": 1,
                    "page_size": 20,
                    "total_pages": 8,
                    "has_next": True,
                    "has_previous": False,
                    "filters_applied": {
                        "status": "processing",
                        "priority": "high"
                    },
                    "sort_by": "created_at",
                    "sort_order": "desc"
                }
            ]
        }
    )
    
    jobs: List[JobStatusResponse] = Field(
        description="List of job status responses"
    )
    
    total_count: int = Field(
        ge=0,
        description="Total number of jobs matching filters"
    )
    
    page: int = Field(
        ge=1,
        description="Current page number"
    )
    
    page_size: int = Field(
        ge=1,
        le=100,
        description="Number of jobs per page"
    )
    
    total_pages: int = Field(
        ge=0,
        description="Total number of pages"
    )
    
    has_next: bool = Field(
        description="Whether there is a next page"
    )
    
    has_previous: bool = Field(
        description="Whether there is a previous page"
    )
    
    filters_applied: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filters applied to the job list"
    )
    
    sort_by: str = Field(
        default="created_at",
        description="Field used for sorting"
    )
    
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort order (asc/desc)"
    )
    
    @computed_field
    @property
    def is_empty(self) -> bool:
        """Check if job list is empty."""
        return len(self.jobs) == 0
    
    @computed_field
    @property
    def status_counts(self) -> Dict[str, int]:
        """Count jobs by status."""
        counts = {}
        for job in self.jobs:
            status = str(job.status)
            counts[status] = counts.get(status, 0) + 1
        return counts
    
    @computed_field
    @property
    def priority_counts(self) -> Dict[str, int]:
        """Count jobs by priority."""
        counts = {}
        for job in self.jobs:
            priority = job.priority
            counts[priority] = counts.get(priority, 0) + 1
        return counts
    
    @computed_field
    @property
    def active_job_count(self) -> int:
        """Count of active jobs in current page."""
        return sum(1 for job in self.jobs if job.is_active)
    
    @computed_field
    @property
    def pagination_info(self) -> Dict[str, Any]:
        """Get pagination information."""
        return {
            "current_page": self.page,
            "total_pages": self.total_pages,
            "page_size": self.page_size,
            "total_count": self.total_count,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
            "showing_from": (self.page - 1) * self.page_size + 1 if self.jobs else 0,
            "showing_to": min(self.page * self.page_size, self.total_count),
            "is_last_page": not self.has_next
        }
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "job_count": len(self.jobs),
            "total_count": self.total_count,
            "pagination": self.pagination_info,
            "status_counts": self.status_counts,
            "priority_counts": self.priority_counts,
            "active_jobs": self.active_job_count,
            "filters_applied": self.filters_applied,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
            "is_empty": self.is_empty
        }
    
    def get_jobs_by_status(self, status: JobStatus) -> List[JobStatusResponse]:
        """Get jobs with specific status."""
        return [job for job in self.jobs if job.status == status]
    
    def get_jobs_by_priority(self, priority: str) -> List[JobStatusResponse]:
        """Get jobs with specific priority."""
        return [job for job in self.jobs if job.priority == priority]
    
    def get_jobs_in_batch(self, batch_id: str) -> List[JobStatusResponse]:
        """Get jobs in specific batch."""
        return [job for job in self.jobs if job.batch_id == batch_id]


class JobActionRequest(BaseModel, AnalysisModelMixin):
    """
    Request model for job actions (cancel, retry, etc.).
    
    Used by job management endpoints to perform actions
    on existing jobs.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Job Action Request",
            "description": "Request to perform an action on an existing job (cancel, retry, pause, etc.)",
            "examples": [
                {
                    "action": "cancel",
                    "reason": "User requested cancellation",
                    "force": False
                },
                {
                    "action": "retry",
                    "reason": "Temporary network error resolved",
                    "reset_retry_count": False
                },
                {
                    "action": "pause",
                    "reason": "System maintenance",
                    "force": True
                },
                {
                    "action": "reset",
                    "reason": "Change priority",
                    "new_priority": "urgent",
                    "reset_retry_count": True
                }
            ]
        }
    )
    
    action: Annotated[str, Field(
        pattern="^(cancel|retry|pause|resume|reset)$",
        description="Action to perform on the job. Available actions: cancel, retry, pause, resume, reset",
        examples=["cancel", "retry", "pause", "resume", "reset"]
    )]
    
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for the action"
    )
    
    force: bool = Field(
        default=False,
        description="Force action even if job state doesn't normally allow it"
    )
    
    reset_retry_count: bool = Field(
        default=False,
        description="Reset retry count when retrying"
    )
    
    new_priority: Optional[str] = Field(
        default=None,
        pattern="^(low|normal|high|urgent)$",
        description="New priority level (for priority change actions)"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the action"
    )
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "action": self.action,
            "reason": self.reason,
            "force": self.force,
            "reset_retry_count": self.reset_retry_count,
            "new_priority": self.new_priority,
            "has_metadata": len(self.metadata) > 0
        }


class JobActionResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for job action results.
    
    Returned after performing actions on jobs to indicate
    success/failure and provide updated job status.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Job Action Response",
            "description": "Result of performing an action on a job",
            "examples": [
                {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "action": "cancel",
                    "success": True,
                    "message": "Job cancelled successfully",
                    "previous_status": "processing",
                    "new_status": "cancelled",
                    "timestamp": "2024-01-15T14:15:00Z",
                    "warnings": []
                },
                {
                    "job_id": "660f9511-f3ac-52e5-b827-557766551111",
                    "action": "retry",
                    "success": True,
                    "message": "Job queued for retry",
                    "previous_status": "failed",
                    "new_status": "pending",
                    "timestamp": "2024-01-15T14:20:00Z",
                    "warnings": ["Retry count reset to 0"]
                }
            ]
        }
    )
    
    job_id: str = Field(
        description="Job ID that action was performed on"
    )
    
    action: str = Field(
        description="Action that was performed"
    )
    
    success: bool = Field(
        description="Whether the action was successful"
    )
    
    message: str = Field(
        description="Result message"
    )
    
    previous_status: JobStatus = Field(
        description="Job status before action"
    )
    
    new_status: JobStatus = Field(
        description="Job status after action"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the action was performed"
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="Any warnings generated during action"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional action result metadata"
    )
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "job_id": self.job_id,
            "action": self.action,
            "success": self.success,
            "message": self.message,
            "status_changed": self.previous_status != self.new_status,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "timestamp": self.timestamp.isoformat(),
            "warning_count": len(self.warnings)
        }


class JobCreationResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for job creation operations.
    
    Returned when creating new analysis jobs to provide
    job identifiers, status, and initial information.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "analysis_id": "analysis_abc123def456",
                    "status": "queued",
                    "priority": "normal",
                    "estimated_completion": "2024-01-15T14:20:00Z",
                    "position_in_queue": 3,
                    "created_at": "2024-01-15T14:15:00Z",
                    "configuration_summary": {
                        "analysis_depth": "standard",
                        "focus_areas": ["security", "functions"],
                        "timeout_seconds": 300
                    },
                    "file_info": {
                        "filename": "sample.exe",
                        "size_mb": 2.5,
                        "format": "pe"
                    }
                }
            ]
        }
    )
    
    job_id: str = Field(
        description="Unique job identifier"
    )
    
    analysis_id: str = Field(
        description="Associated analysis identifier"
    )
    
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        description="Initial job status"
    )
    
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
        description="Job priority level"
    )
    
    estimated_completion: Optional[datetime] = Field(
        default=None,
        description="Estimated completion time"
    )
    
    position_in_queue: Optional[int] = Field(
        default=None,
        ge=0,
        description="Position in processing queue"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When the job was created"
    )
    
    configuration_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of analysis configuration"
    )
    
    file_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Information about the file being analyzed"
    )
    
    worker_assignment: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Worker assignment information if available"
    )
    
    resource_requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Estimated resource requirements"
    )
    
    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for job completion notifications"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional job metadata"
    )
    
    @computed_field
    @property
    def is_queued(self) -> bool:
        """Check if job is currently queued."""
        return self.status == JobStatus.PENDING
    
    @computed_field
    @property
    def estimated_wait_time_seconds(self) -> Optional[int]:
        """Estimate wait time based on queue position."""
        if not self.position_in_queue:
            return None
        
        # Rough estimate: 2 minutes per job ahead in queue
        return self.position_in_queue * 120
    
    @computed_field
    @property
    def estimated_total_time_seconds(self) -> Optional[int]:
        """Estimate total time including queue wait and processing."""
        config_timeout = self.configuration_summary.get("timeout_seconds", 300)
        wait_time = self.estimated_wait_time_seconds or 0
        
        return wait_time + config_timeout
    
    @computed_field
    @property
    def job_summary(self) -> Dict[str, Any]:
        """Get comprehensive job creation summary."""
        return {
            "job_id": self.job_id,
            "analysis_id": self.analysis_id,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "position_in_queue": self.position_in_queue,
            "estimated_wait_time": self.estimated_wait_time_seconds,
            "estimated_total_time": self.estimated_total_time_seconds,
            "has_webhook": self.webhook_url is not None,
            "configuration": self.configuration_summary,
            "file_info": self.file_info,
            "resource_requirements": self.resource_requirements
        }
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get status tracking information."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "is_queued": self.is_queued,
            "position_in_queue": self.position_in_queue,
            "estimated_wait_seconds": self.estimated_wait_time_seconds,
            "created_at": self.created_at.isoformat(),
            "priority": self.priority
        }
    
    def get_polling_info(self) -> Dict[str, Any]:
        """Get information for status polling."""
        return {
            "job_id": self.job_id,
            "status_endpoint": f"/api/v1/jobs/{self.job_id}",
            "result_endpoint": f"/api/v1/jobs/{self.job_id}/result",
            "recommended_poll_interval_seconds": 30 if self.is_queued else 10,
            "has_webhook": self.webhook_url is not None,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None
        }
    
    @classmethod
    def from_job_creation(
        cls,
        job_id: str,
        analysis_id: str,
        priority: str = "normal",
        configuration: Optional[Dict[str, Any]] = None,
        file_info: Optional[Dict[str, Any]] = None,
        webhook_url: Optional[str] = None,
        **kwargs
    ) -> 'JobCreationResponse':
        """Create response from job creation parameters."""
        from datetime import timedelta
        
        # Estimate completion time based on configuration
        timeout_seconds = 300  # default
        if configuration and 'timeout_seconds' in configuration:
            timeout_seconds = configuration['timeout_seconds']
        
        estimated_completion = datetime.now() + timedelta(seconds=timeout_seconds + 120)  # + queue time
        
        return cls(
            job_id=job_id,
            analysis_id=analysis_id,
            status=JobStatus.PENDING,
            priority=priority,
            estimated_completion=estimated_completion,
            configuration_summary=configuration or {},
            file_info=file_info or {},
            webhook_url=webhook_url,
            **kwargs
        )