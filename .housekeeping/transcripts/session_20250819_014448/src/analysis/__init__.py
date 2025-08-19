"""
Binary analysis support components.

This package provides remaining analysis components used by the decompilation system:
- R2 radare2 integration
- Error recovery system
- Base analysis interfaces (kept for compatibility)
"""

from .engines.base import AnalysisEngine

__all__ = [
    'AnalysisEngine'  # Kept for compatibility, may be removed in future cleanup
]