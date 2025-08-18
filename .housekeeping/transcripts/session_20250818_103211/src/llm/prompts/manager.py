"""
Context-Aware Prompt Management System

Intelligent prompt selection and management system that adapts prompts based on
context, provider capabilities, and analysis requirements.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

from .base import (
    PromptTemplate, 
    PromptTemplateRegistry, 
    PromptVersion, 
    TranslationQuality,
    ContextBuilder
)
from .function_translation import get_function_prompt, list_available_function_prompts
from .import_explanation import get_import_prompt, list_available_import_prompts
from .string_interpretation import get_string_prompt, list_available_string_prompts
from .overall_summary import get_summary_prompt, list_available_summary_prompts
from ..base import TranslationOperationType

logger = logging.getLogger(__name__)


class AnalysisContext(str, Enum):
    """Context types for intelligent prompt selection."""
    MALWARE_ANALYSIS = "malware_analysis"
    VULNERABILITY_RESEARCH = "vulnerability_research" 
    REVERSE_ENGINEERING = "reverse_engineering"
    THREAT_INTELLIGENCE = "threat_intelligence"
    SOFTWARE_AUDIT = "software_audit"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    ACADEMIC_RESEARCH = "academic_research"


class ContextualPromptManager:
    """
    Context-aware prompt management system that intelligently selects and adapts
    prompts based on analysis context, provider capabilities, and data characteristics.
    """
    
    def __init__(self):
        """Initialize the contextual prompt manager."""
        self.templates: Dict[str, PromptTemplate] = {}
        self.context_preferences: Dict[AnalysisContext, Dict[str, Any]] = {}
        self.provider_preferences: Dict[str, Dict[str, Any]] = {}
        self._setup_default_preferences()
        
    def _setup_default_preferences(self) -> None:
        """Setup default context and provider preferences."""
        
        # Context-specific preferences
        self.context_preferences = {
            AnalysisContext.MALWARE_ANALYSIS: {
                "preferred_quality": TranslationQuality.STANDARD,
                "specialized_prompts": {
                    "function_translation": "security_analysis",
                    "import_explanation": "malware_analysis", 
                    "string_interpretation": "security_analysis",
                    "overall_summary": "threat_intelligence"
                },
                "emphasis": ["security", "threat_detection", "behavioral_analysis"]
            },
            
            AnalysisContext.VULNERABILITY_RESEARCH: {
                "preferred_quality": TranslationQuality.COMPREHENSIVE,
                "specialized_prompts": {
                    "function_translation": "security_analysis",
                    "import_explanation": "security_analysis",
                    "string_interpretation": "security_analysis", 
                    "overall_summary": "malware_report"
                },
                "emphasis": ["vulnerability_detection", "exploit_analysis", "security_assessment"]
            },
            
            AnalysisContext.REVERSE_ENGINEERING: {
                "preferred_quality": TranslationQuality.COMPREHENSIVE,
                "specialized_prompts": {
                    "function_translation": "algorithm_analysis",
                    "import_explanation": None,
                    "string_interpretation": "config_analysis",
                    "overall_summary": None
                },
                "emphasis": ["algorithm_analysis", "implementation_details", "architecture_assessment"]
            },
            
            AnalysisContext.THREAT_INTELLIGENCE: {
                "preferred_quality": TranslationQuality.STANDARD,
                "specialized_prompts": {
                    "function_translation": "security_analysis",
                    "import_explanation": "malware_analysis",
                    "string_interpretation": "security_analysis",
                    "overall_summary": "threat_intelligence"
                },
                "emphasis": ["attribution", "campaign_analysis", "threat_classification"]
            },
            
            AnalysisContext.PERFORMANCE_ANALYSIS: {
                "preferred_quality": TranslationQuality.STANDARD,
                "specialized_prompts": {
                    "function_translation": "algorithm_analysis",
                    "import_explanation": None,
                    "string_interpretation": "config_analysis",
                    "overall_summary": None
                },
                "emphasis": ["performance_optimization", "efficiency_analysis", "scalability_assessment"]
            },
            
            AnalysisContext.SOFTWARE_AUDIT: {
                "preferred_quality": TranslationQuality.COMPREHENSIVE,
                "specialized_prompts": {
                    "function_translation": None,
                    "import_explanation": "security_analysis",
                    "string_interpretation": "config_analysis",
                    "overall_summary": "malware_report"
                },
                "emphasis": ["code_quality", "security_assessment", "compliance_analysis"]
            },
            
            AnalysisContext.ACADEMIC_RESEARCH: {
                "preferred_quality": TranslationQuality.COMPREHENSIVE,
                "specialized_prompts": {
                    "function_translation": "algorithm_analysis",
                    "import_explanation": None,
                    "string_interpretation": None,
                    "overall_summary": None
                },
                "emphasis": ["technical_accuracy", "detailed_analysis", "methodological_rigor"]
            }
        }
        
        # Provider-specific preferences
        self.provider_preferences = {
            "anthropic": {
                "strengths": ["detailed_reasoning", "security_analysis", "nuanced_assessment"],
                "preferred_contexts": [AnalysisContext.MALWARE_ANALYSIS, AnalysisContext.VULNERABILITY_RESEARCH],
                "quality_bonus": {TranslationQuality.COMPREHENSIVE: 0.2},
                "operation_bonus": {
                    TranslationOperationType.FUNCTION_TRANSLATION: 0.1,
                    TranslationOperationType.OVERALL_SUMMARY: 0.15
                }
            },
            
            "openai": {
                "strengths": ["structured_output", "consistent_formatting", "balanced_analysis"],
                "preferred_contexts": [AnalysisContext.REVERSE_ENGINEERING, AnalysisContext.SOFTWARE_AUDIT],
                "quality_bonus": {TranslationQuality.STANDARD: 0.1},
                "operation_bonus": {
                    TranslationOperationType.IMPORT_EXPLANATION: 0.1,
                    TranslationOperationType.STRING_INTERPRETATION: 0.05
                }
            },
            
            "gemini": {
                "strengths": ["performance_analysis", "competitive_intelligence", "cost_efficiency"],
                "preferred_contexts": [AnalysisContext.PERFORMANCE_ANALYSIS, AnalysisContext.ACADEMIC_RESEARCH],
                "quality_bonus": {TranslationQuality.BRIEF: 0.1, TranslationQuality.STANDARD: 0.05},
                "operation_bonus": {
                    TranslationOperationType.STRING_INTERPRETATION: 0.1,
                    TranslationOperationType.FUNCTION_TRANSLATION: 0.05
                }
            }
        }
    
    def select_prompt(
        self,
        operation_type: TranslationOperationType,
        provider_id: str,
        context: AnalysisContext = AnalysisContext.REVERSE_ENGINEERING,
        quality_override: Optional[TranslationQuality] = None,
        data_characteristics: Optional[Dict[str, Any]] = None
    ) -> PromptTemplate:
        """
        Intelligently select the most appropriate prompt template.
        
        Args:
            operation_type: Type of translation operation
            provider_id: LLM provider identifier
            context: Analysis context for intelligent selection
            quality_override: Override default quality level
            data_characteristics: Characteristics of the data being analyzed
            
        Returns:
            Optimally selected prompt template
        """
        
        # Get context preferences
        context_prefs = self.context_preferences.get(context, {})
        
        # Determine quality level
        quality_level = quality_override or context_prefs.get("preferred_quality", TranslationQuality.STANDARD)
        
        # Check for specialized prompt preferences
        specialized_type = None
        specialized_prefs = context_prefs.get("specialized_prompts", {})
        if operation_type.value in specialized_prefs:
            specialized_type = specialized_prefs[operation_type.value]
        
        # Adapt based on data characteristics
        if data_characteristics:
            quality_level, specialized_type = self._adapt_for_data_characteristics(
                quality_level, specialized_type, data_characteristics, context
            )
        
        # Select appropriate prompt template
        try:
            if operation_type == TranslationOperationType.FUNCTION_TRANSLATION:
                template = get_function_prompt(quality_level, PromptVersion.V1, specialized_type)
            elif operation_type == TranslationOperationType.IMPORT_EXPLANATION:
                template = get_import_prompt(quality_level, PromptVersion.V1, specialized_type)
            elif operation_type == TranslationOperationType.STRING_INTERPRETATION:
                template = get_string_prompt(quality_level, PromptVersion.V1, specialized_type)
            elif operation_type == TranslationOperationType.OVERALL_SUMMARY:
                template = get_summary_prompt(quality_level, PromptVersion.V1, specialized_type)
            else:
                raise ValueError(f"Unknown operation type: {operation_type}")
            
            logger.info(f"Selected prompt: {template.template_id} for {operation_type} with {provider_id}")
            return template
            
        except KeyError as e:
            logger.warning(f"Failed to select specialized prompt: {e}. Falling back to standard.")
            # Fallback to standard prompts
            if operation_type == TranslationOperationType.FUNCTION_TRANSLATION:
                return get_function_prompt(quality_level, PromptVersion.V1)
            elif operation_type == TranslationOperationType.IMPORT_EXPLANATION:
                return get_import_prompt(quality_level, PromptVersion.V1)
            elif operation_type == TranslationOperationType.STRING_INTERPRETATION:
                return get_string_prompt(quality_level, PromptVersion.V1)
            elif operation_type == TranslationOperationType.OVERALL_SUMMARY:
                return get_summary_prompt(quality_level, PromptVersion.V1)
    
    def _adapt_for_data_characteristics(
        self,
        quality_level: TranslationQuality,
        specialized_type: Optional[str],
        data_characteristics: Dict[str, Any],
        context: AnalysisContext
    ) -> Tuple[TranslationQuality, Optional[str]]:
        """Adapt prompt selection based on data characteristics."""
        
        # Adapt based on data complexity
        complexity_indicators = data_characteristics.get("complexity_indicators", {})
        
        # High complexity data may benefit from comprehensive analysis
        if complexity_indicators.get("high_function_count", False) or \
           complexity_indicators.get("complex_imports", False):
            if quality_level == TranslationQuality.BRIEF:
                quality_level = TranslationQuality.STANDARD
            elif quality_level == TranslationQuality.STANDARD and context in [
                AnalysisContext.VULNERABILITY_RESEARCH, AnalysisContext.SOFTWARE_AUDIT
            ]:
                quality_level = TranslationQuality.COMPREHENSIVE
        
        # Adapt based on security indicators
        security_indicators = data_characteristics.get("security_indicators", {})
        if security_indicators.get("suspicious_apis", False) or \
           security_indicators.get("obfuscated_strings", False) or \
           security_indicators.get("crypto_functions", False):
            
            # Switch to security-focused analysis
            if not specialized_type or specialized_type not in ["security_analysis", "malware_analysis"]:
                if context in [AnalysisContext.MALWARE_ANALYSIS, AnalysisContext.THREAT_INTELLIGENCE]:
                    specialized_type = "security_analysis"
        
        # Adapt based on performance indicators
        performance_indicators = data_characteristics.get("performance_indicators", {})
        if performance_indicators.get("optimization_patterns", False) or \
           performance_indicators.get("simd_instructions", False):
            
            if context == AnalysisContext.PERFORMANCE_ANALYSIS:
                specialized_type = "algorithm_analysis"
        
        return quality_level, specialized_type
    
    def build_context_for_operation(
        self,
        operation_type: TranslationOperationType,
        data: Dict[str, Any],
        file_info: Optional[Dict[str, Any]] = None,
        analysis_context: AnalysisContext = AnalysisContext.REVERSE_ENGINEERING,
        quality_level: TranslationQuality = TranslationQuality.STANDARD
    ) -> Dict[str, Any]:
        """
        Build optimized context dictionary for prompt rendering.
        
        Args:
            operation_type: Type of translation operation
            data: Primary data for the operation
            file_info: File metadata and context
            analysis_context: Analysis context for optimization
            quality_level: Quality level for context sizing
            
        Returns:
            Optimized context dictionary for prompt rendering
        """
        
        if operation_type == TranslationOperationType.FUNCTION_TRANSLATION:
            return ContextBuilder.build_function_context(
                function_data=data,
                file_info=file_info,
                related_functions=data.get("related_functions"),
                imports=data.get("relevant_imports"),
                strings=data.get("relevant_strings"),
                quality_level=quality_level
            )
        
        elif operation_type == TranslationOperationType.IMPORT_EXPLANATION:
            return ContextBuilder.build_import_context(
                imports=data.get("imports", []),
                file_info=file_info,
                usage_analysis=data.get("usage_analysis"),
                quality_level=quality_level
            )
        
        elif operation_type == TranslationOperationType.STRING_INTERPRETATION:
            return ContextBuilder.build_string_context(
                strings=data.get("strings", []),
                file_info=file_info,
                function_references=data.get("function_references"),
                quality_level=quality_level
            )
        
        elif operation_type == TranslationOperationType.OVERALL_SUMMARY:
            return ContextBuilder.build_summary_context(
                file_info=file_info or {},
                functions=data.get("functions", []),
                imports=data.get("imports", []),
                strings=data.get("strings", []),
                quality_level=quality_level
            )
        
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")
    
    def get_provider_score(
        self,
        provider_id: str,
        operation_type: TranslationOperationType,
        context: AnalysisContext,
        quality_level: TranslationQuality
    ) -> float:
        """
        Calculate provider suitability score for given operation and context.
        
        Args:
            provider_id: LLM provider identifier
            operation_type: Type of translation operation
            context: Analysis context
            quality_level: Quality level required
            
        Returns:
            Suitability score (0.0 - 1.0)
        """
        
        base_score = 0.5  # Base compatibility score
        
        provider_prefs = self.provider_preferences.get(provider_id, {})
        
        # Context preference bonus
        preferred_contexts = provider_prefs.get("preferred_contexts", [])
        if context in preferred_contexts:
            base_score += 0.2
        
        # Quality level bonus
        quality_bonus = provider_prefs.get("quality_bonus", {})
        if quality_level in quality_bonus:
            base_score += quality_bonus[quality_level]
        
        # Operation type bonus  
        operation_bonus = provider_prefs.get("operation_bonus", {})
        if operation_type in operation_bonus:
            base_score += operation_bonus[operation_type]
        
        return min(1.0, max(0.0, base_score))
    
    def analyze_data_characteristics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze data characteristics to inform prompt selection.
        
        Args:
            data: Analysis data to characterize
            
        Returns:
            Dictionary of data characteristics for prompt adaptation
        """
        
        characteristics = {
            "complexity_indicators": {},
            "security_indicators": {},
            "performance_indicators": {},
            "content_indicators": {}
        }
        
        # Analyze function complexity
        functions = data.get("functions", [])
        if functions:
            avg_size = sum(f.get("size", 0) for f in functions) / len(functions)
            characteristics["complexity_indicators"]["high_function_count"] = len(functions) > 50
            characteristics["complexity_indicators"]["large_functions"] = avg_size > 1000
            characteristics["complexity_indicators"]["complex_calls"] = any(
                len(f.get("calls_to", [])) > 10 for f in functions
            )
        
        # Analyze import patterns
        imports = data.get("imports", [])
        if imports:
            api_libraries = set(imp.get("library", "").lower() for imp in imports)
            
            # Security-relevant APIs
            security_apis = {"kernel32", "ntdll", "advapi32", "wininet", "ws2_32"}
            crypto_apis = {"bcrypt", "cryptsp", "crypt32"}
            
            characteristics["security_indicators"]["suspicious_apis"] = bool(
                security_apis.intersection(api_libraries)
            )
            characteristics["security_indicators"]["crypto_functions"] = bool(
                crypto_apis.intersection(api_libraries)
            )
            characteristics["complexity_indicators"]["complex_imports"] = len(imports) > 30
        
        # Analyze string patterns
        strings = data.get("strings", [])
        if strings:
            string_contents = [s.get("content", "").lower() for s in strings]
            
            characteristics["security_indicators"]["obfuscated_strings"] = any(
                len(s) > 50 and not any(c.isalpha() for c in s) for s in string_contents
            )
            
            characteristics["content_indicators"]["has_urls"] = any(
                "http" in s for s in string_contents
            )
            
            characteristics["content_indicators"]["has_file_paths"] = any(
                "\\" in s or "/" in s for s in string_contents
            )
        
        return characteristics
    
    def get_available_prompts(self) -> Dict[str, Dict[str, List[str]]]:
        """Get comprehensive list of available prompt templates."""
        return {
            "function_translation": list_available_function_prompts(),
            "import_explanation": list_available_import_prompts(),
            "string_interpretation": list_available_string_prompts(),
            "overall_summary": list_available_summary_prompts()
        }
    
    def get_context_recommendations(
        self,
        file_info: Dict[str, Any],
        analysis_summary: Dict[str, Any]
    ) -> List[Tuple[AnalysisContext, float]]:
        """
        Recommend appropriate analysis contexts based on file and analysis data.
        
        Args:
            file_info: File metadata and information
            analysis_summary: Summary of analysis results
            
        Returns:
            List of (context, confidence) tuples sorted by relevance
        """
        
        context_scores = {}
        
        # Analyze file characteristics
        file_type = file_info.get("format", "").lower()
        platform = file_info.get("platform", "").lower()
        
        # Base scoring based on file characteristics
        if "exe" in file_type or "dll" in file_type:
            context_scores[AnalysisContext.MALWARE_ANALYSIS] = 0.6
            context_scores[AnalysisContext.REVERSE_ENGINEERING] = 0.7
            context_scores[AnalysisContext.SOFTWARE_AUDIT] = 0.5
        
        # Analyze content for context clues
        security_indicators = analysis_summary.get("security_indicators", 0)
        if security_indicators > 5:
            context_scores[AnalysisContext.MALWARE_ANALYSIS] = context_scores.get(
                AnalysisContext.MALWARE_ANALYSIS, 0.0
            ) + 0.3
            context_scores[AnalysisContext.THREAT_INTELLIGENCE] = 0.8
        
        complexity_score = analysis_summary.get("complexity_score", 0)
        if complexity_score > 7:
            context_scores[AnalysisContext.VULNERABILITY_RESEARCH] = 0.7
            context_scores[AnalysisContext.REVERSE_ENGINEERING] = context_scores.get(
                AnalysisContext.REVERSE_ENGINEERING, 0.0
            ) + 0.2
        
        # Sort by score and return recommendations
        sorted_contexts = sorted(context_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_contexts[:3]  # Return top 3 recommendations


# Global instance for easy access
contextual_prompt_manager = ContextualPromptManager()