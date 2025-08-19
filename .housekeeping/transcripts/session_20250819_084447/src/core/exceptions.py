"""
Custom exception hierarchy for the bin2nlp analysis system.

Provides structured error handling with specific exception types for different
failure scenarios across analysis, validation, configuration, and processing.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime


class BinaryAnalysisException(Exception):
    """
    Base exception for all bin2nlp analysis system errors.
    
    Provides common functionality for error handling, logging context,
    and error reporting across all system components.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        component: Optional[str] = None
    ):
        """
        Initialize base exception with context information.
        
        Args:
            message: Human-readable error message
            error_code: Specific error code for programmatic handling
            details: Additional context and debugging information
            correlation_id: Request correlation ID for tracing
            component: System component where error occurred
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}
        self.correlation_id = correlation_id
        self.component = component
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/API responses."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "component": self.component,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"message='{self.message}', "
            f"error_code='{self.error_code}', "
            f"component='{self.component}', "
            f"correlation_id='{self.correlation_id}'"
            f")"
        )


class ValidationException(BinaryAnalysisException):
    """
    Exception raised for data validation failures.
    
    Used when input data, configuration, or file content fails
    validation checks before processing.
    """
    
    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize validation exception with field context.
        
        Args:
            message: Validation error message
            field_name: Name of the field that failed validation
            field_value: Value that failed validation (sanitized)
            validation_rule: Rule or constraint that was violated
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if field_name:
            details['field_name'] = field_name
        if field_value is not None:
            # Sanitize sensitive values
            if isinstance(field_value, str) and len(field_value) > 100:
                details['field_value'] = field_value[:100] + "..."
            else:
                details['field_value'] = str(field_value)
        if validation_rule:
            details['validation_rule'] = validation_rule
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'VALIDATION_ERROR')
        super().__init__(message, **kwargs)
        
        self.field_name = field_name
        self.field_value = field_value
        self.validation_rule = validation_rule


class AnalysisException(BinaryAnalysisException):
    """
    Exception raised during binary analysis operations.
    
    Used for errors that occur during file parsing, analysis engine
    execution, or result generation.
    """
    
    def __init__(
        self,
        message: str,
        analysis_id: Optional[str] = None,
        file_path: Optional[str] = None,
        analysis_stage: Optional[str] = None,
        engine_error: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize analysis exception with analysis context.
        
        Args:
            message: Analysis error message
            analysis_id: Unique identifier for the analysis job
            file_path: Path to file being analyzed
            analysis_stage: Stage of analysis where error occurred
            engine_error: Raw error from analysis engine (radare2, etc.)
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if analysis_id:
            details['analysis_id'] = analysis_id
        if file_path:
            details['file_path'] = file_path
        if analysis_stage:
            details['analysis_stage'] = analysis_stage
        if engine_error:
            details['engine_error'] = engine_error
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'ANALYSIS_ERROR')
        kwargs['component'] = kwargs.get('component', 'analysis_engine')
        super().__init__(message, **kwargs)
        
        self.analysis_id = analysis_id
        self.file_path = file_path
        self.analysis_stage = analysis_stage
        self.engine_error = engine_error


class ConfigurationException(BinaryAnalysisException):
    """
    Exception raised for configuration-related errors.
    
    Used when application configuration is invalid, missing,
    or incompatible with system requirements.
    """
    
    def __init__(
        self,
        message: str,
        config_section: Optional[str] = None,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize configuration exception with config context.
        
        Args:
            message: Configuration error message
            config_section: Configuration section with error
            config_key: Specific configuration key
            config_value: Configuration value that caused error
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if config_section:
            details['config_section'] = config_section
        if config_key:
            details['config_key'] = config_key
        if config_value is not None:
            details['config_value'] = str(config_value)
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'CONFIGURATION_ERROR')
        kwargs['component'] = kwargs.get('component', 'configuration')
        super().__init__(message, **kwargs)
        
        self.config_section = config_section
        self.config_key = config_key
        self.config_value = config_value


class CacheException(BinaryAnalysisException):
    """
    Exception raised for cache operation failures.
    
    Used when Redis operations, cache invalidation, or cache
    consistency checks fail.
    """
    
    def __init__(
        self,
        message: str,
        cache_key: Optional[str] = None,
        operation: Optional[str] = None,
        redis_error: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize cache exception with cache context.
        
        Args:
            message: Cache error message
            cache_key: Cache key involved in operation
            operation: Cache operation that failed (get, set, delete, etc.)
            redis_error: Raw Redis error message
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if cache_key:
            details['cache_key'] = cache_key
        if operation:
            details['operation'] = operation
        if redis_error:
            details['redis_error'] = redis_error
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'CACHE_ERROR')
        kwargs['component'] = kwargs.get('component', 'cache')
        super().__init__(message, **kwargs)
        
        self.cache_key = cache_key
        self.operation = operation
        self.redis_error = redis_error


class CacheConnectionError(CacheException):
    """Exception raised when Redis connection fails."""
    
    def __init__(self, message: str, **kwargs):
        kwargs['error_code'] = kwargs.get('error_code', 'CACHE_CONNECTION_ERROR')
        super().__init__(message, **kwargs)


class CacheTimeoutError(CacheException):
    """Exception raised when Redis operations timeout."""
    
    def __init__(self, message: str, **kwargs):
        kwargs['error_code'] = kwargs.get('error_code', 'CACHE_TIMEOUT_ERROR')
        super().__init__(message, **kwargs)


class ProcessingException(BinaryAnalysisException):
    """
    Exception raised during job processing and workflow operations.
    
    Used for errors in job queue management, worker coordination,
    and background task processing.
    """
    
    def __init__(
        self,
        message: str,
        job_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        queue_name: Optional[str] = None,
        processing_stage: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize processing exception with job context.
        
        Args:
            message: Processing error message
            job_id: Job identifier being processed
            worker_id: Worker that encountered the error
            queue_name: Queue where job was processed
            processing_stage: Stage of processing where error occurred
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if job_id:
            details['job_id'] = job_id
        if worker_id:
            details['worker_id'] = worker_id
        if queue_name:
            details['queue_name'] = queue_name
        if processing_stage:
            details['processing_stage'] = processing_stage
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'PROCESSING_ERROR')
        kwargs['component'] = kwargs.get('component', 'job_processor')
        super().__init__(message, **kwargs)
        
        self.job_id = job_id
        self.worker_id = worker_id
        self.queue_name = queue_name
        self.processing_stage = processing_stage


class AuthenticationException(BinaryAnalysisException):
    """
    Exception raised for authentication and authorization failures.
    
    Used when API key validation, rate limiting, or access control
    checks fail.
    """
    
    def __init__(
        self,
        message: str,
        api_key_id: Optional[str] = None,
        required_scope: Optional[str] = None,
        client_ip: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize authentication exception with auth context.
        
        Args:
            message: Authentication error message
            api_key_id: API key involved in authentication
            required_scope: Required permission scope
            client_ip: Client IP address
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if api_key_id:
            details['api_key_id'] = api_key_id
        if required_scope:
            details['required_scope'] = required_scope
        if client_ip:
            details['client_ip'] = client_ip
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'AUTHENTICATION_ERROR')
        kwargs['component'] = kwargs.get('component', 'authentication')
        super().__init__(message, **kwargs)
        
        self.api_key_id = api_key_id
        self.required_scope = required_scope
        self.client_ip = client_ip


class RateLimitException(BinaryAnalysisException):
    """
    Exception raised when rate limits are exceeded.
    
    Used when API request rates exceed configured limits for
    API keys or client IPs.
    """
    
    def __init__(
        self,
        message: str,
        limit_type: Optional[str] = None,
        limit_value: Optional[int] = None,
        current_usage: Optional[int] = None,
        reset_time: Optional[datetime] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize rate limit exception with limit context.
        
        Args:
            message: Rate limit error message
            limit_type: Type of limit exceeded (per_minute, per_day, etc.)
            limit_value: Maximum allowed requests
            current_usage: Current request count
            reset_time: When the limit resets
            retry_after: Seconds to wait before retry
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if limit_type:
            details['limit_type'] = limit_type
        if limit_value is not None:
            details['limit_value'] = limit_value
        if current_usage is not None:
            details['current_usage'] = current_usage
        if reset_time:
            details['reset_time'] = reset_time.isoformat()
        if retry_after is not None:
            details['retry_after'] = retry_after
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'RATE_LIMIT_ERROR')
        kwargs['component'] = kwargs.get('component', 'rate_limiter')
        super().__init__(message, **kwargs)
        
        self.limit_type = limit_type
        self.limit_value = limit_value
        self.current_usage = current_usage
        self.reset_time = reset_time
        self.retry_after = retry_after


class UnsupportedFormatException(AnalysisException):
    """
    Exception raised when encountering unsupported file formats.
    
    Used when file format detection identifies a format that is not
    supported by the analysis engine.
    """
    
    def __init__(self, message: str, detected_format: Optional[str] = None, **kwargs):
        kwargs['error_code'] = kwargs.get('error_code', 'UNSUPPORTED_FORMAT')
        details = kwargs.get('details', {})
        if detected_format:
            details['detected_format'] = detected_format
        kwargs['details'] = details
        super().__init__(message, **kwargs)
        self.detected_format = detected_format


# Alias for backward compatibility
FileFormatException = UnsupportedFormatException
DecompilationException = AnalysisException


class LLMProviderException(BinaryAnalysisException):
    """
    Exception raised for LLM provider-related errors.
    
    Used when LLM API calls, provider connectivity, or
    translation operations fail.
    """
    
    def __init__(
        self,
        message: str,
        provider_id: Optional[str] = None,
        error_code: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize LLM provider exception.
        
        Args:
            message: Error message
            provider_id: LLM provider identifier (openai, anthropic, etc.)
            error_code: Provider-specific error code
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if provider_id:
            details['provider_id'] = provider_id
        
        kwargs['details'] = details
        kwargs['error_code'] = error_code or kwargs.get('error_code', 'LLM_PROVIDER_ERROR')
        kwargs['component'] = kwargs.get('component', 'llm_provider')
        super().__init__(message, **kwargs)
        
        self.provider_id = provider_id


class LLMRateLimitException(LLMProviderException):
    """
    Exception raised when LLM provider rate limits are exceeded.
    
    Used when API rate limits or quotas are hit for specific
    LLM providers.
    """
    
    def __init__(
        self,
        message: str,
        provider_id: str,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize LLM rate limit exception.
        
        Args:
            message: Rate limit error message
            provider_id: LLM provider identifier
            retry_after: Seconds to wait before retry
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if retry_after is not None:
            details['retry_after'] = retry_after
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'LLM_RATE_LIMIT_ERROR')
        super().__init__(message, provider_id=provider_id, **kwargs)
        
        self.retry_after = retry_after


class LLMCostLimitException(LLMProviderException):
    """
    Exception raised when LLM usage would exceed cost limits.
    
    Used when estimated or actual costs would exceed user
    or system-defined spending limits.
    """
    
    def __init__(
        self,
        message: str,
        provider_id: str,
        estimated_cost: Optional[float] = None,
        limit: Optional[float] = None,
        **kwargs
    ):
        """
        Initialize LLM cost limit exception.
        
        Args:
            message: Cost limit error message
            provider_id: LLM provider identifier
            estimated_cost: Estimated operation cost in USD
            limit: Cost limit that would be exceeded
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if estimated_cost is not None:
            details['estimated_cost'] = estimated_cost
        if limit is not None:
            details['limit'] = limit
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'LLM_COST_LIMIT_ERROR')
        super().__init__(message, provider_id=provider_id, **kwargs)
        
        self.estimated_cost = estimated_cost
        self.limit = limit


class FileValidationException(ValidationException):
    """
    Exception raised when file content validation fails.
    
    Used when files fail integrity checks, size validation, or
    content validation before analysis.
    """
    
    def __init__(self, message: str, validation_type: Optional[str] = None, **kwargs):
        kwargs['error_code'] = kwargs.get('error_code', 'FILE_VALIDATION_ERROR')
        details = kwargs.get('details', {})
        if validation_type:
            details['validation_type'] = validation_type
        kwargs['details'] = details
        super().__init__(message, **kwargs)
        self.validation_type = validation_type


class ProcessorException(AnalysisException):
    """
    Exception raised during processor operations.
    
    Used when decompilation processors (string extraction, function analysis,
    radare2 integration, etc.) encounter errors during processing.
    """
    
    def __init__(
        self,
        message: str,
        processor_name: Optional[str] = None,
        processor_stage: Optional[str] = None,
        **kwargs
    ):
        kwargs['error_code'] = kwargs.get('error_code', 'PROCESSOR_ERROR')
        details = kwargs.get('details', {})
        if processor_name:
            details['processor_name'] = processor_name
        if processor_stage:
            details['processor_stage'] = processor_stage
        kwargs['details'] = details
        super().__init__(message, **kwargs)
        self.processor_name = processor_name
        self.processor_stage = processor_stage


class AnalysisTimeoutException(AnalysisException):
    """
    Exception raised when analysis operations exceed time limits.
    
    Used when analysis engines, processors, or radare2 operations
    take longer than configured timeout values.
    """
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[int] = None,
        elapsed_seconds: Optional[float] = None,
        **kwargs
    ):
        kwargs['error_code'] = kwargs.get('error_code', 'ANALYSIS_TIMEOUT')
        details = kwargs.get('details', {})
        if timeout_seconds is not None:
            details['timeout_seconds'] = timeout_seconds
        if elapsed_seconds is not None:
            details['elapsed_seconds'] = elapsed_seconds
        kwargs['details'] = details
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds


class FileException(BinaryAnalysisException):
    """
    Exception raised for file operation failures.
    
    Used when file upload, validation, parsing, or storage
    operations encounter errors.
    """
    
    def __init__(
        self,
        message: str,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None,
        file_format: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize file exception with file context.
        
        Args:
            message: File error message
            file_path: Path to file that caused error
            file_size: Size of file in bytes
            file_format: Detected or expected file format
            operation: File operation that failed
            **kwargs: Additional context for base exception
        """
        details = kwargs.get('details', {})
        if file_path:
            details['file_path'] = file_path
        if file_size is not None:
            details['file_size'] = file_size
        if file_format:
            details['file_format'] = file_format
        if operation:
            details['operation'] = operation
        
        kwargs['details'] = details
        kwargs['error_code'] = kwargs.get('error_code', 'FILE_ERROR')
        kwargs['component'] = kwargs.get('component', 'file_handler')
        super().__init__(message, **kwargs)
        
        self.file_path = file_path
        self.file_size = file_size
        self.file_format = file_format
        self.operation = operation


# Exception factory functions for common error scenarios

def create_validation_error(
    field_name: str,
    field_value: Any,
    validation_rule: str,
    correlation_id: Optional[str] = None
) -> ValidationException:
    """Create a standardized validation error."""
    message = f"Validation failed for field '{field_name}': {validation_rule}"
    return ValidationException(
        message=message,
        field_name=field_name,
        field_value=field_value,
        validation_rule=validation_rule,
        correlation_id=correlation_id
    )


def create_analysis_error(
    analysis_id: str,
    stage: str,
    error_message: str,
    engine_error: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> AnalysisException:
    """Create a standardized analysis error."""
    message = f"Analysis failed at stage '{stage}': {error_message}"
    return AnalysisException(
        message=message,
        analysis_id=analysis_id,
        analysis_stage=stage,
        engine_error=engine_error,
        correlation_id=correlation_id
    )


def create_rate_limit_error(
    limit_type: str,
    limit_value: int,
    current_usage: int,
    retry_after: int,
    correlation_id: Optional[str] = None
) -> RateLimitException:
    """Create a standardized rate limit error."""
    message = f"Rate limit exceeded: {current_usage}/{limit_value} {limit_type}"
    return RateLimitException(
        message=message,
        limit_type=limit_type,
        limit_value=limit_value,
        current_usage=current_usage,
        retry_after=retry_after,
        correlation_id=correlation_id
    )


def create_file_error(
    file_path: str,
    operation: str,
    error_message: str,
    file_size: Optional[int] = None,
    correlation_id: Optional[str] = None
) -> FileException:
    """Create a standardized file error."""
    message = f"File operation '{operation}' failed: {error_message}"
    return FileException(
        message=message,
        file_path=file_path,
        operation=operation,
        file_size=file_size,
        correlation_id=correlation_id
    )


# Error handling utilities

def get_exception_chain(exception: Exception) -> List[Dict[str, Any]]:
    """
    Extract the full exception chain for logging.
    
    Args:
        exception: Exception to analyze
        
    Returns:
        List of exception dictionaries with type, message, and context
    """
    chain = []
    current = exception
    
    while current is not None:
        if isinstance(current, BinaryAnalysisException):
            chain.append(current.to_dict())
        else:
            chain.append({
                "error_type": current.__class__.__name__,
                "message": str(current),
                "timestamp": datetime.now().isoformat()
            })
        
        current = current.__cause__ or current.__context__
        if current in [exc.get('exception_obj') for exc in chain]:
            break  # Prevent infinite loops
    
    return chain


def should_retry(exception: Exception) -> bool:
    """
    Determine if an operation should be retried based on exception type.
    
    Args:
        exception: Exception to analyze
        
    Returns:
        True if operation should be retried, False otherwise
    """
    # Retryable exceptions
    retryable_types = (CacheException, ProcessingException)
    
    # Non-retryable exceptions
    non_retryable_types = (
        ValidationException, AuthenticationException, 
        RateLimitException, ConfigurationException
    )
    
    if isinstance(exception, non_retryable_types):
        return False
    
    if isinstance(exception, retryable_types):
        return True
    
    if isinstance(exception, AnalysisException):
        # Retry analysis failures unless they're validation-related
        return exception.error_code not in ['VALIDATION_ERROR', 'UNSUPPORTED_FORMAT']
    
    if isinstance(exception, FileException):
        # Retry file operations unless they're format-related
        return exception.error_code not in ['INVALID_FORMAT', 'FILE_TOO_LARGE']
    
    # Default to not retrying unknown exceptions
    return False


def get_http_status_code(exception: Exception) -> int:
    """
    Map exception types to appropriate HTTP status codes.
    
    Args:
        exception: Exception to map
        
    Returns:
        HTTP status code
    """
    if isinstance(exception, ValidationException):
        return 400  # Bad Request
    
    if isinstance(exception, AuthenticationException):
        return 401  # Unauthorized
    
    if isinstance(exception, RateLimitException):
        return 429  # Too Many Requests
    
    if isinstance(exception, FileException):
        if exception.error_code in ['FILE_NOT_FOUND']:
            return 404  # Not Found
        return 400  # Bad Request
    
    if isinstance(exception, (AnalysisException, ProcessingException)):
        return 422  # Unprocessable Entity
    
    if isinstance(exception, (CacheException, ConfigurationException)):
        return 500  # Internal Server Error
    
    # Default to Internal Server Error for unknown exceptions
    return 500