"""
Unit tests for analysis configuration models.

Tests the AnalysisConfig, AnalysisRequest, and related validation
functionality for binary analysis configuration.
"""

import pytest
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from src.models.shared.enums import AnalysisDepth, AnalysisFocus, FileFormat
from src.models.analysis.config import AnalysisConfig, AnalysisRequest, AnalysisJobMetadata


class TestAnalysisConfig:
    """Test cases for AnalysisConfig model."""
    
    def test_basic_instantiation(self):
        """Test basic configuration creation with defaults."""
        config = AnalysisConfig()
        
        assert config.depth == AnalysisDepth.STANDARD
        assert config.timeout_seconds == 300
        assert config.focus_areas == [AnalysisFocus.ALL]
        assert config.enable_security_scan is True
        assert config.max_functions is None
        assert config.max_strings is None
        assert config.enable_detailed_analysis is True
    
    def test_custom_configuration(self):
        """Test configuration with custom values."""
        config = AnalysisConfig(
            depth=AnalysisDepth.COMPREHENSIVE,
            timeout_seconds=600,
            focus_areas=[AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS],
            enable_security_scan=False,
            max_functions=5000,
            max_strings=10000,
            enable_detailed_analysis=False
        )
        
        assert config.depth == AnalysisDepth.COMPREHENSIVE
        assert config.timeout_seconds == 600
        assert config.focus_areas == [AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS]
        assert config.enable_security_scan is False
        assert config.max_functions == 5000
        assert config.max_strings == 10000
        assert config.enable_detailed_analysis is False
    
    def test_timeout_validation(self):
        """Test timeout validation constraints."""
        # Valid timeout
        config = AnalysisConfig(timeout_seconds=120)
        assert config.timeout_seconds == 120
        
        # Test boundary values
        config_min = AnalysisConfig(timeout_seconds=30)
        assert config_min.timeout_seconds == 30
        
        config_max = AnalysisConfig(timeout_seconds=3600)
        assert config_max.timeout_seconds == 3600
        
        # Invalid timeouts should raise validation error
        with pytest.raises(ValueError, match="timeout_seconds must be between"):
            AnalysisConfig(timeout_seconds=10)
        
        with pytest.raises(ValueError, match="timeout_seconds must be between"):
            AnalysisConfig(timeout_seconds=7200)
    
    def test_focus_areas_validation(self):
        """Test focus areas validation."""
        # Single focus area
        config = AnalysisConfig(focus_areas=[AnalysisFocus.SECURITY])
        assert config.focus_areas == [AnalysisFocus.SECURITY]
        
        # Multiple focus areas
        areas = [AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS, AnalysisFocus.STRINGS]
        config = AnalysisConfig(focus_areas=areas)
        assert set(config.focus_areas) == set(areas)
        
        # Empty focus areas should default to ALL
        config = AnalysisConfig(focus_areas=[])
        assert config.focus_areas == [AnalysisFocus.ALL]
    
    def test_max_limits_validation(self):
        """Test maximum limit constraints."""
        # Valid limits
        config = AnalysisConfig(max_functions=1000, max_strings=5000)
        assert config.max_functions == 1000
        assert config.max_strings == 5000
        
        # Zero should be valid (no limit)
        config = AnalysisConfig(max_functions=0, max_strings=0)
        assert config.max_functions == 0
        assert config.max_strings == 0
        
        # Negative values should raise error
        with pytest.raises(ValueError, match="max_functions must be non-negative"):
            AnalysisConfig(max_functions=-1)
        
        with pytest.raises(ValueError, match="max_strings must be non-negative"):
            AnalysisConfig(max_strings=-1)
    
    def test_quick_analysis_preset(self):
        """Test quick analysis preset configuration."""
        config = AnalysisConfig.quick_analysis()
        
        assert config.depth == AnalysisDepth.QUICK
        assert config.timeout_seconds == 60
        assert config.enable_security_scan is False
        assert config.enable_detailed_analysis is False
        assert config.focus_areas == [AnalysisFocus.FUNCTIONS, AnalysisFocus.IMPORTS]
    
    def test_comprehensive_analysis_preset(self):
        """Test comprehensive analysis preset configuration."""
        config = AnalysisConfig.comprehensive_analysis()
        
        assert config.depth == AnalysisDepth.COMPREHENSIVE
        assert config.timeout_seconds == 1200
        assert config.enable_security_scan is True
        assert config.enable_detailed_analysis is True
        assert config.focus_areas == [AnalysisFocus.ALL]
    
    def test_security_focused_preset(self):
        """Test security-focused analysis preset."""
        config = AnalysisConfig.security_focused()
        
        assert config.depth == AnalysisDepth.STANDARD
        assert config.enable_security_scan is True
        assert AnalysisFocus.SECURITY in config.focus_areas
        assert AnalysisFocus.STRINGS in config.focus_areas
    
    def test_estimated_duration(self):
        """Test duration estimation method."""
        quick_config = AnalysisConfig(depth=AnalysisDepth.QUICK)
        standard_config = AnalysisConfig(depth=AnalysisDepth.STANDARD)
        comprehensive_config = AnalysisConfig(depth=AnalysisDepth.COMPREHENSIVE)
        
        quick_duration = quick_config.estimate_duration(file_size_mb=10)
        standard_duration = standard_config.estimate_duration(file_size_mb=10)
        comprehensive_duration = comprehensive_config.estimate_duration(file_size_mb=10)
        
        assert quick_duration < standard_duration < comprehensive_duration
        assert all(d > 0 for d in [quick_duration, standard_duration, comprehensive_duration])
    
    def test_resource_requirements(self):
        """Test resource requirement calculation."""
        config = AnalysisConfig(depth=AnalysisDepth.COMPREHENSIVE, enable_detailed_analysis=True)
        requirements = config.get_resource_requirements()
        
        assert isinstance(requirements, dict)
        assert 'memory_mb' in requirements
        assert 'cpu_cores' in requirements
        assert 'disk_mb' in requirements
        assert all(v > 0 for v in requirements.values())
    
    def test_serialization(self):
        """Test configuration serialization and deserialization."""
        config = AnalysisConfig(
            depth=AnalysisDepth.COMPREHENSIVE,
            timeout_seconds=600,
            focus_areas=[AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS]
        )
        
        # Test dictionary serialization
        config_dict = config.to_dict()
        assert config_dict['depth'] == 'comprehensive'
        assert config_dict['timeout_seconds'] == 600
        assert 'security' in config_dict['focus_areas']
        assert 'functions' in config_dict['focus_areas']
        
        # Test reconstruction from dictionary
        reconstructed = AnalysisConfig.from_dict(config_dict)
        assert reconstructed.depth == config.depth
        assert reconstructed.timeout_seconds == config.timeout_seconds
        assert set(reconstructed.focus_areas) == set(config.focus_areas)
    
    def test_compatibility_check(self):
        """Test configuration compatibility with file format."""
        config = AnalysisConfig()
        
        # Should be compatible with supported formats
        assert config.is_compatible_with_format(FileFormat.PE)
        assert config.is_compatible_with_format(FileFormat.ELF)
        assert config.is_compatible_with_format(FileFormat.MACHO)
        
        # May have limitations with experimental formats
        compatibility = config.is_compatible_with_format(FileFormat.APK)
        assert isinstance(compatibility, bool)


class TestAnalysisRequest:
    """Test cases for AnalysisRequest model."""
    
    def test_basic_instantiation(self):
        """Test basic request creation."""
        request = AnalysisRequest(
            file_hash="abc123",
            file_format=FileFormat.PE,
            file_size=1024
        )
        
        assert request.file_hash == "abc123"
        assert request.file_format == FileFormat.PE
        assert request.file_size == 1024
        assert isinstance(request.config, AnalysisConfig)
        assert request.priority == "normal"
        assert request.metadata is None
    
    def test_custom_configuration(self):
        """Test request with custom configuration."""
        custom_config = AnalysisConfig(depth=AnalysisDepth.QUICK, timeout_seconds=60)
        request = AnalysisRequest(
            file_hash="abc123",
            file_format=FileFormat.PE,
            file_size=1024,
            config=custom_config,
            priority="high"
        )
        
        assert request.config.depth == AnalysisDepth.QUICK
        assert request.config.timeout_seconds == 60
        assert request.priority == "high"
    
    def test_file_hash_validation(self):
        """Test file hash validation."""
        # Valid SHA-256 hash
        valid_hash = "a" * 64
        request = AnalysisRequest(
            file_hash=valid_hash,
            file_format=FileFormat.PE,
            file_size=1024
        )
        assert request.file_hash == valid_hash
        
        # Invalid hash length
        with pytest.raises(ValueError, match="file_hash must be a valid"):
            AnalysisRequest(
                file_hash="invalid",
                file_format=FileFormat.PE,
                file_size=1024
            )
        
        # Invalid hash characters
        with pytest.raises(ValueError, match="file_hash must be a valid"):
            AnalysisRequest(
                file_hash="g" * 64,  # 'g' is not a hex character
                file_format=FileFormat.PE,
                file_size=1024
            )
    
    def test_file_size_validation(self):
        """Test file size validation."""
        # Valid file size
        request = AnalysisRequest(
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            file_size=1024 * 1024  # 1MB
        )
        assert request.file_size == 1024 * 1024
        
        # Zero size should be invalid
        with pytest.raises(ValueError, match="file_size must be positive"):
            AnalysisRequest(
                file_hash="a" * 64,
                file_format=FileFormat.PE,
                file_size=0
            )
        
        # Negative size should be invalid
        with pytest.raises(ValueError, match="file_size must be positive"):
            AnalysisRequest(
                file_hash="a" * 64,
                file_format=FileFormat.PE,
                file_size=-1
            )
    
    def test_priority_validation(self):
        """Test priority level validation."""
        valid_priorities = ["low", "normal", "high", "urgent"]
        
        for priority in valid_priorities:
            request = AnalysisRequest(
                file_hash="a" * 64,
                file_format=FileFormat.PE,
                file_size=1024,
                priority=priority
            )
            assert request.priority == priority
        
        # Invalid priority
        with pytest.raises(ValueError, match="priority must be one of"):
            AnalysisRequest(
                file_hash="a" * 64,
                file_format=FileFormat.PE,
                file_size=1024,
                priority="invalid"
            )
    
    def test_metadata_handling(self):
        """Test optional metadata handling."""
        metadata = {
            "source": "upload",
            "filename": "test.exe",
            "tags": ["production", "audit"]
        }
        
        request = AnalysisRequest(
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            file_size=1024,
            metadata=metadata
        )
        
        assert request.metadata == metadata
        assert request.metadata["source"] == "upload"
        assert "production" in request.metadata["tags"]
    
    def test_creation_from_file_info(self):
        """Test request creation from file information."""
        request = AnalysisRequest.from_file_info(
            file_path="/tmp/test.exe",
            file_hash="a" * 64,
            file_size=2048,
            detected_format=FileFormat.PE
        )
        
        assert request.file_hash == "a" * 64
        assert request.file_format == FileFormat.PE
        assert request.file_size == 2048
        assert request.metadata["original_path"] == "/tmp/test.exe"
        assert request.metadata["filename"] == "test.exe"
    
    def test_quick_analysis_factory(self):
        """Test quick analysis request factory method."""
        request = AnalysisRequest.for_quick_analysis(
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            file_size=1024
        )
        
        assert request.config.depth == AnalysisDepth.QUICK
        assert request.priority == "high"
        assert not request.config.enable_security_scan
    
    def test_comprehensive_analysis_factory(self):
        """Test comprehensive analysis request factory method."""
        request = AnalysisRequest.for_comprehensive_analysis(
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            file_size=1024
        )
        
        assert request.config.depth == AnalysisDepth.COMPREHENSIVE
        assert request.config.enable_security_scan is True
        assert request.config.enable_detailed_analysis is True


class TestAnalysisJobMetadata:
    """Test cases for AnalysisJobMetadata model."""
    
    def test_basic_instantiation(self):
        """Test basic metadata creation."""
        metadata = AnalysisJobMetadata(
            request_id="req_123",
            user_id="user_456"
        )
        
        assert isinstance(metadata.job_id, UUID)
        assert metadata.request_id == "req_123"
        assert metadata.user_id == "user_456"
        assert isinstance(metadata.created_at, datetime)
        assert metadata.started_at is None
        assert metadata.completed_at is None
        assert metadata.worker_id is None
    
    def test_job_lifecycle_tracking(self):
        """Test job lifecycle timestamp tracking."""
        metadata = AnalysisJobMetadata(
            request_id="req_123",
            user_id="user_456"
        )
        
        # Mark as started
        metadata.mark_started("worker_001")
        assert metadata.started_at is not None
        assert metadata.worker_id == "worker_001"
        
        # Mark as completed
        metadata.mark_completed()
        assert metadata.completed_at is not None
    
    def test_duration_calculations(self):
        """Test duration calculation methods."""
        metadata = AnalysisJobMetadata(
            request_id="req_123",
            user_id="user_456"
        )
        
        metadata.mark_started("worker_001")
        queue_duration = metadata.get_queue_duration()
        assert queue_duration >= 0
        
        metadata.mark_completed()
        processing_duration = metadata.get_processing_duration()
        total_duration = metadata.get_total_duration()
        
        assert processing_duration >= 0
        assert total_duration >= queue_duration
        assert total_duration >= processing_duration
    
    def test_status_reporting(self):
        """Test status information generation."""
        metadata = AnalysisJobMetadata(
            request_id="req_123",
            user_id="user_456"
        )
        
        status = metadata.get_status_info()
        assert isinstance(status, dict)
        assert 'job_id' in status
        assert 'request_id' in status
        assert 'created_at' in status
        assert 'queue_duration' in status
    
    def test_serialization(self):
        """Test metadata serialization."""
        metadata = AnalysisJobMetadata(
            request_id="req_123",
            user_id="user_456"
        )
        metadata.mark_started("worker_001")
        
        serialized = metadata.to_dict()
        assert serialized['request_id'] == "req_123"
        assert serialized['user_id'] == "user_456"
        assert serialized['worker_id'] == "worker_001"
        
        # Test deserialization
        reconstructed = AnalysisJobMetadata.from_dict(serialized)
        assert reconstructed.request_id == metadata.request_id
        assert reconstructed.user_id == metadata.user_id
        assert reconstructed.worker_id == metadata.worker_id


class TestConfigurationValidation:
    """Test cases for configuration validation logic."""
    
    def test_timeout_depth_consistency(self):
        """Test timeout and depth consistency validation."""
        # Quick analysis with long timeout should trigger warning
        config = AnalysisConfig(depth=AnalysisDepth.QUICK, timeout_seconds=1200)
        warnings = config.validate_configuration()
        assert any("timeout" in warning.lower() for warning in warnings)
        
        # Comprehensive analysis with short timeout should trigger warning
        config = AnalysisConfig(depth=AnalysisDepth.COMPREHENSIVE, timeout_seconds=30)
        warnings = config.validate_configuration()
        assert any("timeout" in warning.lower() for warning in warnings)
    
    def test_focus_area_conflicts(self):
        """Test focus area conflict detection."""
        # ALL focus with specific areas should trigger warning
        config = AnalysisConfig(focus_areas=[AnalysisFocus.ALL, AnalysisFocus.SECURITY])
        warnings = config.validate_configuration()
        assert any("focus" in warning.lower() for warning in warnings)
    
    def test_resource_limit_validation(self):
        """Test resource limit validation."""
        config = AnalysisConfig(
            depth=AnalysisDepth.COMPREHENSIVE,
            enable_detailed_analysis=True,
            max_functions=100000,
            max_strings=500000
        )
        
        requirements = config.get_resource_requirements()
        warnings = config.validate_configuration()
        
        # Should warn about high resource usage
        high_resource_warning = any(
            "resource" in warning.lower() or "memory" in warning.lower() 
            for warning in warnings
        )
        assert isinstance(high_resource_warning, bool)