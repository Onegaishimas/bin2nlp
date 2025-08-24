# Architecture Decision Record: bin2nlp Binary Decompilation & LLM Translation API

## Decision Summary

**Date:** 2025-08-15  
**Project:** bin2nlp - Binary Decompilation & LLM Translation Service  
**Context:** Foundational architecture decisions for binary decompilation with multi-LLM provider translation service  
**Decision Makers:** Project Lead  
**Status:** ✅ Approved  

### Key Architectural Decisions Overview

This ADR establishes the foundational technology stack and development standards for bin2nlp, a containerized API service that transforms binary decompilation into accessible, natural language explanations through configurable LLM providers. The decisions prioritize developer experience, LLM integration flexibility, and translation quality for external analysis tool consumption.

### Decision-Making Criteria and Priorities

1. **Developer Experience**: Clear patterns, good tooling, maintainable code for part-time development
2. **Performance**: API response times, decompilation processing efficiency, and LLM translation performance
3. **Documentation**: Automatic API documentation and clear development guidelines
4. **Containerization**: Cloud-ready deployment with proper isolation
5. **Future Scalability**: Architecture supporting evolution to multi-tenant SaaS

## Technology Stack Decisions

### Backend Stack

**Primary Framework: FastAPI**

**Rationale:**
- **Performance**: Among fastest Python frameworks (TechEmpower benchmarks)
- **Automatic Documentation**: Zero-configuration OpenAPI/Swagger documentation
- **Type Safety**: Built-in request/response validation via Pydantic models
- **Async Support**: Efficient handling of file processing, decompilation, and multi-provider LLM translation
- **Container Efficiency**: Minimal memory footprint, ideal for microservices
- **Modern Python**: Leverages type hints and modern language features

**API Design Standards:**
- RESTful endpoints following OpenAPI 3.0 specification
- JSON request/response format with consistent error handling
- Pydantic models for request validation and response serialization
- Async/await patterns for file processing, radare2 decompilation, and LLM provider API calls

**Key Dependencies:**
- `fastapi`: Core web framework
- `uvicorn`: ASGI server for production deployment
- `pydantic`: Data validation and serialization
- `python-multipart`: File upload support
- `openai`: OpenAI API and OpenAI API-compatible endpoints integration
- `anthropic`: Anthropic API client for Claude model integration
- `google-generativeai`: Google API client for Gemini model integration

### Application Architecture

**Pattern: Modular Monolith**

**Rationale:**
- **Development Simplicity**: Single deployment unit for prototype phase
- **Clear Separation**: Distinct modules for API, decompilation engine, multi-LLM provider integration
- **Future Flexibility**: Easy migration to microservices when scaling needs arise
- **Testing Efficiency**: Simplified integration testing with controlled module boundaries

**Module Structure:**
```
src/
├── api/              # FastAPI routes and endpoint handlers
├── decompilation/    # Binary decompilation engine (radare2 integration)
├── llm/             # Multi-provider LLM integration (OpenAI, Anthropic, Gemini)
├── models/          # Pydantic data models and schemas
├── database/        # PostgreSQL integration and atomic operations
├── cache/           # Hybrid storage layer (PostgreSQL + File Storage)
├── storage/         # File-based storage for large payloads
└── core/            # Shared utilities, config, and exceptions
```

### Database & Data Strategy

**Primary Storage: PostgreSQL + File Storage Hybrid**

**Rationale:**
- **ACID Transactions**: PostgreSQL provides atomic operations for job queue, rate limiting, and session management
- **Hybrid Performance**: Metadata in database for consistency, large payloads in files for performance
- **Data Integrity**: Referential integrity and transactional guarantees for critical operations
- **Scalability**: Database connection pooling and file system caching for optimal performance
- **Operational Excellence**: Advanced monitoring, backup strategies, and operational tooling

**Data Patterns:**
- **Metadata Storage (PostgreSQL)**: Job status, API keys, rate limits, cache metadata, session tracking
- **Large Payload Storage (File System)**: Decompilation results, LLM translation outputs, binary analysis data
- **Atomic Operations**: Database stored procedures for job queue operations and rate limiting
- **TTL Management**: Database-managed expiration with automatic cleanup procedures
- **Performance Optimization**: Hot data in database, cold data in files with intelligent caching

**PostgreSQL Configuration:**
- Connection pooling with asyncpg for high-performance async operations
- Custom enums for job status, user tiers, and system states
- Stored procedures for atomic job queue and rate limiting operations
- Indexes on frequently queried columns (user_id, expires_at, status)
- Automatic cleanup procedures for expired data and file system synchronization

### Infrastructure & Deployment

**Container Strategy: Multi-Container Setup**

**Rationale:**
- **Service Isolation**: Separate containers for API server, decompilation workers, and LLM translation services
- **Independent Scaling**: Scale decompilation workers based on processing demand, manage LLM provider rate limits
- **Resource Management**: Dedicated resource allocation for CPU-intensive decompilation tasks
- **Security**: Decompilation workers run in isolated environment for malware safety
- **LLM Integration**: Flexible LLM provider management without tight coupling to specific services

**Container Architecture:**
```
├── api-container/          # FastAPI application server with LLM provider integration
│   ├── Dockerfile
│   └── requirements.txt       # Including LLM provider clients (openai, anthropic, etc.)
├── decompiler-container/   # Decompilation processing workers
│   ├── Dockerfile
│   ├── radare2 installation
│   └── decompilation dependencies
├── database-container/     # PostgreSQL database service (metadata + atomic operations)
├── storage-container/      # File storage management service (large payloads)
└── docker-compose.yml     # Multi-container orchestration
```

**Deployment Platform:**
- Docker Compose for local development and testing
- Kubernetes-ready architecture for future cloud deployment
- Environment-based configuration (dev/staging/prod)

## Development Standards

### Code Organization

**Directory Structure:**
```
bin2nlp/
├── src/
│   ├── api/                 # FastAPI application
│   │   ├── routes/         # Endpoint definitions
│   │   ├── middleware/     # Custom middleware
│   │   └── dependencies/   # Dependency injection
│   ├── decompilation/      # Binary decompilation logic
│   │   ├── engines/        # radare2 integration
│   │   └── parsers/        # File format handlers
│   ├── llm/                # Multi-LLM provider integration
│   │   ├── providers/      # OpenAI, Anthropic, Gemini clients
│   │   ├── prompts/        # Translation prompt templates
│   │   └── translators/    # Decompilation-to-text logic
│   ├── models/             # Data models
│   │   ├── api/           # Request/Response models
│   │   ├── decompilation/ # Decompilation result models
│   │   ├── translation/   # LLM translation models
│   │   └── config/        # Configuration models
│   ├── database/           # PostgreSQL integration and atomic operations
│   ├── cache/              # Hybrid storage layer (PostgreSQL + File Storage)
│   ├── storage/            # File-based storage for large payloads
│   ├── core/               # Shared utilities
│   └── tests/              # Test organization mirrors src/
├── containers/             # Docker configurations
├── docs/                   # Project documentation
└── scripts/               # Development utilities
```

**File Naming Conventions:**
- Python modules: `snake_case.py`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Test files: `test_[module_name].py`

**Import Organization:**
```python
# Standard library imports
import os
from typing import Optional, List

# Third-party imports
from fastapi import FastAPI, HTTPException
import databases
import asyncpg
import r2pipe

# Local application imports
from src.models.decompilation import DecompilationRequest, DecompilationResult
from src.models.translation import TranslationRequest, TranslationResult
from src.core.config import settings
```

### Coding Patterns

**Pydantic Model Patterns (REQUIRED):**
```python
# All models must use Pydantic BaseModel
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class DecompilationRequest(BaseModel):
    """Decompilation + translation request with comprehensive validation."""
    file_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 file hash")
    decompilation_depth: DecompilationDepth = Field(default=DecompilationDepth.STANDARD)
    llm_provider: Optional[str] = Field(default=None, description="LLM provider for translation")
    llm_model: Optional[str] = Field(default=None, description="Specific LLM model")
    translation_detail: Optional[TranslationDetail] = Field(default=TranslationDetail.STANDARD)
    timeout_seconds: int = Field(default=600, ge=60, le=1800)
    
    @field_validator('file_hash')
    @classmethod
    def validate_hash(cls, v: str) -> str:
        if not re.match(r'^[a-fA-F0-9]{64}$', v):
            raise ValueError('Must be valid SHA-256 hash')
        return v.lower()

# Configuration models must use pydantic-settings
from pydantic_settings import BaseSettings, SettingsConfigDict

class ComponentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COMPONENT_",
        case_sensitive=False
    )
    
    host: str = Field(default="localhost")
    port: int = Field(default=8000, ge=1024, le=65535)
```

**File Detection Patterns (REQUIRED):**
```python
# Must use Magika for all file type detection
from magika import Magika

magika = Magika()

async def validate_binary_file(file_content: bytes) -> Tuple[bool, str]:
    """Validate file is a supported binary type using Magika."""
    result = magika.identify_bytes(file_content)
    file_type = result.output.ct_label
    
    # Check against supported binary types
    is_binary = file_type in SUPPORTED_BINARY_TYPES
    return is_binary, file_type

# Never rely on file extensions alone
def get_file_info(file_path: Path) -> Dict[str, Any]:
    """Get comprehensive file information."""
    with open(file_path, 'rb') as f:
        content = f.read()
    
    # Use Magika, not file extension
    result = magika.identify_bytes(content)
    
    return {
        'detected_type': result.output.ct_label,
        'confidence': result.output.score,
        'size_bytes': len(content),
        'sha256': hashlib.sha256(content).hexdigest()
    }
```

**Configuration Access Patterns (REQUIRED):**
```python
# Always use centralized configuration
from src.core.config import get_settings

async def some_service_function():
    """Service function accessing configuration."""
    settings = get_settings()
    
    # Access hierarchical settings
    database_url = settings.database.url
    max_file_size = settings.decompilation.max_file_size_mb
    api_timeout = settings.api.request_timeout
    
    # Use helper methods when available
    file_size_bytes = settings.get_max_file_size_bytes()
    rate_limits = settings.get_rate_limits()
```

**API Design Patterns:**
```python
# Consistent endpoint structure with Pydantic models
@router.post("/decompile", response_model=DecompilationResponse)
async def decompile_binary(
    request: DecompilationRequest,  # Must be Pydantic model
    background_tasks: BackgroundTasks,
    database: databases.Database = Depends(get_database),
    storage: FileStorageClient = Depends(get_storage),
    llm_service: LLMService = Depends(get_llm_service)
) -> DecompilationResponse:  # Must be Pydantic model
    """Decompile binary file and translate to natural language."""
    # Two-phase implementation: decompilation + translation
```

**Error Handling Patterns:**
```python
# Custom exception hierarchy
class BinaryDecompilationException(Exception):
    """Base exception for decompilation errors."""
    pass

class UnsupportedFormatException(BinaryDecompilationException):
    """Raised when binary format is not supported."""
    pass

class LLMTranslationException(BinaryDecompilationException):
    """Raised when LLM translation fails."""
    pass

# Consistent error responses
@app.exception_handler(BinaryDecompilationException)
async def decompilation_exception_handler(request: Request, exc: BinaryDecompilationException):
    return JSONResponse(
        status_code=400,
        content={"error": "decompilation_error", "message": str(exc)}
    )
```

**Async Patterns:**
- Use `async/await` for all I/O operations (file processing, PostgreSQL, file storage, multi-provider LLM calls)
- Background tasks for long-running decompilation and translation operations
- Proper resource cleanup with context managers
- Concurrent processing: decompilation and LLM translation can run in parallel where possible

### Quality Requirements

**Testing Coverage Expectations:**
- **Unit Tests**: 85% coverage minimum for core business logic
- **Integration Tests**: All external service integrations (radare2, LLM providers, PostgreSQL, File Storage)
- **API Tests**: All endpoints with various input scenarios including LLM provider configurations
- **Performance Tests**: Decompilation and translation time benchmarks for different file sizes

**Code Review Standards:**
- All code changes require self-review using GitHub PR templates
- Type hints required for all function signatures
- Docstrings required for all public functions and classes
- No direct commits to main branch - all changes via feature branches

**Documentation Requirements:**
- API documentation auto-generated via FastAPI OpenAPI
- README with setup instructions and usage examples
- Architecture diagrams for decompilation and translation workflows
- Inline comments for complex decompilation and LLM integration logic

## Architecture Principles

### Core Design Principles

1. **API-First Design**: All functionality exposed through well-documented REST endpoints
2. **Stateless Operations**: No server-side session state, enabling horizontal scaling
3. **Fail-Fast Validation**: Early validation of inputs with clear error messages
4. **Separation of Concerns**: Clear boundaries between API, decompilation, and LLM provider components
5. **Testability**: Design enables easy unit and integration testing

### Security Requirements

**Input Validation:**
- All file uploads validated for size, format, and safety
- Pydantic models enforce request schema validation
- File type detection beyond extension checking

**Execution Safety:**
- Binary decompilation runs in sandboxed container environment
- No persistent storage of uploaded binary files
- LLM provider API calls isolated from decompilation processing
- Resource limits prevent denial-of-service attacks
- Secure handling of potentially malicious code samples

**Data Protection:**
- No logging of binary file contents or sensitive analysis details
- Temporary file cleanup after analysis completion
- PostgreSQL with secure configuration and automatic data cleanup procedures

### Scalability Considerations

**Horizontal Scaling Design:**
- Stateless API servers enable load balancing
- Independent analysis workers can scale based on demand
- PostgreSQL connection pooling with file storage redundancy for high-availability

**Performance Optimization:**
- Async processing prevents blocking operations
- Result caching reduces redundant analysis
- Configurable analysis depth balances speed vs thoroughness

**Resource Management:**
- Container resource limits prevent resource exhaustion
- Analysis job queuing for capacity management
- Graceful degradation during high load periods

## Package and Library Standards

### Approved Libraries and Frameworks

**Core Dependencies:**
- `fastapi[all]>=0.104.0`: Web framework with all optional dependencies
- `uvicorn[standard]>=0.24.0`: ASGI server with performance optimizations
- `pydantic>=2.5.0`: Data validation and serialization (STANDARDIZED)
- `pydantic-settings>=2.1.0`: Environment configuration management (STANDARDIZED)
- `asyncpg>=0.28.0`: PostgreSQL async driver for database operations
- `databases[postgresql]>=0.7.0`: Database abstraction layer with connection pooling
- `sqlalchemy>=2.0.0`: Database ORM for schema management and migrations
- `r2pipe>=1.8.0`: radare2 Python integration for binary decompilation
- `httpx>=0.25.0`: Async HTTP client for multi-provider LLM integration

**LLM Provider Dependencies:**
- `openai>=1.3.0`: OpenAI API and OpenAI API-compatible endpoints client
  - **Compatible Endpoints**: OpenAI, Azure OpenAI, local OpenAI-compatible servers (Ollama, LM Studio, etc.)
  - **Models Supported**: GPT-4, GPT-3.5-turbo, and compatible models from other providers
  - **Configuration**: Supports custom base URLs for OpenAI-compatible endpoints
- `anthropic>=0.8.0`: Anthropic API client for Claude models
  - **Models Supported**: Claude-3-sonnet, Claude-3-haiku, Claude-3-opus
  - **Features**: Constitutional AI, long context windows (up to 200k tokens)
- `google-generativeai>=0.3.0`: Google Generative AI client for Gemini models  
  - **Models Supported**: Gemini-pro, Gemini-pro-vision, Gemini-flash
  - **Features**: Multimodal capabilities, competitive pricing
- `tenacity>=8.2.0`: Robust retry logic with exponential backoff for LLM provider reliability

**Additional Core Dependencies:**
- `magika>=0.3.0`: File type detection and content analysis (STANDARDIZED)

**Development Dependencies:**
- `pytest>=7.4.0`: Testing framework with modern features
- `pytest-asyncio>=0.21.0`: Async test support for LLM provider testing
- `pytest-cov>=4.1.0`: Coverage reporting with branch analysis
- `pytest-mock>=3.12.0`: Mock utilities for LLM provider testing
- `respx>=0.20.0`: HTTP mocking for testing LLM API integrations
- `black>=23.0.0`: Code formatting with consistent style
- `isort>=5.12.0`: Import sorting compatible with black
- `mypy>=1.5.0`: Static type checking with enhanced error reporting
- `pre-commit>=3.4.0`: Git hooks for code quality enforcement
- `bandit>=1.7.0`: Security linting for identifying vulnerabilities
- `safety>=2.3.0`: Dependency vulnerability scanning
- `pip-audit>=2.6.0`: Additional security scanning for Python packages

**Container Dependencies:**
- `radare2>=5.8.0`: Binary decompilation engine with modern analysis capabilities
  - **Installation**: Installed in decompiler containers via package manager or source compilation
  - **Integration**: Accessed via r2pipe Python library for programmatic control
  - **Capabilities**: Multi-architecture support (x86, x64, ARM), multiple binary formats (PE, ELF, Mach-O)

**External Service Dependencies:**
- **OpenAI API and Compatible Services**: No local hosting required
  - OpenAI official API endpoints
  - Azure OpenAI Service endpoints  
  - Local OpenAI-compatible servers (Ollama, LM Studio, vLLM, etc.)
  - Custom OpenAI-compatible API endpoints
- **Anthropic Claude API**: Cloud-hosted service, no local installation
- **Google Gemini API**: Cloud-hosted service, no local installation
- **Network Requirements**: Outbound HTTPS access for LLM provider API calls

### Standardized Technology Decisions

**Pydantic Ecosystem (STANDARDIZED)**

**Decision**: Use Pydantic for all data modeling, validation, and configuration management across the entire application.

**Rationale:**
- **Consistency**: Single validation framework reduces complexity and learning curve
- **Type Safety**: Built-in type hints and runtime validation prevent data errors
- **Performance**: Compiled validation is faster than manual validation code
- **Integration**: Native FastAPI integration for automatic API documentation
- **Configuration**: Pydantic-settings provides robust environment variable handling

**Usage Standards:**
```python
# All data models inherit from BaseModel
class DecompilationRequest(BaseModel):
    file_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 file hash")
    decompilation_depth: DecompilationDepth = Field(default=DecompilationDepth.STANDARD)
    llm_provider: Optional[str] = Field(default=None, description="LLM provider for translation")
    translation_detail: Optional[TranslationDetail] = Field(default=TranslationDetail.STANDARD)
    
# All configuration uses pydantic-settings
class Settings(BaseSettings):
    database_url: str = Field(..., env="DATABASE_URL")
    storage_root: str = Field(..., env="STORAGE_ROOT")
    model_config = SettingsConfigDict(env_file=".env")
```

**Magika for File Detection (STANDARDIZED)**

**Decision**: Use Google's Magika for all file type detection and content analysis tasks.

**Rationale:**
- **Accuracy**: Superior to traditional file extension or magic number detection
- **ML-Based**: Uses machine learning for more intelligent file type classification
- **Security**: More reliable than user-provided MIME types or file extensions
- **Performance**: Fast inference suitable for API workloads
- **Maintenance**: Google-maintained with regular model updates

**Usage Standards:**
```python
# Standardized file detection pattern
from magika import Magika
magika = Magika()

async def detect_file_type(file_content: bytes) -> str:
    """Detect file type using Magika ML-based detection."""
    result = magika.identify_bytes(file_content)
    return result.output.ct_label
```

**Configuration Management (STANDARDIZED)**

**Decision**: All configuration management must use the enhanced validation system in `src/core/config.py`.

**Standards:**
- Environment variables with proper validation and type conversion
- Comprehensive configuration health checks before application startup
- Hierarchical settings structure (database, api, security, etc.)
- Built-in configuration consistency validation
- CLI tools for configuration debugging and validation

**Multi-LLM Provider Integration (STANDARDIZED)**

**Decision**: Implement a unified, provider-agnostic interface for integrating multiple LLM providers (OpenAI, Anthropic, Gemini) with consistent patterns across all translation operations.

**Rationale:**
- **Flexibility**: Users can choose optimal LLM provider based on cost, performance, and quality preferences
- **Resilience**: Provider fallback capabilities prevent single points of failure
- **Cost Management**: Dynamic provider selection based on cost optimization and usage limits
- **Quality Optimization**: Different providers excel at different types of translation tasks
- **Vendor Independence**: Avoid lock-in to any single LLM provider

**Core Integration Standards:**

*1. Provider Interface Pattern:*
```python
# Abstract base class for all LLM providers
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from src.models.translation import TranslationRequest, TranslationResponse

class LLMProvider(ABC):
    """Abstract base class for all LLM provider integrations."""
    
    def __init__(self, config: LLMProviderConfig):
        self.config = config
        self.client = self._initialize_client()
    
    @abstractmethod
    async def translate_function(
        self, 
        function_data: FunctionData, 
        context: TranslationContext
    ) -> FunctionTranslation:
        """Translate assembly function to natural language."""
        pass
    
    @abstractmethod
    async def generate_summary(
        self, 
        decompilation_data: DecompilationData
    ) -> OverallSummary:
        """Generate overall program summary."""
        pass
    
    @abstractmethod
    async def explain_imports(
        self, 
        import_list: List[ImportData]
    ) -> List[ImportExplanation]:
        """Explain purpose and usage of imported functions."""
        pass
    
    @abstractmethod
    def get_cost_estimate(self, token_count: int) -> float:
        """Calculate estimated cost for given token count."""
        pass
    
    @abstractmethod
    async def health_check(self) -> ProviderHealthStatus:
        """Check provider availability and API key validity."""
        pass
```

*2. Provider Factory Pattern:*
```python
class LLMProviderFactory:
    """Factory for creating and managing LLM provider instances."""
    
    _providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider, 
        "gemini": GeminiProvider
    }
    
    @classmethod
    async def create_provider(
        cls, 
        provider_id: str, 
        config: LLMProviderConfig
    ) -> LLMProvider:
        """Create provider instance with validation."""
        if provider_id not in cls._providers:
            raise UnsupportedProviderError(f"Provider {provider_id} not supported")
        
        provider_class = cls._providers[provider_id]
        provider = provider_class(config)
        
        # Validate provider connectivity
        health_status = await provider.health_check()
        if not health_status.is_healthy:
            raise ProviderUnavailableError(f"Provider {provider_id} health check failed")
        
        return provider
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of supported provider identifiers."""
        return list(cls._providers.keys())
```

*3. Configuration Management:*
```python
class LLMProviderConfig(BaseModel):
    """Standardized configuration for all LLM providers."""
    
    provider_id: str = Field(..., regex=r"^(openai|anthropic|gemini)$")
    api_key: SecretStr = Field(..., min_length=20)
    endpoint_url: Optional[HttpUrl] = Field(default=None)
    default_model: str = Field(...)
    
    # Common parameters across providers
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=100, le=8192)
    timeout_seconds: int = Field(default=30, ge=5, le=300)
    
    # Cost and usage controls
    daily_spend_limit: float = Field(default=100.0, ge=0.0)
    monthly_spend_limit: float = Field(default=1000.0, ge=0.0)
    cost_alert_thresholds: List[float] = Field(default=[25.0, 50.0, 75.0])
    
    # Provider-specific overrides
    provider_specific: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key_format(cls, v: SecretStr, info) -> SecretStr:
        """Validate API key format against provider patterns."""
        provider_id = info.data.get('provider_id')
        key_value = v.get_secret_value()
        
        patterns = {
            'openai': r'^sk-[A-Za-z0-9]{48}$',
            'anthropic': r'^sk-ant-[A-Za-z0-9\-]{95}$',
            'gemini': r'^[A-Za-z0-9\-_]{39}$'
        }
        
        if provider_id in patterns and not re.match(patterns[provider_id], key_value):
            raise ValueError(f'Invalid API key format for provider {provider_id}')
        
        return v
```

*4. Error Handling Standards:*
```python
# Standardized exception hierarchy for LLM operations
class LLMProviderException(BinaryDecompilationException):
    """Base exception for all LLM provider errors."""
    def __init__(self, message: str, provider_id: str, error_code: str = None):
        super().__init__(message)
        self.provider_id = provider_id
        self.error_code = error_code

class LLMRateLimitException(LLMProviderException):
    """Raised when provider rate limits are exceeded."""
    def __init__(self, provider_id: str, retry_after: int = None):
        super().__init__(f"Rate limit exceeded for {provider_id}", provider_id, "RATE_LIMIT")
        self.retry_after = retry_after

class LLMCostLimitException(LLMProviderException):
    """Raised when user cost limits would be exceeded."""
    def __init__(self, provider_id: str, estimated_cost: float, limit: float):
        super().__init__(
            f"Cost limit would be exceeded: ${estimated_cost:.2f} > ${limit:.2f}", 
            provider_id, 
            "COST_LIMIT"
        )
        self.estimated_cost = estimated_cost
        self.limit = limit

# Standardized retry decorator for provider operations
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((LLMRateLimitException, httpx.TimeoutException))
)
async def with_provider_retry(operation_func):
    """Standardized retry logic for LLM provider operations."""
    return await operation_func()
```

*5. Usage Tracking and Cost Management:*
```python
class LLMUsageTracker:
    """Centralized tracking of LLM provider usage and costs."""
    
    def __init__(self, database: databases.Database):
        self.database = database
    
    async def track_request(
        self, 
        user_id: str, 
        provider_id: str, 
        tokens_used: int, 
        cost: float,
        operation_type: str
    ):
        """Track LLM provider usage with cost accounting."""
        timestamp = datetime.utcnow()
        
        # Daily tracking using PostgreSQL atomic operations
        await self.database.execute("""
            INSERT INTO llm_usage (user_id, provider_id, usage_date, tokens_used, requests_count, cost, operation_type)
            VALUES (:user_id, :provider_id, :usage_date, :tokens_used, 1, :cost, :operation_type)
            ON CONFLICT (user_id, provider_id, usage_date, operation_type)
            DO UPDATE SET
                tokens_used = llm_usage.tokens_used + EXCLUDED.tokens_used,
                requests_count = llm_usage.requests_count + 1,
                cost = llm_usage.cost + EXCLUDED.cost
        """, {
            "user_id": user_id,
            "provider_id": provider_id, 
            "usage_date": timestamp.date(),
            "tokens_used": tokens_used,
            "cost": cost,
            "operation_type": operation_type
        })
    
    async def check_cost_limits(
        self, 
        user_id: str, 
        provider_id: str, 
        estimated_cost: float,
        config: LLMProviderConfig
    ) -> bool:
        """Check if request would exceed user's cost limits."""
        today = datetime.utcnow().strftime('%Y-%m-%d')
        month = datetime.utcnow().strftime('%Y-%m')
        
        # Check daily limit using PostgreSQL aggregation
        daily_cost = await self.database.fetch_val("""
            SELECT COALESCE(SUM(cost), 0) 
            FROM llm_usage 
            WHERE user_id = :user_id AND provider_id = :provider_id 
            AND usage_date = :today
        """, {"user_id": user_id, "provider_id": provider_id, "today": today}) or 0
        
        if daily_cost + estimated_cost > config.daily_spend_limit:
            raise LLMCostLimitException(provider_id, estimated_cost, config.daily_spend_limit)
        
        # Check monthly limit using PostgreSQL date range query
        monthly_cost = await self.database.fetch_val("""
            SELECT COALESCE(SUM(cost), 0) 
            FROM llm_usage 
            WHERE user_id = :user_id AND provider_id = :provider_id 
            AND usage_date >= :month_start AND usage_date < :month_end
        """, {
            "user_id": user_id, 
            "provider_id": provider_id,
            "month_start": today.replace(day=1),
            "month_end": (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        }) or 0
        
        if monthly_cost + estimated_cost > config.monthly_spend_limit:
            raise LLMCostLimitException(provider_id, estimated_cost, config.monthly_spend_limit)
        
        return True
```

*6. Provider Selection and Fallback Logic:*
```python
class LLMProviderSelector:
    """Intelligent provider selection with fallback capabilities."""
    
    def __init__(self, providers: Dict[str, LLMProvider], usage_tracker: LLMUsageTracker):
        self.providers = providers
        self.usage_tracker = usage_tracker
    
    async def select_provider(
        self, 
        user_id: str, 
        operation_type: str,
        preferences: LLMProviderPreferences = None
    ) -> LLMProvider:
        """Select optimal provider based on preferences, availability, and cost."""
        
        # Get user preferences or use defaults
        if not preferences:
            preferences = await self._get_user_preferences(user_id)
        
        # Try preferred provider first
        if preferences.preferred_provider:
            try:
                provider = self.providers[preferences.preferred_provider]
                health = await provider.health_check()
                if health.is_healthy and health.within_rate_limits:
                    return provider
            except Exception as e:
                logger.warning(f"Preferred provider {preferences.preferred_provider} unavailable: {e}")
        
        # Fall back to best available provider
        available_providers = []
        for provider_id, provider in self.providers.items():
            try:
                health = await provider.health_check()
                if health.is_healthy and health.within_rate_limits:
                    available_providers.append((provider_id, provider, health))
            except Exception:
                continue
        
        if not available_providers:
            raise AllProvidersUnavailableException("No LLM providers available")
        
        # Select based on cost optimization if multiple available
        if preferences.cost_optimization:
            available_providers.sort(key=lambda x: x[2].cost_per_token)
        
        return available_providers[0][1]
```

**Implementation Requirements:**
1. All LLM providers must implement the standardized interface
2. Provider factories must validate connectivity before returning instances
3. Cost tracking must be enabled for all LLM operations
4. Error handling must include provider-specific retry logic
5. Provider selection must support user preferences and fallback chains
6. All LLM operations must be async and include timeout handling
7. Usage statistics must be aggregated across all providers for reporting

**Testing Standards:**
- Mock provider responses for unit tests to avoid API costs
- Integration tests with real providers using dedicated test API keys
- Load testing to validate rate limit handling and fallback behavior
- Cost tracking accuracy tests with known token counts
- Provider health check reliability tests

**Translation Prompt Management (STANDARDIZED)**

**Decision**: Implement a standardized, versioned prompt management system for consistent and optimizable LLM translations across all providers.

**Rationale:**
- **Consistency**: Ensure similar translation quality across different LLM providers
- **Optimization**: Enable A/B testing and iterative prompt improvement
- **Maintainability**: Centralized prompt management prevents prompt drift
- **Provider Adaptation**: Allow provider-specific prompt variations while maintaining consistency

**Prompt Standards:**

*1. Prompt Template Structure:*
```python
class TranslationPromptTemplate(BaseModel):
    """Standardized prompt template for LLM translations."""
    
    template_id: str = Field(..., regex=r"^[a-z_]+_v\d+$")  # e.g., "function_translation_v1"
    version: str = Field(..., regex=r"^v\d+$")
    operation_type: str = Field(..., choices=["function_translation", "import_explanation", "overall_summary"])
    
    # Core prompt components
    system_prompt: str = Field(..., min_length=50)
    user_prompt_template: str = Field(..., min_length=20)
    
    # Provider-specific variations
    provider_adaptations: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    
    # Prompt parameters
    expected_tokens: int = Field(..., ge=50, le=4000)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    max_tokens: int = Field(..., ge=100, le=2048)
    
    # Quality metrics
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_quality_score: float = Field(default=0.0, ge=0.0, le=10.0)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Example function translation prompt
FUNCTION_TRANSLATION_V1 = TranslationPromptTemplate(
    template_id="function_translation_v1",
    version="v1",
    operation_type="function_translation",
    system_prompt="""You are an expert binary analysis assistant specializing in translating assembly code and decompiled functions into clear, natural language explanations.

Your task is to analyze the provided function data and create a comprehensive, human-readable explanation that would be valuable for developers, security analysts, and reverse engineers.

Focus on:
1. The function's primary purpose and behavior
2. Input parameters and their types
3. Return values and their significance  
4. Key operations and logic flow
5. Any notable patterns, algorithms, or security implications
6. Cross-references to other functions or external dependencies""",
    
    user_prompt_template="""Please translate this decompiled function into a natural language explanation:

**Function Information:**
- Name: {function_name}
- Address: {function_address}
- Size: {function_size} bytes

**Decompiled Code:**
```c
{decompiled_code}
```

**Assembly Context:**
```assembly
{assembly_sample}
```

**Function Calls:** {function_calls}
**Variables:** {variables}

Provide a comprehensive explanation in 2-4 paragraphs that explains what this function does, how it works, and why it matters.""",
    
    expected_tokens=400,
    max_tokens=800,
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nBe thorough but concise. Focus on technical accuracy while remaining accessible."
        },
        "openai": {
            "user_prompt_suffix": "\n\nFormat your response with clear section headers if the explanation is complex."
        }
    }
)
```

*2. Prompt Management Service:*
```python
class PromptManager:
    """Centralized management of translation prompts with versioning."""
    
    def __init__(self, database: databases.Database):
        self.database = database
        self.templates: Dict[str, TranslationPromptTemplate] = {}
        self._load_default_templates()
    
    async def get_prompt(
        self, 
        operation_type: str, 
        provider_id: str,
        version: str = "latest"
    ) -> TranslationPromptTemplate:
        """Get prompt template for specific operation and provider."""
        
        # Get template version
        if version == "latest":
            version = await self._get_latest_version(operation_type)
        
        template_key = f"{operation_type}_{version}"
        
        if template_key not in self.templates:
            template = await self._load_template(template_key)
            if not template:
                raise PromptTemplateNotFoundError(f"Template {template_key} not found")
            self.templates[template_key] = template
        
        template = self.templates[template_key]
        
        # Apply provider-specific adaptations
        if provider_id in template.provider_adaptations:
            adapted_template = template.copy()
            adaptations = template.provider_adaptations[provider_id]
            
            if "system_prompt_suffix" in adaptations:
                adapted_template.system_prompt += adaptations["system_prompt_suffix"]
            if "user_prompt_suffix" in adaptations:
                adapted_template.user_prompt_template += adaptations["user_prompt_suffix"]
            if "temperature" in adaptations:
                adapted_template.temperature = float(adaptations["temperature"])
                
            return adapted_template
        
        return template
    
    def render_prompt(
        self, 
        template: TranslationPromptTemplate, 
        context: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Render system and user prompts with provided context."""
        try:
            system_prompt = template.system_prompt
            user_prompt = template.user_prompt_template.format(**context)
            return system_prompt, user_prompt
        except KeyError as e:
            raise PromptRenderingError(f"Missing context variable: {e}")
    
    async def track_prompt_performance(
        self,
        template_id: str,
        success: bool,
        quality_score: float = None,
        execution_time: float = None,
        provider_id: str = None
    ):
        """Track prompt performance for optimization."""
        # Track prompt metrics using PostgreSQL atomic operations
        await self.database.execute("""
            INSERT INTO prompt_metrics (
                template_id, provider_id, total_uses, successes, 
                quality_score, execution_time, recorded_at
            )
            VALUES (:template_id, :provider_id, 1, :success_count, :quality_score, :execution_time, NOW())
        """, {
            "template_id": template_id,
            "provider_id": provider_id,
            "success_count": 1 if success else 0,
            "quality_score": quality_score,
            "execution_time": execution_time
        })
        
        # Update aggregated statistics
        await self.database.execute("""
            INSERT INTO prompt_stats (template_id, provider_id, total_uses, successes, updated_at)
            VALUES (:template_id, :provider_id, 1, :success_count, NOW())
            ON CONFLICT (template_id, provider_id)
            DO UPDATE SET
                total_uses = prompt_stats.total_uses + 1,
                successes = prompt_stats.successes + EXCLUDED.successes,
                updated_at = NOW()
        """, {
            "template_id": template_id,
            "provider_id": provider_id,
            "success_count": 1 if success else 0
        })
```

*3. Quality Assessment Integration:*
```python
class TranslationQualityAssessor:
    """Assess and score translation quality for prompt optimization."""
    
    def __init__(self):
        self.metrics = [
            "technical_accuracy",
            "clarity_readability", 
            "completeness",
            "context_relevance"
        ]
    
    def assess_translation_quality(
        self, 
        translation: str, 
        source_data: Dict[str, Any],
        expected_elements: List[str] = None
    ) -> TranslationQualityScore:
        """Assess translation quality across multiple dimensions."""
        
        scores = {}
        
        # Technical accuracy (keyword presence, technical terms)
        scores["technical_accuracy"] = self._assess_technical_accuracy(
            translation, source_data
        )
        
        # Clarity and readability (sentence structure, language clarity)
        scores["clarity_readability"] = self._assess_clarity(translation)
        
        # Completeness (coverage of source elements)
        scores["completeness"] = self._assess_completeness(
            translation, source_data, expected_elements
        )
        
        # Context relevance (appropriate level of detail)
        scores["context_relevance"] = self._assess_context_relevance(
            translation, source_data
        )
        
        # Calculate overall score
        overall_score = sum(scores.values()) / len(scores)
        
        return TranslationQualityScore(
            overall_score=overall_score,
            dimension_scores=scores,
            feedback=self._generate_feedback(scores),
            timestamp=datetime.utcnow()
        )
```

**Prompt Versioning and A/B Testing:**
- All prompts must include version identifiers
- A/B testing framework for comparing prompt effectiveness
- Automatic rollback to previous versions if quality degrades
- Performance metrics tracked per prompt version and provider
- Regular prompt optimization based on quality assessments

**LLM Provider Dependency Management (STANDARDIZED)**

**Decision**: Establish standardized patterns for managing LLM provider client libraries with proper version constraints, security considerations, and OpenAI API compatibility requirements.

**Core Integration Requirements:**

*1. OpenAI API Compatibility Standards:*
```python
# Configuration supporting OpenAI API and compatible endpoints
class OpenAICompatibleConfig(BaseModel):
    api_key: SecretStr = Field(..., description="API key for authentication")
    base_url: Optional[str] = Field(default=None, description="Custom API endpoint URL")
    organization: Optional[str] = Field(default=None, description="Organization ID for OpenAI")
    timeout: int = Field(default=30, ge=5, le=300, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    
    # Supported endpoints
    COMPATIBLE_ENDPOINTS = {
        "openai": "https://api.openai.com/v1",
        "azure": "https://{resource}.openai.azure.com/",
        "ollama": "http://localhost:11434/v1",
        "lm_studio": "http://localhost:1234/v1",
        "vllm": "http://localhost:8000/v1",
        "custom": "{user_provided_url}"
    }
    
    @field_validator('base_url')
    @classmethod
    def validate_endpoint(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError("Base URL must start with http:// or https://")
        return v

# Usage pattern for OpenAI-compatible clients
async def create_openai_compatible_client(config: OpenAICompatibleConfig) -> OpenAI:
    """Create OpenAI client that works with compatible endpoints."""
    client_kwargs = {
        'api_key': config.api_key.get_secret_value(),
        'timeout': config.timeout,
        'max_retries': config.max_retries,
    }
    
    if config.base_url:
        client_kwargs['base_url'] = config.base_url
    if config.organization:
        client_kwargs['organization'] = config.organization
    
    return OpenAI(**client_kwargs)
```

*2. Version Compatibility Matrix:*
```python
# Minimum supported versions with compatibility notes
LLM_CLIENT_VERSIONS = {
    "openai": {
        "min_version": "1.3.0",
        "recommended": "1.6.0+",
        "compatibility_notes": [
            "v1.3.0+: Supports custom base_url for OpenAI-compatible endpoints",
            "v1.5.0+: Enhanced error handling and retry logic",
            "v1.6.0+: Improved streaming and timeout management"
        ],
        "breaking_changes": [
            "v1.0.0: Major API restructure from v0.x",
            "v1.3.0: Changed authentication parameter structure"
        ]
    },
    "anthropic": {
        "min_version": "0.8.0",
        "recommended": "0.12.0+",
        "compatibility_notes": [
            "v0.8.0+: Supports Claude-3 model family",
            "v0.10.0+: Enhanced message handling and streaming",
            "v0.12.0+: Improved error handling and token counting"
        ]
    },
    "google-generativeai": {
        "min_version": "0.3.0",
        "recommended": "0.4.0+",
        "compatibility_notes": [
            "v0.3.0+: Supports Gemini Pro models",
            "v0.4.0+: Enhanced safety settings and content filtering"
        ]
    }
}
```

*3. Dependency Installation Patterns:*
```python
# requirements.txt structure
CORE_LLM_REQUIREMENTS = """
# OpenAI API and compatible endpoints
openai>=1.3.0,<2.0.0

# Anthropic Claude API
anthropic>=0.8.0,<1.0.0

# Google Gemini API
google-generativeai>=0.3.0,<1.0.0

# Retry and resilience
tenacity>=8.2.0,<9.0.0

# HTTP client for custom integrations
httpx>=0.25.0,<1.0.0

# Async support
asyncio-throttle>=1.0.0,<2.0.0
"""

# Optional dependencies for enhanced features
OPTIONAL_LLM_REQUIREMENTS = """
# Token counting and cost estimation
tiktoken>=0.5.0,<1.0.0  # For OpenAI token counting

# Advanced prompt templating
jinja2>=3.1.0,<4.0.0

# Response caching
diskcache>=5.6.0,<6.0.0
"""
```

*4. Security and API Key Management:*
```python
class LLMSecurityConfig(BaseModel):
    """Security configuration for LLM provider integration."""
    
    # API key validation patterns
    API_KEY_PATTERNS = {
        "openai": r"^sk-[A-Za-z0-9]{48}$",
        "anthropic": r"^sk-ant-[A-Za-z0-9\-]{95}$",
        "google": r"^AIza[A-Za-z0-9\-_]{35}$"
    }
    
    # Security requirements
    require_https: bool = Field(default=True, description="Require HTTPS for all API calls")
    validate_certificates: bool = Field(default=True, description="Validate SSL certificates")
    timeout_limits: Dict[str, int] = Field(default={
        "connection": 10,
        "read": 30,
        "total": 120
    })
    
    # Rate limiting to prevent abuse
    rate_limits: Dict[str, Dict[str, int]] = Field(default={
        "openai": {"requests_per_minute": 3000, "tokens_per_minute": 250000},
        "anthropic": {"requests_per_minute": 1000, "tokens_per_minute": 200000},
        "google": {"requests_per_minute": 1500, "tokens_per_minute": 300000}
    })
    
    @classmethod
    def validate_api_key(cls, provider: str, api_key: str) -> bool:
        """Validate API key format against provider patterns."""
        if provider not in cls.API_KEY_PATTERNS:
            return False
        
        pattern = cls.API_KEY_PATTERNS[provider]
        return bool(re.match(pattern, api_key))
```

*5. Dependency Health Monitoring:*
```python
async def check_llm_dependencies_health() -> Dict[str, Dict[str, Any]]:
    """Check health and versions of all LLM dependencies."""
    health_status = {}
    
    # Check installed versions
    for package in ["openai", "anthropic", "google-generativeai", "tenacity"]:
        try:
            version = pkg_resources.get_distribution(package).version
            min_required = LLM_CLIENT_VERSIONS[package]["min_version"]
            is_compatible = version >= min_required
            
            health_status[package] = {
                "installed_version": version,
                "min_required": min_required,
                "is_compatible": is_compatible,
                "status": "healthy" if is_compatible else "outdated"
            }
        except pkg_resources.DistributionNotFound:
            health_status[package] = {
                "installed_version": None,
                "status": "missing"
            }
    
    return health_status
```

**Installation and Configuration Guidelines:**
1. **Environment Isolation**: Always install in virtual environments or containers
2. **Version Pinning**: Use version constraints to prevent breaking changes
3. **Security Scanning**: Regular vulnerability checks with safety and pip-audit
4. **API Key Management**: Store API keys in secure environment variables or secret managers
5. **Network Security**: Enforce HTTPS and certificate validation for all API calls
6. **Monitoring**: Implement dependency health checks in application startup

### Package Selection Criteria

1. **Maintenance**: Active development and community support
2. **Documentation**: Comprehensive documentation and examples
3. **Performance**: Suitable for production API workloads
4. **Security**: Regular security updates and vulnerability management
5. **License**: Compatible with commercial use (MIT, Apache, BSD)
6. **Standardization**: Prefer libraries that align with our standardized choices

### Version Management Strategy

- **Pinned Dependencies**: Exact versions in requirements.txt for reproducible builds
- **Dependency Updates**: Monthly review of security updates and minor versions
- **Breaking Changes**: Major version updates require testing and approval
- **Lock Files**: Use pip-tools for dependency resolution and locking

## Simplified Data Model Architecture

### Core Data Models (STANDARDIZED)

**Decision**: Streamline data models to focus on decompilation and translation workflows, eliminating complex analysis structures in favor of clean, translation-ready data formats.

**Rationale:**
- **Simplicity**: Reduce cognitive overhead with focused, purpose-built models
- **Translation-Ready**: Structure optimized for LLM consumption and external tool integration
- **Maintainability**: Fewer, cleaner models are easier to maintain and extend
- **Performance**: Simpler serialization/deserialization improves API response times

**Core Model Hierarchy:**

*1. Decompilation Models:*
```python
class DecompilationDepth(str, Enum):
    """Decompilation analysis depth levels."""
    BASIC = "basic"          # Function discovery and basic metadata
    STANDARD = "standard"    # Functions + imports + strings
    COMPREHENSIVE = "comprehensive"  # Full analysis with cross-references

class TranslationDetail(str, Enum):
    """Natural language translation detail levels."""
    BRIEF = "brief"          # Concise explanations
    STANDARD = "standard"    # Balanced detail
    COMPREHENSIVE = "comprehensive"  # Detailed explanations with context

class DecompilationMetadata(BaseModel):
    """Core binary file metadata from decompilation."""
    file_hash: str = Field(..., description="SHA-256 hash of analyzed file")
    file_name: str = Field(..., description="Original filename")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    file_format: str = Field(..., description="Detected file format (PE, ELF, Mach-O)")
    architecture: str = Field(..., description="Target architecture (x86, x64, ARM)")
    platform: str = Field(..., description="Target platform (Windows, Linux, macOS)")
    
    decompilation_time: float = Field(..., description="Processing time in seconds")
    decompilation_depth: DecompilationDepth = Field(..., description="Analysis depth used")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class FunctionData(BaseModel):
    """Extracted function information from decompilation."""
    name: str = Field(..., description="Function name or identifier")
    address: str = Field(..., description="Memory address (hex format)")
    size: int = Field(..., gt=0, description="Function size in bytes")
    
    # Decompilation output
    disassembly: str = Field(..., description="Assembly code representation")
    decompiled_code: Optional[str] = Field(None, description="Pseudo-C code if available")
    
    # Function metadata
    calls_to: List[str] = Field(default_factory=list, description="Functions called by this function")
    called_by: List[str] = Field(default_factory=list, description="Functions that call this function")
    variables: List[str] = Field(default_factory=list, description="Local variables and parameters")
    
    # Analysis flags
    is_entry_point: bool = Field(default=False, description="Whether this is a program entry point")
    is_imported: bool = Field(default=False, description="Whether this is an imported function")
    complexity_score: Optional[float] = Field(None, description="Function complexity (0-10)")

class ImportData(BaseModel):
    """Imported library and function information."""
    library: str = Field(..., description="Library or DLL name")
    function: str = Field(..., description="Imported function name")
    address: Optional[str] = Field(None, description="Import address if available")
    ordinal: Optional[int] = Field(None, description="Ordinal number for unnamed imports")
    
class StringData(BaseModel):
    """String extraction results."""
    content: str = Field(..., description="String content")
    address: str = Field(..., description="Memory address where string is located")
    encoding: str = Field(..., description="String encoding (ASCII, UTF-8, UTF-16)")
    context: Optional[str] = Field(None, description="Usage context if determinable")
    category: Optional[str] = Field(None, description="String category (URL, path, config, etc.)")

class DecompilationResult(BaseModel):
    """Complete decompilation results - phase 1 output."""
    metadata: DecompilationMetadata
    functions: List[FunctionData] = Field(default_factory=list)
    imports: List[ImportData] = Field(default_factory=list)
    strings: List[StringData] = Field(default_factory=list)
    
    # Summary statistics
    total_functions: int = Field(..., description="Total number of functions found")
    total_imports: int = Field(..., description="Total number of imports")
    total_strings: int = Field(..., description="Total number of strings extracted")
    
    # Status and errors
    status: str = Field(..., description="Decompilation status (completed, partial, failed)")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Warnings during processing")
```

*2. Translation Models:*
```python
class FunctionTranslation(BaseModel):
    """Natural language translation of a function."""
    function_name: str = Field(..., description="Original function name")
    function_address: str = Field(..., description="Memory address")
    
    # Translation content
    natural_language: str = Field(..., description="Human-readable explanation")
    purpose: str = Field(..., description="Function purpose summary")
    parameters: List[str] = Field(default_factory=list, description="Parameter descriptions")
    return_value: Optional[str] = Field(None, description="Return value explanation")
    
    # Translation metadata
    translation_quality: Optional[float] = Field(None, description="Quality score (0-10)")
    confidence: Optional[float] = Field(None, description="Translation confidence (0-1)")
    tokens_used: Optional[int] = Field(None, description="LLM tokens consumed")

class ImportTranslation(BaseModel):
    """Natural language explanation of imported functions."""
    library: str = Field(..., description="Library name")
    function: str = Field(..., description="Function name")
    
    purpose: str = Field(..., description="Function purpose and typical usage")
    parameters: Optional[str] = Field(None, description="Parameter information")
    common_usage: Optional[str] = Field(None, description="Common usage patterns")

class OverallSummary(BaseModel):
    """High-level natural language summary of the entire program."""
    program_purpose: str = Field(..., description="Overall program purpose and functionality")
    key_behaviors: List[str] = Field(default_factory=list, description="Key behaviors and capabilities")
    security_considerations: Optional[str] = Field(None, description="Security-relevant observations")
    technical_details: Optional[str] = Field(None, description="Important technical implementation details")
    
    # Summary metadata
    confidence: Optional[float] = Field(None, description="Summary confidence (0-1)")
    tokens_used: Optional[int] = Field(None, description="LLM tokens consumed")

class TranslationResult(BaseModel):
    """Complete LLM translation results - phase 2 output."""
    
    # Core translations
    overall_summary: Optional[OverallSummary] = Field(None, description="Program-level summary")
    function_translations: List[FunctionTranslation] = Field(default_factory=list)
    import_explanations: List[ImportTranslation] = Field(default_factory=list)
    
    # Translation metadata
    llm_provider: str = Field(..., description="LLM provider used")
    llm_model: str = Field(..., description="Specific model used")
    translation_detail: TranslationDetail = Field(..., description="Detail level used")
    
    # Resource usage
    total_tokens_used: int = Field(..., description="Total tokens consumed")
    estimated_cost: float = Field(..., description="Estimated cost in USD")
    processing_time: float = Field(..., description="Translation time in seconds")
    
    # Quality and status
    overall_quality: Optional[float] = Field(None, description="Overall translation quality (0-10)")
    status: str = Field(..., description="Translation status (completed, partial, failed)")
    errors: List[str] = Field(default_factory=list, description="Translation errors")
```

*3. Combined Response Models:*
```python
class DecompilationJobResponse(BaseModel):
    """Complete job response combining decompilation and translation results."""
    
    # Job identification
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Overall job status")
    
    # Results
    decompilation_results: DecompilationResult
    translation_results: Optional[TranslationResult] = Field(
        None, 
        description="Translation results (null if translation failed or was skipped)"
    )
    
    # Job metadata
    created_at: datetime = Field(..., description="Job creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    processing_time: float = Field(..., description="Total processing time in seconds")
    
    # User and provider context
    user_id: Optional[str] = Field(None, description="User identifier")
    api_key_id: Optional[str] = Field(None, description="API key used")

class QuickDecompilationResponse(BaseModel):
    """Streamlined response for synchronous small file processing."""
    
    success: bool = Field(..., description="Whether processing succeeded")
    
    # Core results (always present if successful)
    file_info: DecompilationMetadata
    summary: Dict[str, int] = Field(..., description="Quick statistics")
    
    # Optional detailed results
    functions: Optional[List[FunctionTranslation]] = Field(None, description="Translated functions")
    imports: Optional[List[ImportTranslation]] = Field(None, description="Import explanations")  
    overall_summary: Optional[str] = Field(None, description="Program summary")
    
    # Processing metadata
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    llm_provider: Optional[str] = Field(None, description="LLM provider used")
    cost: Optional[float] = Field(None, description="Processing cost in USD")
    
    # Error handling
    errors: Optional[List[str]] = Field(None, description="Any errors encountered")
    warnings: Optional[List[str]] = Field(None, description="Processing warnings")
```

**Model Design Principles:**
1. **Separation of Concerns**: Decompilation and translation results are separate
2. **Optional Translation**: Translation results can be null if LLM processing fails
3. **Rich Metadata**: Comprehensive metadata for cost tracking and quality assessment
4. **Error Handling**: Structured error reporting at all levels
5. **External Tool Friendly**: Clean, structured data optimized for consumption by analysis tools
6. **Performance Optimized**: Minimal nesting and efficient serialization

## Integration Guidelines

### API Design Standards

**Endpoint Conventions:**
```
POST /api/v1/analyze              # Submit binary for analysis
GET  /api/v1/analyze/{job_id}     # Get analysis results
GET  /api/v1/health               # Health check endpoint
GET  /api/v1/docs                 # Interactive API documentation
```

**Request/Response Format:**
```json
{
  "success": true,
  "data": { /* actual response data */ },
  "metadata": {
    "timestamp": "2025-08-15T10:30:00Z",
    "version": "1.0.0",
    "processing_time_ms": 1234
  },
  "errors": null
}
```

**Status Code Usage:**
- `200`: Successful operation
- `202`: Analysis job accepted (async processing)
- `400`: Invalid request (validation error)
- `404`: Resource not found
- `413`: File too large
- `422`: Unsupported file format
- `500`: Internal server error

### External Service Integration

**radare2 Integration:**
```python
# Standardized radare2 wrapper
class RadareAnalyzer:
    async def analyze_binary(self, file_path: str, depth: AnalysisDepth) -> Dict:
        """Analyze binary using radare2 with specified depth."""
        # Implementation with error handling and timeout
```

**Ollama LLM Integration:**
```python
# Async LLM client with retry logic
class OllamaClient:
    async def translate_assembly(self, assembly: str, context: str) -> str:
        """Convert assembly code to natural language explanation."""
        # Implementation with prompt templates and error handling
```

### Error Handling Standards

**Exception Hierarchy:**
```python
class BinaryAnalysisException(Exception):
    """Base exception for all analysis-related errors."""
    
class FileFormatException(BinaryAnalysisException):
    """File format not supported or corrupted."""
    
class AnalysisTimeoutException(BinaryAnalysisException):
    """Analysis operation exceeded time limit."""
    
class LLMIntegrationException(BinaryAnalysisException):
    """Error communicating with LLM service."""
```

**Logging Standards:**
```python
import logging
import structlog

# Structured logging configuration
logger = structlog.get_logger(__name__)

# Usage pattern
logger.info("analysis_started", 
           file_size=file_size, 
           analysis_depth=depth.value,
           job_id=job_id)
```

## Development Environment

### Required Development Tools

**Core Tools:**
- Python 3.11+ with virtual environment support
- Docker and Docker Compose for containerization
- Git for version control
- VS Code or PyCharm with Python extensions

**Recommended VS Code Extensions:**
- Python (Microsoft)
- Pylance (Microsoft)
- Docker (Microsoft)
- REST Client (Huachao Mao)
- GitLens (GitKraken)

### Local Development Setup

**Environment Configuration:**
```bash
# Development setup script
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
pre-commit install
```

**Environment Variables:**
```bash
# .env file for local development
ENVIRONMENT=development
DATABASE_URL=postgresql://bin2nlp:bin2nlp_password@localhost:5432/bin2nlp
STORAGE_ROOT=/app/storage
OLLAMA_BASE_URL=http://localhost:11434
LOG_LEVEL=DEBUG
MAX_FILE_SIZE_MB=100
ANALYSIS_TIMEOUT_SECONDS=1200
```

**Development Docker Compose:**
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  database:
    image: postgres:15-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: bin2nlp
      POSTGRES_USER: bin2nlp
      POSTGRES_PASSWORD: bin2nlp_password
  
  ollama:
    image: ollama/ollama
    ports: ["11434:11434"]
    volumes: ["ollama-data:/root/.ollama"]
```

### Testing Environment

**Test Configuration:**
- Separate test database/cache instances
- Mock external services (Ollama) for unit tests
- Sample binary files for integration testing
- Performance test suite with benchmarks

**Test Execution:**
```bash
# Run test suite
pytest tests/ -v --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/ -v                    # Unit tests only
pytest tests/integration/ -v --slow      # Integration tests
pytest tests/performance/ -v             # Performance benchmarks
```

## Security Standards

### Authentication and Authorization

**Initial Implementation:**
- No authentication required for prototype phase
- API key-based authentication planned for production
- Rate limiting based on IP address

**Future Security Model:**
- JWT-based authentication for user sessions
- Role-based access control (admin, user, readonly)
- API quotas and usage tracking

### Data Validation and Sanitization

**Input Validation:**
```python
class DecompilationRequest(BaseModel):
    file: UploadFile = Field(..., description="Binary file for decompilation")
    decompilation_depth: DecompilationDepth = Field(default=DecompilationDepth.STANDARD)
    llm_provider: Optional[str] = Field(default=None, description="LLM provider for translation")
    llm_model: Optional[str] = Field(default=None, description="Specific LLM model")
    translation_detail: Optional[TranslationDetail] = Field(default=TranslationDetail.STANDARD)
    timeout_seconds: int = Field(default=600, ge=60, le=1800)
    
    @field_validator('file')
    @classmethod
    def validate_file_size(cls, v):
        if v.size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {v.size} bytes")
        return v
    
    @field_validator('llm_provider')
    @classmethod
    def validate_provider(cls, v):
        if v and v not in ['openai', 'anthropic', 'gemini']:
            raise ValueError(f"Unsupported LLM provider: {v}")
        return v
```

**Output Sanitization:**
- Remove potential code injection from decompilation results and LLM translations
- Sanitize file paths and system information in translation context
- Redact sensitive assembly code patterns from LLM training data
- Validate LLM response format and content before returning to users
- Filter out potentially harmful or inappropriate content from natural language translations

### Secure Coding Practices

**File Handling:**
```python
# Secure temporary file handling
async def process_uploaded_file(file: UploadFile) -> str:
    """Process uploaded file securely with automatic cleanup."""
    with tempfile.NamedTemporaryFile(delete=True, suffix='.bin') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file.flush()
        
        # Analysis with temp file path
        result = await analyze_binary(tmp_file.name)
        return result
    # File automatically deleted when context exits
```

**Environment Isolation:**
- All binary analysis runs in Docker containers
- No network access for analysis containers
- Resource limits prevent DoS attacks
- Regular container image updates for security patches

## Performance Guidelines

### Performance Targets

**API Response Times:**
- Health check: < 100ms
- Analysis submission: < 2 seconds
- Result retrieval: < 500ms
- Documentation endpoints: < 1 second

**Analysis Processing Times:**
- Small files (≤10MB): 95% complete within 30 seconds
- Medium files (≤30MB): 90% complete within 5 minutes  
- Large files (≤100MB): 85% complete within 20 minutes

**Resource Usage:**
- API container: 512MB RAM, 0.5 CPU
- Analysis worker: 2GB RAM, 2 CPU
- PostgreSQL database: 1GB RAM
- File storage: 512MB cache
- Total system: < 4GB RAM, < 4 CPU cores

### Optimization Strategies

**Caching Implementation:**
```python
# Analysis result caching
@cache_result(ttl_seconds=3600)  # 1 hour cache
async def get_analysis_result(file_hash: str, depth: AnalysisDepth) -> AnalysisResult:
    """Get cached analysis result from hybrid storage or compute new one."""
    # Implementation
```

**Async Processing:**
- Background task queues for long-running analysis
- Streaming responses for large analysis results
- Connection pooling for PostgreSQL database and external services
- File storage caching and cleanup procedures

**Resource Management:**
- Lazy loading of analysis modules
- Memory-efficient file processing
- Graceful degradation during high load

## Decision Rationale

### Technology Choice Trade-offs

**FastAPI vs Flask vs Django:**
- **Chosen**: FastAPI for automatic documentation, performance, type safety
- **Rejected**: Flask (manual API docs), Django (heavyweight for API-only service)
- **Risk**: Newer ecosystem, but strong community and documentation

**PostgreSQL + File Storage vs Pure Database:**
- **Chosen**: Hybrid PostgreSQL + File Storage for optimal performance and data integrity
- **Rationale**: ACID transactions for metadata, file storage for large payloads
- **Benefits**: Atomic operations, referential integrity, excellent query capabilities, performance scaling

**Multi-Container vs Single Container:**
- **Chosen**: Multi-container for isolation and independent scaling
- **Rejected**: Single container for deployment simplicity
- **Risk**: More complex orchestration, but better resource management

### Alternative Options Evaluated

**Container Orchestration:**
- **Considered**: Kubernetes for production scalability
- **Chosen**: Docker Compose for development simplicity
- **Future**: Kubernetes deployment when scaling requirements emerge

**LLM Integration:**
- **Considered**: OpenAI API for better quality
- **Chosen**: Local Ollama for privacy and cost control
- **Trade-off**: Potentially lower quality for better security/cost

### Risk Assessment and Mitigation

**Technical Risks:**
1. **radare2 Integration Complexity**
   - *Risk*: Unstable Python bindings or version conflicts
   - *Mitigation*: Container-based radare2 installation, fallback analysis methods

2. **LLM Translation Quality**
   - *Risk*: Poor assembly-to-text conversion quality
   - *Mitigation*: Prompt engineering, multiple model support, quality metrics

3. **Performance at Scale**
   - *Risk*: Analysis bottlenecks under load
   - *Mitigation*: Async processing, caching, horizontal scaling design

**Business Risks:**
1. **Market Demand Uncertainty**
   - *Risk*: Low adoption of automated binary analysis
   - *Mitigation*: Early user feedback, iterative development

2. **Competition from Existing Tools**
   - *Risk*: Established tools (IDA Pro, Ghidra) maintain dominance
   - *Mitigation*: Focus on automation and natural language output differentiators

## Implementation Guidelines

### Feature Development Approach

**Development Workflow:**
1. Create feature branch from main
2. Implement with unit tests (TDD encouraged)
3. Add integration tests for external dependencies
4. Update API documentation if endpoints change
5. Performance test with realistic file samples
6. Code review and merge to main

**Quality Gates:**
- All tests must pass (unit, integration, performance)
- Code coverage must remain above 85%
- Type checking (mypy) must pass
- Security scan (bandit) must pass
- API documentation must be updated

### Exception Handling Process

**Adding New Dependencies:**
1. Evaluate against package selection criteria
2. Add to requirements.in with version constraint
3. Update lock file with pip-compile
4. Document rationale in ADR update

**Changing Architecture Decisions:**
1. Document reason for change
2. Impact assessment on existing code
3. Migration plan for breaking changes
4. Update ADR with new decision and rationale

### Documentation Requirements

**Code Documentation:**
- All public APIs documented with docstrings
- Complex algorithms explained with inline comments
- Architecture decisions recorded in ADR updates
- API changes documented in changelog

**User Documentation:**
- README with quick start guide
- API documentation auto-generated
- Docker deployment instructions
- Troubleshooting guide for common issues

## Conclusion

This Architecture Decision Record establishes a solid foundation for the bin2nlp binary analysis API service. The chosen technology stack prioritizes developer experience while maintaining performance and scalability requirements. The modular monolith architecture provides immediate development benefits while preserving options for future scaling.

The decisions made here should guide all subsequent feature development and ensure consistency across the codebase. Regular review and updates of these decisions will be necessary as the project evolves and requirements change.

---

**Document Status:** ✅ Complete - Ready for feature development planning  
**Next Document:** Feature PRD creation using `@instruct/003_create-feature-prd.md`  
**Related Documents:** `000_PPRD|bin2nlp.md` (Project PRD)  
**Last Updated:** 2025-08-17  
**Document Version:** 1.2 - Course Correction: Removed complex analysis architecture, focused on decompilation + multi-LLM translation service