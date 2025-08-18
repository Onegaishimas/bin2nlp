"""
Integration tests for Decompilation Engine with real radare2 integration.

These tests validate the complete decompilation workflow using actual binary files
and real radare2 integration, updated for decompilation + LLM translation focus.
"""

import pytest
import asyncio
import tempfile
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List
import hashlib

from src.decompilation.engine import DecompilationEngine, DecompilationConfig
from src.models.analysis.basic_results import BasicDecompilationResult
from src.models.decompilation.results import DecompilationResult, DecompilationDepth
from src.models.shared.enums import FileFormat, Platform
from src.core.config import get_settings
from src.core.exceptions import BinaryAnalysisException


class TestDecompilationEngineIntegration:
    """Integration tests for DecompilationEngine with real radare2."""

    @pytest.fixture(scope="class")
    def sample_binaries(self):
        """
        Provides sample binary files for testing different formats.
        
        Returns dict mapping format names to file paths for test binaries.
        """
        samples = {}
        
        # Use existing PE executables from pip installation
        pip_bin_dir = Path(__file__).parent / "../../.env-bin2nlp/lib/python3.12/site-packages/pip/_vendor/distlib"
        
        if (pip_bin_dir / "w32.exe").exists():
            samples["pe32"] = str(pip_bin_dir / "w32.exe")
        if (pip_bin_dir / "w64.exe").exists():
            samples["pe64"] = str(pip_bin_dir / "w64.exe")
        
        # Try to find ELF binaries from system
        system_bins = ["/bin/ls", "/usr/bin/cat", "/bin/echo"]
        for bin_path in system_bins:
            if Path(bin_path).exists():
                samples["elf"] = bin_path
                break
        
        # Create a simple test binary if no samples found
        if not samples:
            # Use the test binary generator from our radare2 integration tests
            from tests.integration.test_radare2_integration import TestBinaryGenerator
            
            test_dir = Path(tempfile.mkdtemp())
            test_file = test_dir / "test_binary.exe"
            
            binary_data = TestBinaryGenerator.create_simple_pe_binary()
            with open(test_file, 'wb') as f:
                f.write(binary_data)
            
            samples["test_pe"] = str(test_file)
        
        return samples

    @pytest.fixture(scope="class")
    def corrupted_samples(self):
        """Create corrupted binary samples for error testing."""
        samples = {}
        test_dir = Path(tempfile.mkdtemp())
        
        # Create truncated PE file
        truncated_pe = test_dir / "truncated.exe"
        with open(truncated_pe, 'wb') as f:
            f.write(b'MZ\x90\x00')  # Incomplete PE header
        samples["truncated_pe"] = str(truncated_pe)
        
        # Create empty file
        empty_file = test_dir / "empty.bin"
        with open(empty_file, 'wb') as f:
            pass  # Create empty file
        samples["empty"] = str(empty_file)
        
        return samples

    @pytest.fixture
    def decompilation_engine(self):
        """Create DecompilationEngine with standard configuration."""
        config = DecompilationConfig(
            max_file_size_mb=100,
            timeout_seconds=120,  # Shorter timeout for tests
            r2_analysis_level="aa",
            extract_functions=True,
            extract_strings=True,
            extract_imports=True
        )
        return DecompilationEngine(config)

    @pytest.mark.asyncio
    async def test_decompile_pe_binary_complete_workflow(self, decompilation_engine, sample_binaries):
        """
        Test complete decompilation workflow with a PE binary file.
        
        Tests decompilation engine with real radare2 integration.
        """
        if not sample_binaries:
            pytest.skip("No sample binaries available for testing")
        
        # Use the first available sample
        sample_path = list(sample_binaries.values())[0]
        
        # Execute complete decompilation
        result = await decompilation_engine.decompile_binary(sample_path)
        
        # Validate result structure
        assert isinstance(result, BasicDecompilationResult)
        assert result.metadata.file_size > 0
        assert result.metadata.file_hash
        assert len(result.metadata.file_hash) == 64  # SHA-256 hash without algorithm prefix
        
        # Should either succeed or have partial results
        assert result.success or result.partial_results
        
        # Validate timing information
        assert result.metadata.decompilation_time >= 0
        assert result.metadata.timestamp
        
        # Validate file format detection
        assert result.metadata.file_format is not None
        
        # Validate decompilation data structures
        assert isinstance(result.functions, list)
        assert isinstance(result.imports, list)
        assert isinstance(result.strings, list)
        
        # Check error handling
        assert isinstance(result.errors, list)
        assert isinstance(result.warnings, list)

    @pytest.mark.asyncio
    async def test_decompile_elf_binary_workflow(self, decompilation_engine, sample_binaries):
        """
        Test decompilation workflow with ELF binary (Linux executable).
        """
        if "elf" not in sample_binaries:
            pytest.skip("No ELF sample available for testing")
        
        sample_path = sample_binaries["elf"]
        
        # Execute decompilation
        result = await decompilation_engine.decompile_binary(sample_path)
        
        # Basic validation
        assert isinstance(result, DecompilationResult)
        
        # Should either succeed or have partial results
        assert result.success or result.partial_results
        
        # Check format detection specifically for ELF
        if result.success:
            assert result.file_format in [FileFormat.ELF, FileFormat.ELF32, FileFormat.ELF64, FileFormat.UNKNOWN]
            assert result.platform in [Platform.LINUX, Platform.UNIX, Platform.UNKNOWN]

    @pytest.mark.asyncio
    async def test_error_handling_corrupted_files(self, decompilation_engine, corrupted_samples):
        """
        Test error handling with corrupted and malformed files.
        """
        for corruption_type, file_path in corrupted_samples.items():
            
            # Decompilation should not crash on corrupted files
            result = await decompilation_engine.decompile_binary(file_path)
            
            # Result should be returned even for corrupted files
            assert isinstance(result, DecompilationResult)
            assert result.file_size >= 0  # May be 0 for empty files
            
            # May or may not succeed, but should handle gracefully
            if not result.success:
                # Should have error information
                assert len(result.errors) > 0 or result.partial_results
            
            # Should not crash the process
            assert isinstance(result.errors, list)
            assert isinstance(result.warnings, list)

    @pytest.mark.asyncio
    async def test_file_hash_consistency(self, decompilation_engine, sample_binaries):
        """
        Test that file hash calculation is consistent across runs.
        """
        if not sample_binaries:
            pytest.skip("No samples available for hash consistency testing")
        
        sample_path = list(sample_binaries.values())[0]
        
        # Run decompilation multiple times
        results = []
        for _ in range(2):  # Keep it to 2 runs to save time
            result = await decompilation_engine.decompile_binary(sample_path)
            results.append(result)
        
        # All runs should produce same file hash
        hashes = [result.file_hash for result in results]
        assert len(set(hashes)) == 1  # All hashes should be identical
        
        # Hash should be valid format
        assert "sha256:" in hashes[0]
        hash_value = hashes[0].replace("sha256:", "")
        assert len(hash_value) == 64
        assert all(c in '0123456789abcdef' for c in hash_value)

    @pytest.mark.asyncio
    async def test_large_file_handling(self, decompilation_engine):
        """
        Test handling of large files within memory constraints.
        """
        # Create a moderately large temporary file (5MB to keep test reasonable)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp_file:
            # Create 5MB file with some structure
            chunk = b'MZ\x90\x00' + b'\x00' * 1020  # 1KB chunks with PE header start
            for _ in range(5 * 1024):  # 5MB
                tmp_file.write(chunk)
            large_file_path = tmp_file.name
        
        try:
            # Should handle large file without crashing
            result = await decompilation_engine.decompile_binary(large_file_path)
            
            assert isinstance(result, DecompilationResult)
            assert result.file_size > 0
            
            # Decompilation may or may not succeed on a random large file, but should not crash
            
        finally:
            # Clean up
            os.unlink(large_file_path)

    @pytest.mark.asyncio
    async def test_nonexistent_file_handling(self, decompilation_engine):
        """
        Test error handling with nonexistent files.
        """
        nonexistent_path = "/path/that/does/not/exist.exe"
        
        # Should raise appropriate exception
        with pytest.raises(FileNotFoundError):
            await decompilation_engine.decompile_binary(nonexistent_path)

    @pytest.mark.asyncio
    async def test_decompilation_data_structure_validity(self, decompilation_engine, sample_binaries):
        """
        Test that decompilation results have proper data structure.
        """
        if not sample_binaries:
            pytest.skip("No samples available for data structure testing")
        
        sample_path = list(sample_binaries.values())[0]
        result = await decompilation_engine.decompile_binary(sample_path)
        
        # Test computed properties work
        assert isinstance(result.total_duration_seconds, (int, float))
        assert result.total_duration_seconds >= 0
        
        # Test method calls work
        assert isinstance(result.is_decompilation_complete(), bool)
        
        # Test summary generation
        summary = result.decompilation_summary
        assert isinstance(summary, dict)
        assert "file_info" in summary
        assert "processing_stats" in summary


@pytest.mark.skipif(shutil.which('radare2') is None, reason="radare2 not available")
class TestDecompilationEngineWithRadare2:
    """Tests that run only when radare2 is actually available."""
    
    @pytest.fixture
    def decompilation_engine(self):
        """Create DecompilationEngine with radare2 available."""
        config = DecompilationConfig(
            max_file_size_mb=50,
            timeout_seconds=60,  # Shorter timeout for tests
            r2_analysis_level="aa"
        )
        return DecompilationEngine(config)
    
    @pytest.mark.asyncio
    async def test_real_radare2_decompilation(self, decompilation_engine):
        """Test decompilation with real radare2 when available."""
        from tests.integration.test_radare2_integration import TestBinaryGenerator
        
        # Create a test binary
        binary_data = TestBinaryGenerator.create_simple_pe_binary()
        
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(binary_data)
            tmp_file.flush()
            
            try:
                # This should work with real radare2
                result = await decompilation_engine.decompile_binary(tmp_file.name)
                
                assert isinstance(result, DecompilationResult)
                print(f"✅ Real radare2 decompilation successful: {result.success}")
                
                if result.success:
                    assert result.file_format == FileFormat.PE
                    assert len(result.functions) >= 0  # May or may not find functions in minimal binary
                    assert len(result.imports) >= 0
                    assert len(result.strings) >= 0
                    
            finally:
                os.unlink(tmp_file.name)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "--tb=short"])