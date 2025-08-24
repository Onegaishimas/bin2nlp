"""
Custom serialization utilities for analysis models.

Provides specialized serializers, validators, and export functions
for analysis data models.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import field_serializer, field_validator


class AnalysisModelMixin:
    """
    Mixin providing common serialization methods for analysis models.
    
    Can be inherited by analysis models to provide consistent
    serialization and export capabilities.
    """
    
    def to_compact_dict(self) -> Dict[str, Any]:
        """
        Create a compact dictionary representation.
        
        Excludes None values and optional metadata for smaller payloads.
        """
        data = self.model_dump(exclude_none=True, exclude_unset=True)
        
        # Remove large or optional fields for compact representation
        compact_excludes = [
            'analysis_metadata', 'upload_metadata', 'processing_notes',
            'validation_metadata', 'custom_patterns'
        ]
        
        for field in compact_excludes:
            data.pop(field, None)
        
        return data
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """
        Create a summary dictionary with only key information.
        
        Useful for lists and overview displays.
        """
        # Default implementation - should be overridden by specific models
        return self.to_compact_dict()
    
    def to_detailed_dict(self) -> Dict[str, Any]:
        """
        Create a detailed dictionary representation.
        
        Includes all fields and computed properties.
        """
        data = self.model_dump()
        
        # Add computed fields if available
        computed_fields = getattr(self, '_computed_fields', {})
        for field_name in computed_fields:
            try:
                data[field_name] = getattr(self, field_name)
            except Exception:
                # Skip computed fields that fail
                continue
        
        return data
    
    def to_export_format(self, format_type: str = "json") -> Union[str, Dict[str, Any]]:
        """
        Export model in specified format.
        
        Args:
            format_type: Export format ("json", "dict", "compact", "summary")
            
        Returns:
            Formatted data
        """
        if format_type == "json":
            return self.model_dump_json(exclude_none=True, indent=2)
        elif format_type == "dict":
            return self.to_detailed_dict()
        elif format_type == "compact":
            return self.to_compact_dict()
        elif format_type == "summary":
            return self.to_summary_dict()
        else:
            raise ValueError(f"Unsupported export format: {format_type}")


def validate_hex_address(value: str) -> str:
    """
    Validate and normalize hexadecimal memory addresses.
    
    Args:
        value: Address string to validate
        
    Returns:
        Normalized address string
        
    Raises:
        ValueError: If address format is invalid
    """
    if not value:
        raise ValueError("Address cannot be empty")
    
    value = value.strip()
    
    # Ensure hex prefix
    if not value.startswith('0x'):
        if value.startswith('0X'):
            value = '0x' + value[2:]
        else:
            # Check if it looks like hex without prefix
            if all(c in '0123456789abcdefABCDEF' for c in value):
                value = '0x' + value
            else:
                raise ValueError(f"Invalid address format: {value}")
    
    # Validate hex characters
    try:
        int(value, 16)
    except ValueError:
        raise ValueError(f"Invalid hexadecimal address: {value}")
    
    return value.lower()


def validate_hash_string(value: str, algorithm: str) -> str:
    """
    Validate hash string for specific algorithm.
    
    Args:
        value: Hash string to validate
        algorithm: Hash algorithm (md5, sha1, sha256, sha512)
        
    Returns:
        Normalized hash string
        
    Raises:
        ValueError: If hash format is invalid
    """
    if not value:
        raise ValueError(f"{algorithm.upper()} hash cannot be empty")
    
    value = value.strip().lower()
    
    # Check expected length
    expected_lengths = {
        'md5': 32,
        'sha1': 40,
        'sha256': 64,
        'sha512': 128
    }
    
    expected_length = expected_lengths.get(algorithm.lower())
    if expected_length and len(value) != expected_length:
        raise ValueError(f"{algorithm.upper()} hash must be {expected_length} characters long")
    
    # Validate hex characters
    if not all(c in '0123456789abcdef' for c in value):
        raise ValueError(f"Invalid {algorithm.upper()} hash format: contains non-hex characters")
    
    return value


def validate_string_list(value: List[str], max_items: Optional[int] = None) -> List[str]:
    """
    Validate and clean list of strings.
    
    Args:
        value: List of strings to validate
        max_items: Maximum number of items allowed
        
    Returns:
        Cleaned list of strings
        
    Raises:
        ValueError: If validation fails
    """
    if not isinstance(value, list):
        raise ValueError("Value must be a list")
    
    cleaned = []
    for item in value:
        if isinstance(item, str) and item.strip():
            cleaned_item = item.strip()
            if cleaned_item not in cleaned:  # Remove duplicates
                cleaned.append(cleaned_item)
    
    if max_items and len(cleaned) > max_items:
        raise ValueError(f"Too many items: {len(cleaned)} > {max_items}")
    
    return cleaned


def validate_severity_level(value: str) -> str:
    """
    Validate security finding severity level.
    
    Args:
        value: Severity level string
        
    Returns:
        Normalized severity level
        
    Raises:
        ValueError: If severity level is invalid
    """
    valid_severities = ['low', 'medium', 'high', 'critical']
    value = value.strip().lower()
    
    if value not in valid_severities:
        raise ValueError(f"Invalid severity level: {value}. Must be one of {valid_severities}")
    
    return value


def validate_confidence_score(value: float) -> float:
    """
    Validate confidence score.
    
    Args:
        value: Confidence score to validate
        
    Returns:
        Validated confidence score
        
    Raises:
        ValueError: If score is out of range
    """
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {value}")
    
    return round(value, 3)  # Round to 3 decimal places


def serialize_datetime(value: datetime) -> str:
    """
    Serialize datetime to ISO format.
    
    Args:
        value: Datetime to serialize
        
    Returns:
        ISO format datetime string
    """
    return value.isoformat()


def serialize_uuid(value: UUID) -> str:
    """
    Serialize UUID to string.
    
    Args:
        value: UUID to serialize
        
    Returns:
        String representation of UUID
    """
    return str(value)


def serialize_enum(value) -> str:
    """
    Serialize enum to string value.
    
    Args:
        value: Enum to serialize
        
    Returns:
        String value of enum
    """
    return str(value) if hasattr(value, 'value') else str(value)


class CustomFieldValidators:
    """
    Collection of custom field validators for analysis models.
    """
    
    @staticmethod
    @field_validator('*')
    def validate_string_fields(cls, v, info):
        """Universal string field validator."""
        if isinstance(v, str):
            # Strip whitespace
            v = v.strip()
            
            # Check for empty strings in required fields
            if not v and info.field_name in getattr(cls, '_required_string_fields', []):
                raise ValueError(f"{info.field_name} cannot be empty")
        
        return v
    
    @staticmethod
    @field_validator('confidence', 'risk_score', 'significance')
    def validate_score_fields(cls, v):
        """Validate score fields (0.0-1.0 range)."""
        return validate_confidence_score(v)
    
    @staticmethod
    @field_validator('address', 'entry_point')
    def validate_address_fields(cls, v):
        """Validate memory address fields."""
        if v is None:
            return v
        return validate_hex_address(v)
    
    @staticmethod
    @field_validator('severity')
    def validate_severity_field(cls, v):
        """Validate severity level field."""
        return validate_severity_level(v)


class ExportFormats:
    """
    Predefined export format configurations.
    """
    
    # Standard JSON export with all fields
    COMPLETE = {
        "exclude_none": False,
        "exclude_unset": False,
        "indent": 2
    }
    
    # Compact JSON export excluding optional fields
    COMPACT = {
        "exclude_none": True,
        "exclude_unset": True,
        "exclude": {
            "analysis_metadata", "upload_metadata", "processing_notes",
            "validation_metadata", "custom_patterns"
        }
    }
    
    # Summary export with only key fields
    SUMMARY = {
        "include": {
            "id", "filename", "file_size", "detected_format", "platform",
            "analysis_depth", "processing_status", "success", "created_at"
        },
        "exclude_none": True
    }
    
    # API response format
    API_RESPONSE = {
        "exclude_none": True,
        "exclude_unset": True,
        "by_alias": True
    }


def create_analysis_export(
    model_instance,
    format_type: str = "complete",
    custom_excludes: Optional[List[str]] = None,
    custom_includes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create export data for analysis models.
    
    Args:
        model_instance: Model instance to export
        format_type: Export format type
        custom_excludes: Additional fields to exclude
        custom_includes: Only include these fields
        
    Returns:
        Export data dictionary
    """
    export_config = getattr(ExportFormats, format_type.upper(), ExportFormats.COMPLETE)
    
    # Apply custom modifications
    if custom_excludes:
        exclude = export_config.get("exclude", set())
        if isinstance(exclude, set):
            exclude.update(custom_excludes)
        else:
            exclude = set(custom_excludes)
        export_config["exclude"] = exclude
    
    if custom_includes:
        export_config["include"] = set(custom_includes)
    
    return model_instance.model_dump(**export_config)


def validate_analysis_data_integrity(data: Dict[str, Any]) -> List[str]:
    """
    Validate integrity of analysis data.
    
    Args:
        data: Analysis data to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check required top-level fields
    required_fields = ['analysis_id', 'file_hash', 'file_size', 'success']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Validate file hash format
    if 'file_hash' in data:
        file_hash = data['file_hash']
        if not isinstance(file_hash, str) or ':' not in file_hash:
            errors.append("Invalid file_hash format (must be 'algorithm:hash')")
    
    # Validate functions data
    if 'functions' in data and isinstance(data['functions'], list):
        for i, func in enumerate(data['functions']):
            if not isinstance(func, dict):
                errors.append(f"Function {i}: must be an object")
                continue
            
            if 'name' not in func:
                errors.append(f"Function {i}: missing 'name' field")
            
            if 'address' not in func:
                errors.append(f"Function {i}: missing 'address' field")
    
    # Validate security findings
    if 'security_findings' in data and isinstance(data['security_findings'], dict):
        findings = data['security_findings'].get('findings', [])
        if isinstance(findings, list):
            for i, finding in enumerate(findings):
                if not isinstance(finding, dict):
                    errors.append(f"Security finding {i}: must be an object")
                    continue
                
                required_finding_fields = ['finding_type', 'severity', 'title', 'confidence']
                for field in required_finding_fields:
                    if field not in finding:
                        errors.append(f"Security finding {i}: missing '{field}' field")
    
    return errors