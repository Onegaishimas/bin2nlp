"""
Unit tests for API analysis models.

Tests the API request/response models for analysis endpoints including
validation, serialization, and OpenAPI documentation.
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Dict, Any, List

from src.models.shared.enums import AnalysisDepth, AnalysisFocus, FileFormat, Platform
from src.models.api.analysis import (
    AnalysisSubmissionRequest, AnalysisSummaryResponse, AnalysisDetailResponse,
    FileUploadRequest, FileUploadResponse, AnalysisConfigRequest
)


class TestAnalysisConfigRequest:
    """Test cases for AnalysisConfigRequest model."""
    
    def test_basic_instantiation(self):
        """Test basic config request creation."""
        config_request = AnalysisConfigRequest()
        
        # Should use defaults
        assert config_request.depth == AnalysisDepth.STANDARD
        assert config_request.timeout_seconds == 300
        assert config_request.focus_areas == [AnalysisFocus.ALL]
        assert config_request.enable_security_scan is True
        assert config_request.priority == "normal"
    
    def test_custom_configuration(self):
        """Test custom configuration request."""
        config_request = AnalysisConfigRequest(
            depth=AnalysisDepth.COMPREHENSIVE,
            timeout_seconds=600,
            focus_areas=[AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS],
            enable_security_scan=True,
            max_functions=5000,
            max_strings=10000,
            priority="high",
            metadata={"source": "api", "user": "test_user"}
        )
        
        assert config_request.depth == AnalysisDepth.COMPREHENSIVE
        assert config_request.timeout_seconds == 600
        assert AnalysisFocus.SECURITY in config_request.focus_areas
        assert AnalysisFocus.FUNCTIONS in config_request.focus_areas
        assert config_request.max_functions == 5000
        assert config_request.max_strings == 10000
        assert config_request.priority == "high"
        assert config_request.metadata["source"] == "api"
    
    def test_validation_constraints(self):
        """Test configuration validation constraints."""
        # Valid timeout range
        valid_config = AnalysisConfigRequest(timeout_seconds=120)
        assert valid_config.timeout_seconds == 120
        
        # Invalid timeout - too low
        with pytest.raises(ValueError, match="timeout_seconds must be between"):
            AnalysisConfigRequest(timeout_seconds=10)
        
        # Invalid timeout - too high
        with pytest.raises(ValueError, match="timeout_seconds must be between"):
            AnalysisConfigRequest(timeout_seconds=7200)
    
    def test_priority_validation(self):
        """Test priority validation."""
        valid_priorities = ["low", "normal", "high", "urgent"]
        
        for priority in valid_priorities:
            config = AnalysisConfigRequest(priority=priority)
            assert config.priority == priority
        
        # Invalid priority
        with pytest.raises(ValueError, match="priority must be one of"):
            AnalysisConfigRequest(priority="invalid")
    
    def test_focus_areas_validation(self):
        """Test focus areas validation and normalization."""
        # Empty focus areas should default to ALL
        config = AnalysisConfigRequest(focus_areas=[])
        assert config.focus_areas == [AnalysisFocus.ALL]
        
        # Duplicate focus areas should be deduplicated
        config = AnalysisConfigRequest(
            focus_areas=[AnalysisFocus.SECURITY, AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS]
        )
        assert len(config.focus_areas) == 2
        assert AnalysisFocus.SECURITY in config.focus_areas
        assert AnalysisFocus.FUNCTIONS in config.focus_areas
    
    def test_resource_limits_validation(self):
        """Test resource limit validation."""
        # Valid limits
        config = AnalysisConfigRequest(max_functions=1000, max_strings=5000)
        assert config.max_functions == 1000
        assert config.max_strings == 5000
        
        # Negative limits should raise error
        with pytest.raises(ValueError, match="max_functions must be non-negative"):
            AnalysisConfigRequest(max_functions=-1)
        
        with pytest.raises(ValueError, match="max_strings must be non-negative"):
            AnalysisConfigRequest(max_strings=-1)
    
    def test_serialization(self):
        """Test config request serialization."""
        config = AnalysisConfigRequest(
            depth=AnalysisDepth.QUICK,
            focus_areas=[AnalysisFocus.FUNCTIONS],
            priority="high"
        )
        
        serialized = config.to_dict()
        assert serialized["depth"] == "quick"
        assert serialized["focus_areas"] == ["functions"]
        assert serialized["priority"] == "high"
        
        # Test JSON serialization
        json_str = config.to_json()
        assert isinstance(json_str, str)
        assert "quick" in json_str


class TestFileUploadRequest:
    """Test cases for FileUploadRequest model."""
    
    def test_basic_instantiation(self):
        """Test basic file upload request."""
        upload_request = FileUploadRequest(
            filename="test.exe",
            file_size=2048,
            content_type="application/octet-stream"
        )
        
        assert upload_request.filename == "test.exe"
        assert upload_request.file_size == 2048
        assert upload_request.content_type == "application/octet-stream"
        assert upload_request.metadata == {}
    
    def test_with_metadata(self):
        """Test upload request with metadata."""
        metadata = {
            "source": "user_upload",
            "description": "Suspicious binary",
            "tags": ["malware", "analysis"]
        }
        
        upload_request = FileUploadRequest(
            filename="suspicious.exe",
            file_size=4096,
            content_type="application/x-executable",
            metadata=metadata
        )
        
        assert upload_request.metadata == metadata
        assert upload_request.metadata["source"] == "user_upload"
        assert "malware" in upload_request.metadata["tags"]
    
    def test_file_size_validation(self):
        """Test file size validation."""
        # Valid file size
        upload_request = FileUploadRequest(
            filename="test.exe",
            file_size=1024 * 1024,  # 1MB
            content_type="application/octet-stream"
        )
        assert upload_request.file_size == 1024 * 1024
        
        # Zero size should be invalid
        with pytest.raises(ValueError, match="file_size must be positive"):
            FileUploadRequest(
                filename="test.exe",
                file_size=0,
                content_type="application/octet-stream"
            )
        
        # File too large
        with pytest.raises(ValueError, match="file_size exceeds maximum"):
            FileUploadRequest(
                filename="huge.exe",
                file_size=200 * 1024 * 1024,  # 200MB
                content_type="application/octet-stream"
            )
    
    def test_filename_validation(self):
        """Test filename validation."""
        # Valid filename
        upload_request = FileUploadRequest(
            filename="test.exe",
            file_size=1024,
            content_type="application/octet-stream"
        )
        assert upload_request.filename == "test.exe"
        
        # Invalid filename characters
        with pytest.raises(ValueError, match="filename contains invalid characters"):
            FileUploadRequest(
                filename="test<>.exe",
                file_size=1024,
                content_type="application/octet-stream"
            )
        
        # Filename too long
        with pytest.raises(ValueError, match="filename is too long"):
            FileUploadRequest(
                filename="a" * 300 + ".exe",
                file_size=1024,
                content_type="application/octet-stream"
            )
    
    def test_content_type_validation(self):
        """Test content type validation."""
        valid_content_types = [
            "application/octet-stream",
            "application/x-executable",
            "application/x-dosexec",
            "application/vnd.microsoft.portable-executable"
        ]
        
        for content_type in valid_content_types:
            upload_request = FileUploadRequest(
                filename="test.exe",
                file_size=1024,
                content_type=content_type
            )
            assert upload_request.content_type == content_type


class TestFileUploadResponse:
    """Test cases for FileUploadResponse model."""
    
    def test_basic_instantiation(self):
        """Test basic upload response creation."""
        response = FileUploadResponse(
            upload_id="upload_123",
            presigned_url="https://storage.example.com/upload_123",
            expires_at=datetime.now(timezone.utc)
        )
        
        assert response.upload_id == "upload_123"
        assert response.presigned_url.startswith("https://")
        assert isinstance(response.expires_at, datetime)
        assert response.max_file_size == 100 * 1024 * 1024  # Default 100MB
    
    def test_with_custom_limits(self):
        """Test upload response with custom limits."""
        response = FileUploadResponse(
            upload_id="upload_456",
            presigned_url="https://storage.example.com/upload_456",
            expires_at=datetime.now(timezone.utc),
            max_file_size=50 * 1024 * 1024,  # 50MB
            allowed_extensions=[".exe", ".dll", ".so"]
        )
        
        assert response.max_file_size == 50 * 1024 * 1024
        assert ".exe" in response.allowed_extensions
        assert ".dll" in response.allowed_extensions
    
    def test_expiry_validation(self):
        """Test expiry time validation."""
        future_time = datetime.now(timezone.utc).replace(microsecond=0)  # Remove microseconds
        
        response = FileUploadResponse(
            upload_id="upload_789",
            presigned_url="https://storage.example.com/upload_789",
            expires_at=future_time
        )
        
        assert not response.is_expired()
        assert response.get_seconds_until_expiry() >= 0
    
    def test_instructions_generation(self):
        """Test upload instructions generation."""
        response = FileUploadResponse(
            upload_id="upload_123",
            presigned_url="https://storage.example.com/upload_123",
            expires_at=datetime.now(timezone.utc)
        )
        
        instructions = response.get_upload_instructions()
        assert isinstance(instructions, dict)
        assert "url" in instructions
        assert "method" in instructions
        assert "headers" in instructions
        assert instructions["method"] == "PUT"


class TestAnalysisSubmissionRequest:
    """Test cases for AnalysisSubmissionRequest model."""
    
    def test_basic_instantiation(self):
        """Test basic submission request."""
        request = AnalysisSubmissionRequest(
            file_reference="upload_123",
            filename="test.exe"
        )
        
        assert request.file_reference == "upload_123"
        assert request.filename == "test.exe"
        assert isinstance(request.config, AnalysisConfigRequest)
        assert request.metadata == {}
    
    def test_with_custom_config(self):
        """Test submission with custom configuration."""
        custom_config = AnalysisConfigRequest(
            depth=AnalysisDepth.QUICK,
            timeout_seconds=60,
            priority="high"
        )
        
        request = AnalysisSubmissionRequest(
            file_reference="upload_456",
            filename="quick_test.exe",
            config=custom_config
        )
        
        assert request.config.depth == AnalysisDepth.QUICK
        assert request.config.timeout_seconds == 60
        assert request.config.priority == "high"
    
    def test_with_metadata(self):
        """Test submission with metadata."""
        metadata = {
            "source": "api_client",
            "user_id": "user_123",
            "tags": ["production", "urgent"]
        }
        
        request = AnalysisSubmissionRequest(
            file_reference="upload_789",
            filename="prod.exe",
            metadata=metadata
        )
        
        assert request.metadata == metadata
        assert request.metadata["user_id"] == "user_123"
    
    def test_file_reference_validation(self):
        """Test file reference validation."""
        # Valid upload reference
        request = AnalysisSubmissionRequest(
            file_reference="upload_abc123",
            filename="test.exe"
        )
        assert request.file_reference == "upload_abc123"
        
        # Valid hash reference
        request = AnalysisSubmissionRequest(
            file_reference="a" * 64,  # SHA-256 hash
            filename="test.exe"
        )
        assert request.file_reference == "a" * 64
        
        # Invalid reference format
        with pytest.raises(ValueError, match="file_reference must be either"):
            AnalysisSubmissionRequest(
                file_reference="invalid_ref",
                filename="test.exe"
            )
    
    def test_request_validation(self):
        """Test overall request validation."""
        request = AnalysisSubmissionRequest(
            file_reference="upload_123",
            filename="test.exe"
        )
        
        validation_result = request.validate_request()
        assert validation_result.is_valid
        assert len(validation_result.errors) == 0


class TestAnalysisSummaryResponse:
    """Test cases for AnalysisSummaryResponse model."""
    
    def test_basic_instantiation(self):
        """Test basic summary response."""
        response = AnalysisSummaryResponse(
            success=True,
            analysis_id=uuid4(),
            file_info={
                "name": "test.exe",
                "size": 2048,
                "format": "pe",
                "platform": "windows"
            },
            summary={
                "function_count": 15,
                "import_count": 8,
                "string_count": 45,
                "risk_score": 3.5
            }
        )
        
        assert response.success is True
        assert isinstance(response.analysis_id, UUID)
        assert response.file_info["name"] == "test.exe"
        assert response.summary["function_count"] == 15
        assert isinstance(response.timestamp, datetime)
    
    def test_failed_analysis_response(self):
        """Test failed analysis response."""
        response = AnalysisSummaryResponse(
            success=False,
            analysis_id=uuid4(),
            file_info={
                "name": "corrupted.exe",
                "size": 0,
                "format": "unknown"
            },
            errors=[
                {
                    "type": "format_error",
                    "message": "Unable to parse file format",
                    "component": "file_parser"
                }
            ]
        )
        
        assert response.success is False
        assert len(response.errors) == 1
        assert response.errors[0]["type"] == "format_error"
        assert response.summary is None
    
    def test_with_detail_endpoints(self):
        """Test response with detail endpoint URLs."""
        response = AnalysisSummaryResponse(
            success=True,
            analysis_id=uuid4(),
            file_info={"name": "test.exe"},
            summary={"function_count": 10},
            detail_endpoints={
                "functions": "/api/v1/analysis/123/functions",
                "imports": "/api/v1/analysis/123/imports",
                "strings": "/api/v1/analysis/123/strings",
                "security": "/api/v1/analysis/123/security"
            }
        )
        
        assert response.detail_endpoints is not None
        assert "/functions" in response.detail_endpoints["functions"]
        assert "/security" in response.detail_endpoints["security"]
    
    def test_processing_metadata(self):
        """Test processing metadata inclusion."""
        metadata = {
            "processing_time_ms": 45000,
            "worker_id": "worker_001", 
            "engine_version": "1.0.0",
            "analysis_depth": "standard"
        }
        
        response = AnalysisSummaryResponse(
            success=True,
            analysis_id=uuid4(),
            file_info={"name": "test.exe"},
            summary={"function_count": 20},
            metadata=metadata
        )
        
        assert response.metadata == metadata
        assert response.metadata["processing_time_ms"] == 45000
        assert response.metadata["worker_id"] == "worker_001"
    
    def test_serialization_with_openapi_fields(self):
        """Test serialization includes OpenAPI documentation fields."""
        response = AnalysisSummaryResponse(
            success=True,
            analysis_id=uuid4(),
            file_info={"name": "test.exe", "size": 1024},
            summary={"function_count": 5}
        )
        
        # Test model schema includes OpenAPI documentation
        schema = response.model_json_schema()
        assert "properties" in schema
        assert "success" in schema["properties"]
        assert "analysis_id" in schema["properties"]
        
        # Test serialization preserves all fields
        serialized = response.to_dict()
        assert serialized["success"] is True
        assert "analysis_id" in serialized
        assert "timestamp" in serialized


class TestAnalysisDetailResponse:
    """Test cases for AnalysisDetailResponse model."""
    
    def test_functions_detail_response(self):
        """Test functions detail response."""
        functions_data = [
            {
                "name": "main",
                "address": "0x401000",
                "size": 256,
                "calls_to": ["helper", "cleanup"],
                "calls_from": ["_start"],
                "is_exported": False
            },
            {
                "name": "DllMain", 
                "address": "0x402000",
                "size": 128,
                "calls_to": [],
                "calls_from": [],
                "is_exported": True
            }
        ]
        
        response = AnalysisDetailResponse(
            analysis_id=uuid4(),
            detail_type="functions",
            data=functions_data,
            total_count=2
        )
        
        assert response.detail_type == "functions"
        assert len(response.data) == 2
        assert response.total_count == 2
        assert response.data[0]["name"] == "main"
        assert response.data[1]["is_exported"] is True
    
    def test_imports_detail_response(self):
        """Test imports detail response."""
        imports_data = [
            {
                "library": "kernel32.dll",
                "function": "CreateFileA",
                "address": "0x405000",
                "ordinal": None,
                "is_delayed": False
            },
            {
                "library": "user32.dll",
                "function": "MessageBoxW",
                "address": "0x405010", 
                "ordinal": 123,
                "is_delayed": True
            }
        ]
        
        response = AnalysisDetailResponse(
            analysis_id=uuid4(),
            detail_type="imports",
            data=imports_data,
            total_count=2
        )
        
        assert response.detail_type == "imports"
        assert response.data[0]["library"] == "kernel32.dll"
        assert response.data[1]["ordinal"] == 123
        assert response.data[1]["is_delayed"] is True
    
    def test_security_detail_response(self):
        """Test security findings detail response."""
        security_data = {
            "risk_score": 7.2,
            "risk_level": "high",
            "findings": [
                {
                    "category": "network_behavior",
                    "finding": "Outbound HTTP connections detected",
                    "severity": "medium",
                    "details": {"urls": ["http://example.com/check"]}
                },
                {
                    "category": "suspicious_behavior", 
                    "finding": "Code injection patterns detected",
                    "severity": "high",
                    "details": {"apis": ["VirtualAlloc", "WriteProcessMemory"]}
                }
            ],
            "mitigations": [
                "Monitor network connections",
                "Enable DEP and ASLR",
                "Use application sandboxing"
            ]
        }
        
        response = AnalysisDetailResponse(
            analysis_id=uuid4(),
            detail_type="security",
            data=security_data
        )
        
        assert response.detail_type == "security"
        assert response.data["risk_score"] == 7.2
        assert response.data["risk_level"] == "high"
        assert len(response.data["findings"]) == 2
        assert len(response.data["mitigations"]) == 3
    
    def test_with_pagination(self):
        """Test detail response with pagination."""
        large_dataset = [{"id": i, "data": f"item_{i}"} for i in range(100)]
        
        response = AnalysisDetailResponse(
            analysis_id=uuid4(),
            detail_type="strings",
            data=large_dataset[:20],  # First page
            total_count=100,
            pagination={
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "has_next": True,
                "has_previous": False
            }
        )
        
        assert response.pagination is not None
        assert response.pagination["page"] == 1
        assert response.pagination["total_pages"] == 5
        assert response.pagination["has_next"] is True
        assert response.pagination["has_previous"] is False
    
    def test_with_filters_applied(self):
        """Test detail response with applied filters."""
        filtered_data = [
            {"name": "main", "type": "internal"},
            {"name": "helper", "type": "internal"}
        ]
        
        response = AnalysisDetailResponse(
            analysis_id=uuid4(),
            detail_type="functions",
            data=filtered_data,
            total_count=2,
            filters_applied={
                "function_type": "internal",
                "min_size": 64,
                "exclude_imports": True
            }
        )
        
        assert response.filters_applied is not None
        assert response.filters_applied["function_type"] == "internal"
        assert response.filters_applied["min_size"] == 64
    
    def test_detail_response_validation(self):
        """Test detail response validation."""
        response = AnalysisDetailResponse(
            analysis_id=uuid4(),
            detail_type="functions",
            data=[{"name": "test"}],
            total_count=1
        )
        
        # Validate the response structure
        schema = response.model_json_schema()
        assert "properties" in schema
        assert "analysis_id" in schema["properties"]
        assert "detail_type" in schema["properties"]
        assert "data" in schema["properties"]