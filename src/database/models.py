"""
Database models for the hybrid PostgreSQL + File Storage system.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import json

from pydantic import BaseModel, Field, validator
from ..models.shared.enums import JobStatus
from ..llm.base import LLMProviderType


# Enums matching PostgreSQL types
class JobPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RateLimitScope(str, Enum):
    GLOBAL = "global"
    API_KEY = "api_key"
    IP_ADDRESS = "ip_address"


# Pydantic models for data validation and serialization
class Job(BaseModel):
    """Job model for queue management."""
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    
    # File information
    file_hash: str = Field(..., max_length=64)
    filename: str = Field(..., max_length=255)
    file_reference: str
    
    # Analysis configuration
    analysis_config: Dict[str, Any]
    
    # Result storage (points to file storage)
    result_file_path: Optional[str] = Field(None, max_length=500)
    error_message: Optional[str] = None
    
    # Progress tracking
    progress_percentage: float = Field(0.0, ge=0.0, le=100.0)
    current_stage: Optional[str] = Field(None, max_length=100)
    worker_id: Optional[str] = Field(None, max_length=100)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Request context
    submitted_by: Optional[str] = Field(None, max_length=100)
    callback_url: Optional[str] = None
    correlation_id: Optional[str] = Field(None, max_length=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Performance tracking
    processing_time_seconds: Optional[int] = None
    estimated_completion_seconds: Optional[int] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }
    
    @validator('analysis_config', pre=True)
    def parse_analysis_config(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    @validator('metadata', pre=True)
    def parse_metadata(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class CacheEntry(BaseModel):
    """Cache metadata model (actual data stored in files)."""
    
    cache_key: str = Field(..., max_length=255)
    file_hash: str = Field(..., max_length=64)
    config_hash: str = Field(..., max_length=32)
    
    # File storage reference
    file_path: str = Field(..., max_length=500)
    
    # Cache metadata
    cache_version: str = Field(default="1.0", max_length=10)
    tags: List[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    
    # Statistics
    access_count: int = Field(default=0, ge=0)
    data_size_bytes: int = Field(default=0, ge=0)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class RateLimit(BaseModel):
    """Rate limiting model."""
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    scope: RateLimitScope
    identifier: str = Field(..., max_length=255)
    
    # Rate limit tracking
    request_count: int = Field(default=1, ge=0)
    window_start: datetime = Field(default_factory=datetime.utcnow)
    window_size_seconds: int = Field(..., gt=0)
    
    # Limits
    max_requests: int = Field(..., gt=0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }


class Session(BaseModel):
    """Session model for API key and user session management."""
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_key: str = Field(..., max_length=255)
    
    # Session data
    session_data: Dict[str, Any] = Field(default_factory=dict)
    
    # API key information
    api_key_hash: Optional[str] = Field(None, max_length=64)
    api_key_prefix: Optional[str] = Field(None, max_length=10)
    user_tier: str = Field(default="basic", max_length=50)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Session metadata
    ip_address: Optional[str] = Field(None, max_length=45)  # IPv6 max length
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }
    
    @validator('session_data', 'metadata', pre=True)
    def parse_json_fields(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


class SystemStat(BaseModel):
    """System statistics model."""
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    stat_key: str = Field(..., max_length=100)
    stat_value: int = Field(default=0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }


class WorkerHeartbeat(BaseModel):
    """Worker heartbeat tracking model."""
    
    worker_id: str = Field(..., max_length=100)
    
    # Worker information
    worker_type: str = Field(default="decompilation", max_length=50)
    status: str = Field(default="active", max_length=20)
    current_job_id: Optional[uuid.UUID] = None
    
    # Timestamps
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Worker metadata
    hostname: Optional[str] = Field(None, max_length=255)
    process_id: Optional[int] = None
    version: Optional[str] = Field(None, max_length=20)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v)
        }


class FileStorageEntry(BaseModel):
    """File storage tracking model."""
    
    file_path: str = Field(..., max_length=500)
    
    # File metadata
    original_filename: Optional[str] = Field(None, max_length=255)
    content_type: Optional[str] = Field(None, max_length=100)
    file_size_bytes: Optional[int] = Field(None, ge=0)
    file_hash: Optional[str] = Field(None, max_length=64)
    
    # Storage metadata
    storage_type: str = Field(default="cache", max_length=20)  # 'cache', 'result', 'upload'
    reference_count: int = Field(default=1, ge=0)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserLLMProvider(BaseModel):
    """User-configured LLM provider model."""
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(..., max_length=255, description="User-defined provider name")
    provider_type: LLMProviderType = Field(..., description="Provider type (openai, anthropic, etc.)")
    
    # Encrypted credentials
    encrypted_api_key: str = Field(..., description="Encrypted API key for secure storage")
    endpoint_url: Optional[str] = Field(None, max_length=500, description="Custom endpoint URL (for ollama)")
    
    # Configuration and metadata
    config_json: Dict[str, Any] = Field(default_factory=dict, description="Additional provider settings")
    is_active: bool = Field(default=True, description="Whether provider is enabled")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v),
            LLMProviderType: lambda v: v.value if hasattr(v, 'value') else str(v)
        }
    
    @validator('provider_type', pre=True)
    def parse_provider_type(cls, v):
        from ..core.logging import get_logger
        logger = get_logger(__name__)
        
        logger.info(
            "DEBUG parse_provider_type validator called",
            extra={
                "input_value": v,
                "input_type": type(v).__name__,
                "is_string": isinstance(v, str)
            }
        )
        
        if isinstance(v, str):
            try:
                # Check if it's already an enum string representation (the bug)
                if v.startswith('LLMProviderType.'):
                    logger.error(
                        "DEBUG Detected enum string representation - converting to value",
                        extra={"input": v}
                    )
                    # Extract the actual enum value (e.g., "LLMProviderType.OLLAMA" -> "ollama")
                    enum_name = v.split('.')[-1]  # Get "OLLAMA"
                    enum_value = enum_name.lower()  # Convert to "ollama"
                    converted = LLMProviderType(enum_value)
                else:
                    converted = LLMProviderType(v)
                
                logger.info(
                    "DEBUG parse_provider_type conversion successful",
                    extra={"converted": converted, "converted_value": str(converted), "actual_value": converted.value}
                )
                return converted
            except (ValueError, Exception) as e:
                logger.error(
                    "DEBUG parse_provider_type conversion failed",
                    extra={"error": str(e), "input_value": v}
                )
                # If conversion fails, return as-is and let normal validation handle it
                return v
        
        logger.info("DEBUG parse_provider_type returning unchanged", extra={"value": v})
        return v
    
    @validator('config_json', pre=True)
    def parse_config_json(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v
    
    @validator('endpoint_url')
    def validate_endpoint_url_for_ollama(cls, v, values):
        """Validate that Ollama providers have endpoint URLs."""
        from ..core.logging import get_logger
        logger = get_logger(__name__)
        
        provider_type = values.get('provider_type')
        logger.info(
            "DEBUG validate_endpoint_url_for_ollama called",
            extra={
                "endpoint_url": v,
                "provider_type": provider_type,
                "provider_type_type": type(provider_type).__name__,
                "values": values
            }
        )
        
        # Bulletproof comparison - handle both enum and string types
        is_ollama = False
        try:
            if hasattr(provider_type, 'value'):
                # It's an enum, use .value to get the actual string value
                is_ollama = provider_type.value == 'ollama'
                logger.info("DEBUG Using enum.value comparison", extra={"enum_value": provider_type.value})
            elif isinstance(provider_type, str):
                is_ollama = provider_type == 'ollama'
                logger.info("DEBUG Using string comparison", extra={"string_value": provider_type})
            else:
                # Last resort, convert to string (but this should ideally not happen)
                is_ollama = str(provider_type) == 'ollama'
                logger.info("DEBUG Using str() conversion as fallback", extra={"converted_value": str(provider_type)})
        except (AttributeError, Exception) as e:
            logger.error(
                "DEBUG Error in endpoint_url validation comparison",
                extra={"error": str(e), "provider_type": provider_type}
            )
            is_ollama = str(provider_type) == 'ollama'
        
        logger.info("DEBUG is_ollama determined", extra={"is_ollama": is_ollama})
        
        if is_ollama and not v:
            logger.error("DEBUG Validation failure: endpoint_url required for ollama")
            raise ValueError('endpoint_url is required for ollama providers')
        
        logger.info("DEBUG endpoint_url validation passed")
        return v
    
    @validator('name')
    def validate_name(cls, v):
        """Ensure provider name is not empty and properly formatted."""
        if not v or not v.strip():
            raise ValueError('Provider name cannot be empty')
        return v.strip()


# Query result models for complex operations
class JobQueueStats(BaseModel):
    """Job queue statistics result."""
    
    status: JobStatus
    priority: JobPriority
    job_count: int
    avg_processing_time: Optional[float]
    oldest_job: Optional[datetime]
    newest_job: Optional[datetime]
    
    class Config:
        use_enum_values = True


class CachePerformance(BaseModel):
    """Cache performance statistics."""
    
    total_entries: int
    active_entries: int
    expired_entries: int
    avg_access_count: Optional[float]
    total_size_bytes: Optional[int]
    avg_age_seconds: Optional[float]


class RateLimitStats(BaseModel):
    """Rate limiting statistics."""
    
    scope: RateLimitScope
    unique_identifiers: int
    total_requests: int
    avg_requests_per_window: Optional[float]
    max_requests_in_window: Optional[int]
    
    class Config:
        use_enum_values = True


# Helper functions for model conversion
def dict_to_job(data: dict) -> Job:
    """Convert database row to Job model."""
    return Job(**data)


def job_to_dict(job: Job) -> dict:
    """Convert Job model to database dict."""
    return job.dict(exclude_unset=True)


def dict_to_cache_entry(data: dict) -> CacheEntry:
    """Convert database row to CacheEntry model."""
    return CacheEntry(**data)


def cache_entry_to_dict(entry: CacheEntry) -> dict:
    """Convert CacheEntry model to database dict."""
    return entry.dict(exclude_unset=True)