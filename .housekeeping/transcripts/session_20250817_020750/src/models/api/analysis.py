"""
API models for binary analysis endpoints.

Provides request/response models for analysis submission, status checking,
and result retrieval endpoints.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field, ConfigDict
from typing_extensions import Annotated

from ..shared.base import BaseModel
from ..shared.enums import AnalysisDepth, AnalysisFocus, Platform, FileFormat, JobStatus
from ..analysis.serialization import AnalysisModelMixin, validate_string_list


class AnalysisSubmissionRequest(BaseModel, AnalysisModelMixin):
    """
    Request model for submitting a binary file for analysis.
    
    Used by the POST /api/v1/analyze endpoint to accept file uploads
    and analysis configuration.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Analysis Submission Request",
            "description": "Request to analyze a binary file with configurable analysis parameters and options",
            "examples": [
                {
                    "filename": "sample.exe",
                    "analysis_depth": "standard",
                    "focus_areas": ["security", "functions"],
                    "timeout_seconds": 300,
                    "enable_security_scan": True,
                    "enable_function_analysis": True,
                    "priority": "normal",
                    "platform_hint": "windows",
                    "format_hint": "pe",
                    "metadata": {
                        "source": "user_upload",
                        "project": "security-review"
                    },
                    "tags": ["production", "malware-analysis"]
                },
                {
                    "filename": "library.so",
                    "analysis_depth": "comprehensive",
                    "focus_areas": ["functions", "strings", "imports"],
                    "timeout_seconds": 600,
                    "enable_security_scan": False,
                    "max_functions": 1000,
                    "max_strings": 5000,
                    "priority": "low",
                    "custom_patterns": ["API_.*", ".*_encrypt.*"],
                    "callback_url": "https://api.example.com/webhook"
                }
            ]
        }
    )
    
    filename: Annotated[str, Field(
        description="Name of the file being analyzed",
        min_length=1,
        max_length=255,
        examples=["malware.exe", "library.dll", "binary.elf", "app.bin"]
    )]
    
    analysis_depth: AnalysisDepth = Field(
        default=AnalysisDepth.STANDARD,
        description="Depth of analysis to perform"
    )
    
    focus_areas: Annotated[List[AnalysisFocus], Field(
        default_factory=lambda: [AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS],
        description="Specific areas to focus analysis on. Available areas: security, functions, strings, imports, exports, metadata",
        examples=[["security", "functions"], ["strings", "imports"], ["security"]]
    )]
    
    timeout_seconds: Optional[int] = Field(
        default=None,
        ge=30,
        le=1200,
        description="Maximum analysis time in seconds"
    )
    
    enable_security_scan: bool = Field(
        default=True,
        description="Whether to perform security pattern detection"
    )
    
    enable_function_analysis: bool = Field(
        default=True,
        description="Whether to perform function detection and analysis"
    )
    
    enable_string_extraction: bool = Field(
        default=True,
        description="Whether to extract and analyze strings"
    )
    
    max_functions: Optional[int] = Field(
        default=None,
        ge=1,
        le=50000,
        description="Maximum number of functions to analyze"
    )
    
    max_strings: Optional[int] = Field(
        default=None,
        ge=1,
        le=100000,
        description="Maximum number of strings to extract"
    )
    
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
        description="Analysis priority level"
    )
    
    platform_hint: Optional[Platform] = Field(
        default=None,
        description="Platform hint to guide analysis"
    )
    
    format_hint: Optional[FileFormat] = Field(
        default=None,
        description="File format hint to guide analysis"
    )
    
    force_reanalysis: bool = Field(
        default=False,
        description="Force re-analysis even if cached results exist"
    )
    
    custom_patterns: List[str] = Field(
        default_factory=list,
        description="Custom regex patterns for specialized detection"
    )
    
    callback_url: Optional[str] = Field(
        default=None,
        description="URL to receive analysis completion notification"
    )
    
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracking related requests"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the analysis request"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing the analysis request"
    )
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename."""
        v = v.strip()
        if not v:
            raise ValueError("Filename cannot be empty")
        
        # Check for problematic characters
        problematic_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        if any(char in v for char in problematic_chars):
            raise ValueError("Filename contains invalid characters")
        
        return v
    
    @field_validator('focus_areas')
    @classmethod
    def validate_focus_areas(cls, v: List[AnalysisFocus]) -> List[AnalysisFocus]:
        """Validate focus areas."""
        if not v:
            raise ValueError("At least one focus area must be specified")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_areas = []
        for area in v:
            if area not in seen:
                seen.add(area)
                unique_areas.append(area)
        
        return unique_areas
    
    @field_validator('custom_patterns')
    @classmethod
    def validate_custom_patterns(cls, v: List[str]) -> List[str]:
        """Validate custom regex patterns."""
        return validate_string_list(v, max_items=20)
    
    @field_validator('callback_url')
    @classmethod
    def validate_callback_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate callback URL format."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
        
        # Basic URL validation
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("Callback URL must start with http:// or https://")
        
        if len(v) > 500:
            raise ValueError("Callback URL too long (max 500 characters)")
        
        return v
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        return validate_string_list(v, max_items=10)
    
    @field_validator('metadata')
    @classmethod
    def validate_metadata(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metadata size and content."""
        if len(v) > 20:
            raise ValueError("Too many metadata fields (max 20)")
        
        for key, value in v.items():
            if len(str(key)) > 50:
                raise ValueError(f"Metadata key too long: {key}")
            if isinstance(value, str) and len(value) > 500:
                raise ValueError(f"Metadata value too long for key: {key}")
        
        return v
    
    @computed_field
    @property
    def estimated_duration_seconds(self) -> int:
        """Estimate analysis duration based on configuration."""
        if self.timeout_seconds:
            return self.timeout_seconds
        
        base_time = AnalysisDepth.get_timeout_seconds(self.analysis_depth)
        
        # Adjust based on enabled features
        multiplier = 1.0
        if self.enable_security_scan:
            multiplier += 0.3
        if self.enable_function_analysis:
            multiplier += 0.2
        if self.enable_string_extraction:
            multiplier += 0.1
        
        return int(base_time * multiplier)
    
    def to_analysis_config(self):
        """Convert to AnalysisConfig model."""
        from ..analysis.config import AnalysisConfig
        
        return AnalysisConfig(
            analysis_depth=self.analysis_depth,
            focus_areas=self.focus_areas,
            timeout_seconds=self.timeout_seconds or self.estimated_duration_seconds,
            enable_security_scan=self.enable_security_scan,
            enable_function_analysis=self.enable_function_analysis,
            enable_string_extraction=self.enable_string_extraction,
            max_functions=self.max_functions,
            max_strings=self.max_strings,
            force_reanalysis=self.force_reanalysis,
            custom_patterns=self.custom_patterns,
            platform_hint=self.platform_hint,
            format_hint=self.format_hint,
            priority=self.priority
        )
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "filename": self.filename,
            "analysis_depth": self.analysis_depth,
            "focus_areas": self.focus_areas,
            "estimated_duration": self.estimated_duration_seconds,
            "priority": self.priority,
            "enable_security_scan": self.enable_security_scan,
            "has_custom_patterns": len(self.custom_patterns) > 0,
            "has_callback": self.callback_url is not None,
            "tag_count": len(self.tags),
            "metadata_fields": len(self.metadata)
        }


class AnalysisSubmissionResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for successful analysis submission.
    
    Returned by POST /api/v1/analyze endpoint after accepting
    a file for analysis.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Analysis Submission Response",
            "description": "Response after successfully submitting a file for analysis",
            "examples": [
                {
                    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "pending",
                    "filename": "sample.exe",
                    "estimated_duration_seconds": 300,
                    "estimated_completion_time": "2024-01-15T14:30:00Z",
                    "status_url": "/api/v1/analyze/550e8400-e29b-41d4-a716-446655440000",
                    "result_url": None,
                    "priority": "normal",
                    "queue_position": 3,
                    "submission_time": "2024-01-15T14:25:00Z"
                }
            ]
        }
    )
    
    analysis_id: str = Field(
        description="Unique identifier for the analysis job"
    )
    
    status: JobStatus = Field(
        description="Current status of the analysis"
    )
    
    filename: str = Field(
        description="Name of the file being analyzed"
    )
    
    estimated_duration_seconds: int = Field(
        description="Estimated analysis duration in seconds"
    )
    
    estimated_completion_time: datetime = Field(
        description="Estimated completion time"
    )
    
    status_url: str = Field(
        description="URL to check analysis status"
    )
    
    result_url: Optional[str] = Field(
        default=None,
        description="URL to retrieve results (available when complete)"
    )
    
    priority: str = Field(
        description="Analysis priority level"
    )
    
    queue_position: Optional[int] = Field(
        default=None,
        description="Position in analysis queue"
    )
    
    submission_time: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Time when analysis was submitted"
    )
    
    @computed_field
    @property
    def is_queued(self) -> bool:
        """Check if analysis is queued."""
        return self.status == JobStatus.PENDING
    
    @computed_field
    @property
    def is_processing(self) -> bool:
        """Check if analysis is currently processing."""
        return self.status == JobStatus.PROCESSING
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "analysis_id": self.analysis_id,
            "status": self.status,
            "filename": self.filename,
            "estimated_duration": self.estimated_duration_seconds,
            "priority": self.priority,
            "is_queued": self.is_queued,
            "queue_position": self.queue_position,
            "submission_time": self.submission_time.isoformat()
        }


class AnalysisSummaryResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for analysis summary information.
    
    Returned by GET /api/v1/analyze/{id} endpoint for basic
    analysis status and summary data.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Analysis Summary Response",
            "description": "Summary of analysis results with key metrics and status information",
            "examples": [
                {
                    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "completed",
                    "filename": "sample.exe",
                    "file_size": 1048576,
                    "file_format": "pe",
                    "platform": "windows",
                    "architecture": "x86_64",
                    "success": True,
                    "analysis_duration_seconds": 45.2,
                    "function_count": 127,
                    "security_findings_count": 3,
                    "critical_findings_count": 1,
                    "string_count": 245,
                    "import_count": 23,
                    "export_count": 5,
                    "overall_risk_score": 6.5,
                    "confidence_score": 0.92,
                    "submission_time": "2024-01-15T14:20:00Z",
                    "start_time": "2024-01-15T14:22:00Z",
                    "completion_time": "2024-01-15T14:25:30Z",
                    "warning_count": 1
                },
                {
                    "analysis_id": "660f9511-f3ac-52e5-b827-557766551111",
                    "status": "processing",
                    "filename": "library.dll",
                    "file_size": 524288,
                    "file_format": "pe",
                    "platform": "windows",
                    "success": False,
                    "analysis_duration_seconds": None,
                    "function_count": 0,
                    "security_findings_count": 0,
                    "string_count": 0,
                    "overall_risk_score": 0.0,
                    "submission_time": "2024-01-15T14:30:00Z",
                    "start_time": "2024-01-15T14:32:00Z"
                }
            ]
        }
    )
    
    analysis_id: str = Field(
        description="Unique identifier for the analysis"
    )
    
    status: JobStatus = Field(
        description="Current analysis status"
    )
    
    filename: str = Field(
        description="Name of the analyzed file"
    )
    
    file_size: int = Field(
        description="Size of the analyzed file in bytes"
    )
    
    file_format: FileFormat = Field(
        description="Detected file format"
    )
    
    platform: Platform = Field(
        description="Target platform"
    )
    
    architecture: Optional[str] = Field(
        default=None,
        description="Processor architecture"
    )
    
    success: bool = Field(
        description="Whether analysis completed successfully"
    )
    
    analysis_duration_seconds: Optional[float] = Field(
        default=None,
        description="Actual analysis duration in seconds"
    )
    
    function_count: int = Field(
        default=0,
        description="Number of functions discovered"
    )
    
    security_findings_count: int = Field(
        default=0,
        description="Number of security findings"
    )
    
    critical_findings_count: int = Field(
        default=0,
        description="Number of critical security findings"
    )
    
    string_count: int = Field(
        default=0,
        description="Number of strings extracted"
    )
    
    import_count: int = Field(
        default=0,
        description="Number of imported functions"
    )
    
    export_count: int = Field(
        default=0,
        description="Number of exported functions"
    )
    
    overall_risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Overall risk score (0.0-10.0)"
    )
    
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in analysis results"
    )
    
    submission_time: datetime = Field(
        description="Time when analysis was submitted"
    )
    
    start_time: Optional[datetime] = Field(
        default=None,
        description="Time when analysis started processing"
    )
    
    completion_time: Optional[datetime] = Field(
        default=None,
        description="Time when analysis completed"
    )
    
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if analysis failed"
    )
    
    warning_count: int = Field(
        default=0,
        description="Number of warnings generated"
    )
    
    @computed_field
    @property
    def is_complete(self) -> bool:
        """Check if analysis is complete."""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED]
    
    @computed_field
    @property
    def has_critical_findings(self) -> bool:
        """Check if there are critical security findings."""
        return self.critical_findings_count > 0
    
    @computed_field
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return round(self.file_size / (1024 * 1024), 2)
    
    @computed_field
    @property
    def progress_percentage(self) -> Optional[int]:
        """Calculate progress percentage if applicable."""
        if self.status == JobStatus.COMPLETED:
            return 100
        elif self.status == JobStatus.FAILED:
            return 0
        elif self.status == JobStatus.PROCESSING:
            # Estimate based on elapsed time vs expected duration
            if self.start_time and self.analysis_duration_seconds:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                progress = min(95, int((elapsed / self.analysis_duration_seconds) * 100))
                return progress
        return None
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "analysis_id": self.analysis_id,
            "status": self.status,
            "filename": self.filename,
            "file_size_mb": self.file_size_mb,
            "file_format": self.file_format,
            "platform": self.platform,
            "success": self.success,
            "function_count": self.function_count,
            "security_findings_count": self.security_findings_count,
            "has_critical_findings": self.has_critical_findings,
            "overall_risk_score": self.overall_risk_score,
            "confidence_score": self.confidence_score,
            "is_complete": self.is_complete,
            "progress_percentage": self.progress_percentage
        }


class AnalysisDetailResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for detailed analysis results.
    
    Returned by GET /api/v1/analyze/{id}/details endpoint
    with complete analysis data.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Analysis Detail Response",
            "description": "Complete analysis results with detailed findings, functions, and metadata",
            "examples": [
                {
                    "analysis_id": "550e8400-e29b-41d4-a716-446655440000",
                    "summary": {
                        "status": "completed",
                        "filename": "sample.exe",
                        "success": True,
                        "overall_risk_score": 6.5
                    },
                    "functions": [
                        {
                            "name": "main",
                            "address": "0x401000",
                            "size": 256,
                            "calls": 15,
                            "complexity": "medium"
                        },
                        {
                            "name": "WinMain",
                            "address": "0x401100",
                            "size": 512,
                            "calls": 8,
                            "complexity": "low"
                        }
                    ],
                    "security_findings": {
                        "total_findings": 3,
                        "by_severity": {
                            "critical": 1,
                            "high": 0,
                            "medium": 2,
                            "low": 0
                        },
                        "findings": [
                            {
                                "type": "suspicious_api",
                                "severity": "critical",
                                "description": "Use of VirtualAllocEx API",
                                "address": "0x401230"
                            }
                        ]
                    },
                    "strings": [
                        {
                            "content": "http://malicious.example.com",
                            "address": "0x402000",
                            "type": "url",
                            "significance": "high"
                        }
                    ],
                    "imports": [
                        {
                            "library": "kernel32.dll",
                            "function": "VirtualAllocEx",
                            "address": "0x403000"
                        }
                    ],
                    "file_metadata": {
                        "hash": "sha256:abc123...",
                        "size": 1048576,
                        "format": "pe",
                        "platform": "windows"
                    },
                    "errors": [],
                    "warnings": ["Some functions could not be analyzed"],
                    "metadata": {
                        "analysis_version": "1.0.0",
                        "engine_version": "radare2-5.8.0",
                        "scan_time": "2024-01-15T14:25:30Z"
                    }
                }
            ]
        }
    )
    
    analysis_id: str = Field(
        description="Unique identifier for the analysis"
    )
    
    summary: AnalysisSummaryResponse = Field(
        description="Analysis summary information"
    )
    
    functions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Discovered functions"
    )
    
    security_findings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Security analysis results"
    )
    
    strings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Extracted strings"
    )
    
    imports: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Imported functions and libraries"
    )
    
    exports: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Exported functions"
    )
    
    file_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="File metadata and properties"
    )
    
    analysis_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Analysis configuration used"
    )
    
    errors: List[str] = Field(
        default_factory=list,
        description="Errors encountered during analysis"
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings generated during analysis"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional analysis metadata"
    )
    
    @computed_field
    @property
    def has_functions(self) -> bool:
        """Check if functions were discovered."""
        return len(self.functions) > 0
    
    @computed_field
    @property
    def has_security_findings(self) -> bool:
        """Check if security findings exist."""
        return len(self.security_findings) > 0
    
    @computed_field
    @property
    def has_errors(self) -> bool:
        """Check if errors occurred."""
        return len(self.errors) > 0
    
    @computed_field
    @property
    def data_size_estimate(self) -> int:
        """Estimate response data size in bytes."""
        # Rough estimation for API response planning
        size = 0
        size += len(str(self.summary)) * 2  # JSON overhead
        size += len(self.functions) * 200  # Average function size
        size += len(self.strings) * 100    # Average string size
        size += len(self.imports) * 50     # Average import size
        size += len(self.exports) * 50     # Average export size
        return size
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "analysis_id": self.analysis_id,
            "summary": self.summary.to_summary_dict(),
            "data_counts": {
                "functions": len(self.functions),
                "security_findings": len(self.security_findings),
                "strings": len(self.strings),
                "imports": len(self.imports),
                "exports": len(self.exports)
            },
            "has_errors": self.has_errors,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "estimated_size_kb": round(self.data_size_estimate / 1024, 1)
        }
    
    def to_compact_response(self) -> Dict[str, Any]:
        """Create compact response excluding large data arrays."""
        return {
            "analysis_id": self.analysis_id,
            "summary": self.summary.to_summary_dict(),
            "function_count": len(self.functions),
            "security_summary": self.security_findings.get("summary", {}),
            "string_count": len(self.strings),
            "import_count": len(self.imports),
            "export_count": len(self.exports),
            "file_metadata": self.file_metadata,
            "analysis_config": self.analysis_config,
            "has_errors": self.has_errors,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_analysis_result(cls, analysis_result) -> 'AnalysisDetailResponse':
        """Create response from AnalysisResult model."""
        from ..analysis.results import AnalysisResult
        
        if not isinstance(analysis_result, AnalysisResult):
            raise ValueError("Expected AnalysisResult instance")
        
        # Create summary
        summary = AnalysisSummaryResponse(
            analysis_id=analysis_result.analysis_id,
            status=JobStatus.COMPLETED if analysis_result.success else JobStatus.FAILED,
            filename=f"file_{analysis_result.analysis_id[:8]}",  # Placeholder
            file_size=analysis_result.file_size,
            file_format=analysis_result.file_format,
            platform=analysis_result.platform,
            architecture=analysis_result.architecture,
            success=analysis_result.success,
            analysis_duration_seconds=analysis_result.analysis_duration_seconds,
            function_count=len(analysis_result.functions),
            security_findings_count=len(analysis_result.security_findings.findings),
            critical_findings_count=len(analysis_result.security_findings.get_findings_by_severity("critical")),
            string_count=len(analysis_result.strings),
            import_count=len(analysis_result.imports),
            export_count=len(analysis_result.exports),
            overall_risk_score=analysis_result.security_findings.overall_risk_score,
            confidence_score=analysis_result.overall_confidence,
            submission_time=analysis_result.created_at,
            completion_time=analysis_result.updated_at or analysis_result.created_at,
            warning_count=len(analysis_result.warnings)
        )
        
        # Convert functions to API format
        functions = [func.function_summary for func in analysis_result.functions]
        
        # Convert security findings to API format
        security_findings = analysis_result.security_findings.security_summary
        
        # Convert strings to API format
        strings = [
            {
                "content": s.content,
                "address": s.address,
                "type": s.string_type,
                "significance": s.significance
            }
            for s in analysis_result.strings
        ]
        
        return cls(
            analysis_id=analysis_result.analysis_id,
            summary=summary,
            functions=functions,
            security_findings=security_findings,
            strings=strings,
            imports=analysis_result.imports,
            exports=analysis_result.exports,
            file_metadata={
                "hash": analysis_result.file_hash,
                "size": analysis_result.file_size,
                "format": analysis_result.file_format,
                "platform": analysis_result.platform,
                "architecture": analysis_result.architecture
            },
            analysis_config=analysis_result.analysis_config_summary,
            errors=analysis_result.errors,
            warnings=analysis_result.warnings,
            metadata=analysis_result.analysis_metadata
        )


class FileUploadRequest(BaseModel, AnalysisModelMixin):
    """
    Request model for file upload endpoints.
    
    Used for both direct file uploads and pre-signed URL generation
    to handle file transfer before analysis.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "filename": "sample.exe",
                    "file_size": 1048576,
                    "file_hash": "sha256:abc123...",
                    "upload_type": "direct",
                    "expires_in_seconds": 3600
                }
            ]
        }
    )
    
    filename: str = Field(
        description="Original filename"
    )
    
    file_size: int = Field(
        ge=1,
        le=100 * 1024 * 1024,  # 100MB limit
        description="Size of file in bytes"
    )
    
    file_hash: Optional[str] = Field(
        default=None,
        description="Hash of file content for integrity verification"
    )
    
    upload_type: str = Field(
        default="direct",
        pattern="^(direct|presigned_url)$",
        description="Type of upload method"
    )
    
    expires_in_seconds: int = Field(
        default=3600,
        ge=300,
        le=86400,  # Max 24 hours
        description="Upload session expiration time"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional upload metadata"
    )
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename."""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Filename too long")
        
        # Check for problematic characters
        problematic_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        if any(char in v for char in problematic_chars):
            raise ValueError("Filename contains invalid characters")
        
        return v


class FileUploadResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for file upload operations.
    
    Contains upload session information, URLs, and processing status
    for file upload workflows.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "upload_id": "upload_12345",
                    "file_reference": "upload://abc123def456",
                    "upload_url": "https://api.example.com/upload/abc123",
                    "status": "pending",
                    "expires_at": "2024-01-01T11:00:00Z"
                }
            ]
        }
    )
    
    upload_id: str = Field(
        description="Unique upload session identifier"
    )
    
    file_reference: str = Field(
        description="Reference to uploaded file"
    )
    
    upload_url: Optional[str] = Field(
        default=None,
        description="Pre-signed URL for file upload (if using presigned method)"
    )
    
    status: str = Field(
        default="pending",
        pattern="^(pending|uploading|uploaded|validated|failed|expired)$",
        description="Current upload status"
    )
    
    expires_at: datetime = Field(
        description="When upload session expires"
    )
    
    max_file_size: int = Field(
        description="Maximum allowed file size for this upload"
    )
    
    allowed_formats: List[str] = Field(
        default_factory=list,
        description="Allowed file formats"
    )
    
    upload_instructions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Instructions for completing the upload"
    )
    
    validation_rules: Dict[str, Any] = Field(
        default_factory=dict,
        description="File validation rules"
    )
    
    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if upload session has expired."""
        return datetime.now() > self.expires_at
    
    @computed_field
    @property
    def time_remaining_seconds(self) -> int:
        """Get remaining time in seconds."""
        if self.is_expired:
            return 0
        return int((self.expires_at - datetime.now()).total_seconds())


class AnalysisConfigRequest(BaseModel, AnalysisModelMixin):
    """
    Request model for analysis configuration endpoints.
    
    Used to validate, customize, and retrieve analysis configuration
    options without submitting files.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_size_mb": 5.2,
                    "file_format": "pe",
                    "platform": "windows",
                    "requested_depth": "comprehensive",
                    "focus_areas": ["security", "functions"],
                    "constraints": {
                        "max_timeout": 600,
                        "memory_limit_mb": 1024
                    }
                }
            ]
        }
    )
    
    file_size_mb: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="File size in MB for configuration optimization"
    )
    
    file_format: Optional[FileFormat] = Field(
        default=None,
        description="File format for format-specific configuration"
    )
    
    platform: Optional[Platform] = Field(
        default=None,
        description="Target platform for platform-specific configuration"
    )
    
    requested_depth: Optional[AnalysisDepth] = Field(
        default=None,
        description="Requested analysis depth"
    )
    
    focus_areas: List[AnalysisFocus] = Field(
        default_factory=list,
        description="Requested focus areas"
    )
    
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="User or system constraints"
    )
    
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="User preferences and options"
    )
    
    @computed_field
    @property
    def optimization_hints(self) -> Dict[str, Any]:
        """Get optimization hints based on provided information."""
        hints = {}
        
        if self.file_size_mb:
            if self.file_size_mb > 10:
                hints["large_file"] = True
                hints["recommended_timeout"] = 900
            elif self.file_size_mb < 1:
                hints["small_file"] = True
                hints["recommended_timeout"] = 60
        
        if self.file_format:
            if self.file_format == FileFormat.PE:
                hints["windows_specific"] = True
            elif self.file_format == FileFormat.ELF:
                hints["linux_specific"] = True
        
        if self.platform:
            hints["platform_optimizations"] = str(self.platform)
        
        return hints
    
    def get_recommended_config(self) -> Dict[str, Any]:
        """Get recommended analysis configuration."""
        config = {
            "analysis_depth": self.requested_depth or AnalysisDepth.STANDARD,
            "focus_areas": self.focus_areas or [AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS],
            "enable_security_scan": True,
            "enable_function_analysis": True,
            "enable_string_extraction": True
        }
        
        # Optimize based on file size
        if self.file_size_mb:
            if self.file_size_mb > 20:
                config["timeout_seconds"] = 900
                config["max_functions"] = 5000
            elif self.file_size_mb < 1:
                config["timeout_seconds"] = 120
                config["max_functions"] = 500
        
        # Apply constraints
        if "max_timeout" in self.constraints:
            config["timeout_seconds"] = min(
                config.get("timeout_seconds", 300),
                self.constraints["max_timeout"]
            )
        
        # Apply preferences
        config.update(self.preferences)
        
        return config