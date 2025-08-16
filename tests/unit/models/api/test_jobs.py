"""
Unit tests for API job management models.

Tests the job creation, status tracking, and management models
for the asynchronous analysis job system.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from typing import Dict, Any, List, Optional

from src.models.shared.enums import JobStatus, AnalysisDepth, FileFormat
from src.models.api.jobs import (
    JobCreationRequest, JobCreationResponse, JobStatusResponse, 
    JobListResponse, JobActionRequest, JobActionResponse
)


class TestJobCreationRequest:
    """Test cases for JobCreationRequest model."""
    
    def test_basic_instantiation(self):
        """Test basic job creation request."""
        request = JobCreationRequest(
            file_reference="upload_123",
            filename="test.exe",
            analysis_config={
                "depth": "standard",
                "timeout_seconds": 300,
                "focus_areas": ["security", "functions"]
            }
        )
        
        assert request.file_reference == "upload_123"
        assert request.filename == "test.exe"
        assert request.analysis_config["depth"] == "standard"
        assert request.priority == "normal"  # Default
        assert request.callback_url is None
        assert request.metadata == {}
    
    def test_with_callback_url(self):
        """Test job creation with callback URL."""
        request = JobCreationRequest(
            file_reference="upload_456",
            filename="callback_test.exe",
            analysis_config={"depth": "quick"},
            callback_url="https://api.client.com/webhooks/analysis"
        )
        
        assert request.callback_url == "https://api.client.com/webhooks/analysis"
    
    def test_with_priority_and_metadata(self):
        """Test job creation with priority and metadata."""
        metadata = {
            "user_id": "user_123",
            "project_id": "proj_456",
            "tags": ["urgent", "security_audit"]
        }
        
        request = JobCreationRequest(
            file_reference="upload_789",
            filename="urgent.exe",
            analysis_config={"depth": "comprehensive", "timeout_seconds": 1200},
            priority="high",
            metadata=metadata
        )
        
        assert request.priority == "high"
        assert request.metadata == metadata
        assert request.metadata["user_id"] == "user_123"
    
    def test_file_reference_validation(self):
        """Test file reference validation."""
        # Valid upload ID
        request = JobCreationRequest(
            file_reference="upload_abc123",
            filename="test.exe",
            analysis_config={"depth": "standard"}
        )
        assert request.file_reference == "upload_abc123"
        
        # Valid SHA-256 hash
        hash_ref = "a" * 64
        request = JobCreationRequest(
            file_reference=hash_ref,
            filename="test.exe",
            analysis_config={"depth": "standard"}
        )
        assert request.file_reference == hash_ref
        
        # Invalid reference
        with pytest.raises(ValueError, match="file_reference must be either"):
            JobCreationRequest(
                file_reference="invalid_ref",
                filename="test.exe",
                analysis_config={"depth": "standard"}
            )
    
    def test_analysis_config_validation(self):
        """Test analysis configuration validation."""
        # Valid minimal config
        request = JobCreationRequest(
            file_reference="upload_123",
            filename="test.exe",
            analysis_config={"depth": "standard"}
        )
        assert request.analysis_config["depth"] == "standard"
        
        # Config with all optional fields
        full_config = {
            "depth": "comprehensive",
            "timeout_seconds": 600,
            "focus_areas": ["security", "functions", "strings"],
            "enable_security_scan": True,
            "max_functions": 5000,
            "max_strings": 10000
        }
        
        request = JobCreationRequest(
            file_reference="upload_456",
            filename="test.exe",
            analysis_config=full_config
        )
        assert request.analysis_config == full_config
    
    def test_priority_validation(self):
        """Test priority validation."""
        valid_priorities = ["low", "normal", "high", "urgent"]
        
        for priority in valid_priorities:
            request = JobCreationRequest(
                file_reference="upload_123",
                filename="test.exe",
                analysis_config={"depth": "standard"},
                priority=priority
            )
            assert request.priority == priority
        
        # Invalid priority
        with pytest.raises(ValueError, match="priority must be one of"):
            JobCreationRequest(
                file_reference="upload_123",
                filename="test.exe", 
                analysis_config={"depth": "standard"},
                priority="invalid"
            )
    
    def test_callback_url_validation(self):
        """Test callback URL validation."""
        # Valid HTTPS URL
        request = JobCreationRequest(
            file_reference="upload_123",
            filename="test.exe",
            analysis_config={"depth": "standard"},
            callback_url="https://secure.client.com/webhook"
        )
        assert request.callback_url.startswith("https://")
        
        # HTTP URL should work but may generate warning
        request = JobCreationRequest(
            file_reference="upload_123",
            filename="test.exe",
            analysis_config={"depth": "standard"},
            callback_url="http://localhost:8080/webhook"
        )
        assert request.callback_url.startswith("http://")
        
        # Invalid URL format
        with pytest.raises(ValueError, match="callback_url must be a valid"):
            JobCreationRequest(
                file_reference="upload_123",
                filename="test.exe",
                analysis_config={"depth": "standard"},
                callback_url="not_a_url"
            )


class TestJobCreationResponse:
    """Test cases for JobCreationResponse model."""
    
    def test_basic_instantiation(self):
        """Test basic job creation response."""
        job_id = uuid4()
        response = JobCreationResponse(
            success=True,
            job_id=job_id,
            status=JobStatus.PENDING
        )
        
        assert response.success is True
        assert response.job_id == job_id
        assert response.status == JobStatus.PENDING
        assert isinstance(response.created_at, datetime)
        assert response.estimated_completion_time is None
        assert response.queue_position is None
    
    def test_with_queue_information(self):
        """Test response with queue information."""
        estimated_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        
        response = JobCreationResponse(
            success=True,
            job_id=uuid4(),
            status=JobStatus.PENDING,
            queue_position=15,
            estimated_completion_time=estimated_time
        )
        
        assert response.queue_position == 15
        assert response.estimated_completion_time == estimated_time
    
    def test_with_polling_information(self):
        """Test response with polling endpoints."""
        job_id = uuid4()
        polling_info = {
            "status_url": f"/api/v1/jobs/{job_id}/status",
            "results_url": f"/api/v1/jobs/{job_id}/results",
            "recommended_poll_interval": 30
        }
        
        response = JobCreationResponse(
            success=True,
            job_id=job_id,
            status=JobStatus.PENDING,
            polling_info=polling_info
        )
        
        assert response.polling_info is not None
        assert job_id.hex in response.polling_info["status_url"]
        assert response.polling_info["recommended_poll_interval"] == 30
    
    def test_failed_creation_response(self):
        """Test failed job creation response."""
        response = JobCreationResponse(
            success=False,
            job_id=None,
            status=None,
            error_message="File reference not found",
            error_code="FILE_NOT_FOUND"
        )
        
        assert response.success is False
        assert response.job_id is None
        assert response.status is None
        assert response.error_message == "File reference not found"
        assert response.error_code == "FILE_NOT_FOUND"


class TestJobStatusResponse:
    """Test cases for JobStatusResponse model."""
    
    def test_pending_job_status(self):
        """Test pending job status response."""
        job_id = uuid4()
        response = JobStatusResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            queue_position=5
        )
        
        assert response.job_id == job_id
        assert response.status == JobStatus.PENDING
        assert response.queue_position == 5
        assert response.started_at is None
        assert response.completed_at is None
        assert response.progress_percentage is None
    
    def test_processing_job_status(self):
        """Test processing job status response."""
        now = datetime.now(timezone.utc)
        response = JobStatusResponse(
            job_id=uuid4(),
            status=JobStatus.PROCESSING,
            created_at=now - timedelta(minutes=2),
            started_at=now - timedelta(minutes=1),
            progress_percentage=45.5,
            current_stage="function_analysis",
            estimated_remaining_seconds=120
        )
        
        assert response.status == JobStatus.PROCESSING
        assert response.progress_percentage == 45.5
        assert response.current_stage == "function_analysis"
        assert response.estimated_remaining_seconds == 120
        assert response.queue_position is None
    
    def test_completed_job_status(self):
        """Test completed job status response."""
        now = datetime.now(timezone.utc)
        response = JobStatusResponse(
            job_id=uuid4(),
            status=JobStatus.COMPLETED,
            created_at=now - timedelta(minutes=10),
            started_at=now - timedelta(minutes=8),
            completed_at=now,
            progress_percentage=100.0,
            results_available=True,
            results_url="/api/v1/jobs/123/results"
        )
        
        assert response.status == JobStatus.COMPLETED
        assert response.completed_at is not None
        assert response.progress_percentage == 100.0
        assert response.results_available is True
        assert response.results_url is not None
    
    def test_failed_job_status(self):
        """Test failed job status response."""
        now = datetime.now(timezone.utc)
        response = JobStatusResponse(
            job_id=uuid4(),
            status=JobStatus.FAILED,
            created_at=now - timedelta(minutes=5),
            started_at=now - timedelta(minutes=3),
            completed_at=now,
            error_message="Analysis timeout after 300 seconds",
            error_code="ANALYSIS_TIMEOUT"
        )
        
        assert response.status == JobStatus.FAILED
        assert response.error_message == "Analysis timeout after 300 seconds"
        assert response.error_code == "ANALYSIS_TIMEOUT"
        assert response.results_available is False
    
    def test_duration_calculations(self):
        """Test duration calculation methods."""
        now = datetime.now(timezone.utc)
        response = JobStatusResponse(
            job_id=uuid4(),
            status=JobStatus.COMPLETED,
            created_at=now - timedelta(minutes=10),
            started_at=now - timedelta(minutes=8),
            completed_at=now
        )
        
        queue_duration = response.get_queue_duration_seconds()
        processing_duration = response.get_processing_duration_seconds()
        total_duration = response.get_total_duration_seconds()
        
        assert queue_duration == 120  # 2 minutes in queue
        assert processing_duration == 480  # 8 minutes processing
        assert total_duration == 600  # 10 minutes total
    
    def test_status_checks(self):
        """Test status check convenience methods."""
        pending_response = JobStatusResponse(
            job_id=uuid4(),
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        assert pending_response.is_pending()
        assert not pending_response.is_terminal()
        assert not pending_response.is_complete()
        
        completed_response = JobStatusResponse(
            job_id=uuid4(),
            status=JobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        assert not completed_response.is_pending()
        assert completed_response.is_terminal()
        assert completed_response.is_complete()


class TestJobStatusResponse:
    """Test cases for JobStatusResponse model."""
    
    def test_basic_instantiation(self):
        """Test basic job list item."""
        item = JobStatusResponse(
            job_id=uuid4(),
            filename="test.exe",
            status=JobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            file_size=2048
        )
        
        assert isinstance(item.job_id, UUID)
        assert item.filename == "test.exe"
        assert item.status == JobStatus.COMPLETED
        assert item.file_size == 2048
    
    def test_with_analysis_summary(self):
        """Test job list item with analysis summary."""
        summary = {
            "function_count": 25,
            "import_count": 12,
            "risk_score": 4.5,
            "analysis_duration": 180
        }
        
        item = JobStatusResponse(
            job_id=uuid4(),
            filename="analyzed.exe",
            status=JobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            analysis_summary=summary
        )
        
        assert item.analysis_summary == summary
        assert item.analysis_summary["function_count"] == 25
        assert item.analysis_summary["risk_score"] == 4.5
    
    def test_with_tags_and_metadata(self):
        """Test job list item with tags and metadata."""
        tags = ["security", "audit", "urgent"]
        metadata = {
            "user_id": "user_123",
            "project": "security_review"
        }
        
        item = JobStatusResponse(
            job_id=uuid4(),
            filename="tagged.exe",
            status=JobStatus.PROCESSING,
            created_at=datetime.now(timezone.utc),
            tags=tags,
            metadata=metadata
        )
        
        assert item.tags == tags
        assert "security" in item.tags
        assert item.metadata == metadata
        assert item.metadata["project"] == "security_review"


class TestJobListResponse:
    """Test cases for JobListResponse model."""
    
    def test_basic_instantiation(self):
        """Test basic job list response."""
        jobs = [
            JobStatusResponse(
                job_id=uuid4(),
                filename="job1.exe",
                status=JobStatus.COMPLETED,
                created_at=datetime.now(timezone.utc)
            ),
            JobStatusResponse(
                job_id=uuid4(),
                filename="job2.exe", 
                status=JobStatus.PROCESSING,
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        response = JobListResponse(
            jobs=jobs,
            total_count=2,
            page=1,
            page_size=10
        )
        
        assert len(response.jobs) == 2
        assert response.total_count == 2
        assert response.page == 1
        assert response.page_size == 10
        assert response.total_pages == 1
    
    def test_with_pagination(self):
        """Test job list response with pagination."""
        jobs = [JobStatusResponse(
            job_id=uuid4(),
            filename=f"job{i}.exe",
            status=JobStatus.COMPLETED,
            created_at=datetime.now(timezone.utc)
        ) for i in range(20)]
        
        response = JobListResponse(
            jobs=jobs[:10],  # First 10 jobs
            total_count=50,
            page=1,
            page_size=10
        )
        
        assert len(response.jobs) == 10
        assert response.total_count == 50
        assert response.total_pages == 5
        assert response.has_next_page() is True
        assert response.has_previous_page() is False
        
        # Test second page
        page2_response = JobListResponse(
            jobs=jobs[10:20],
            total_count=50,
            page=2,
            page_size=10
        )
        
        assert page2_response.has_next_page() is True
        assert page2_response.has_previous_page() is True
    
    def test_with_filters_applied(self):
        """Test job list response with applied filters."""
        jobs = [
            JobStatusResponse(
                job_id=uuid4(),
                filename="filtered.exe",
                status=JobStatus.COMPLETED,
                created_at=datetime.now(timezone.utc),
                tags=["security"]
            )
        ]
        
        response = JobListResponse(
            jobs=jobs,
            total_count=1,
            page=1,
            page_size=10,
            filters_applied={
                "status": "completed",
                "tags": ["security"],
                "created_after": "2024-01-01T00:00:00Z"
            }
        )
        
        assert response.filters_applied is not None
        assert response.filters_applied["status"] == "completed"
        assert "security" in response.filters_applied["tags"]
    
    def test_sorting_information(self):
        """Test job list response with sorting information."""
        jobs = [
            JobStatusResponse(
                job_id=uuid4(),
                filename="recent.exe",
                status=JobStatus.COMPLETED,
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        response = JobListResponse(
            jobs=jobs,
            total_count=1,
            page=1,
            page_size=10,
            sort_by="created_at",
            sort_order="desc"
        )
        
        assert response.sort_by == "created_at"
        assert response.sort_order == "desc"


class TestJobActionRequest:
    """Test cases for JobActionRequest model."""
    
    def test_basic_instantiation(self):
        """Test basic cancellation request."""
        request = JobActionRequest(
            job_id=uuid4(),
            reason="User requested cancellation"
        )
        
        assert isinstance(request.job_id, UUID)
        assert request.reason == "User requested cancellation"
        assert request.force is False
    
    def test_force_cancellation(self):
        """Test force cancellation request."""
        request = JobActionRequest(
            job_id=uuid4(),
            reason="System maintenance",
            force=True
        )
        
        assert request.force is True
        assert request.reason == "System maintenance"
    
    def test_cancellation_validation(self):
        """Test cancellation request validation."""
        request = JobActionRequest(
            job_id=uuid4(),
            reason="Test cancellation"
        )
        
        # Should have required fields
        assert request.job_id is not None
        assert request.reason is not None
        assert isinstance(request.force, bool)


class TestJobActionResponse:
    """Test cases for JobActionResponse model."""
    
    def test_basic_metrics(self):
        """Test basic job metrics."""
        metrics = JobActionResponse(
            total_jobs=150,
            pending_jobs=10,
            processing_jobs=5,
            completed_jobs=130,
            failed_jobs=5
        )
        
        assert metrics.total_jobs == 150
        assert metrics.pending_jobs == 10
        assert metrics.processing_jobs == 5
        assert metrics.completed_jobs == 130
        assert metrics.failed_jobs == 5
    
    def test_calculated_metrics(self):
        """Test calculated metrics properties."""
        metrics = JobActionResponse(
            total_jobs=100,
            pending_jobs=20,
            processing_jobs=10,
            completed_jobs=60,
            failed_jobs=10
        )
        
        assert metrics.active_jobs == 30  # pending + processing
        assert metrics.terminal_jobs == 70  # completed + failed
        assert metrics.success_rate == 0.6  # 60/100
        assert metrics.failure_rate == 0.1  # 10/100
    
    def test_queue_statistics(self):
        """Test queue-related statistics."""
        metrics = JobActionResponse(
            total_jobs=50,
            pending_jobs=15,
            processing_jobs=3,
            completed_jobs=30,
            failed_jobs=2,
            average_queue_time_seconds=120.5,
            average_processing_time_seconds=300.0
        )
        
        assert metrics.average_queue_time_seconds == 120.5
        assert metrics.average_processing_time_seconds == 300.0
        assert metrics.queue_utilization == 0.2  # 3/(3+15)
    
    def test_time_period_metrics(self):
        """Test metrics for specific time periods."""
        metrics = JobActionResponse(
            total_jobs=200,
            completed_jobs=180,
            failed_jobs=15,
            time_period="last_24_hours",
            jobs_per_hour=8.5
        )
        
        assert metrics.time_period == "last_24_hours"
        assert metrics.jobs_per_hour == 8.5
        assert metrics.success_rate == 0.9  # 180/200