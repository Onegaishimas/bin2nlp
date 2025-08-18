"""
Test radare2 availability and integration structure validation.

This module tests that our real radare2 integration is structured correctly
and would work properly when radare2 is available on the system.
"""

import pytest
import tempfile
import os
import shutil
from unittest.mock import Mock, patch, AsyncMock

from src.decompilation.r2_session import R2Session, R2SessionException
from src.decompilation.engine import DecompilationEngine
from src.core.config import get_settings


@pytest.mark.asyncio
class TestRadare2Availability:
    """Test radare2 availability and integration structure."""
    
    def test_radare2_availability_detection(self):
        """Test that we can detect whether radare2 is available."""
        # Check if radare2 is in PATH
        radare2_available = shutil.which('radare2') is not None
        
        # This tells us the current environment status
        if radare2_available:
            print("\n✅ radare2 is available for real integration testing")
        else:
            print("\n⚠️  radare2 not available - would need installation for real tests")
    
    async def test_r2session_structure_without_radare2(self):
        """Test R2Session structure and error handling when radare2 unavailable."""
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(b"MZ" + b"\x00" * 100)
            tmp_file.flush()
            
            try:
                # This should fail gracefully with proper error
                with pytest.raises(R2SessionException) as exc_info:
                    async with R2Session(tmp_file.name) as r2:
                        pass  # Should never reach here
                
                # Verify error message is meaningful
                assert "Failed to initialize R2 session" in str(exc_info.value)
                assert "Cannot find radare2" in str(exc_info.value) or "radare2" in str(exc_info.value).lower()
                
            finally:
                os.unlink(tmp_file.name)
    
    @patch('src.analysis.engines.r2_integration.r2pipe.open')
    async def test_r2session_with_mocked_radare2(self, mock_r2pipe):
        """Test R2Session behavior with mocked radare2 to validate integration structure."""
        # Set up mock r2pipe
        mock_r2 = Mock()
        mock_r2.cmd = Mock()
        mock_r2.quit = Mock()
        mock_r2pipe.return_value = mock_r2
        
        # Mock basic r2 commands
        mock_r2.cmd.side_effect = lambda cmd: {
            'i': '{"format":"pe","arch":"x86","bits":32}',
            'afl': '[{"name":"main","offset":4194304,"size":64}]',
            'iI': '[{"name":"kernel32.dll","func":"CreateFileA"}]',
            'iz': '[{"vaddr":8192,"string":"Hello World"}]'
        }.get(cmd, '{}')
        
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(b"MZ" + b"\x00" * 100)
            tmp_file.flush()
            
            try:
                # Test that our R2Session would work with real radare2
                async with R2Session(tmp_file.name) as r2:
                    # Test file info
                    file_info = await r2.get_file_info()
                    assert file_info is not None
                    
                    # Test functions analysis
                    functions = await r2.extract_functions()
                    assert isinstance(functions, list)
                    
                    # Test imports
                    imports = await r2.get_imports()
                    assert isinstance(imports, list)
                    
                    # Test strings
                    strings = await r2.get_strings()
                    assert isinstance(strings, list)
                
                # Verify cleanup was called
                mock_r2.quit.assert_called_once()
                
            finally:
                os.unlink(tmp_file.name)
    
    async def test_decompilation_engine_radare2_dependency(self):
        """Test that DecompilationEngine properly handles radare2 dependency."""
        settings = get_settings()
        engine = DecompilationEngine(settings)
        
        # Create test binary
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(b"MZ" + b"\x00" * 100)
            tmp_file.flush()
            
            try:
                # This should fail gracefully when radare2 is not available
                result = await engine.decompile_binary(tmp_file.name)
                
                # Should return error result, not crash
                assert hasattr(result, 'success')
                assert hasattr(result, 'errors')
                
                # If radare2 unavailable, should have error
                if not shutil.which('radare2'):
                    assert result.success == False
                    assert len(result.errors) > 0
                    assert any('radare2' in error.lower() for error in result.errors)
                
            finally:
                os.unlink(tmp_file.name)
    
    def test_integration_test_structure_validation(self):
        """Validate that our integration tests are structured correctly."""
        # Import the test classes to verify structure
        from tests.integration.test_radare2_integration import (
            TestRealRadare2Integration, 
            TestRealRadare2ErrorScenarios,
            TestBinaryGenerator
        )
        
        # Verify test classes exist and have expected methods
        assert hasattr(TestRealRadare2Integration, 'test_real_r2session_basic_analysis')
        assert hasattr(TestRealRadare2Integration, 'test_decompilation_engine_end_to_end')
        assert hasattr(TestRealRadare2Integration, 'test_performance_benchmarking')
        assert hasattr(TestRealRadare2Integration, 'test_concurrent_analysis')
        
        assert hasattr(TestRealRadare2ErrorScenarios, 'test_corrupted_pe_header')
        assert hasattr(TestRealRadare2ErrorScenarios, 'test_empty_file')
        
        # Verify binary generator has expected methods
        assert hasattr(TestBinaryGenerator, 'create_simple_pe_binary')
        assert hasattr(TestBinaryGenerator, 'create_simple_elf_binary')
        assert hasattr(TestBinaryGenerator, 'create_binary_with_strings')
        assert hasattr(TestBinaryGenerator, 'create_malformed_binary')
    
    def test_binary_generator_functionality(self):
        """Test that our binary generators create valid test data."""
        from tests.integration.test_radare2_integration import TestBinaryGenerator
        
        # Test PE binary generation
        pe_binary = TestBinaryGenerator.create_simple_pe_binary()
        assert isinstance(pe_binary, bytes)
        assert len(pe_binary) > 100
        assert pe_binary[:2] == b"MZ"  # DOS header
        assert b"PE\x00\x00" in pe_binary  # PE signature
        
        # Test ELF binary generation
        elf_binary = TestBinaryGenerator.create_simple_elf_binary()
        assert isinstance(elf_binary, bytes)
        assert len(elf_binary) > 100
        assert elf_binary[:4] == b"\x7fELF"  # ELF magic
        
        # Test string binary generation
        string_binary = TestBinaryGenerator.create_binary_with_strings()
        assert isinstance(string_binary, bytes)
        assert len(string_binary) > 100
        assert b"Hello World" in string_binary
        assert b"Test Application" in string_binary
        
        # Test malformed binary
        malformed = TestBinaryGenerator.create_malformed_binary()
        assert isinstance(malformed, bytes)
        assert b"This is not a valid binary" in malformed


@pytest.mark.integration
@pytest.mark.skipif(shutil.which('radare2') is None, reason="radare2 not available")
class TestRealRadare2Available:
    """Tests that run only when radare2 is actually available."""
    
    @pytest.mark.asyncio
    async def test_real_radare2_basic_functionality(self):
        """Test basic radare2 functionality when available."""
        from tests.integration.test_radare2_integration import TestBinaryGenerator
        
        pe_binary = TestBinaryGenerator.create_simple_pe_binary()
        
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp_file:
            tmp_file.write(pe_binary)
            tmp_file.flush()
            
            try:
                async with R2Session(tmp_file.name) as r2:
                    # Basic functionality test
                    file_info = await r2.get_file_info()
                    assert file_info is not None
                    print(f"✅ Real radare2 analysis successful: {file_info}")
                    
            finally:
                os.unlink(tmp_file.name)


if __name__ == "__main__":
    # Allow running tests directly  
    pytest.main([__file__, "-v", "--tb=short"])