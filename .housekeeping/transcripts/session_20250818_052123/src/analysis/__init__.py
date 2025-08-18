"""
Binary analysis engine components.

This package provides the core binary analysis functionality including
file format detection, radare2 integration, and analysis processors.
"""

from .processors.format_detector import FormatDetector
from .engines.base import AnalysisEngine

__all__ = [
    'FormatDetector',
    'AnalysisEngine'
]