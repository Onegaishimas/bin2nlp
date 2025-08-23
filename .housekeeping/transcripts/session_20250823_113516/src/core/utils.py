"""
Core utility functions for the bin2nlp analysis system.

Provides file validation, hash generation, data sanitization, and other
common utility functions used across the application.
"""

import hashlib
import mimetypes
import os
import re
import secrets
import string
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, BinaryIO
from urllib.parse import urlparse
from magika import Magika

from .exceptions import ValidationException, FileException
from ..models.shared.enums import FileFormat, get_file_format_from_magika_label


# File validation constants
MAX_FILENAME_LENGTH = 255
ALLOWED_FILE_EXTENSIONS = {
    '.exe', '.dll', '.sys', '.bin', '.com', '.scr',  # Windows
    '.elf', '.so', '.o', '.ko',                      # Linux
    '.dylib', '.bundle', '.app',                     # macOS
    '.raw', '.dump', '.img', '.firmware'             # Generic binary
}

DANGEROUS_EXTENSIONS = {
    '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jar',
    '.sh', '.py', '.rb', '.pl', '.php'
}

# Binary file content types detected by Magika
BINARY_CONTENT_TYPES = {
    'pe', 'elf', 'macho', 'dex', 'java', 'pyc', 'wasm',
    'sharedlib', 'dll', 'com', 'executable', 'binary'
}

# Content types that indicate binary executables
EXECUTABLE_CONTENT_TYPES = {
    'pe', 'elf', 'macho', 'dex', 'com', 'msdos', 'executable'
}

# Security patterns for sanitization
SENSITIVE_PATTERNS = [
    r'(?i)password\s*[:=]\s*[^\s]+',
    r'(?i)api[_-]?key\s*[:=]\s*[a-zA-Z0-9_\-]+',
    r'(?i)secret\s*[:=]\s*[^\s]+',
    r'(?i)token\s*[:=]\s*[a-zA-Z0-9_\-\.]+',
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
    r'\b(?:\d{1,3}\.){3}\d{1,3}\b',  # IP addresses
    r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'  # UUIDs
]


class FileValidator:
    """File validation utility with security checks and AI-powered format detection."""
    
    def __init__(self, max_size_bytes: int = 104857600):  # 100MB default
        """
        Initialize file validator with Google Magika.
        
        Args:
            max_size_bytes: Maximum allowed file size in bytes
        """
        self.max_size_bytes = max_size_bytes
        self._magika = Magika()
    
    def validate_filename(self, filename: str) -> str:
        """
        Validate and sanitize filename.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
            
        Raises:
            ValidationException: If filename is invalid
        """
        if not filename or not filename.strip():
            raise ValidationException(
                "Filename cannot be empty",
                field_name="filename",
                field_value=filename
            )
        
        filename = filename.strip()
        
        if len(filename) > MAX_FILENAME_LENGTH:
            raise ValidationException(
                f"Filename too long (max {MAX_FILENAME_LENGTH} characters)",
                field_name="filename",
                field_value=filename
            )
        
        # Check for dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00', '\\', '/']
        if any(char in filename for char in dangerous_chars):
            raise ValidationException(
                "Filename contains invalid characters",
                field_name="filename",
                field_value=filename,
                validation_rule="Must not contain: < > : \" | ? * \\ / or null bytes"
            )
        
        # Check for dangerous extensions
        file_ext = Path(filename).suffix.lower()
        if file_ext in DANGEROUS_EXTENSIONS:
            raise ValidationException(
                f"File extension '{file_ext}' not allowed for security reasons",
                field_name="filename",
                field_value=filename
            )
        
        # Check if extension is in allowed list (if specified)
        if ALLOWED_FILE_EXTENSIONS and file_ext not in ALLOWED_FILE_EXTENSIONS:
            raise ValidationException(
                f"File extension '{file_ext}' not supported for analysis",
                field_name="filename",
                field_value=filename,
                validation_rule=f"Allowed extensions: {', '.join(sorted(ALLOWED_FILE_EXTENSIONS))}"
            )
        
        return filename
    
    def validate_file_size(self, file_path: Union[str, Path, BinaryIO]) -> int:
        """
        Validate file size.
        
        Args:
            file_path: Path to file or file-like object
            
        Returns:
            File size in bytes
            
        Raises:
            FileException: If file size is invalid
        """
        try:
            if hasattr(file_path, 'seek') and hasattr(file_path, 'tell'):
                # File-like object
                current_pos = file_path.tell()
                file_path.seek(0, 2)  # Seek to end
                size = file_path.tell()
                file_path.seek(current_pos)  # Restore position
            else:
                # File path
                size = Path(file_path).stat().st_size
        except (OSError, IOError) as e:
            raise FileException(
                f"Cannot determine file size: {e}",
                file_path=str(file_path),
                operation="size_check"
            )
        
        if size == 0:
            raise FileException(
                "File is empty",
                file_path=str(file_path),
                file_size=size,
                operation="size_check"
            )
        
        if size > self.max_size_bytes:
            raise FileException(
                f"File too large: {size} bytes (max {self.max_size_bytes})",
                file_path=str(file_path),
                file_size=size,
                operation="size_check"
            )
        
        return size
    
    def detect_file_format(self, file_path: Union[str, Path, bytes]) -> Dict[str, Any]:
        """
        Detect file format using AI-powered Magika and validate it's a binary file.
        
        Args:
            file_path: Path to file or file content bytes
            
        Returns:
            Dictionary with format information including Magika results
            
        Raises:
            FileException: If file format detection fails
        """
        try:
            if isinstance(file_path, bytes):
                # File content provided - use Magika's identify_bytes
                result = self._magika.identify_bytes(file_path)
                file_size = len(file_path)
                file_name = "uploaded_file"
                path_str = "uploaded_content"
            else:
                # File path provided - use Magika's identify_path
                file_path = Path(file_path)
                if not file_path.exists():
                    raise FileException(
                        f"File not found: {file_path}",
                        file_path=str(file_path),
                        operation="format_detection"
                    )
                
                result = self._magika.identify_path(file_path)
                file_size = file_path.stat().st_size
                file_name = file_path.name
                path_str = str(file_path)
            
            # Extract Magika results
            content_type = result.output.ct_label  # Content type label
            mime_type = result.output.mime_type    # MIME type
            confidence = result.score              # Confidence score (now in main result)
            
            # Determine format information using Magika's AI detection
            format_info = {
                "content_type": content_type,
                "mime_type": mime_type,
                "confidence": confidence,
                "file_size": file_size,
                "filename": file_name,
                "is_binary": self._is_binary_content_type(content_type),
                "is_executable": self._is_executable_content_type(content_type),
                "format": self._map_content_type_to_format(content_type),
                "platform": self._determine_platform_from_content_type(content_type),
                "architecture": None,  # Will be determined during analysis
                "magika_raw": {
                    "ct_label": content_type,
                    "mime_type": mime_type,
                    "magic": result.output.magic,
                    "score": confidence,
                    "dl_prediction": getattr(result, 'dl', None),
                    "output_details": str(result.output)
                }
            }
            
            # Validate that it's a binary file suitable for analysis
            if not format_info["is_binary"]:
                raise FileException(
                    f"File is not a binary executable: detected as '{content_type}' (confidence: {confidence:.3f})",
                    file_path=path_str,
                    file_format=content_type,
                    operation="format_validation"
                )
            
            # Additional validation for low confidence detection
            if confidence < 0.7:  # Magika typically has very high confidence
                format_info["warning"] = f"Low confidence detection: {confidence:.3f}"
            
            return format_info
            
        except Exception as e:
            raise FileException(
                f"AI file format detection failed: {e}",
                file_path=path_str if 'path_str' in locals() else "unknown",
                operation="format_detection"
            )
    
    def _is_binary_content_type(self, content_type: str) -> bool:
        """Check if Magika content type represents a binary file."""
        return content_type.lower() in BINARY_CONTENT_TYPES
    
    def _is_executable_content_type(self, content_type: str) -> bool:
        """Check if Magika content type represents an executable."""
        return content_type.lower() in EXECUTABLE_CONTENT_TYPES
    
    def _map_content_type_to_format(self, content_type: str) -> str:
        """Map Magika content type to our internal format classification."""
        content_type_lower = content_type.lower()
        
        if content_type_lower in ['pe', 'msdos', 'com']:
            return 'pe'
        elif content_type_lower == 'elf':
            return 'elf'
        elif content_type_lower in ['macho', 'dmg']:
            return 'macho'
        elif content_type_lower in ['dex', 'apk']:
            return 'dex'
        elif content_type_lower in ['java', 'jar']:
            return 'java'
        elif content_type_lower == 'wasm':
            return 'wasm'
        elif content_type_lower in ['dll', 'sharedlib']:
            return 'library'
        else:
            return 'raw'
    
    def _determine_platform_from_content_type(self, content_type: str) -> str:
        """Determine target platform from Magika content type."""
        content_type_lower = content_type.lower()
        
        if content_type_lower in ['pe', 'msdos', 'com', 'dll']:
            return 'windows'
        elif content_type_lower == 'elf':
            return 'linux'
        elif content_type_lower in ['macho', 'dmg']:
            return 'macos'
        elif content_type_lower in ['dex', 'apk']:
            return 'android'
        elif content_type_lower in ['java', 'jar']:
            return 'jvm'
        elif content_type_lower == 'wasm':
            return 'web'
        else:
            return 'unknown'


class HashGenerator:
    """Secure hash generation utility for files and data."""
    
    @staticmethod
    def generate_file_hashes(file_path: Union[str, Path, BinaryIO]) -> Dict[str, str]:
        """
        Generate multiple hashes for a file.
        
        Args:
            file_path: Path to file or file-like object
            
        Returns:
            Dictionary with hash algorithm names and hex values
            
        Raises:
            FileException: If hash generation fails
        """
        algorithms = ['md5', 'sha1', 'sha256', 'sha512']
        hashers = {alg: hashlib.new(alg) for alg in algorithms}
        
        try:
            if hasattr(file_path, 'read'):
                # File-like object
                file_obj = file_path
                original_pos = file_obj.tell() if hasattr(file_obj, 'tell') else None
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
            else:
                # File path
                file_obj = open(file_path, 'rb')
                original_pos = None
            
            # Read and hash in chunks to handle large files
            chunk_size = 8192
            while chunk := file_obj.read(chunk_size):
                for hasher in hashers.values():
                    hasher.update(chunk)
            
            # Restore original position for file-like objects
            if original_pos is not None and hasattr(file_obj, 'seek'):
                file_obj.seek(original_pos)
            elif not hasattr(file_path, 'read'):
                file_obj.close()
            
            return {alg: hasher.hexdigest() for alg, hasher in hashers.items()}
            
        except (OSError, IOError) as e:
            raise FileException(
                f"Hash generation failed: {e}",
                file_path=str(file_path) if not hasattr(file_path, 'read') else "file_object",
                operation="hash_generation"
            )
    
    @staticmethod
    def generate_content_hash(content: Union[str, bytes], algorithm: str = 'sha256') -> str:
        """
        Generate hash for string or bytes content.
        
        Args:
            content: Content to hash
            algorithm: Hash algorithm to use
            
        Returns:
            Hex digest of hash
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        hasher = hashlib.new(algorithm)
        hasher.update(content)
        return hasher.hexdigest()
    
    @staticmethod
    def generate_api_key(length: int = 32, prefix: str = 'ak_') -> str:
        """
        Generate secure API key.
        
        Args:
            length: Length of random part
            prefix: Prefix for the API key
            
        Returns:
            Secure random API key
        """
        alphabet = string.ascii_letters + string.digits
        random_part = ''.join(secrets.choice(alphabet) for _ in range(length))
        return f"{prefix}{random_part}"
    
    @staticmethod
    def generate_correlation_id() -> str:
        """Generate unique correlation ID for request tracking."""
        return f"req_{secrets.token_urlsafe(12)}"


class DataSanitizer:
    """Data sanitization utility for security and privacy."""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename for safe storage and display.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
        
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        
        # Ensure reasonable length
        if len(sanitized) > MAX_FILENAME_LENGTH:
            name, ext = os.path.splitext(sanitized)
            max_name_len = MAX_FILENAME_LENGTH - len(ext)
            sanitized = name[:max_name_len] + ext
        
        return sanitized or 'unnamed_file'
    
    @staticmethod
    def sanitize_log_data(data: Any, sensitive_fields: Optional[List[str]] = None) -> Any:
        """
        Sanitize data for safe logging by removing sensitive information.
        
        Args:
            data: Data to sanitize (dict, list, str, etc.)
            sensitive_fields: Additional field names to redact
            
        Returns:
            Sanitized data
        """
        if sensitive_fields is None:
            sensitive_fields = ['password', 'api_key', 'token', 'secret', 'auth']
        
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(field.lower() in key.lower() for field in sensitive_fields):
                    sanitized[key] = "***REDACTED***"
                else:
                    sanitized[key] = DataSanitizer.sanitize_log_data(value, sensitive_fields)
            return sanitized
        
        elif isinstance(data, list):
            return [DataSanitizer.sanitize_log_data(item, sensitive_fields) for item in data]
        
        elif isinstance(data, str):
            # Redact patterns that look like sensitive data
            sanitized = data
            for pattern in SENSITIVE_PATTERNS:
                sanitized = re.sub(pattern, '***REDACTED***', sanitized)
            return sanitized
        
        else:
            return data
    
    @staticmethod
    def sanitize_error_message(message: str) -> str:
        """
        Sanitize error message for safe display to users.
        
        Args:
            message: Original error message
            
        Returns:
            Sanitized error message
        """
        # Remove file paths
        sanitized = re.sub(r'/[^\s]*', '/***PATH***', message)
        sanitized = re.sub(r'[A-Z]:\\[^\s]*', 'C:\\***PATH***', sanitized)
        
        # Remove sensitive patterns
        for pattern in SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, '***REDACTED***', sanitized)
        
        return sanitized
    
    @staticmethod
    def truncate_large_data(data: str, max_length: int = 1000) -> str:
        """
        Truncate large data for logging/display.
        
        Args:
            data: Data to truncate
            max_length: Maximum length to keep
            
        Returns:
            Truncated data with indicator if truncated
        """
        if len(data) <= max_length:
            return data
        
        return data[:max_length] + f"... (truncated, {len(data)} total chars)"


class URLValidator:
    """URL validation utility for callback URLs and webhooks."""
    
    @staticmethod
    def validate_callback_url(url: str) -> bool:
        """
        Validate callback URL for security.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid and safe
            
        Raises:
            ValidationException: If URL is invalid or unsafe
        """
        if not url or not url.strip():
            raise ValidationException(
                "Callback URL cannot be empty",
                field_name="callback_url",
                field_value=url
            )
        
        try:
            parsed = urlparse(url.strip())
        except Exception as e:
            raise ValidationException(
                f"Invalid URL format: {e}",
                field_name="callback_url",
                field_value=url
            )
        
        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            raise ValidationException(
                "Callback URL must use HTTP or HTTPS",
                field_name="callback_url",
                field_value=url,
                validation_rule="Scheme must be http or https"
            )
        
        # Check hostname
        if not parsed.hostname:
            raise ValidationException(
                "Callback URL must have a valid hostname",
                field_name="callback_url",
                field_value=url
            )
        
        # Block dangerous hosts
        dangerous_hosts = ['localhost', '127.0.0.1', '0.0.0.0', '::1']
        if parsed.hostname.lower() in dangerous_hosts:
            raise ValidationException(
                "Callback URL cannot point to localhost",
                field_name="callback_url",
                field_value=url,
                validation_rule="Cannot use localhost, 127.0.0.1, or ::1"
            )
        
        # Block private IP ranges (basic check)
        if parsed.hostname.startswith(('10.', '172.', '192.168.')):
            raise ValidationException(
                "Callback URL cannot point to private IP addresses",
                field_name="callback_url",
                field_value=url,
                validation_rule="Private IP addresses not allowed"
            )
        
        return True


# Utility functions for common operations

def safe_path_join(base_path: Union[str, Path], *paths: str) -> Path:
    """
    Safely join paths preventing directory traversal attacks.
    
    Args:
        base_path: Base directory path
        *paths: Additional path components
        
    Returns:
        Safe resolved path
        
    Raises:
        ValidationException: If path traversal is detected
    """
    base = Path(base_path).resolve()
    
    # Join all path components
    try:
        result = base
        for path_component in paths:
            # Remove any directory traversal attempts
            clean_component = str(path_component).replace('..', '').strip('/')
            if clean_component:
                result = result / clean_component
        
        resolved = result.resolve()
        
        # Ensure result is still under base directory
        if not str(resolved).startswith(str(base)):
            raise ValidationException(
                "Path traversal detected",
                field_name="file_path",
                field_value=str(result),
                validation_rule="Path must be within base directory"
            )
        
        return resolved
    
    except Exception as e:
        raise ValidationException(
            f"Invalid path: {e}",
            field_name="file_path",
            field_value="/".join(str(p) for p in paths)
        )


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def validate_hex_string(hex_str: str, expected_length: Optional[int] = None) -> bool:
    """
    Validate hexadecimal string format.
    
    Args:
        hex_str: Hexadecimal string to validate
        expected_length: Expected length in characters
        
    Returns:
        True if valid hex string
        
    Raises:
        ValidationException: If hex string is invalid
    """
    if not hex_str or not isinstance(hex_str, str):
        raise ValidationException(
            "Hex string cannot be empty",
            field_name="hex_string",
            field_value=hex_str
        )
    
    # Remove common prefixes
    clean_hex = hex_str.lower()
    if clean_hex.startswith('0x'):
        clean_hex = clean_hex[2:]
    
    # Check if all characters are hex
    if not all(c in '0123456789abcdef' for c in clean_hex):
        raise ValidationException(
            "Invalid hexadecimal characters",
            field_name="hex_string",
            field_value=hex_str,
            validation_rule="Must contain only 0-9, a-f, A-F"
        )
    
    # Check expected length
    if expected_length and len(clean_hex) != expected_length:
        raise ValidationException(
            f"Hex string length mismatch: expected {expected_length}, got {len(clean_hex)}",
            field_name="hex_string",
            field_value=hex_str,
            validation_rule=f"Must be exactly {expected_length} characters"
        )
    
    return True


def create_secure_temp_filename(prefix: str = 'bin2nlp_', suffix: str = '.tmp') -> str:
    """
    Create secure temporary filename.
    
    Args:
        prefix: Filename prefix
        suffix: Filename suffix
        
    Returns:
        Secure temporary filename
    """
    random_part = secrets.token_urlsafe(16)
    return f"{prefix}{random_part}{suffix}"


# ADR STANDARDIZED FUNCTIONS - Use these for all file detection
# =============================================================

def detect_file_format(file_content: bytes, filename: Optional[str] = None) -> FileFormat:
    """
    Detect file format using Magika ML-based detection (ADR STANDARDIZED).
    
    This is the preferred method for file format detection per ADR standards.
    Falls back to filename-based detection only if Magika fails.
    
    Args:
        file_content: Raw file content bytes
        filename: Optional filename for fallback detection
        
    Returns:
        FileFormat enum value based on detection
    """
    magika = Magika()
    
    try:
        # Primary detection: Use Magika ML-based detection
        result = magika.identify_bytes(file_content)
        detected_format = get_file_format_from_magika_label(result.output.ct_label)
        
        # If Magika gives us a definitive result, use it
        if detected_format != FileFormat.UNKNOWN:
            return detected_format
            
    except Exception:
        # If Magika fails, fall back to filename-based detection
        pass
    
    # Fallback: Use filename-based detection (if available)
    if filename:
        from ..models.shared.enums import get_file_format_from_extension
        return get_file_format_from_extension(filename)
    
    return FileFormat.UNKNOWN


def validate_binary_file_content(file_content: bytes, filename: Optional[str] = None) -> Tuple[bool, str, FileFormat]:
    """
    Validate file content for binary analysis using Magika (ADR STANDARDIZED).
    
    Args:
        file_content: Raw file content bytes
        filename: Optional filename for additional context
        
    Returns:
        Tuple of (is_valid_binary, detected_type_label, file_format_enum)
    """
    magika = Magika()
    
    try:
        result = magika.identify_bytes(file_content)
        content_type = result.output.ct_label
        file_format = get_file_format_from_magika_label(content_type)
        
        # Check if it's a supported binary type
        is_binary = content_type.lower() in BINARY_CONTENT_TYPES
        
        return is_binary, content_type, file_format
        
    except Exception as e:
        # If Magika fails, return unknown status
        return False, f"detection_failed: {str(e)}", FileFormat.UNKNOWN


def get_file_info_with_magika(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Get comprehensive file information using Magika detection (ADR STANDARDIZED).
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        Dictionary with file information including Magika-based detection
    """
    file_path = Path(file_path)
    magika = Magika()
    
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Use Magika for content detection
        result = magika.identify_bytes(content)
        content_type = result.output.ct_label
        file_format = get_file_format_from_magika_label(content_type)
        
        # Generate file hash
        sha256_hash = hashlib.sha256(content).hexdigest()
        
        return {
            'path': str(file_path),
            'filename': file_path.name,
            'size_bytes': len(content),
            'sha256': sha256_hash,
            'detected_type': content_type,
            'confidence': result.output.score,
            'file_format': file_format,
            'is_binary': content_type.lower() in BINARY_CONTENT_TYPES,
            'is_executable': content_type.lower() in EXECUTABLE_CONTENT_TYPES,
            'detection_method': 'magika'
        }
        
    except Exception as e:
        return {
            'path': str(file_path),
            'filename': file_path.name if file_path.exists() else 'unknown',
            'error': str(e),
            'detection_method': 'failed'
        }