"""
Binary Analysis Engine - Main orchestrator for comprehensive binary analysis.

This module provides the primary BinaryAnalysisEngine class that coordinates all
analysis processors and aggregates results following the ADR standards.
"""

import asyncio
import time
import aiofiles
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from enum import Enum

import structlog
from pydantic import BaseModel, Field, field_validator

from src.models.shared.enums import AnalysisDepth, FileFormat, Platform
from src.models.analysis.config import AnalysisConfig
from src.models.analysis.results import AnalysisResult, SecurityFindings, FunctionInfo, StringExtraction
from src.analysis.processors.format_detector import FormatDetector, FormatDetectionResult
from src.analysis.processors.function_analyzer import FunctionAnalyzer, FunctionAnalysisResult  
from src.analysis.processors.security_scanner import SecurityScanner, SecurityAnalysisResult
from src.analysis.processors.string_extractor import StringExtractor
from src.analysis.error_recovery import get_recovery_manager, recovery_context
from src.core.exceptions import BinaryAnalysisException
from src.core.config import get_settings
from src.analysis.engines.r2_integration import R2Session

logger = structlog.get_logger(__name__)


class AnalysisPhase(str, Enum):
    """Analysis execution phases."""
    FORMAT_DETECTION = "format_detection"
    FUNCTION_ANALYSIS = "function_analysis"
    SECURITY_SCANNING = "security_scanning"
    STRING_EXTRACTION = "string_extraction"
    RESULT_AGGREGATION = "result_aggregation"


class ProcessorConfig(BaseModel):
    """Configuration for individual analysis processors."""
    
    enabled: bool = Field(default=True, description="Whether processor is enabled")
    timeout_seconds: int = Field(default=300, ge=30, le=3600, description="Processor timeout")
    priority: int = Field(default=1, ge=1, le=10, description="Execution priority (1=highest)")
    required: bool = Field(default=False, description="Whether processor is required for analysis")


class EngineConfig(BaseModel):
    """Configuration for the binary analysis engine."""
    
    analysis_depth: AnalysisDepth = Field(default=AnalysisDepth.STANDARD, description="Analysis depth level")
    focus_areas: Set[str] = Field(default_factory=set, description="Specific analysis focus areas")
    max_analysis_time: int = Field(default=1200, ge=60, le=7200, description="Maximum total analysis time in seconds")
    parallel_execution: bool = Field(default=True, description="Enable parallel processor execution")
    stop_on_critical_error: bool = Field(default=False, description="Stop analysis on critical processor failure")
    
    # Processor configurations
    format_detection: ProcessorConfig = Field(default_factory=lambda: ProcessorConfig(required=True, priority=1))
    function_analysis: ProcessorConfig = Field(default_factory=lambda: ProcessorConfig(priority=2))
    security_scanning: ProcessorConfig = Field(default_factory=lambda: ProcessorConfig(priority=3))
    string_extraction: ProcessorConfig = Field(default_factory=lambda: ProcessorConfig(priority=4))
    
    @field_validator('focus_areas')
    @classmethod
    def validate_focus_areas(cls, v: Set[str]) -> Set[str]:
        """Validate focus areas are recognized."""
        valid_areas = {
            "malware", "vulnerabilities", "crypto", "network", "filesystem", 
            "strings", "functions", "imports", "exports", "certificates"
        }
        invalid_areas = v - valid_areas
        if invalid_areas:
            raise ValueError(f"Invalid focus areas: {invalid_areas}")
        return v


class ProcessorResult(BaseModel):
    """Result from individual processor execution."""
    
    processor_name: str = Field(..., description="Name of the processor")
    phase: AnalysisPhase = Field(..., description="Analysis phase")
    success: bool = Field(..., description="Whether processor succeeded")
    execution_time_ms: int = Field(..., ge=0, description="Processor execution time")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    result_data: Optional[Dict[str, Any]] = Field(default=None, description="Processor-specific results")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Result confidence score")


class AggregatedAnalysisResult(BaseModel):
    """Comprehensive analysis result with all processor outputs."""
    
    file_path: str = Field(..., description="Path to analyzed file")
    file_hash: str = Field(..., description="SHA-256 hash of analyzed file")
    analysis_config: EngineConfig = Field(..., description="Configuration used for analysis")
    
    # Timing information
    total_analysis_time_ms: int = Field(..., ge=0, description="Total analysis time")
    start_timestamp: str = Field(..., description="Analysis start timestamp")
    end_timestamp: str = Field(..., description="Analysis end timestamp")
    
    # Overall results
    analysis_success: bool = Field(..., description="Whether analysis completed successfully")
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall analysis confidence")
    errors_encountered: List[str] = Field(default_factory=list, description="List of errors encountered")
    
    # Processor results
    processor_results: List[ProcessorResult] = Field(default_factory=list, description="Individual processor results")
    
    # Aggregated findings
    format_info: Optional[FormatDetectionResult] = Field(default=None, description="File format detection results")
    function_analysis: Optional[FunctionAnalysisResult] = Field(default=None, description="Function analysis results")
    security_findings: Optional[SecurityAnalysisResult] = Field(default=None, description="Security analysis results")
    string_analysis: Optional[StringExtractionResult] = Field(default=None, description="String extraction results")
    
    # High-level insights
    risk_level: str = Field(default="unknown", description="Overall risk assessment")
    key_findings: List[str] = Field(default_factory=list, description="Key analysis findings")
    recommendations: List[str] = Field(default_factory=list, description="Security recommendations")
    
    # Error recovery and diagnostics
    error_recovery_summary: Dict[str, Any] = Field(default_factory=dict, description="Error recovery summary")
    partial_results_used: bool = Field(default=False, description="Whether partial results were used")
    recovery_actions_taken: List[str] = Field(default_factory=list, description="Recovery actions taken")


class BinaryAnalysisEngineException(BinaryAnalysisException):
    """Exception raised by the binary analysis engine."""
    pass


class BinaryAnalysisEngine:
    """
    Main binary analysis engine that orchestrates all analysis processors.
    
    Coordinates format detection, function analysis, security scanning, and string extraction
    based on configurable analysis depth and focus areas.
    """
    
    def __init__(self, config: Optional[EngineConfig] = None):
        """Initialize the binary analysis engine."""
        self.config = config or EngineConfig()
        self.settings = get_settings()
        
        # Initialize processors
        self.format_detector = FormatDetector()
        self.function_analyzer = FunctionAnalyzer()
        self.security_scanner = SecurityScanner()
        self.string_extractor = StringExtractor()
        
        # Initialize error recovery manager
        self.recovery_manager = get_recovery_manager()
        
        logger.info(
            "binary_analysis_engine_initialized",
            analysis_depth=self.config.analysis_depth.value,
            focus_areas=list(self.config.focus_areas),
            parallel_execution=self.config.parallel_execution,
            error_recovery_enabled=True
        )
    
    async def analyze_binary(self, file_path: str) -> AggregatedAnalysisResult:
        """
        Perform comprehensive binary analysis using all configured processors.
        
        Args:
            file_path: Path to binary file to analyze
            
        Returns:
            AggregatedAnalysisResult with comprehensive analysis results
            
        Raises:
            BinaryAnalysisEngineException: If analysis fails
        """
        start_time = time.time()
        start_timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(start_time))
        
        # Use error recovery context for the entire analysis
        async with recovery_context(
            "binary_analysis",
            timeout_seconds=self.config.max_analysis_time,
            context={"file_path": file_path}
        ) as recovery:
            
            async def _perform_analysis():
                # Validate file exists and is readable
                if not Path(file_path).exists():
                    raise BinaryAnalysisEngineException(f"File not found: {file_path}")
                
                # Calculate file hash for tracking
                file_hash = await self._calculate_file_hash(file_path)
                
                logger.info(
                    "binary_analysis_started",
                    file_path=file_path,
                    file_hash=file_hash[:16] + "...",
                    analysis_depth=self.config.analysis_depth.value
                )
                
                # Initialize result structure
                result = AggregatedAnalysisResult(
                    file_path=file_path,
                    file_hash=file_hash,
                    analysis_config=self.config,
                    total_analysis_time_ms=0,
                    start_timestamp=start_timestamp,
                    end_timestamp="",
                    analysis_success=False,
                    overall_confidence=0.0
                )
                
                # Execute analysis phases with recovery
                await self._execute_analysis_phases_with_recovery(result)
                
                # Aggregate results and calculate confidence
                await self._aggregate_results(result)
                
                # Add recovery information
                recovery_summary = self.recovery_manager.get_error_summary()
                result.error_recovery_summary = recovery_summary
                result.partial_results_used = recovery_summary.get("partial_results_available", 0) > 0
                
                # Get recovery actions taken
                detailed_errors = self.recovery_manager.get_detailed_errors()
                result.recovery_actions_taken = [
                    f"{e.component}:{e.recovery_action.value}" 
                    for e in detailed_errors 
                    if e.recovery_action and e.recovery_attempted
                ]
                
                # Calculate timing
                end_time = time.time()
                result.end_timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(end_time))
                result.total_analysis_time_ms = int((end_time - start_time) * 1000)
                
                # Determine overall success (accounting for partial results)
                critical_failures = [
                    r for r in result.processor_results 
                    if not r.success and self._is_processor_required(r.processor_name)
                ]
                result.analysis_success = len(critical_failures) == 0 or result.partial_results_used
                
                logger.info(
                    "binary_analysis_completed",
                    file_path=file_path,
                    success=result.analysis_success,
                    total_time_ms=result.total_analysis_time_ms,
                    confidence=result.overall_confidence,
                    processors_run=len(result.processor_results),
                    recovery_actions=len(result.recovery_actions_taken),
                    partial_results_used=result.partial_results_used
                )
                
                return result
            
            try:
                return await recovery.execute(_perform_analysis)
            except Exception as e:
                logger.error(
                    "binary_analysis_failed",
                    file_path=file_path,
                    error=str(e),
                    error_type=type(e).__name__
                )
                raise BinaryAnalysisEngineException(f"Binary analysis failed: {str(e)}") from e
    
    async def _execute_analysis_phases_with_recovery(self, result: AggregatedAnalysisResult) -> None:
        """Execute all analysis phases with comprehensive error recovery."""
        
        # Phase 1: Format Detection (always required) with recovery
        if self.config.format_detection.enabled:
            async with recovery_context(
                "format_detection_phase",
                timeout_seconds=self.config.format_detection.timeout_seconds,
                context={"file_path": result.file_path}
            ) as recovery:
                await recovery.execute(lambda: self._execute_format_detection(result))
            
            # Skip further analysis if format detection failed and it's required
            if self.config.format_detection.required:
                format_result = next(
                    (r for r in result.processor_results if r.processor_name == "format_detector"), 
                    None
                )
                if format_result and not format_result.success:
                    logger.warning("skipping_remaining_phases_due_to_format_failure")
                    return
        
        # Determine execution strategy with recovery
        if self.config.parallel_execution:
            await self._execute_phases_parallel_with_recovery(result)
        else:
            await self._execute_phases_sequential_with_recovery(result)
    
    async def _execute_analysis_phases(self, result: AggregatedAnalysisResult) -> None:
        """Execute all analysis phases based on configuration (legacy method)."""
        return await self._execute_analysis_phases_with_recovery(result)
    
    async def _execute_phases_parallel_with_recovery(self, result: AggregatedAnalysisResult) -> None:
        """Execute analysis phases in parallel with comprehensive error recovery."""
        
        # Create recovery-wrapped tasks for all enabled processors
        tasks = []
        
        if self.config.function_analysis.enabled:
            async def function_analysis_task():
                async with recovery_context(
                    "function_analysis_phase",
                    timeout_seconds=self.config.function_analysis.timeout_seconds,
                    context={"file_path": result.file_path}
                ) as recovery:
                    return await recovery.execute(lambda: self._execute_function_analysis(result))
            tasks.append(function_analysis_task())
        
        if self.config.security_scanning.enabled:
            async def security_scanning_task():
                async with recovery_context(
                    "security_scanning_phase", 
                    timeout_seconds=self.config.security_scanning.timeout_seconds,
                    context={"file_path": result.file_path}
                ) as recovery:
                    return await recovery.execute(lambda: self._execute_security_scanning(result))
            tasks.append(security_scanning_task())
        
        if self.config.string_extraction.enabled:
            async def string_extraction_task():
                async with recovery_context(
                    "string_extraction_phase",
                    timeout_seconds=self.config.string_extraction.timeout_seconds,
                    context={"file_path": result.file_path}
                ) as recovery:
                    return await recovery.execute(lambda: self._execute_string_extraction(result))
            tasks.append(string_extraction_task())
        
        # Execute all tasks with timeout and recovery
        if tasks:
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results and log any exceptions
                for i, task_result in enumerate(results):
                    if isinstance(task_result, Exception):
                        logger.error(
                            "parallel_phase_exception",
                            phase_index=i,
                            error=str(task_result),
                            error_type=type(task_result).__name__
                        )
                        result.errors_encountered.append(f"Phase {i} failed: {str(task_result)}")
                        
            except Exception as e:
                logger.error("parallel_execution_failed", error=str(e))
                result.errors_encountered.append(f"Parallel execution failed: {str(e)}")
    
    async def _execute_phases_parallel(self, result: AggregatedAnalysisResult) -> None:
        """Execute analysis phases in parallel where possible (legacy method)."""
        return await self._execute_phases_parallel_with_recovery(result)
    
    async def _execute_phases_sequential_with_recovery(self, result: AggregatedAnalysisResult) -> None:
        """Execute analysis phases sequentially with comprehensive error recovery."""
        
        phases = [
            ("function_analysis", self.config.function_analysis.enabled, 
             self.config.function_analysis.timeout_seconds, self._execute_function_analysis),
            ("security_scanning", self.config.security_scanning.enabled,
             self.config.security_scanning.timeout_seconds, self._execute_security_scanning),
            ("string_extraction", self.config.string_extraction.enabled,
             self.config.string_extraction.timeout_seconds, self._execute_string_extraction),
        ]
        
        for phase_name, enabled, timeout, phase_func in phases:
            if enabled:
                try:
                    async with recovery_context(
                        f"{phase_name}_phase",
                        timeout_seconds=timeout,
                        context={"file_path": result.file_path}
                    ) as recovery:
                        await recovery.execute(lambda: phase_func(result))
                        
                except Exception as e:
                    logger.error(
                        "sequential_phase_failed", 
                        phase=phase_name, 
                        error=str(e),
                        stop_on_error=self.config.stop_on_critical_error
                    )
                    result.errors_encountered.append(f"{phase_name} failed: {str(e)}")
                    
                    if self.config.stop_on_critical_error:
                        logger.warning("stopping_sequential_execution_due_to_critical_error", phase=phase_name)
                        break
    
    async def _execute_phases_sequential(self, result: AggregatedAnalysisResult) -> None:
        """Execute analysis phases sequentially (legacy method)."""
        return await self._execute_phases_sequential_with_recovery(result)
    
    async def _execute_format_detection(self, result: AggregatedAnalysisResult) -> None:
        """Execute format detection phase following ADR patterns."""
        start_time = time.time()
        
        try:
            # Read file content for format detection (ADR: proper file handling)
            async with aiofiles.open(result.file_path, 'rb') as f:
                file_content = await f.read()
            
            # Extract filename from path
            filename = Path(result.file_path).name
            
            # Execute format detection with proper parameters
            format_result = await self.format_detector.detect_format(
                file_content=file_content,
                filename=filename,
                file_size=len(file_content)
            )
            
            processor_result = ProcessorResult(
                processor_name="format_detector",
                phase=AnalysisPhase.FORMAT_DETECTION,
                success=True,
                execution_time_ms=int((time.time() - start_time) * 1000),
                result_data=format_result.model_dump(),
                confidence_score=format_result.confidence_score
            )
            
            result.processor_results.append(processor_result)
            result.format_info = format_result
            
            # ADR: Structured logging
            logger.info(
                "format_detection_completed",
                detected_format=format_result.detected_format.value,
                confidence=format_result.confidence_score,
                execution_time_ms=processor_result.execution_time_ms
            )
            
        except Exception as e:
            processor_result = ProcessorResult(
                processor_name="format_detector",
                phase=AnalysisPhase.FORMAT_DETECTION,
                success=False,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
                confidence_score=0.0
            )
            
            result.processor_results.append(processor_result)
            result.errors_encountered.append(f"Format detection failed: {str(e)}")
            
            # ADR: Structured logging for errors
            logger.error(
                "format_detection_failed",
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=processor_result.execution_time_ms
            )
    
    async def _execute_function_analysis(self, result: AggregatedAnalysisResult) -> None:
        """Execute function analysis phase following ADR patterns."""
        start_time = time.time()
        
        try:
            # Create R2Session for function analysis (ADR: radare2 integration pattern)
            async with R2Session(result.file_path) as r2_session:
                # Get platform from format detection if available
                platform = Platform.UNKNOWN
                if result.format_info:
                    platform = Platform.from_file_format(result.format_info.detected_format)
                
                # Configure function analyzer for this platform
                self.function_analyzer.platform = platform
                
                # Execute function analysis
                function_result = await self.function_analyzer.analyze_functions(r2_session)
                
                processor_result = ProcessorResult(
                    processor_name="function_analyzer",
                    phase=AnalysisPhase.FUNCTION_ANALYSIS,
                    success=True,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    result_data=function_result.model_dump(),
                    confidence_score=self._calculate_function_confidence(function_result)
                )
                
                result.processor_results.append(processor_result)
                result.function_analysis = function_result
                
                # ADR: Structured logging
                logger.info(
                    "function_analysis_completed",
                    functions_found=function_result.total_functions,
                    platform=platform.value,
                    execution_time_ms=processor_result.execution_time_ms
                )
            
        except Exception as e:
            processor_result = ProcessorResult(
                processor_name="function_analyzer",
                phase=AnalysisPhase.FUNCTION_ANALYSIS,
                success=False,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
                confidence_score=0.0
            )
            
            result.processor_results.append(processor_result)
            result.errors_encountered.append(f"Function analysis failed: {str(e)}")
            
            # ADR: Structured logging for errors
            logger.error(
                "function_analysis_failed",
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=processor_result.execution_time_ms
            )
    
    async def _execute_security_scanning(self, result: AggregatedAnalysisResult) -> None:
        """Execute security scanning phase following ADR patterns."""
        start_time = time.time()
        
        try:
            # Create R2Session for security scanning (ADR: radare2 integration pattern)
            async with R2Session(result.file_path) as r2_session:
                # Execute security analysis
                security_result = await self.security_scanner.scan_binary(r2_session)
                
                processor_result = ProcessorResult(
                    processor_name="security_scanner",
                    phase=AnalysisPhase.SECURITY_SCANNING,
                    success=True,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    result_data=security_result.model_dump(),
                    confidence_score=self._calculate_security_confidence(security_result)
                )
                
                result.processor_results.append(processor_result)
                result.security_findings = security_result
                
                # ADR: Structured logging
                logger.info(
                    "security_scanning_completed",
                    findings_count=security_result.total_findings,
                    high_risk_findings=len([f for f in security_result.findings if f.severity.value in ['high', 'critical']]),
                    execution_time_ms=processor_result.execution_time_ms
                )
            
        except Exception as e:
            processor_result = ProcessorResult(
                processor_name="security_scanner",
                phase=AnalysisPhase.SECURITY_SCANNING,
                success=False,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
                confidence_score=0.0
            )
            
            result.processor_results.append(processor_result)
            result.errors_encountered.append(f"Security scanning failed: {str(e)}")
            
            # ADR: Structured logging for errors
            logger.error(
                "security_scanning_failed",
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=processor_result.execution_time_ms
            )
    
    async def _execute_string_extraction(self, result: AggregatedAnalysisResult) -> None:
        """Execute string extraction phase following ADR patterns."""
        start_time = time.time()
        
        try:
            # Create R2Session for string extraction (ADR: radare2 integration pattern)
            async with R2Session(result.file_path) as r2_session:
                # Configure based on analysis depth (ADR: configuration-based depth)
                min_length = self._get_string_min_length()
                max_length = self._get_string_max_length()
                include_context = self.config.analysis_depth != AnalysisDepth.QUICK
                
                # Execute string extraction
                string_result = await self.string_extractor.extract_strings(
                    r2_session=r2_session,
                    min_length=min_length,
                    max_length=max_length,
                    include_context=include_context
                )
                
                processor_result = ProcessorResult(
                    processor_name="string_extractor",
                    phase=AnalysisPhase.STRING_EXTRACTION,
                    success=True,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    result_data=string_result.model_dump(),
                    confidence_score=self._calculate_string_confidence(string_result)
                )
                
                result.processor_results.append(processor_result)
                result.string_analysis = string_result
                
                # ADR: Structured logging
                logger.info(
                    "string_extraction_completed",
                    total_strings=string_result.total_strings,
                    ascii_count=string_result.ascii_count,
                    unicode_count=string_result.unicode_count,
                    wide_count=string_result.wide_count,
                    execution_time_ms=processor_result.execution_time_ms
                )
            
        except Exception as e:
            processor_result = ProcessorResult(
                processor_name="string_extractor",
                phase=AnalysisPhase.STRING_EXTRACTION,
                success=False,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=str(e),
                confidence_score=0.0
            )
            
            result.processor_results.append(processor_result)
            result.errors_encountered.append(f"String extraction failed: {str(e)}")
            
            # ADR: Structured logging for errors
            logger.error(
                "string_extraction_failed",
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=processor_result.execution_time_ms
            )
    
    async def _aggregate_results(self, result: AggregatedAnalysisResult) -> None:
        """Aggregate results from all processors and generate insights."""
        
        # Calculate overall confidence
        successful_results = [r for r in result.processor_results if r.success]
        if successful_results:
            result.overall_confidence = sum(r.confidence_score for r in successful_results) / len(successful_results)
        
        # Generate risk assessment
        result.risk_level = self._assess_risk_level(result)
        
        # Extract key findings
        result.key_findings = self._extract_key_findings(result)
        
        # Generate recommendations
        result.recommendations = self._generate_recommendations(result)
        
        logger.debug(
            "results_aggregated",
            confidence=result.overall_confidence,
            risk_level=result.risk_level,
            findings_count=len(result.key_findings)
        )
    
    def _create_function_config(self) -> Any:
        """Create function analysis configuration based on engine settings."""
        # Import here to avoid circular imports
        from src.analysis.processors.function_analyzer import FunctionAnalysisConfig
        
        if self.config.analysis_depth == AnalysisDepth.QUICK:
            return FunctionAnalysisConfig(
                analyze_calls=False,
                extract_signatures=False,
                max_functions=50
            )
        elif self.config.analysis_depth == AnalysisDepth.DEEP:
            return FunctionAnalysisConfig(
                analyze_calls=True,
                extract_signatures=True,
                analyze_control_flow=True,
                max_functions=1000
            )
        else:  # STANDARD
            return FunctionAnalysisConfig()
    
    def _create_security_config(self) -> Any:
        """Create security scanning configuration based on engine settings."""
        # Import here to avoid circular imports  
        from src.analysis.processors.security_scanner import SecurityScanConfig
        
        config = SecurityScanConfig()
        
        # Adjust based on focus areas
        if "malware" in self.config.focus_areas:
            config.scan_network_operations = True
            config.scan_file_operations = True
            config.scan_process_operations = True
        
        if "crypto" in self.config.focus_areas:
            config.scan_cryptographic_operations = True
        
        return config
    
    def _get_string_min_length(self) -> int:
        """Get minimum string length based on analysis depth (ADR: configuration-based analysis)."""
        depth_settings = {
            AnalysisDepth.QUICK: 6,
            AnalysisDepth.STANDARD: 4,
            AnalysisDepth.COMPREHENSIVE: 3
        }
        return depth_settings.get(self.config.analysis_depth, 4)
    
    def _get_string_max_length(self) -> int:
        """Get maximum string length based on analysis depth (ADR: configuration-based analysis)."""
        depth_settings = {
            AnalysisDepth.QUICK: 512,
            AnalysisDepth.STANDARD: 1024,
            AnalysisDepth.COMPREHENSIVE: 2048
        }
        return depth_settings.get(self.config.analysis_depth, 1024)
    
    def _calculate_function_confidence(self, function_result: Any) -> float:
        """Calculate confidence score for function analysis results."""
        if not function_result or not function_result.functions_found:
            return 0.0
        
        # Base confidence on analysis completeness
        confidence = 0.5
        
        # Increase confidence based on analysis depth
        if hasattr(function_result, 'call_graph_analyzed') and function_result.call_graph_analyzed:
            confidence += 0.2
        
        if hasattr(function_result, 'signatures_extracted') and function_result.signatures_extracted:
            confidence += 0.1
        
        # Factor in analysis success rate
        if hasattr(function_result, 'analysis_time_ms') and function_result.analysis_time_ms < 60000:
            confidence += 0.2
        
        return min(confidence, 1.0)
    
    def _calculate_security_confidence(self, security_result: Any) -> float:
        """Calculate confidence score for security analysis results."""
        if not security_result:
            return 0.0
        
        # Base confidence on findings
        base_confidence = 0.7 if security_result.total_findings > 0 else 0.5
        
        # Adjust based on analysis completeness
        if hasattr(security_result, 'scans_completed') and security_result.scans_completed:
            completed_scans = len(security_result.scans_completed)
            base_confidence += min(completed_scans * 0.05, 0.3)
        
        return min(base_confidence, 1.0)
    
    def _calculate_string_confidence(self, string_result: StringExtraction) -> float:
        """Calculate confidence score for string extraction results (ADR: confidence scoring)."""
        if string_result.total_strings == 0:
            return 0.0
        
        # Base confidence on extraction success
        base_confidence = 0.6
        
        # Factor in categorization success (more categories found = better analysis)
        if hasattr(string_result, 'strings') and string_result.strings:
            categorized_count = sum(1 for s in string_result.strings if s.categories)
            categorized_ratio = categorized_count / max(string_result.total_strings, 1)
            base_confidence += categorized_ratio * 0.3
        
        # Factor in string type diversity (ADR: comprehensive analysis)
        type_diversity = 0
        if string_result.ascii_count > 0:
            type_diversity += 1
        if string_result.unicode_count > 0:
            type_diversity += 1
        if string_result.wide_count > 0:
            type_diversity += 1
        
        base_confidence += (type_diversity / 3.0) * 0.1
        
        return min(base_confidence, 1.0)
    
    def _assess_risk_level(self, result: AggregatedAnalysisResult) -> str:
        """Assess overall risk level based on analysis results."""
        risk_score = 0
        
        # Factor in security findings
        if result.security_findings and result.security_findings.total_findings > 0:
            risk_score += min(result.security_findings.total_findings * 10, 50)
        
        # Factor in suspicious strings (ADR: risk-based assessment)
        if result.string_analysis and hasattr(result.string_analysis, 'strings'):
            from src.models.shared.enums import StringCategory
            suspicious_categories = {
                StringCategory.CREDENTIAL, StringCategory.URL, 
                StringCategory.NETWORK_SERVICE, StringCategory.REGISTRY
            }
            suspicious_count = sum(
                1 for string_info in result.string_analysis.strings
                if any(cat in suspicious_categories for cat in string_info.categories)
            )
            risk_score += min(suspicious_count * 5, 30)
        
        # Determine risk level
        if risk_score >= 70:
            return "high"
        elif risk_score >= 40:
            return "medium"
        elif risk_score >= 15:
            return "low"
        else:
            return "minimal"
    
    def _extract_key_findings(self, result: AggregatedAnalysisResult) -> List[str]:
        """Extract key findings from analysis results."""
        findings = []
        
        # Format detection findings
        if result.format_info:
            findings.append(f"File format: {result.format_info.detected_format}")
            if result.format_info.platform:
                findings.append(f"Target platform: {result.format_info.platform}")
        
        # Function analysis findings
        if result.function_analysis and hasattr(result.function_analysis, 'functions_found'):
            count = result.function_analysis.functions_found
            findings.append(f"Identified {count} functions")
        
        # Security findings
        if result.security_findings and result.security_findings.total_findings > 0:
            findings.append(f"Found {result.security_findings.total_findings} security-related patterns")
        
        # String analysis findings (ADR: key findings extraction)
        if result.string_analysis and hasattr(result.string_analysis, 'strings'):
            from src.models.shared.enums import StringCategory
            interesting_cats = {StringCategory.CREDENTIAL, StringCategory.URL, StringCategory.NETWORK_SERVICE}
            for cat in interesting_cats:
                count = sum(
                    1 for string_info in result.string_analysis.strings
                    if cat in string_info.categories
                )
                if count > 0:
                    cat_name = cat.value.replace('_', ' ')
                    findings.append(f"Found {count} {cat_name} strings")
        
        return findings[:10]  # Limit to top 10 findings
    
    def _generate_recommendations(self, result: AggregatedAnalysisResult) -> List[str]:
        """Generate security recommendations based on analysis results."""
        recommendations = []
        
        # Security-based recommendations
        if result.security_findings and result.security_findings.total_findings > 0:
            recommendations.append("Review identified security patterns for potential threats")
            
            if hasattr(result.security_findings, 'network_operations') and result.security_findings.network_operations:
                recommendations.append("Analyze network communications for malicious activity")
        
        # String-based recommendations (ADR: security-focused recommendations)
        if result.string_analysis and hasattr(result.string_analysis, 'strings'):
            from src.models.shared.enums import StringCategory
            creds_found = sum(
                1 for string_info in result.string_analysis.strings
                if StringCategory.CREDENTIAL in string_info.categories
            )
            if creds_found > 0:
                recommendations.append("Investigate potential credential exposure")
            
            network_found = sum(
                1 for string_info in result.string_analysis.strings
                if StringCategory.URL in string_info.categories or StringCategory.NETWORK_SERVICE in string_info.categories
            )
            if network_found > 0:
                recommendations.append("Analyze network communications for malicious activity")
        
        # Risk-based recommendations
        if result.risk_level in ["high", "medium"]:
            recommendations.append("Conduct manual review due to elevated risk level")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def _is_processor_required(self, processor_name: str) -> bool:
        """Check if a processor is marked as required."""
        processor_configs = {
            "format_detector": self.config.format_detection,
            "function_analyzer": self.config.function_analysis,
            "security_scanner": self.config.security_scanning,
            "string_extractor": self.config.string_extraction,
        }
        
        config = processor_configs.get(processor_name)
        return config.required if config else False
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        import hashlib
        import aiofiles
        
        hash_sha256 = hashlib.sha256()
        async with aiofiles.open(file_path, 'rb') as f:
            async for chunk in f:
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats."""
        return [format_type.value for format_type in FileFormat]
    
    def get_analysis_capabilities(self) -> Dict[str, Any]:
        """Get information about analysis capabilities."""
        return {
            "processors": [
                {
                    "name": "format_detector", 
                    "description": "File format detection and validation",
                    "enabled": self.config.format_detection.enabled
                },
                {
                    "name": "function_analyzer",
                    "description": "Function discovery and analysis", 
                    "enabled": self.config.function_analysis.enabled
                },
                {
                    "name": "security_scanner",
                    "description": "Security pattern detection",
                    "enabled": self.config.security_scanning.enabled
                },
                {
                    "name": "string_extractor", 
                    "description": "String extraction and categorization",
                    "enabled": self.config.string_extraction.enabled
                }
            ],
            "analysis_depths": [depth.value for depth in AnalysisDepth],
            "supported_formats": self.get_supported_formats(),
            "focus_areas": [
                "malware", "vulnerabilities", "crypto", "network", 
                "filesystem", "strings", "functions", "imports", "exports"
            ]
        }