"""
Unit tests for error recovery and timeout management system.

Tests comprehensive error handling, timeout management, partial result recovery,
and detailed error diagnostics.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any

from src.analysis.error_recovery import (
    AnalysisRecoveryManager,
    AnalysisError,
    PartialResult,
    TimeoutContext,
    ErrorSeverity,
    RecoveryAction,
    get_recovery_manager,
    recovery_context
)
from src.core.exceptions import (
    BinaryAnalysisException,
    AnalysisTimeoutException,
    FileFormatException
)


class TestAnalysisError:
    """Test AnalysisError model."""
    
    def test_error_creation(self):
        """Test AnalysisError creation and properties."""
        error = AnalysisError(
            error_id="test_error_123",
            timestamp=time.time(),
            component="test_component",
            phase="test_phase",
            severity=ErrorSeverity.HIGH,
            exception_type="ValueError",
            error_message="Test error message",
            context={"test": "context"},
            recovery_attempted=True,
            recovery_action=RecoveryAction.RETRY,
            recovery_success=True
        )
        
        assert error.error_id == "test_error_123"
        assert error.component == "test_component"
        assert error.severity == ErrorSeverity.HIGH
        assert error.recovery_attempted is True
        assert error.recovery_action == RecoveryAction.RETRY
        assert error.recovery_success is True


class TestPartialResult:
    """Test PartialResult model."""
    
    def test_partial_result_creation(self):
        """Test PartialResult creation."""
        result = PartialResult(
            component="test_component",
            phase="test_phase",
            data={"partial": "data"},
            confidence=0.7,
            completeness=0.5,
            timestamp=time.time()
        )
        
        assert result.component == "test_component"
        assert result.phase == "test_phase"
        assert result.confidence == 0.7
        assert result.completeness == 0.5


class TestTimeoutContext:
    """Test TimeoutContext model."""
    
    def test_timeout_context_creation(self):
        """Test TimeoutContext creation and validation."""
        context = TimeoutContext(
            operation_name="test_operation",
            timeout_seconds=30.0,
            start_time=time.time(),
            warning_threshold=0.8,
            grace_period=5.0
        )
        
        assert context.operation_name == "test_operation"
        assert context.timeout_seconds == 30.0
        assert context.warning_threshold == 0.8
        assert context.grace_period == 5.0
    
    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeout
        context = TimeoutContext(
            operation_name="test",
            timeout_seconds=10.0,
            start_time=time.time()
        )
        assert context.timeout_seconds == 10.0
        
        # Invalid timeout (negative)
        with pytest.raises(ValueError):
            TimeoutContext(
                operation_name="test",
                timeout_seconds=-5.0,
                start_time=time.time()
            )


class TestAnalysisRecoveryManager:
    """Test AnalysisRecoveryManager functionality."""
    
    @pytest.fixture
    def recovery_manager(self):
        """Create AnalysisRecoveryManager instance."""
        return AnalysisRecoveryManager()
    
    @pytest.mark.asyncio
    async def test_execute_with_recovery_success(self, recovery_manager):
        """Test successful operation execution with recovery."""
        async def successful_operation():
            return "success_result"
        
        result = await recovery_manager.execute_with_recovery(
            successful_operation,
            "test_operation",
            timeout_seconds=5.0,
            max_retries=2
        )
        
        assert result == "success_result"
    
    @pytest.mark.asyncio
    async def test_execute_with_recovery_retry_success(self, recovery_manager):
        """Test operation success after retry."""
        call_count = 0
        
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First attempt failed")
            return "retry_success"
        
        result = await recovery_manager.execute_with_recovery(
            failing_then_success,
            "test_operation",
            timeout_seconds=5.0,
            max_retries=2
        )
        
        assert result == "retry_success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_execute_with_recovery_max_retries_exceeded(self, recovery_manager):
        """Test operation failure after max retries."""
        async def always_failing():
            raise ValueError("Always fails")
        
        with pytest.raises(BinaryAnalysisException, match="failed after 3 attempts"):
            await recovery_manager.execute_with_recovery(
                always_failing,
                "test_operation",
                timeout_seconds=5.0,
                max_retries=2
            )
        
        # Should have recorded errors
        errors = recovery_manager.get_detailed_errors()
        assert len(errors) > 0
    
    @pytest.mark.asyncio
    async def test_execute_with_recovery_timeout(self, recovery_manager):
        """Test operation timeout handling."""
        async def slow_operation():
            await asyncio.sleep(2.0)  # Longer than timeout
            return "slow_result"
        
        with pytest.raises(BinaryAnalysisException):
            await recovery_manager.execute_with_recovery(
                slow_operation,
                "test_operation",
                timeout_seconds=0.1,  # Short timeout
                max_retries=1
            )
    
    @pytest.mark.asyncio
    async def test_timeout_error_recovery(self, recovery_manager):
        """Test timeout error recovery strategy."""
        timeout_error = asyncio.TimeoutError("Operation timed out")
        
        # Mock error for testing
        mock_error = AnalysisError(
            error_id="timeout_test",
            timestamp=time.time(),
            component="test_component",
            phase="test_phase",
            severity=ErrorSeverity.MEDIUM,
            exception_type="TimeoutError",
            error_message="Test timeout",
            context={"timeout_seconds": 30}
        )
        
        recovery_result = await recovery_manager._handle_timeout_error(
            timeout_error,
            mock_error,
            "test_operation",
            {"timeout_seconds": 30}
        )
        
        # Should attempt to extend timeout
        assert recovery_result["action"] == RecoveryAction.RETRY
        assert recovery_result["can_retry"] is True
    
    @pytest.mark.asyncio
    async def test_format_error_recovery(self, recovery_manager):
        """Test file format error recovery strategy."""
        format_error = FileFormatException("Unsupported format")
        
        mock_error = AnalysisError(
            error_id="format_test",
            timestamp=time.time(),
            component="test_component",
            phase="test_phase",
            severity=ErrorSeverity.HIGH,
            exception_type="FileFormatException",
            error_message="Format error"
        )
        
        recovery_result = await recovery_manager._handle_format_error(
            format_error,
            mock_error,
            "test_operation",
            {}
        )
        
        # Format errors should not be recoverable
        assert recovery_result["action"] == RecoveryAction.ABORT
        assert recovery_result["can_retry"] is False
    
    @pytest.mark.asyncio
    async def test_connection_error_recovery(self, recovery_manager):
        """Test connection error recovery strategy."""
        connection_error = ConnectionError("R2 connection failed")
        
        mock_error = AnalysisError(
            error_id="connection_test",
            timestamp=time.time(),
            component="test_component",
            phase="test_phase",
            severity=ErrorSeverity.HIGH,
            exception_type="ConnectionError",
            error_message="Connection error"
        )
        
        recovery_result = await recovery_manager._handle_connection_error(
            connection_error,
            mock_error,
            "test_operation",
            {}
        )
        
        # Connection errors should trigger restart
        assert recovery_result["action"] == RecoveryAction.RESTART
        assert recovery_result["can_retry"] is True
    
    @pytest.mark.asyncio
    async def test_memory_error_recovery(self, recovery_manager):
        """Test memory error recovery strategy."""
        memory_error = MemoryError("Out of memory")
        
        mock_error = AnalysisError(
            error_id="memory_test",
            timestamp=time.time(),
            component="test_component",
            phase="test_phase",
            severity=ErrorSeverity.CRITICAL,
            exception_type="MemoryError",
            error_message="Memory error"
        )
        
        recovery_result = await recovery_manager._handle_memory_error(
            memory_error,
            mock_error,
            "test_operation",
            {}
        )
        
        # Memory errors should abort
        assert recovery_result["action"] == RecoveryAction.ABORT
        assert recovery_result["can_retry"] is False
    
    @pytest.mark.asyncio
    async def test_partial_result_collection(self, recovery_manager):
        """Test partial result collection."""
        context = {
            "intermediate_results": {"step1": "complete"},
            "processor_state": {"current": "step2"},
            "completed_operations": ["init", "validate"]
        }
        
        partial_result = await recovery_manager._collect_partial_results(
            "test_operation",
            context
        )
        
        assert partial_result is not None
        assert partial_result.component == "test_operation"
        assert "intermediate_results" in partial_result.data
        assert "processor_state" in partial_result.data
        assert "completed_operations" in partial_result.data
        assert partial_result.completeness > 0
    
    def test_classify_error_severity(self, recovery_manager):
        """Test error severity classification."""
        # Critical error
        memory_error = MemoryError("Out of memory")
        assert recovery_manager._classify_error_severity(memory_error) == ErrorSeverity.CRITICAL
        
        # High severity error
        connection_error = ConnectionError("Connection failed")
        assert recovery_manager._classify_error_severity(connection_error) == ErrorSeverity.HIGH
        
        # Medium severity error
        timeout_error = AnalysisTimeoutException("Timeout occurred")
        assert recovery_manager._classify_error_severity(timeout_error) == ErrorSeverity.MEDIUM
        
        # Low severity error
        generic_error = ValueError("Generic error")
        assert recovery_manager._classify_error_severity(generic_error) == ErrorSeverity.LOW
    
    def test_get_error_summary(self, recovery_manager):
        """Test error summary generation."""
        # Add some test errors
        test_error = AnalysisError(
            error_id="test_1",
            timestamp=time.time(),
            component="test_component",
            phase="test_phase",
            severity=ErrorSeverity.HIGH,
            exception_type="TestError",
            error_message="Test error",
            recovery_attempted=True,
            recovery_success=True
        )
        
        recovery_manager._errors.append(test_error)
        
        summary = recovery_manager.get_error_summary()
        
        assert summary["total_errors"] == 1
        assert ErrorSeverity.HIGH in summary["severity_breakdown"]
        assert "test_component" in summary["component_breakdown"]
        assert summary["recovery_stats"]["attempts"] == 1
        assert summary["recovery_stats"]["successes"] == 1
        assert summary["recovery_stats"]["success_rate"] == 1.0
    
    def test_get_detailed_errors(self, recovery_manager):
        """Test detailed error retrieval."""
        initial_errors = recovery_manager.get_detailed_errors()
        assert len(initial_errors) == 0
        
        # Add test error
        test_error = AnalysisError(
            error_id="detailed_test",
            timestamp=time.time(),
            component="test",
            phase="test",
            severity=ErrorSeverity.LOW,
            exception_type="TestError",
            error_message="Test"
        )
        
        recovery_manager._errors.append(test_error)
        
        detailed_errors = recovery_manager.get_detailed_errors()
        assert len(detailed_errors) == 1
        assert detailed_errors[0].error_id == "detailed_test"
    
    def test_clear_history(self, recovery_manager):
        """Test error and partial result history clearing."""
        # Add test data
        test_error = AnalysisError(
            error_id="test",
            timestamp=time.time(),
            component="test",
            phase="test",
            severity=ErrorSeverity.LOW,
            exception_type="TestError",
            error_message="Test"
        )
        
        test_partial = PartialResult(
            component="test",
            phase="test",
            data={},
            confidence=0.5,
            completeness=0.5,
            timestamp=time.time()
        )
        
        recovery_manager._errors.append(test_error)
        recovery_manager._partial_results.append(test_partial)
        
        # Verify data exists
        assert len(recovery_manager._errors) > 0
        assert len(recovery_manager._partial_results) > 0
        
        # Clear history
        recovery_manager.clear_history()
        
        # Verify data cleared
        assert len(recovery_manager._errors) == 0
        assert len(recovery_manager._partial_results) == 0


class TestRecoveryContext:
    """Test recovery context manager."""
    
    @pytest.mark.asyncio
    async def test_recovery_context_success(self):
        """Test successful operation in recovery context."""
        async def successful_operation():
            return "context_success"
        
        async with recovery_context("test_operation") as recovery:
            result = await recovery.execute(successful_operation)
            assert result == "context_success"
    
    @pytest.mark.asyncio
    async def test_recovery_context_with_timeout(self):
        """Test recovery context with timeout."""
        async def slow_operation():
            await asyncio.sleep(1.0)
            return "slow_result"
        
        with pytest.raises(Exception):  # Should timeout
            async with recovery_context("test_operation", timeout_seconds=0.1) as recovery:
                await recovery.execute(slow_operation)
    
    @pytest.mark.asyncio
    async def test_recovery_context_with_context_data(self):
        """Test recovery context with additional context data."""
        async def context_aware_operation():
            return "context_aware"
        
        context_data = {"test_key": "test_value"}
        
        async with recovery_context("test_operation", context=context_data) as recovery:
            result = await recovery.execute(context_aware_operation)
            assert result == "context_aware"


class TestRecoveryManagerSingleton:
    """Test recovery manager singleton functionality."""
    
    def test_get_recovery_manager_singleton(self):
        """Test that get_recovery_manager returns the same instance."""
        manager1 = get_recovery_manager()
        manager2 = get_recovery_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, AnalysisRecoveryManager)


class TestRecoveryManagerEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.fixture
    def recovery_manager(self):
        """Create fresh AnalysisRecoveryManager instance."""
        return AnalysisRecoveryManager()
    
    @pytest.mark.asyncio
    async def test_nested_recovery_contexts(self, recovery_manager):
        """Test nested recovery context behavior."""
        async def nested_operation():
            async with recovery_context("inner_operation") as inner_recovery:
                return await inner_recovery.execute(lambda: "nested_result")
        
        async with recovery_context("outer_operation") as outer_recovery:
            result = await outer_recovery.execute(nested_operation)
            assert result == "nested_result"
    
    @pytest.mark.asyncio
    async def test_concurrent_recovery_operations(self, recovery_manager):
        """Test concurrent operations with recovery."""
        async def concurrent_operation(operation_id):
            await asyncio.sleep(0.1)
            return f"result_{operation_id}"
        
        tasks = []
        for i in range(5):
            task = recovery_manager.execute_with_recovery(
                lambda i=i: concurrent_operation(i),
                f"concurrent_operation_{i}",
                timeout_seconds=1.0
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result == f"result_{i}"
    
    @pytest.mark.asyncio
    async def test_recovery_with_partial_results(self, recovery_manager):
        """Test recovery system with partial results."""
        call_count = 0
        
        async def partial_failure_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails but provides partial results
                raise Exception("Partial failure")
            return "final_result"
        
        # Mock partial result collection
        original_collect = recovery_manager._collect_partial_results
        
        async def mock_collect_partial_results(operation_name, context):
            if call_count == 1:  # After first failure
                return PartialResult(
                    component=operation_name,
                    phase="test",
                    data={"partial": "data"},
                    confidence=0.7,
                    completeness=0.5,
                    timestamp=time.time()
                )
            return await original_collect(operation_name, context)
        
        recovery_manager._collect_partial_results = mock_collect_partial_results
        
        result = await recovery_manager.execute_with_recovery(
            partial_failure_operation,
            "partial_test_operation",
            timeout_seconds=5.0,
            max_retries=2
        )
        
        assert result == "final_result"
        
        # Should have partial results recorded
        partial_results = recovery_manager.get_partial_results()
        assert len(partial_results) > 0
    
    @pytest.mark.asyncio
    async def test_timeout_warning_system(self, recovery_manager):
        """Test timeout warning monitoring."""
        warning_triggered = False
        
        async def monitored_operation():
            await asyncio.sleep(0.5)  # Half the timeout
            return "warning_test_result"
        
        # Mock timeout context with low warning threshold
        timeout_ctx = TimeoutContext(
            operation_name="warning_test",
            timeout_seconds=1.0,
            start_time=time.time(),
            warning_threshold=0.4  # Trigger warning at 40% of timeout
        )
        
        # Execute with timeout context
        result = await recovery_manager._execute_with_timeout(
            monitored_operation,
            timeout_ctx,
            {}
        )
        
        assert result == "warning_test_result"
    
    def test_system_metrics_collection(self, recovery_manager):
        """Test system metrics collection."""
        memory_usage = recovery_manager._get_memory_usage()
        system_load = recovery_manager._get_system_load()
        
        assert memory_usage >= 0.0
        assert system_load >= 0.0