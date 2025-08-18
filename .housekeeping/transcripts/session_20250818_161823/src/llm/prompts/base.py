"""
Base Prompt Template System

Standardized prompt template management for consistent LLM translations
across all providers with versioning and optimization capabilities.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict


class PromptVersion(str, Enum):
    """Prompt template versions for A/B testing and optimization."""
    V1 = "v1"
    V2 = "v2"
    V3 = "v3"
    LATEST = "latest"


class TranslationQuality(str, Enum):
    """Quality levels for translation detail."""
    BRIEF = "brief"           # Concise explanations
    STANDARD = "standard"     # Balanced detail
    COMPREHENSIVE = "comprehensive"  # Detailed explanations with context


class PromptTemplate(BaseModel):
    """
    Standardized prompt template for LLM translations.
    
    Provides versioned, provider-adaptable prompts with quality metrics
    and optimization capabilities.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "template_id": "function_translation_v1",
                    "version": "v1",
                    "operation_type": "function_translation",
                    "system_prompt": "You are an expert binary analyst...",
                    "user_prompt_template": "Analyze this function: {function_data}",
                    "expected_tokens": 400,
                    "temperature": 0.1,
                    "max_tokens": 800
                }
            ]
        }
    )
    
    template_id: str = Field(
        ...,
        pattern=r"^[a-z_]+_v\d+$",
        description="Unique template identifier (e.g., 'function_translation_v1')"
    )
    
    version: PromptVersion = Field(
        ...,
        description="Template version for A/B testing and rollbacks"
    )
    
    operation_type: str = Field(
        ...,
        description="Type of translation operation (function, import, string, summary)"
    )
    
    quality_level: TranslationQuality = Field(
        default=TranslationQuality.STANDARD,
        description="Target quality/detail level for responses"
    )
    
    # Core prompt components
    system_prompt: str = Field(
        ...,
        min_length=50,
        description="System prompt defining AI role and capabilities"
    )
    
    user_prompt_template: str = Field(
        ...,
        min_length=20,
        description="User prompt template with variable placeholders"
    )
    
    # Provider-specific adaptations
    provider_adaptations: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Provider-specific prompt variations and enhancements"
    )
    
    # Generation parameters
    expected_tokens: int = Field(
        ...,
        ge=50,
        le=8000,
        description="Expected token count for response generation"
    )
    
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature setting for generation consistency"
    )
    
    max_tokens: int = Field(
        ...,
        ge=100,
        le=8192,
        description="Maximum tokens for response generation"
    )
    
    # Quality and performance metrics
    success_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Historical success rate for this template"
    )
    
    average_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Average quality score from evaluations"
    )
    
    average_response_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Average response time across providers"
    )
    
    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Template creation timestamp"
    )
    
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last modification timestamp"
    )
    
    usage_count: int = Field(
        default=0,
        ge=0,
        description="Number of times this template has been used"
    )
    
    notes: Optional[str] = Field(
        default=None,
        description="Development and optimization notes"
    )
    
    @field_validator('template_id')
    @classmethod
    def validate_template_id(cls, v: str) -> str:
        """Validate template ID format."""
        if not v:
            raise ValueError("Template ID cannot be empty")
        
        # Check format: operation_type_version
        parts = v.split('_')
        if len(parts) < 2 or not parts[-1].startswith('v'):
            raise ValueError("Template ID must end with version (e.g., '_v1')")
        
        return v.lower()
    
    def get_adapted_prompt(self, provider_id: str) -> Tuple[str, str]:
        """
        Get provider-adapted system and user prompts.
        
        Args:
            provider_id: LLM provider identifier
            
        Returns:
            Tuple of (system_prompt, user_prompt_template) adapted for provider
        """
        system_prompt = self.system_prompt
        user_prompt = self.user_prompt_template
        
        # Apply provider-specific adaptations
        if provider_id in self.provider_adaptations:
            adaptations = self.provider_adaptations[provider_id]
            
            # Apply system prompt modifications
            if "system_prompt_prefix" in adaptations:
                system_prompt = adaptations["system_prompt_prefix"] + "\n\n" + system_prompt
            
            if "system_prompt_suffix" in adaptations:
                system_prompt = system_prompt + "\n\n" + adaptations["system_prompt_suffix"]
            
            if "system_prompt_replace" in adaptations:
                system_prompt = adaptations["system_prompt_replace"]
            
            # Apply user prompt modifications
            if "user_prompt_prefix" in adaptations:
                user_prompt = adaptations["user_prompt_prefix"] + "\n\n" + user_prompt
            
            if "user_prompt_suffix" in adaptations:
                user_prompt = user_prompt + "\n\n" + adaptations["user_prompt_suffix"]
            
            if "user_prompt_replace" in adaptations:
                user_prompt = adaptations["user_prompt_replace"]
        
        return system_prompt, user_prompt
    
    def render_user_prompt(self, context: Dict[str, Any]) -> str:
        """
        Render user prompt template with provided context variables.
        
        Args:
            context: Dictionary of variables to substitute in template
            
        Returns:
            Rendered user prompt string
            
        Raises:
            KeyError: If required template variables are missing
        """
        try:
            return self.user_prompt_template.format(**context)
        except KeyError as e:
            missing_var = str(e).strip("'")
            raise KeyError(f"Missing required template variable: {missing_var}")
    
    def update_metrics(
        self, 
        success: bool, 
        quality_score: Optional[float] = None,
        response_time_ms: Optional[float] = None
    ) -> None:
        """Update template performance metrics."""
        self.usage_count += 1
        self.last_updated = datetime.utcnow()
        
        # Update success rate (exponential moving average)
        if self.success_rate == 0.0:
            self.success_rate = 1.0 if success else 0.0
        else:
            alpha = 0.1  # Smoothing factor
            new_success = 1.0 if success else 0.0
            self.success_rate = (1 - alpha) * self.success_rate + alpha * new_success
        
        # Update quality score
        if quality_score is not None:
            if self.average_quality_score == 0.0:
                self.average_quality_score = quality_score
            else:
                alpha = 0.1
                self.average_quality_score = ((1 - alpha) * self.average_quality_score + 
                                            alpha * quality_score)
        
        # Update response time
        if response_time_ms is not None:
            if self.average_response_time_ms == 0.0:
                self.average_response_time_ms = response_time_ms
            else:
                alpha = 0.1
                self.average_response_time_ms = ((1 - alpha) * self.average_response_time_ms + 
                                               alpha * response_time_ms)


class PromptTemplateRegistry(ABC):
    """
    Abstract registry for managing prompt templates with versioning
    and optimization capabilities.
    """
    
    @abstractmethod
    async def get_template(
        self, 
        operation_type: str,
        provider_id: str,
        quality_level: TranslationQuality = TranslationQuality.STANDARD,
        version: PromptVersion = PromptVersion.LATEST
    ) -> PromptTemplate:
        """Get prompt template for operation and provider."""
        pass
    
    @abstractmethod
    async def register_template(self, template: PromptTemplate) -> None:
        """Register a new prompt template."""
        pass
    
    @abstractmethod
    async def update_template_metrics(
        self,
        template_id: str,
        success: bool,
        quality_score: Optional[float] = None,
        response_time_ms: Optional[float] = None,
        provider_id: Optional[str] = None
    ) -> None:
        """Update template performance metrics."""
        pass
    
    @abstractmethod
    async def get_template_stats(self, template_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics for a template."""
        pass
    
    @abstractmethod 
    async def list_templates(
        self, 
        operation_type: Optional[str] = None,
        provider_id: Optional[str] = None
    ) -> List[PromptTemplate]:
        """List available templates with optional filtering."""
        pass


class ContextBuilder:
    """
    Builder for creating context dictionaries for prompt template rendering.
    
    Provides standardized context creation for different translation operations
    with appropriate data formatting and validation.
    """
    
    @staticmethod
    def build_function_context(
        function_data: Dict[str, Any],
        file_info: Optional[Dict[str, Any]] = None,
        related_functions: Optional[List[Dict[str, Any]]] = None,
        imports: Optional[List[Dict[str, Any]]] = None,
        strings: Optional[List[Dict[str, Any]]] = None,
        quality_level: TranslationQuality = TranslationQuality.STANDARD
    ) -> Dict[str, Any]:
        """Build context for function translation prompts."""
        context = {
            "function_name": function_data.get("name", "unknown"),
            "function_address": function_data.get("address", "0x0"),
            "function_size": function_data.get("size", 0),
            "assembly_code": function_data.get("assembly_code", "Not available"),
            "decompiled_code": function_data.get("decompiled_code", "Not available"),
            "function_calls": ", ".join(function_data.get("calls_to", [])) or "None identified",
            "variables": ", ".join(function_data.get("variables", [])) or "None identified",
            "is_entry_point": function_data.get("is_entry_point", False),
            "is_imported": function_data.get("is_imported", False)
        }
        
        # Add file context if available
        if file_info:
            context["file_name"] = file_info.get("name", "unknown")
            context["file_format"] = file_info.get("format", "unknown") 
            context["file_platform"] = file_info.get("platform", "unknown")
            context["file_architecture"] = file_info.get("architecture", "unknown")
        
        # Add related functions for context (limited by quality level)
        if related_functions:
            limit = {"brief": 3, "standard": 5, "comprehensive": 10}[quality_level]
            context["related_functions"] = [
                f"{func.get('name', 'unknown')} ({func.get('address', '0x0')})"
                for func in related_functions[:limit]
            ]
        
        # Add relevant imports
        if imports:
            limit = {"brief": 5, "standard": 10, "comprehensive": 20}[quality_level]
            context["relevant_imports"] = [
                f"{imp.get('library', 'unknown')}!{imp.get('function', 'unknown')}"
                for imp in imports[:limit]
            ]
        
        # Add relevant strings
        if strings:
            limit = {"brief": 3, "standard": 5, "comprehensive": 10}[quality_level]
            context["relevant_strings"] = [
                f'"{s.get("content", "")[:50]}..."' if len(s.get("content", "")) > 50
                else f'"{s.get("content", "")}"'
                for s in strings[:limit]
            ]
        
        return context
    
    @staticmethod
    def build_import_context(
        imports: List[Dict[str, Any]],
        file_info: Optional[Dict[str, Any]] = None,
        usage_analysis: Optional[Dict[str, Any]] = None,
        quality_level: TranslationQuality = TranslationQuality.STANDARD
    ) -> Dict[str, Any]:
        """Build context for import explanation prompts."""
        context = {
            "import_count": len(imports),
            "imports": imports,
            "unique_libraries": list(set(imp.get("library", "unknown") for imp in imports))
        }
        
        # Group imports by library
        imports_by_lib = {}
        for imp in imports:
            lib = imp.get("library", "unknown")
            if lib not in imports_by_lib:
                imports_by_lib[lib] = []
            imports_by_lib[lib].append(imp.get("function", "unknown"))
        
        context["imports_by_library"] = imports_by_lib
        
        # Add file context
        if file_info:
            context["file_format"] = file_info.get("format", "unknown")
            context["file_platform"] = file_info.get("platform", "unknown")
            context["target_architecture"] = file_info.get("architecture", "unknown")
        
        # Add usage analysis if available
        if usage_analysis:
            context["usage_patterns"] = usage_analysis.get("patterns", [])
            context["frequency_data"] = usage_analysis.get("frequency", {})
        
        return context
    
    @staticmethod
    def build_string_context(
        strings: List[Dict[str, Any]],
        file_info: Optional[Dict[str, Any]] = None,
        function_references: Optional[Dict[str, List[str]]] = None,
        quality_level: TranslationQuality = TranslationQuality.STANDARD
    ) -> Dict[str, Any]:
        """Build context for string interpretation prompts."""
        # Categorize strings by type for better analysis
        categorized_strings = {
            "urls": [],
            "file_paths": [],
            "registry_keys": [],
            "error_messages": [],
            "config_values": [],
            "general": []
        }
        
        for string in strings:
            content = string.get("content", "").lower()
            if any(proto in content for proto in ["http://", "https://", "ftp://"]):
                categorized_strings["urls"].append(string)
            elif any(path_char in content for path_char in ["\\", "/", ".exe", ".dll"]):
                categorized_strings["file_paths"].append(string)
            elif any(reg_key in content for reg_key in ["hkey_", "software\\", "system\\"]):
                categorized_strings["registry_keys"].append(string)
            elif any(error_word in content for error_word in ["error", "failed", "exception"]):
                categorized_strings["error_messages"].append(string)
            elif "=" in content or ":" in content:
                categorized_strings["config_values"].append(string)
            else:
                categorized_strings["general"].append(string)
        
        context = {
            "total_strings": len(strings),
            "categorized_strings": categorized_strings,
            "strings": strings
        }
        
        # Add file context
        if file_info:
            context["file_type"] = file_info.get("format", "unknown")
            context["target_platform"] = file_info.get("platform", "unknown")
        
        # Add function reference information
        if function_references:
            context["function_references"] = function_references
        
        return context
    
    @staticmethod
    def build_summary_context(
        file_info: Dict[str, Any],
        functions: List[Dict[str, Any]],
        imports: List[Dict[str, Any]],
        strings: List[Dict[str, Any]],
        quality_level: TranslationQuality = TranslationQuality.STANDARD
    ) -> Dict[str, Any]:
        """Build context for overall summary prompts."""
        context = {
            "file_info": file_info,
            "total_functions": len(functions),
            "total_imports": len(imports),
            "total_strings": len(strings)
        }
        
        # Function analysis summary
        if functions:
            entry_points = [f for f in functions if f.get("is_entry_point")]
            imported_funcs = [f for f in functions if f.get("is_imported")]
            
            context["function_summary"] = {
                "entry_points": len(entry_points),
                "imported_functions": len(imported_funcs),
                "internal_functions": len(functions) - len(imported_funcs),
                "key_functions": [f.get("name", "unknown") for f in functions[:10]]
            }
        
        # Import analysis summary
        if imports:
            libraries = list(set(imp.get("library", "unknown") for imp in imports))
            context["import_summary"] = {
                "unique_libraries": libraries,
                "library_count": len(libraries),
                "top_libraries": libraries[:5]
            }
        
        # String analysis summary
        if strings:
            context["string_summary"] = {
                "encoding_types": list(set(s.get("encoding", "ascii") for s in strings)),
                "sample_strings": [s.get("content", "")[:100] for s in strings[:10]]
            }
        
        return context