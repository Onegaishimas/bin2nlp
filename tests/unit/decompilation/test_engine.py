"""
Unit tests for the simplified binary decompilation engine.

Tests the real DecompilationEngine with mocked radare2 responses to verify
the actual decompilation logic, data processing, and error handling.
"""

import pytest
import tempfile
import os
import asyncio
import hashlib
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any
from pathlib import Path

from src.decompilation.engine import (
    DecompilationEngine,
    DecompilationConfig,
    DecompilationEngineException,
    create_decompilation_engine,
    decompile_file
)
from src.models.analysis.basic_results import (
    BasicDecompilationResult,
    DecompilationMetadata,
    BasicFunctionInfo,
    BasicImportInfo,
    BasicStringInfo
)
from src.models.shared.enums import FileFormat, Platform
from src.analysis.engines.r2_integration import R2Session


class TestDecompilationConfig:
    """Test DecompilationConfig validation."""
    
    def test_config_defaults(self):
        """Test default configuration values."""
        config = DecompilationConfig()
        
        assert config.max_file_size_mb == 100
        assert config.timeout_seconds == 300
        assert config.r2_analysis_level == "aa"
        assert config.extract_functions is True
        assert config.extract_strings is True
        assert config.extract_imports is True
        assert config.include_assembly_code is True
        assert config.max_functions is None
        assert config.max_strings is None
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = DecompilationConfig(
            max_file_size_mb=50,
            timeout_seconds=600,
            r2_analysis_level="aaa",
            extract_functions=True,
            extract_strings=False,
            max_functions=100
        )
        assert config.max_file_size_mb == 50
        assert config.timeout_seconds == 600
        assert config.r2_analysis_level == "aaa"
        assert config.extract_functions is True
        assert config.extract_strings is False
        assert config.max_functions == 100
        
        # Test constraints
        with pytest.raises(ValueError):
            DecompilationConfig(max_file_size_mb=0)  # Should be >= 1
        
        with pytest.raises(ValueError):
            DecompilationConfig(timeout_seconds=20)  # Should be >= 30


class TestDecompilationEngine:
    """Test DecompilationEngine functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test decompilation configuration."""
        return DecompilationConfig(
            max_file_size_mb=10,
            timeout_seconds=120,
            r2_analysis_level="aa",
            max_functions=50,
            max_strings=100
        )
    
    @pytest.fixture
    def engine(self, config):
        """Create DecompilationEngine instance."""
        return DecompilationEngine(config)
    
    @pytest.fixture
    def test_file_path(self):
        """Create temporary test file."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            # Create a mock PE file with proper header
            pe_header = b'MZ' + b'\x00' * 58 + b'\x80\x00\x00\x00'  # DOS header
            pe_header += b'\x00' * (0x80 - len(pe_header))  # Padding to PE header offset
            pe_header += b'PE\x00\x00'  # PE signature
            pe_header += b'\x00' * 1000  # Additional content
            tmp_file.write(pe_header)
            tmp_file.flush()
            yield tmp_file.name
        
        try:
            os.unlink(tmp_file.name)
        except FileNotFoundError:
            pass
    
    def create_mock_r2_session(self, functions=None, imports=None, strings=None):
        """Helper to create mock R2Session with realistic data."""
        mock_session = AsyncMock(spec=R2Session)
        
        # Default realistic function data
        if functions is None:
            functions = [
                {"name": "main", "offset": 0x401000, "size": 128},
                {"name": "sub_401080", "offset": 0x401080, "size": 64}
            ]
        
        # Default realistic import data  
        if imports is None:
            imports = [
                {"name": "CreateFileA", "libname": "kernel32.dll", "plt": 0x402000},
                {"name": "MessageBoxA", "libname": "user32.dll", "plt": 0x402010}
            ]
            
        # Default realistic string data
        if strings is None:
            strings = [
                {"string": "Hello World", "vaddr": 0x403000, "size": 11, "section": ".rdata", "type": "ascii"},
                {"string": "Error", "vaddr": 0x403010, "size": 5, "section": ".rdata", "type": "ascii"}
            ]
        
        mock_session.extract_functions.return_value = functions
        mock_session.get_imports.return_value = imports  
        mock_session.get_strings.return_value = strings
        mock_session.get_function_assembly.return_value = (
            "0x00401000      push    rbp\n"
            "0x00401001      mov     rbp, rsp\n"
            "0x00401004      call    sub_401080\n"
            "0x00401009      pop     rbp\n"
            "0x0040100a      ret\n"
        )
        
        return mock_session
    
    @pytest.fixture
    def mock_import_data(self):
        """Mock import data."""
        return [
            {
                "libname": "kernel32.dll",
                "name": "CreateFileA",
                "plt": 0x402000,
                "ordinal": None
            },
            {
                "libname": "user32.dll", 
                "name": "MessageBoxA",
                "plt": 0x402010,
                "ordinal": None
            }
        ]
    
    @pytest.fixture
    def mock_string_data(self):
        """Mock string data."""
        return [
            {
                "string": "Hello, World!",
                "vaddr": 0x403000,
                "size": 13,
                "section": ".rdata",
                "type": "ascii"
            },
            {
                "string": "Error: File not found",
                "vaddr": 0x403010,
                "size": 21,
                "section": ".rdata", 
                "type": "ascii"
            }
        ]
    
    def test_engine_initialization(self, engine):
        """Test engine initialization."""
        assert engine.config is not None
        assert engine.config.max_file_size_mb == 10
        assert engine.config.timeout_seconds == 120
        assert engine.config.r2_analysis_level == "aa"
    
    def test_engine_initialization_default_config(self):
        """Test engine initialization with default config."""
        engine = DecompilationEngine()
        assert engine.config is not None
        assert engine.config.max_file_size_mb == 100
        assert engine.config.timeout_seconds == 300
    
    @pytest.mark.asyncio
    async def test_decompile_binary_success(self, engine, test_file_path):
        """Test successful binary decompilation using real engine logic."""
        # Mock only the R2Session to return realistic data
        mock_r2_session = self.create_mock_r2_session()
        
        with patch('src.decompilation.engine.R2Session') as mock_r2_class:
            mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
            
            # Use the REAL decompilation engine
            result = await engine.decompile_binary(test_file_path)
            
            # Verify the engine processed the data correctly
            assert isinstance(result, BasicDecompilationResult)
            assert result.success is True
            assert result.metadata.file_format == FileFormat.PE
            assert result.metadata.platform == Platform.WINDOWS
            assert len(result.functions) == 2
            assert len(result.imports) == 2  
            assert len(result.strings) == 2
            assert result.duration_seconds > 0
            
            # Verify the engine correctly processed function data
            main_func = next((f for f in result.functions if f.name == "main"), None)
            assert main_func is not None
            assert main_func.address == "0x00401000"
            assert main_func.size == 128
            assert main_func.assembly_code is not None  # Should have assembly
            
            # Verify the engine correctly processed import data
            kernel32_import = next((i for i in result.imports if i.library_name == "kernel32.dll"), None)
            assert kernel32_import is not None
            assert kernel32_import.function_name == "CreateFileA"
            assert kernel32_import.address == "0x00402000"
            
            # Verify the engine correctly processed string data
            hello_string = next((s for s in result.strings if "Hello" in s.value), None)
            assert hello_string is not None
            assert hello_string.address == "0x00403000"
            assert hello_string.encoding == "ascii"
    
    @pytest.mark.asyncio
    async def test_decompile_binary_file_not_found(self, engine):
        """Test decompilation with non-existent file."""
        result = await engine.decompile_binary("/nonexistent/file.exe")
        
        assert isinstance(result, BasicDecompilationResult)
        assert result.success is False
        assert len(result.errors) > 0
        assert "File not found" in result.errors[0]
    
    @pytest.mark.asyncio
    async def test_decompile_binary_empty_file(self, engine):
        """Test decompilation with empty file."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            # Create empty file
            tmp_file.write(b'')
            tmp_file.flush()
            
            try:
                result = await engine.decompile_binary(tmp_file.name)
                
                assert isinstance(result, BasicDecompilationResult)
                assert result.success is False
                assert len(result.errors) > 0
                assert "empty" in result.errors[0].lower()
                
            finally:
                os.unlink(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_decompile_binary_file_too_large(self, engine):
        """Test decompilation with file that exceeds size limit."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            # Create file larger than limit (config has 10MB limit)
            large_data = b'A' * (11 * 1024 * 1024)  # 11MB
            tmp_file.write(large_data)
            tmp_file.flush()
            
            try:
                result = await engine.decompile_binary(tmp_file.name)
                
                assert isinstance(result, BasicDecompilationResult)
                assert result.success is False
                assert len(result.errors) > 0
                assert "too large" in result.errors[0].lower()
                
            finally:
                os.unlink(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_decompile_binary_r2_failure(self, engine, test_file_path):
        """Test decompilation when R2Session fails."""
        with patch('src.decompilation.engine.R2Session') as mock_r2_class:
            # Make R2Session raise an exception
            mock_r2_class.side_effect = Exception("Radare2 initialization failed")
            
            result = await engine.decompile_binary(test_file_path)
            
            assert isinstance(result, BasicDecompilationResult)
            # Should still have metadata even if R2 fails
            assert result.metadata.file_format == FileFormat.PE
            assert result.metadata.platform == Platform.WINDOWS
            # But should have empty data
            assert len(result.functions) == 0
            assert len(result.imports) == 0
            assert len(result.strings) == 0
    
    @pytest.mark.asyncio
    async def test_extract_functions_with_limits(self, engine, test_file_path, mock_r2_session):
        """Test function extraction with max_functions limit."""
        # Set max_functions to 1
        engine.config.max_functions = 1
        
        # Mock R2Session to return 3 functions
        mock_r2_session.extract_functions.return_value = [
            {"name": "func1", "offset": 0x1000, "size": 100},
            {"name": "func2", "offset": 0x2000, "size": 100},
            {"name": "func3", "offset": 0x3000, "size": 100}
        ]
        mock_r2_session.get_imports.return_value = []
        mock_r2_session.get_strings.return_value = []
        
        with patch('src.decompilation.engine.R2Session') as mock_r2_class:
            mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
            
            result = await engine.decompile_binary(test_file_path)
            
            # Should only have 1 function due to limit
            assert len(result.functions) == 1
            assert result.functions[0].name == "func1"
    
    @pytest.mark.asyncio
    async def test_extract_strings_with_limits(self, engine, test_file_path, mock_r2_session, mock_string_data):
        """Test string extraction with max_strings limit."""
        # Set max_strings to 1
        engine.config.max_strings = 1
        
        mock_r2_session.extract_functions.return_value = []
        mock_r2_session.get_imports.return_value = []
        mock_r2_session.get_strings.return_value = mock_string_data  # Returns 2 strings
        
        with patch('src.decompilation.engine.R2Session') as mock_r2_class:
            mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
            
            result = await engine.decompile_binary(test_file_path)
            
            # Should only have 1 string due to limit
            assert len(result.strings) == 1
            assert result.strings[0].value == "Hello, World!"
    
    @pytest.mark.asyncio
    async def test_disable_extraction_features(self, engine, test_file_path, mock_r2_session, mock_import_data, mock_string_data):
        """Test disabling specific extraction features."""
        # Disable string and import extraction
        engine.config.extract_strings = False
        engine.config.extract_imports = False
        
        mock_r2_session.extract_functions.return_value = [{"name": "main", "offset": 0x1000, "size": 100}]
        mock_r2_session.get_imports.return_value = []
        mock_r2_session.get_strings.return_value = []
        
        with patch('src.decompilation.engine.R2Session') as mock_r2_class:
            mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
            
            result = await engine.decompile_binary(test_file_path)
            
            # Should have functions but no strings or imports
            assert len(result.functions) == 1
            assert len(result.strings) == 0
            assert len(result.imports) == 0
    
    def test_detect_file_format_pe(self, engine):
        """Test PE file format detection."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            # Write PE header
            tmp_file.write(b'MZ' + b'\x00' * 100)
            tmp_file.flush()
            
            try:
                format_detected = engine._detect_file_format(tmp_file.name)
                assert format_detected == FileFormat.PE
            finally:
                os.unlink(tmp_file.name)
    
    def test_detect_file_format_elf(self, engine):
        """Test ELF file format detection."""
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as tmp_file:
            # Write ELF header
            tmp_file.write(b'\x7fELF' + b'\x00' * 100)
            tmp_file.flush()
            
            try:
                format_detected = engine._detect_file_format(tmp_file.name)
                assert format_detected == FileFormat.ELF
            finally:
                os.unlink(tmp_file.name)
    
    def test_detect_file_format_unknown(self, engine):
        """Test unknown file format detection."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
            # Write unknown header
            tmp_file.write(b'UNKNOWN' + b'\x00' * 100)
            tmp_file.flush()
            
            try:
                format_detected = engine._detect_file_format(tmp_file.name)
                assert format_detected == FileFormat.UNKNOWN
            finally:
                os.unlink(tmp_file.name)
    
    def test_detect_platform_mapping(self, engine):
        """Test platform detection based on file format."""
        assert engine._detect_platform(FileFormat.PE) == Platform.WINDOWS
        assert engine._detect_platform(FileFormat.ELF) == Platform.LINUX
        assert engine._detect_platform(FileFormat.MACHO) == Platform.MACOS
        assert engine._detect_platform(FileFormat.JAVA_CLASS) == Platform.JAVA
        assert engine._detect_platform(FileFormat.UNKNOWN) == Platform.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_create_metadata(self, engine, test_file_path):
        """Test metadata creation."""
        metadata = await engine._create_metadata(test_file_path)
        
        assert isinstance(metadata, DecompilationMetadata)
        assert metadata.file_hash.startswith("sha256:")
        assert metadata.file_size > 0
        assert metadata.file_format == FileFormat.PE
        assert metadata.platform == Platform.WINDOWS
        assert metadata.decompilation_tool == "radare2"
    
    def test_generate_id(self, engine):
        """Test ID generation."""
        id1 = engine._generate_id()
        id2 = engine._generate_id()
        
        assert isinstance(id1, str)
        assert isinstance(id2, str)
        assert id1 != id2  # Should be unique
        assert len(id1) == 36  # UUID4 length


class TestFactoryFunctions:
    """Test factory and convenience functions."""
    
    def test_create_decompilation_engine_default(self):
        """Test creating engine with default config."""
        engine = create_decompilation_engine()
        
        assert isinstance(engine, DecompilationEngine)
        assert engine.config.max_file_size_mb == 100
        assert engine.config.timeout_seconds == 300
    
    def test_create_decompilation_engine_custom_config(self):
        """Test creating engine with custom config."""
        config = DecompilationConfig(
            max_file_size_mb=50,
            timeout_seconds=200
        )
        engine = create_decompilation_engine(config)
        
        assert isinstance(engine, DecompilationEngine)
        assert engine.config.max_file_size_mb == 50
        assert engine.config.timeout_seconds == 200
    
    @pytest.mark.asyncio
    async def test_decompile_file_convenience(self):
        """Test convenience function for single file decompilation."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            # Create mock PE file
            tmp_file.write(b'MZ' + b'\x00' * 100)
            tmp_file.flush()
            
            try:
                with patch('src.decompilation.engine.R2Session') as mock_r2_class:
                    mock_r2_session = AsyncMock(spec=R2Session)
                    mock_r2_session.extract_functions.return_value = []
                    mock_r2_session.get_imports.return_value = []
                    mock_r2_session.get_strings.return_value = []
                    mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
                    
                    result = await decompile_file(tmp_file.name)
                    
                    assert isinstance(result, BasicDecompilationResult)
                    assert result.metadata.file_format == FileFormat.PE
                    
            finally:
                os.unlink(tmp_file.name)


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and comprehensive error handling."""
    
    @pytest.fixture
    def engine(self):
        """Create engine with default config."""
        return DecompilationEngine()
    
    @pytest.mark.asyncio
    async def test_concurrent_decompilations(self, engine):
        """Test concurrent decompilation operations."""
        # Create multiple test files
        test_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix=f'_test_{i}.exe', delete=False) as tmp_file:
                tmp_file.write(b'MZ' + bytes([i]) * 100)
                tmp_file.flush()
                test_files.append(tmp_file.name)
        
        try:
            with patch('src.decompilation.engine.R2Session') as mock_r2_class:
                mock_r2_session = AsyncMock(spec=R2Session)
                mock_r2_session.extract_functions.return_value = []
                mock_r2_session.get_imports.return_value = []
                mock_r2_session.get_strings.return_value = []
                mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
                
                # Run concurrent decompilations
                tasks = [engine.decompile_binary(file_path) for file_path in test_files]
                results = await asyncio.gather(*tasks)
                
                assert len(results) == 3
                for result in results:
                    assert isinstance(result, BasicDecompilationResult)
                    assert result.metadata.file_format == FileFormat.PE
        
        finally:
            # Cleanup test files
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except FileNotFoundError:
                    pass
    
    @pytest.mark.asyncio
    async def test_partial_r2_extraction_failures(self, engine, test_file_path):
        """Test handling of partial R2 extraction failures."""
        with patch('src.decompilation.engine.R2Session') as mock_r2_class:
            mock_r2_session = AsyncMock(spec=R2Session)
            
            def mock_cmd_json_side_effect(cmd):
                if cmd == "aflj":  # Functions work
                    return [{"name": "main", "offset": 0x1000, "size": 100}]
                elif cmd == "iij":  # Imports fail
                    raise Exception("Import extraction failed")
                elif cmd == "izj":  # Strings work
                    return [{"string": "test", "vaddr": 0x1000, "size": 4, "section": ".data", "type": "ascii"}]
                return []
            
            mock_r2_session.cmd_json.side_effect = mock_cmd_json_side_effect
            mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
            
            result = await engine.decompile_binary(test_file_path)
            
            # Should have partial results
            assert len(result.functions) == 1
            assert len(result.imports) == 0  # Failed
            assert len(result.strings) == 1
            # Should still be marked as successful since file was processed
            assert result.success is True or len(result.errors) == 0
    
    @pytest.mark.asyncio
    async def test_assembly_code_extraction_failure(self, engine, test_file_path):
        """Test handling of assembly code extraction failures."""
        with patch('src.decompilation.engine.R2Session') as mock_r2_class:
            mock_r2_session = AsyncMock(spec=R2Session)
            mock_r2_session.cmd_json.return_value = [
                {"name": "main", "offset": 0x1000, "size": 100}
            ]
            # Assembly code extraction fails
            mock_r2_session.cmd.side_effect = Exception("Assembly extraction failed")
            mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
            
            result = await engine.decompile_binary(test_file_path)
            
            # Should have function but no assembly code
            assert len(result.functions) == 1
            assert result.functions[0].assembly_code is None
    
    @pytest.mark.asyncio
    async def test_malformed_r2_response_handling(self, engine, test_file_path):
        """Test handling of malformed radare2 responses."""
        with patch('src.decompilation.engine.R2Session') as mock_r2_class:
            mock_r2_session = AsyncMock(spec=R2Session)
            
            def mock_cmd_json_side_effect(cmd):
                if cmd == "aflj":  # Return malformed function data
                    return [
                        {"name": "main"},  # Missing offset and size
                        {"offset": 0x1000, "size": 100},  # Missing name
                        {"name": "valid_func", "offset": 0x2000, "size": 50}  # Valid
                    ]
                return []
            
            mock_r2_session.cmd_json.side_effect = mock_cmd_json_side_effect
            mock_r2_class.return_value.__aenter__.return_value = mock_r2_session
            
            result = await engine.decompile_binary(test_file_path)
            
            # Should handle malformed data gracefully and only return valid function
            assert len(result.functions) >= 1
            valid_func = next((f for f in result.functions if f.name == "valid_func"), None)
            assert valid_func is not None
            assert valid_func.size == 50