"""
Error Handling Middleware

Standardized error handling for all API responses with proper
HTTP status codes and error formatting.
"""

import traceback
from typing import Callable

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from ...core.exceptions import (
    BinaryAnalysisException,
    UnsupportedFormatException,
    DecompilationException,
    LLMProviderException,
    LLMRateLimitException,
    LLMCostLimitException
)
from ...core.logging import get_logger

logger = get_logger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle exceptions and standardize error responses.
    
    Converts various exception types to appropriate HTTP responses
    with consistent error format.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle any exceptions."""
        try:
            response = await call_next(request)
            return response
            
        except HTTPException:
            # Re-raise FastAPI HTTPExceptions as-is
            raise
            
        except UnsupportedFormatException as exc:
            logger.warning(f"Unsupported file format: {exc}")
            return self._create_error_response(
                status_code=422,
                error_type="unsupported_format",
                message=str(exc),
                details={"supported_formats": ["PE", "ELF", "Mach-O"]}
            )
            
        except DecompilationException as exc:
            logger.error(f"Decompilation error: {exc}")
            return self._create_error_response(
                status_code=422,
                error_type="decompilation_error",
                message=str(exc),
                details={"component": "decompilation_engine"}
            )
            
        except LLMRateLimitException as exc:
            logger.warning(f"LLM rate limit exceeded: {exc}")
            return self._create_error_response(
                status_code=429,
                error_type="rate_limit_exceeded",
                message=str(exc),
                details={
                    "provider": exc.provider_id,
                    "retry_after": exc.retry_after
                },
                headers={"Retry-After": str(exc.retry_after)} if exc.retry_after else None
            )
            
        except LLMCostLimitException as exc:
            logger.warning(f"LLM cost limit would be exceeded: {exc}")
            return self._create_error_response(
                status_code=402,
                error_type="cost_limit_exceeded",
                message=str(exc),
                details={
                    "provider": exc.provider_id,
                    "estimated_cost": exc.estimated_cost,
                    "limit": exc.limit
                }
            )
            
        except LLMProviderException as exc:
            logger.error(f"LLM provider error: {exc}")
            return self._create_error_response(
                status_code=503,
                error_type="llm_provider_error",
                message=str(exc),
                details={
                    "provider": exc.provider_id,
                    "error_code": exc.error_code
                }
            )
            
        except BinaryAnalysisException as exc:
            logger.error(f"Binary analysis error: {exc}")
            return self._create_error_response(
                status_code=400,
                error_type="binary_analysis_error",
                message=str(exc)
            )
            
        except ValueError as exc:
            logger.warning(f"Validation error: {exc}")
            return self._create_error_response(
                status_code=422,
                error_type="validation_error",
                message=str(exc)
            )
            
        except FileNotFoundError as exc:
            logger.error(f"File not found: {exc}")
            return self._create_error_response(
                status_code=404,
                error_type="file_not_found",
                message="Requested file or resource not found"
            )
            
        except PermissionError as exc:
            logger.error(f"Permission denied: {exc}")
            return self._create_error_response(
                status_code=403,
                error_type="permission_denied",
                message="Insufficient permissions to access resource"
            )
            
        except TimeoutError as exc:
            logger.error(f"Request timeout: {exc}")
            return self._create_error_response(
                status_code=408,
                error_type="request_timeout",
                message="Request processing timed out"
            )
            
        except Exception as exc:
            # Log full traceback for unexpected errors
            logger.error(f"Unexpected error: {exc}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return self._create_error_response(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                error_type="internal_server_error",
                message="An unexpected error occurred while processing your request"
            )

    def _create_error_response(
        self,
        status_code: int,
        error_type: str,
        message: str,
        details: dict = None,
        headers: dict = None
    ) -> JSONResponse:
        """
        Create standardized error response.
        
        Args:
            status_code: HTTP status code
            error_type: Error category/type
            message: Human-readable error message
            details: Additional error details
            headers: Optional response headers
            
        Returns:
            JSONResponse with standardized error format
        """
        error_response = {
            "success": False,
            "error": {
                "type": error_type,
                "message": message,
                "status_code": status_code
            }
        }
        
        if details:
            error_response["error"]["details"] = details
            
        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers=headers or {}
        )