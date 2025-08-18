"""
Analysis result models for binary analysis operations.

Provides models for storing and representing analysis results including
function information, security findings, string extraction, and metadata.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field, ConfigDict

from ..shared.base import BaseModel, TimestampedModel
from ..shared.enums import FileFormat, Platform, AnalysisDepth, AnalysisFocus
from .serialization import AnalysisModelMixin


class FunctionInfo(BaseModel):
    """
    Information about a function discovered during binary analysis.
    
    Represents a single function with its metadata, calling information,
    and analysis details.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "main",
                    "address": "0x00401000",
                    "size": 256,
                    "function_type": "user",
                    "calling_convention": "cdecl",
                    "calls_to": ["printf", "scanf"],
                    "calls_from": ["_start"],
                    "complexity": 8,
                    "confidence": 0.95
                }
            ]
        }
    )
    
    name: str = Field(
        description="Function name (may be demangled or auto-generated)"
    )
    
    address: str = Field(
        description="Memory address of function entry point (hex format)"
    )
    
    size: int = Field(
        ge=1,
        description="Size of function in bytes"
    )
    
    function_type: str = Field(
        default="unknown",
        pattern="^(user|library|system|import|export|unknown)$",
        description="Type/category of function"
    )
    
    calling_convention: Optional[str] = Field(
        default=None,
        description="Detected calling convention (cdecl, stdcall, fastcall, etc.)"
    )
    
    signature: Optional[str] = Field(
        default=None,
        description="Function signature if detected"
    )
    
    calls_to: List[str] = Field(
        default_factory=list,
        description="List of functions this function calls"
    )
    
    calls_from: List[str] = Field(
        default_factory=list,
        description="List of functions that call this function"
    )
    
    basic_blocks: int = Field(
        default=0,
        ge=0,
        description="Number of basic blocks in function"
    )
    
    complexity: int = Field(
        default=0,
        ge=0,
        description="Cyclomatic complexity score"
    )
    
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for function detection (0.0-1.0)"
    )
    
    imports_used: List[str] = Field(
        default_factory=list,
        description="External functions/APIs called by this function"
    )
    
    strings_referenced: List[str] = Field(
        default_factory=list,
        description="String literals referenced in this function"
    )
    
    analysis_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional analysis metadata"
    )
    
    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate memory address format."""
        if not v:
            raise ValueError("Address cannot be empty")
        
        v = v.strip()
        
        # Ensure hex format
        if not v.startswith('0x'):
            if v.startswith('0X'):
                v = '0x' + v[2:]
            else:
                # Assume hex and add prefix
                v = '0x' + v
        
        # Validate hex characters
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hexadecimal address: {v}")
        
        return v.lower()
    
    @field_validator('calls_to', 'calls_from', 'imports_used', 'strings_referenced')
    @classmethod
    def validate_string_lists(cls, v: List[str]) -> List[str]:
        """Validate and clean string lists."""
        if not v:
            return []
        
        cleaned = []
        for item in v:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())
        
        return list(dict.fromkeys(cleaned))  # Remove duplicates while preserving order
    
    @computed_field
    @property
    def is_high_complexity(self) -> bool:
        """Check if function has high cyclomatic complexity."""
        return self.complexity > 10
    
    @computed_field
    @property
    def call_count(self) -> int:
        """Total number of function calls (incoming + outgoing)."""
        return len(self.calls_to) + len(self.calls_from)
    
    @computed_field
    @property
    def function_summary(self) -> Dict[str, Any]:
        """Get summary information about the function."""
        return {
            "name": self.name,
            "address": self.address,
            "size": self.size,
            "type": self.function_type,
            "complexity": self.complexity,
            "call_count": self.call_count,
            "confidence": self.confidence,
            "is_high_complexity": self.is_high_complexity,
            "has_imports": len(self.imports_used) > 0,
            "has_strings": len(self.strings_referenced) > 0
        }


class SecurityFinding(BaseModel):
    """
    Individual security finding discovered during analysis.
    
    Represents a specific security concern, vulnerability, or suspicious
    behavior pattern identified in the binary.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "finding_type": "suspicious_api",
                    "severity": "medium",
                    "title": "Registry Modification Detected",
                    "description": "Function calls RegSetValueEx to modify registry",
                    "confidence": 0.85,
                    "location": "0x00401500",
                    "evidence": ["RegOpenKeyEx", "RegSetValueEx"]
                }
            ]
        }
    )
    
    finding_type: str = Field(
        description="Type/category of security finding"
    )
    
    severity: str = Field(
        pattern="^(low|medium|high|critical)$",
        description="Severity level of the finding"
    )
    
    title: str = Field(
        description="Brief title describing the finding"
    )
    
    description: str = Field(
        description="Detailed description of the security concern"
    )
    
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for this finding (0.0-1.0)"
    )
    
    location: Optional[str] = Field(
        default=None,
        description="Memory address or location where finding was detected"
    )
    
    function_name: Optional[str] = Field(
        default=None,
        description="Function name associated with the finding"
    )
    
    evidence: List[str] = Field(
        default_factory=list,
        description="Evidence supporting this finding (API calls, strings, etc.)"
    )
    
    mitigation: Optional[str] = Field(
        default=None,
        description="Suggested mitigation or remediation steps"
    )
    
    references: List[str] = Field(
        default_factory=list,
        description="External references (CVE IDs, documentation links, etc.)"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing the finding"
    )
    
    @field_validator('evidence', 'references', 'tags')
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
    def severity_score(self) -> int:
        """Get numeric severity score for sorting."""
        severity_scores = {
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4
        }
        return severity_scores.get(self.severity, 0)
    
    @computed_field
    @property
    def risk_score(self) -> float:
        """Calculate risk score based on severity and confidence."""
        return self.severity_score * self.confidence
    
    def is_high_risk(self) -> bool:
        """Check if this is a high-risk finding."""
        return self.severity in ['high', 'critical'] and self.confidence >= 0.7


class SecurityFindings(BaseModel):
    """
    Collection of security findings from binary analysis.
    
    Aggregates all security-related discoveries with summary statistics
    and risk assessment.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "findings": [
                        {
                            "finding_type": "suspicious_api",
                            "severity": "medium",
                            "title": "Network Communication",
                            "confidence": 0.9
                        }
                    ],
                    "analysis_metadata": {
                        "scan_depth": "standard",
                        "patterns_used": 15
                    }
                }
            ]
        }
    )
    
    findings: List[SecurityFinding] = Field(
        default_factory=list,
        description="List of individual security findings"
    )
    
    overall_risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=10.0,
        description="Overall risk score for the binary (0.0-10.0)"
    )
    
    analysis_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the security analysis process"
    )
    
    patterns_detected: List[str] = Field(
        default_factory=list,
        description="List of security patterns that were detected"
    )
    
    mitre_techniques: List[str] = Field(
        default_factory=list,
        description="MITRE ATT&CK techniques identified"
    )
    
    @computed_field
    @property
    def finding_count_by_severity(self) -> Dict[str, int]:
        """Count findings by severity level."""
        counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for finding in self.findings:
            counts[finding.severity] += 1
        return counts
    
    @computed_field
    @property
    def high_risk_findings(self) -> List[SecurityFinding]:
        """Get list of high-risk findings."""
        return [f for f in self.findings if f.is_high_risk()]
    
    @computed_field
    @property
    def has_critical_findings(self) -> bool:
        """Check if any critical findings exist."""
        return any(f.severity == "critical" for f in self.findings)
    
    @computed_field
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all findings."""
        if not self.findings:
            return 0.0
        return sum(f.confidence for f in self.findings) / len(self.findings)
    
    @computed_field
    @property
    def security_summary(self) -> Dict[str, Any]:
        """Get comprehensive security summary."""
        return {
            "total_findings": len(self.findings),
            "by_severity": self.finding_count_by_severity,
            "high_risk_count": len(self.high_risk_findings),
            "has_critical": self.has_critical_findings,
            "overall_risk_score": self.overall_risk_score,
            "average_confidence": round(self.average_confidence, 2),
            "techniques_detected": len(self.mitre_techniques),
            "patterns_detected": len(self.patterns_detected)
        }
    
    def add_finding(self, finding: SecurityFinding) -> None:
        """Add a security finding to the collection."""
        self.findings.append(finding)
        self._recalculate_risk_score()
    
    def get_findings_by_severity(self, severity: str) -> List[SecurityFinding]:
        """Get findings of a specific severity level."""
        return [f for f in self.findings if f.severity == severity]
    
    def get_findings_by_type(self, finding_type: str) -> List[SecurityFinding]:
        """Get findings of a specific type."""
        return [f for f in self.findings if f.finding_type == finding_type]
    
    def _recalculate_risk_score(self) -> None:
        """Recalculate overall risk score based on findings."""
        if not self.findings:
            self.overall_risk_score = 0.0
            return
        
        # Weight findings by severity and confidence
        total_risk = sum(f.risk_score for f in self.findings)
        max_possible_risk = len(self.findings) * 4.0  # max severity * max confidence
        
        # Scale to 0-10 range
        self.overall_risk_score = min(10.0, (total_risk / max_possible_risk) * 10.0)


class StringExtraction(BaseModel):
    """
    Information about strings extracted from the binary.
    
    Contains categorized strings with context and significance analysis.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "content": "admin@example.com",
                    "address": "0x00402000",
                    "string_type": "email",
                    "context": "hardcoded_credential",
                    "significance": 0.8
                }
            ]
        }
    )
    
    content: str = Field(
        description="The actual string content"
    )
    
    address: str = Field(
        description="Memory address where string was found"
    )
    
    string_type: str = Field(
        default="generic",
        description="Categorized type of string (url, email, path, etc.)"
    )
    
    context: str = Field(
        default="unknown",
        description="Context where string appears (function, data section, etc.)"
    )
    
    significance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Significance score for this string (0.0-1.0)"
    )
    
    encoding: str = Field(
        default="ascii",
        description="Character encoding of the string"
    )
    
    length: int = Field(
        ge=1,
        description="Length of the string in characters"
    )
    
    references: List[str] = Field(
        default_factory=list,
        description="Functions or locations that reference this string"
    )
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate string content."""
        if not v:
            raise ValueError("String content cannot be empty")
        return v
    
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
    def is_significant(self) -> bool:
        """Check if string is considered significant."""
        return self.significance >= 0.7


class ImportInfo(BaseModel):
    """
    Information about imported functions and libraries.
    
    Represents external dependencies and API calls used by the binary,
    including metadata about the import mechanism and usage context.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "library_name": "kernel32.dll",
                    "function_name": "CreateFileA",
                    "ordinal": None,
                    "address": "0x00401000",
                    "import_type": "name",
                    "is_delayed": False,
                    "usage_count": 3,
                    "calling_functions": ["main", "file_handler"]
                }
            ]
        }
    )
    
    library_name: str = Field(
        description="Name of the imported library (DLL, SO, dylib, etc.)"
    )
    
    function_name: Optional[str] = Field(
        default=None,
        description="Name of the imported function (if available)"
    )
    
    ordinal: Optional[int] = Field(
        default=None,
        ge=0,
        description="Import ordinal number (if imported by ordinal)"
    )
    
    address: Optional[str] = Field(
        default=None,
        description="Import address table entry address"
    )
    
    import_type: str = Field(
        default="name",
        pattern="^(name|ordinal|unknown)$",
        description="Type of import (by name or ordinal)"
    )
    
    is_delayed: bool = Field(
        default=False,
        description="Whether this is a delay-loaded import"
    )
    
    is_bound: bool = Field(
        default=False,
        description="Whether import is bound to a specific address"
    )
    
    usage_count: int = Field(
        default=0,
        ge=0,
        description="Number of times this import is referenced"
    )
    
    calling_functions: List[str] = Field(
        default_factory=list,
        description="Functions that call this imported function"
    )
    
    api_category: Optional[str] = Field(
        default=None,
        description="Category of API functionality (file, network, registry, etc.)"
    )
    
    security_relevance: str = Field(
        default="low",
        pattern="^(low|medium|high|critical)$",
        description="Security relevance of this import"
    )
    
    description: Optional[str] = Field(
        default=None,
        description="Description of the imported function's purpose"
    )
    
    risk_indicators: List[str] = Field(
        default_factory=list,
        description="Security risk indicators associated with this import"
    )
    
    @field_validator('library_name')
    @classmethod
    def validate_library_name(cls, v: str) -> str:
        """Validate library name."""
        if not v or not v.strip():
            raise ValueError("Library name cannot be empty")
        
        v = v.strip()
        if len(v) > 255:
            raise ValueError("Library name too long")
        
        return v
    
    @field_validator('function_name')
    @classmethod
    def validate_function_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate function name."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
        
        if len(v) > 255:
            raise ValueError("Function name too long")
        
        return v
    
    @field_validator('address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate address format."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
        
        # Ensure hex format
        if not v.startswith('0x'):
            v = '0x' + v
        
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hexadecimal address: {v}")
        
        return v.lower()
    
    @field_validator('calling_functions', 'risk_indicators')
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
    def display_name(self) -> str:
        """Get display name for the import."""
        if self.function_name:
            return f"{self.library_name}!{self.function_name}"
        elif self.ordinal is not None:
            return f"{self.library_name}!#{self.ordinal}"
        else:
            return self.library_name
    
    @computed_field
    @property
    def is_high_risk(self) -> bool:
        """Check if import is considered high risk."""
        return self.security_relevance in ['high', 'critical'] or len(self.risk_indicators) > 2
    
    @computed_field
    @property
    def is_system_api(self) -> bool:
        """Check if import is from a system library."""
        system_libs = [
            'kernel32.dll', 'user32.dll', 'advapi32.dll', 'shell32.dll',
            'ntdll.dll', 'ole32.dll', 'oleaut32.dll', 'ws2_32.dll',
            'libc.so', 'libdl.so', 'libpthread.so', 'libm.so',
            'libSystem.dylib', 'CoreFoundation', 'Foundation'
        ]
        
        lib_lower = self.library_name.lower()
        return any(sys_lib.lower() in lib_lower for sys_lib in system_libs)
    
    @computed_field
    @property
    def import_summary(self) -> Dict[str, Any]:
        """Get summary of import information."""
        return {
            "display_name": self.display_name,
            "library": self.library_name,
            "function": self.function_name,
            "ordinal": self.ordinal,
            "import_type": self.import_type,
            "is_delayed": self.is_delayed,
            "is_bound": self.is_bound,
            "usage_count": self.usage_count,
            "calling_functions_count": len(self.calling_functions),
            "api_category": self.api_category,
            "security_relevance": self.security_relevance,
            "is_high_risk": self.is_high_risk,
            "is_system_api": self.is_system_api,
            "risk_indicators_count": len(self.risk_indicators),
            "has_description": self.description is not None
        }
    
    def add_calling_function(self, function_name: str) -> None:
        """Add a function that calls this import."""
        function_name = function_name.strip()
        if function_name and function_name not in self.calling_functions:
            self.calling_functions.append(function_name)
            self.usage_count = len(self.calling_functions)
    
    def add_risk_indicator(self, indicator: str) -> None:
        """Add a risk indicator."""
        indicator = indicator.strip()
        if indicator and indicator not in self.risk_indicators:
            self.risk_indicators.append(indicator)
    
    def categorize_api(self) -> str:
        """Automatically categorize the API based on function name and library."""
        if not self.function_name:
            return "unknown"
        
        func_name = self.function_name.lower()
        lib_name = self.library_name.lower()
        
        # File operations
        if any(api in func_name for api in ['file', 'read', 'write', 'create', 'open', 'close', 'delete']):
            return "file"
        
        # Network operations
        if any(api in func_name for api in ['socket', 'recv', 'send', 'bind', 'connect', 'listen']) or 'ws2_32' in lib_name:
            return "network"
        
        # Registry operations
        if any(api in func_name for api in ['reg', 'key', 'value']) and 'advapi32' in lib_name:
            return "registry"
        
        # Process operations
        if any(api in func_name for api in ['process', 'thread', 'execute', 'create']):
            return "process"
        
        # Memory operations
        if any(api in func_name for api in ['alloc', 'virtual', 'heap', 'memory']):
            return "memory"
        
        # Crypto operations
        if any(api in func_name for api in ['crypt', 'hash', 'encrypt', 'decrypt']):
            return "crypto"
        
        # System information
        if any(api in func_name for api in ['system', 'computer', 'version', 'info']):
            return "system"
        
        return "other"
    
    def assess_security_relevance(self) -> str:
        """Assess security relevance of the import."""
        if not self.function_name:
            return "low"
        
        func_name = self.function_name.lower()
        
        # Critical security APIs
        critical_apis = [
            'createprocess', 'shellexecute', 'winexec',
            'virtualalloc', 'writeprocessmemory', 'readprocessmemory',
            'createremotethread', 'setwindowshook', 'keybd_event',
            'internetopen', 'internetconnect', 'httpopen'
        ]
        
        if any(api in func_name for api in critical_apis):
            return "critical"
        
        # High risk APIs
        high_risk_apis = [
            'regset', 'regdelete', 'regcreate',
            'createfile', 'writefile', 'deletefile',
            'socket', 'connect', 'send', 'recv',
            'createservice', 'startservice', 'controlservice'
        ]
        
        if any(api in func_name for api in high_risk_apis):
            return "high"
        
        # Medium risk APIs
        medium_risk_apis = [
            'getmodule', 'getproc', 'loadlibrary',
            'getstartupinfo', 'getcurrentprocess', 'getwindowsdir',
            'getsystemdir', 'gettemppath'
        ]
        
        if any(api in func_name for api in medium_risk_apis):
            return "medium"
        
        return "low"
    
    @classmethod
    def from_analysis_data(
        cls, 
        library: str, 
        function: Optional[str] = None, 
        ordinal: Optional[int] = None,
        **kwargs
    ) -> 'ImportInfo':
        """Create ImportInfo from analysis data."""
        import_info = cls(
            library_name=library,
            function_name=function,
            ordinal=ordinal,
            **kwargs
        )
        
        # Auto-categorize and assess
        import_info.api_category = import_info.categorize_api()
        import_info.security_relevance = import_info.assess_security_relevance()
        
        # Determine import type
        if function:
            import_info.import_type = "name"
        elif ordinal is not None:
            import_info.import_type = "ordinal"
        else:
            import_info.import_type = "unknown"
        
        return import_info


class AnalysisResult(TimestampedModel, AnalysisModelMixin):
    """
    Complete result of binary analysis operation.
    
    Contains all analysis results including file metadata, function information,
    security findings, strings, and analysis statistics.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "analysis_id": "12345678-1234-5678-9012-123456789012",
                    "file_hash": "sha256:abc123...",
                    "success": True,
                    "analysis_duration_seconds": 45.2,
                    "functions": [],
                    "security_findings": {"findings": []},
                    "strings": []
                }
            ]
        }
    )
    
    analysis_id: str = Field(
        description="Unique identifier for this analysis"
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
    
    analysis_config_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of analysis configuration used"
    )
    
    success: bool = Field(
        default=True,
        description="Whether analysis completed successfully"
    )
    
    analysis_duration_seconds: float = Field(
        ge=0.0,
        description="Time taken for analysis in seconds"
    )
    
    functions: List[FunctionInfo] = Field(
        default_factory=list,
        description="Discovered functions"
    )
    
    security_findings: SecurityFindings = Field(
        default_factory=SecurityFindings,
        description="Security analysis results"
    )
    
    strings: List[StringExtraction] = Field(
        default_factory=list,
        description="Extracted strings"
    )
    
    imports: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Imported functions and libraries"
    )
    
    exports: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Exported functions"
    )
    
    errors: List[str] = Field(
        default_factory=list,
        description="Any errors encountered during analysis"
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings generated during analysis"
    )
    
    analysis_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the analysis"
    )
    
    @field_validator('file_hash')
    @classmethod
    def validate_file_hash(cls, v: str) -> str:
        """Validate file hash format."""
        if not v:
            raise ValueError("File hash cannot be empty")
        
        v = v.strip()
        
        # Check for algorithm prefix
        if ':' not in v:
            raise ValueError("File hash must include algorithm prefix (e.g., 'sha256:...')")
        
        algorithm, hash_value = v.split(':', 1)
        algorithm = algorithm.lower()
        
        # Validate known algorithms
        valid_algorithms = ['md5', 'sha1', 'sha256', 'sha512']
        if algorithm not in valid_algorithms:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
        
        # Basic validation of hex characters
        if not all(c in '0123456789abcdef' for c in hash_value.lower()):
            raise ValueError("Hash value contains invalid characters")
        
        return f"{algorithm}:{hash_value.lower()}"
    
    @computed_field
    @property
    def analysis_summary(self) -> Dict[str, Any]:
        """Get comprehensive analysis summary."""
        return {
            "analysis_id": self.analysis_id,
            "file_info": {
                "hash": self.file_hash,
                "size": self.file_size,
                "format": self.file_format,
                "platform": self.platform,
                "architecture": self.architecture
            },
            "analysis_stats": {
                "success": self.success,
                "duration_seconds": self.analysis_duration_seconds,
                "function_count": len(self.functions),
                "string_count": len(self.strings),
                "import_count": len(self.imports),
                "export_count": len(self.exports),
                "error_count": len(self.errors),
                "warning_count": len(self.warnings)
            },
            "security_summary": self.security_findings.security_summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @computed_field
    @property
    def high_value_functions(self) -> List[FunctionInfo]:
        """Get functions with high complexity or many calls."""
        return [
            f for f in self.functions 
            if f.is_high_complexity or f.call_count > 10 or f.confidence < 0.8
        ]
    
    @computed_field
    @property
    def significant_strings(self) -> List[StringExtraction]:
        """Get strings marked as significant."""
        return [s for s in self.strings if s.is_significant]
    
    @computed_field
    @property
    def overall_confidence(self) -> float:
        """Calculate overall confidence in analysis results."""
        if not self.functions:
            return 1.0 if self.success else 0.0
        
        function_confidence = sum(f.confidence for f in self.functions) / len(self.functions)
        security_confidence = self.security_findings.average_confidence
        
        # Weight function analysis more heavily
        return (function_confidence * 0.7 + security_confidence * 0.3)
    
    def add_error(self, error: str) -> None:
        """Add an error to the analysis results."""
        if error and error not in self.errors:
            self.errors.append(error)
            self.mark_updated()
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the analysis results."""
        if warning and warning not in self.warnings:
            self.warnings.append(warning)
            self.mark_updated()
    
    def get_functions_by_type(self, function_type: str) -> List[FunctionInfo]:
        """Get functions of a specific type."""
        return [f for f in self.functions if f.function_type == function_type]
    
    def get_strings_by_type(self, string_type: str) -> List[StringExtraction]:
        """Get strings of a specific type."""
        return [s for s in self.strings if s.string_type == string_type]
    
    def is_analysis_complete(self) -> bool:
        """Check if analysis appears to be complete."""
        return (
            self.success and 
            len(self.errors) == 0 and
            self.analysis_duration_seconds > 0 and
            (len(self.functions) > 0 or len(self.strings) > 0)
        )