"""
Decompilation-focused data models.

This package contains Pydantic models for binary decompilation and LLM translation
results, replacing the complex analysis processor models with focused translation
data structures.
"""

from .results import (
    DecompilationResult,
    FunctionTranslation, 
    ImportTranslation,
    StringTranslation,
    OverallSummary
)
from .basic_results import (
    BasicDecompilationResult, 
    DecompilationMetadata,
    BasicFunctionInfo, 
    BasicStringInfo, 
    BasicImportInfo
)

__all__ = [
    'DecompilationResult',
    'FunctionTranslation',
    'ImportTranslation', 
    'StringTranslation',
    'OverallSummary',
    'BasicDecompilationResult', 
    'DecompilationMetadata',
    'BasicFunctionInfo', 
    'BasicStringInfo', 
    'BasicImportInfo'
]