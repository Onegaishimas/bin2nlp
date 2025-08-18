"""
Structured logging configuration using structlog.

Provides centralized logging setup with correlation ID support, 
sensitive data redaction, and configurable formatters for development
and production environments.
"""

import json
import logging
import logging.handlers
import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from structlog.typing import Processor

from .config import get_settings, LoggingSettings


# Context variable for correlation ID tracking
correlation_id_context: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class CorrelationIDProcessor:
    """Add correlation ID to log entries."""
    
    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add correlation ID from context to log entry."""
        correlation_id = correlation_id_context.get()
        if correlation_id:
            event_dict['correlation_id'] = correlation_id
        return event_dict


class SensitiveDataRedactor:
    """Redact sensitive data from log entries."""
    
    def __init__(self, sensitive_fields: Optional[List[str]] = None):
        """
        Initialize redactor with sensitive field names.
        
        Args:
            sensitive_fields: List of field names to redact
        """
        self.sensitive_fields = set(sensitive_fields or [
            'password', 'api_key', 'token', 'secret', 'authorization', 
            'auth', 'key', 'credential', 'private_key', 'session_id'
        ])
    
    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields from log entry."""
        return self._redact_dict(event_dict)
    
    def _redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive fields from dictionary."""
        redacted = {}
        
        for key, value in data.items():
            if self._is_sensitive_field(key):
                redacted[key] = self._redact_value(value)
            elif isinstance(value, dict):
                redacted[key] = self._redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [self._redact_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                redacted[key] = value
        
        return redacted
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if field name contains sensitive information."""
        field_lower = field_name.lower()
        return any(sensitive in field_lower for sensitive in self.sensitive_fields)
    
    def _redact_value(self, value: Any) -> str:
        """Redact sensitive value while preserving type information."""
        if value is None:
            return None
        elif isinstance(value, str):
            if len(value) <= 8:
                return "***"
            else:
                return f"{value[:2]}***{value[-2:]}"
        else:
            return f"<redacted:{type(value).__name__}>"


class RequestContextProcessor:
    """Add request context information to log entries."""
    
    def __call__(self, logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add request context to log entry if available."""
        # This will be populated by API middleware
        # For now, just ensure the structure exists
        if 'request_id' not in event_dict:
            event_dict['request_id'] = correlation_id_context.get()
        
        return event_dict


class JSONFormatter:
    """Custom JSON formatter for structured logs."""
    
    def __init__(self, include_timestamp: bool = True, include_level: bool = True):
        """
        Initialize JSON formatter.
        
        Args:
            include_timestamp: Whether to include timestamp
            include_level: Whether to include log level
        """
        self.include_timestamp = include_timestamp
        self.include_level = include_level
    
    def __call__(self, logger: Any, name: str, event_dict: Dict[str, Any]) -> str:
        """Format log entry as JSON."""
        # Add standard fields
        if self.include_timestamp and 'timestamp' not in event_dict:
            event_dict['timestamp'] = structlog.dev.ConsoleRenderer._get_timestamp()
        
        if self.include_level and 'level' not in event_dict:
            event_dict['level'] = name.upper()
        
        # Ensure message is present
        if 'event' in event_dict:
            event_dict['message'] = event_dict.pop('event')
        
        try:
            return json.dumps(event_dict, sort_keys=True, default=str)
        except (TypeError, ValueError) as e:
            # Fallback for non-serializable objects
            fallback_dict = {
                'timestamp': structlog.dev.ConsoleRenderer._get_timestamp(),
                'level': 'ERROR',
                'message': f'Log serialization error: {e}',
                'original_event': str(event_dict),
                'error': str(e)
            }
            return json.dumps(fallback_dict, sort_keys=True)


class DevelopmentFormatter:
    """Human-readable formatter for development."""
    
    def __init__(self):
        """Initialize development formatter."""
        self.console_renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback
        )
    
    def __call__(self, logger: Any, name: str, event_dict: Dict[str, Any]) -> str:
        """Format log entry for development console."""
        # Add level to event dict for console renderer
        event_dict['level'] = name.upper()
        return self.console_renderer(logger, name, event_dict)


class LoggingManager:
    """Central logging configuration manager."""
    
    def __init__(self):
        """Initialize logging manager."""
        self.is_configured = False
        self.settings: Optional[LoggingSettings] = None
    
    def configure_logging(self, settings: Optional[LoggingSettings] = None) -> None:
        """
        Configure structured logging based on settings.
        
        Args:
            settings: Logging settings (uses default if None)
        """
        if settings is None:
            app_settings = get_settings()
            settings = app_settings.logging
        
        self.settings = settings
        
        # Configure Python logging
        self._configure_stdlib_logging(settings)
        
        # Configure structlog
        self._configure_structlog(settings)
        
        self.is_configured = True
    
    def _configure_stdlib_logging(self, settings: LoggingSettings) -> None:
        """Configure standard library logging."""
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        # Set log level
        log_level = getattr(logging, settings.level.upper())
        root_logger.setLevel(log_level)
        
        # Create formatter based on format setting
        if settings.format == "json":
            formatter = logging.Formatter('%(message)s')
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
        
        # File handler (if configured)
        if settings.file_path:
            file_path = Path(settings.file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                filename=str(file_path),
                maxBytes=settings.max_file_size_mb * 1024 * 1024,
                backupCount=settings.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            root_logger.addHandler(file_handler)
    
    def _configure_structlog(self, settings: LoggingSettings) -> None:
        """Configure structlog processors and formatting."""
        # Build processor chain
        processors: List[Processor] = [
            # Add standard fields
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
        ]
        
        # Add correlation ID processor if enabled
        if settings.enable_correlation_id:
            processors.append(CorrelationIDProcessor())
        
        # Add request context processor
        processors.append(RequestContextProcessor())
        
        # Add sensitive data redactor
        processors.append(SensitiveDataRedactor(settings.sensitive_fields))
        
        # Add appropriate formatter
        if settings.format == "json":
            processors.append(JSONFormatter())
        else:
            processors.append(DevelopmentFormatter())
        
        # Add stdlib processor (must be last)
        processors.append(structlog.stdlib.ProcessorFormatter.wrap_for_formatter)
        
        # Configure structlog
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            context_class=dict,
            cache_logger_on_first_use=True,
        )
    
    def get_logger(self, name: str = None) -> structlog.BoundLogger:
        """
        Get structured logger instance.
        
        Args:
            name: Logger name (uses calling module if None)
            
        Returns:
            Configured structlog logger
        """
        if not self.is_configured:
            self.configure_logging()
        
        return structlog.get_logger(name)


# Global logging manager instance
_logging_manager = LoggingManager()


def configure_logging(settings: Optional[LoggingSettings] = None) -> None:
    """
    Configure application logging.
    
    Args:
        settings: Logging settings (uses default if None)
    """
    _logging_manager.configure_logging(settings)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get structured logger for the calling module.
    
    Args:
        name: Logger name (uses calling module if None)
        
    Returns:
        Configured structlog logger
        
    Example:
        logger = get_logger(__name__)
        logger.info("Analysis started", file_size=1024, format="PE")
    """
    return _logging_manager.get_logger(name)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """
    Set correlation ID for request tracking.
    
    Args:
        correlation_id: Correlation ID to set (generates UUID if None)
        
    Returns:
        The correlation ID that was set
        
    Example:
        correlation_id = set_correlation_id()
        logger = get_logger(__name__)
        logger.info("Request started", correlation_id=correlation_id)
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    correlation_id_context.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """
    Get current correlation ID from context.
    
    Returns:
        Current correlation ID or None
    """
    return correlation_id_context.get()


def clear_correlation_id() -> None:
    """Clear correlation ID from context."""
    correlation_id_context.set(None)


def create_request_logger(
    logger: structlog.BoundLogger, 
    request_id: Optional[str] = None, 
    user_id: Optional[str] = None,
    **extra_context
) -> structlog.BoundLogger:
    """
    Create logger with request context.
    
    Args:
        logger: Base logger instance
        request_id: Request identifier
        user_id: User identifier  
        **extra_context: Additional context fields
        
    Returns:
        Logger bound with request context
        
    Example:
        base_logger = get_logger(__name__)
        request_logger = create_request_logger(
            base_logger, 
            request_id="req_123", 
            user_id="user_456",
            endpoint="/api/v1/analyze"
        )
        request_logger.info("Request received")
    """
    context = {}
    
    if request_id:
        context['request_id'] = request_id
    
    if user_id:
        context['user_id'] = user_id
    
    context.update(extra_context)
    
    return logger.bind(**context)


def log_function_call(
    logger: structlog.BoundLogger,
    function_name: str,
    args: Optional[Dict[str, Any]] = None,
    **context
) -> structlog.BoundLogger:
    """
    Log function call with parameters.
    
    Args:
        logger: Logger instance
        function_name: Name of the function being called
        args: Function arguments to log
        **context: Additional context
        
    Returns:
        Logger bound with function context
        
    Example:
        logger = get_logger(__name__)
        func_logger = log_function_call(
            logger, 
            "analyze_binary", 
            args={"file_path": "/tmp/binary.exe", "depth": "standard"}
        )
        func_logger.info("Function started")
    """
    call_context = {
        'function': function_name,
        **context
    }
    
    if args:
        # Redact sensitive arguments
        redactor = SensitiveDataRedactor()
        call_context['args'] = redactor._redact_dict(args)
    
    return logger.bind(**call_context)


# Performance monitoring utilities

class LoggingTimer:
    """Context manager for timing operations with logging."""
    
    def __init__(
        self, 
        logger: structlog.BoundLogger, 
        operation: str, 
        **context
    ):
        """
        Initialize logging timer.
        
        Args:
            logger: Logger instance
            operation: Operation being timed
            **context: Additional context
        """
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None
    
    def __enter__(self) -> 'LoggingTimer':
        """Start timing operation."""
        import time
        self.start_time = time.perf_counter()
        self.logger.info(
            f"{self.operation} started",
            operation=self.operation,
            **self.context
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End timing operation and log results."""
        import time
        duration = time.perf_counter() - self.start_time
        
        if exc_type is None:
            self.logger.info(
                f"{self.operation} completed",
                operation=self.operation,
                duration_seconds=round(duration, 3),
                **self.context
            )
        else:
            self.logger.error(
                f"{self.operation} failed",
                operation=self.operation,
                duration_seconds=round(duration, 3),
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                **self.context
            )


def time_operation(
    logger: structlog.BoundLogger, 
    operation: str, 
    **context
) -> LoggingTimer:
    """
    Create timing context manager for operation.
    
    Args:
        logger: Logger instance
        operation: Operation being timed
        **context: Additional context
        
    Returns:
        Timing context manager
        
    Example:
        logger = get_logger(__name__)
        with time_operation(logger, "binary_analysis", file_size=1024):
            # Perform analysis
            pass
    """
    return LoggingTimer(logger, operation, **context)


# Module initialization - configure logging if not already done
def ensure_logging_configured() -> None:
    """Ensure logging is configured (called on module import)."""
    if not _logging_manager.is_configured:
        try:
            _logging_manager.configure_logging()
        except Exception:
            # If configuration fails, set up basic logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )


# Initialize logging on import
ensure_logging_configured()