"""
Base classes for binary analysis engines.

Provides abstract base classes and interfaces for implementing
analysis engines that can process different binary formats.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

from ...core.exceptions import AnalysisException
from ...core.logging import get_logger
from ...models.analysis.config import AnalysisConfig
from ...models.analysis.results import AnalysisResult
from ...models.shared.enums import FileFormat, Platform, AnalysisDepth


class AnalysisEngine(ABC):
    """
    Abstract base class for binary analysis engines.
    
    Defines the common interface that all analysis engines must implement,
    providing standardized methods for file analysis, result generation,
    and error handling.
    """
    
    def __init__(self, name: str):
        """
        Initialize analysis engine.
        
        Args:
            name: Human-readable name of the analysis engine
        """
        self.name = name
        self.logger = get_logger(f"{__name__}.{name}")
        self._supported_formats: List[FileFormat] = []
        self._supported_platforms: List[Platform] = []
    
    @property
    def supported_formats(self) -> List[FileFormat]:
        """Get list of supported file formats."""
        return self._supported_formats.copy()
    
    @property
    def supported_platforms(self) -> List[Platform]:
        """Get list of supported platforms."""
        return self._supported_platforms.copy()
    
    def supports_format(self, file_format: FileFormat) -> bool:
        """Check if engine supports a specific file format."""
        return file_format in self._supported_formats
    
    def supports_platform(self, platform: Platform) -> bool:
        """Check if engine supports a specific platform."""
        return platform in self._supported_platforms
    
    @abstractmethod
    async def analyze_file(
        self,
        file_path: Union[str, Path],
        config: AnalysisConfig
    ) -> AnalysisResult:
        """
        Analyze a binary file and return comprehensive results.
        
        Args:
            file_path: Path to the binary file to analyze
            config: Analysis configuration and parameters
            
        Returns:
            Complete analysis results
            
        Raises:
            AnalysisException: If analysis fails
        """
        pass
    
    @abstractmethod
    async def validate_file(
        self,
        file_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        Validate that a file can be analyzed by this engine.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            Dictionary with validation results and metadata
            
        Raises:
            AnalysisException: If validation fails
        """
        pass
    
    async def get_file_info(
        self,
        file_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        Get basic file information without full analysis.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Basic file metadata and format information
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise AnalysisException(f"File not found: {file_path}")
            
            stat = path.stat()
            return {
                'file_path': str(path.absolute()),
                'file_name': path.name,
                'file_size': stat.st_size,
                'modified_time': stat.st_mtime,
                'engine': self.name
            }
            
        except Exception as e:
            raise AnalysisException(
                f"Failed to get file info: {str(e)}",
                file_path=str(file_path),
                component=self.name
            )
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Perform health check on the analysis engine.
        
        Returns:
            Health status and engine information
        """
        return {
            'engine_name': self.name,
            'status': 'healthy',
            'supported_formats': [fmt.value for fmt in self.supported_formats],
            'supported_platforms': [plat.value for plat in self.supported_platforms]
        }
    
    def _validate_config(self, config: AnalysisConfig) -> None:
        """
        Validate analysis configuration for this engine.
        
        Args:
            config: Configuration to validate
            
        Raises:
            AnalysisException: If configuration is invalid
        """
        if not isinstance(config, AnalysisConfig):
            raise AnalysisException(
                "Invalid configuration type",
                component=self.name
            )
        
        # Validate timeout is reasonable
        if config.timeout_seconds < 1 or config.timeout_seconds > 7200:  # Max 2 hours
            raise AnalysisException(
                f"Invalid timeout: {config.timeout_seconds}s (must be 1-7200)",
                component=self.name
            )
    
    def __str__(self) -> str:
        """String representation of the engine."""
        return f"{self.__class__.__name__}(name='{self.name}')"
    
    def __repr__(self) -> str:
        """Detailed representation of the engine."""
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"formats={len(self.supported_formats)}, "
            f"platforms={len(self.supported_platforms)}"
            f")"
        )


class MockAnalysisEngine(AnalysisEngine):
    """
    Mock analysis engine for testing purposes.
    
    Provides a simple implementation that can be used in unit tests
    without requiring external dependencies like radare2.
    """
    
    def __init__(self):
        super().__init__("mock")
        self._supported_formats = [FileFormat.PE, FileFormat.ELF, FileFormat.MACHO]
        self._supported_platforms = [Platform.WINDOWS, Platform.LINUX, Platform.MACOS]
    
    async def analyze_file(
        self,
        file_path: Union[str, Path],
        config: AnalysisConfig
    ) -> AnalysisResult:
        """Mock analysis that returns basic results."""
        self._validate_config(config)
        
        file_info = await self.get_file_info(file_path)
        
        # Create mock results
        from ...models.analysis.results import AnalysisResult, SecurityFindings, FunctionInfo
        
        return AnalysisResult(
            file_hash=f"mock_hash_{Path(file_path).name}",
            file_format=FileFormat.PE,
            file_size=file_info['file_size'],
            platform=Platform.WINDOWS,
            analysis_depth=config.depth,
            functions=[
                FunctionInfo(
                    name="main",
                    address="0x401000",
                    size=256,
                    function_type="user",
                    calling_convention="cdecl"
                )
            ],
            security=SecurityFindings(),
            analysis_time_seconds=1.0,
            metadata={
                'engine': self.name,
                'mock': True
            }
        )
    
    async def validate_file(
        self,
        file_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """Mock validation that accepts all files."""
        file_info = await self.get_file_info(file_path)
        
        return {
            'valid': True,
            'format': FileFormat.PE.value,
            'platform': Platform.WINDOWS.value,
            'size': file_info['file_size'],
            'engine': self.name
        }