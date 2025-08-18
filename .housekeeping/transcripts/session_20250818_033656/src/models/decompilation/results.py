"""
Decompilation result models for binary decompilation and LLM translation operations.

This module provides Pydantic models for storing and representing decompilation results
including LLM-translated function descriptions, import explanations, string interpretations,
and overall program summaries.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field, ConfigDict

from ..shared.base import BaseModel, TimestampedModel
from ..shared.enums import FileFormat, Platform
from enum import Enum


class DecompilationDepth(str, Enum):
    """Decompilation analysis depth levels."""
    BASIC = "basic"          # Function discovery and basic metadata
    STANDARD = "standard"    # Functions + imports + strings
    COMPREHENSIVE = "comprehensive"  # Full analysis with cross-references


class TranslationDetail(str, Enum):
    """Natural language translation detail levels."""
    BRIEF = "brief"          # Concise explanations
    STANDARD = "standard"    # Balanced detail
    COMPREHENSIVE = "comprehensive"  # Detailed explanations with context


class LLMProviderMetadata(BaseModel):
    """
    Metadata about the LLM provider used for translation.
    
    Contains information about which provider was used, model settings,
    and performance metrics for the translation.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "provider": "openai",
                    "model": "gpt-4",
                    "tokens_used": 450,
                    "processing_time_ms": 1200,
                    "api_version": "2023-12-01",
                    "custom_endpoint": None
                }
            ]
        }
    )
    
    provider: str = Field(
        description="LLM provider name (openai, anthropic, gemini)"
    )
    
    model: str = Field(
        description="Specific model used (gpt-4, claude-3-sonnet, gemini-pro)"
    )
    
    tokens_used: int = Field(
        ge=0,
        description="Total tokens consumed for this translation"
    )
    
    processing_time_ms: int = Field(
        ge=0,
        description="Time taken for LLM processing in milliseconds"
    )
    
    api_version: Optional[str] = Field(
        default=None,
        description="API version used for the request"
    )
    
    custom_endpoint: Optional[str] = Field(
        default=None,
        description="Custom API endpoint URL (for OpenAI-compatible providers)"
    )
    
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Temperature setting used for generation"
    )
    
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum tokens limit for the response"
    )
    
    cost_estimate_usd: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Estimated cost in USD for this translation"
    )


class FunctionTranslation(BaseModel):
    """
    LLM translation result for a single function.
    
    Contains the natural language explanation of a function's purpose,
    parameters, return values, and security implications based on
    assembly code analysis.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "function_name": "authenticate_user",
                    "address": "0x401000",
                    "size": 256,
                    "natural_language_description": "This function validates user credentials using bcrypt hashing...",
                    "parameters_explanation": "Takes username (string) and password_hash (string) parameters...",
                    "return_value_explanation": "Returns boolean indicating authentication success...",
                    "security_analysis": "Implements secure password hashing with timing attack protection...",
                    "confidence_score": 0.92,
                    "llm_provider": {"provider": "anthropic", "model": "claude-3-sonnet"}
                }
            ]
        }
    )
    
    function_name: str = Field(
        description="Assigned function name (may be original or LLM-generated)"
    )
    
    address: str = Field(
        description="Memory address of function entry point (hex format)"
    )
    
    size: int = Field(
        ge=1,
        description="Size of function in bytes"
    )
    
    assembly_code: Optional[str] = Field(
        default=None,
        description="Raw assembly code that was translated"
    )
    
    natural_language_description: str = Field(
        description="Natural language explanation of function's purpose and behavior"
    )
    
    parameters_explanation: Optional[str] = Field(
        default=None,
        description="Explanation of function parameters and their purposes"
    )
    
    return_value_explanation: Optional[str] = Field(
        default=None,
        description="Explanation of function return values and error conditions"
    )
    
    assembly_summary: Optional[str] = Field(
        default=None,
        description="Technical summary of assembly-level implementation details"
    )
    
    security_analysis: Optional[str] = Field(
        default=None,
        description="Security implications and vulnerability analysis"
    )
    
    performance_notes: Optional[str] = Field(
        default=None,
        description="Performance characteristics and optimization notes"
    )
    
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM's confidence in the translation accuracy (0.0-1.0)"
    )
    
    reasoning: Optional[str] = Field(
        default=None,
        description="LLM's reasoning for the analysis (mainly for Claude)"
    )
    
    llm_provider: LLMProviderMetadata = Field(
        description="Metadata about the LLM provider used for translation"
    )
    
    context_used: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context information used for translation (imports, strings, etc.)"
    )
    
    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate memory address format."""
        if not v:
            raise ValueError("Address cannot be empty")
        
        v = v.strip()
        if not v.startswith('0x'):
            v = '0x' + v
        
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hexadecimal address: {v}")
        
        return v.lower()
    
    @computed_field
    @property
    def is_high_confidence(self) -> bool:
        """Check if translation has high confidence."""
        return self.confidence_score >= 0.8
    
    @computed_field
    @property
    def has_security_implications(self) -> bool:
        """Check if function has identified security implications."""
        return self.security_analysis is not None and len(self.security_analysis) > 0
    
    @computed_field
    @property
    def translation_summary(self) -> Dict[str, Any]:
        """Get summary of translation results."""
        return {
            "function_name": self.function_name,
            "address": self.address,
            "size": self.size,
            "confidence_score": self.confidence_score,
            "is_high_confidence": self.is_high_confidence,
            "has_security_implications": self.has_security_implications,
            "llm_provider": self.llm_provider.provider,
            "llm_model": self.llm_provider.model,
            "tokens_used": self.llm_provider.tokens_used,
            "processing_time_ms": self.llm_provider.processing_time_ms,
            "has_parameters": self.parameters_explanation is not None,
            "has_return_info": self.return_value_explanation is not None
        }


class ImportTranslation(BaseModel):
    """
    LLM translation result for imported functions and libraries.
    
    Contains detailed explanations of external API calls including
    their purpose, parameters, security implications, and usage context.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "library_name": "kernel32.dll",
                    "function_name": "CreateFileA",
                    "api_documentation_summary": "Creates or opens a file for I/O operations...",
                    "usage_context": "Used for file creation in Windows applications...",
                    "parameters_description": "lpFileName: path to file, dwDesiredAccess: access rights...",
                    "security_implications": "Requires path validation to prevent directory traversal...",
                    "confidence_score": 0.95,
                    "llm_provider": {"provider": "gemini", "model": "gemini-pro"}
                }
            ]
        }
    )
    
    library_name: str = Field(
        description="Name of the imported library (DLL, SO, dylib, etc.)"
    )
    
    function_name: str = Field(
        description="Name of the imported function"
    )
    
    api_documentation_summary: str = Field(
        description="Summary of the API function's official documentation and purpose"
    )
    
    usage_context: str = Field(
        description="Context of how this API is typically used in applications"
    )
    
    parameters_description: Optional[str] = Field(
        default=None,
        description="Detailed description of function parameters and their meanings"
    )
    
    return_value_description: Optional[str] = Field(
        default=None,
        description="Description of return values and error conditions"
    )
    
    security_implications: Optional[str] = Field(
        default=None,
        description="Security considerations and potential vulnerabilities"
    )
    
    alternative_apis: List[str] = Field(
        default_factory=list,
        description="Alternative or related APIs that could be used instead"
    )
    
    common_misuses: List[str] = Field(
        default_factory=list,
        description="Common ways this API is misused or can lead to vulnerabilities"
    )
    
    detection_signatures: List[str] = Field(
        default_factory=list,
        description="Patterns that security tools use to detect suspicious usage"
    )
    
    legitimate_vs_malicious: Optional[str] = Field(
        default=None,
        description="Analysis of legitimate vs suspicious usage patterns"
    )
    
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM's confidence in the analysis accuracy (0.0-1.0)"
    )
    
    llm_provider: LLMProviderMetadata = Field(
        description="Metadata about the LLM provider used for translation"
    )
    
    cross_references: List[str] = Field(
        default_factory=list,
        description="Functions in the binary that use this import"
    )
    
    @field_validator('alternative_apis', 'common_misuses', 'detection_signatures', 'cross_references')
    @classmethod
    def validate_string_lists(cls, v: List[str]) -> List[str]:
        """Validate and clean string lists."""
        if not v:
            return []
        
        cleaned = []
        for item in v:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())
        
        return list(dict.fromkeys(cleaned))  # Remove duplicates
    
    @computed_field
    @property
    def full_api_name(self) -> str:
        """Get full API name including library."""
        return f"{self.library_name}!{self.function_name}"
    
    @computed_field
    @property
    def is_high_risk(self) -> bool:
        """Check if import is considered high risk based on security implications."""
        if not self.security_implications:
            return False
        
        high_risk_keywords = [
            'critical', 'high risk', 'vulnerability', 'exploit',
            'injection', 'overflow', 'privilege escalation'
        ]
        
        security_text = self.security_implications.lower()
        return any(keyword in security_text for keyword in high_risk_keywords)


class StringTranslation(BaseModel):
    """
    LLM translation result for extracted strings.
    
    Contains interpretation of string usage, context analysis,
    and security implications based on the string content and
    its usage within the binary.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "string_value": "SELECT * FROM users WHERE id = ?",
                    "address": "0x403000",
                    "encoding": "ascii",
                    "usage_context": "Database query for user authentication",
                    "interpretation": "Parameterized SQL query using prepared statements...",
                    "security_analysis": "Properly parameterized query prevents SQL injection...",
                    "confidence_score": 0.88,
                    "llm_provider": {"provider": "openai", "model": "gpt-4"}
                }
            ]
        }
    )
    
    string_value: str = Field(
        description="The actual string content"
    )
    
    address: str = Field(
        description="Memory address where string was found (hex format)"
    )
    
    size: int = Field(
        ge=1,
        description="Size of string in bytes"
    )
    
    encoding: str = Field(
        default="ascii",
        description="Character encoding (ascii, unicode, utf-16, etc.)"
    )
    
    usage_context: str = Field(
        description="Analysis of how and where this string is likely used"
    )
    
    interpretation: str = Field(
        description="Natural language interpretation of the string's meaning and purpose"
    )
    
    encoding_details: Optional[str] = Field(
        default=None,
        description="Technical details about string encoding and format"
    )
    
    security_analysis: Optional[str] = Field(
        default=None,
        description="Security implications of this string's content or usage"
    )
    
    data_classification: Optional[str] = Field(
        default=None,
        description="Classification of data type (credential, URL, path, config, etc.)"
    )
    
    obfuscation_analysis: Optional[str] = Field(
        default=None,
        description="Analysis of any obfuscation or encoding applied to the string"
    )
    
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM's confidence in the interpretation (0.0-1.0)"
    )
    
    llm_provider: LLMProviderMetadata = Field(
        description="Metadata about the LLM provider used for translation"
    )
    
    cross_references: List[str] = Field(
        default_factory=list,
        description="Functions or locations that reference this string"
    )
    
    related_strings: List[str] = Field(
        default_factory=list,
        description="Other strings that appear related or used together"
    )
    
    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate memory address format."""
        if not v:
            raise ValueError("Address cannot be empty")
        
        v = v.strip()
        if not v.startswith('0x'):
            v = '0x' + v
        
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hexadecimal address: {v}")
        
        return v.lower()
    
    @computed_field
    @property
    def is_potentially_sensitive(self) -> bool:
        """Check if string might contain sensitive information."""
        if not self.security_analysis:
            return False
        
        sensitive_keywords = [
            'credential', 'password', 'key', 'token', 'secret',
            'sensitive', 'private', 'confidential'
        ]
        
        analysis_text = self.security_analysis.lower()
        return any(keyword in analysis_text for keyword in sensitive_keywords)
    
    @computed_field
    @property
    def string_category(self) -> str:
        """Categorize the string based on its content and interpretation."""
        value_lower = self.string_value.lower()
        
        # URL patterns
        if any(protocol in value_lower for protocol in ['http://', 'https://', 'ftp://', 'file://']):
            return "url"
        
        # File path patterns
        if any(path_char in value_lower for path_char in ['\\', '/', '.exe', '.dll', '.so']):
            return "file_path"
        
        # Registry path patterns
        if any(reg_prefix in value_lower for reg_prefix in ['hkey_', 'software\\', 'system\\']):
            return "registry_path"
        
        # SQL patterns
        if any(sql_keyword in value_lower for sql_keyword in ['select ', 'insert ', 'update ', 'delete ']):
            return "sql_query"
        
        # Error/debug messages
        if any(msg_word in value_lower for msg_word in ['error', 'failed', 'debug', 'warning']):
            return "error_message"
        
        # Format strings
        if '%' in value_lower or '{}' in value_lower or '{' in value_lower:
            return "format_string"
        
        return "general"


class OverallSummary(BaseModel):
    """
    LLM-generated overall summary of the binary's purpose and functionality.
    
    Provides high-level analysis combining insights from functions, imports,
    strings, and structural analysis to describe the program's main purpose,
    architecture, and security characteristics.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "program_purpose": "Network file transfer utility with encryption capabilities",
                    "main_functionality": "Provides secure file transfer over TCP with AES encryption...",
                    "architecture_overview": "Multi-threaded client-server application using Windows sockets...",
                    "data_flow_description": "Input files are encrypted, transmitted via TCP, and decrypted on receiver...",
                    "security_analysis": "Implements AES-256 encryption with proper key exchange...",
                    "key_insights": ["Uses secure cryptographic libraries", "Proper error handling implemented"],
                    "confidence_score": 0.87,
                    "llm_provider": {"provider": "anthropic", "model": "claude-3-opus"}
                }
            ]
        }
    )
    
    program_purpose: str = Field(
        description="High-level description of what the program is designed to do"
    )
    
    main_functionality: str = Field(
        description="Detailed explanation of the program's core functionality and features"
    )
    
    architecture_overview: str = Field(
        description="Analysis of the program's overall architecture and design patterns"
    )
    
    data_flow_description: str = Field(
        description="Description of how data flows through the program"
    )
    
    security_analysis: str = Field(
        description="Overall security assessment including strengths and weaknesses"
    )
    
    technology_stack: List[str] = Field(
        default_factory=list,
        description="Technologies, libraries, and frameworks used"
    )
    
    key_insights: List[str] = Field(
        default_factory=list,
        description="Important insights and notable characteristics discovered"
    )
    
    potential_use_cases: List[str] = Field(
        default_factory=list,
        description="Legitimate and potential malicious use cases"
    )
    
    risk_assessment: Optional[str] = Field(
        default=None,
        description="Overall risk assessment from security perspective"
    )
    
    behavioral_indicators: List[str] = Field(
        default_factory=list,
        description="Observable behavioral patterns and indicators"
    )
    
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM's confidence in the overall analysis (0.0-1.0)"
    )
    
    llm_provider: LLMProviderMetadata = Field(
        description="Metadata about the LLM provider used for translation"
    )
    
    synthesis_notes: Optional[str] = Field(
        default=None,
        description="Notes on how different analysis components were synthesized"
    )
    
    @computed_field
    @property
    def is_likely_malicious(self) -> bool:
        """Check if program exhibits characteristics of malicious software."""
        if not self.risk_assessment:
            return False
        
        malicious_indicators = [
            'malware', 'trojan', 'virus', 'backdoor', 'rootkit',
            'keylogger', 'stealer', 'ransomware', 'suspicious'
        ]
        
        risk_text = self.risk_assessment.lower()
        return any(indicator in risk_text for indicator in malicious_indicators)
    
    @computed_field
    @property
    def complexity_level(self) -> str:
        """Assess the complexity level of the program."""
        insight_count = len(self.key_insights)
        tech_count = len(self.technology_stack)
        
        if insight_count >= 10 or tech_count >= 8:
            return "high"
        elif insight_count >= 5 or tech_count >= 4:
            return "medium"
        else:
            return "low"


class DecompilationResult(TimestampedModel):
    """
    Complete result of binary decompilation and LLM translation operation.
    
    Contains all decompilation results including file metadata, function translations,
    import explanations, string interpretations, and overall program analysis.
    Replaces the complex AnalysisResult model with a focus on LLM translation.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "decompilation_id": "12345678-1234-5678-9012-123456789012",
                    "file_hash": "sha256:abc123def456...",
                    "file_size": 245760,
                    "file_format": "pe",
                    "platform": "windows",
                    "success": True,
                    "decompilation_duration_seconds": 12.5,
                    "translation_duration_seconds": 45.8,
                    "functions": [],
                    "imports": [],
                    "strings": [],
                    "overall_summary": {}
                }
            ]
        }
    )
    
    decompilation_id: str = Field(
        description="Unique identifier for this decompilation"
    )
    
    file_hash: str = Field(
        description="Hash of the analyzed file (algorithm:hash format)"
    )
    
    file_size: int = Field(
        ge=1,
        description="Size of analyzed file in bytes"
    )
    
    file_format: FileFormat = Field(
        description="Detected file format"
    )
    
    platform: Platform = Field(
        description="Target platform"
    )
    
    architecture: Optional[str] = Field(
        default=None,
        description="Processor architecture (x86, x64, ARM, etc.)"
    )
    
    # Status and timing
    success: bool = Field(
        default=True,
        description="Whether decompilation completed successfully"
    )
    
    decompilation_duration_seconds: float = Field(
        ge=0.0,
        description="Time taken for radare2 decompilation in seconds"
    )
    
    translation_duration_seconds: float = Field(
        ge=0.0,
        description="Time taken for LLM translation in seconds"
    )
    
    # LLM translation results
    functions: List[FunctionTranslation] = Field(
        default_factory=list,
        description="LLM translations of discovered functions"
    )
    
    imports: List[ImportTranslation] = Field(
        default_factory=list,
        description="LLM explanations of imported functions and libraries"
    )
    
    strings: List[StringTranslation] = Field(
        default_factory=list,
        description="LLM interpretations of extracted strings"
    )
    
    overall_summary: Optional[OverallSummary] = Field(
        default=None,
        description="LLM-generated overall program analysis and summary"
    )
    
    # Configuration and metadata
    llm_providers_used: List[str] = Field(
        default_factory=list,
        description="List of LLM providers used for different translations"
    )
    
    decompilation_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration used for radare2 decompilation"
    )
    
    translation_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration used for LLM translation"
    )
    
    # Error handling
    errors: List[str] = Field(
        default_factory=list,
        description="Any errors encountered during decompilation or translation"
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings generated during processing"
    )
    
    partial_results: bool = Field(
        default=False,
        description="Whether results are partial due to errors or timeouts"
    )
    
    # Raw decompilation data (kept for reference)
    raw_decompilation_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw output from radare2 decompilation (for debugging)"
    )
    
    @field_validator('file_hash')
    @classmethod
    def validate_file_hash(cls, v: str) -> str:
        """Validate file hash format."""
        if not v:
            raise ValueError("File hash cannot be empty")
        
        v = v.strip()
        
        if ':' not in v:
            raise ValueError("File hash must include algorithm prefix (e.g., 'sha256:...')")
        
        algorithm, hash_value = v.split(':', 1)
        algorithm = algorithm.lower()
        
        valid_algorithms = ['md5', 'sha1', 'sha256', 'sha512']
        if algorithm not in valid_algorithms:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        if not all(c in '0123456789abcdef' for c in hash_value.lower()):
            raise ValueError("Hash value contains invalid characters")
        
        return f"{algorithm}:{hash_value.lower()}"
    
    @computed_field
    @property
    def total_duration_seconds(self) -> float:
        """Get total time for decompilation and translation."""
        return self.decompilation_duration_seconds + self.translation_duration_seconds
    
    @computed_field
    @property
    def total_llm_tokens_used(self) -> int:
        """Calculate total tokens used across all LLM translations."""
        total_tokens = 0
        
        for func in self.functions:
            total_tokens += func.llm_provider.tokens_used
        
        for imp in self.imports:
            total_tokens += imp.llm_provider.tokens_used
        
        for string in self.strings:
            total_tokens += string.llm_provider.tokens_used
        
        if self.overall_summary:
            total_tokens += self.overall_summary.llm_provider.tokens_used
        
        return total_tokens
    
    @computed_field
    @property
    def estimated_total_cost_usd(self) -> float:
        """Estimate total cost for all LLM translations."""
        total_cost = 0.0
        
        for func in self.functions:
            if func.llm_provider.cost_estimate_usd:
                total_cost += func.llm_provider.cost_estimate_usd
        
        for imp in self.imports:
            if imp.llm_provider.cost_estimate_usd:
                total_cost += imp.llm_provider.cost_estimate_usd
        
        for string in self.strings:
            if string.llm_provider.cost_estimate_usd:
                total_cost += string.llm_provider.cost_estimate_usd
        
        if self.overall_summary and self.overall_summary.llm_provider.cost_estimate_usd:
            total_cost += self.overall_summary.llm_provider.cost_estimate_usd
        
        return total_cost
    
    @computed_field
    @property
    def decompilation_summary(self) -> Dict[str, Any]:
        """Get comprehensive decompilation summary."""
        return {
            "decompilation_id": self.decompilation_id,
            "file_info": {
                "hash": self.file_hash,
                "size": self.file_size,
                "format": self.file_format,
                "platform": self.platform,
                "architecture": self.architecture
            },
            "processing_stats": {
                "success": self.success,
                "partial_results": self.partial_results,
                "decompilation_duration_seconds": self.decompilation_duration_seconds,
                "translation_duration_seconds": self.translation_duration_seconds,
                "total_duration_seconds": self.total_duration_seconds,
                "function_count": len(self.functions),
                "import_count": len(self.imports),
                "string_count": len(self.strings),
                "has_overall_summary": self.overall_summary is not None,
                "error_count": len(self.errors),
                "warning_count": len(self.warnings)
            },
            "llm_stats": {
                "providers_used": list(set(self.llm_providers_used)),
                "total_tokens_used": self.total_llm_tokens_used,
                "estimated_cost_usd": self.estimated_total_cost_usd
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @computed_field
    @property
    def high_confidence_translations(self) -> Dict[str, List]:
        """Get translations with high confidence scores."""
        return {
            "functions": [f for f in self.functions if f.is_high_confidence],
            "imports": [i for i in self.imports if i.confidence_score >= 0.8],
            "strings": [s for s in self.strings if s.confidence_score >= 0.8]
        }
    
    @computed_field
    @property
    def security_relevant_items(self) -> Dict[str, List]:
        """Get items with security relevance."""
        return {
            "functions_with_security_analysis": [f for f in self.functions if f.has_security_implications],
            "high_risk_imports": [i for i in self.imports if i.is_high_risk],
            "sensitive_strings": [s for s in self.strings if s.is_potentially_sensitive],
            "overall_risk_assessment": self.overall_summary.risk_assessment if self.overall_summary else None,
            "likely_malicious": self.overall_summary.is_likely_malicious if self.overall_summary else False
        }
    
    def add_error(self, error: str) -> None:
        """Add an error to the decompilation results."""
        if error and error not in self.errors:
            self.errors.append(error)
            if not self.partial_results and len(self.errors) > 0:
                self.partial_results = True
            self.mark_updated()
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the decompilation results."""
        if warning and warning not in self.warnings:
            self.warnings.append(warning)
            self.mark_updated()
    
    def is_decompilation_complete(self) -> bool:
        """Check if decompilation appears to be complete."""
        has_content = (
            len(self.functions) > 0 or 
            len(self.imports) > 0 or 
            len(self.strings) > 0
        )
        
        return (
            self.success and 
            len(self.errors) == 0 and
            self.decompilation_duration_seconds > 0 and
            has_content
        )
    
    def get_provider_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get usage statistics for each LLM provider."""
        provider_stats = {}
        
        all_translations = []
        all_translations.extend([(f.llm_provider, 'function') for f in self.functions])
        all_translations.extend([(i.llm_provider, 'import') for i in self.imports])
        all_translations.extend([(s.llm_provider, 'string') for s in self.strings])
        
        if self.overall_summary:
            all_translations.append((self.overall_summary.llm_provider, 'summary'))
        
        for provider_meta, translation_type in all_translations:
            provider = provider_meta.provider
            
            if provider not in provider_stats:
                provider_stats[provider] = {
                    'translation_count': 0,
                    'total_tokens': 0,
                    'total_processing_time_ms': 0,
                    'total_cost_usd': 0.0,
                    'translation_types': []
                }
            
            stats = provider_stats[provider]
            stats['translation_count'] += 1
            stats['total_tokens'] += provider_meta.tokens_used
            stats['total_processing_time_ms'] += provider_meta.processing_time_ms
            
            if provider_meta.cost_estimate_usd:
                stats['total_cost_usd'] += provider_meta.cost_estimate_usd
            
            if translation_type not in stats['translation_types']:
                stats['translation_types'].append(translation_type)
        
        return provider_stats