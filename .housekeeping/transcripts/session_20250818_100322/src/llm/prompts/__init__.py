"""
LLM Prompt Templates

Standardized prompt templates and context-aware management for decompilation translation tasks.
"""

from .base import (
    PromptTemplate, 
    PromptVersion, 
    TranslationQuality,
    ContextBuilder
)
from .function_translation import (
    get_function_prompt, 
    list_available_function_prompts,
    FUNCTION_TRANSLATION_PROMPTS,
    SPECIALIZED_FUNCTION_PROMPTS
)
from .import_explanation import (
    get_import_prompt,
    list_available_import_prompts, 
    IMPORT_EXPLANATION_PROMPTS,
    SPECIALIZED_IMPORT_PROMPTS
)
from .string_interpretation import (
    get_string_prompt,
    list_available_string_prompts,
    STRING_INTERPRETATION_PROMPTS,
    SPECIALIZED_STRING_PROMPTS
)
from .overall_summary import (
    get_summary_prompt,
    list_available_summary_prompts,
    OVERALL_SUMMARY_PROMPTS,
    SPECIALIZED_SUMMARY_PROMPTS
)
from .manager import (
    ContextualPromptManager,
    AnalysisContext,
    contextual_prompt_manager
)

__all__ = [
    # Base classes and utilities
    'PromptTemplate',
    'PromptVersion', 
    'TranslationQuality',
    'ContextBuilder',
    
    # Function translation
    'get_function_prompt',
    'list_available_function_prompts',
    'FUNCTION_TRANSLATION_PROMPTS',
    'SPECIALIZED_FUNCTION_PROMPTS',
    
    # Import explanation
    'get_import_prompt',
    'list_available_import_prompts',
    'IMPORT_EXPLANATION_PROMPTS', 
    'SPECIALIZED_IMPORT_PROMPTS',
    
    # String interpretation
    'get_string_prompt',
    'list_available_string_prompts',
    'STRING_INTERPRETATION_PROMPTS',
    'SPECIALIZED_STRING_PROMPTS',
    
    # Overall summary
    'get_summary_prompt',
    'list_available_summary_prompts', 
    'OVERALL_SUMMARY_PROMPTS',
    'SPECIALIZED_SUMMARY_PROMPTS',
    
    # Context-aware management
    'ContextualPromptManager',
    'AnalysisContext',
    'contextual_prompt_manager'
]