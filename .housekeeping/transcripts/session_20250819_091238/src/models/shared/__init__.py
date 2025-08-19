"""
Shared base models and enumerations for the bin2nlp analysis system.

This module provides foundational data models and enumerations used across
the binary analysis and API components.
"""

from .base import BaseModel, TimestampedModel
from .enums import (
    JobStatus,
    FileFormat,
    Platform,
    JOB_STATE_TRANSITIONS,
    validate_job_transition,
    get_file_format_from_extension,  # DEPRECATED - use get_file_format_from_magika_label
    get_file_format_from_magika_label
)

__all__ = [
    # Base models
    "BaseModel",
    "TimestampedModel",
    
    # Enumerations
    "JobStatus",
    "FileFormat",
    "Platform",
    
    # Utilities
    "JOB_STATE_TRANSITIONS",
    "validate_job_transition", 
    "get_file_format_from_extension",  # DEPRECATED
    "get_file_format_from_magika_label",
]