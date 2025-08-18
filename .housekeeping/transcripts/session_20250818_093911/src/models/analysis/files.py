"""
File handling models for binary analysis operations.

Provides models for file metadata, binary file representation,
validation results, and file processing workflows.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, BinaryIO
from uuid import UUID

from pydantic import Field, field_validator, computed_field, ConfigDict

from ..shared.base import BaseModel, TimestampedModel
from ..shared.enums import FileFormat, Platform, get_file_format_from_extension


class FileMetadata(BaseModel):
    """
    Metadata information about a binary file.
    
    Contains file system information, format detection,
    and basic properties without file content.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "filename": "sample.exe",
                    "file_size": 1048576,
                    "mime_type": "application/x-dosexec",
                    "detected_format": "pe",
                    "platform": "windows",
                    "architecture": "x64"
                }
            ]
        }
    )
    
    filename: str = Field(
        description="Original filename of the binary"
    )
    
    file_size: int = Field(
        ge=1,
        le=100 * 1024 * 1024,  # 100MB limit
        description="Size of the file in bytes"
    )
    
    mime_type: Optional[str] = Field(
        default=None,
        description="MIME type of the file"
    )
    
    detected_format: FileFormat = Field(
        description="Detected binary file format"
    )
    
    platform: Platform = Field(
        description="Target platform for the binary"
    )
    
    architecture: Optional[str] = Field(
        default=None,
        pattern="^(x86|x64|arm|arm64|mips|sparc|unknown)$",
        description="Processor architecture"
    )
    
    entry_point: Optional[str] = Field(
        default=None,
        description="Entry point address (hex format)"
    )
    
    compiler_info: Optional[str] = Field(
        default=None,
        description="Detected compiler or toolchain information"
    )
    
    debug_info: bool = Field(
        default=False,
        description="Whether debug information is present"
    )
    
    stripped: bool = Field(
        default=False,
        description="Whether symbols have been stripped"
    )
    
    packed: bool = Field(
        default=False,
        description="Whether the binary appears to be packed"
    )
    
    digital_signature: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Digital signature information if present"
    )
    
    version_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Version information from file resources"
    )
    
    creation_time: Optional[datetime] = Field(
        default=None,
        description="File creation timestamp if available"
    )
    
    modification_time: Optional[datetime] = Field(
        default=None,
        description="File modification timestamp"
    )
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename."""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        
        v = v.strip()
        
        # Check length
        if len(v) > 255:
            raise ValueError("Filename too long (max 255 characters)")
        
        # Check for problematic characters
        problematic_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        if any(char in v for char in problematic_chars):
            raise ValueError(f"Filename contains invalid characters: {problematic_chars}")
        
        return v
    
    @field_validator('entry_point')
    @classmethod
    def validate_entry_point(cls, v: Optional[str]) -> Optional[str]:
        """Validate entry point address format."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
        
        # Ensure hex format
        if not v.startswith('0x'):
            if v.startswith('0X'):
                v = '0x' + v[2:]
            else:
                v = '0x' + v
        
        # Validate hex characters
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"Invalid hexadecimal entry point: {v}")
        
        return v.lower()
    
    @computed_field
    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return round(self.file_size / (1024 * 1024), 2)
    
    @computed_field
    @property
    def is_large_file(self) -> bool:
        """Check if file is considered large (>10MB)."""
        return self.file_size > 10 * 1024 * 1024
    
    @computed_field
    @property
    def is_executable(self) -> bool:
        """Check if file is an executable format."""
        executable_formats = [FileFormat.PE, FileFormat.ELF, FileFormat.MACHO]
        return self.detected_format in executable_formats
    
    @computed_field
    @property
    def analysis_hints(self) -> Dict[str, Any]:
        """Get hints for analysis configuration."""
        return {
            "format": self.detected_format,
            "platform": self.platform,
            "architecture": self.architecture,
            "is_large": self.is_large_file,
            "is_packed": self.packed,
            "has_debug_info": self.debug_info,
            "is_stripped": self.stripped,
            "has_signature": self.digital_signature is not None
        }
    
    @classmethod
    def from_filename(cls, filename: str) -> 'FileMetadata':
        """Create basic metadata from filename only."""
        detected_format = get_file_format_from_extension(filename)
        platform = Platform.from_file_format(detected_format)
        
        return cls(
            filename=filename,
            file_size=0,  # Will be updated when file is processed
            detected_format=detected_format,
            platform=platform
        )


class HashInfo(BaseModel):
    """
    Hash information for a binary file.
    
    Contains multiple hash algorithms for file integrity
    and duplicate detection.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "sha1": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                }
            ]
        }
    )
    
    md5: Optional[str] = Field(
        default=None,
        pattern="^[a-fA-F0-9]{32}$",
        description="MD5 hash of the file"
    )
    
    sha1: Optional[str] = Field(
        default=None,
        pattern="^[a-fA-F0-9]{40}$",
        description="SHA-1 hash of the file"
    )
    
    sha256: Optional[str] = Field(
        default=None,
        pattern="^[a-fA-F0-9]{64}$",
        description="SHA-256 hash of the file"
    )
    
    sha512: Optional[str] = Field(
        default=None,
        pattern="^[a-fA-F0-9]{128}$",
        description="SHA-512 hash of the file"
    )
    
    @field_validator('md5', 'sha1', 'sha256', 'sha512')
    @classmethod
    def validate_hash(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize hash values."""
        if v is None:
            return v
        
        v = v.strip().lower()
        if not v:
            return None
        
        return v
    
    @computed_field
    @property
    def primary_hash(self) -> Optional[str]:
        """Get the strongest available hash."""
        if self.sha256:
            return f"sha256:{self.sha256}"
        elif self.sha1:
            return f"sha1:{self.sha1}"
        elif self.md5:
            return f"md5:{self.md5}"
        else:
            return None
    
    @computed_field
    @property
    def available_hashes(self) -> List[str]:
        """Get list of available hash algorithms."""
        available = []
        if self.md5:
            available.append("md5")
        if self.sha1:
            available.append("sha1")
        if self.sha256:
            available.append("sha256")
        if self.sha512:
            available.append("sha512")
        return available
    
    def get_hash(self, algorithm: str) -> Optional[str]:
        """Get hash by algorithm name."""
        algorithm = algorithm.lower()
        hash_map = {
            "md5": self.md5,
            "sha1": self.sha1,
            "sha256": self.sha256,
            "sha512": self.sha512
        }
        return hash_map.get(algorithm)
    
    @classmethod
    def calculate_from_bytes(cls, file_data: bytes) -> 'HashInfo':
        """Calculate all hashes from file bytes."""
        return cls(
            md5=hashlib.md5(file_data).hexdigest(),
            sha1=hashlib.sha1(file_data).hexdigest(),
            sha256=hashlib.sha256(file_data).hexdigest(),
            sha512=hashlib.sha512(file_data).hexdigest()
        )


class ValidationResult(BaseModel):
    """
    Result of file validation process.
    
    Contains validation status, detected issues,
    and recommendations for processing.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "is_valid": True,
                    "validation_status": "passed",
                    "issues": [],
                    "warnings": ["Large file size"],
                    "confidence": 0.95
                }
            ]
        }
    )
    
    is_valid: bool = Field(
        description="Whether the file passed validation"
    )
    
    validation_status: str = Field(
        pattern="^(passed|failed|warning|skipped)$",
        description="Overall validation status"
    )
    
    issues: List[str] = Field(
        default_factory=list,
        description="Critical issues that prevent processing"
    )
    
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-critical warnings about the file"
    )
    
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in validation result (0.0-1.0)"
    )
    
    format_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in format detection (0.0-1.0)"
    )
    
    recommended_action: str = Field(
        default="proceed",
        pattern="^(proceed|proceed_with_caution|reject|manual_review)$",
        description="Recommended action based on validation"
    )
    
    validation_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional validation metadata"
    )
    
    @computed_field
    @property
    def has_critical_issues(self) -> bool:
        """Check if there are critical issues."""
        return len(self.issues) > 0
    
    @computed_field
    @property
    def has_warnings(self) -> bool:
        """Check if there are warnings."""
        return len(self.warnings) > 0
    
    @computed_field
    @property
    def overall_score(self) -> float:
        """Calculate overall validation score."""
        base_score = self.confidence
        
        # Reduce score for issues and warnings
        if self.has_critical_issues:
            base_score *= 0.5
        if self.has_warnings:
            base_score *= 0.8
        
        return round(base_score, 2)
    
    def add_issue(self, issue: str) -> None:
        """Add a critical issue."""
        if issue and issue not in self.issues:
            self.issues.append(issue)
            self.is_valid = False
            self.validation_status = "failed"
            self.recommended_action = "reject"
    
    def add_warning(self, warning: str) -> None:
        """Add a warning."""
        if warning and warning not in self.warnings:
            self.warnings.append(warning)
            if self.validation_status == "passed":
                self.validation_status = "warning"
                if self.recommended_action == "proceed":
                    self.recommended_action = "proceed_with_caution"


class BinaryFile(TimestampedModel):
    """
    Complete representation of a binary file for analysis.
    
    Contains file metadata, validation results, hash information,
    and processing status.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_reference": "upload://abc123def456",
                    "metadata": {
                        "filename": "sample.exe",
                        "file_size": 1048576,
                        "detected_format": "pe"
                    },
                    "processing_status": "validated"
                }
            ]
        }
    )
    
    file_reference: str = Field(
        description="Reference to the file (path, URL, or identifier)"
    )
    
    metadata: FileMetadata = Field(
        description="File metadata and properties"
    )
    
    hashes: Optional[HashInfo] = Field(
        default=None,
        description="File hash information"
    )
    
    validation_result: Optional[ValidationResult] = Field(
        default=None,
        description="File validation results"
    )
    
    processing_status: str = Field(
        default="pending",
        pattern="^(pending|uploaded|validated|processing|completed|failed|expired)$",
        description="Current processing status"
    )
    
    storage_location: Optional[str] = Field(
        default=None,
        description="Temporary storage location for processing"
    )
    
    expiration_time: Optional[datetime] = Field(
        default=None,
        description="When temporary storage expires"
    )
    
    analysis_id: Optional[str] = Field(
        default=None,
        description="Associated analysis job ID"
    )
    
    upload_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata from upload process"
    )
    
    processing_notes: List[str] = Field(
        default_factory=list,
        description="Notes from processing steps"
    )
    
    @field_validator('file_reference')
    @classmethod
    def validate_file_reference(cls, v: str) -> str:
        """Validate file reference format."""
        if not v or not v.strip():
            raise ValueError("File reference cannot be empty")
        
        v = v.strip()
        
        # Check for valid reference patterns
        valid_prefixes = ['file://', 'upload://', 'http://', 'https://', '/']
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            # Assume it's a local file path if no prefix
            if not v.startswith('/'):
                raise ValueError(
                    "File reference must be a valid path, URL, or identifier"
                )
        
        return v
    
    @computed_field
    @property
    def is_ready_for_analysis(self) -> bool:
        """Check if file is ready for analysis."""
        return (
            self.processing_status in ["validated", "processing"] and
            self.validation_result is not None and
            self.validation_result.is_valid and
            self.hashes is not None
        )
    
    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if file storage has expired."""
        if self.expiration_time is None:
            return False
        return datetime.now() > self.expiration_time
    
    @computed_field
    @property
    def file_summary(self) -> Dict[str, Any]:
        """Get summary of file information."""
        return {
            "id": str(self.id),
            "filename": self.metadata.filename,
            "size": self.metadata.file_size,
            "size_mb": self.metadata.file_size_mb,
            "format": self.metadata.detected_format,
            "platform": self.metadata.platform,
            "architecture": self.metadata.architecture,
            "processing_status": self.processing_status,
            "is_validated": self.validation_result is not None,
            "is_valid": self.validation_result.is_valid if self.validation_result else False,
            "has_hashes": self.hashes is not None,
            "primary_hash": self.hashes.primary_hash if self.hashes else None,
            "is_ready": self.is_ready_for_analysis,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat(),
            "analysis_id": self.analysis_id
        }
    
    @computed_field
    @property
    def processing_history(self) -> List[Dict[str, Any]]:
        """Get processing history with timestamps."""
        history = []
        
        # Add creation event
        history.append({
            "event": "created",
            "timestamp": self.created_at.isoformat(),
            "status": "pending"
        })
        
        # Add update event if applicable
        if self.updated_at:
            history.append({
                "event": "updated",
                "timestamp": self.updated_at.isoformat(),
                "status": self.processing_status
            })
        
        return history
    
    def update_status(self, new_status: str, note: Optional[str] = None) -> None:
        """Update processing status with optional note."""
        old_status = self.processing_status
        self.processing_status = new_status
        
        if note:
            self.add_processing_note(f"Status changed from {old_status} to {new_status}: {note}")
        else:
            self.add_processing_note(f"Status changed from {old_status} to {new_status}")
        
        self.mark_updated()
    
    def add_processing_note(self, note: str) -> None:
        """Add a processing note with timestamp."""
        if note:
            timestamped_note = f"[{datetime.now().isoformat()}] {note}"
            self.processing_notes.append(timestamped_note)
    
    def set_hashes(self, file_data: bytes) -> None:
        """Calculate and set file hashes."""
        self.hashes = HashInfo.calculate_from_bytes(file_data)
        self.add_processing_note("File hashes calculated")
        self.mark_updated()
    
    def validate_file(self, file_data: Optional[bytes] = None) -> ValidationResult:
        """Validate the file and store results."""
        validation = ValidationResult(
            is_valid=True,
            validation_status="passed",
            confidence=0.9
        )
        
        # Basic validations
        if self.metadata.file_size == 0:
            validation.add_issue("File is empty")
        
        if self.metadata.file_size > 100 * 1024 * 1024:  # 100MB
            validation.add_issue("File exceeds maximum size limit")
        
        if self.metadata.detected_format == FileFormat.UNKNOWN:
            validation.add_warning("Unknown file format detected")
            validation.format_confidence = 0.3
        
        if self.metadata.is_large_file:
            validation.add_warning("Large file may require extended processing time")
        
        if self.metadata.packed:
            validation.add_warning("Packed binary may have limited analysis results")
        
        # Store validation result
        self.validation_result = validation
        self.add_processing_note(f"Validation completed: {validation.validation_status}")
        
        # Update processing status based on validation
        if validation.is_valid:
            self.update_status("validated")
        else:
            self.update_status("failed", "Validation failed")
        
        return validation
    
    @classmethod
    def from_upload(
        cls, 
        file_reference: str, 
        filename: str, 
        file_size: int,
        **metadata_kwargs
    ) -> 'BinaryFile':
        """Create BinaryFile from upload information."""
        # Create metadata
        detected_format = get_file_format_from_extension(filename)
        platform = Platform.from_file_format(detected_format)
        
        metadata = FileMetadata(
            filename=filename,
            file_size=file_size,
            detected_format=detected_format,
            platform=platform,
            **metadata_kwargs
        )
        
        # Create binary file
        binary_file = cls(
            file_reference=file_reference,
            metadata=metadata,
            processing_status="uploaded"
        )
        
        binary_file.add_processing_note("File uploaded and metadata created")
        return binary_file


class FileAnalysisInfo(BaseModel):
    """
    Comprehensive file analysis information combining metadata and analysis results.
    
    Provides a unified view of file properties, analysis status, and key findings
    for quick assessment and decision making.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "file_reference": "upload://abc123def456",
                    "metadata": {
                        "filename": "sample.exe",
                        "file_size": 1048576,
                        "detected_format": "pe",
                        "platform": "windows"
                    },
                    "analysis_status": "completed",
                    "risk_assessment": "medium",
                    "confidence_score": 0.85,
                    "key_findings": ["network_activity", "registry_access"]
                }
            ]
        }
    )
    
    file_reference: str = Field(
        description="Reference to the file"
    )
    
    metadata: FileMetadata = Field(
        description="File metadata and properties"
    )
    
    analysis_status: str = Field(
        default="pending",
        pattern="^(pending|processing|completed|failed|skipped)$",
        description="Current analysis status"
    )
    
    analysis_id: Optional[str] = Field(
        default=None,
        description="Associated analysis job ID"
    )
    
    risk_assessment: str = Field(
        default="unknown",
        pattern="^(low|medium|high|critical|unknown)$",
        description="Overall risk assessment"
    )
    
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence in analysis results (0.0-1.0)"
    )
    
    key_findings: List[str] = Field(
        default_factory=list,
        description="Key security and behavioral findings"
    )
    
    function_count: int = Field(
        default=0,
        ge=0,
        description="Number of functions discovered"
    )
    
    import_count: int = Field(
        default=0,
        ge=0,
        description="Number of imported functions"
    )
    
    string_count: int = Field(
        default=0,
        ge=0,
        description="Number of extracted strings"
    )
    
    security_flags: List[str] = Field(
        default_factory=list,
        description="Security-related flags and indicators"
    )
    
    malware_indicators: List[str] = Field(
        default_factory=list,
        description="Potential malware indicators"
    )
    
    analysis_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of analysis results"
    )
    
    processing_time_seconds: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Time taken for analysis"
    )
    
    last_analyzed: Optional[datetime] = Field(
        default=None,
        description="When analysis was last performed"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Classification and organizational tags"
    )
    
    @field_validator('key_findings', 'security_flags', 'malware_indicators', 'tags')
    @classmethod
    def validate_string_lists(cls, v: List[str]) -> List[str]:
        """Validate and clean string lists."""
        if not v:
            return []
        
        cleaned = []
        for item in v:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip().lower())
        
        return list(dict.fromkeys(cleaned))  # Remove duplicates
    
    @computed_field
    @property
    def is_analyzed(self) -> bool:
        """Check if file has been analyzed."""
        return self.analysis_status == "completed"
    
    @computed_field
    @property
    def is_high_risk(self) -> bool:
        """Check if file is assessed as high risk."""
        return self.risk_assessment in ['high', 'critical'] and self.confidence_score >= 0.7
    
    @computed_field
    @property
    def has_security_concerns(self) -> bool:
        """Check if file has security-related findings."""
        return len(self.security_flags) > 0 or len(self.malware_indicators) > 0
    
    @computed_field
    @property
    def analysis_completeness(self) -> float:
        """Calculate analysis completeness score."""
        completeness = 0.0
        
        if self.function_count > 0:
            completeness += 0.3
        if self.import_count > 0:
            completeness += 0.2
        if self.string_count > 0:
            completeness += 0.2
        if len(self.key_findings) > 0:
            completeness += 0.3
        
        return min(1.0, completeness)
    
    @computed_field
    @property
    def file_info_summary(self) -> Dict[str, Any]:
        """Get comprehensive file information summary."""
        return {
            "filename": self.metadata.filename,
            "size_mb": self.metadata.file_size_mb,
            "format": self.metadata.detected_format,
            "platform": self.metadata.platform,
            "architecture": self.metadata.architecture,
            "analysis_status": self.analysis_status,
            "risk_assessment": self.risk_assessment,
            "confidence": self.confidence_score,
            "is_analyzed": self.is_analyzed,
            "is_high_risk": self.is_high_risk,
            "has_security_concerns": self.has_security_concerns,
            "completeness": self.analysis_completeness,
            "function_count": self.function_count,
            "import_count": self.import_count,
            "string_count": self.string_count,
            "key_findings_count": len(self.key_findings),
            "security_flags_count": len(self.security_flags),
            "malware_indicators_count": len(self.malware_indicators),
            "processing_time": self.processing_time_seconds,
            "last_analyzed": self.last_analyzed.isoformat() if self.last_analyzed else None
        }
    
    def update_from_analysis_result(self, result: Dict[str, Any]) -> None:
        """Update file info from analysis results."""
        # Update counts
        if 'functions' in result:
            self.function_count = len(result['functions'])
        if 'imports' in result:
            self.import_count = len(result['imports'])
        if 'strings' in result:
            self.string_count = len(result['strings'])
        
        # Update security assessment
        if 'security_findings' in result:
            security_findings = result['security_findings']
            if 'overall_risk_score' in security_findings:
                risk_score = security_findings['overall_risk_score']
                if risk_score >= 7.0:
                    self.risk_assessment = "high"
                elif risk_score >= 5.0:
                    self.risk_assessment = "medium"
                else:
                    self.risk_assessment = "low"
        
        # Update timing info
        if 'analysis_duration_seconds' in result:
            self.processing_time_seconds = result['analysis_duration_seconds']
        
        self.last_analyzed = datetime.now()
        self.analysis_status = "completed"
    
    def add_security_flag(self, flag: str) -> None:
        """Add a security flag."""
        flag = flag.strip().lower()
        if flag and flag not in self.security_flags:
            self.security_flags.append(flag)
    
    def add_malware_indicator(self, indicator: str) -> None:
        """Add a malware indicator."""
        indicator = indicator.strip().lower()
        if indicator and indicator not in self.malware_indicators:
            self.malware_indicators.append(indicator)
    
    def add_key_finding(self, finding: str) -> None:
        """Add a key finding."""
        finding = finding.strip().lower()
        if finding and finding not in self.key_findings:
            self.key_findings.append(finding)
    
    def add_tag(self, tag: str) -> None:
        """Add a classification tag."""
        tag = tag.strip().lower()
        if tag and tag not in self.tags:
            self.tags.append(tag)
    
    def get_risk_factors(self) -> Dict[str, Any]:
        """Get detailed risk factor analysis."""
        risk_factors = {
            "file_properties": {},
            "security_indicators": {},
            "behavioral_patterns": {},
            "overall_assessment": {}
        }
        
        # File property risks
        if self.metadata.is_large_file:
            risk_factors["file_properties"]["large_file"] = True
        if self.metadata.packed:
            risk_factors["file_properties"]["packed_binary"] = True
        if not self.metadata.digital_signature:
            risk_factors["file_properties"]["unsigned_binary"] = True
        if self.metadata.stripped:
            risk_factors["file_properties"]["stripped_symbols"] = True
        
        # Security indicators
        risk_factors["security_indicators"]["security_flags"] = self.security_flags
        risk_factors["security_indicators"]["malware_indicators"] = self.malware_indicators
        risk_factors["security_indicators"]["key_findings"] = self.key_findings
        
        # Behavioral patterns
        if "network_activity" in self.key_findings:
            risk_factors["behavioral_patterns"]["network_communication"] = True
        if "registry_access" in self.key_findings:
            risk_factors["behavioral_patterns"]["system_modification"] = True
        if "file_operations" in self.key_findings:
            risk_factors["behavioral_patterns"]["file_system_access"] = True
        
        # Overall assessment
        risk_factors["overall_assessment"] = {
            "risk_level": self.risk_assessment,
            "confidence": self.confidence_score,
            "is_high_risk": self.is_high_risk,
            "has_security_concerns": self.has_security_concerns,
            "analysis_completeness": self.analysis_completeness
        }
        
        return risk_factors
    
    @classmethod
    def from_binary_file(cls, binary_file: BinaryFile) -> 'FileAnalysisInfo':
        """Create FileAnalysisInfo from BinaryFile instance."""
        return cls(
            file_reference=binary_file.file_reference,
            metadata=binary_file.metadata,
            analysis_id=binary_file.analysis_id,
            analysis_status="pending" if binary_file.is_ready_for_analysis else "failed"
        )