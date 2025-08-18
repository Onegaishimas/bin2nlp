"""
Unit tests for radare2 integration layer.

Tests R2Session functionality with comprehensive mocking of r2pipe,
covering connection management, command execution, error handling, and timeout scenarios.
"""

import pytest
import asyncio
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock, call
from typing import Any, Dict, List

from src.decompilation.r2_session import (
    R2Session,
    R2SessionState,
    R2Command,
    R2CommandResult,
    R2SessionException,
    R2TimeoutException,
    r2_session
)


class TestR2Session:
    """Test R2Session class functionality."""
    
    @pytest.fixture
    def mock_r2pipe(self):
        """Create mock r2pipe instance."""
        mock_pipe = Mock()
        mock_pipe.cmd.return_value = "radare2 5.8.8"
        mock_pipe.cmdj.return_value = {"version": "5.8.8"}
        mock_pipe.quit = Mock()
        return mock_pipe
    
    @pytest.fixture
    def test_file_path(self):
        """Create temporary test file."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            tmp_file.write(b'MZ' + b'\x00' * 100)  # Simple PE-like content
            tmp_file.flush()
            yield tmp_file.name
        
        # Cleanup
        try:
            os.unlink(tmp_file.name)
        except FileNotFoundError:
            pass
    
    @pytest.fixture
    def session(self, test_file_path):
        """Create R2Session instance with test file."""
        return R2Session(
            file_path=test_file_path,
            default_timeout=5.0,
            max_retries=2
        )
    
    @pytest.mark.asyncio
    async def test_session_initialization_with_file_path(self, session, mock_r2pipe):
        """Test session initialization with file path."""
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            assert session.is_ready is True
            assert session._state == R2SessionState.READY
            assert session.file_path is not None
            assert session._r2_pipe is mock_r2pipe
    
    @pytest.mark.asyncio 
    async def test_session_initialization_with_file_content(self, mock_r2pipe):
        """Test session initialization with file content."""
        content = b'MZ' + b'\x00' * 100
        session = R2Session(file_content=content, default_timeout=5.0)
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            assert session.is_ready is True
            assert session._temp_file_path is not None
            assert Path(session._temp_file_path).exists()
    
    @pytest.mark.asyncio
    async def test_session_initialization_failure(self, session):
        """Test session initialization failure handling."""
        with patch('r2pipe.open', side_effect=Exception("R2 initialization failed")):
            with pytest.raises(R2SessionException, match="Failed to initialize R2 session"):
                await session.initialize()
            
            assert session._state == R2SessionState.CLOSED  # State becomes CLOSED after cleanup
    
    def test_session_creation_validation(self):
        """Test session creation validation."""
        # Should raise error when neither file_path nor file_content provided
        with pytest.raises(ValueError, match="Either file_path or file_content must be provided"):
            R2Session()
    
    @pytest.mark.asyncio
    async def test_context_manager(self, test_file_path, mock_r2pipe):
        """Test async context manager functionality."""
        with patch('r2pipe.open', return_value=mock_r2pipe):
            async with R2Session(file_path=test_file_path) as session:
                assert session.is_ready is True
                assert session._r2_pipe is mock_r2pipe
            
            # Session should be cleaned up
            assert session._state == R2SessionState.CLOSED
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, session, mock_r2pipe):
        """Test successful command execution."""
        mock_r2pipe.cmdj.return_value = {"test": "result"}
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Reset call count after initialization (which calls ?V and i for verification)
            mock_r2pipe.cmdj.reset_mock()
            
            result = await session.execute_command("ij")
            
            assert result.success is True
            assert result.output == {"test": "result"}
            assert result.command == "ij"
            assert result.execution_time > 0
            mock_r2pipe.cmdj.assert_called_once_with("ij")
    
    @pytest.mark.asyncio
    async def test_execute_command_text_output(self, session, mock_r2pipe):
        """Test command execution with text output."""
        mock_r2pipe.cmd.return_value = "text output"
        mock_r2pipe.cmdj.return_value = {"version": "5.8.8"}  # For verification commands
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Reset after initialization
            mock_r2pipe.cmd.reset_mock()
            
            result = await session.execute_command("?V", expected_type="text")
            
            assert result.success is True
            assert result.output == "text output"
            # Expect 2 calls: 1 for health check + 1 for actual command
            assert mock_r2pipe.cmd.call_count == 2
            # Both calls should be for the same command
            mock_r2pipe.cmd.assert_has_calls([call("?V"), call("?V")])
    
    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, session, mock_r2pipe):
        """Test command execution timeout handling."""
        # Set up normal responses for initialization
        mock_r2pipe.cmd.return_value = "5.8.8"  # For health checks
        mock_r2pipe.cmdj.return_value = {"arch": "x86"}  # For initialization
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Now set up hanging command for the specific test
            def hanging_command(cmd):
                import time
                time.sleep(10)  # Blocks for longer than timeout
                return "result"
            
            mock_r2pipe.cmdj.side_effect = hanging_command
            
            # Should timeout and return failed result
            result = await session.execute_command("ij", timeout=0.1)
            
            assert result.success is False
            assert "timed out" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_execute_command_retry_logic(self, session, mock_r2pipe):
        """Test command execution retry logic."""
        # Set up successful initialization
        mock_r2pipe.cmd.return_value = "5.8.8"  # For health checks
        mock_r2pipe.cmdj.return_value = {"arch": "x86"}  # For session verification
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Now test the retry logic on a new command
            # Mock will return failures then success (including health checks)
            call_count = 0
            def mock_cmdj_with_retries(cmd):
                nonlocal call_count
                call_count += 1
                if cmd == "test_command" and call_count <= 2:
                    raise Exception(f"Failure {call_count}")
                return {"success": True, "data": f"call_{call_count}"}
            
            mock_r2pipe.cmdj.side_effect = mock_cmdj_with_retries
            
            result = await session.execute_command("test_command")
            
            assert result.success is True
            assert "success" in str(result.output)
            assert result.retry_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_command_max_retries_exceeded(self, session, mock_r2pipe):
        """Test command execution when max retries exceeded."""
        # Set up successful initialization
        mock_r2pipe.cmd.return_value = "5.8.8"  # For health checks
        mock_r2pipe.cmdj.return_value = {"arch": "x86"}  # For session verification
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Set up persistent failure for the test command
            def persistent_failure(cmd):
                if cmd == "test_fails":
                    raise Exception("Persistent failure")
                return {"default": "response"}
            
            mock_r2pipe.cmdj.side_effect = persistent_failure
            
            result = await session.execute_command("test_fails")
            
            assert result.success is False
            assert "Persistent failure" in result.error_message
            assert result.retry_count == session.max_retries
    
    @pytest.mark.asyncio
    async def test_command_caching(self, session, mock_r2pipe):
        """Test command result caching functionality."""
        mock_r2pipe.cmdj.return_value = {"cached": "result"}
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Reset mock after initialization to isolate test calls
            mock_r2pipe.cmdj.reset_mock()
            mock_r2pipe.cmd.reset_mock()  # Health checks use cmd("?V")
            
            # First call should execute command (health check + actual command)
            result1 = await session.execute_command("ij", cache_result=True)
            assert result1.success is True
            initial_cmdj_count = mock_r2pipe.cmdj.call_count  # Could be 1 or 2 depending on implementation
            
            # Second call should use cache (only health check, no actual command)
            result2 = await session.execute_command("ij", cache_result=True)
            assert result2.success is True
            assert result2.output == result1.output
            # cmdj count should remain the same since command was cached
            assert mock_r2pipe.cmdj.call_count == initial_cmdj_count
    
    @pytest.mark.asyncio
    async def test_session_not_ready_error(self, session):
        """Test command execution when session is not ready."""
        # Set session to CLOSED state to trigger the session not ready error
        session._state = R2SessionState.CLOSED
        
        with pytest.raises(R2SessionException, match="Session not ready"):
            await session.execute_command("ij")
    
    @pytest.mark.asyncio
    async def test_get_file_info(self, session, mock_r2pipe):
        """Test get_file_info method."""
        mock_info = {
            "core": {"format": "pe", "size": 1024, "type": "EXEC"},
            "bin": {"arch": "x86", "bits": 32, "endian": "little"}
        }
        mock_r2pipe.cmdj.return_value = mock_info
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            info = await session.get_file_info()
            
            assert info == mock_info
            mock_r2pipe.cmdj.assert_called_with("ij")
    
    @pytest.mark.asyncio
    async def test_extract_functions(self, session, mock_r2pipe):
        """Test extract_functions method."""
        mock_functions = [
            {"name": "main", "offset": 4096, "size": 100},
            {"name": "sub_1000", "offset": 5000, "size": 50}
        ]
        
        # Set up successful initialization
        mock_r2pipe.cmd.return_value = "5.8.8"  # For health checks
        mock_r2pipe.cmdj.return_value = {"arch": "x86"}  # For session verification
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Reset and set up the function extraction mock
            mock_r2pipe.cmdj.reset_mock()
            mock_r2pipe.cmdj.return_value = mock_functions
            
            functions = await session.extract_functions("standard")
            
            assert functions == mock_functions
            assert mock_r2pipe.cmdj.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_get_strings(self, session, mock_r2pipe):
        """Test get_strings method."""
        # Set up successful initialization
        mock_r2pipe.cmd.return_value = "5.8.8"  # For health checks
        mock_r2pipe.cmdj.return_value = {"arch": "x86"}  # For session verification
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Test strings data with mixed lengths for filtering test
            mock_strings = [
                {"string": "Hello World", "vaddr": 0x1000, "length": 11},  # Above min_length
                {"string": "Hi", "vaddr": 0x1500, "length": 2},           # Below min_length 
                {"string": "Error", "vaddr": 0x2000, "length": 5}         # Above min_length
            ]
            
            # Mock the string extraction and cross-reference commands
            def mock_cmdj_for_strings(cmd):
                if cmd == "izj":
                    return mock_strings
                elif cmd.startswith("axtj @"):
                    return []  # Empty cross-references
                return {}
            
            mock_r2pipe.cmdj.reset_mock()
            mock_r2pipe.cmdj.side_effect = mock_cmdj_for_strings
            
            # Test with min_length=4, should filter out "Hi" (length 2)
            strings = await session.get_strings(min_length=4)
            
            # Should return only strings with length >= 4
            expected_strings = [
                {"string": "Hello World", "vaddr": 0x1000, "length": 11, "cross_references": []},
                {"string": "Error", "vaddr": 0x2000, "length": 5, "cross_references": []}
            ]
            assert len(strings) == 2
            assert strings[0]["string"] == "Hello World"
            assert strings[1]["string"] == "Error"
    
    @pytest.mark.asyncio
    async def test_get_imports(self, session, mock_r2pipe):
        """Test get_imports method."""
        mock_imports = [
            {"name": "printf", "type": "FUNC", "bind": "GLOBAL"},
            {"name": "malloc", "type": "FUNC", "bind": "GLOBAL"}
        ]
        mock_r2pipe.cmdj.return_value = mock_imports
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            imports = await session.get_imports()
            
            assert imports == mock_imports
            mock_r2pipe.cmdj.assert_called_with("iij")
    
    @pytest.mark.asyncio
    async def test_get_exports(self, session, mock_r2pipe):
        """Test get_exports method."""
        mock_exports = [
            {"name": "exported_func", "vaddr": 0x1000, "type": "FUNC"}
        ]
        mock_r2pipe.cmdj.return_value = mock_exports
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            exports = await session.get_exports()
            
            assert exports == mock_exports
            mock_r2pipe.cmdj.assert_called_with("iEj")
    
    @pytest.mark.asyncio
    async def test_get_sections(self, session, mock_r2pipe):
        """Test get_sections method."""
        mock_sections = [
            {"name": ".text", "vaddr": 0x1000, "size": 2048, "perm": "r-x"},
            {"name": ".data", "vaddr": 0x2000, "size": 1024, "perm": "rw-"}
        ]
        mock_r2pipe.cmdj.return_value = mock_sections
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            sections = await session.get_sections()
            
            assert sections == mock_sections
            mock_r2pipe.cmdj.assert_called_with("iSj")
    
    @pytest.mark.asyncio
    async def test_disassemble_function(self, session, mock_r2pipe):
        """Test disassemble_function method."""
        mock_disassembly = """
        ; CALL XREF from entry0 @ 0x1000
        0x00001000      push   ebp
        0x00001001      mov    ebp, esp
        0x00001003      ret
        """
        mock_r2pipe.cmd.return_value = mock_disassembly
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Test with hex string address
            disasm = await session.disassemble_function("0x1000")
            assert disasm == mock_disassembly
            mock_r2pipe.cmd.assert_called_with("pdf @ 0x1000")
            
            # Test with integer address
            disasm = await session.disassemble_function(4096)
            assert disasm == mock_disassembly
            mock_r2pipe.cmd.assert_called_with("pdf @ 0x1000")
    
    # NOTE: search_pattern method removed during architecture transformation
    # Binary search functionality not needed in decompilation-focused workflow
    
    @pytest.mark.asyncio
    async def test_cleanup(self, session, mock_r2pipe):
        """Test session cleanup."""
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Create temp file to verify cleanup
            assert session.file_path is not None
            
            await session.cleanup()
            
            assert session._state == R2SessionState.CLOSED
            assert session._r2_pipe is None
            mock_r2pipe.quit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_with_temp_file(self, mock_r2pipe):
        """Test cleanup with temporary file removal."""
        content = b'test content'
        session = R2Session(file_content=content)
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            temp_path = session._temp_file_path
            assert temp_path is not None
            assert Path(temp_path).exists()
            
            await session.cleanup()
            
            # Temp file should be removed
            assert not Path(temp_path).exists()
    
    @pytest.mark.asyncio
    async def test_concurrent_commands(self, session, mock_r2pipe):
        """Test concurrent command execution."""
        # Mock different responses for different commands
        command_responses = {
            "ij": {"info": "file_info"},
            "aflj": [{"name": "main"}],
            "iij": [{"name": "printf"}],
            "iEj": [{"name": "exported"}]
        }
        
        def mock_cmdj(cmd):
            return command_responses.get(cmd, {})
        
        mock_r2pipe.cmdj.side_effect = mock_cmdj
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            
            # Execute multiple commands concurrently
            tasks = [
                session.get_file_info(),
                session.get_imports(),
                session.get_exports(),
            ]
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == 3
            assert results[0] == command_responses["ij"]
            assert results[1] == command_responses["iij"] 
            assert results[2] == command_responses["iEj"]


class TestR2SessionContextManager:
    """Test standalone r2_session context manager."""
    
    @pytest.mark.asyncio
    async def test_context_manager_function(self, mock_r2pipe=None):
        """Test r2_session context manager function."""
        if mock_r2pipe is None:
            mock_r2pipe = Mock()
            mock_r2pipe.cmd.return_value = "radare2 5.8.8"
            mock_r2pipe.cmdj.return_value = {"version": "5.8.8"}
        
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            tmp_file.write(b'MZ' + b'\x00' * 100)
            tmp_file.flush()
            
            try:
                with patch('r2pipe.open', return_value=mock_r2pipe):
                    async with r2_session(file_path=tmp_file.name) as session:
                        assert isinstance(session, R2Session)
                        assert session.is_ready is True
                        
                        # Should be able to execute commands
                        result = await session.execute_command("ij")
                        assert result.success is True
                
            finally:
                os.unlink(tmp_file.name)


class TestR2SessionEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.mark.asyncio
    async def test_session_state_transitions(self):
        """Test session state transitions."""
        content = b'test'
        session = R2Session(file_content=content)
        
        # Initial state
        assert session._state == R2SessionState.INITIALIZING
        
        # Initialization failure
        with patch('r2pipe.open', side_effect=Exception("Failed")):
            with pytest.raises(R2SessionException):
                await session.initialize()
        
        # After initialization failure and cleanup, session should be CLOSED
        assert session._state == R2SessionState.CLOSED
    
    @pytest.mark.asyncio
    async def test_command_execution_in_error_state(self):
        """Test command execution when session is in error state."""
        content = b'test'
        session = R2Session(file_content=content)
        session._state = R2SessionState.ERROR
        
        with pytest.raises(R2SessionException, match="Session not ready"):
            await session.execute_command("ij")
    
    @pytest.mark.asyncio
    async def test_multiple_initialization_calls(self, mock_r2pipe=None):
        """Test calling initialize multiple times."""
        if mock_r2pipe is None:
            mock_r2pipe = Mock()
            mock_r2pipe.cmd.return_value = "radare2 5.8.8"
            mock_r2pipe.cmdj.return_value = {"version": "5.8.8"}
        
        content = b'test'
        session = R2Session(file_content=content)
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            await session.initialize()
            assert session.is_ready
            
            # Second initialization should work (maybe warn but not fail)
            await session.initialize()
            assert session.is_ready
    
    def test_session_id_uniqueness(self):
        """Test that each session gets a unique ID."""
        session1 = R2Session(file_content=b'test1')
        session2 = R2Session(file_content=b'test2')
        
        assert session1.session_id != session2.session_id
        assert "r2_" in session1.session_id
        assert "r2_" in session2.session_id
    
    @pytest.mark.asyncio
    async def test_command_result_properties(self):
        """Test R2CommandResult properties and behavior."""
        result = R2CommandResult(
            command="test_cmd",
            output={"test": "data"},
            execution_time=0.123,
            success=True,
            retry_count=1
        )
        
        assert result.command == "test_cmd"
        assert result.success is True
        assert result.retry_count == 1
        assert result.error_message is None
        
        # Test failed result
        failed_result = R2CommandResult(
            command="failed_cmd",
            output=None,
            execution_time=0.0,
            success=False,
            error_message="Command failed",
            retry_count=3
        )
        
        assert failed_result.success is False
        assert failed_result.error_message == "Command failed"
    
    @pytest.mark.asyncio
    async def test_memory_cleanup_on_exception(self, mock_r2pipe=None):
        """Test that memory is properly cleaned up when exceptions occur."""
        if mock_r2pipe is None:
            mock_r2pipe = Mock()
            mock_r2pipe.cmd.return_value = "radare2 5.8.8"
            mock_r2pipe.cmdj.return_value = {"version": "5.8.8"}  # Successful initialization
            mock_r2pipe.quit = Mock()
        
        content = b'test content'
        session = None
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            try:
                async with R2Session(file_content=content) as s:
                    session = s
                    # Now set up failure for the actual command after initialization
                    mock_r2pipe.cmdj.side_effect = Exception("Command execution failed")
                    # This should fail
                    await session.execute_command("ij")
            except:
                pass  # Expected to fail
        
        # Session should still be cleaned up despite exception
        assert session is not None
        assert session._state == R2SessionState.CLOSED
    
    @pytest.mark.asyncio
    async def test_very_long_command_output(self, mock_r2pipe=None):
        """Test handling of very long command output."""
        if mock_r2pipe is None:
            mock_r2pipe = Mock()
            mock_r2pipe.cmd.return_value = "radare2 5.8.8"
        
        # Create very long output
        long_output = "A" * 1000000  # 1MB of output
        mock_r2pipe.cmdj.return_value = {"long_data": long_output}
        
        content = b'test'
        
        with patch('r2pipe.open', return_value=mock_r2pipe):
            async with R2Session(file_content=content) as session:
                result = await session.execute_command("ij")
                
                assert result.success is True
                assert len(result.output["long_data"]) == 1000000