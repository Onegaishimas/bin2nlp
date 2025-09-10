"""
API models for user LLM provider operations.

Provides Pydantic models for request/response handling in user provider endpoints
with validation and serialization.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field, validator

from ...llm.base import LLMProviderType


class UserLLMProviderCreate(BaseModel):
    """Request model for creating a new user LLM provider."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User-defined provider name"
    )
    provider_type: LLMProviderType = Field(
        ...,
        description="Type of LLM provider"
    )
    api_key: str = Field(
        ...,
        min_length=1,
        description="API key for the provider (will be encrypted before storage)"
    )
    endpoint_url: Optional[str] = Field(
        None,
        max_length=500,
        description="Custom endpoint URL (required for ollama providers)"
    )
    config_json: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional provider-specific configuration options"
    )
    
    @validator('name')
    def validate_name(cls, v):
        """Ensure provider name is not empty and properly formatted."""
        if not v or not v.strip():
            raise ValueError('Provider name cannot be empty')
        return v.strip()
    
    @validator('endpoint_url')
    def validate_endpoint_url_for_ollama(cls, v, values):
        """Validate that Ollama providers have endpoint URLs."""
        provider_type = values.get('provider_type')
        if provider_type == LLMProviderType.OLLAMA:
            if not v:
                raise ValueError('endpoint_url is required for ollama providers')
            if not v.startswith(('http://', 'https://')):
                raise ValueError('endpoint_url must be a valid HTTP/HTTPS URL')
        return v
    
    @validator('api_key')
    def validate_api_key(cls, v):
        """Basic API key validation."""
        if not v or not v.strip():
            raise ValueError('API key cannot be empty')
        # For ollama, allow fake keys
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "name": "My OpenAI Provider",
                "provider_type": "openai",
                "api_key": "sk-1234567890abcdef...",
                "config_json": {
                    "default_model": "gpt-4",
                    "max_tokens": 4000
                }
            }
        }


class UserLLMProviderUpdate(BaseModel):
    """Request model for updating a user LLM provider."""
    
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Updated provider name"
    )
    api_key: Optional[str] = Field(
        None,
        min_length=1,
        description="Updated API key (will be encrypted before storage)"
    )
    endpoint_url: Optional[str] = Field(
        None,
        max_length=500,
        description="Updated endpoint URL"
    )
    config_json: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated configuration options"
    )
    is_active: Optional[bool] = Field(
        None,
        description="Updated active status"
    )
    
    @validator('name')
    def validate_name(cls, v):
        """Ensure provider name is not empty and properly formatted."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Provider name cannot be empty')
            return v.strip()
        return v
    
    @validator('api_key')
    def validate_api_key(cls, v):
        """Basic API key validation."""
        if v is not None:
            if not v or not v.strip():
                raise ValueError('API key cannot be empty')
            return v.strip()
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Updated Provider Name",
                "is_active": True,
                "config_json": {
                    "max_tokens": 8000
                }
            }
        }


class UserLLMProviderResponse(BaseModel):
    """Response model for user LLM provider information."""
    
    id: str = Field(..., description="Provider UUID")
    name: str = Field(..., description="Provider name")
    provider_type: LLMProviderType = Field(..., description="Provider type")
    endpoint_url: Optional[str] = Field(None, description="Endpoint URL (for ollama)")
    config_json: Dict[str, Any] = Field(default_factory=dict, description="Configuration options")
    is_active: bool = Field(..., description="Whether provider is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    # Note: encrypted_api_key is never included in responses for security
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "My OpenAI Provider",
                "provider_type": "openai",
                "endpoint_url": None,
                "config_json": {
                    "default_model": "gpt-4",
                    "max_tokens": 4000
                },
                "is_active": True,
                "created_at": "2025-09-06T10:00:00Z",
                "updated_at": "2025-09-06T10:00:00Z"
            }
        }


class UserLLMProviderListResponse(BaseModel):
    """Response model for listing user LLM providers."""
    
    providers: List[UserLLMProviderResponse] = Field(
        ...,
        description="List of user LLM providers"
    )
    total: int = Field(..., description="Total number of providers")
    active_count: int = Field(..., description="Number of active providers")
    
    class Config:
        schema_extra = {
            "example": {
                "providers": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "My OpenAI Provider",
                        "provider_type": "openai",
                        "endpoint_url": None,
                        "config_json": {},
                        "is_active": True,
                        "created_at": "2025-09-06T10:00:00Z",
                        "updated_at": "2025-09-06T10:00:00Z"
                    }
                ],
                "total": 1,
                "active_count": 1
            }
        }


class ProviderTestRequest(BaseModel):
    """Request model for testing provider connectivity."""
    
    # Empty for now - may add test parameters in the future
    pass


class ProviderTestResult(BaseModel):
    """Response model for provider connectivity test."""
    
    success: bool = Field(..., description="Whether the test succeeded")
    message: str = Field(..., description="Test result message")
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")
    provider_info: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional provider information from test"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "OpenAI provider configured successfully",
                "latency_ms": 150.5,
                "provider_info": {
                    "provider_type": "openai",
                    "endpoint_url": "https://api.openai.com/v1"
                }
            }
        }


class ProviderTypesResponse(BaseModel):
    """Response model for available provider types."""
    
    provider_types: List[Dict[str, Any]] = Field(
        ...,
        description="Available provider types with metadata"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "provider_types": [
                    {
                        "type": "openai",
                        "name": "OpenAI",
                        "description": "OpenAI GPT models",
                        "requires_endpoint": False,
                        "supports_streaming": True
                    },
                    {
                        "type": "anthropic",
                        "name": "Anthropic",
                        "description": "Anthropic Claude models",
                        "requires_endpoint": False,
                        "supports_streaming": True
                    },
                    {
                        "type": "gemini",
                        "name": "Google Gemini",
                        "description": "Google Gemini models",
                        "requires_endpoint": False,
                        "supports_streaming": False
                    },
                    {
                        "type": "ollama",
                        "name": "Ollama",
                        "description": "Local Ollama server",
                        "requires_endpoint": True,
                        "supports_streaming": True
                    }
                ]
            }
        }


# Error response models
class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")
    
    class Config:
        schema_extra = {
            "example": {
                "detail": "Provider not found",
                "error_code": "PROVIDER_NOT_FOUND"
            }
        }


class ValidationErrorResponse(BaseModel):
    """Validation error response model."""
    
    detail: List[Dict[str, Any]] = Field(..., description="Validation error details")
    
    class Config:
        schema_extra = {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "name"],
                        "msg": "Provider name cannot be empty",
                        "type": "value_error"
                    }
                ]
            }
        }


# Helper functions
def convert_provider_to_response(provider) -> UserLLMProviderResponse:
    """
    Convert UserLLMProvider model to API response model.
    
    Args:
        provider: UserLLMProvider instance
        
    Returns:
        UserLLMProviderResponse instance
    """
    return UserLLMProviderResponse(
        id=str(provider.id),
        name=provider.name,
        provider_type=provider.provider_type,
        endpoint_url=provider.endpoint_url,
        config_json=provider.config_json or {},
        is_active=provider.is_active,
        created_at=provider.created_at,
        updated_at=provider.updated_at
    )


def get_provider_types_info() -> List[Dict[str, Any]]:
    """
    Get information about available provider types.
    
    Returns:
        List of provider type information
    """
    return [
        {
            "type": "openai",
            "name": "OpenAI",
            "description": "OpenAI GPT models for high-quality natural language processing",
            "requires_endpoint": False,
            "supports_streaming": True,
            "config_fields": {
                "api_key": {
                    "type": "string",
                    "required": True,
                    "description": "OpenAI API key"
                }
            }
        },
        {
            "type": "anthropic",
            "name": "Anthropic",
            "description": "Anthropic Claude models for advanced reasoning and analysis",
            "requires_endpoint": False,
            "supports_streaming": True,
            "config_fields": {
                "api_key": {
                    "type": "string",
                    "required": True,
                    "description": "Anthropic API key"
                }
            }
        },
        {
            "type": "gemini",
            "name": "Google Gemini",
            "description": "Google Gemini models for multimodal AI capabilities",
            "requires_endpoint": False,
            "supports_streaming": False,
            "config_fields": {
                "api_key": {
                    "type": "string",
                    "required": True,
                    "description": "Google AI API key"
                }
            }
        },
        {
            "type": "ollama",
            "name": "Ollama",
            "description": "Local Ollama server for privacy-focused inference",
            "requires_endpoint": True,
            "supports_streaming": True,
            "config_fields": {
                "api_key": {
                    "type": "string",
                    "required": True,
                    "description": "Placeholder API key (can be any value)"
                },
                "endpoint_url": {
                    "type": "string",
                    "required": True,
                    "description": "Ollama server endpoint URL"
                }
            }
        }
    ]