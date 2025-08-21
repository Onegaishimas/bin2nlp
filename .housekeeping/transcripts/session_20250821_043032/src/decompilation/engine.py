"""
Binary Decompilation Engine - Simplified orchestrator for decompilation and LLM translation.

This module provides the primary DecompilationEngine class that coordinates
radare2 decompilation and LLM translation following the simplified architecture.

Replaces the complex BinaryAnalysisEngine with a focused approach:
1. File validation
2. Radare2 decompilation
3. LLM translation 
4. Structured response
"""

import asyncio
import time
import hashlib
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from pydantic import BaseModel, Field

from ..models.shared.enums import FileFormat, Platform
from ..models.analysis.basic_results import (
    BasicDecompilationResult, DecompilationMetadata,
    BasicFunctionInfo, BasicStringInfo, BasicImportInfo
)
from ..models.decompilation.results import (
    DecompilationResult, FunctionTranslation, ImportTranslation, 
    StringTranslation, OverallSummary, LLMProviderMetadata
)
from .r2_session import R2Session
from ..core.exceptions import BinaryAnalysisException
from ..core.logging import get_logger, time_operation
from ..core.metrics import (
    time_async_operation, OperationType, 
    increment_counter, record_histogram, set_gauge
)

logger = get_logger(__name__)


class DecompilationConfig(BaseModel):
    """Configuration for the decompilation engine."""
    
    # File processing
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum file size in megabytes"
    )
    
    timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=1800,
        description="Maximum decompilation time"
    )
    
    # Radare2 settings
    r2_analysis_level: str = Field(
        default="aa",
        description="Radare2 analysis command level (aa, aaa, aaaa)"
    )
    
    extract_functions: bool = Field(
        default=True,
        description="Extract function information"
    )
    
    extract_strings: bool = Field(
        default=True,
        description="Extract string information"
    )
    
    extract_imports: bool = Field(
        default=True,
        description="Extract import information"
    )
    
    # Output settings
    include_assembly_code: bool = Field(
        default=True,
        description="Include raw assembly code in function results"
    )
    
    max_functions: Optional[int] = Field(
        default=None,
        description="Maximum number of functions to process (None = all)"
    )
    
    max_strings: Optional[int] = Field(
        default=None,
        description="Maximum number of strings to process (None = all)"
    )


class DecompilationEngineException(BinaryAnalysisException):
    """Exception raised by the decompilation engine."""
    pass


class DecompilationEngine:
    """
    Simplified binary decompilation engine for radare2 + LLM translation.
    
    Coordinates basic binary decompilation and prepares data for LLM translation.
    Focused approach without complex processor orchestration or error recovery.
    """
    
    def __init__(self, config: Optional[DecompilationConfig] = None):
        """Initialize the decompilation engine."""
        self.config = config or DecompilationConfig()
        
        logger.info(
            "decompilation_engine_initialized",
            max_file_size_mb=self.config.max_file_size_mb,
            timeout_seconds=self.config.timeout_seconds,
            r2_analysis_level=self.config.r2_analysis_level,
            extract_functions=self.config.extract_functions,
            extract_strings=self.config.extract_strings,
            extract_imports=self.config.extract_imports
        )
    
    async def decompile_binary(self, file_path: str) -> BasicDecompilationResult:
        """
        Perform basic binary decompilation using radare2.
        
        Args:
            file_path: Path to binary file to decompile
            
        Returns:
            BasicDecompilationResult with decompilation data ready for LLM translation
            
        Raises:
            DecompilationEngineException: If decompilation fails
        """
        file_path_obj = Path(file_path)
        
        # Track timing manually for the result object
        start_time = time.perf_counter()
        
        try:
            # Get file size after validation
            try:
                file_size_mb = file_path_obj.stat().st_size / 1024 / 1024
            except FileNotFoundError:
                raise DecompilationEngineException(f"File not found: {file_path}")
            
            # Track metrics for this decompilation operation
            async with time_async_operation(
                OperationType.DECOMPILATION,
                "radare2_decompilation",
                file_size_mb=round(file_size_mb, 2),
                file_name=file_path_obj.name,
                file_extension=file_path_obj.suffix.lower()
            ):
                try:
                    # Increment decompilation attempt counter
                    increment_counter("decompilation_attempts", 1, 
                                    file_extension=file_path_obj.suffix.lower())
                    
                    # Step 1: File validation
                    await self._validate_file(file_path)
                    
                    # Step 2: Calculate file metadata
                    metadata = await self._create_metadata(file_path)
                    
                    # Step 3: Radare2 decompilation with timing
                    functions, imports, strings = await self._perform_r2_decompilation(file_path)
                    
                    # Calculate actual duration
                    duration_seconds = time.perf_counter() - start_time
                    
                    # Step 4: Create basic result
                    result = BasicDecompilationResult(
                        decompilation_id=self._generate_id(),
                        metadata=metadata,
                        functions=functions,
                        imports=imports,
                        strings=strings,
                        success=True,
                        duration_seconds=duration_seconds
                    )
                    
                    # Record detailed metrics
                    record_histogram("decompilation_file_size_mb", file_size_mb)
                    record_histogram("decompilation_function_count", len(functions))
                    record_histogram("decompilation_import_count", len(imports))
                    record_histogram("decompilation_string_count", len(strings))
                    
                    # Set current gauges
                    set_gauge("last_decompilation_functions", len(functions))
                    set_gauge("last_decompilation_imports", len(imports))
                    set_gauge("last_decompilation_strings", len(strings))
                    
                    logger.info(
                        "decompilation_completed",
                        file_path=file_path,
                        function_count=len(functions),
                        import_count=len(imports),
                        string_count=len(strings),
                        file_size_mb=round(file_size_mb, 2),
                        decompilation_id=result.decompilation_id
                    )
                    
                    increment_counter("decompilation_success", 1,
                                    file_extension=file_path_obj.suffix.lower())
                    
                    return result
                    
                except Exception as e:
                    # Record failure metrics
                    increment_counter("decompilation_failures", 1,
                                    file_extension=file_path_obj.suffix.lower(),
                                    error_type=e.__class__.__name__)
                    
                    logger.error(
                        "decompilation_failed",
                        file_path=file_path,
                        error=str(e),
                        error_type=e.__class__.__name__,
                        file_size_mb=round(file_size_mb, 2)
                    )
                    
                    # Re-raise to let the metrics context manager handle timing and the exception
                    raise
                    
        except Exception as e:
            # Handle cases where we can't even get file stats (file doesn't exist, etc.)
            logger.error(
                "decompilation_failed",
                file_path=file_path,
                error=str(e),
                error_type=e.__class__.__name__
            )
            
            # Create minimal result for file not found scenarios
            duration_seconds = time.perf_counter() - start_time
            
            # Create minimal metadata
            metadata = DecompilationMetadata(
                file_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
                file_size=1,  # Minimum valid size
                file_format=FileFormat.UNKNOWN,
                platform=Platform.UNKNOWN
            )
            
            result = BasicDecompilationResult(
                decompilation_id=self._generate_id(),
                metadata=metadata,
                functions=[],
                imports=[],
                strings=[],
                success=False,
                duration_seconds=duration_seconds,
                errors=[str(e)]
            )
            
            return result
    
    async def _validate_file(self, file_path: str) -> None:
        """Validate file exists and is within size limits."""
        path = Path(file_path)
        
        if not path.exists():
            raise DecompilationEngineException(f"File not found: {file_path}")
        
        if not path.is_file():
            raise DecompilationEngineException(f"Path is not a file: {file_path}")
        
        # Check file size
        file_size = path.stat().st_size
        max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            raise DecompilationEngineException(
                f"File too large: {file_size} bytes (max: {max_size_bytes})"
            )
        
        if file_size == 0:
            raise DecompilationEngineException("File is empty")
    
    async def _create_metadata(self, file_path: str) -> DecompilationMetadata:
        """Create basic file metadata."""
        path = Path(file_path)
        file_size = path.stat().st_size
        
        # Calculate SHA-256 hash
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        file_hash = f"sha256:{hasher.hexdigest()}"
        
        # Basic file format detection (simplified)
        file_format = self._detect_file_format(file_path)
        platform = self._detect_platform(file_format)
        
        return DecompilationMetadata(
            file_hash=file_hash,
            file_size=file_size,
            file_format=file_format,
            platform=platform,
            decompilation_tool="radare2"
        )
    
    def _detect_file_format(self, file_path: str) -> FileFormat:
        """Simple file format detection based on file headers."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)
            
            # PE format
            if len(header) >= 2 and header[:2] == b'MZ':
                return FileFormat.PE
            
            # ELF format
            elif len(header) >= 4 and header[:4] == b'\x7fELF':
                return FileFormat.ELF
            
            # Mach-O format
            elif len(header) >= 4 and header[:4] in [b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe']:
                return FileFormat.MACHO
            
            # Java class file
            elif len(header) >= 4 and header[:4] == b'\xca\xfe\xba\xbe':
                return FileFormat.JAVA_CLASS
            
            else:
                return FileFormat.UNKNOWN
                
        except Exception:
            return FileFormat.UNKNOWN
    
    def _detect_platform(self, file_format: FileFormat) -> Platform:
        """Detect platform based on file format."""
        if file_format == FileFormat.PE:
            return Platform.WINDOWS
        elif file_format == FileFormat.ELF:
            return Platform.LINUX
        elif file_format == FileFormat.MACHO:
            return Platform.MACOS
        elif file_format == FileFormat.JAVA:
            return Platform.JAVA
        else:
            return Platform.UNKNOWN
    
    async def _perform_r2_decompilation(self, file_path: str) -> tuple[
        List[BasicFunctionInfo], 
        List[BasicImportInfo], 
        List[BasicStringInfo]
    ]:
        """Perform radare2 decompilation and extract data."""
        
        functions = []
        imports = []
        strings = []
        
        try:
            # Use radare2 integration
            async with R2Session(file_path) as r2:
                # No explicit analysis needed - extract_functions will handle it
                
                # Extract functions
                if self.config.extract_functions:
                    functions = await self._extract_functions(r2)
                
                # Extract imports  
                if self.config.extract_imports:
                    imports = await self._extract_imports(r2)
                
                # Extract strings
                if self.config.extract_strings:
                    strings = await self._extract_strings(r2)
            
        except Exception as e:
            logger.warning(
                "r2_decompilation_partial_failure",
                file_path=file_path,
                error=str(e)
            )
            # Continue with partial results
        
        return functions, imports, strings
    
    async def _extract_functions(self, r2: R2Session) -> List[BasicFunctionInfo]:
        """Extract function information from radare2."""
        functions = []
        
        try:
            # Get function list using R2Session method
            func_data = await r2.extract_functions(self.config.r2_analysis_level)
            
            if not func_data:
                return functions
            
            # Limit number of functions if specified
            if self.config.max_functions:
                func_data = func_data[:self.config.max_functions]
            
            for func in func_data:
                try:
                    # Get basic function info
                    name = func.get('name', f"fcn_{func.get('offset', 0):08x}")
                    address = f"0x{func.get('offset', 0):08x}"
                    size = func.get('size', 0)
                    
                    # Get assembly code if requested
                    assembly_code = None
                    if self.config.include_assembly_code and size > 0:
                        try:
                            assembly_code = await r2.get_function_assembly(address)
                        except Exception:
                            pass  # Skip assembly if it fails
                    
                    # Get cross-references (calls) - simplified for now
                    calls_to = []
                    calls_from = []
                    # Cross-reference extraction will be handled by assembly analysis
                    
                    function_info = BasicFunctionInfo(
                        name=name,
                        address=address,
                        size=size,
                        assembly_code=assembly_code,
                        calls_to=calls_to,
                        calls_from=calls_from
                    )
                    
                    functions.append(function_info)
                    
                except Exception as e:
                    logger.debug("function_extraction_error", func=func, error=str(e))
                    continue
            
        except Exception as e:
            logger.warning("functions_extraction_failed", error=str(e))
        
        return functions
    
    async def _extract_imports(self, r2: R2Session) -> List[BasicImportInfo]:
        """Extract import information from radare2."""
        imports = []
        
        try:
            # Get import list using R2Session method
            import_data = await r2.get_imports()
            
            if not import_data:
                return imports
            
            for imp in import_data:
                try:
                    library_name = imp.get('libname', 'unknown')
                    function_name = imp.get('name')
                    ordinal = imp.get('ordinal')
                    address = imp.get('plt')
                    
                    if address:
                        address = f"0x{address:08x}"
                    
                    import_info = BasicImportInfo(
                        library_name=library_name,
                        function_name=function_name,
                        ordinal=ordinal,
                        address=address
                    )
                    
                    imports.append(import_info)
                    
                except Exception as e:
                    logger.debug("import_extraction_error", imp=imp, error=str(e))
                    continue
                    
        except Exception as e:
            logger.warning("imports_extraction_failed", error=str(e))
        
        return imports
    
    async def _extract_strings(self, r2: R2Session) -> List[BasicStringInfo]:
        """Extract string information from radare2."""
        strings = []
        
        try:
            # Get string list using R2Session method
            string_data = await r2.get_strings(min_length=3)
            
            if not string_data:
                return strings
            
            # Limit number of strings if specified
            if self.config.max_strings:
                string_data = string_data[:self.config.max_strings]
            
            for string_entry in string_data:
                try:
                    value = string_entry.get('string', '')
                    address = string_entry.get('vaddr', 0)
                    size = string_entry.get('size', len(value))
                    section = string_entry.get('section', '')
                    
                    # Skip empty strings
                    if not value.strip():
                        continue
                    
                    address_hex = f"0x{address:08x}" if isinstance(address, int) else str(address)
                    
                    # Determine encoding
                    encoding = "ascii"
                    if string_entry.get('type') == 'utf16':
                        encoding = "utf-16"
                    elif string_entry.get('type') == 'utf32':
                        encoding = "utf-32"
                    
                    string_info = BasicStringInfo(
                        value=value,
                        address=address_hex,
                        size=size,
                        encoding=encoding,
                        section=section
                    )
                    
                    strings.append(string_info)
                    
                except Exception as e:
                    logger.debug("string_extraction_error", string=string_entry, error=str(e))
                    continue
                    
        except Exception as e:
            logger.warning("strings_extraction_failed", error=str(e))
        
        return strings
    
    def _generate_id(self) -> str:
        """Generate unique decompilation ID."""
        import uuid
        return str(uuid.uuid4())


# Factory function for creating decompilation engine
def create_decompilation_engine(config: Optional[DecompilationConfig] = None) -> DecompilationEngine:
    """Create a new decompilation engine instance."""
    return DecompilationEngine(config)


# Convenience function for one-off decompilation
async def decompile_file(file_path: str, config: Optional[DecompilationConfig] = None) -> BasicDecompilationResult:
    """
    Convenience function to decompile a single file.
    
    Args:
        file_path: Path to binary file
        config: Optional configuration
        
    Returns:
        BasicDecompilationResult with decompilation data
    """
    engine = create_decompilation_engine(config)
    return await engine.decompile_binary(file_path)