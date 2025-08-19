"""
Request Logging Middleware

Structured logging for all API requests and responses with
performance metrics and correlation tracking.
"""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...core.logging import get_logger, set_correlation_id, clear_correlation_id


logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all API requests and responses with performance metrics.
    
    Adds correlation IDs and structured logging for observability.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with logging and performance tracking."""
        # Generate correlation ID and set in context
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        set_correlation_id(correlation_id)
        
        # Start timing
        start_time = time.time()
        
        # Extract request information
        request_info = {
            "correlation_id": correlation_id,
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
            "content_type": request.headers.get("Content-Type", ""),
            "content_length": request.headers.get("Content-Length", 0)
        }
        
        # Log incoming request
        logger.info(
            "Request started", 
            event_type="request_started",
            **request_info
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            processing_time_ms = (time.time() - start_time) * 1000
            
            # Extract response information
            response_info = {
                "status_code": response.status_code,
                "processing_time_ms": round(processing_time_ms, 2),
                "response_size": self._get_response_size(response)
            }
            
            # Determine status category and log accordingly
            if 200 <= response.status_code < 300:
                status_category = "success"
                logger.info(
                    "Request completed - success",
                    event_type="request_completed",
                    status_category=status_category,
                    **request_info,
                    **response_info
                )
            elif 300 <= response.status_code < 400:
                status_category = "redirect" 
                logger.info(
                    "Request completed - redirect",
                    event_type="request_completed",
                    status_category=status_category,
                    **request_info,
                    **response_info
                )
            elif 400 <= response.status_code < 500:
                status_category = "client_error"
                logger.warning(
                    "Request completed - client error",
                    event_type="request_completed",
                    status_category=status_category,
                    **request_info,
                    **response_info
                )
            else:
                status_category = "server_error"
                logger.error(
                    "Request completed - server error",
                    event_type="request_completed",
                    status_category=status_category,
                    **request_info,
                    **response_info
                )
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            return response
            
        except Exception as exc:
            # Calculate processing time for failed requests
            processing_time_ms = (time.time() - start_time) * 1000
            
            # Log failed request
            logger.error(
                "Request failed",
                event_type="request_failed",
                error=str(exc),
                error_type=exc.__class__.__name__,
                processing_time_ms=round(processing_time_ms, 2),
                **request_info
            )
            
            # Re-raise the exception
            raise
        finally:
            # Clear correlation ID from context
            clear_correlation_id()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request headers."""
        # Check for forwarded headers first (reverse proxy scenarios)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"

    def _get_response_size(self, response: Response) -> int:
        """Get response size from headers."""
        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        
        return 0