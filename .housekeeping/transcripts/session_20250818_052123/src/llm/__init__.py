"""
LLM Provider Framework

Multi-LLM provider integration for binary decompilation translation.
Supports OpenAI, Anthropic, and Google Gemini providers with unified interface.
"""

from .base import LLMProvider, LLMConfig, TranslationRequest, TranslationResponse
from .providers.factory import LLMProviderFactory

__all__ = [
    'LLMProvider',
    'LLMConfig', 
    'TranslationRequest',
    'TranslationResponse',
    'LLMProviderFactory'
]