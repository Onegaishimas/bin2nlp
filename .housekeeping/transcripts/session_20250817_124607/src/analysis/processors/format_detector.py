"""
File format detection and validation system.

Provides comprehensive file format detection using multiple techniques including
magic number analysis, header parsing, and ML-based detection with Magika.
"""

import hashlib
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass
from enum import Enum

from magika import Magika

from ...models.shared.enums import FileFormat, Platform
from ...core.logging import get_logger
from ...core.exceptions import UnsupportedFormatException, FileValidationException


logger = get_logger(__name__)


@dataclass
class FormatDetectionResult:
    """Result of file format detection analysis."""
    
    primary_format: FileFormat
    confidence: float
    magika_type: str
    magika_confidence: float
    header_analysis: Dict[str, Any]
    platform: Platform
    warnings: List[str]
    
    @property
    def is_high_confidence(self) -> bool:
        """Check if detection has high confidence (>= 0.8)."""
        return self.confidence >= 0.8
    
    @property
    def is_supported_format(self) -> bool:
        """Check if detected format is supported for analysis."""
        return self.primary_format in [FileFormat.PE, FileFormat.ELF, FileFormat.MACHO]


class HeaderType(Enum):
    """Binary file header types."""
    PE_DOS = "PE_DOS"
    PE_NT = "PE_NT" 
    ELF = "ELF"
    MACHO_32 = "MACHO_32"
    MACHO_64 = "MACHO_64"
    MACHO_UNIVERSAL = "MACHO_UNIVERSAL"
    UNKNOWN = "UNKNOWN"


class FormatDetector:
    """
    Multi-stage file format detector using magic numbers, header analysis, and ML.
    
    Combines traditional binary analysis techniques with modern ML-based detection
    to provide robust and accurate file format identification.
    """
    
    # Magic number patterns for binary formats
    MAGIC_PATTERNS = {
        FileFormat.PE: [
            b'MZ',  # DOS header
        ],
        FileFormat.ELF: [
            b'\x7fELF',  # ELF magic number
        ],
        FileFormat.MACHO: [
            b'\xfe\xed\xfa\xce',  # Mach-O 32-bit big endian
            b'\xce\xfa\xed\xfe',  # Mach-O 32-bit little endian  
            b'\xfe\xed\xfa\xcf',  # Mach-O 64-bit big endian
            b'\xcf\xfa\xed\xfe',  # Mach-O 64-bit little endian
            b'\xca\xfe\xba\xbe',  # Universal binary big endian
            b'\xbe\xba\xfe\xca',  # Universal binary little endian
        ],
        FileFormat.APK: [
            b'PK\x03\x04',  # ZIP signature (APK is ZIP-based)
        ],
    }
    
    # File extension mappings
    EXTENSION_MAPPING = {
        '.exe': FileFormat.PE,
        '.dll': FileFormat.PE,
        '.sys': FileFormat.PE,
        '.scr': FileFormat.PE,
        '.com': FileFormat.PE,
        '.so': FileFormat.ELF,
        '.elf': FileFormat.ELF,
        '.o': FileFormat.ELF,
        '.dylib': FileFormat.MACHO,
        '.bundle': FileFormat.MACHO,
        '.apk': FileFormat.APK,
        '.ipa': FileFormat.IPA,
    }
    
    def __init__(self):
        """Initialize the format detector."""
        self.magika = Magika()
        self.logger = logger.bind(component="format_detector")
    
    async def detect_format(
        self, 
        file_content: bytes, 
        filename: Optional[str] = None,
        file_size: Optional[int] = None
    ) -> FormatDetectionResult:
        """
        Detect file format using multiple detection methods.
        
        Args:
            file_content: Binary file content to analyze
            filename: Original filename (optional, for extension hints)
            file_size: File size in bytes (optional, will calculate if not provided)
            
        Returns:
            Comprehensive format detection result
            
        Raises:
            FileValidationException: If file validation fails
        """
        if file_size is None:
            file_size = len(file_content)
        
        self.logger.info(
            "Starting file format detection",
            filename=filename,
            file_size=file_size,
            content_preview=file_content[:16].hex() if len(file_content) >= 16 else file_content.hex()
        )
        
        # Validate basic file properties
        self._validate_file_content(file_content, file_size)
        
        warnings = []
        
        # Stage 1: Magic number detection
        magic_format = self._detect_by_magic_numbers(file_content)
        
        # Stage 2: Header analysis
        header_analysis = self._analyze_headers(file_content)
        header_format = header_analysis.get('detected_format', FileFormat.UNKNOWN)
        
        # Stage 3: Magika ML detection
        magika_result = self.magika.identify_bytes(file_content)
        magika_format = self._map_magika_to_format(magika_result.output.ct_label)
        magika_confidence = float(magika_result.output.score)
        
        # Stage 4: Extension hint (lowest priority)
        extension_format = FileFormat.UNKNOWN
        if filename:
            extension_format = self._detect_by_extension(filename)
        
        # Combine results and determine primary format
        primary_format, confidence = self._combine_detection_results(
            magic_format, header_format, magika_format, extension_format,
            magika_confidence, warnings
        )
        
        # Determine platform
        platform = self._infer_platform(primary_format, header_analysis)
        
        result = FormatDetectionResult(
            primary_format=primary_format,
            confidence=confidence,
            magika_type=magika_result.output.ct_label,
            magika_confidence=magika_confidence,
            header_analysis=header_analysis,
            platform=platform,
            warnings=warnings
        )
        
        self.logger.info(
            "Format detection completed",
            primary_format=primary_format.value,
            confidence=confidence,
            platform=platform.value,
            magika_type=magika_result.output.ct_label,
            warnings_count=len(warnings)
        )
        
        return result
    
    def _validate_file_content(self, file_content: bytes, file_size: int) -> None:
        """Validate basic file properties."""
        if not file_content:
            raise FileValidationException("File content is empty")
        
        if file_size <= 0:
            raise FileValidationException("Invalid file size")
        
        if len(file_content) != file_size:
            raise FileValidationException(
                f"Content length ({len(file_content)}) doesn't match reported size ({file_size})"
            )
        
        # Check for minimum size requirements
        if file_size < 64:
            raise FileValidationException(
                f"File too small for binary analysis: {file_size} bytes (minimum 64 bytes)"
            )
        
        # Check for maximum size (configurable limit)
        max_size = 100 * 1024 * 1024  # 100MB default
        if file_size > max_size:
            raise FileValidationException(
                f"File too large for analysis: {file_size} bytes (maximum {max_size} bytes)"
            )
    
    def _detect_by_magic_numbers(self, file_content: bytes) -> FileFormat:
        """Detect format using magic number patterns."""
        for file_format, patterns in self.MAGIC_PATTERNS.items():
            for pattern in patterns:
                if file_content.startswith(pattern):
                    self.logger.debug(
                        "Magic number match found",
                        format=file_format.value,
                        pattern=pattern.hex()
                    )
                    return file_format
        
        return FileFormat.UNKNOWN
    
    def _analyze_headers(self, file_content: bytes) -> Dict[str, Any]:
        """Analyze file headers for format-specific information."""
        header_info = {
            'detected_format': FileFormat.UNKNOWN,
            'header_type': HeaderType.UNKNOWN,
            'architecture': 'unknown',
            'endianness': 'unknown',
            'entry_point': None,
            'sections': [],
            'imports': [],
            'corruption_indicators': []
        }
        
        try:
            # Try PE analysis
            pe_info = self._analyze_pe_header(file_content)
            if pe_info['valid']:
                header_info.update(pe_info)
                header_info['detected_format'] = FileFormat.PE
                return header_info
        except Exception as e:
            self.logger.debug("PE header analysis failed", error=str(e))
        
        try:
            # Try ELF analysis
            elf_info = self._analyze_elf_header(file_content)
            if elf_info['valid']:
                header_info.update(elf_info)
                header_info['detected_format'] = FileFormat.ELF
                return header_info
        except Exception as e:
            self.logger.debug("ELF header analysis failed", error=str(e))
        
        try:
            # Try Mach-O analysis
            macho_info = self._analyze_macho_header(file_content)
            if macho_info['valid']:
                header_info.update(macho_info)
                header_info['detected_format'] = FileFormat.MACHO
                return header_info
        except Exception as e:
            self.logger.debug("Mach-O header analysis failed", error=str(e))
        
        return header_info
    
    def _analyze_pe_header(self, file_content: bytes) -> Dict[str, Any]:
        """Analyze PE file header structure."""
        if len(file_content) < 64:
            return {'valid': False}
        
        # Check DOS header
        if not file_content.startswith(b'MZ'):
            return {'valid': False}
        
        # Get PE header offset
        pe_offset = struct.unpack('<I', file_content[60:64])[0]
        
        if pe_offset >= len(file_content) - 4:
            return {'valid': False}
        
        # Check PE signature
        if file_content[pe_offset:pe_offset+4] != b'PE\x00\x00':
            return {'valid': False}
        
        # Parse COFF header
        coff_header = file_content[pe_offset+4:pe_offset+24]
        if len(coff_header) < 20:
            return {'valid': False}
        
        machine, _, _, _, _, _, characteristics = struct.unpack('<HHLLLHH', coff_header)
        
        # Determine architecture
        architecture_map = {
            0x014c: 'i386',
            0x0200: 'ia64',
            0x8664: 'x86_64',
            0x01c0: 'arm',
            0xaa64: 'aarch64'
        }
        
        return {
            'valid': True,
            'header_type': HeaderType.PE_NT,
            'architecture': architecture_map.get(machine, f'unknown_{machine:x}'),
            'endianness': 'little',
            'machine_type': machine,
            'characteristics': characteristics,
            'pe_offset': pe_offset
        }
    
    def _analyze_elf_header(self, file_content: bytes) -> Dict[str, Any]:
        """Analyze ELF file header structure."""
        if len(file_content) < 52:  # Minimum ELF header size
            return {'valid': False}
        
        if not file_content.startswith(b'\x7fELF'):
            return {'valid': False}
        
        # Parse ELF header
        ei_class = file_content[4]  # 32-bit or 64-bit
        ei_data = file_content[5]   # Endianness
        
        is_64bit = ei_class == 2
        is_big_endian = ei_data == 2
        
        endianness = 'big' if is_big_endian else 'little'
        endian_char = '>' if is_big_endian else '<'
        
        # Parse machine type
        if is_64bit and len(file_content) >= 64:
            machine = struct.unpack(f'{endian_char}H', file_content[18:20])[0]
        else:
            machine = struct.unpack(f'{endian_char}H', file_content[18:20])[0]
        
        architecture_map = {
            0x03: 'i386',
            0x3e: 'x86_64',
            0x28: 'arm',
            0xb7: 'aarch64',
            0x08: 'mips',
            0x14: 'powerpc'
        }
        
        return {
            'valid': True,
            'header_type': HeaderType.ELF,
            'architecture': architecture_map.get(machine, f'unknown_{machine:x}'),
            'endianness': endianness,
            'class': '64-bit' if is_64bit else '32-bit',
            'machine_type': machine
        }
    
    def _analyze_macho_header(self, file_content: bytes) -> Dict[str, Any]:
        """Analyze Mach-O file header structure."""
        if len(file_content) < 28:
            return {'valid': False}
        
        magic = struct.unpack('<I', file_content[0:4])[0]
        
        magic_map = {
            0xfeedface: ('32-bit', 'little', HeaderType.MACHO_32),
            0xcefaedfe: ('32-bit', 'big', HeaderType.MACHO_32),
            0xfeedfacf: ('64-bit', 'little', HeaderType.MACHO_64),
            0xcffaedfe: ('64-bit', 'big', HeaderType.MACHO_64),
            0xcafebabe: ('universal', 'big', HeaderType.MACHO_UNIVERSAL),
            0xbebafeca: ('universal', 'little', HeaderType.MACHO_UNIVERSAL)
        }
        
        if magic not in magic_map:
            return {'valid': False}
        
        arch_class, endianness, header_type = magic_map[magic]
        
        # For universal binaries, analyze the fat header
        if header_type == HeaderType.MACHO_UNIVERSAL:
            if len(file_content) < 8:
                return {'valid': False}
            nfat_arch = struct.unpack('>I', file_content[4:8])[0]
            return {
                'valid': True,
                'header_type': header_type,
                'architecture': 'universal',
                'endianness': endianness,
                'class': arch_class,
                'fat_architectures': nfat_arch
            }
        
        # Parse CPU type for single-arch binaries
        endian_char = '>' if endianness == 'big' else '<'
        cputype = struct.unpack(f'{endian_char}I', file_content[4:8])[0]
        
        cpu_map = {
            7: 'i386',
            16777223: 'x86_64',  # CPU_TYPE_X86_64
            12: 'arm',
            16777228: 'aarch64'  # CPU_TYPE_ARM64
        }
        
        return {
            'valid': True,
            'header_type': header_type,
            'architecture': cpu_map.get(cputype, f'unknown_{cputype}'),
            'endianness': endianness,
            'class': arch_class,
            'cpu_type': cputype
        }
    
    def _detect_by_extension(self, filename: str) -> FileFormat:
        """Detect format using file extension as a hint."""
        if not filename:
            return FileFormat.UNKNOWN
        
        extension = Path(filename).suffix.lower()
        return self.EXTENSION_MAPPING.get(extension, FileFormat.UNKNOWN)
    
    def _map_magika_to_format(self, magika_type: str) -> FileFormat:
        """Map Magika content type to our FileFormat enum."""
        magika_mapping = {
            'peexe': FileFormat.PE,
            'elf': FileFormat.ELF,
            'macho': FileFormat.MACHO,
            'apk': FileFormat.APK,
            'ipa': FileFormat.IPA,
        }
        
        return magika_mapping.get(magika_type.lower(), FileFormat.UNKNOWN)
    
    def _combine_detection_results(
        self,
        magic_format: FileFormat,
        header_format: FileFormat, 
        magika_format: FileFormat,
        extension_format: FileFormat,
        magika_confidence: float,
        warnings: List[str]
    ) -> Tuple[FileFormat, float]:
        """Combine multiple detection results into final format and confidence."""
        
        # Count agreement between methods
        formats = [magic_format, header_format, magika_format, extension_format]
        non_unknown_formats = [f for f in formats if f != FileFormat.UNKNOWN]
        
        if not non_unknown_formats:
            return FileFormat.UNKNOWN, 0.0
        
        # If all methods agree, high confidence
        if len(set(non_unknown_formats)) == 1:
            primary_format = non_unknown_formats[0]
            confidence = min(0.95, 0.7 + (magika_confidence * 0.25))
            return primary_format, confidence
        
        # Priority order: header analysis > magic numbers > magika > extension
        if header_format != FileFormat.UNKNOWN:
            primary_format = header_format
            base_confidence = 0.8
        elif magic_format != FileFormat.UNKNOWN:
            primary_format = magic_format  
            base_confidence = 0.7
        elif magika_format != FileFormat.UNKNOWN:
            primary_format = magika_format
            base_confidence = 0.6
        else:
            primary_format = extension_format
            base_confidence = 0.3
        
        # Adjust confidence based on agreement
        agreement_count = sum(1 for f in non_unknown_formats if f == primary_format)
        agreement_bonus = (agreement_count - 1) * 0.1
        
        # Factor in Magika confidence
        magika_bonus = magika_confidence * 0.1 if magika_format == primary_format else 0
        
        final_confidence = min(0.95, base_confidence + agreement_bonus + magika_bonus)
        
        # Add warnings for disagreements
        if len(set(non_unknown_formats)) > 1:
            warnings.append(
                f"Detection methods disagree: magic={magic_format.value}, "
                f"header={header_format.value}, magika={magika_format.value}, "
                f"extension={extension_format.value}"
            )
        
        return primary_format, final_confidence
    
    def _infer_platform(
        self, 
        file_format: FileFormat, 
        header_analysis: Dict[str, Any]
    ) -> Platform:
        """Infer target platform from file format and header analysis."""
        
        # Direct format-to-platform mapping
        if file_format == FileFormat.PE:
            return Platform.WINDOWS
        elif file_format == FileFormat.ELF:
            # ELF can be Linux or other Unix-like systems, default to Linux
            return Platform.LINUX
        elif file_format == FileFormat.MACHO:
            return Platform.MACOS
        elif file_format == FileFormat.APK:
            return Platform.ANDROID
        elif file_format == FileFormat.IPA:
            return Platform.IOS
        
        return Platform.UNKNOWN
    
    async def validate_file_integrity(
        self, 
        file_content: bytes,
        expected_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate file integrity and detect potential corruption.
        
        Args:
            file_content: Binary file content
            expected_hash: Expected SHA-256 hash (optional)
            
        Returns:
            Integrity validation result
        """
        result = {
            'is_valid': True,
            'corruption_indicators': [],
            'hash_matches': None,
            'calculated_hash': None,
            'size_anomalies': []
        }
        
        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        result['calculated_hash'] = file_hash
        
        if expected_hash:
            result['hash_matches'] = file_hash.lower() == expected_hash.lower()
            if not result['hash_matches']:
                result['corruption_indicators'].append(
                    f"Hash mismatch: expected {expected_hash}, got {file_hash}"
                )
        
        # Check for truncation indicators
        if len(file_content) < 1024 and not file_content.endswith(b'\x00' * 10):
            result['size_anomalies'].append("File appears truncated")
        
        # Check for null byte patterns that might indicate corruption
        null_runs = []
        null_start = None
        for i, byte in enumerate(file_content):
            if byte == 0:
                if null_start is None:
                    null_start = i
            else:
                if null_start is not None and i - null_start > 100:
                    null_runs.append((null_start, i))
                null_start = None
        
        if len(null_runs) > 3:
            result['corruption_indicators'].append(
                f"Excessive null byte sequences found: {len(null_runs)} runs"
            )
        
        # Overall integrity assessment
        result['is_valid'] = (
            len(result['corruption_indicators']) == 0 and
            (result['hash_matches'] is None or result['hash_matches'])
        )
        
        self.logger.debug(
            "File integrity validation completed",
            is_valid=result['is_valid'],
            corruption_count=len(result['corruption_indicators']),
            hash_matches=result['hash_matches']
        )
        
        return result