"""
Decompilation configuration models for binary decompilation operations.

Provides models for configuring decompilation depth, processing options, timeouts,
and other parameters that control binary decompilation and LLM translation behavior.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID, uuid4

from pydantic import Field, field_validator, computed_field, ConfigDict, field_serializer

from ..shared.base import BaseModel, TimestampedModel
from ..shared.enums import Platform, FileFormat
from ..decompilation.results import DecompilationDepth, TranslationDetail
from .serialization import AnalysisModelMixin, validate_string_list, validate_confidence_score


class DecompilationConfig(BaseModel, AnalysisModelMixin):
    """
    Configuration for binary decompilation operations.
    
    Defines decompilation parameters including depth, timeout, processing options,
    and various options that control decompilation and LLM translation behavior.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "decompilation_depth": "standard",
                    "extract_functions": True,
                    "extract_imports": True,
                    "extract_strings": True,
                    "timeout_seconds": 300,
                    "max_functions": 1000,
                    "llm_provider": "openai",
                    "translation_detail": "standard"
                }
            ]
        }
    )
    
    decompilation_depth: DecompilationDepth = Field(
        default=DecompilationDepth.STANDARD,
        description="Level of decompilation depth to perform"
    )
    
    extract_functions: bool = Field(
        default=True,
        description="Whether to extract and analyze functions"
    )
    
    extract_imports: bool = Field(
        default=True,
        description="Whether to extract import information"
    )
    
    extract_strings: bool = Field(
        default=True,
        description="Whether to extract string information"
    )
    
    timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=1800,
        description="Maximum time to spend on decompilation in seconds"
    )
    
    llm_provider: Optional[str] = Field(
        default=None,
        description="LLM provider for translation (openai, anthropic, gemini)"
    )
    
    llm_model: Optional[str] = Field(
        default=None,
        description="Specific LLM model to use for translation"
    )
    
    translation_detail: TranslationDetail = Field(
        default=TranslationDetail.STANDARD,
        description="Level of detail for LLM translations"
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
    
    platform_hint: Optional[Platform] = Field(
        default=None,
        description="Platform hint to guide decompilation decisions"
    )
    
    format_hint: Optional[FileFormat] = Field(
        default=None,
        description="File format hint to guide decompilation decisions"
    )
    
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
        description="Decompilation priority level"
    )
    
    @field_validator('llm_provider')
    @classmethod
    def validate_llm_provider(cls, v: Optional[str]) -> Optional[str]:
        """Validate LLM provider selection."""
        if v is None:
            return v
        
        valid_providers = ['openai', 'anthropic', 'gemini', 'ollama']
        v = v.strip().lower()
        
        if v not in valid_providers:
            raise ValueError(f"Invalid LLM provider: {v}. Must be one of {valid_providers}")
        
        return v
    
    @field_validator('timeout_seconds')
    @classmethod
    def validate_timeout_with_depth(cls, v: int, info) -> int:
        """Validate timeout is appropriate for decompilation depth."""
        if hasattr(info, 'data') and 'decompilation_depth' in info.data:
            depth = info.data['decompilation_depth']
            # Basic timeout validation - more specific logic could be added
            if depth == DecompilationDepth.BASIC and v > 300:
                # Log warning for potentially excessive timeout
                pass
            elif depth == DecompilationDepth.COMPREHENSIVE and v < 600:
                # Log warning for potentially insufficient timeout
                pass
        
        return v
    
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
    
    @field_serializer('decompilation_depth')
    def serialize_decompilation_depth(self, value: DecompilationDepth) -> str:
        """Serialize decompilation depth to string."""
        return str(value)
    
    @field_serializer('translation_detail')
    def serialize_translation_detail(self, value: TranslationDetail) -> str:
        """Serialize translation detail to string."""
        return str(value)
    
    @field_serializer('platform_hint', 'format_hint')
    def serialize_enum_hints(self, value: Optional[Union[Platform, FileFormat]]) -> Optional[str]:
        """Serialize platform and format hints to strings."""
        return str(value) if value else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "decompilation_depth": str(self.decompilation_depth),
            "extract_functions": self.extract_functions,
            "extract_imports": self.extract_imports,
            "extract_strings": self.extract_strings,
            "timeout_seconds": self.timeout_seconds,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "translation_detail": str(self.translation_detail),
            "max_functions": self.max_functions,
            "max_strings": self.max_strings,
            "min_string_length": self.min_string_length,
            "force_reanalysis": self.force_reanalysis,
            "priority": self.priority,
            "platform_hint": str(self.platform_hint) if self.platform_hint else None,
            "format_hint": str(self.format_hint) if self.format_hint else None
        }


class DecompilationRequest(TimestampedModel, AnalysisModelMixin):
    """
    Complete request for binary decompilation including file reference and configuration.
    
    Represents a user's request to decompile a binary file with specific
    configuration parameters.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": "req_123456789",
                    "file_hash": "sha256:abc123...",
                    "filename": "example.exe",
                    "config": {
                        "decompilation_depth": "standard",
                        "llm_provider": "openai"
                    }
                }
            ]
        }
    )
    
    request_id: str = Field(
        default_factory=lambda: f"req_{uuid4().hex[:12]}",
        description="Unique request identifier"
    )
    
    file_hash: str = Field(
        ...,
        min_length=10,
        description="Hash identifier for the binary file"
    )
    
    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename of the binary"
    )
    
    config: DecompilationConfig = Field(
        default_factory=DecompilationConfig,
        description="Decompilation configuration parameters"
    )
    
    user_id: Optional[str] = Field(
        default=None,
        description="User identifier for tracking and quotas"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="User-defined tags for organization"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional request metadata"
    )
    
    @field_validator('file_hash')
    @classmethod
    def validate_file_hash(cls, v: str) -> str:
        """Validate file hash format."""
        v = v.strip()
        if not v:
            raise ValueError("File hash cannot be empty")
        
        # Basic validation - could be enhanced
        if len(v) < 10:
            raise ValueError("File hash appears too short")
        
        return v
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        return validate_string_list(v, max_items=20, max_length=50)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "request_id": self.request_id,
            "file_hash": self.file_hash,
            "filename": self.filename,
            "config": self.config.to_dict(),
            "user_id": self.user_id,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class DecompilationConfigBuilder:
    """
    Builder pattern implementation for creating DecompilationConfig instances.
    
    Provides a fluent interface for constructing decompilation configurations
    with sensible defaults and validation.
    """
    
    def __init__(self):
        """Initialize builder with default values."""
        self._decompilation_depth = DecompilationDepth.STANDARD
        self._extract_functions = True
        self._extract_imports = True
        self._extract_strings = True
        self._timeout_seconds = 300
        self._llm_provider = None
        self._llm_model = None
        self._translation_detail = TranslationDetail.STANDARD
        self._max_functions = 10000
        self._max_strings = 50000
        self._min_string_length = 4
        self._force_reanalysis = False
        self._platform_hint = None
        self._format_hint = None
        self._priority = "normal"
    
    def with_depth(self, depth: DecompilationDepth) -> 'DecompilationConfigBuilder':
        """Set decompilation depth."""
        self._decompilation_depth = depth
        return self
    
    def with_llm_provider(self, provider: str, model: Optional[str] = None) -> 'DecompilationConfigBuilder':
        """Set LLM provider and model."""
        self._llm_provider = provider
        self._llm_model = model
        return self
    
    def with_translation_detail(self, detail: TranslationDetail) -> 'DecompilationConfigBuilder':
        """Set translation detail level."""
        self._translation_detail = detail
        return self
    
    def with_timeout(self, seconds: int) -> 'DecompilationConfigBuilder':
        """Set timeout in seconds."""
        self._timeout_seconds = seconds
        return self
    
    def with_extraction(self, functions: bool = True, imports: bool = True, strings: bool = True) -> 'DecompilationConfigBuilder':
        """Configure what to extract."""
        self._extract_functions = functions
        self._extract_imports = imports
        self._extract_strings = strings
        return self
    
    def with_limits(self, max_functions: int = 10000, max_strings: int = 50000) -> 'DecompilationConfigBuilder':
        """Set extraction limits."""
        self._max_functions = max_functions
        self._max_strings = max_strings
        return self
    
    def with_priority(self, priority: str) -> 'DecompilationConfigBuilder':
        """Set processing priority."""
        self._priority = priority
        return self
    
    def with_hints(self, platform: Optional[Platform] = None, format_hint: Optional[FileFormat] = None) -> 'DecompilationConfigBuilder':
        """Set platform and format hints."""
        self._platform_hint = platform
        self._format_hint = format_hint
        return self
    
    def build(self) -> DecompilationConfig:
        """Build the final configuration."""
        return DecompilationConfig(
            decompilation_depth=self._decompilation_depth,
            extract_functions=self._extract_functions,
            extract_imports=self._extract_imports,
            extract_strings=self._extract_strings,
            timeout_seconds=self._timeout_seconds,
            llm_provider=self._llm_provider,
            llm_model=self._llm_model,
            translation_detail=self._translation_detail,
            max_functions=self._max_functions,
            max_strings=self._max_strings,
            min_string_length=self._min_string_length,
            force_reanalysis=self._force_reanalysis,
            platform_hint=self._platform_hint,
            format_hint=self._format_hint,
            priority=self._priority
        )
    
    @classmethod
    def quick(cls) -> DecompilationConfig:
        """Create a quick decompilation configuration."""
        return (cls()
                .with_depth(DecompilationDepth.BASIC)
                .with_timeout(60)
                .with_limits(max_functions=100, max_strings=1000)
                .build())
    
    @classmethod
    def comprehensive(cls) -> DecompilationConfig:
        """Create a comprehensive decompilation configuration."""
        return (cls()
                .with_depth(DecompilationDepth.COMPREHENSIVE)
                .with_timeout(1200)
                .with_limits(max_functions=50000, max_strings=100000)
                .build())