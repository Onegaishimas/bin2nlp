"""
Basic binary analysis models for metadata and simple decompilation results.

This module contains simplified models focused on basic binary metadata,
file information, and radare2 decompilation data without complex analysis
or security-focused processing.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import Field, field_validator, computed_field, ConfigDict

from ..shared.base import BaseModel, TimestampedModel
from ..shared.enums import FileFormat, Platform


class BasicFunctionInfo(BaseModel):
    """
    Basic information about a function discovered during decompilation.
    
    Simplified version focusing on core metadata needed for LLM translation
    without complex analysis features.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "main",
                    "address": "0x00401000",
                    "size": 256,
                    "assembly_code": "push ebp\nmov ebp, esp\n...",
                    "calls_to": ["printf", "scanf"],
                    "calls_from": ["_start"]
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
    
    assembly_code: Optional[str] = Field(
        default=None,
        description="Raw assembly code for the function"
    )
    
    function_type: str = Field(
        default="user",
        pattern="^(user|library|import|export|unknown)$",
        description="Basic function category"
    )
    
    calls_to: List[str] = Field(
        default_factory=list,
        description="List of functions this function calls"
    )
    
    calls_from: List[str] = Field(
        default_factory=list,
        description="List of functions that call this function"
    )
    
    imports_used: List[str] = Field(
        default_factory=list,
        description="External functions/APIs called by this function"
    )
    
    strings_referenced: List[str] = Field(
        default_factory=list,
        description="String addresses referenced in this function"
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
    def hex_address(self) -> str:
        """Get address in hexadecimal format."""
        return self.address


class BasicStringInfo(BaseModel):
    """
    Basic information about extracted strings.
    
    Simplified version focusing on essential string data needed
    for LLM translation without complex categorization.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "value": "Hello World",
                    "address": "0x00403000",
                    "size": 12,
                    "encoding": "ascii",
                    "section": ".rdata"
                }
            ]
        }
    )
    
    value: str = Field(
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
        description="Character encoding (ascii, unicode, utf-16)"
    )
    
    section: Optional[str] = Field(
        default=None,
        description="Binary section containing the string"
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
    def hex_address(self) -> str:
        """Get address in hexadecimal format."""
        return self.address


class BasicImportInfo(BaseModel):
    """
    Basic information about imported functions and libraries.
    
    Simplified version focusing on import metadata needed for LLM analysis
    without complex security assessment.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "library_name": "kernel32.dll",
                    "function_name": "CreateFileA",
                    "address": "0x00401000",
                    "ordinal": None
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
    
    @field_validator('address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate address format."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
        
        if not v.startswith('0x'):
            v = '0x' + v
        
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hexadecimal address: {v}")
        
        return v.lower()
    
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


class DecompilationMetadata(BaseModel):
    """
    Basic metadata about the decompilation process.
    
    Contains essential information about the decompilation without
    complex analysis metrics or security assessments.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_hash": "sha256:abc123def456...",
                    "file_size": 245760,
                    "file_format": "pe",
                    "platform": "windows",
                    "architecture": "x86",
                    "decompilation_tool": "radare2",
                    "tool_version": "5.8.0"
                }
            ]
        }
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
    
    entry_point: Optional[str] = Field(
        default=None,
        description="Entry point address (hex format)"
    )
    
    base_address: Optional[str] = Field(
        default=None,
        description="Base load address (hex format)"
    )
    
    decompilation_tool: str = Field(
        default="radare2",
        description="Tool used for decompilation"
    )
    
    tool_version: Optional[str] = Field(
        default=None,
        description="Version of decompilation tool"
    )
    
    sections: List[str] = Field(
        default_factory=list,
        description="Binary sections found in the file"
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


class BasicDecompilationResult(TimestampedModel):
    """
    Basic decompilation result containing essential binary information.
    
    Simplified version of decompilation results focused on core metadata
    needed for LLM translation without complex analysis features.
    This serves as input to the LLM translation process.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "decompilation_id": "12345678-1234-5678-9012-123456789012",
                    "metadata": {},
                    "functions": [],
                    "imports": [],
                    "strings": [],
                    "success": True,
                    "duration_seconds": 12.5
                }
            ]
        }
    )
    
    decompilation_id: str = Field(
        description="Unique identifier for this decompilation"
    )
    
    metadata: DecompilationMetadata = Field(
        description="Basic file and decompilation metadata"
    )
    
    functions: List[BasicFunctionInfo] = Field(
        default_factory=list,
        description="Basic function information from decompilation"
    )
    
    imports: List[BasicImportInfo] = Field(
        default_factory=list,
        description="Basic import information"
    )
    
    strings: List[BasicStringInfo] = Field(
        default_factory=list,
        description="Basic string information"
    )
    
    exports: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Basic export information"
    )
    
    success: bool = Field(
        default=True,
        description="Whether decompilation completed successfully"
    )
    
    duration_seconds: float = Field(
        ge=0.0,
        description="Time taken for decompilation in seconds"
    )
    
    errors: List[str] = Field(
        default_factory=list,
        description="Any errors encountered during decompilation"
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings generated during decompilation"
    )
    
    raw_output: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw decompilation tool output (for debugging)"
    )
    
    @computed_field
    @property
    def basic_summary(self) -> Dict[str, Any]:
        """Get basic summary of decompilation results."""
        return {
            "decompilation_id": self.decompilation_id,
            "file_info": {
                "hash": self.metadata.file_hash,
                "size": self.metadata.file_size,
                "format": self.metadata.file_format,
                "platform": self.metadata.platform,
                "architecture": self.metadata.architecture
            },
            "counts": {
                "functions": len(self.functions),
                "imports": len(self.imports),
                "strings": len(self.strings),
                "exports": len(self.exports)
            },
            "status": {
                "success": self.success,
                "duration_seconds": self.duration_seconds,
                "error_count": len(self.errors),
                "warning_count": len(self.warnings)
            },
            "created_at": self.created_at.isoformat()
        }
    
    def add_error(self, error: str) -> None:
        """Add an error to the decompilation results."""
        if error and error not in self.errors:
            self.errors.append(error)
            self.mark_updated()
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the decompilation results."""
        if warning and warning not in self.warnings:
            self.warnings.append(warning)
            self.mark_updated()
    
    def is_ready_for_translation(self) -> bool:
        """Check if decompilation results are ready for LLM translation."""
        return (
            self.success and
            len(self.errors) == 0 and
            (len(self.functions) > 0 or len(self.imports) > 0 or len(self.strings) > 0)
        )