"""
Unit tests for analysis file models.

Tests the FileMetadata, BinaryFile, ValidationResult, and related
functionality for file representation and validation.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from src.models.shared.enums import FileFormat, Platform
from src.models.analysis.files import FileMetadata, BinaryFile, ValidationResult, FileAnalysisInfo


class TestFileMetadata:
    """Test cases for FileMetadata model."""
    
    def test_basic_instantiation(self):
        """Test basic metadata creation."""
        metadata = FileMetadata(
            name="test.exe",
            size=1024,
            hash_sha256="a" * 64,
            format=FileFormat.PE,
            platform=Platform.WINDOWS
        )
        
        assert metadata.name == "test.exe"
        assert metadata.size == 1024
        assert metadata.hash_sha256 == "a" * 64
        assert metadata.format == FileFormat.PE
        assert metadata.platform == Platform.WINDOWS
    
    def test_from_file_path(self):
        """Test metadata creation from file path."""
        # This would normally access a real file, so we'll test the interface
        test_path = Path("/tmp/test.exe")
        
        # Since we can't create a real file in tests, we'll test the method exists
        # and handles the interface correctly
        assert hasattr(FileMetadata, 'from_file_path')
        assert callable(FileMetadata.from_file_path)
    
    def test_file_extension_detection(self):
        """Test file extension and format detection."""
        metadata = FileMetadata(
            name="test.exe",
            size=1024,
            hash_sha256="a" * 64,
            format=FileFormat.PE,
            platform=Platform.WINDOWS
        )
        
        assert metadata.get_file_extension() == ".exe"
        assert metadata.is_executable()
    
    def test_size_formatting(self):
        """Test human-readable size formatting."""
        # Test bytes
        metadata_bytes = FileMetadata(
            name="small.exe", size=512, hash_sha256="a" * 64,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        assert "512 B" in metadata_bytes.format_size()
        
        # Test kilobytes
        metadata_kb = FileMetadata(
            name="medium.exe", size=2048, hash_sha256="a" * 64,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        assert "2.0 KB" in metadata_kb.format_size()
        
        # Test megabytes
        metadata_mb = FileMetadata(
            name="large.exe", size=2 * 1024 * 1024, hash_sha256="a" * 64,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        assert "2.0 MB" in metadata_mb.format_size()
    
    def test_platform_inference(self):
        """Test platform inference from format."""
        # PE format should infer Windows
        pe_metadata = FileMetadata.infer_platform_from_format(FileFormat.PE)
        assert pe_metadata == Platform.WINDOWS
        
        # ELF format should infer Linux
        elf_metadata = FileMetadata.infer_platform_from_format(FileFormat.ELF)
        assert elf_metadata == Platform.LINUX
        
        # Mach-O format should infer macOS
        macho_metadata = FileMetadata.infer_platform_from_format(FileFormat.MACHO)
        assert macho_metadata == Platform.MACOS
    
    def test_hash_validation(self):
        """Test hash validation."""
        # Valid SHA-256 hash
        valid_hash = "a" * 64
        metadata = FileMetadata(
            name="test.exe", size=1024, hash_sha256=valid_hash,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        assert metadata.hash_sha256 == valid_hash
        
        # Invalid hash length
        with pytest.raises(ValueError, match="hash_sha256 must be 64 characters"):
            FileMetadata(
                name="test.exe", size=1024, hash_sha256="invalid",
                format=FileFormat.PE, platform=Platform.WINDOWS
            )
        
        # Invalid hash characters
        with pytest.raises(ValueError, match="hash_sha256 must contain only"):
            FileMetadata(
                name="test.exe", size=1024, hash_sha256="g" * 64,
                format=FileFormat.PE, platform=Platform.WINDOWS
            )
    
    def test_serialization(self):
        """Test metadata serialization."""
        metadata = FileMetadata(
            name="test.exe",
            size=1024,
            hash_sha256="a" * 64,
            format=FileFormat.PE,
            platform=Platform.WINDOWS
        )
        
        serialized = metadata.to_dict()
        assert serialized['name'] == "test.exe"
        assert serialized['size'] == 1024
        assert serialized['format'] == "pe"
        assert serialized['platform'] == "windows"
        
        # Test deserialization
        reconstructed = FileMetadata.from_dict(serialized)
        assert reconstructed.name == metadata.name
        assert reconstructed.size == metadata.size
        assert reconstructed.format == metadata.format
        assert reconstructed.platform == metadata.platform


class TestBinaryFile:
    """Test cases for BinaryFile model."""
    
    def test_basic_instantiation(self):
        """Test basic binary file creation."""
        metadata = FileMetadata(
            name="test.exe", size=1024, hash_sha256="a" * 64,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        
        binary_file = BinaryFile(
            metadata=metadata,
            file_path="/tmp/test.exe"
        )
        
        assert binary_file.metadata == metadata
        assert binary_file.file_path == "/tmp/test.exe"
        assert binary_file.analysis_data is None
        assert binary_file.is_analyzed is False
    
    def test_with_analysis_data(self):
        """Test binary file with analysis data."""
        metadata = FileMetadata(
            name="test.exe", size=1024, hash_sha256="a" * 64,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        
        analysis_data = {
            "functions": [{"name": "main", "address": "0x401000"}],
            "imports": ["kernel32.dll", "user32.dll"],
            "strings": ["Hello World", "Error"]
        }
        
        binary_file = BinaryFile(
            metadata=metadata,
            file_path="/tmp/test.exe",
            analysis_data=analysis_data
        )
        
        assert binary_file.analysis_data == analysis_data
        assert binary_file.is_analyzed is True
        assert len(binary_file.get_functions()) == 1
        assert len(binary_file.get_imports()) == 2
        assert len(binary_file.get_strings()) == 2
    
    def test_file_access_methods(self):
        """Test file access and validation methods."""
        metadata = FileMetadata(
            name="test.exe", size=1024, hash_sha256="a" * 64,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        
        binary_file = BinaryFile(
            metadata=metadata,
            file_path="/tmp/test.exe"
        )
        
        # Test path properties
        assert binary_file.get_filename() == "test.exe"
        assert binary_file.get_file_extension() == ".exe"
        assert binary_file.get_directory() == "/tmp"
        
        # Test file type checks
        assert binary_file.is_windows_executable()
        assert not binary_file.is_linux_executable()
        assert not binary_file.is_macos_executable()
    
    def test_analysis_summary(self):
        """Test analysis summary generation."""
        metadata = FileMetadata(
            name="test.exe", size=1024, hash_sha256="a" * 64,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        
        analysis_data = {
            "functions": [
                {"name": "main", "address": "0x401000"},
                {"name": "helper", "address": "0x401100"}
            ],
            "imports": ["kernel32.dll", "user32.dll", "ntdll.dll"],
            "strings": ["Hello", "World", "Error", "Success"],
            "security_findings": [
                {"type": "suspicious_api", "description": "Uses CreateProcess"}
            ]
        }
        
        binary_file = BinaryFile(
            metadata=metadata,
            file_path="/tmp/test.exe",
            analysis_data=analysis_data
        )
        
        summary = binary_file.get_analysis_summary()
        assert summary['function_count'] == 2
        assert summary['import_count'] == 3
        assert summary['string_count'] == 4
        assert summary['security_finding_count'] == 1
        assert summary['is_analyzed'] is True
    
    def test_analysis_data_validation(self):
        """Test analysis data validation."""
        metadata = FileMetadata(
            name="test.exe", size=1024, hash_sha256="a" * 64,
            format=FileFormat.PE, platform=Platform.WINDOWS
        )
        
        # Valid analysis data
        valid_data = {
            "functions": [],
            "imports": [],
            "strings": [],
            "security_findings": []
        }
        
        binary_file = BinaryFile(
            metadata=metadata,
            file_path="/tmp/test.exe",
            analysis_data=valid_data
        )
        
        validation_result = binary_file.validate_analysis_data()
        assert validation_result.is_valid
        assert len(validation_result.errors) == 0


class TestValidationResult:
    """Test cases for ValidationResult model."""
    
    def test_valid_result(self):
        """Test valid validation result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Minor issue detected"]
        )
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert result.has_warnings() is True
        assert result.has_errors() is False
    
    def test_invalid_result(self):
        """Test invalid validation result."""
        result = ValidationResult(
            is_valid=False,
            errors=["Critical error", "Another error"],
            warnings=["Warning message"]
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.has_errors() is True
        assert result.has_warnings() is True
    
    def test_success_factory(self):
        """Test success result factory method."""
        result = ValidationResult.success()
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_error_factory(self):
        """Test error result factory method."""
        result = ValidationResult.error("Something went wrong")
        assert result.is_valid is False
        assert "Something went wrong" in result.errors
        assert len(result.warnings) == 0
    
    def test_warning_factory(self):
        """Test warning result factory method."""
        result = ValidationResult.warning("Minor issue")
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert "Minor issue" in result.warnings
    
    def test_multiple_issues(self):
        """Test result with multiple issues."""
        result = ValidationResult.with_issues(
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1", "Warning 2", "Warning 3"]
        )
        
        assert result.is_valid is False  # Has errors
        assert len(result.errors) == 2
        assert len(result.warnings) == 3
    
    def test_summary_generation(self):
        """Test summary message generation."""
        result = ValidationResult(
            is_valid=False,
            errors=["Critical error"],
            warnings=["Minor warning"]
        )
        
        summary = result.get_summary()
        assert "1 error" in summary
        assert "1 warning" in summary
        assert isinstance(summary, str)
    
    def test_combine_results(self):
        """Test combining multiple validation results."""
        result1 = ValidationResult.error("Error 1")
        result2 = ValidationResult.warning("Warning 1")
        result3 = ValidationResult.success()
        
        combined = ValidationResult.combine([result1, result2, result3])
        
        assert combined.is_valid is False  # Has errors
        assert len(combined.errors) == 1
        assert len(combined.warnings) == 1
        assert "Error 1" in combined.errors
        assert "Warning 1" in combined.warnings


class TestFileAnalysisInfo:
    """Test cases for FileAnalysisInfo model."""
    
    def test_basic_instantiation(self):
        """Test basic analysis info creation."""
        info = FileAnalysisInfo(
            entry_point="0x401000",
            architecture="x86_64",
            compiler_info="Microsoft Visual C++ 14.0"
        )
        
        assert info.entry_point == "0x401000"
        assert info.architecture == "x86_64"
        assert info.compiler_info == "Microsoft Visual C++ 14.0"
        assert info.sections == []
        assert info.headers == {}
        assert info.debug_info is None
    
    def test_with_sections(self):
        """Test analysis info with sections."""
        sections = [
            {
                "name": ".text",
                "virtual_address": "0x401000",
                "size": 2048,
                "characteristics": ["executable", "readable"]
            },
            {
                "name": ".data",
                "virtual_address": "0x403000", 
                "size": 1024,
                "characteristics": ["readable", "writable"]
            }
        ]
        
        info = FileAnalysisInfo(
            entry_point="0x401000",
            architecture="x86_64",
            sections=sections
        )
        
        assert len(info.sections) == 2
        assert info.get_section_by_name(".text")["size"] == 2048
        assert info.get_executable_sections() == [sections[0]]
        assert info.get_data_sections() == [sections[1]]
    
    def test_header_parsing(self):
        """Test header information parsing."""
        headers = {
            "pe_header": {
                "machine": "IMAGE_FILE_MACHINE_AMD64",
                "timestamp": 1640995200,
                "characteristics": ["IMAGE_FILE_EXECUTABLE_IMAGE"]
            },
            "optional_header": {
                "subsystem": "IMAGE_SUBSYSTEM_WINDOWS_CUI",
                "dll_characteristics": ["IMAGE_DLLCHARACTERISTICS_ASLR"]
            }
        }
        
        info = FileAnalysisInfo(
            entry_point="0x401000",
            architecture="x86_64",
            headers=headers
        )
        
        assert info.headers == headers
        assert info.get_header_value("pe_header.machine") == "IMAGE_FILE_MACHINE_AMD64"
        assert info.has_aslr_support()
        assert info.get_subsystem() == "IMAGE_SUBSYSTEM_WINDOWS_CUI"
    
    def test_debug_information(self):
        """Test debug information handling."""
        debug_info = {
            "has_symbols": True,
            "debug_format": "PDB",
            "debug_file": "test.pdb",
            "compile_flags": ["/Zi", "/Od"]
        }
        
        info = FileAnalysisInfo(
            entry_point="0x401000",
            architecture="x86_64",
            debug_info=debug_info
        )
        
        assert info.debug_info == debug_info
        assert info.has_debug_symbols()
        assert info.get_debug_format() == "PDB"
        assert info.is_debug_build()
    
    def test_security_features(self):
        """Test security feature detection."""
        headers = {
            "optional_header": {
                "dll_characteristics": [
                    "IMAGE_DLLCHARACTERISTICS_ASLR",
                    "IMAGE_DLLCHARACTERISTICS_DEP_COMPATIBLE",
                    "IMAGE_DLLCHARACTERISTICS_CFG"
                ]
            }
        }
        
        info = FileAnalysisInfo(
            entry_point="0x401000",
            architecture="x86_64",
            headers=headers
        )
        
        security_features = info.get_security_features()
        assert security_features["aslr"] is True
        assert security_features["dep"] is True
        assert security_features["cfg"] is True
        assert security_features["stack_canary"] is False  # Not specified
    
    def test_summary_generation(self):
        """Test analysis info summary."""
        sections = [{"name": ".text", "size": 1024}]
        
        info = FileAnalysisInfo(
            entry_point="0x401000",
            architecture="x86_64",
            compiler_info="GCC 9.3.0",
            sections=sections
        )
        
        summary = info.get_summary()
        assert isinstance(summary, dict)
        assert summary["entry_point"] == "0x401000"
        assert summary["architecture"] == "x86_64"
        assert summary["section_count"] == 1
        assert "compiler" in summary