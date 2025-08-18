"""
API request/response models for the bin2nlp analysis system.

This module provides data models for API endpoints including request
validation, response formatting, and error handling.
"""

from .analysis import (
    DecompilationRequest, DecompilationSubmissionResponse,
    AnalysisSummaryResponse, AnalysisDetailResponse,
    FileUploadRequest, FileUploadResponse, DecompilationConfigRequest
)
from .jobs import (
    JobCreationRequest, JobStatusResponse, JobListResponse,
    JobActionRequest, JobActionResponse
)
from .auth import (
    APIKeyRequest, APIKeyResponse, RateLimitInfo,
    ErrorResponse, AuthenticationStatus
)

__all__ = [
    # Analysis API models (decompilation-focused)
    "DecompilationRequest",
    "DecompilationSubmissionResponse", 
    "AnalysisSummaryResponse",
    "AnalysisDetailResponse",
    "FileUploadRequest",
    "FileUploadResponse",
    "DecompilationConfigRequest",
    
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