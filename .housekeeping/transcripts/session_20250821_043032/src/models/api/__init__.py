"""
API request/response models for the bin2nlp analysis system.

This module provides data models for API endpoints including request
validation, response formatting, and error handling.
"""

# Legacy analysis models removed - use decompilation models instead
from .jobs import (
    JobCreationRequest, JobStatusResponse, JobListResponse,
    JobActionRequest, JobActionResponse
)
from .auth import (
    APIKeyRequest, APIKeyResponse, RateLimitInfo,
    ErrorResponse, AuthenticationStatus
)

__all__ = [
    # Job API models
    "JobCreationRequest",
    "JobStatusResponse",
    "JobListResponse", 
    "JobActionRequest",
    "JobActionResponse",
    
    # Auth API models
    "APIKeyRequest",
    "APIKeyResponse",
    "RateLimitInfo",
    "ErrorResponse",
    "AuthenticationStatus",
]