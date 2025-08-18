"""
Analysis processors for different aspects of binary analysis.

This module contains processors for format detection, function analysis,
security scanning, and other specialized analysis operations.
"""

from .format_detector import FormatDetector

__all__ = [
    'FormatDetector'
]