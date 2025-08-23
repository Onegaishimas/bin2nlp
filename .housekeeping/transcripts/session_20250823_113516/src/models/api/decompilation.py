"""
Decompilation API Models

Request and response models for decompilation + LLM translation endpoints.
Simplified architecture focusing on binary decompilation and natural language output.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field, ConfigDict

from ..shared.base import BaseModel
from ..shared.enums import Platform, FileFormat, JobStatus
from ..decompilation.results import DecompilationDepth, TranslationDetail


class DecompilationRequest(BaseModel):
    """
    Request model for binary decompilation + LLM translation.
    
    Simplified request focusing on file upload, decompilation configuration,
    and LLM provider selection for natural language output.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Decompilation Request",
            "description": "Request to decompile a binary file and translate to natural language using LLM providers",
            "examples": [
                {
                    "filename": "malware.exe",
                    "decompilation_depth": "standard",
                    "llm_provider": "anthropic",
                    "llm_model": "claude-3-sonnet-20240229",
                    "translation_detail": "standard",
                    "include_function_translations": True,
                    "include_import_explanations": True,
                    "include_overall_summary": True,
                    "max_functions_translate": 20,
                    "cost_limit_usd": 5.0,
                    "timeout_seconds": 600
                },
                {
                    "filename": "app.elf",
                    "decompilation_depth": "comprehensive",
                    "llm_provider": "openai",
                    "llm_model": "gpt-4",
                    "translation_detail": "comprehensive",
                    "platform_hint": "linux",
                    "format_hint": "elf",
                    "custom_prompts": {
                        "function_translation": "Focus on security implications and potential vulnerabilities"
                    }
                }
            ]
        }
    )
    
    filename: str = Field(
        description="Name of the binary file being analyzed",
        min_length=1,
        max_length=255,
        examples=["malware.exe", "app.elf", "library.dylib"]
    )
    
    decompilation_depth: DecompilationDepth = Field(
        default=DecompilationDepth.STANDARD,
        description="Depth of binary decompilation analysis"
    )
    
    llm_provider: Optional[str] = Field(
        default=None,
        description="LLM provider for translation (openai, anthropic, gemini). Auto-selected if not specified."
    )
    
    llm_model: Optional[str] = Field(
        default=None,
        description="Specific model to use (e.g., gpt-4, claude-3-sonnet-20240229, gemini-pro)"
    )
    
    translation_detail: TranslationDetail = Field(
        default=TranslationDetail.STANDARD,
        description="Level of detail for natural language translations"
    )
    
    include_function_translations: bool = Field(
        default=True,
        description="Include function-by-function natural language explanations"
    )
    
    include_import_explanations: bool = Field(
        default=True,
        description="Include explanations of imported libraries and functions"
    )
    
    include_overall_summary: bool = Field(
        default=True,
        description="Include high-level program purpose and behavior summary"
    )
    
    max_functions_translate: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of functions to translate (cost control)"
    )
    
    cost_limit_usd: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Maximum LLM translation cost in USD"
    )
    
    timeout_seconds: Optional[int] = Field(
        default=None,
        ge=60,
        le=1800,
        description="Maximum processing time in seconds"
    )
    
    platform_hint: Optional[Platform] = Field(
        default=None,
        description="Platform hint for optimization"
    )
    
    format_hint: Optional[FileFormat] = Field(
        default=None,
        description="File format hint for optimization"
    )
    
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high)$",
        description="Processing priority level"
    )
    
    custom_prompts: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom prompts for specific translation operations"
    )
    
    callback_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for completion notification"
    )
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename."""
        v = v.strip()
        if not v:
            raise ValueError("Filename cannot be empty")
        
        # Check for problematic characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        if any(char in v for char in invalid_chars):
            raise ValueError("Filename contains invalid characters")
        
        return v
    
    @field_validator('llm_provider')
    @classmethod
    def validate_llm_provider(cls, v: Optional[str]) -> Optional[str]:
        """Validate LLM provider."""
        if v is None:
            return v
        
        v = v.lower().strip()
        if v not in ['openai', 'anthropic', 'gemini']:
            raise ValueError(f"Unsupported LLM provider: {v}. Supported: openai, anthropic, gemini")
        
        return v
    
    @field_validator('cost_limit_usd')
    @classmethod
    def validate_cost_limit(cls, v: Optional[float]) -> Optional[float]:
        """Validate cost limit."""
        if v is not None and v <= 0:
            raise ValueError("Cost limit must be greater than 0")
        return v
    
    @field_validator('custom_prompts')
    @classmethod
    def validate_custom_prompts(cls, v: Dict[str, str]) -> Dict[str, str]:
        """Validate custom prompts."""
        if len(v) > 10:
            raise ValueError("Too many custom prompts (max 10)")
        
        valid_operations = {
            'function_translation',
            'import_explanation', 
            'string_interpretation',
            'overall_summary'
        }
        
        for operation in v.keys():
            if operation not in valid_operations:
                raise ValueError(f"Invalid prompt operation: {operation}")
            if len(v[operation]) > 1000:
                raise ValueError(f"Prompt too long for {operation} (max 1000 chars)")
        
        return v
    
    @computed_field
    @property
    def estimated_duration_seconds(self) -> int:
        """Estimate total processing duration."""
        if self.timeout_seconds:
            return self.timeout_seconds
        
        # Base decompilation time
        base_time = {
            DecompilationDepth.BASIC: 120,
            DecompilationDepth.STANDARD: 300,
            DecompilationDepth.COMPREHENSIVE: 600
        }.get(self.decompilation_depth, 300)
        
        # Add LLM translation time
        llm_multiplier = 1.0
        if self.include_function_translations:
            llm_multiplier += 0.5
        if self.include_import_explanations:
            llm_multiplier += 0.2
        if self.include_overall_summary:
            llm_multiplier += 0.3
        
        return int(base_time * llm_multiplier)


class DecompilationJobResponse(BaseModel):
    """
    Response for successful decompilation job submission.
    
    Contains job tracking information and estimated completion details.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Decompilation Job Response",
            "description": "Response after successful decompilation job submission",
            "examples": [
                {
                    "job_id": "dec_550e8400-e29b-41d4-a716-446655440000",
                    "status": "pending",
                    "filename": "malware.exe",
                    "estimated_duration_seconds": 450,
                    "estimated_completion_time": "2024-01-15T14:35:30Z",
                    "llm_provider": "anthropic",
                    "llm_model": "claude-3-sonnet-20240229",
                    "estimated_cost_usd": 2.50,
                    "status_url": "/api/v1/decompile/dec_550e8400-e29b-41d4-a716-446655440000",
                    "queue_position": 2,
                    "created_at": "2024-01-15T14:28:00Z"
                }
            ]
        }
    )
    
    job_id: str = Field(
        description="Unique job identifier with 'dec_' prefix"
    )
    
    status: JobStatus = Field(
        description="Current job status"
    )
    
    filename: str = Field(
        description="Name of file being processed"
    )
    
    estimated_duration_seconds: int = Field(
        description="Estimated total processing time"
    )
    
    estimated_completion_time: datetime = Field(
        description="Expected completion timestamp"
    )
    
    llm_provider: Optional[str] = Field(
        default=None,
        description="Selected LLM provider"
    )
    
    llm_model: Optional[str] = Field(
        default=None,
        description="Selected LLM model"
    )
    
    estimated_cost_usd: Optional[float] = Field(
        default=None,
        description="Estimated LLM translation cost"
    )
    
    status_url: str = Field(
        description="URL to check job status and retrieve results"
    )
    
    queue_position: Optional[int] = Field(
        default=None,
        description="Position in processing queue"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Job creation timestamp"
    )
    
    @computed_field
    @property
    def is_queued(self) -> bool:
        """Check if job is queued."""
        return self.status == JobStatus.PENDING
    
    @computed_field
    @property
    def is_processing(self) -> bool:
        """Check if job is currently processing."""
        return self.status == JobStatus.PROCESSING


class DecompilationResultResponse(BaseModel):
    """
    Complete decompilation and translation results.
    
    Contains both the raw decompilation data and natural language translations
    from the selected LLM provider.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Decompilation Results",
            "description": "Complete binary decompilation and LLM translation results",
            "examples": [
                {
                    "job_id": "dec_550e8400-e29b-41d4-a716-446655440000",
                    "status": "completed",
                    "success": True,
                    "filename": "malware.exe",
                    "file_metadata": {
                        "hash": "sha256:abc123...",
                        "size_bytes": 1048576,
                        "format": "pe",
                        "platform": "windows",
                        "architecture": "x64"
                    },
                    "decompilation_summary": {
                        "functions_found": 127,
                        "imports_found": 23,
                        "strings_found": 245,
                        "processing_time_seconds": 45.2
                    },
                    "translation_summary": {
                        "llm_provider": "anthropic",
                        "llm_model": "claude-3-sonnet-20240229",
                        "functions_translated": 20,
                        "imports_explained": 23,
                        "overall_summary_included": True,
                        "tokens_used": 8450,
                        "cost_usd": 2.31
                    },
                    "results": {
                        "overall_summary": "This appears to be a Windows executable that...",
                        "function_translations": [],
                        "import_explanations": []
                    }
                }
            ]
        }
    )
    
    job_id: str = Field(description="Job identifier")
    status: JobStatus = Field(description="Final job status")
    success: bool = Field(description="Whether processing completed successfully")
    filename: str = Field(description="Original filename")
    
    file_metadata: Dict[str, Any] = Field(
        description="Binary file metadata and properties"
    )
    
    decompilation_summary: Dict[str, Any] = Field(
        description="Summary of decompilation process and findings"
    )
    
    translation_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Summary of LLM translation process and costs"
    )
    
    results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Complete translation results (functions, imports, summary)"
    )
    
    errors: List[str] = Field(
        default_factory=list,
        description="Processing errors encountered"
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="Processing warnings"
    )
    
    created_at: datetime = Field(description="Job creation time")
    started_at: Optional[datetime] = Field(default=None, description="Processing start time")
    completed_at: Optional[datetime] = Field(default=None, description="Processing completion time")
    
    @computed_field
    @property
    def total_processing_time_seconds(self) -> Optional[float]:
        """Calculate total processing time."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @computed_field
    @property
    def has_translation_results(self) -> bool:
        """Check if LLM translation was successful."""
        return self.translation_summary is not None and self.results is not None


class LLMProviderInfo(BaseModel):
    """Information about available LLM providers."""
    
    provider_id: str = Field(description="Provider identifier")
    name: str = Field(description="Human-readable provider name")
    status: str = Field(description="Provider availability status")
    available_models: List[str] = Field(description="Available models")
    cost_per_1k_tokens: Optional[float] = Field(default=None, description="Approximate cost per 1K tokens")
    capabilities: List[str] = Field(description="Supported translation operations")
    health_score: Optional[float] = Field(default=None, description="Provider health score (0-1)")


class LLMProvidersResponse(BaseModel):
    """Response listing available LLM providers."""
    
    providers: List[LLMProviderInfo] = Field(description="Available LLM providers")
    recommended_provider: Optional[str] = Field(default=None, description="Recommended provider ID")
    total_healthy: int = Field(description="Number of healthy providers")
    last_updated: datetime = Field(default_factory=datetime.utcnow)