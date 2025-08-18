"""
Analysis domain models for the bin2nlp analysis system.

This module provides data models for analysis configuration, requests,
results, and file handling used in binary analysis operations.
"""

from .config import AnalysisConfig, AnalysisRequest, AnalysisConfigBuilder
from .results import (
    AnalysisResult, SecurityFindings, SecurityFinding, 
    FunctionInfo, StringInfo, StringExtraction, StringContext
)
from .files import FileMetadata, BinaryFile, ValidationResult, HashInfo
from .serialization import (
    AnalysisModelMixin, validate_hex_address, validate_hash_string,
    validate_string_list, validate_severity_level, validate_confidence_score,
    ExportFormats, create_analysis_export, validate_analysis_data_integrity
)

__all__ = [
    # Configuration models
    "AnalysisConfig",
    "AnalysisRequest", 
    "AnalysisConfigBuilder",
    
    # Result models
    "AnalysisResult",
    "SecurityFindings",
    "SecurityFinding",
    "FunctionInfo",
    "StringInfo",
    "StringExtraction",
    "StringContext",
    
    # File models
    "FileMetadata",
    "BinaryFile",
    "ValidationResult",
    "HashInfo",
    
    # Serialization utilities
    "AnalysisModelMixin",
    "validate_hex_address",
    "validate_hash_string",
    "validate_string_list",
    "validate_severity_level",
    "validate_confidence_score",
    "ExportFormats",
    "create_analysis_export",
    "validate_analysis_data_integrity",
]