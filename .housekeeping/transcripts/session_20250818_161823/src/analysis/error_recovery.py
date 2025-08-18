"""
Error recovery and timeout management for binary analysis.

Provides comprehensive error handling, timeout management, partial result recovery,
and detailed diagnostic information following ADR standards.
"""

import asyncio
import time
import traceback
import signal
import psutil
from typing import Dict, List, Optional, Any, Type, Union, Callable
from pathlib import Path
from enum import Enum
from contextlib import asynccontextmanager

import structlog
from pydantic import BaseModel, Field

from src.core.exceptions import (
    BinaryAnalysisException, 
    AnalysisTimeoutException,
    FileFormatException
)
from src.core.config import get_settings

logger = structlog.get_logger(__name__)


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"  
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(str, Enum):
    """Available recovery actions."""
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK = "fallback"
    ABORT = "abort"
    RESTART = "restart"


class AnalysisError(BaseModel):
    """Structured analysis error information."""
    
    error_id: str = Field(..., description="Unique error identifier")
    timestamp: float = Field(..., description="Error timestamp")
    component: str = Field(..., description="Component where error occurred")
    phase: str = Field(..., description="Analysis phase during error")
    severity: ErrorSeverity = Field(..., description="Error severity level")
    exception_type: str = Field(..., description="Exception type")
    error_message: str = Field(..., description="Error message")
    stack_trace: Optional[str] = Field(default=None, description="Stack trace if available")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional error context")
    recovery_attempted: bool = Field(default=False, description="Whether recovery was attempted")
    recovery_action: Optional[RecoveryAction] = Field(default=None, description="Recovery action taken")
    recovery_success: bool = Field(default=False, description="Whether recovery succeeded")


class PartialResult(BaseModel):
    """Partial analysis result for recovery scenarios."""
    
    component: str = Field(..., description="Component that produced partial result")
    phase: str = Field(..., description="Analysis phase")
    data: Dict[str, Any] = Field(..., description="Partial result data")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Result confidence")
    completeness: float = Field(default=0.0, ge=0.0, le=1.0, description="Result completeness percentage")
    timestamp: float = Field(..., description="Result timestamp")
    
    
class TimeoutContext(BaseModel):
    """Timeout management context."""
    
    operation_name: str = Field(..., description="Name of operation")
    timeout_seconds: float = Field(..., gt=0, description="Timeout value in seconds")
    start_time: float = Field(..., description="Operation start time")
    warning_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Warning threshold ratio")
    grace_period: float = Field(default=5.0, ge=0, description="Grace period for cleanup")
    cancellation_token: Optional[Any] = Field(default=None, description="Cancellation token")


class AnalysisRecoveryManager:
    """
    Comprehensive error recovery and timeout management system.
    
    Handles graceful cancellation, partial result recovery, session restart logic,
    and detailed error diagnostics with context preservation.
    """
    
    def __init__(self):
        """Initialize the recovery manager."""
        self.settings = get_settings()
        self._errors: List[AnalysisError] = []
        self._partial_results: List[PartialResult] = []
        self._active_timeouts: Dict[str, TimeoutContext] = {}
        self._recovery_strategies: Dict[Type[Exception], Callable] = {}
        self._session_health_checks: Dict[str, Callable] = {}
        
        # Initialize default recovery strategies
        self._initialize_recovery_strategies()
        
        logger.info("AnalysisRecoveryManager initialized")
    
    def _initialize_recovery_strategies(self) -> None:
        """Initialize default recovery strategies for common exceptions."""
        self._recovery_strategies.update({
            asyncio.TimeoutError: self._handle_timeout_error,
            AnalysisTimeoutException: self._handle_analysis_timeout,
            FileFormatException: self._handle_format_error,
            ConnectionError: self._handle_connection_error,
            MemoryError: self._handle_memory_error,
            ProcessLookupError: self._handle_process_error,
            BinaryAnalysisException: self._handle_analysis_error,
        })
    
    async def execute_with_recovery(
        self,
        operation_func: Callable,
        operation_name: str,
        timeout_seconds: Optional[float] = None,
        max_retries: int = 3,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute operation with comprehensive error recovery.
        
        Args:
            operation_func: Function to execute
            operation_name: Name for logging and error tracking
            timeout_seconds: Operation timeout
            max_retries: Maximum retry attempts
            context: Additional context information
            
        Returns:
            Operation result or partial result if recovery successful
            
        Raises:
            BinaryAnalysisException: If all recovery attempts fail
        """
        context = context or {}
        timeout_seconds = timeout_seconds or self.settings.analysis.default_timeout_seconds
        
        # Create timeout context
        timeout_ctx = TimeoutContext(
            operation_name=operation_name,
            timeout_seconds=timeout_seconds,
            start_time=time.time(),
            cancellation_token=asyncio.Event()
        )
        
        self._active_timeouts[operation_name] = timeout_ctx
        
        try:
            for attempt in range(max_retries + 1):
                try:
                    # Get current timeout from context (may have been extended by recovery)
                    current_timeout = context.get("timeout_seconds", timeout_seconds)
                    
                    # Update timeout context if timeout was extended
                    if current_timeout != timeout_ctx.timeout_seconds:
                        timeout_ctx.timeout_seconds = current_timeout
                        timeout_ctx.start_time = time.time()  # Reset start time for new timeout
                        timeout_ctx.cancellation_token.clear()  # Reset cancellation token
                    
                    logger.info(
                        "executing_operation_with_recovery",
                        operation=operation_name,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        timeout=current_timeout
                    )
                    
                    # Execute with timeout and cancellation support
                    result = await self._execute_with_timeout(
                        operation_func,
                        timeout_ctx,
                        context
                    )
                    
                    logger.info(
                        "operation_completed_successfully",
                        operation=operation_name,
                        attempt=attempt + 1,
                        execution_time=time.time() - timeout_ctx.start_time
                    )
                    
                    return result
                    
                except Exception as e:
                    error = await self._record_error(
                        e, operation_name, "execution", context, attempt
                    )
                    
                    # Attempt recovery if not final attempt
                    if attempt < max_retries:
                        recovery_result = await self._attempt_recovery(
                            e, error, operation_name, context
                        )
                        
                        if recovery_result.get("can_retry", False):
                            delay = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                            logger.info(
                                "retrying_after_recovery",
                                operation=operation_name,
                                delay=delay,
                                recovery_action=recovery_result.get("action")
                            )
                            await asyncio.sleep(delay)
                            continue
                        elif recovery_result.get("partial_result"):
                            logger.info(
                                "returning_partial_result",
                                operation=operation_name,
                                completeness=recovery_result.get("completeness", 0.0)
                            )
                            return recovery_result["partial_result"]
                    
                    # Final attempt failed
                    if attempt == max_retries:
                        raise BinaryAnalysisException(
                            f"Operation '{operation_name}' failed after {max_retries + 1} attempts: {str(e)}"
                        ) from e
                        
        finally:
            # Cleanup timeout tracking
            self._active_timeouts.pop(operation_name, None)
    
    async def _execute_with_timeout(
        self,
        operation_func: Callable,
        timeout_ctx: TimeoutContext,
        context: Dict[str, Any]
    ) -> Any:
        """Execute operation with timeout and cancellation support."""
        
        # Create cancellation-aware wrapper
        async def cancellable_operation():
            # Start timeout warning task
            warning_task = asyncio.create_task(
                self._monitor_timeout_warning(timeout_ctx)
            )
            
            try:
                # Check if operation is already cancelled
                if timeout_ctx.cancellation_token.is_set():
                    raise asyncio.CancelledError("Operation was cancelled")
                
                # Execute the operation
                if asyncio.iscoroutinefunction(operation_func):
                    result = await operation_func()
                else:
                    # Run sync function in executor
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, operation_func)
                
                return result
                
            finally:
                warning_task.cancel()
                try:
                    await warning_task
                except asyncio.CancelledError:
                    pass
        
        try:
            # Execute with timeout
            return await asyncio.wait_for(
                cancellable_operation(),
                timeout=timeout_ctx.timeout_seconds
            )
            
        except asyncio.TimeoutError:
            # Set cancellation token
            timeout_ctx.cancellation_token.set()
            
            # Attempt graceful cancellation
            await self._attempt_graceful_cancellation(timeout_ctx, context)
            
            raise AnalysisTimeoutException(
                f"Operation '{timeout_ctx.operation_name}' timed out after {timeout_ctx.timeout_seconds} seconds"
            )
    
    async def _monitor_timeout_warning(self, timeout_ctx: TimeoutContext) -> None:
        """Monitor for timeout warnings."""
        warning_time = timeout_ctx.timeout_seconds * timeout_ctx.warning_threshold
        
        try:
            await asyncio.sleep(warning_time)
            
            elapsed = time.time() - timeout_ctx.start_time
            remaining = timeout_ctx.timeout_seconds - elapsed
            
            logger.warning(
                "operation_timeout_warning",
                operation=timeout_ctx.operation_name,
                elapsed=elapsed,
                remaining=remaining,
                threshold_reached=timeout_ctx.warning_threshold
            )
            
        except asyncio.CancelledError:
            pass
    
    async def _attempt_graceful_cancellation(
        self,
        timeout_ctx: TimeoutContext,
        context: Dict[str, Any]
    ) -> None:
        """Attempt graceful cancellation of timed-out operation."""
        logger.info(
            "attempting_graceful_cancellation",
            operation=timeout_ctx.operation_name,
            grace_period=timeout_ctx.grace_period
        )
        
        try:
            # Give grace period for cleanup
            await asyncio.sleep(timeout_ctx.grace_period)
            
            # Check for partial results
            partial_result = await self._collect_partial_results(
                timeout_ctx.operation_name,
                context
            )
            
            if partial_result:
                logger.info(
                    "partial_results_collected_during_cancellation",
                    operation=timeout_ctx.operation_name,
                    partial_data_size=len(str(partial_result.data))
                )
                self._partial_results.append(partial_result)
        
        except Exception as e:
            logger.error(
                "graceful_cancellation_failed",
                operation=timeout_ctx.operation_name,
                error=str(e)
            )
    
    async def _record_error(
        self,
        exception: Exception,
        component: str,
        phase: str,
        context: Dict[str, Any],
        attempt: int
    ) -> AnalysisError:
        """Record structured error information."""
        error_id = f"{component}_{phase}_{int(time.time() * 1000)}_{attempt}"
        
        # Determine severity
        severity = self._classify_error_severity(exception)
        
        # Capture stack trace for debugging
        stack_trace = None
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            stack_trace = traceback.format_exc()
        
        # Add system context
        enhanced_context = {
            **context,
            "attempt": attempt,
            "memory_usage_mb": self._get_memory_usage(),
            "active_timeouts": len(self._active_timeouts),
            "system_load": self._get_system_load(),
        }
        
        error = AnalysisError(
            error_id=error_id,
            timestamp=time.time(),
            component=component,
            phase=phase,
            severity=severity,
            exception_type=type(exception).__name__,
            error_message=str(exception),
            stack_trace=stack_trace,
            context=enhanced_context
        )
        
        self._errors.append(error)
        
        logger.error(
            "analysis_error_recorded",
            error_id=error_id,
            component=component,
            phase=phase,
            severity=severity.value,
            exception_type=type(exception).__name__,
            error_message=str(exception)
        )
        
        return error
    
    async def _attempt_recovery(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Attempt to recover from the error."""
        
        # Find appropriate recovery strategy
        recovery_func = None
        for exc_type, func in self._recovery_strategies.items():
            if isinstance(exception, exc_type):
                recovery_func = func
                break
        
        if not recovery_func:
            recovery_func = self._default_recovery_handler
        
        try:
            recovery_result = await recovery_func(
                exception, error, operation_name, context
            )
            
            # Update error record
            error.recovery_attempted = True
            error.recovery_action = recovery_result.get("action")
            error.recovery_success = recovery_result.get("success", False)
            
            logger.info(
                "recovery_attempted",
                error_id=error.error_id,
                action=error.recovery_action,
                success=error.recovery_success
            )
            
            return recovery_result
            
        except Exception as recovery_error:
            logger.error(
                "recovery_attempt_failed",
                error_id=error.error_id,
                recovery_error=str(recovery_error)
            )
            return {"success": False, "can_retry": False}
    
    async def _handle_timeout_error(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle timeout-related errors."""
        logger.info(
            "handling_timeout_error",
            operation=operation_name,
            error_id=error.error_id
        )
        
        # Collect any partial results
        partial_result = await self._collect_partial_results(operation_name, context)
        
        # Check if we can extend timeout and retry
        current_timeout = context.get("timeout_seconds", 30)
        max_timeout = self.settings.analysis.max_timeout_seconds
        
        if current_timeout < max_timeout:
            extended_timeout = min(current_timeout * 1.5, max_timeout)
            context["timeout_seconds"] = extended_timeout
            
            logger.info(
                "extending_timeout_for_retry",
                operation=operation_name,
                old_timeout=current_timeout,
                new_timeout=extended_timeout
            )
            
            return {
                "action": RecoveryAction.RETRY,
                "success": True,
                "can_retry": True,
                "partial_result": partial_result.data if partial_result else None
            }
        
        # Return partial results if available
        if partial_result and partial_result.completeness > 0.5:
            return {
                "action": RecoveryAction.FALLBACK,
                "success": True,
                "can_retry": False,
                "partial_result": partial_result.data,
                "completeness": partial_result.completeness
            }
        
        return {"action": RecoveryAction.ABORT, "success": False, "can_retry": False}
    
    async def _handle_analysis_timeout(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle analysis-specific timeout errors."""
        return await self._handle_timeout_error(exception, error, operation_name, context)
    
    async def _handle_format_error(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle file format errors."""
        logger.info(
            "handling_format_error",
            operation=operation_name,
            error_id=error.error_id
        )
        
        # File format errors are usually not recoverable
        return {
            "action": RecoveryAction.ABORT,
            "success": False,
            "can_retry": False,
            "reason": "File format not supported or corrupted"
        }
    
    async def _handle_connection_error(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle connection-related errors (e.g., r2pipe connection issues)."""
        logger.info(
            "handling_connection_error",
            operation=operation_name,
            error_id=error.error_id
        )
        
        # Connection errors might be recoverable with restart
        return {
            "action": RecoveryAction.RESTART,
            "success": True,
            "can_retry": True,
            "restart_component": "r2_session"
        }
    
    async def _handle_memory_error(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle memory-related errors."""
        logger.error(
            "handling_memory_error",
            operation=operation_name,
            error_id=error.error_id,
            memory_usage=self._get_memory_usage()
        )
        
        # Try to collect partial results and abort
        partial_result = await self._collect_partial_results(operation_name, context)
        
        return {
            "action": RecoveryAction.ABORT,
            "success": False,
            "can_retry": False,
            "partial_result": partial_result.data if partial_result else None,
            "reason": "Insufficient memory"
        }
    
    async def _handle_process_error(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle process-related errors (e.g., radare2 process crashed)."""
        logger.error(
            "handling_process_error",
            operation=operation_name,
            error_id=error.error_id
        )
        
        # Process errors might be recoverable with restart
        return {
            "action": RecoveryAction.RESTART,
            "success": True,
            "can_retry": True,
            "restart_component": "analysis_engine"
        }
    
    async def _handle_analysis_error(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle generic analysis errors."""
        logger.info(
            "handling_analysis_error",
            operation=operation_name,
            error_id=error.error_id
        )
        
        # Generic analysis errors might be worth retrying
        return {
            "action": RecoveryAction.RETRY,
            "success": True,
            "can_retry": True
        }
    
    async def _default_recovery_handler(
        self,
        exception: Exception,
        error: AnalysisError,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Default recovery handler for unhandled exceptions."""
        logger.warning(
            "using_default_recovery_handler",
            operation=operation_name,
            error_id=error.error_id,
            exception_type=type(exception).__name__
        )
        
        # Conservative approach: try once more, then abort
        if error.context.get("attempt", 0) == 0:
            return {
                "action": RecoveryAction.RETRY,
                "success": True,
                "can_retry": True
            }
        
        return {
            "action": RecoveryAction.ABORT,
            "success": False,
            "can_retry": False
        }
    
    async def _collect_partial_results(
        self,
        operation_name: str,
        context: Dict[str, Any]
    ) -> Optional[PartialResult]:
        """Collect partial results from failed operation."""
        
        # Try to extract any available partial data from context
        partial_data = {}
        completeness = 0.0
        
        # Check for cached intermediate results
        if "intermediate_results" in context:
            partial_data.update(context["intermediate_results"])
            completeness += 0.3
        
        # Check for processor-specific partial results
        if "processor_state" in context:
            partial_data["processor_state"] = context["processor_state"]
            completeness += 0.2
        
        # Check for any completed sub-operations
        if "completed_operations" in context:
            partial_data["completed_operations"] = context["completed_operations"]
            completeness += 0.5
        
        if not partial_data:
            return None
        
        return PartialResult(
            component=operation_name,
            phase="recovery",
            data=partial_data,
            confidence=0.5,  # Partial results have lower confidence
            completeness=min(completeness, 1.0),
            timestamp=time.time()
        )
    
    def _classify_error_severity(self, exception: Exception) -> ErrorSeverity:
        """Classify error severity based on exception type."""
        if isinstance(exception, MemoryError):
            return ErrorSeverity.CRITICAL
        elif isinstance(exception, (ProcessLookupError, ConnectionError)):
            return ErrorSeverity.HIGH
        elif isinstance(exception, (AnalysisTimeoutException, asyncio.TimeoutError)):
            return ErrorSeverity.MEDIUM
        elif isinstance(exception, BinaryAnalysisException):
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def _get_system_load(self) -> float:
        """Get current system load average."""
        try:
            return psutil.getloadavg()[0]  # 1-minute load average
        except Exception:
            return 0.0
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all recorded errors."""
        if not self._errors:
            return {"total_errors": 0, "error_summary": {}}
        
        # Count by severity
        severity_counts = {}
        for error in self._errors:
            severity_counts[error.severity] = severity_counts.get(error.severity, 0) + 1
        
        # Count by component
        component_counts = {}
        for error in self._errors:
            component_counts[error.component] = component_counts.get(error.component, 0) + 1
        
        # Recovery statistics
        total_recovery_attempts = sum(1 for e in self._errors if e.recovery_attempted)
        successful_recoveries = sum(1 for e in self._errors if e.recovery_success)
        
        return {
            "total_errors": len(self._errors),
            "severity_breakdown": severity_counts,
            "component_breakdown": component_counts,
            "recovery_stats": {
                "attempts": total_recovery_attempts,
                "successes": successful_recoveries,
                "success_rate": successful_recoveries / max(total_recovery_attempts, 1)
            },
            "partial_results_available": len(self._partial_results)
        }
    
    def get_detailed_errors(self) -> List[AnalysisError]:
        """Get list of all detailed error records."""
        return self._errors.copy()
    
    def get_partial_results(self) -> List[PartialResult]:
        """Get list of all collected partial results."""
        return self._partial_results.copy()
    
    def clear_history(self) -> None:
        """Clear error and partial result history."""
        self._errors.clear()
        self._partial_results.clear()
        logger.info("Error and partial result history cleared")


# Global recovery manager instance
_recovery_manager: Optional[AnalysisRecoveryManager] = None


def get_recovery_manager() -> AnalysisRecoveryManager:
    """Get global recovery manager instance."""
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = AnalysisRecoveryManager()
    return _recovery_manager


@asynccontextmanager
async def recovery_context(
    operation_name: str,
    timeout_seconds: Optional[float] = None,
    context: Optional[Dict[str, Any]] = None
):
    """
    Context manager for operations with automatic error recovery.
    
    Usage:
        async with recovery_context("analyze_functions", timeout_seconds=300) as recovery:
            result = await recovery.execute(some_analysis_function)
    """
    manager = get_recovery_manager()
    
    class RecoveryContextManager:
        def __init__(self):
            self.manager = manager
            self.operation_name = operation_name
            self.timeout_seconds = timeout_seconds
            self.context = context or {}
        
        async def execute(self, operation_func: Callable, **kwargs) -> Any:
            return await self.manager.execute_with_recovery(
                operation_func,
                self.operation_name,
                self.timeout_seconds,
                context={**self.context, **kwargs}
            )
    
    try:
        yield RecoveryContextManager()
    except Exception as e:
        logger.error(
            "recovery_context_exception",
            operation=operation_name,
            error=str(e)
        )
        raise