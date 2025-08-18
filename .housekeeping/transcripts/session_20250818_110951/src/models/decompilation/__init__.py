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

__all__ = [
    'DecompilationResult',
    'FunctionTranslation',
    'ImportTranslation', 
    'StringTranslation',
    'OverallSummary'
]