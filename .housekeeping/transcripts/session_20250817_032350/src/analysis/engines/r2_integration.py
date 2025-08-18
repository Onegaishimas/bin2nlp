"""
Radare2 integration layer for binary analysis.

Provides a robust wrapper around r2pipe with connection management,
error handling, timeout support, and resource cleanup.
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

from ...core.logging import get_logger
from ...core.exceptions import BinaryAnalysisException, AnalysisTimeoutException
from ...models.shared.enums import Platform, FileFormat


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
        self.r2_flags = r2_flags or ['-2', '-q']  # quiet mode, no colors
        
        self._r2_pipe: Optional[r2pipe.open_sync] = None
        self._temp_file_path: Optional[str] = None
        self._state = R2SessionState.INITIALIZING
        self._command_cache: Dict[str, R2CommandResult] = {}
        self._session_id = f"r2_{int(time.time() * 1000)}"
        
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
            loop = asyncio.get_event_loop()
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
        return r2pipe.open(
            filename=self.file_path,
            flags=self.r2_flags
        )
    
    async def _create_temp_file(self) -> str:
        """Create temporary file from file content."""
        loop = asyncio.get_event_loop()
        
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
        if not self.is_ready:
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
        """Execute command with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                self._state = R2SessionState.BUSY
                
                start_time = time.time()
                
                # Execute command with timeout
                result = await self._execute_single_command(cmd)
                
                execution_time = time.time() - start_time
                
                self._state = R2SessionState.READY
                
                return R2CommandResult(
                    command=cmd.command,
                    output=result,
                    execution_time=execution_time,
                    success=True,
                    retry_count=attempt
                )
                
            except asyncio.TimeoutError as e:
                last_exception = e
                self.logger.warning(
                    "Command timeout",
                    command=cmd.command,
                    attempt=attempt + 1,
                    timeout=cmd.timeout
                )
                if attempt >= self.max_retries:
                    break
                    
                # Brief pause before retry
                await asyncio.sleep(0.5 * (attempt + 1))
                
            except Exception as e:
                last_exception = e
                self.logger.warning(
                    "Command execution failed",
                    command=cmd.command,
                    attempt=attempt + 1,
                    error=str(e)
                )
                if attempt >= self.max_retries:
                    break
                    
                # Brief pause before retry
                await asyncio.sleep(1.0 * (attempt + 1))
        
        self._state = R2SessionState.ERROR
        
        # Return failed result
        return R2CommandResult(
            command=cmd.command,
            output=None,
            execution_time=0.0,
            success=False,
            error_message=str(last_exception),
            retry_count=self.max_retries
        )
    
    async def _execute_single_command(self, cmd: R2Command) -> Any:
        """Execute single command with timeout."""
        loop = asyncio.get_event_loop()
        
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
    
    async def analyze_functions(self, analysis_depth: str = "standard") -> List[Dict[str, Any]]:
        """
        Analyze functions in the binary.
        
        Args:
            analysis_depth: Analysis depth (quick, standard, comprehensive)
            
        Returns:
            List of function analysis results
        """
        # First run analysis
        analysis_commands = {
            "quick": ["aa"],      # Basic analysis
            "standard": ["aaa"],  # More thorough analysis
            "comprehensive": ["aaaa"]  # Full analysis
        }
        
        commands = analysis_commands.get(analysis_depth, ["aaa"])
        
        # Run analysis commands
        for cmd in commands:
            result = await self.execute_command(cmd, timeout=120.0)
            if not result.success:
                self.logger.warning(
                    "Analysis command failed",
                    command=cmd,
                    error=result.error_message
                )
        
        # Get function list
        result = await self.execute_command("aflj", cache_result=True)
        if not result.success:
            raise R2SessionException(f"Failed to get function list: {result.error_message}")
        
        return result.output or []
    
    async def get_strings(self, min_length: int = 4) -> List[Dict[str, Any]]:
        """Get strings from the binary."""
        command = f"izj~{{length>={min_length}}}"
        result = await self.execute_command(command, cache_result=True)
        
        if not result.success:
            raise R2SessionException(f"Failed to get strings: {result.error_message}")
        
        return result.output or []
    
    async def get_imports(self) -> List[Dict[str, Any]]:
        """Get imported functions."""
        result = await self.execute_command("iij", cache_result=True)
        
        if not result.success:
            raise R2SessionException(f"Failed to get imports: {result.error_message}")
        
        return result.output or []
    
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
    
    async def search_pattern(self, pattern: str, pattern_type: str = "string") -> List[Dict[str, Any]]:
        """
        Search for patterns in the binary.
        
        Args:
            pattern: Pattern to search for
            pattern_type: Type of pattern (string, hex, regex)
            
        Returns:
            List of search results
        """
        command_map = {
            "string": f"/j {pattern}",
            "hex": f"/xj {pattern}",
            "regex": f"/rj {pattern}"
        }
        
        command = command_map.get(pattern_type, f"/j {pattern}")
        result = await self.execute_command(command)
        
        if not result.success:
            raise R2SessionException(f"Failed to search pattern: {result.error_message}")
        
        return result.output or []
    
    async def cleanup(self) -> None:
        """Clean up session resources."""
        self.logger.info("Cleaning up R2 session")
        
        try:
            if self._r2_pipe:
                # Close r2pipe session
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._close_r2pipe)
                self._r2_pipe = None
            
            # Remove temporary file if created
            if self._temp_file_path and os.path.exists(self._temp_file_path):
                await asyncio.get_event_loop().run_in_executor(
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