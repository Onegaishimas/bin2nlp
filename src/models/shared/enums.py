"""
Shared enumerations for the bin2nlp analysis system.

Provides standard enumerations for job statuses, analysis configurations,
file formats, and platform types used throughout the application.
"""

from enum import Enum
from typing import Dict, List


class JobStatus(str, Enum):
    """
    Enumeration for analysis job status tracking.
    
    Represents the current state of an analysis job in the processing pipeline.
    Used for job queue management and status reporting.
    """
    
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
    @classmethod
    def terminal_states(cls) -> List['JobStatus']:
        """Return list of terminal job states that don't transition further."""
        return [cls.COMPLETED, cls.FAILED, cls.CANCELLED]
    
    @classmethod
    def active_states(cls) -> List['JobStatus']:
        """Return list of active job states that may still transition."""
        return [cls.PENDING, cls.PROCESSING]
    
    def is_terminal(self) -> bool:
        """Check if this status is a terminal state."""
        return self in self.terminal_states()
    
    def is_active(self) -> bool:
        """Check if this status represents an active job."""
        return self in self.active_states()


class AnalysisDepth(str, Enum):
    """
    Enumeration for analysis depth configuration.
    
    Controls the comprehensiveness of binary analysis operations.
    Affects processing time and resource usage.
    """
    
    QUICK = "quick"           # Basic analysis, fast results (< 30 seconds)
    STANDARD = "standard"     # Standard analysis, balanced approach (< 5 minutes)
    COMPREHENSIVE = "comprehensive"  # Deep analysis, thorough results (< 20 minutes)
    
    @classmethod
    def get_timeout_seconds(cls, depth: 'AnalysisDepth') -> int:
        """Get recommended timeout in seconds for analysis depth."""
        timeouts = {
            cls.QUICK: 30,
            cls.STANDARD: 300,  # 5 minutes
            cls.COMPREHENSIVE: 1200  # 20 minutes
        }
        return timeouts.get(depth, 300)
    
    def get_timeout(self) -> int:
        """Get timeout for this analysis depth."""
        return self.get_timeout_seconds(self)
    
    @property
    def description(self) -> str:
        """Get human-readable description of analysis depth."""
        descriptions = {
            self.QUICK: "Fast analysis with basic functionality detection",
            self.STANDARD: "Balanced analysis with comprehensive feature detection", 
            self.COMPREHENSIVE: "Deep analysis with extensive security and behavioral patterns"
        }
        return descriptions.get(self, "Unknown analysis depth")


class FileFormat(str, Enum):
    """
    Enumeration for supported binary file formats.
    
    Represents the detected or expected format of binary files
    submitted for analysis.
    """
    
    PE = "pe"           # Windows Portable Executable
    ELF = "elf"         # Linux Executable and Linkable Format
    MACHO = "macho"     # macOS Mach-O format
    APK = "apk"         # Android Package
    IPA = "ipa"         # iOS Application Package
    JAVA = "java"       # Java bytecode/JAR files
    WASM = "wasm"       # WebAssembly modules
    RAW = "raw"         # Raw binary data
    UNKNOWN = "unknown" # Unrecognized or unsupported format
    
    @classmethod
    def get_supported_formats(cls) -> List['FileFormat']:
        """Return list of fully supported file formats."""
        return [cls.PE, cls.ELF, cls.MACHO]
    
    @classmethod
    def get_experimental_formats(cls) -> List['FileFormat']:
        """Return list of experimentally supported formats."""
        return [cls.APK, cls.IPA]
    
    @classmethod
    def get_all_known_formats(cls) -> List['FileFormat']:
        """Return all known formats excluding UNKNOWN."""
        return [fmt for fmt in cls if fmt != cls.UNKNOWN]
    
    def is_supported(self) -> bool:
        """Check if this format is fully supported."""
        return self in self.get_supported_formats()
    
    def is_experimental(self) -> bool:
        """Check if this format has experimental support."""
        return self in self.get_experimental_formats()
    
    @property
    def description(self) -> str:
        """Get human-readable description of file format."""
        descriptions = {
            self.PE: "Windows Portable Executable (PE)",
            self.ELF: "Linux Executable and Linkable Format (ELF)",
            self.MACHO: "macOS Mach-O executable format",
            self.APK: "Android Package (APK) - experimental support",
            self.IPA: "iOS Application Package (IPA) - experimental support",
            self.UNKNOWN: "Unknown or unsupported file format"
        }
        return descriptions.get(self, "Unknown file format")


class Platform(str, Enum):
    """
    Enumeration for target platform identification.
    
    Represents the intended execution platform for binary files.
    Used for platform-specific analysis and security assessments.
    """
    
    WINDOWS = "windows"
    LINUX = "linux" 
    MACOS = "macos"
    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"
    
    @classmethod
    def get_desktop_platforms(cls) -> List['Platform']:
        """Return list of desktop/server platforms."""
        return [cls.WINDOWS, cls.LINUX, cls.MACOS]
    
    @classmethod
    def get_mobile_platforms(cls) -> List['Platform']:
        """Return list of mobile platforms."""
        return [cls.ANDROID, cls.IOS]
    
    @classmethod
    def from_file_format(cls, file_format: FileFormat) -> 'Platform':
        """Infer platform from file format."""
        format_to_platform = {
            FileFormat.PE: cls.WINDOWS,
            FileFormat.ELF: cls.LINUX,
            FileFormat.MACHO: cls.MACOS,
            FileFormat.APK: cls.ANDROID,
            FileFormat.IPA: cls.IOS,
            FileFormat.UNKNOWN: cls.UNKNOWN
        }
        return format_to_platform.get(file_format, cls.UNKNOWN)
    
    def is_desktop(self) -> bool:
        """Check if this is a desktop/server platform."""
        return self in self.get_desktop_platforms()
    
    def is_mobile(self) -> bool:
        """Check if this is a mobile platform."""
        return self in self.get_mobile_platforms()
    
    @property
    def description(self) -> str:
        """Get human-readable description of platform."""
        descriptions = {
            self.WINDOWS: "Microsoft Windows",
            self.LINUX: "Linux",
            self.MACOS: "Apple macOS",
            self.ANDROID: "Google Android",
            self.IOS: "Apple iOS",
            self.UNKNOWN: "Unknown or unsupported platform"
        }
        return descriptions.get(self, "Unknown platform")


class AnalysisFocus(str, Enum):
    """
    Enumeration for analysis focus areas.
    
    Allows users to specify particular aspects of analysis to emphasize.
    Can be combined for comprehensive analysis.
    """
    
    SECURITY = "security"           # Focus on security patterns and risks
    FUNCTIONS = "functions"         # Emphasize function analysis and call graphs
    STRINGS = "strings"             # Detailed string extraction and analysis
    IMPORTS = "imports"             # Focus on import/export analysis
    METADATA = "metadata"           # Emphasize file metadata and headers
    ALL = "all"                     # Comprehensive analysis of all areas
    
    @classmethod
    def get_default_focus_areas(cls) -> List['AnalysisFocus']:
        """Return default focus areas for standard analysis."""
        return [cls.SECURITY, cls.FUNCTIONS, cls.STRINGS]
    
    @property
    def description(self) -> str:
        """Get human-readable description of focus area."""
        descriptions = {
            self.SECURITY: "Security patterns, suspicious behaviors, and risk assessment",
            self.FUNCTIONS: "Function detection, analysis, and call graph generation",
            self.STRINGS: "String extraction, categorization, and significance analysis",
            self.IMPORTS: "Import/export analysis and dependency tracking",
            self.METADATA: "File metadata, headers, and structural information",
            self.ALL: "Comprehensive analysis covering all available areas"
        }
        return descriptions.get(self, "Unknown focus area")


class StringCategory(str, Enum):
    """
    Enumeration for string categorization during binary analysis.
    
    Categorizes extracted strings based on content patterns and usage.
    Used for string filtering, prioritization, and security analysis.
    """
    
    URL = "url"                     # HTTP/HTTPS/FTP URLs
    DOMAIN = "domain"               # Domain names and IP addresses
    EMAIL = "email"                 # Email addresses
    FILE_PATH = "file_path"         # File system paths (Windows, Unix, UNC)
    REGISTRY = "registry"           # Windows registry keys
    CREDENTIAL = "credential"       # Password, key, token, auth patterns
    CONFIGURATION = "configuration" # Configuration keys, INI sections, XML
    EXECUTABLE = "executable"       # Executable and library names
    NETWORK_SERVICE = "network_service"  # Network service URLs and protocols
    FORMAT_STRING = "format_string" # C/Python/.NET format strings
    COMMAND_LINE = "command_line"   # Command line flags and options
    GENERIC = "generic"             # Generic printable strings
    BINARY_DATA = "binary_data"     # Non-printable or binary content
    
    @property
    def description(self) -> str:
        """Get human-readable description of string category."""
        descriptions = {
            self.URL: "Web URLs (HTTP, HTTPS, FTP)",
            self.DOMAIN: "Domain names, hostnames, and IP addresses",
            self.EMAIL: "Email addresses",
            self.FILE_PATH: "File system paths and locations",
            self.REGISTRY: "Windows registry keys and values",
            self.CREDENTIAL: "Authentication credentials and security tokens",
            self.CONFIGURATION: "Configuration parameters and settings",
            self.EXECUTABLE: "Executable files and library names",
            self.NETWORK_SERVICE: "Network services and protocol URLs",
            self.FORMAT_STRING: "String formatting templates",
            self.COMMAND_LINE: "Command line arguments and flags",
            self.GENERIC: "General printable text strings",
            self.BINARY_DATA: "Non-printable or binary content"
        }
        return descriptions.get(self, "Unknown string category")
    
    @classmethod
    def get_high_priority_categories(cls) -> List['StringCategory']:
        """Return categories that typically indicate high-value strings."""
        return [
            cls.CREDENTIAL,
            cls.URL,
            cls.NETWORK_SERVICE,
            cls.EMAIL,
            cls.REGISTRY
        ]
    
    def is_high_priority(self) -> bool:
        """Check if this category is typically high-priority."""
        return self in self.get_high_priority_categories()


class StringSignificance(str, Enum):
    """
    Enumeration for string significance scoring.
    
    Represents the relative importance of extracted strings for analysis.
    Used for filtering and prioritizing strings in analysis workflows.
    """
    
    CRITICAL = "critical"   # Highest significance (credentials, C&C URLs)
    HIGH = "high"          # High significance (network indicators, registry keys)
    MEDIUM = "medium"      # Medium significance (file paths, configuration)
    LOW = "low"           # Low significance (generic strings, common text)
    NOISE = "noise"       # Minimal significance (repetitive, irrelevant strings)
    
    @property
    def description(self) -> str:
        """Get human-readable description of significance level."""
        descriptions = {
            self.CRITICAL: "Critical for security analysis (credentials, C&C)",
            self.HIGH: "High importance (network indicators, security-relevant)",
            self.MEDIUM: "Moderate importance (configuration, file paths)",
            self.LOW: "Low importance (generic application strings)",
            self.NOISE: "Minimal importance (repetitive or common strings)"
        }
        return descriptions.get(self, "Unknown significance level")
    
    @classmethod
    def get_analysis_priorities(cls) -> List['StringSignificance']:
        """Return significance levels in analysis priority order."""
        return [cls.CRITICAL, cls.HIGH, cls.MEDIUM, cls.LOW, cls.NOISE]
    
    def get_priority_score(self) -> int:
        """Get numeric priority score for sorting (higher = more important)."""
        scores = {
            self.CRITICAL: 5,
            self.HIGH: 4,
            self.MEDIUM: 3,
            self.LOW: 2,
            self.NOISE: 1
        }
        return scores.get(self, 0)


# Valid state transitions for job status management
JOB_STATE_TRANSITIONS: Dict[JobStatus, List[JobStatus]] = {
    JobStatus.PENDING: [JobStatus.PROCESSING, JobStatus.CANCELLED],
    JobStatus.PROCESSING: [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED],
    JobStatus.COMPLETED: [],  # Terminal state
    JobStatus.FAILED: [],     # Terminal state
    JobStatus.CANCELLED: []   # Terminal state
}


def validate_job_transition(from_status: JobStatus, to_status: JobStatus) -> bool:
    """
    Validate if a job status transition is allowed.
    
    Args:
        from_status: Current job status
        to_status: Desired new status
        
    Returns:
        True if transition is valid, False otherwise
    """
    valid_transitions = JOB_STATE_TRANSITIONS.get(from_status, [])
    return to_status in valid_transitions


def get_file_format_from_extension(filename: str) -> FileFormat:
    """
    DEPRECATED: Attempt to determine file format from filename extension.
    
    ⚠️  WARNING: This function is deprecated and violates our ADR standards.
    Use Magika-based file detection instead via src/core/utils.py
    
    This function should only be used as a fallback when file content
    is not available. Prefer get_file_format_from_content() when possible.
    
    Args:
        filename: Name of the file including extension
        
    Returns:
        Likely file format based on extension (UNRELIABLE)
    """
    import warnings
    warnings.warn(
        "get_file_format_from_extension() is deprecated. "
        "Use Magika-based detection via src/core/utils.py instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    filename_lower = filename.lower()
    
    if filename_lower.endswith(('.exe', '.dll', '.sys', '.scr')):
        return FileFormat.PE
    elif filename_lower.endswith(('.so', '.o', '.a')):
        return FileFormat.ELF
    elif filename_lower.endswith(('.dylib', '.bundle')):
        return FileFormat.MACHO
    elif filename_lower.endswith('.apk'):
        return FileFormat.APK
    elif filename_lower.endswith('.ipa'):
        return FileFormat.IPA
    else:
        return FileFormat.UNKNOWN


def get_file_format_from_magika_label(magika_label: str) -> FileFormat:
    """
    Convert Magika content type label to FileFormat enum.
    
    This is the PREFERRED method for file format detection per ADR standards.
    
    Args:
        magika_label: Content type label from Magika detection
        
    Returns:
        FileFormat enum value based on Magika detection
    """
    label_lower = magika_label.lower()
    
    # Map Magika labels to our FileFormat enum
    magika_to_format = {
        'pe': FileFormat.PE,
        'msdos': FileFormat.PE,
        'com': FileFormat.PE,
        'dll': FileFormat.PE,
        'elf': FileFormat.ELF,
        'macho': FileFormat.MACHO,
        'dex': FileFormat.APK,  # DEX files are Android
        'apk': FileFormat.APK,
        'dmg': FileFormat.MACHO,  # DMG typically contains macOS apps
        'jar': FileFormat.JAVA,
        'java': FileFormat.JAVA,
        'wasm': FileFormat.WASM,
        'binary': FileFormat.RAW,
        'executable': FileFormat.RAW,  # Generic executable
        'sharedlib': FileFormat.ELF,   # Shared libraries are typically ELF
    }
    
    return magika_to_format.get(label_lower, FileFormat.UNKNOWN)