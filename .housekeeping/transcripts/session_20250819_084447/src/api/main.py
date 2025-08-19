"""
bin2nlp FastAPI Application

Main application setup for binary decompilation + LLM translation service.
Focused on simplicity with decompilation and translation endpoints only.
"""

from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
import uvicorn

from ..core.config import get_settings
from ..core.exceptions import BinaryAnalysisException
from ..core.logging import configure_logging, get_logger
from .routes import decompilation, health, llm_providers, admin
from .middleware import (
    ErrorHandlingMiddleware,
    RequestLoggingMiddleware, 
    AuthenticationMiddleware,
    RateLimitingMiddleware
)


# Setup structured logging
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    # Startup
    settings = get_settings()
    configure_logging(settings.logging)
    
    logger.info("Starting bin2nlp API service")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Initialize components
    try:
        # Test Redis connection
        from ..cache.base import get_redis_client
        redis_client = get_redis_client()
        await redis_client.ping()
        logger.info("Redis connection established")
        
        # Initialize LLM provider factory
        from ..llm.providers.factory import LLMProviderFactory
        factory = LLMProviderFactory()
        await factory.initialize()
        logger.info(f"LLM providers initialized: {len(factory.get_healthy_providers())}")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Continue startup but log the issue
    
    logger.info("bin2nlp API service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down bin2nlp API service")
    
    try:
        # Cleanup Redis connections
        redis_client = get_redis_client()
        await redis_client.close()
        logger.info("Redis connections closed")
        
        # Cleanup LLM providers
        factory = LLMProviderFactory()
        await factory.cleanup()
        logger.info("LLM provider factory cleaned up")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    logger.info("bin2nlp API service shut down complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    # Create FastAPI app with comprehensive documentation
    app = FastAPI(
        title="bin2nlp API",
        description="""
        ## Binary Decompilation & Multi-LLM Translation Service

        Transform binary executables into human-readable analysis through advanced decompilation 
        and multi-provider LLM translation.

        ### Key Features
        - **Multi-format support**: PE, ELF, Mach-O binary analysis
        - **Multi-LLM providers**: OpenAI, Anthropic, Google Gemini integration
        - **Scalable architecture**: Redis caching, async processing
        - **Production ready**: Authentication, rate limiting, monitoring

        ### Authentication
        Most endpoints require API key authentication. Provide your API key in the 
        `Authorization` header as `Bearer <your_api_key>`.

        ### Rate Limits
        Rate limits vary by access tier:
        - **Basic**: 10 requests/minute, 600/hour
        - **Standard**: 60 requests/minute, 3600/hour  
        - **Premium**: 300 requests/minute, 18000/hour
        - **Enterprise**: 1000 requests/minute, 60000/hour

        ### Support
        - Documentation: [GitHub Repository](https://github.com/example/bin2nlp)
        - Issues: [Issue Tracker](https://github.com/example/bin2nlp/issues)
        """,
        version="1.0.0",
        terms_of_service="https://example.com/terms",
        contact={
            "name": "bin2nlp Support",
            "url": "https://example.com/support",
            "email": "support@example.com"
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT"
        },
        docs_url="/docs" if settings.debug or not settings.is_production else None,
        redoc_url="/redoc" if settings.debug or not settings.is_production else None,
        openapi_url="/openapi.json" if settings.debug or not settings.is_production else None,
        lifespan=lifespan,
        servers=[
            {
                "url": f"http://{settings.api.host}:{settings.api.port}",
                "description": "Development server"
            },
            {
                "url": "https://api.bin2nlp.com",
                "description": "Production server"
            }
        ] if settings.debug else [
            {
                "url": "https://api.bin2nlp.com", 
                "description": "Production API"
            }
        ]
    )
    
    # Add middleware (order matters - last added is first executed)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Custom middleware (in reverse order of execution)
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    # Production middleware (disabled in development/testing by default)
    if settings.is_production:
        app.add_middleware(RateLimitingMiddleware)
        app.add_middleware(
            AuthenticationMiddleware,
            require_auth=True  # Require auth in production
        )
        logger.info("Production middleware enabled (authentication + rate limiting)")
    else:
        logger.info("Development mode - authentication and rate limiting disabled")
    
    # Include routers
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["health"]
    )
    
    app.include_router(
        decompilation.router,
        prefix="/api/v1",
        tags=["decompilation"]
    )
    
    app.include_router(
        llm_providers.router,
        prefix="/api/v1",
        tags=["llm-providers"]
    )
    
    app.include_router(
        admin.router,
        prefix="/api/v1",
        tags=["admin"]
    )
    
    # Root endpoint - redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        """Redirect root to API documentation."""
        if settings.debug:
            return RedirectResponse(url="/docs")
        return {"message": "bin2nlp Binary Decompilation & LLM Translation API"}
    
    # Global exception handlers
    @app.exception_handler(BinaryAnalysisException)
    async def binary_analysis_exception_handler(request, exc: BinaryAnalysisException):
        """Handle custom binary analysis exceptions."""
        return HTTPException(
            status_code=400,
            detail={
                "error": "binary_analysis_error",
                "message": str(exc),
                "error_type": exc.__class__.__name__
            }
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc: ValueError):
        """Handle validation errors."""
        return HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": str(exc)
            }
        )
    
    return app


# Create the application instance
app = create_app()


# Development server runner
if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.debug,
        log_level=settings.log_level.value.lower(),
        access_log=True
    )