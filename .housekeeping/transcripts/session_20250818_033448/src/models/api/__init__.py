"""
API request/response models for the bin2nlp analysis system.

This module provides data models for API endpoints including request
validation, response formatting, and error handling.
"""

from .analysis import (
    AnalysisSubmissionRequest, AnalysisSubmissionResponse,
    AnalysisSummaryResponse, AnalysisDetailResponse
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
    # Analysis API models
    "AnalysisSubmissionRequest",
    "AnalysisSubmissionResponse", 
    "AnalysisSummaryResponse",
    "AnalysisDetailResponse",
    
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