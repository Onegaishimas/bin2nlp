"""
API request/response models for the bin2nlp analysis system.

This module provides data models for API endpoints including request
validation, response formatting, and error handling.
"""

from .analysis import (
    DecompilationRequest, DecompilationSubmissionResponse,
    AnalysisSummaryResponse, AnalysisDetailResponse,
    FileUploadRequest, FileUploadResponse, AnalysisConfigRequest
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
    "AnalysisConfigRequest",
    
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