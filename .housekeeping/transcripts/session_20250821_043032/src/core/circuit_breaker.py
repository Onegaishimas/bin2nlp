"""
Circuit Breaker Pattern Implementation

Provides circuit breaker pattern for LLM provider reliability and fault tolerance.
Includes configurable failure thresholds, recovery mechanisms, and health monitoring.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager
import random

from .logging import get_logger
from .metrics import increment_counter, record_histogram, set_gauge


logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests due to failures  
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    
    # Failure detection
    failure_threshold: int = 5  # Failures needed to open circuit
    success_threshold: int = 3  # Successes needed to close circuit from half-open
    timeout_seconds: float = 60.0  # How long to wait before trying half-open
    
    # Health check settings
    health_check_interval: float = 30.0  # Seconds between health checks
    health_check_timeout: float = 10.0   # Timeout for health check requests
    
    # Monitoring
    enable_metrics: bool = True
    enable_alerts: bool = True


@dataclass
class CircuitBreakerStats:
    """Statistics tracking for circuit breaker."""
    
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    circuit_opens: int = 0
    circuit_closes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    failure_reasons: List[str] = field(default_factory=list)
    
    def get_success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100.0
    
    def get_recent_failures(self, window_minutes: int = 5) -> int:
        """Get number of failures in recent time window."""
        if not self.failure_reasons:
            return 0
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
        # For simplicity, return total failures (could be enhanced to track timestamps)
        return len([f for f in self.failure_reasons[-10:]])  # Last 10 failures


class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open."""
    
    def __init__(self, circuit_name: str, state: CircuitState, last_failure_time: Optional[datetime] = None):
        self.circuit_name = circuit_name
        self.state = state
        self.last_failure_time = last_failure_time
        
        if last_failure_time:
            message = f"Circuit breaker '{circuit_name}' is {state.value}. Last failure at {last_failure_time}"
        else:
            message = f"Circuit breaker '{circuit_name}' is {state.value}"
            
        super().__init__(message)


class CircuitBreaker:
    """
    Circuit breaker implementation with configurable failure detection,
    recovery mechanisms, and health monitoring.
    """
    
    def __init__(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None,
        health_check_func: Optional[Callable[[], Awaitable[bool]]] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Unique identifier for this circuit
            config: Configuration settings
            health_check_func: Optional async function to check service health
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.health_check_func = health_check_func
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_health_check: Optional[float] = None
        
        # Statistics
        self.stats = CircuitBreakerStats()
        
        # Concurrency control
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        if self.config.enable_metrics:
            # Start background health checks if configured
            if self.health_check_func:
                self._health_check_task = asyncio.create_task(self._health_check_loop())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
    
    @asynccontextmanager
    async def call(self):
        """
        Context manager for protected calls.
        
        Usage:
            async with circuit_breaker.call():
                result = await some_external_service()
        """
        await self._check_state()
        
        if self.state == CircuitState.OPEN:
            increment_counter("circuit_breaker_blocked", 1, circuit_name=self.name)
            raise CircuitBreakerException(self.name, self.state, 
                                        datetime.fromtimestamp(self.last_failure_time) if self.last_failure_time else None)
        
        start_time = time.perf_counter()
        success = False
        
        try:
            yield
            success = True
            await self._on_success()
            
        except Exception as e:
            await self._on_failure(e)
            raise
        finally:
            # Record timing metrics
            duration_ms = (time.perf_counter() - start_time) * 1000
            record_histogram("circuit_breaker_call_duration_ms", duration_ms, 
                           circuit_name=self.name, success=str(success).lower())
    
    async def _check_state(self):
        """Check and update circuit breaker state."""
        async with self._lock:
            now = time.time()
            
            if self.state == CircuitState.OPEN:
                # Check if timeout has passed for half-open transition
                if self.last_failure_time and (now - self.last_failure_time) >= self.config.timeout_seconds:
                    await self._transition_to_half_open()
            
            # Update metrics
            if self.config.enable_metrics:
                set_gauge("circuit_breaker_state", self._state_to_numeric(), circuit_name=self.name)
                set_gauge("circuit_breaker_failure_count", self.failure_count, circuit_name=self.name)
                set_gauge("circuit_breaker_success_rate", self.stats.get_success_rate(), circuit_name=self.name)
    
    async def _on_success(self):
        """Handle successful operation."""
        async with self._lock:
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.last_success_time = datetime.utcnow()
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.info(
                    "Circuit breaker success in half-open state",
                    circuit_name=self.name,
                    success_count=self.success_count,
                    required_successes=self.config.success_threshold
                )
                
                if self.success_count >= self.config.success_threshold:
                    await self._transition_to_closed()
            
            # Reset failure count on any success
            self.failure_count = 0
            
            # Record success metrics
            if self.config.enable_metrics:
                increment_counter("circuit_breaker_success", 1, circuit_name=self.name)
    
    async def _on_failure(self, exception: Exception):
        """Handle failed operation."""
        async with self._lock:
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.last_failure_time = datetime.utcnow()
            self.stats.failure_reasons.append(f"{exception.__class__.__name__}: {str(exception)}")
            
            # Keep only recent failure reasons to prevent memory growth
            if len(self.stats.failure_reasons) > 50:
                self.stats.failure_reasons = self.stats.failure_reasons[-25:]
            
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            logger.warning(
                "Circuit breaker failure recorded",
                circuit_name=self.name,
                failure_count=self.failure_count,
                error_type=exception.__class__.__name__,
                error_message=str(exception)
            )
            
            # Check if we should open the circuit
            if self.state == CircuitState.CLOSED and self.failure_count >= self.config.failure_threshold:
                await self._transition_to_open()
            elif self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                await self._transition_to_open()
            
            # Record failure metrics
            if self.config.enable_metrics:
                increment_counter("circuit_breaker_failure", 1, 
                                circuit_name=self.name, 
                                error_type=exception.__class__.__name__)
    
    async def _transition_to_open(self):
        """Transition circuit breaker to OPEN state."""
        if self.state != CircuitState.OPEN:
            old_state = self.state
            self.state = CircuitState.OPEN
            self.success_count = 0
            self.stats.circuit_opens += 1
            
            logger.error(
                "Circuit breaker opened",
                circuit_name=self.name,
                previous_state=old_state.value,
                failure_count=self.failure_count,
                failure_threshold=self.config.failure_threshold
            )
            
            if self.config.enable_metrics:
                increment_counter("circuit_breaker_state_change", 1, 
                                circuit_name=self.name, 
                                from_state=old_state.value, 
                                to_state=self.state.value)
    
    async def _transition_to_half_open(self):
        """Transition circuit breaker to HALF_OPEN state."""
        if self.state != CircuitState.HALF_OPEN:
            old_state = self.state
            self.state = CircuitState.HALF_OPEN
            self.success_count = 0
            
            logger.info(
                "Circuit breaker transitioned to half-open",
                circuit_name=self.name,
                previous_state=old_state.value,
                timeout_seconds=self.config.timeout_seconds
            )
            
            if self.config.enable_metrics:
                increment_counter("circuit_breaker_state_change", 1,
                                circuit_name=self.name,
                                from_state=old_state.value,
                                to_state=self.state.value)
    
    async def _transition_to_closed(self):
        """Transition circuit breaker to CLOSED state."""
        if self.state != CircuitState.CLOSED:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.stats.circuit_closes += 1
            
            logger.info(
                "Circuit breaker closed",
                circuit_name=self.name,
                previous_state=old_state.value,
                success_count=self.success_count
            )
            
            if self.config.enable_metrics:
                increment_counter("circuit_breaker_state_change", 1,
                                circuit_name=self.name,
                                from_state=old_state.value,
                                to_state=self.state.value)
    
    async def _health_check_loop(self):
        """Background health check loop."""
        logger.debug("Starting health check loop", circuit_name=self.name)
        
        try:
            while True:
                await asyncio.sleep(self.config.health_check_interval)
                
                # Only do health checks if circuit is open or we haven't checked recently
                now = time.time()
                should_check = (
                    self.state == CircuitState.OPEN or 
                    not self.last_health_check or 
                    (now - self.last_health_check) >= self.config.health_check_interval
                )
                
                if should_check and self.health_check_func:
                    await self._perform_health_check()
                    
        except asyncio.CancelledError:
            logger.debug("Health check loop cancelled", circuit_name=self.name)
            raise
        except Exception as e:
            logger.error("Health check loop error", circuit_name=self.name, error=str(e))
    
    async def _perform_health_check(self):
        """Perform health check on the service."""
        try:
            # Run health check with timeout
            health_check_result = await asyncio.wait_for(
                self.health_check_func(),
                timeout=self.config.health_check_timeout
            )
            
            self.last_health_check = time.time()
            
            if health_check_result:
                logger.debug("Health check passed", circuit_name=self.name)
                
                # If circuit is open and health check passes, transition to half-open
                if self.state == CircuitState.OPEN:
                    await self._transition_to_half_open()
                    
                if self.config.enable_metrics:
                    increment_counter("circuit_breaker_health_check", 1, 
                                    circuit_name=self.name, result="success")
            else:
                logger.warning("Health check failed", circuit_name=self.name)
                if self.config.enable_metrics:
                    increment_counter("circuit_breaker_health_check", 1,
                                    circuit_name=self.name, result="failure")
                
        except asyncio.TimeoutError:
            logger.warning("Health check timed out", circuit_name=self.name, 
                         timeout=self.config.health_check_timeout)
            if self.config.enable_metrics:
                increment_counter("circuit_breaker_health_check", 1,
                                circuit_name=self.name, result="timeout")
        except Exception as e:
            logger.warning("Health check exception", circuit_name=self.name, 
                         error_type=e.__class__.__name__, error=str(e))
            if self.config.enable_metrics:
                increment_counter("circuit_breaker_health_check", 1,
                                circuit_name=self.name, result="exception")
    
    def _state_to_numeric(self) -> float:
        """Convert state to numeric value for metrics."""
        return {
            CircuitState.CLOSED: 0.0,
            CircuitState.HALF_OPEN: 0.5,
            CircuitState.OPEN: 1.0
        }.get(self.state, -1.0)
    
    # Public API methods
    
    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self.state
    
    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self.stats
    
    def is_available(self) -> bool:
        """Check if circuit breaker allows calls."""
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
    
    async def force_open(self):
        """Manually force circuit breaker to open state."""
        async with self._lock:
            await self._transition_to_open()
            logger.warning("Circuit breaker manually forced open", circuit_name=self.name)
    
    async def force_close(self):
        """Manually force circuit breaker to closed state."""
        async with self._lock:
            await self._transition_to_closed()
            logger.info("Circuit breaker manually forced closed", circuit_name=self.name)
    
    async def reset(self):
        """Reset circuit breaker statistics and state."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.last_health_check = None
            self.stats = CircuitBreakerStats()
            
            logger.info("Circuit breaker reset", circuit_name=self.name)
            
            if self.config.enable_metrics:
                increment_counter("circuit_breaker_reset", 1, circuit_name=self.name)


# Circuit breaker manager for multiple circuits

class CircuitBreakerManager:
    """Manages multiple circuit breakers with shared configuration."""
    
    def __init__(self, default_config: Optional[CircuitBreakerConfig] = None):
        """Initialize manager with default configuration."""
        self.default_config = default_config or CircuitBreakerConfig()
        self.circuits: Dict[str, CircuitBreaker] = {}
        
    def get_or_create_circuit(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None,
        health_check_func: Optional[Callable[[], Awaitable[bool]]] = None
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one."""
        if name not in self.circuits:
            circuit_config = config or self.default_config
            self.circuits[name] = CircuitBreaker(name, circuit_config, health_check_func)
            
        return self.circuits[name]
    
    def get_all_circuits(self) -> Dict[str, CircuitBreaker]:
        """Get all managed circuit breakers."""
        return dict(self.circuits)
    
    def get_circuit_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuits."""
        return {
            name: {
                "state": circuit.get_state().value,
                "stats": circuit.get_stats(),
                "is_available": circuit.is_available()
            }
            for name, circuit in self.circuits.items()
        }
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Perform health checks on all circuits with health check functions."""
        results = {}
        
        for name, circuit in self.circuits.items():
            if circuit.health_check_func:
                try:
                    results[name] = await circuit.health_check_func()
                except Exception as e:
                    logger.warning(f"Health check failed for {name}: {e}")
                    results[name] = False
            else:
                results[name] = circuit.is_available()
                
        return results
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        for circuit in self.circuits.values():
            await circuit.reset()


# Global circuit breaker manager
_circuit_manager = CircuitBreakerManager()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager."""
    return _circuit_manager


def get_circuit_breaker(
    name: str, 
    config: Optional[CircuitBreakerConfig] = None,
    health_check_func: Optional[Callable[[], Awaitable[bool]]] = None
) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    return _circuit_manager.get_or_create_circuit(name, config, health_check_func)