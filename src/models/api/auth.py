"""
API models for authentication and error handling.

Provides request/response models for API key management, rate limiting,
error responses, and authentication workflows.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field, ConfigDict
from typing_extensions import Annotated

from ..shared.base import BaseModel
from ..shared.serialization import AnalysisModelMixin, validate_string_list


class APIKeyRequest(BaseModel, AnalysisModelMixin):
    """
    Request model for API key operations.
    
    Used for API key creation, validation, and management
    endpoints.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "API Key Request",
            "description": "Request model for creating or updating API keys with access control and rate limiting configuration",
            "examples": [
                {
                    "name": "Production Analysis API",
                    "description": "API key for production binary analysis",
                    "scopes": ["analysis:submit", "analysis:read", "jobs:read"],
                    "rate_limit_tier": "standard",
                    "expires_in_days": 90,
                    "ip_whitelist": ["192.168.1.100", "10.0.0.0/24"],
                    "metadata": {
                        "department": "security",
                        "project": "malware-analysis"
                    }
                },
                {
                    "name": "Development Testing",
                    "description": "Limited API key for development and testing",
                    "scopes": ["analysis:read"],
                    "rate_limit_tier": "basic",
                    "expires_in_days": 30,
                    "never_expires": False,
                    "max_requests_per_day": 100,
                    "tags": ["development", "testing"]
                }
            ]
        }
    )
    
    name: Annotated[str, Field(
        description="Human-readable name for the API key",
        min_length=1,
        max_length=100,
        examples=["Production Analysis API", "Development Testing", "CI/CD Pipeline"]
    )]
    
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Description of the API key purpose"
    )
    
    scopes: Annotated[List[str], Field(
        default_factory=lambda: ["analysis:read"],
        description="List of permission scopes for the API key. Available scopes: analysis:submit, analysis:read, analysis:delete, jobs:read, jobs:create, jobs:cancel, jobs:retry, admin:read, admin:write, keys:read, keys:write",
        examples=[["analysis:read"], ["analysis:submit", "analysis:read", "jobs:read"]]
    )]
    
    rate_limit_tier: Annotated[str, Field(
        default="standard",
        pattern="^(basic|standard|premium|enterprise|unlimited)$",
        description="Rate limiting tier for the API key. Tiers: basic (100/day), standard (1000/day), premium (10000/day), enterprise (100000/day), unlimited (no limits)",
        examples=["basic", "standard", "premium"]
    )]
    
    expires_in_days: Optional[int] = Field(
        default=90,
        ge=1,
        le=3650,
        description="Number of days until the API key expires"
    )
    
    never_expires: bool = Field(
        default=False,
        description="Whether the API key should never expire"
    )
    
    ip_whitelist: List[str] = Field(
        default_factory=list,
        description="List of allowed IP addresses or CIDR ranges"
    )
    
    allowed_origins: List[str] = Field(
        default_factory=list,
        description="List of allowed origin domains for CORS"
    )
    
    max_requests_per_day: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum requests per day (overrides tier default)"
    )
    
    max_requests_per_minute: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum requests per minute (overrides tier default)"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the API key"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing the API key"
    )
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate API key name."""
        v = v.strip()
        if not v:
            raise ValueError("API key name cannot be empty")
        return v
    
    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Validate API key scopes."""
        valid_scopes = [
            'analysis:submit', 'analysis:read', 'analysis:delete',
            'jobs:read', 'jobs:create', 'jobs:cancel', 'jobs:retry',
            'admin:read', 'admin:write', 'keys:read', 'keys:write'
        ]
        
        validated = []
        for scope in v:
            if scope in valid_scopes and scope not in validated:
                validated.append(scope)
        
        if not validated:
            raise ValueError("At least one valid scope must be specified")
        
        return validated
    
    @field_validator('ip_whitelist')
    @classmethod
    def validate_ip_whitelist(cls, v: List[str]) -> List[str]:
        """Validate IP whitelist entries."""
        import ipaddress
        
        validated = []
        for ip_entry in v:
            try:
                # Try to parse as IP address or network
                ipaddress.ip_network(ip_entry, strict=False)
                if ip_entry not in validated:
                    validated.append(ip_entry)
            except ValueError:
                raise ValueError(f"Invalid IP address or CIDR range: {ip_entry}")
        
        return validated
    
    @field_validator('allowed_origins')
    @classmethod
    def validate_allowed_origins(cls, v: List[str]) -> List[str]:
        """Validate allowed origins."""
        validated = []
        for origin in v:
            origin = origin.strip().lower()
            if origin and origin not in validated:
                if not (origin.startswith('http://') or origin.startswith('https://') or origin == '*'):
                    raise ValueError(f"Invalid origin format: {origin}")
                validated.append(origin)
        
        return validated
    
    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        return validate_string_list(v, max_items=10)
    
    @computed_field
    @property
    def has_ip_restrictions(self) -> bool:
        """Check if API key has IP restrictions."""
        return len(self.ip_whitelist) > 0
    
    @computed_field
    @property
    def has_origin_restrictions(self) -> bool:
        """Check if API key has origin restrictions."""
        return len(self.allowed_origins) > 0
    
    @computed_field
    @property
    def is_admin_key(self) -> bool:
        """Check if API key has admin privileges."""
        return any(scope.startswith('admin:') for scope in self.scopes)
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "name": self.name,
            "description": self.description,
            "scope_count": len(self.scopes),
            "rate_limit_tier": self.rate_limit_tier,
            "expires_in_days": self.expires_in_days,
            "never_expires": self.never_expires,
            "has_ip_restrictions": self.has_ip_restrictions,
            "has_origin_restrictions": self.has_origin_restrictions,
            "is_admin_key": self.is_admin_key,
            "tag_count": len(self.tags),
            "metadata_fields": len(self.metadata)
        }


class APIKeyResponse(BaseModel, AnalysisModelMixin):
    """
    Response model for API key information.
    
    Returned by API key management endpoints with key details
    and usage statistics.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "API Key Response",
            "description": "API key information with usage statistics and metadata",
            "examples": [
                {
                    "key_id": "ak_1234567890abcdef",
                    "name": "Production Analysis API",
                    "key_prefix": "ak_1234",
                    "scopes": ["analysis:submit", "analysis:read"],
                    "rate_limit_tier": "standard",
                    "created_at": "2024-01-15T14:00:00Z",
                    "expires_at": "2024-04-15T14:00:00Z",
                    "is_active": True,
                    "usage_stats": {
                        "requests_today": 145,
                        "requests_this_month": 4200,
                        "total_requests": 15780
                    },
                    "ip_whitelist": ["192.168.1.100"],
                    "tags": ["production", "analysis"]
                }
            ]
        }
    )
    
    key_id: str = Field(
        description="Unique identifier for the API key"
    )
    
    name: str = Field(
        description="Human-readable name for the API key"
    )
    
    key_prefix: str = Field(
        description="First few characters of the API key for identification"
    )
    
    scopes: List[str] = Field(
        description="List of permission scopes"
    )
    
    rate_limit_tier: str = Field(
        description="Rate limiting tier"
    )
    
    created_at: datetime = Field(
        description="When the API key was created"
    )
    
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When the API key expires (null if never expires)"
    )
    
    last_used_at: Optional[datetime] = Field(
        default=None,
        description="When the API key was last used"
    )
    
    is_active: bool = Field(
        description="Whether the API key is currently active"
    )
    
    usage_stats: Dict[str, int] = Field(
        default_factory=dict,
        description="Usage statistics for the API key"
    )
    
    ip_whitelist: List[str] = Field(
        default_factory=list,
        description="List of allowed IP addresses"
    )
    
    allowed_origins: List[str] = Field(
        default_factory=list,
        description="List of allowed origins"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="API key tags"
    )
    
    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if API key is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    @computed_field
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Calculate days until expiry."""
        if self.expires_at is None:
            return None
        
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)
    
    @computed_field
    @property
    def is_near_expiry(self) -> bool:
        """Check if API key expires within 30 days."""
        days = self.days_until_expiry
        return days is not None and days <= 30
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "key_id": self.key_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scope_count": len(self.scopes),
            "rate_limit_tier": self.rate_limit_tier,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "is_near_expiry": self.is_near_expiry,
            "days_until_expiry": self.days_until_expiry,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "usage_today": self.usage_stats.get("requests_today", 0)
        }


class RateLimitInfo(BaseModel, AnalysisModelMixin):
    """
    Model for rate limiting information.
    
    Provides current rate limit status and remaining quota
    information for API responses.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Rate Limit Information",
            "description": "Current rate limiting status and remaining quota information",
            "examples": [
                {
                    "tier": "standard",
                    "requests_per_minute": 60,
                    "requests_per_hour": 1000,
                    "requests_per_day": 10000,
                    "remaining_minute": 45,
                    "remaining_hour": 892,
                    "remaining_day": 8734,
                    "reset_time": "2024-01-15T14:01:00Z",
                    "retry_after": None,
                    "burst_allowed": True,
                    "burst_remaining": 10
                },
                {
                    "tier": "basic",
                    "requests_per_minute": 10,
                    "requests_per_hour": 100,
                    "requests_per_day": 1000,
                    "remaining_minute": 0,
                    "remaining_hour": 45,
                    "remaining_day": 234,
                    "reset_time": "2024-01-15T14:02:00Z",
                    "retry_after": 58,
                    "burst_allowed": False
                }
            ]
        }
    )
    
    tier: str = Field(
        description="Rate limit tier name"
    )
    
    requests_per_minute: int = Field(
        description="Maximum requests per minute"
    )
    
    requests_per_hour: int = Field(
        description="Maximum requests per hour"
    )
    
    requests_per_day: int = Field(
        description="Maximum requests per day"
    )
    
    remaining_minute: int = Field(
        ge=0,
        description="Remaining requests in current minute"
    )
    
    remaining_hour: int = Field(
        ge=0,
        description="Remaining requests in current hour"
    )
    
    remaining_day: int = Field(
        ge=0,
        description="Remaining requests in current day"
    )
    
    reset_time: datetime = Field(
        description="When the current rate limit window resets"
    )
    
    retry_after: Optional[int] = Field(
        default=None,
        description="Seconds to wait before retrying (when rate limited)"
    )
    
    burst_allowed: bool = Field(
        default=False,
        description="Whether burst requests above the limit are allowed"
    )
    
    burst_remaining: Optional[int] = Field(
        default=None,
        description="Remaining burst requests if burst is allowed"
    )
    
    @computed_field
    @property
    def is_rate_limited(self) -> bool:
        """Check if currently rate limited."""
        return self.retry_after is not None and self.retry_after > 0
    
    @computed_field
    @property
    def percentage_used_minute(self) -> float:
        """Percentage of minute limit used."""
        if self.requests_per_minute == 0:
            return 0.0
        return ((self.requests_per_minute - self.remaining_minute) / self.requests_per_minute) * 100
    
    @computed_field
    @property
    def percentage_used_day(self) -> float:
        """Percentage of daily limit used."""
        if self.requests_per_day == 0:
            return 0.0
        return ((self.requests_per_day - self.remaining_day) / self.requests_per_day) * 100
    
    @computed_field
    @property
    def is_near_limit(self) -> bool:
        """Check if near any rate limit (>90% used)."""
        return (
            self.percentage_used_minute > 90 or
            self.percentage_used_day > 90
        )
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "tier": self.tier,
            "remaining_minute": self.remaining_minute,
            "remaining_hour": self.remaining_hour,
            "remaining_day": self.remaining_day,
            "is_rate_limited": self.is_rate_limited,
            "retry_after": self.retry_after,
            "percentage_used_minute": round(self.percentage_used_minute, 1),
            "percentage_used_day": round(self.percentage_used_day, 1),
            "is_near_limit": self.is_near_limit,
            "reset_time": self.reset_time.isoformat()
        }


class ErrorResponse(BaseModel, AnalysisModelMixin):
    """
    Standardized error response model.
    
    Used across all API endpoints to provide consistent
    error information and debugging details.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Error Response",
            "description": "Standardized error response with debugging information and documentation links",
            "examples": [
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Invalid file format",
                        "details": "File must be a valid PE, ELF, or Mach-O binary",
                        "field": "file_format",
                        "timestamp": "2024-01-15T14:15:30Z"
                    },
                    "request_id": "req_1234567890abcdef",
                    "documentation_url": "https://docs.example.com/errors/validation"
                },
                {
                    "error": {
                        "code": "RATE_LIMIT_ERROR",
                        "message": "Rate limit exceeded",
                        "retry_after": 60,
                        "timestamp": "2024-01-15T14:16:00Z"
                    },
                    "request_id": "req_abcdef1234567890",
                    "documentation_url": "https://docs.example.com/rate-limits"
                },
                {
                    "error": {
                        "code": "AUTHENTICATION_ERROR",
                        "message": "Invalid API key",
                        "timestamp": "2024-01-15T14:17:00Z"
                    },
                    "request_id": "req_fedcba0987654321",
                    "documentation_url": "https://docs.example.com/authentication"
                }
            ]
        }
    )
    
    error: Dict[str, Any] = Field(
        description="Error information"
    )
    
    request_id: Optional[str] = Field(
        default=None,
        description="Unique request identifier for debugging"
    )
    
    documentation_url: Optional[str] = Field(
        default=None,
        description="URL to relevant documentation"
    )
    
    support_contact: Optional[str] = Field(
        default=None,
        description="Support contact information"
    )
    
    @field_validator('error')
    @classmethod
    def validate_error_structure(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate error structure."""
        required_fields = ['code', 'message']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Error must contain '{field}' field")
        
        # Ensure timestamp is present
        if 'timestamp' not in v:
            v['timestamp'] = datetime.now().isoformat()
        
        return v
    
    @classmethod
    def validation_error(
        cls,
        message: str,
        field: Optional[str] = None,
        details: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> 'ErrorResponse':
        """Create a validation error response."""
        error_data = {
            "code": "VALIDATION_ERROR",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if field:
            error_data["field"] = field
        if details:
            error_data["details"] = details
        
        return cls(
            error=error_data,
            request_id=request_id,
            documentation_url="https://docs.example.com/errors/validation"
        )
    
    @classmethod
    def authentication_error(
        cls,
        message: str = "Authentication required",
        request_id: Optional[str] = None
    ) -> 'ErrorResponse':
        """Create an authentication error response."""
        return cls(
            error={
                "code": "AUTHENTICATION_ERROR",
                "message": message,
                "timestamp": datetime.now().isoformat()
            },
            request_id=request_id,
            documentation_url="https://docs.example.com/authentication"
        )
    
    @classmethod
    def authorization_error(
        cls,
        message: str = "Insufficient permissions",
        required_scope: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> 'ErrorResponse':
        """Create an authorization error response."""
        error_data = {
            "code": "AUTHORIZATION_ERROR",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if required_scope:
            error_data["required_scope"] = required_scope
        
        return cls(
            error=error_data,
            request_id=request_id,
            documentation_url="https://docs.example.com/authorization"
        )
    
    @classmethod
    def rate_limit_error(
        cls,
        retry_after: int,
        message: str = "Rate limit exceeded",
        request_id: Optional[str] = None
    ) -> 'ErrorResponse':
        """Create a rate limit error response."""
        return cls(
            error={
                "code": "RATE_LIMIT_ERROR",
                "message": message,
                "retry_after": retry_after,
                "timestamp": datetime.now().isoformat()
            },
            request_id=request_id,
            documentation_url="https://docs.example.com/rate-limits"
        )
    
    @classmethod
    def not_found_error(
        cls,
        resource: str,
        resource_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> 'ErrorResponse':
        """Create a not found error response."""
        message = f"{resource} not found"
        if resource_id:
            message += f": {resource_id}"
        
        return cls(
            error={
                "code": "NOT_FOUND_ERROR",
                "message": message,
                "resource": resource,
                "timestamp": datetime.now().isoformat()
            },
            request_id=request_id
        )
    
    @classmethod
    def internal_error(
        cls,
        message: str = "Internal server error",
        error_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> 'ErrorResponse':
        """Create an internal server error response."""
        error_data = {
            "code": "INTERNAL_ERROR",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if error_id:
            error_data["error_id"] = error_id
        
        return cls(
            error=error_data,
            request_id=request_id,
            support_contact="support@example.com"
        )
    
    @classmethod
    def service_unavailable_error(
        cls,
        message: str = "Service temporarily unavailable",
        retry_after: Optional[int] = None,
        request_id: Optional[str] = None
    ) -> 'ErrorResponse':
        """Create a service unavailable error response."""
        error_data = {
            "code": "SERVICE_UNAVAILABLE",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if retry_after:
            error_data["retry_after"] = retry_after
        
        return cls(
            error=error_data,
            request_id=request_id
        )
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "error_code": self.error.get("code"),
            "message": self.error.get("message"),
            "field": self.error.get("field"),
            "timestamp": self.error.get("timestamp"),
            "request_id": self.request_id,
            "has_documentation": self.documentation_url is not None,
            "has_support_contact": self.support_contact is not None
        }


class AuthenticationStatus(BaseModel, AnalysisModelMixin):
    """
    Model for authentication status information.
    
    Provides information about the current authentication
    state and user context.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "title": "Authentication Status",
            "description": "Current authentication state and context information",
            "examples": [
                {
                    "authenticated": True,
                    "key_id": "ak_1234567890abcdef",
                    "scopes": ["analysis:submit", "analysis:read"],
                    "rate_limit": {
                        "tier": "standard",
                        "remaining_day": 8500,
                        "remaining_hour": 890
                    },
                    "ip_address": "192.168.1.100",
                    "user_agent": "AnalysisClient/1.0",
                    "expires_at": "2024-04-15T14:00:00Z"
                },
                {
                    "authenticated": False,
                    "key_id": None,
                    "scopes": [],
                    "rate_limit": None,
                    "ip_address": "203.0.113.45",
                    "user_agent": "curl/7.68.0"
                }
            ]
        }
    )
    
    authenticated: bool = Field(
        description="Whether the request is authenticated"
    )
    
    key_id: Optional[str] = Field(
        default=None,
        description="API key ID if authenticated"
    )
    
    scopes: List[str] = Field(
        default_factory=list,
        description="Available scopes for the authenticated key"
    )
    
    rate_limit: Optional[RateLimitInfo] = Field(
        default=None,
        description="Rate limit information"
    )
    
    ip_address: Optional[str] = Field(
        default=None,
        description="Client IP address"
    )
    
    user_agent: Optional[str] = Field(
        default=None,
        description="Client user agent"
    )
    
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When the authentication expires"
    )
    
    @computed_field
    @property
    def has_scope(self) -> bool:
        """Check if any scopes are available."""
        return len(self.scopes) > 0
    
    def can_access(self, required_scope: str) -> bool:
        """Check if the authenticated key has required scope."""
        return self.authenticated and required_scope in self.scopes
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Create API-friendly summary."""
        return {
            "authenticated": self.authenticated,
            "key_id": self.key_id,
            "scope_count": len(self.scopes),
            "has_rate_limit": self.rate_limit is not None,
            "ip_address": self.ip_address,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


class APIKeyInfo(BaseModel, AnalysisModelMixin):
    """
    Information about an API key and its permissions.
    
    Provides detailed information about API key properties, permissions,
    usage statistics, and current status.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "key_id": "ak_1234567890abcdef",
                    "name": "Production Analysis Key",
                    "description": "Main API key for production analysis workflows",
                    "scopes": ["analysis:submit", "analysis:read", "jobs:manage"],
                    "tier": "premium",
                    "status": "active",
                    "created_at": "2024-01-01T00:00:00Z",
                    "expires_at": "2024-12-31T23:59:59Z",
                    "last_used_at": "2024-01-15T14:30:00Z",
                    "usage_stats": {
                        "requests_today": 450,
                        "requests_this_month": 12500,
                        "total_requests": 125000
                    },
                    "rate_limits": {
                        "requests_per_minute": 100,
                        "requests_per_hour": 5000,
                        "requests_per_day": 50000
                    }
                }
            ]
        }
    )
    
    key_id: str = Field(
        description="Unique API key identifier"
    )
    
    name: Optional[str] = Field(
        default=None,
        description="Human-readable name for the API key"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Description of the API key's purpose"
    )
    
    scopes: List[str] = Field(
        default_factory=list,
        description="List of permissions/scopes for this API key"
    )
    
    tier: str = Field(
        default="standard",
        pattern="^(free|standard|premium|enterprise)$",
        description="API key tier determining rate limits and features"
    )
    
    status: str = Field(
        default="active",
        pattern="^(active|inactive|suspended|revoked|expired)$",
        description="Current status of the API key"
    )
    
    created_at: datetime = Field(
        description="When the API key was created"
    )
    
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When the API key expires (if applicable)"
    )
    
    last_used_at: Optional[datetime] = Field(
        default=None,
        description="When the API key was last used"
    )
    
    usage_stats: Dict[str, int] = Field(
        default_factory=dict,
        description="Usage statistics for the API key"
    )
    
    rate_limits: Dict[str, int] = Field(
        default_factory=dict,
        description="Rate limit configuration for this key"
    )
    
    ip_whitelist: List[str] = Field(
        default_factory=list,
        description="IP addresses allowed to use this key (if restricted)"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for organizing and categorizing API keys"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the API key"
    )
    
    @field_validator('scopes')
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Validate and normalize scopes."""
        if not v:
            return []
        
        valid_scopes = [
            'analysis:submit', 'analysis:read', 'analysis:delete',
            'jobs:read', 'jobs:manage', 'jobs:cancel',
            'upload:create', 'upload:read',
            'admin:keys', 'admin:users', 'admin:system'
        ]
        
        normalized = []
        for scope in v:
            scope = scope.strip().lower()
            if scope in valid_scopes:
                normalized.append(scope)
            else:
                # Allow custom scopes but validate format
                if ':' in scope and len(scope) <= 50:
                    normalized.append(scope)
        
        return list(dict.fromkeys(normalized))  # Remove duplicates
    
    @field_validator('ip_whitelist')
    @classmethod
    def validate_ip_whitelist(cls, v: List[str]) -> List[str]:
        """Validate IP addresses in whitelist."""
        if not v:
            return []
        
        import ipaddress
        validated_ips = []
        
        for ip in v:
            try:
                # Validate IP address or CIDR block
                ipaddress.ip_network(ip.strip(), strict=False)
                validated_ips.append(ip.strip())
            except ValueError:
                # Skip invalid IP addresses
                continue
        
        return validated_ips
    
    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if API key is currently active."""
        if self.status != "active":
            return False
        
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        
        return True
    
    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if API key has expired."""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    @computed_field
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Get number of days until expiry."""
        if not self.expires_at:
            return None
        
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)
    
    @computed_field
    @property
    def is_recently_used(self) -> bool:
        """Check if key was used in the last 7 days."""
        if not self.last_used_at:
            return False
        
        days_since_use = (datetime.now() - self.last_used_at).days
        return days_since_use <= 7
    
    @computed_field
    @property
    def key_summary(self) -> Dict[str, Any]:
        """Get summary information about the API key."""
        return {
            "key_id": self.key_id,
            "name": self.name,
            "tier": self.tier,
            "status": self.status,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "scope_count": len(self.scopes),
            "has_ip_restrictions": len(self.ip_whitelist) > 0,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "days_until_expiry": self.days_until_expiry,
            "is_recently_used": self.is_recently_used,
            "total_requests": self.usage_stats.get("total_requests", 0),
            "requests_today": self.usage_stats.get("requests_today", 0)
        }
    
    def has_scope(self, required_scope: str) -> bool:
        """Check if key has required scope."""
        return required_scope in self.scopes
    
    def has_any_scope(self, required_scopes: List[str]) -> bool:
        """Check if key has any of the required scopes."""
        return any(scope in self.scopes for scope in required_scopes)
    
    def has_all_scopes(self, required_scopes: List[str]) -> bool:
        """Check if key has all required scopes."""
        return all(scope in self.scopes for scope in required_scopes)
    
    def can_access_ip(self, ip_address: str) -> bool:
        """Check if IP address is allowed to use this key."""
        if not self.ip_whitelist:
            return True  # No restrictions
        
        import ipaddress
        try:
            client_ip = ipaddress.ip_address(ip_address)
            for allowed_ip in self.ip_whitelist:
                if client_ip in ipaddress.ip_network(allowed_ip, strict=False):
                    return True
            return False
        except ValueError:
            return False
    
    def get_rate_limit_info(self) -> Dict[str, int]:
        """Get rate limit information for this key."""
        default_limits = {
            "requests_per_minute": 60,
            "requests_per_hour": 1000,
            "requests_per_day": 10000
        }
        
        # Tier-based defaults
        tier_limits = {
            "free": {"requests_per_minute": 10, "requests_per_hour": 100, "requests_per_day": 1000},
            "standard": {"requests_per_minute": 60, "requests_per_hour": 1000, "requests_per_day": 10000},
            "premium": {"requests_per_minute": 200, "requests_per_hour": 5000, "requests_per_day": 100000},
            "enterprise": {"requests_per_minute": 500, "requests_per_hour": 20000, "requests_per_day": 1000000}
        }
        
        # Start with tier defaults
        limits = tier_limits.get(self.tier, default_limits).copy()
        
        # Override with specific rate limits if provided
        limits.update(self.rate_limits)
        
        return limits
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the API key."""
        tag = tag.strip().lower()
        if tag and tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the API key."""
        tag = tag.strip().lower()
        if tag in self.tags:
            self.tags.remove(tag)
    
    def update_usage_stats(self, requests_today: int, requests_this_month: int, total_requests: int) -> None:
        """Update usage statistics."""
        self.usage_stats.update({
            "requests_today": requests_today,
            "requests_this_month": requests_this_month,
            "total_requests": total_requests
        })
        
        self.last_used_at = datetime.now()
    
    @classmethod
    def create_new_key(
        cls,
        name: str,
        scopes: List[str],
        tier: str = "standard",
        expires_in_days: Optional[int] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> 'APIKeyInfo':
        """Create a new API key info instance."""
        import secrets
        import string
        
        # Generate key ID
        key_id = f"ak_{''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(16))}"
        
        # Set expiration if specified
        expires_at = None
        if expires_in_days:
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(days=expires_in_days)
        
        return cls(
            key_id=key_id,
            name=name,
            description=description,
            scopes=scopes,
            tier=tier,
            status="active",
            created_at=datetime.now(),
            expires_at=expires_at,
            **kwargs
        )