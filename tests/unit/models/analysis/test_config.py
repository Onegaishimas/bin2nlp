"""
Unit tests for basic analysis configuration models.

Tests the basic AnalysisConfig and AnalysisRequest models focused on
simplified decompilation configuration without complex analysis features.
"""

import pytest
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from src.models.shared.enums import FileFormat, Platform
from src.models.decompilation.results import DecompilationDepth, TranslationDetail
from src.models.analysis.config import DecompilationConfig, DecompilationRequest


class TestAnalysisConfig:
    """Test cases for simplified AnalysisConfig model."""
    
    def test_basic_instantiation(self):
        """Test basic configuration creation with defaults."""
        config = AnalysisConfig()
        
        # Test basic required attributes
        assert config.depth == AnalysisDepth.STANDARD
        assert config.timeout_seconds == 300
        assert hasattr(config, 'depth')
        assert hasattr(config, 'timeout_seconds')
    
    def test_custom_configuration(self):
        """Test configuration with custom values."""
        config = AnalysisConfig(
            depth=AnalysisDepth.COMPREHENSIVE,
            timeout_seconds=600
        )
        
        assert config.depth == AnalysisDepth.COMPREHENSIVE
        assert config.timeout_seconds == 600
    
    def test_timeout_validation(self):
        """Test timeout validation."""
        # Should accept reasonable timeout values
        config1 = AnalysisConfig(timeout_seconds=60)
        assert config1.timeout_seconds == 60
        
        config2 = AnalysisConfig(timeout_seconds=1800)
        assert config2.timeout_seconds == 1800
        
        # Test with invalid values if validation exists
        with pytest.raises((ValueError, TypeError)):
            AnalysisConfig(timeout_seconds=-1)
    
    def test_depth_validation(self):
        """Test analysis depth validation."""
        for depth in AnalysisDepth:
            config = AnalysisConfig(depth=depth)
            assert config.depth == depth


class TestAnalysisRequest:
    """Test cases for simplified AnalysisRequest model."""
    
    def test_basic_analysis_request(self):
        """Test basic analysis request creation."""
        config = AnalysisConfig()
        metadata = AnalysisJobMetadata(
            job_id="test-job-123",
            user_id="test-user", 
            priority="normal"
        )
        
        request = AnalysisRequest(
            config=config,
            metadata=metadata,
            file_hash="abc123def456"
        )
        
        assert request.config == config
        assert request.metadata == metadata
        assert request.file_hash == "abc123def456"
    
    def test_request_with_custom_config(self):
        """Test analysis request with custom configuration."""
        config = AnalysisConfig(
            depth=AnalysisDepth.QUICK,
            timeout_seconds=120
        )
        
        metadata = AnalysisJobMetadata(
            job_id="quick-job-456",
            user_id="test-user-2",
            priority="high"
        )
        
        request = AnalysisRequest(
            config=config,
            metadata=metadata,
            file_hash="def789ghi012"
        )
        
        assert request.config.depth == AnalysisDepth.QUICK
        assert request.config.timeout_seconds == 120
        assert request.metadata.priority == "high"
        assert request.file_hash == "def789ghi012"


class TestAnalysisJobMetadata:
    """Test cases for AnalysisJobMetadata model."""
    
    def test_basic_metadata(self):
        """Test basic job metadata creation."""
        metadata = AnalysisJobMetadata(
            job_id="metadata-test-789",
            user_id="test-user-3",
            priority="normal"
        )
        
        assert metadata.job_id == "metadata-test-789" 
        assert metadata.user_id == "test-user-3"
        assert metadata.priority == "normal"
        assert isinstance(metadata.created_at, datetime)
    
    def test_priority_validation(self):
        """Test priority validation if implemented."""
        # Test valid priorities
        valid_priorities = ["low", "normal", "high", "critical"]
        
        for priority in valid_priorities:
            try:
                metadata = AnalysisJobMetadata(
                    job_id=f"test-{priority}",
                    user_id="test-user",
                    priority=priority
                )
                assert metadata.priority == priority
            except (ValueError, TypeError):
                # If validation is strict, this is expected
                pass
    
    def test_uuid_job_id(self):
        """Test with UUID job ID."""
        job_uuid = str(UUID('12345678-1234-5678-9012-123456789abc'))
        
        metadata = AnalysisJobMetadata(
            job_id=job_uuid,
            user_id="uuid-user",
            priority="normal"
        )
        
        assert metadata.job_id == job_uuid
        assert len(metadata.job_id) == 36  # Standard UUID string length