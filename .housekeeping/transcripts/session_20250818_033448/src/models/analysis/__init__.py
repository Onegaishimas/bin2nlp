"""
Analysis domain models for the bin2nlp decompilation system.

This module provides simplified data models for basic binary metadata,
decompilation configuration, and file handling. Complex analysis models
have been moved to the decompilation module for LLM translation.
"""

from .config import AnalysisConfig, AnalysisRequest, AnalysisConfigBuilder
from .basic_results import (
    BasicDecompilationResult, DecompilationMetadata,
    BasicFunctionInfo, BasicStringInfo, BasicImportInfo
)
from .files import FileMetadata, BinaryFile, ValidationResult, HashInfo
from .serialization import (
    AnalysisModelMixin, validate_hex_address, validate_hash_string,
    validate_string_list, validate_confidence_score,
    ExportFormats, create_analysis_export, validate_analysis_data_integrity
)

# Legacy imports for backward compatibility (deprecated)
# TODO: Remove in future version once migration is complete
try:
    from .results import AnalysisResult, FunctionInfo, StringExtraction
    _LEGACY_AVAILABLE = True
except ImportError:
    _LEGACY_AVAILABLE = False

__all__ = [
    # Configuration models
    "AnalysisConfig",
    "AnalysisRequest", 
    "AnalysisConfigBuilder",
    
    # Basic decompilation models (new)
    "BasicDecompilationResult",
    "DecompilationMetadata",
    "BasicFunctionInfo",
    "BasicStringInfo", 
    "BasicImportInfo",
    
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
    "validate_confidence_score",
    "ExportFormats",
    "create_analysis_export",
    "validate_analysis_data_integrity",
]

# Legacy exports (deprecated)
if _LEGACY_AVAILABLE:
    __all__.extend([
        "AnalysisResult",  # Deprecated: Use DecompilationResult from decompilation module
        "FunctionInfo",    # Deprecated: Use BasicFunctionInfo
        "StringExtraction" # Deprecated: Use BasicStringInfo
    ])