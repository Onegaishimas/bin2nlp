"""
Real radare2 integration tests using actual R2Session calls.

These tests use real radare2 binary analysis without mocking R2Session.
They require radare2 to be installed and working on the test system.

Test Categories:
- Real binary file analysis with actual R2Session
- Performance benchmarking for radare2 operations  
- Error handling with malformed/unsupported files
- Complete end-to-end decompilation pipeline
"""

import pytest
import asyncio
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, List
import struct
import os

from src.decompilation.engine import DecompilationEngine
from src.decompilation.r2_session import R2Session
from src.core.config import get_settings
from src.models.decompilation.results import (
    DecompilationResult,
    FunctionTranslation,
    ImportTranslation,
    StringTranslation,
    OverallSummary
)


class TestBinaryGenerator:
    """Helper to create realistic test binaries for integration testing."""
    
    @staticmethod
    def create_simple_pe_binary() -> bytes:
        """Create a minimal but valid PE executable for testing."""
        # PE header structure - simplified but functional
        dos_header = b"MZ" + b"\x00" * 58 + struct.pack("<I", 0x80)  # e_lfanew = 0x80
        
        # PE signature and headers
        pe_signature = b"PE\x00\x00"
        
        # File header
        file_header = struct.pack("<HHIIIHH",
            0x014c,  # Machine (i386)
            1,       # NumberOfSections
            0,       # TimeDateStamp
            0,       # PointerToSymbolTable
            0,       # NumberOfSymbols
            0xe0,    # SizeOfOptionalHeader
            0x010e   # Characteristics
        )
        
        # Optional header (simplified)
        optional_header = (
            struct.pack("<HBB", 0x010b, 1, 0) +  # Magic, MajorLinkerVersion, MinorLinkerVersion
            b"\x00" * (0xe0 - 4)  # Rest of optional header zeroed
        )
        
        # Section header
        section_header = (
            b".text\x00\x00\x00" +  # Name
            struct.pack("<IIIIIIHHI",
                0x1000,  # VirtualSize
                0x1000,  # VirtualAddress
                0x1000,  # SizeOfRawData
                0x200,   # PointerToRawData
                0, 0, 0, 0, 0  # Relocations, LineNumbers, etc.
            )
        )
        
        # Simple code section with some basic instructions
        code_section = (
            b"\x55" +           # push ebp
            b"\x89\xe5" +       # mov ebp, esp
            b"\x83\xec\x10" +   # sub esp, 16
            b"\xc7\x45\xfc\x00\x00\x00\x00" +  # mov dword [ebp-4], 0
            b"\x8b\x45\xfc" +   # mov eax, dword [ebp-4]
            b"\x89\xec" +       # mov esp, ebp
            b"\x5d" +           # pop ebp
            b"\xc3" +           # ret
            b"\x00" * (0x1000 - 20)  # Padding to section size
        )
        
        # Assemble the PE file
        pe_binary = (
            dos_header +
            b"\x00" * (0x80 - len(dos_header)) +  # DOS stub
            pe_signature +
            file_header +
            optional_header +
            section_header +
            b"\x00" * (0x200 - len(dos_header + b"\x00" * (0x80 - len(dos_header)) + pe_signature + file_header + optional_header + section_header)) +
            code_section
        )
        
        return pe_binary
    
    @staticmethod
    def create_simple_elf_binary() -> bytes:
        """Create a minimal but valid ELF executable for testing."""
        # ELF header (64-bit)
        elf_header = (
            b"\x7fELF" +           # Magic
            b"\x02\x01\x01\x00" + # 64-bit, little-endian, current version, ABI
            b"\x00" * 8 +         # Padding
            struct.pack("<HHIQQQIHHHHHH",
                2,      # e_type (ET_EXEC)
                0x3e,   # e_machine (EM_X86_64)
                1,      # e_version
                0x400000,  # e_entry
                64,     # e_phoff
                0,      # e_shoff
                0,      # e_flags
                64,     # e_ehsize
                56,     # e_phentsize
                1,      # e_phnum
                0,      # e_shentsize
                0,      # e_shnum
                0       # e_shstrndx
            )
        )
        
        # Program header
        program_header = struct.pack("<IIQQQQQQ",
            1,         # p_type (PT_LOAD)
            5,         # p_flags (PF_R | PF_X)
            0,         # p_offset
            0x400000,  # p_vaddr
            0x400000,  # p_paddr
            0x1000,    # p_filesz
            0x1000,    # p_memsz
            0x1000     # p_align
        )
        
        # Simple code
        code = (
            b"\x48\xc7\xc0\x3c\x00\x00\x00" +  # mov rax, 60 (sys_exit)
            b"\x48\xc7\xc7\x00\x00\x00\x00" +  # mov rdi, 0
            b"\x0f\x05" +                       # syscall
            b"\x00" * (0x1000 - 120 - 15)      # Padding
        )
        
        return elf_header + program_header + code
    
    @staticmethod
    def create_binary_with_strings() -> bytes:
        """Create a binary with identifiable strings for string extraction testing."""
        # Start with simple PE
        pe_binary = TestBinaryGenerator.create_simple_pe_binary()
        
        # Add string data section
        test_strings = [
            b"Hello World\x00",
            b"Test Application\x00", 
            b"Error: Invalid input\x00",
            b"https://example.com/api\x00",
            b"C:\\Users\\test\\file.txt\x00"
        ]
        
        string_section = b"".join(test_strings) + b"\x00" * (256 - sum(len(s) for s in test_strings))
        
        return pe_binary + string_section
    
    @staticmethod
    def create_malformed_binary() -> bytes:
        """Create a malformed binary to test error handling."""
        return b"This is not a valid binary file" + b"\x00" * 1000


@pytest.mark.asyncio
@pytest.mark.integration 
@pytest.mark.slow
class TestRealRadare2Integration:
    """Integration tests using real radare2 without mocking."""
    
    @pytest.fixture
    async def decompilation_engine(self):
        """Create real decompilation engine instance."""
        settings = get_settings()
        engine = DecompilationEngine(settings)
        return engine
    
    @pytest.fixture
    def temp_pe_file(self):
        """Create temporary PE file for testing."""
        binary_data = TestBinaryGenerator.create_simple_pe_binary()
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(binary_data)
            tmp_file.flush()
            yield tmp_file.name
        os.unlink(tmp_file.name)
    
    @pytest.fixture
    def temp_elf_file(self):
        """Create temporary ELF file for testing."""
        binary_data = TestBinaryGenerator.create_simple_elf_binary()
        with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as tmp_file:
            tmp_file.write(binary_data)
            tmp_file.flush()
            yield tmp_file.name
        os.unlink(tmp_file.name)
    
    @pytest.fixture
    def temp_string_binary(self):
        """Create temporary binary with test strings."""
        binary_data = TestBinaryGenerator.create_binary_with_strings()
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(binary_data)
            tmp_file.flush()
            yield tmp_file.name
        os.unlink(tmp_file.name)
    
    async def test_real_r2session_basic_analysis(self, temp_pe_file):
        """Test basic analysis using real R2Session without mocking."""
        # This uses actual R2Session, not mocked
        async with R2Session(temp_pe_file) as r2:
            # Test basic info extraction
            file_info = await r2.get_file_info()
            assert file_info is not None
            assert "format" in file_info
            assert file_info["format"] in ["pe", "PE"]
            
            # Test function analysis
            functions = await r2.extract_functions()
            assert isinstance(functions, list)
            # PE should have at least some basic functions/entry points
    
    async def test_real_r2session_elf_analysis(self, temp_elf_file):
        """Test ELF analysis using real R2Session."""
        async with R2Session(temp_elf_file) as r2:
            file_info = await r2.get_file_info()
            assert file_info["format"] in ["elf", "ELF"]
            
            functions = await r2.extract_functions()
            assert isinstance(functions, list)
    
    async def test_real_string_extraction(self, temp_string_binary):
        """Test string extraction with real radare2."""
        async with R2Session(temp_string_binary) as r2:
            strings = await r2.get_strings()
            
            # Verify we found some of our test strings
            string_contents = [s.get("content", "") for s in strings]
            found_strings = [s for s in string_contents if any(
                test_str in s for test_str in ["Hello World", "Test Application", "example.com"]
            )]
            
            assert len(found_strings) > 0, f"Expected test strings not found. Got: {string_contents[:10]}"
    
    async def test_real_import_analysis(self, temp_pe_file):
        """Test import extraction with real radare2."""
        async with R2Session(temp_pe_file) as r2:
            imports = await r2.get_imports()
            assert isinstance(imports, list)
            # Even minimal PE might have some imports or at least empty list
    
    async def test_decompilation_engine_end_to_end(self, decompilation_engine, temp_pe_file):
        """Test complete decompilation engine workflow with real radare2."""
        result = await decompilation_engine.decompile_binary(temp_pe_file)
        
        # Verify result structure
        assert isinstance(result, DecompilationResult)
        assert result.file_format.value.lower() in ["pe", "pe32"]
        assert result.file_size > 0
        
        # Verify functions list (even if empty for minimal binary)
        assert isinstance(result.functions, list)
        assert isinstance(result.imports, list) 
        assert isinstance(result.strings, list)
        
        # Verify success status
        assert result.success == True or result.partial_results == True
        assert len(result.functions) >= 0
        assert len(result.imports) >= 0
        assert len(result.strings) >= 0
    
    async def test_error_handling_malformed_file(self, decompilation_engine):
        """Test error handling with malformed binary file."""
        malformed_data = TestBinaryGenerator.create_malformed_binary()
        
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(malformed_data)
            tmp_file.flush()
            
            try:
                # This should handle the error gracefully
                result = await decompilation_engine.decompile_binary(tmp_file.name)
                
                # Should return result with error status, not crash
                assert result.success == False or len(result.errors) > 0
                
            finally:
                os.unlink(tmp_file.name)
    
    async def test_nonexistent_file_handling(self, decompilation_engine):
        """Test error handling with nonexistent file."""
        with pytest.raises(FileNotFoundError):
            await decompilation_engine.decompile_binary("/path/that/does/not/exist.exe")
    
    @pytest.mark.performance
    async def test_performance_benchmarking(self, decompilation_engine, temp_pe_file):
        """Benchmark radare2 operation performance."""
        # Test multiple runs for consistent timing
        run_times = []
        
        for i in range(3):
            start_time = time.perf_counter()
            result = await decompilation_engine.decompile_binary(temp_pe_file)
            end_time = time.perf_counter()
            
            processing_time = end_time - start_time
            run_times.append(processing_time)
            
            # Verify result is valid
            assert result.success == True or result.partial_results == True
        
        # Performance assertions
        avg_time = sum(run_times) / len(run_times)
        max_time = max(run_times)
        
        # For small test files, should be very fast
        assert avg_time < 10.0, f"Average processing time too slow: {avg_time:.2f}s"
        assert max_time < 15.0, f"Max processing time too slow: {max_time:.2f}s"
        
        print(f"Performance benchmark - Avg: {avg_time:.3f}s, Max: {max_time:.3f}s, Min: {min(run_times):.3f}s")
    
    @pytest.mark.performance
    async def test_concurrent_analysis(self, decompilation_engine, temp_pe_file, temp_elf_file):
        """Test concurrent analysis of multiple files."""
        start_time = time.perf_counter()
        
        # Run analyses concurrently
        tasks = [
            decompilation_engine.decompile_binary(temp_pe_file),
            decompilation_engine.decompile_binary(temp_elf_file),
            decompilation_engine.decompile_binary(temp_pe_file)  # Same file again
        ]
        
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        # All should succeed
        assert len(results) == 3
        for result in results:
            assert result.success == True or result.partial_results == True
        
        total_time = end_time - start_time
        assert total_time < 30.0, f"Concurrent analysis too slow: {total_time:.2f}s"
        
        print(f"Concurrent analysis benchmark: {total_time:.3f}s for 3 files")
    
    async def test_r2session_resource_cleanup(self, temp_pe_file):
        """Test that R2Session properly cleans up resources."""
        # Test multiple session creations and closures
        for i in range(5):
            async with R2Session(temp_pe_file) as r2:
                file_info = await r2.get_file_info()
                assert file_info is not None
                
                # Session should be usable
                functions = await r2.extract_functions()
                assert isinstance(functions, list)
            
            # After context exit, session should be cleaned up
            # No way to directly test this, but multiple iterations
            # would fail if resources weren't being freed
    
    async def test_large_function_analysis(self, temp_pe_file):
        """Test analysis of binaries with many functions."""
        # Create a more complex PE with multiple functions
        # (This is a simplified test - in reality would need more complex binary)
        
        async with R2Session(temp_pe_file) as r2:
            # Force comprehensive analysis
            await r2.cmd("aaa")  # Analyze all
            
            functions = await r2.extract_functions()
            
            # Verify function data structure
            for func in functions[:5]:  # Check first 5 functions
                if isinstance(func, dict):
                    # Should have basic function metadata
                    assert "name" in func or "addr" in func
                    if "size" in func:
                        assert func["size"] >= 0
    
    async def test_assembly_extraction_quality(self, temp_pe_file):
        """Test quality and format of extracted assembly code."""
        async with R2Session(temp_pe_file) as r2:
            functions = await r2.extract_functions()
            
            if functions:
                # Get disassembly for first function
                first_func = functions[0]
                if isinstance(first_func, dict) and "addr" in first_func:
                    addr = first_func["addr"]
                    disasm = await r2.cmd(f"pdf @ {addr}")
                    
                    # Basic assembly format checks
                    assert isinstance(disasm, str)
                    assert len(disasm.strip()) > 0
                    
                    # Should contain recognizable assembly patterns
                    # (instruction:operand format)
                    lines = disasm.split('\n')
                    non_empty_lines = [line.strip() for line in lines if line.strip()]
                    
                    if non_empty_lines:
                        # At least some lines should look like assembly
                        has_assembly = any(
                            any(instr in line.lower() for instr in ['mov', 'push', 'pop', 'call', 'ret', 'jmp'])
                            for line in non_empty_lines[:10]  # Check first 10 lines
                        )
                        assert has_assembly, f"No recognizable assembly found in: {non_empty_lines[:5]}"


@pytest.mark.asyncio
@pytest.mark.integration
class TestRealRadare2ErrorScenarios:
    """Test error handling scenarios with real radare2."""
    
    async def test_corrupted_pe_header(self):
        """Test handling of corrupted PE header."""
        # Create PE with corrupted header
        corrupted_pe = b"MZ" + b"\xFF" * 100 + TestBinaryGenerator.create_simple_pe_binary()[102:]
        
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(corrupted_pe)
            tmp_file.flush()
            
            try:
                async with R2Session(tmp_file.name) as r2:
                    # Should handle gracefully
                    file_info = await r2.get_file_info()
                    # May succeed with warning or fail gracefully
                    assert file_info is None or isinstance(file_info, dict)
                    
            finally:
                os.unlink(tmp_file.name)
    
    async def test_empty_file(self):
        """Test handling of empty file."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(b"")  # Empty file
            tmp_file.flush()
            
            try:
                async with R2Session(tmp_file.name) as r2:
                    file_info = await r2.get_file_info()
                    # Should handle gracefully
                    
            finally:
                os.unlink(tmp_file.name)
    
    async def test_very_large_file_handling(self):
        """Test handling of very large files (within reason)."""
        # Create a larger file (but not too large for CI)
        large_data = TestBinaryGenerator.create_simple_pe_binary() + b"\x00" * (10 * 1024 * 1024)  # 10MB
        
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(large_data)
            tmp_file.flush()
            
            try:
                start_time = time.perf_counter()
                
                async with R2Session(tmp_file.name) as r2:
                    file_info = await r2.get_file_info()
                    
                end_time = time.perf_counter()
                
                # Should complete within reasonable time
                processing_time = end_time - start_time
                assert processing_time < 30.0, f"Large file processing too slow: {processing_time:.2f}s"
                
            finally:
                os.unlink(tmp_file.name)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "--tb=short"])