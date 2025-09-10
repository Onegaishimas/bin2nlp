"""
Radare2 integration layer for binary decompilation.

Provides a focused wrapper around r2pipe optimized for decompilation operations
with assembly extraction, function analysis, and structured data output for LLM consumption.
"""

import asyncio
import time
import tempfile
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, AsyncIterator
from dataclasses import dataclass
from enum import Enum

import r2pipe

from ..core.logging import get_logger
from ..core.exceptions import BinaryAnalysisException, AnalysisTimeoutException
from ..models.shared.enums import Platform, FileFormat


logger = get_logger(__name__)


class R2SessionState(Enum):
    """Radare2 session state."""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class R2Command:
    """Radare2 command with execution metadata."""
    command: str
    timeout: Optional[float] = None
    retry_count: int = 0
    expected_output_type: str = "json"  # json, text, binary


@dataclass
class R2CommandResult:
    """Result of radare2 command execution."""
    command: str
    output: Any
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    retry_count: int = 0
    session_restarted: bool = False


class R2SessionException(BinaryAnalysisException):
    """Radare2 session-specific exception."""
    pass


class R2TimeoutException(AnalysisTimeoutException):
    """Radare2 command timeout exception."""
    pass


class R2Session:
    """
    Asynchronous radare2 session manager with robust error handling.
    
    Provides a high-level interface for radare2 operations with:
    - Connection pooling and retry logic
    - Automatic timeout handling
    - Resource cleanup and session management
    - Command result caching
    - Progress tracking for long operations
    """
    
    def __init__(
        self,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        default_timeout: float = 30.0,
        max_retries: int = 3,
        r2_flags: Optional[List[str]] = None
    ):
        """
        Initialize R2 session.
        
        Args:
            file_path: Path to binary file to analyze
            file_content: Binary content (alternative to file_path)
            default_timeout: Default command timeout in seconds
            max_retries: Maximum retry attempts for failed commands
            r2_flags: Additional radare2 flags (e.g., ['-A', '-e', 'scr.interactive=false'])
        """
        if not file_path and not file_content:
            raise ValueError("Either file_path or file_content must be provided")
        
        self.file_path = file_path
        self.file_content = file_content
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.r2_flags = r2_flags or [
            '-2',  # Disable colors
            '-q',  # Quiet mode  
            '-e', 'bin.relocs.apply=true',  # Apply relocations for better analysis
            '-e', 'bin.cache=true'  # Enable binary cache for performance
        ]
        
        self._r2_pipe: Optional[r2pipe.open_sync] = None
        self._temp_file_path: Optional[str] = None
        self._state = R2SessionState.INITIALIZING
        self._command_cache: Dict[str, R2CommandResult] = {}
        self._session_id = f"r2_{int(time.time() * 1000000)}_{id(self)}"
        
        self.logger = logger.bind(
            component="r2_session",
            session_id=self._session_id
        )
    
    async def __aenter__(self) -> 'R2Session':
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup."""
        await self.cleanup()
    
    async def initialize(self) -> None:
        """Initialize radare2 session."""
        try:
            self._state = R2SessionState.INITIALIZING
            
            # Handle file content by writing to temporary file
            if self.file_content and not self.file_path:
                self._temp_file_path = await self._create_temp_file()
                self.file_path = self._temp_file_path
            
            # Initialize r2pipe session
            self.logger.info(
                "Initializing r2pipe session",
                file_path=self.file_path,
                flags=self.r2_flags
            )
            
            # Run r2pipe initialization in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            self._r2_pipe = await loop.run_in_executor(
                None,
                self._init_r2pipe
            )
            
            # Verify session is working
            await self._verify_session()
            
            self._state = R2SessionState.READY
            self.logger.info("R2 session initialized successfully")
            
        except Exception as e:
            self._state = R2SessionState.ERROR
            self.logger.error(
                "Failed to initialize R2 session",
                error=str(e),
                error_type=type(e).__name__
            )
            await self.cleanup()
            raise R2SessionException(f"Failed to initialize R2 session: {e}")
    
    def _init_r2pipe(self) -> r2pipe.open_sync:
        """Initialize r2pipe (runs in thread pool)."""
        # Try to open with configured flags first, fallback to no flags if needed
        try:
            return r2pipe.open(
                filename=self.file_path,
                flags=self.r2_flags
            )
        except Exception as e:
            # Fallback: try without flags for uploaded files that may have compatibility issues
            self.logger.warning(
                f"r2pipe.open failed with flags {self.r2_flags}, trying without flags: {e}"
            )
            try:
                return r2pipe.open(filename=self.file_path)
            except Exception as e2:
                raise R2SessionException(f"Failed to open file with radare2: {e2}")
    
    async def _create_temp_file(self) -> str:
        """Create temporary file from file content."""
        loop = asyncio.get_running_loop()
        
        def _write_temp_file():
            fd, temp_path = tempfile.mkstemp(suffix='.bin', prefix='r2_analysis_')
            try:
                with os.fdopen(fd, 'wb') as temp_file:
                    temp_file.write(self.file_content)
                return temp_path
            except Exception:
                os.unlink(temp_path)
                raise
        
        temp_path = await loop.run_in_executor(None, _write_temp_file)
        self.logger.debug("Created temporary file", temp_path=temp_path)
        return temp_path
    
    async def _verify_session(self) -> None:
        """Verify that R2 session is working properly."""
        try:
            # Test basic command
            result = await self.execute_command("?V")  # Get version
            if not result.success:
                raise R2SessionException("Session verification failed")
            
            # Test file loading
            info_result = await self.execute_command("i")  # Get file info
            if not info_result.success:
                raise R2SessionException("File loading verification failed")
                
        except Exception as e:
            raise R2SessionException(f"Session verification failed: {e}")
    
    @property
    def is_ready(self) -> bool:
        """Check if session is ready for commands."""
        return self._state == R2SessionState.READY
    
    @property
    def session_id(self) -> str:
        """Get unique session identifier."""
        return self._session_id
    
    async def execute_command(
        self,
        command: str,
        timeout: Optional[float] = None,
        cache_result: bool = False,
        expected_type: str = "json"
    ) -> R2CommandResult:
        """
        Execute radare2 command with error handling and timeout.
        
        Args:
            command: R2 command to execute
            timeout: Command timeout (uses default if None)
            cache_result: Whether to cache the result
            expected_type: Expected output type (json, text, binary)
            
        Returns:
            Command execution result
            
        Raises:
            R2TimeoutException: If command times out
            R2SessionException: If session is not ready or command fails
        """
        if not self.is_ready and self._state != R2SessionState.INITIALIZING:
            raise R2SessionException(f"Session not ready (state: {self._state.value})")
        
        timeout = timeout or self.default_timeout
        
        # Check cache first
        cache_key = f"{command}:{expected_type}"
        if cache_result and cache_key in self._command_cache:
            cached_result = self._command_cache[cache_key]
            self.logger.debug(
                "Using cached command result",
                command=command,
                cached_execution_time=cached_result.execution_time
            )
            return cached_result
        
        cmd_obj = R2Command(
            command=command,
            timeout=timeout,
            expected_output_type=expected_type
        )
        
        result = await self._execute_with_retry(cmd_obj)
        
        # Cache successful results if requested
        if cache_result and result.success:
            self._command_cache[cache_key] = result
        
        return result
    
    async def _execute_with_retry(self, cmd: R2Command) -> R2CommandResult:
        """Execute command with retry logic and crash recovery (ADR: comprehensive error handling)."""
        last_exception = None
        session_restart_attempted = False
        
        for attempt in range(self.max_retries + 1):
            try:
                # Check session health before command execution (ADR: crash recovery)
                if not await self._check_session_health():
                    self.logger.warning(
                        "R2 session unhealthy before command execution",
                        command=cmd.command,
                        attempt=attempt + 1,
                        session_state=self._state.value
                    )
                    
                    if not session_restart_attempted and await self._attempt_session_restart():
                        session_restart_attempted = True
                        self.logger.info(
                            "R2 session restarted successfully", 
                            command=cmd.command
                        )
                    else:
                        raise BinaryAnalysisException("R2 session is unhealthy and restart failed")
                
                self._state = R2SessionState.BUSY
                start_time = time.time()
                
                # Execute command with timeout
                result = await self._execute_single_command(cmd)
                
                execution_time = time.time() - start_time
                self._state = R2SessionState.READY
                
                # ADR: structured logging for success
                self.logger.info(
                    "R2 command executed successfully",
                    command=cmd.command,
                    execution_time=execution_time,
                    attempt=attempt + 1,
                    session_restarted=session_restart_attempted
                )
                
                return R2CommandResult(
                    command=cmd.command,
                    output=result,
                    execution_time=execution_time,
                    success=True,
                    retry_count=attempt,
                    session_restarted=session_restart_attempted
                )
                
            except asyncio.TimeoutError as e:
                last_exception = e
                self._state = R2SessionState.ERROR
                
                self.logger.warning(
                    "R2 command timeout",
                    command=cmd.command,
                    attempt=attempt + 1,
                    timeout=cmd.timeout
                )
                
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                
            except (ConnectionError, ProcessLookupError, BrokenPipeError, OSError) as e:
                # R2 process crash detected (ADR: crash recovery patterns)
                last_exception = e
                self._state = R2SessionState.ERROR
                
                self.logger.error(
                    "R2 process crash detected",
                    command=cmd.command,
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                # Attempt session restart for crash-related errors
                if attempt < self.max_retries and not session_restart_attempted:
                    if await self._attempt_session_restart():
                        session_restart_attempted = True
                        self.logger.info(
                            "R2 session restarted after crash",
                            command=cmd.command
                        )
                        # Don't sleep after successful restart
                        continue
                    else:
                        self.logger.error(
                            "Failed to restart R2 session after crash",
                            command=cmd.command
                        )
                        break
                
                if attempt < self.max_retries:
                    await asyncio.sleep(2.0 * (attempt + 1))  # Longer delay for crash recovery
                
            except Exception as e:
                last_exception = e
                
                self.logger.warning(
                    "R2 command execution failed",
                    command=cmd.command,
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                # For certain errors, attempt session restart (ADR: intelligent recovery)
                if (attempt < self.max_retries and 
                    not session_restart_attempted and
                    self._should_restart_for_error(e)):
                    
                    if await self._attempt_session_restart():
                        session_restart_attempted = True
                        self.logger.info(
                            "R2 session restarted due to error",
                            command=cmd.command,
                            error_type=type(e).__name__
                        )
                        continue
                
                if attempt < self.max_retries:
                    await asyncio.sleep(1.0 * (attempt + 1))
        
        self._state = R2SessionState.ERROR
        
        # ADR: comprehensive error reporting
        self.logger.error(
            "R2 command failed after all retry attempts",
            command=cmd.command,
            max_retries=self.max_retries,
            session_restart_attempted=session_restart_attempted,
            final_error=str(last_exception),
            final_error_type=type(last_exception).__name__ if last_exception else "Unknown"
        )
        
        # Return failed result
        return R2CommandResult(
            command=cmd.command,
            output=None,
            execution_time=0.0,
            success=False,
            error_message=str(last_exception),
            retry_count=self.max_retries,
            session_restarted=session_restart_attempted
        )
    
    async def _execute_single_command(self, cmd: R2Command) -> Any:
        """Execute single command with timeout."""
        loop = asyncio.get_running_loop()
        
        def _run_command():
            try:
                if cmd.expected_output_type == "json":
                    return self._r2_pipe.cmdj(cmd.command)
                else:
                    return self._r2_pipe.cmd(cmd.command)
            except Exception as e:
                self.logger.error(
                    "R2 command execution error",
                    command=cmd.command,
                    error=str(e)
                )
                raise
        
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, _run_command),
                timeout=cmd.timeout
            )
            
            self.logger.debug(
                "Command executed successfully",
                command=cmd.command,
                output_size=len(str(result)) if result else 0
            )
            
            return result
            
        except asyncio.TimeoutError:
            self.logger.error(
                "Command timed out",
                command=cmd.command,
                timeout=cmd.timeout
            )
            raise R2TimeoutException(
                f"Command '{cmd.command}' timed out after {cmd.timeout} seconds"
            )
    
    async def get_file_info(self) -> Dict[str, Any]:
        """Get basic file information."""
        result = await self.execute_command("ij", cache_result=True)
        if not result.success:
            raise R2SessionException(f"Failed to get file info: {result.error_message}")
        
        return result.output
    
    async def extract_functions(self, analysis_depth: str = "standard") -> List[Dict[str, Any]]:
        """
        Extract functions for decompilation.
        
        Args:
            analysis_depth: Analysis depth (basic, standard, comprehensive)
            
        Returns:
            List of function information with addresses and metadata
        """
        # Simplified analysis for decompilation focus
        analysis_commands = {
            "basic": ["aa"],       # Basic function discovery
            "standard": ["aaa"],   # Function analysis with imports
            "comprehensive": ["aaaa"] # Full analysis (for complex binaries)
        }
        
        commands = analysis_commands.get(analysis_depth, ["aaa"])
        
        # Run minimal analysis for function extraction
        for cmd in commands:
            result = await self.execute_command(cmd, timeout=60.0)  # Reduced timeout
            if not result.success:
                self.logger.warning(
                    "Function discovery failed",
                    command=cmd,
                    error=result.error_message
                )
        
        # Get function list with basic info
        result = await self.execute_command("aflj", cache_result=True)
        if not result.success:
            raise R2SessionException(f"Failed to extract functions: {result.error_message}")
        
        functions = result.output or []
        self.logger.info(f"DEBUG: extracted {len(functions)} functions from radare2")
        return functions
    
    async def get_strings(self, min_length: int = 4) -> List[Dict[str, Any]]:
        """Get strings from the binary (simplified version)."""
        return await self.get_strings_with_context(min_length)
    
    async def get_imports(self) -> List[Dict[str, Any]]:
        """Get imported functions (enhanced version with context)."""
        return await self.get_import_details()
    
    async def get_exports(self) -> List[Dict[str, Any]]:
        """Get exported functions."""
        result = await self.execute_command("iEj", cache_result=True)
        
        if not result.success:
            raise R2SessionException(f"Failed to get exports: {result.error_message}")
        
        return result.output or []
    
    async def get_sections(self) -> List[Dict[str, Any]]:
        """Get binary sections."""
        result = await self.execute_command("iSj", cache_result=True)
        
        if not result.success:
            raise R2SessionException(f"Failed to get sections: {result.error_message}")
        
        return result.output or []
    
    async def disassemble_function(
        self,
        function_address: Union[str, int],
        instruction_limit: int = 100
    ) -> str:
        """
        Disassemble a specific function.
        
        Args:
            function_address: Function address (hex string or int)
            instruction_limit: Maximum instructions to disassemble
            
        Returns:
            Disassembly text
        """
        if isinstance(function_address, int):
            function_address = f"0x{function_address:x}"
        
        command = f"pdf @ {function_address}"
        result = await self.execute_command(command, expected_type="text")
        
        if not result.success:
            raise R2SessionException(
                f"Failed to disassemble function at {function_address}: {result.error_message}"
            )
        
        return result.output or ""
    
    async def get_function_assembly(
        self, 
        function_address: Union[str, int],
        include_comments: bool = True,
        max_instructions: int = 200
    ) -> Dict[str, Any]:
        """
        Extract assembly code for a function optimized for LLM consumption.
        
        Args:
            function_address: Function address (hex string or int)
            include_comments: Include r2 comments and analysis
            max_instructions: Maximum number of instructions to extract
            
        Returns:
            Dict containing assembly code, metadata, and context
        """
        if isinstance(function_address, int):
            function_address = f"0x{function_address:x}"
        
        # Get function info
        info_cmd = f"afij @ {function_address}"
        info_result = await self.execute_command(info_cmd)
        
        function_info = {}
        if info_result.success and info_result.output:
            function_info = info_result.output[0] if isinstance(info_result.output, list) else {}
        
        # Get disassembly with context
        # Use pdr instead of pdf to handle cases where "Linear size differs too much from the bbsum"
        disasm_cmd = f"pdr @ {function_address}"
        if not include_comments:
            disasm_cmd = f"pD {max_instructions} @ {function_address}"
            
        disasm_result = await self.execute_command(disasm_cmd, expected_type="text")
        
        if not disasm_result.success:
            raise R2SessionException(
                f"Failed to get assembly for function at {function_address}: {disasm_result.error_message}"
            )
        
        # Get cross-references
        xrefs_cmd = f"axtj @ {function_address}"
        xrefs_result = await self.execute_command(xrefs_cmd)
        xrefs = xrefs_result.output or [] if xrefs_result.success else []
        
        return {
            "address": function_address,
            "assembly": disasm_result.output or "",
            "function_info": function_info,
            "cross_references": xrefs,
            "instruction_count": len([line for line in (disasm_result.output or "").split('\n') if line.strip() and not line.startswith(';')])
        }
    
    async def get_strings_with_context(self, min_length: int = 4) -> List[Dict[str, Any]]:
        """
        Get strings with usage context and cross-references for LLM analysis.
        
        Args:
            min_length: Minimum string length
            
        Returns:
            List of strings with context information
        """
        # Get all strings
        strings_result = await self.execute_command("izj", cache_result=True)
        if not strings_result.success:
            raise R2SessionException(f"Failed to get strings: {strings_result.error_message}")
        
        strings = strings_result.output or []
        enhanced_strings = []
        
        for string_data in strings:
            if string_data.get('length', 0) < min_length:
                continue
                
            # Get cross-references for this string
            string_addr = string_data.get('vaddr', 0)
            if string_addr:
                xrefs_cmd = f"axtj @ 0x{string_addr:x}"
                xrefs_result = await self.execute_command(xrefs_cmd)
                xrefs = xrefs_result.output or [] if xrefs_result.success else []
                
                string_data['cross_references'] = xrefs
                string_data['usage_count'] = len(xrefs)
            
            enhanced_strings.append(string_data)
        
        return enhanced_strings
    
    async def get_import_details(self) -> List[Dict[str, Any]]:
        """
        Get detailed import information with function signatures and usage context.
        
        Returns:
            List of imports with enhanced metadata
        """
        # Get basic imports
        imports_result = await self.execute_command("iij", cache_result=True)
        if not imports_result.success:
            raise R2SessionException(f"Failed to get imports: {imports_result.error_message}")
        
        imports = imports_result.output or []
        enhanced_imports = []
        
        for import_data in imports:
            # Get cross-references for each import
            import_addr = import_data.get('plt', 0) or import_data.get('vaddr', 0)
            if import_addr:
                xrefs_cmd = f"axtj @ 0x{import_addr:x}"
                xrefs_result = await self.execute_command(xrefs_cmd)
                xrefs = xrefs_result.output or [] if xrefs_result.success else []
                
                import_data['cross_references'] = xrefs
                import_data['usage_count'] = len(xrefs)
            
            enhanced_imports.append(import_data)
        
        return enhanced_imports
    
    async def format_assembly_for_llm(self, assembly_text: str) -> str:
        """
        Format assembly code for optimal LLM consumption.
        
        Args:
            assembly_text: Raw assembly output from r2
            
        Returns:
            Formatted assembly text with consistent structure
        """
        if not assembly_text:
            return ""
            
        lines = assembly_text.split('\n')
        formatted_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines and header/footer
            if not stripped or stripped.startswith('/') or '0x' not in stripped:
                continue
                
            # Clean up instruction formatting
            # Extract address, instruction, and operands
            parts = stripped.split(None, 2)  # Split into max 3 parts
            if len(parts) >= 2:
                address = parts[0]
                instruction = parts[1] if len(parts) > 1 else ""
                operands = parts[2] if len(parts) > 2 else ""
                
                # Format consistently: address: instruction operands
                formatted_line = f"{address}: {instruction}"
                if operands:
                    formatted_line += f" {operands}"
                    
                formatted_lines.append(formatted_line)
        
        return '\n'.join(formatted_lines)
    
    async def get_address_mapping(self, start_addr: Union[str, int], size: int = 100) -> Dict[str, str]:
        """
        Get address-to-symbol mapping for debugging and reference.
        
        Args:
            start_addr: Starting address 
            size: Number of bytes to map
            
        Returns:
            Dict mapping addresses to symbol names and information
        """
        if isinstance(start_addr, int):
            start_addr = f"0x{start_addr:x}"
            
        # Get symbols in range
        symbols_cmd = f"isj"
        symbols_result = await self.execute_command(symbols_cmd, cache_result=True)
        
        mapping = {}
        if symbols_result.success and symbols_result.output:
            for symbol in symbols_result.output:
                addr = symbol.get('vaddr', 0)
                name = symbol.get('name', '')
                if addr and name:
                    mapping[f"0x{addr:x}"] = name
        
        return mapping
    
    async def cleanup(self) -> None:
        """Clean up session resources."""
        self.logger.info("Cleaning up R2 session")
        
        try:
            if self._r2_pipe:
                # Close r2pipe session
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._close_r2pipe)
                self._r2_pipe = None
            
            # Remove temporary file if created
            if self._temp_file_path and os.path.exists(self._temp_file_path):
                await asyncio.get_running_loop().run_in_executor(
                    None,
                    os.unlink,
                    self._temp_file_path
                )
                self.logger.debug("Removed temporary file", path=self._temp_file_path)
                self._temp_file_path = None
            
            # Clear cache
            self._command_cache.clear()
            
            self._state = R2SessionState.CLOSED
            self.logger.info("R2 session cleanup completed")
            
        except Exception as e:
            self.logger.error(
                "Error during R2 session cleanup",
                error=str(e)
            )
            self._state = R2SessionState.ERROR
    
    def _close_r2pipe(self) -> None:
        """Close r2pipe (runs in thread pool)."""
        try:
            if hasattr(self._r2_pipe, 'quit'):
                self._r2_pipe.quit()
            else:
                # Fallback for different r2pipe versions
                self._r2_pipe = None
        except Exception as e:
            self.logger.warning("Error closing r2pipe", error=str(e))
    
    async def _check_session_health(self) -> bool:
        """
        Check if R2 session is healthy and responsive (ADR: crash recovery).
        
        Returns:
            True if session is healthy, False otherwise
        """
        if not self._r2_pipe or self._state in [R2SessionState.ERROR, R2SessionState.CLOSED]:
            return False
        
        try:
            # Quick health check command
            def _health_check():
                try:
                    # Simple command that should always work
                    result = self._r2_pipe.cmd("?V")  # Get version
                    return result is not None
                except Exception:
                    return False
            
            # Run health check with short timeout
            loop = asyncio.get_running_loop()
            is_healthy = await asyncio.wait_for(
                loop.run_in_executor(None, _health_check),
                timeout=2.0
            )
            
            if not is_healthy:
                self.logger.warning(
                    "R2 session health check failed",
                    session_id=self._session_id,
                    state=self._state.value
                )
            
            return is_healthy
            
        except Exception as e:
            self.logger.error(
                "R2 session health check exception",
                session_id=self._session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    async def _attempt_session_restart(self) -> bool:
        """
        Attempt to restart the R2 session after a crash (ADR: crash recovery).
        
        Returns:
            True if restart was successful, False otherwise
        """
        self.logger.info(
            "Attempting R2 session restart",
            session_id=self._session_id,
            file_path=self.file_path
        )
        
        try:
            # Clean up existing session
            if self._r2_pipe:
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self._close_r2pipe)
                except Exception as cleanup_error:
                    self.logger.warning(
                        "Error during session cleanup before restart",
                        error=str(cleanup_error)
                    )
                finally:
                    self._r2_pipe = None
            
            # Clear command cache as it may be stale
            self._command_cache.clear()
            
            # Reset state
            self._state = R2SessionState.INITIALIZING
            
            # Re-initialize the session
            await self.initialize()
            
            # Verify the restart was successful
            if await self._check_session_health():
                self.logger.info(
                    "R2 session restart successful",
                    session_id=self._session_id
                )
                return True
            else:
                self.logger.error(
                    "R2 session restart failed health check",
                    session_id=self._session_id
                )
                self._state = R2SessionState.ERROR
                return False
                
        except Exception as e:
            self.logger.error(
                "R2 session restart failed",
                session_id=self._session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            self._state = R2SessionState.ERROR
            return False
    
    def _should_restart_for_error(self, error: Exception) -> bool:
        """
        Simplified error restart logic for decompilation operations.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if restart should be attempted, False otherwise
        """
        # Restart only for critical process-related errors
        restart_error_types = (
            ConnectionError, ProcessLookupError, BrokenPipeError
        )
        
        if isinstance(error, restart_error_types):
            return True
        
        # Restart for essential error indicators only
        error_str = str(error).lower()
        restart_indicators = [
            'broken pipe', 'process not found', 'session closed'
        ]
        
        return any(indicator in error_str for indicator in restart_indicators)


@asynccontextmanager
async def r2_session(
    file_path: Optional[str] = None,
    file_content: Optional[bytes] = None,
    **kwargs
) -> AsyncIterator[R2Session]:
    """
    Context manager for R2 sessions with automatic cleanup.
    
    Args:
        file_path: Path to binary file
        file_content: Binary content
        **kwargs: Additional R2Session arguments
        
    Yields:
        Initialized R2Session instance
        
    Example:
        async with r2_session(file_path="/path/to/binary.exe") as r2:
            file_info = await r2.get_file_info()
            functions = await r2.analyze_functions("standard")
    """
    session = R2Session(
        file_path=file_path,
        file_content=file_content,
        **kwargs
    )
    
    try:
        await session.initialize()
        yield session
    finally:
        await session.cleanup()