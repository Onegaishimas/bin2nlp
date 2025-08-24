"""
bin2nlp FastAPI Application

Main application setup for binary decompilation + LLM translation service.
Focused on simplicity with decompilation and translation endpoints only.
"""

from contextlib import asynccontextmanager
from typing import Dict, Any
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
import uvicorn

from ..core.config import get_settings
from ..core.exceptions import BinaryAnalysisException
from ..core.logging import configure_logging, get_logger
from ..core.dashboards import run_alert_checks
from .routes import decompilation, health, llm_providers, admin, dashboard
from .middleware import (
    ErrorHandlingMiddleware,
    RequestLoggingMiddleware, 
    AuthenticationMiddleware,
    RateLimitingMiddleware
)


# Setup structured logging
logger = get_logger(__name__)

# Background task for alert monitoring
_alert_monitoring_task = None


async def alert_monitoring_task():
    """Background task to continuously monitor alerts."""
    logger.info("Starting alert monitoring background task")
    
    while True:
        try:
            # Run alert checks every 60 seconds
            await run_alert_checks()
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("Alert monitoring task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in alert monitoring task: {e}")
            # Continue monitoring even if there's an error
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    global _alert_monitoring_task
    
    # Startup
    settings = get_settings()
    configure_logging(settings.logging)
    
    logger.info("Starting bin2nlp API service")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    
    # Initialize components
    try:
        # Test Database connection
        from ..database.connection import get_database, init_database
        await init_database(settings)
        db = await get_database()
        
        # Test connection with a simple query
        result = await db.fetch_one("SELECT 1 as test")
        if result and result['test'] == 1:
            logger.info("PostgreSQL database connection established")
        else:
            logger.warning("PostgreSQL database connection test failed")
        
        # Initialize LLM provider factory
        from ..llm.providers.factory import LLMProviderFactory
        factory = LLMProviderFactory()
        await factory.initialize()
        logger.info(f"LLM providers initialized: {len(factory.get_healthy_providers())}")
        
        # Start background alert monitoring
        if not settings.is_production or settings.debug:
            _alert_monitoring_task = asyncio.create_task(alert_monitoring_task())
            logger.info("Alert monitoring background task started")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # Continue startup but log the issue
    
    logger.info("bin2nlp API service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down bin2nlp API service")
    
    try:
        # Stop background alert monitoring task
        if _alert_monitoring_task and not _alert_monitoring_task.done():
            _alert_monitoring_task.cancel()
            try:
                await _alert_monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Alert monitoring background task stopped")
        
        # Cleanup Database connections
        from ..database.connection import close_database
        await close_database()
        logger.info("PostgreSQL database connections closed")
        
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
        - **Scalable architecture**: PostgreSQL database, file storage, async processing
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
        docs_url="/docs",
        redoc_url="/redoc", 
        openapi_url="/openapi.json",
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
    
    # Authentication and rate limiting middleware
    # Add rate limiting in production
    if settings.is_production:
        app.add_middleware(RateLimitingMiddleware)
    
    # Add authentication middleware based on security settings
    require_auth = settings.security.require_api_keys
    app.add_middleware(
        AuthenticationMiddleware,
        require_auth=require_auth
    )
    
    # Log middleware configuration
    if settings.is_production and require_auth:
        logger.info("Production middleware enabled (authentication + rate limiting)")
    elif settings.is_production:
        logger.info("Production middleware enabled (rate limiting only)")
    elif require_auth:
        logger.info("Development mode with authentication enabled")
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
    
    # Dashboard routes (web interface)
    app.include_router(
        dashboard.router,
        tags=["dashboard"]
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