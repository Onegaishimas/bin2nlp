"""
Analysis configuration models for binary analysis operations.

Provides models for configuring analysis depth, focus areas, timeouts,
and other parameters that control binary analysis behavior.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import Field, field_validator, computed_field, ConfigDict, field_serializer

from ..shared.base import BaseModel, TimestampedModel
from ..shared.enums import AnalysisDepth, AnalysisFocus, Platform, FileFormat, get_file_format_from_extension
from .serialization import AnalysisModelMixin, validate_string_list, validate_confidence_score


class AnalysisConfig(BaseModel, AnalysisModelMixin):
    """
    Configuration for binary analysis operations.
    
    Defines analysis parameters including depth, timeout, focus areas,
    and various options that control analysis behavior.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "analysis_depth": "standard",
                    "focus_areas": ["security", "functions"],
                    "timeout_seconds": 300,
                    "enable_security_scan": True,
                    "max_functions": 1000
                }
            ]
        }
    )
    
    analysis_depth: AnalysisDepth = Field(
        default=AnalysisDepth.STANDARD,
        description="Level of analysis depth to perform"
    )
    
    focus_areas: List[AnalysisFocus] = Field(
        default_factory=lambda: [AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS, AnalysisFocus.STRINGS],
        description="Specific areas to focus analysis on"
    )
    
    timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=1200,
        description="Maximum time to spend on analysis in seconds"
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
        default=10000,
        ge=1,
        le=50000,
        description="Maximum number of functions to analyze"
    )
    
    max_strings: Optional[int] = Field(
        default=50000,
        ge=1,
        le=100000,
        description="Maximum number of strings to extract"
    )
    
    min_string_length: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Minimum length for string extraction"
    )
    
    force_reanalysis: bool = Field(
        default=False,
        description="Force re-analysis even if cached results exist"
    )
    
    custom_patterns: List[str] = Field(
        default_factory=list,
        description="Custom regex patterns for specialized detection"
    )
    
    platform_hint: Optional[Platform] = Field(
        default=None,
        description="Platform hint to guide analysis decisions"
    )
    
    format_hint: Optional[FileFormat] = Field(
        default=None,
        description="File format hint to guide analysis decisions"
    )
    
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
        description="Analysis priority level"
    )
    
    @field_validator('focus_areas')
    @classmethod
    def validate_focus_areas(cls, v: List[AnalysisFocus]) -> List[AnalysisFocus]:
        """Validate focus areas list."""
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
    
    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout_with_depth(cls, v: int, info) -> int:
        """Validate timeout is appropriate for analysis depth."""
        if hasattr(info, 'data') and 'analysis_depth' in info.data:
            depth = info.data['analysis_depth']
            recommended_timeout = AnalysisDepth.get_timeout_seconds(depth)
            
            # Allow timeout but warn if it's very different from recommended
            if v < recommended_timeout * 0.5:
                # This would be logged in a real implementation
                pass
            elif v > recommended_timeout * 3:
                # This would be logged in a real implementation  
                pass
        
        return v
    
    @field_validator('custom_patterns')
    @classmethod
    def validate_custom_patterns(cls, v: List[str]) -> List[str]:
        """Validate custom regex patterns."""
        import re
        validated_patterns = []
        
        for pattern in v:
            if not pattern.strip():
                continue
                
            try:
                # Test compile the regex to ensure it's valid
                re.compile(pattern)
                validated_patterns.append(pattern.strip())
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{pattern}': {e}")
        
        return validated_patterns
    
    @field_validator('priority')
    @classmethod
    def validate_priority_level(cls, v: str) -> str:
        """Validate priority level."""
        valid_priorities = ['low', 'normal', 'high', 'urgent']
        v = v.strip().lower()
        
        if v not in valid_priorities:
            raise ValueError(f"Invalid priority level: {v}. Must be one of {valid_priorities}")
        
        return v
    
    @field_validator('max_functions', 'max_strings')
    @classmethod
    def validate_max_limits(cls, v: Optional[int], info) -> Optional[int]:
        """Validate maximum limits for functions and strings."""
        if v is None:
            return v
        
        field_name = info.field_name
        if field_name == 'max_functions':
            if v < 1 or v > 50000:
                raise ValueError("max_functions must be between 1 and 50000")
        elif field_name == 'max_strings':
            if v < 1 or v > 100000:
                raise ValueError("max_strings must be between 1 and 100000")
        
        return v
    
    @field_serializer('focus_areas')
    def serialize_focus_areas(self, value: List[AnalysisFocus]) -> List[str]:
        """Serialize focus areas to string list."""
        return [str(area) for area in value]
    
    @field_serializer('analysis_depth')
    def serialize_analysis_depth(self, value: AnalysisDepth) -> str:
        """Serialize analysis depth to string."""
        return str(value)
    
    @field_serializer('platform_hint', 'format_hint')
    def serialize_enum_hints(self, value: Optional[Union[Platform, FileFormat]]) -> Optional[str]:
        """Serialize enum hints to strings."""
        return str(value) if value else None
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create summary for configuration."""
        return {
            "analysis_depth": str(self.analysis_depth),
            "focus_areas": [str(area) for area in self.focus_areas],
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority,
            "enable_security_scan": self.enable_security_scan,
            "estimated_duration": self.estimated_duration_seconds,
            "has_custom_patterns": len(self.custom_patterns) > 0
        }
    
    def validate_for_file_size(self, file_size_mb: float) -> List[str]:
        """Validate configuration against file size and return warnings."""
        warnings = []
        
        if file_size_mb > 50 and self.analysis_depth == AnalysisDepth.COMPREHENSIVE:
            warnings.append("Comprehensive analysis of large files may take significant time")
        
        if file_size_mb > 10 and self.timeout_seconds < 300:
            warnings.append("Timeout may be too short for large file analysis")
        
        if self.max_functions and self.max_functions < 100 and file_size_mb > 20:
            warnings.append("Function limit may be too low for large binaries")
        
        return warnings
    
    @computed_field
    @property
    def estimated_duration_seconds(self) -> int:
        """Estimate analysis duration based on configuration."""
        base_time = AnalysisDepth.get_timeout_seconds(self.analysis_depth)
        
        # Adjust based on enabled features
        multiplier = 1.0
        if self.enable_security_scan:
            multiplier += 0.3
        if self.enable_function_analysis:
            multiplier += 0.2
        if self.enable_string_extraction:
            multiplier += 0.1
        
        # Adjust based on focus areas
        if AnalysisFocus.ALL in self.focus_areas:
            multiplier += 0.5
        
        return int(base_time * multiplier)
    
    @computed_field
    @property
    def analysis_scope_summary(self) -> Dict[str, Any]:
        """Get summary of analysis scope."""
        return {
            "depth": self.analysis_depth,
            "focus_areas": [area for area in self.focus_areas],
            "security_enabled": self.enable_security_scan,
            "function_analysis_enabled": self.enable_function_analysis,
            "string_extraction_enabled": self.enable_string_extraction,
            "estimated_duration": self.estimated_duration_seconds,
            "has_custom_patterns": len(self.custom_patterns) > 0
        }
    
    def is_comprehensive_analysis(self) -> bool:
        """Check if this represents a comprehensive analysis."""
        return (
            self.analysis_depth == AnalysisDepth.COMPREHENSIVE and
            self.enable_security_scan and
            self.enable_function_analysis and
            self.enable_string_extraction and
            (AnalysisFocus.ALL in self.focus_areas or len(self.focus_areas) >= 4)
        )
    
    def get_cache_key_components(self) -> Dict[str, Any]:
        """Get components for cache key generation."""
        return {
            "depth": self.analysis_depth,
            "focus_areas": sorted([str(area) for area in self.focus_areas]),
            "security": self.enable_security_scan,
            "functions": self.enable_function_analysis,
            "strings": self.enable_string_extraction,
            "max_functions": self.max_functions,
            "max_strings": self.max_strings,
            "min_string_length": self.min_string_length,
            "custom_patterns": sorted(self.custom_patterns),
            "platform_hint": str(self.platform_hint) if self.platform_hint else None,
            "format_hint": str(self.format_hint) if self.format_hint else None
        }


class AnalysisRequest(TimestampedModel, AnalysisModelMixin):
    """
    Complete request for binary analysis including file reference and configuration.
    
    Represents a user's request to analyze a binary file with specific
    configuration parameters and metadata.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_reference": "upload://abc123def456",
                    "filename": "sample.exe",
                    "config": {
                        "analysis_depth": "standard",
                        "focus_areas": ["security", "functions"],
                        "timeout_seconds": 300
                    },
                    "metadata": {
                        "source": "security_audit",
                        "tags": ["production", "critical"]
                    }
                }
            ]
        }
    )
    
    file_reference: str = Field(
        description="Reference to the uploaded file (path, URL, or identifier)"
    )
    
    filename: str = Field(
        description="Original filename of the binary file"
    )
    
    config: AnalysisConfig = Field(
        default_factory=AnalysisConfig,
        description="Analysis configuration parameters"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the analysis request"
    )
    
    requester_id: Optional[str] = Field(
        default=None,
        description="Identifier of the user or system making the request"
    )
    
    correlation_id: Optional[str] = Field(
        default=None,
        description="Correlation ID for tracking related requests"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing and organizing analysis requests"
    )
    
    @field_validator('file_reference')
    @classmethod
    def validate_file_reference(cls, v: str) -> str:
        """Validate file reference format."""
        if not v or not v.strip():
            raise ValueError("File reference cannot be empty")
        
        v = v.strip()
        
        # Check for valid reference patterns
        valid_prefixes = ['file://', 'upload://', 'http://', 'https://', '/']
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            # Assume it's a local file path if no prefix
            if not v.startswith('/'):
                raise ValueError(
                    "File reference must be a valid path, URL, or identifier "
                    "(file://, upload://, http://, https://, or absolute path)"
                )
        
        return v
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename."""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        
        v = v.strip()
        
        # Check for reasonable filename constraints
        if len(v) > 255:
            raise ValueError("Filename too long (max 255 characters)")
        
        # Check for potentially problematic characters
        problematic_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        if any(char in v for char in problematic_chars):
            raise ValueError(f"Filename contains invalid characters: {problematic_chars}")
        
        return v
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        validated_tags = []
        
        for tag in v:
            if not isinstance(tag, str):
                continue
                
            tag = tag.strip().lower()
            if not tag:
                continue
                
            # Basic tag validation
            if len(tag) > 50:
                continue  # Skip overly long tags
                
            if tag not in validated_tags:
                validated_tags.append(tag)
        
        return validated_tags
    
    @field_validator('correlation_id')
    @classmethod
    def validate_correlation_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate correlation ID format."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
        
        # Basic validation - should be alphanumeric with hyphens/underscores
        if not all(c.isalnum() or c in '-_' for c in v):
            raise ValueError("Correlation ID can only contain alphanumeric characters, hyphens, and underscores")
        
        if len(v) > 100:
            raise ValueError("Correlation ID too long (max 100 characters)")
        
        return v
    
    @field_validator('metadata')
    @classmethod
    def validate_metadata_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metadata size and content."""
        if not v:
            return {}
        
        # Limit metadata size
        if len(v) > 50:
            raise ValueError("Too many metadata fields (max 50)")
        
        # Check individual field sizes
        for key, value in v.items():
            if len(str(key)) > 100:
                raise ValueError(f"Metadata key too long: {key}")
            if isinstance(value, str) and len(value) > 1000:
                raise ValueError(f"Metadata value too long for key: {key}")
        
        return v
    
    @field_serializer('config')
    def serialize_config(self, value: AnalysisConfig) -> Dict[str, Any]:
        """Serialize analysis config."""
        return value.to_summary_dict()
    
    @field_serializer('tags')
    def serialize_tags(self, value: List[str]) -> List[str]:
        """Serialize tags ensuring they're lowercase."""
        return [tag.lower() for tag in value]
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create summary for analysis request."""
        return {
            "id": str(self.id),
            "filename": self.filename,
            "analysis_depth": str(self.config.analysis_depth),
            "focus_areas": [str(area) for area in self.config.focus_areas],
            "priority": self.config.priority,
            "estimated_duration": self.config.estimated_duration_seconds,
            "created_at": self.created_at.isoformat(),
            "requester_id": self.requester_id,
            "tags": self.tags,
            "has_metadata": len(self.metadata) > 0,
            "correlation_id": self.correlation_id
        }
    
    def validate_request_consistency(self) -> List[str]:
        """Validate internal consistency of the request."""
        issues = []
        
        # Check if file format hint matches filename
        format_from_filename = get_file_format_from_extension(self.filename)
        if (self.config.format_hint and 
            self.config.format_hint != format_from_filename and 
            format_from_filename != FileFormat.UNKNOWN):
            issues.append(f"Format hint {self.config.format_hint} doesn't match filename format {format_from_filename}")
        
        # Check if platform hint is consistent with format
        if self.config.platform_hint and self.config.format_hint:
            expected_platform = Platform.from_file_format(self.config.format_hint)
            if expected_platform != Platform.UNKNOWN and expected_platform != self.config.platform_hint:
                issues.append(f"Platform hint {self.config.platform_hint} inconsistent with format {self.config.format_hint}")
        
        return issues
    
    @computed_field
    @property
    def estimated_completion_time(self) -> datetime:
        """Estimate when analysis will complete."""
        from datetime import timedelta
        return self.created_at + timedelta(seconds=self.config.estimated_duration_seconds)
    
    @computed_field
    @property
    def request_summary(self) -> Dict[str, Any]:
        """Get summary of the analysis request."""
        return {
            "id": str(self.id),
            "filename": self.filename,
            "analysis_depth": self.config.analysis_depth,
            "estimated_duration": self.config.estimated_duration_seconds,
            "focus_areas": [area for area in self.config.focus_areas],
            "created_at": self.created_at.isoformat(),
            "tags": self.tags,
            "has_metadata": len(self.metadata) > 0
        }
    
    def get_file_format_hint(self) -> Optional[FileFormat]:
        """Get file format hint from filename or config."""
        if self.config.format_hint:
            return self.config.format_hint
        
        # Try to infer from filename
        from ..shared.enums import get_file_format_from_extension
        return get_file_format_from_extension(self.filename)
    
    def get_platform_hint(self) -> Optional[Platform]:
        """Get platform hint from config or inferred from file format."""
        if self.config.platform_hint:
            return self.config.platform_hint
        
        # Try to infer from file format
        file_format = self.get_file_format_hint()
        if file_format:
            return Platform.from_file_format(file_format)
        
        return None
    
    def is_high_priority(self) -> bool:
        """Check if this is a high priority request."""
        return self.config.priority in ['high', 'urgent']
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the request."""
        self.metadata[key] = value
        self.mark_updated()
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the request."""
        normalized_tag = tag.strip().lower()
        if normalized_tag and normalized_tag not in self.tags:
            self.tags.append(normalized_tag)
            self.mark_updated()


class AnalysisConfigBuilder:
    """
    Builder pattern implementation for creating AnalysisConfig instances.
    
    Provides a fluent interface for constructing analysis configurations
    with validation and convenient defaults.
    """
    
    def __init__(self):
        """Initialize builder with default values."""
        self._depth = AnalysisDepth.STANDARD
        self._focus_areas = [AnalysisFocus.SECURITY, AnalysisFocus.FUNCTIONS, AnalysisFocus.STRINGS]
        self._timeout = 300
        self._enable_security_scan = True
        self._enable_function_analysis = True
        self._enable_string_extraction = True
        self._max_functions = 10000
        self._max_strings = 50000
        self._min_string_length = 4
        self._force_reanalysis = False
        self._custom_patterns = []
        self._platform_hint = None
        self._format_hint = None
        self._priority = "normal"
    
    def with_depth(self, depth: AnalysisDepth) -> 'AnalysisConfigBuilder':
        """Set analysis depth."""
        self._depth = depth
        # Auto-adjust timeout based on depth
        self._timeout = depth.get_timeout()
        return self
    
    def quick_analysis(self) -> 'AnalysisConfigBuilder':
        """Configure for quick analysis."""
        return self.with_depth(AnalysisDepth.QUICK).with_timeout(30)
    
    def standard_analysis(self) -> 'AnalysisConfigBuilder':
        """Configure for standard analysis."""
        return self.with_depth(AnalysisDepth.STANDARD).with_timeout(300)
    
    def comprehensive_analysis(self) -> 'AnalysisConfigBuilder':
        """Configure for comprehensive analysis."""
        return (self.with_depth(AnalysisDepth.COMPREHENSIVE)
                .with_timeout(1200)
                .with_focus_areas([AnalysisFocus.ALL]))
    
    def with_focus_areas(self, areas: List[AnalysisFocus]) -> 'AnalysisConfigBuilder':
        """Set focus areas for analysis."""
        self._focus_areas = areas if areas else [AnalysisFocus.SECURITY]
        return self
    
    def add_focus_area(self, area: AnalysisFocus) -> 'AnalysisConfigBuilder':
        """Add a focus area for analysis."""
        if area not in self._focus_areas:
            self._focus_areas.append(area)
        return self
    
    def with_timeout(self, seconds: int) -> 'AnalysisConfigBuilder':
        """Set timeout for analysis."""
        self._timeout = max(30, min(1200, seconds))  # Clamp to valid range
        return self
    
    def with_security_scan(self, enabled: bool = True) -> 'AnalysisConfigBuilder':
        """Enable or disable security scanning."""
        self._enable_security_scan = enabled
        if enabled and AnalysisFocus.SECURITY not in self._focus_areas:
            self._focus_areas.append(AnalysisFocus.SECURITY)
        return self
    
    def with_function_analysis(self, enabled: bool = True) -> 'AnalysisConfigBuilder':
        """Enable or disable function analysis."""
        self._enable_function_analysis = enabled
        if enabled and AnalysisFocus.FUNCTIONS not in self._focus_areas:
            self._focus_areas.append(AnalysisFocus.FUNCTIONS)
        return self
    
    def with_string_extraction(self, enabled: bool = True) -> 'AnalysisConfigBuilder':
        """Enable or disable string extraction."""
        self._enable_string_extraction = enabled
        if enabled and AnalysisFocus.STRINGS not in self._focus_areas:
            self._focus_areas.append(AnalysisFocus.STRINGS)
        return self
    
    def with_limits(self, max_functions: int = None, max_strings: int = None) -> 'AnalysisConfigBuilder':
        """Set limits for functions and strings."""
        if max_functions is not None:
            self._max_functions = max(1, min(50000, max_functions))
        if max_strings is not None:
            self._max_strings = max(1, min(100000, max_strings))
        return self
    
    def with_custom_patterns(self, patterns: List[str]) -> 'AnalysisConfigBuilder':
        """Add custom regex patterns."""
        self._custom_patterns = patterns if patterns else []
        return self
    
    def with_platform_hint(self, platform: Platform) -> 'AnalysisConfigBuilder':
        """Set platform hint."""
        self._platform_hint = platform
        return self
    
    def with_format_hint(self, file_format: FileFormat) -> 'AnalysisConfigBuilder':
        """Set file format hint."""
        self._format_hint = file_format
        return self
    
    def with_priority(self, priority: str) -> 'AnalysisConfigBuilder':
        """Set analysis priority."""
        if priority in ['low', 'normal', 'high', 'urgent']:
            self._priority = priority
        return self
    
    def force_reanalysis(self, force: bool = True) -> 'AnalysisConfigBuilder':
        """Force re-analysis even if cached results exist."""
        self._force_reanalysis = force
        return self
    
    def build(self) -> AnalysisConfig:
        """Build the final AnalysisConfig instance."""
        return AnalysisConfig(
            analysis_depth=self._depth,
            focus_areas=self._focus_areas,
            timeout_seconds=self._timeout,
            enable_security_scan=self._enable_security_scan,
            enable_function_analysis=self._enable_function_analysis,
            enable_string_extraction=self._enable_string_extraction,
            max_functions=self._max_functions,
            max_strings=self._max_strings,
            min_string_length=self._min_string_length,
            force_reanalysis=self._force_reanalysis,
            custom_patterns=self._custom_patterns,
            platform_hint=self._platform_hint,
            format_hint=self._format_hint,
            priority=self._priority
        )


# Convenience functions for common configurations
def create_quick_config() -> AnalysisConfig:
    """Create configuration for quick analysis."""
    return AnalysisConfigBuilder().quick_analysis().build()


def create_standard_config() -> AnalysisConfig:
    """Create configuration for standard analysis."""
    return AnalysisConfigBuilder().standard_analysis().build()


def create_comprehensive_config() -> AnalysisConfig:
    """Create configuration for comprehensive analysis."""
    return AnalysisConfigBuilder().comprehensive_analysis().build()


def create_security_focused_config() -> AnalysisConfig:
    """Create configuration focused on security analysis."""
    return (AnalysisConfigBuilder()
            .standard_analysis()
            .with_focus_areas([AnalysisFocus.SECURITY, AnalysisFocus.STRINGS])
            .with_security_scan(True)
            .build())


class AnalysisJobMetadata(TimestampedModel, AnalysisModelMixin):
    """
    Metadata about an analysis job execution.
    
    Tracks job lifecycle, execution details, worker information,
    and performance metrics for analysis operations.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "12345678-1234-5678-9012-123456789012",
                    "request_id": "req_abc123",
                    "user_id": "user_456",
                    "worker_id": "worker_001",
                    "priority": "normal",
                    "status": "processing",
                    "started_at": "2024-01-01T10:00:00Z",
                    "estimated_completion": "2024-01-01T10:05:00Z"
                }
            ]
        }
    )
    
    job_id: UUID = Field(
        default_factory=uuid4,
        description="Unique job identifier"
    )
    
    request_id: str = Field(
        description="Associated analysis request ID"
    )
    
    user_id: Optional[str] = Field(
        default=None,
        description="User who submitted the analysis request"
    )
    
    worker_id: Optional[str] = Field(
        default=None,
        description="Worker process handling the analysis"
    )
    
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
        description="Job priority level"
    )
    
    status: str = Field(
        default="queued",
        pattern="^(queued|processing|completed|failed|cancelled|timeout)$",
        description="Current job status"
    )
    
    started_at: Optional[datetime] = Field(
        default=None,
        description="When job processing started"
    )
    
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When job processing completed"
    )
    
    estimated_completion: Optional[datetime] = Field(
        default=None,
        description="Estimated completion time"
    )
    
    progress_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Job progress percentage (0-100)"
    )
    
    current_step: str = Field(
        default="initializing",
        description="Current processing step description"
    )
    
    result_size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Size of analysis results in bytes"
    )
    
    memory_usage_mb: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Peak memory usage in MB"
    )
    
    cpu_time_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="CPU time consumed in seconds"
    )
    
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if job failed"
    )
    
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts"
    )
    
    job_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional job-specific metadata"
    )
    
    @field_validator('request_id')
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request ID format."""
        if not v or not v.strip():
            raise ValueError("Request ID cannot be empty")
        
        v = v.strip()
        if len(v) > 100:
            raise ValueError("Request ID too long (max 100 characters)")
        
        return v
    
    @computed_field
    @property
    def queue_duration_seconds(self) -> Optional[float]:
        """Calculate time spent in queue before processing started."""
        if not self.started_at:
            return None
        return (self.started_at - self.created_at).total_seconds()
    
    @computed_field
    @property
    def processing_duration_seconds(self) -> Optional[float]:
        """Calculate time spent processing."""
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    @computed_field
    @property
    def total_duration_seconds(self) -> Optional[float]:
        """Calculate total job duration from creation to completion."""
        end_time = self.completed_at or datetime.now()
        return (end_time - self.created_at).total_seconds()
    
    @computed_field
    @property
    def is_terminal_status(self) -> bool:
        """Check if job is in a terminal state."""
        terminal_states = {'completed', 'failed', 'cancelled', 'timeout'}
        return self.status in terminal_states
    
    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if job is actively processing."""
        active_states = {'queued', 'processing'}
        return self.status in active_states
    
    @computed_field
    @property
    def job_summary(self) -> Dict[str, Any]:
        """Get summary of job information."""
        return {
            "job_id": str(self.job_id),
            "request_id": self.request_id,
            "user_id": self.user_id,
            "status": self.status,
            "priority": self.priority,
            "progress": self.progress_percentage,
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "queue_duration": self.queue_duration_seconds,
            "processing_duration": self.processing_duration_seconds,
            "total_duration": self.total_duration_seconds,
            "worker_id": self.worker_id,
            "retry_count": self.retry_count,
            "has_error": self.error_message is not None
        }
    
    def mark_started(self, worker_id: str) -> None:
        """Mark job as started with worker assignment."""
        self.worker_id = worker_id
        self.status = "processing"
        self.started_at = datetime.now()
        self.current_step = "analysis_beginning"
        self.mark_updated()
    
    def mark_completed(self, result_size: Optional[int] = None) -> None:
        """Mark job as completed."""
        self.status = "completed"
        self.completed_at = datetime.now()
        self.progress_percentage = 100.0
        self.current_step = "completed"
        if result_size is not None:
            self.result_size_bytes = result_size
        self.mark_updated()
    
    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed with error message."""
        self.status = "failed"
        self.completed_at = datetime.now()
        self.error_message = error_message
        self.current_step = "failed"
        self.mark_updated()
    
    def update_progress(self, percentage: float, step_description: str) -> None:
        """Update job progress."""
        self.progress_percentage = max(0.0, min(100.0, percentage))
        self.current_step = step_description
        self.mark_updated()
    
    def increment_retry(self) -> None:
        """Increment retry counter."""
        self.retry_count += 1
        self.status = "queued"  # Reset to queued for retry
        self.worker_id = None
        self.started_at = None
        self.completed_at = None
        self.progress_percentage = 0.0
        self.current_step = "retrying"
        self.mark_updated()
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get detailed status information."""
        return {
            "job_id": str(self.job_id),
            "request_id": self.request_id,
            "status": self.status,
            "progress": self.progress_percentage,
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "queue_duration": self.queue_duration_seconds,
            "processing_duration": self.processing_duration_seconds,
            "is_terminal": self.is_terminal_status,
            "is_active": self.is_active,
            "worker_id": self.worker_id,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_time_seconds": self.cpu_time_seconds
        }