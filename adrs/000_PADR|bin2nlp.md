# Architecture Decision Record: bin2nlp Binary Analysis API

## Decision Summary

**Date:** 2025-08-15  
**Project:** bin2nlp - Binary Analysis API Service  
**Context:** Foundational architecture decisions for automated binary reverse engineering platform  
**Decision Makers:** Project Lead  
**Status:** ✅ Approved  

### Key Architectural Decisions Overview

This ADR establishes the foundational technology stack and development standards for bin2nlp, a containerized API service that transforms binary reverse engineering into an automated, intelligent analysis system. The decisions prioritize developer experience while maintaining performance and scalability for future commercial deployment.

### Decision-Making Criteria and Priorities

1. **Developer Experience**: Clear patterns, good tooling, maintainable code for part-time development
2. **Performance**: API response times and analysis processing efficiency
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
- **Async Support**: Efficient handling of file processing and LLM interactions
- **Container Efficiency**: Minimal memory footprint, ideal for microservices
- **Modern Python**: Leverages type hints and modern language features

**API Design Standards:**
- RESTful endpoints following OpenAPI 3.0 specification
- JSON request/response format with consistent error handling
- Pydantic models for request validation and response serialization
- Async/await patterns for file processing and external service calls

**Key Dependencies:**
- `fastapi`: Core web framework
- `uvicorn`: ASGI server for production deployment
- `pydantic`: Data validation and serialization
- `python-multipart`: File upload support

### Application Architecture

**Pattern: Modular Monolith**

**Rationale:**
- **Development Simplicity**: Single deployment unit for prototype phase
- **Clear Separation**: Distinct modules for API, analysis engine, LLM integration
- **Future Flexibility**: Easy migration to microservices when scaling needs arise
- **Testing Efficiency**: Simplified integration testing with controlled module boundaries

**Module Structure:**
```
src/
├── api/              # FastAPI routes and endpoint handlers
├── analysis/         # Binary analysis engine (radare2 integration)
├── llm/             # Ollama integration and prompt management
├── models/          # Pydantic data models and schemas
├── cache/           # Redis integration and caching logic
└── core/            # Shared utilities, config, and exceptions
```

### Database & Data Strategy

**Primary Storage: Redis Only**

**Rationale:**
- **Cache-First Design**: Analysis results are temporary, no persistent storage needed
- **Performance**: In-memory operations for fast result retrieval
- **Simplicity**: Minimal setup complexity, perfect for containerized deployment
- **Automatic Cleanup**: TTL-based expiration prevents storage bloat
- **Security Compliance**: No persistent storage of potentially sensitive binaries

**Data Patterns:**
- Analysis results cached with configurable TTL (1-24 hours)
- Job status tracking for long-running analysis operations
- Rate limiting and request throttling data
- Session-based temporary file tracking

**Redis Configuration:**
- LRU eviction policy for memory management
- Persistence disabled for security (no disk writes)
- JSON serialization for complex analysis result objects

### Infrastructure & Deployment

**Container Strategy: Multi-Container Setup**

**Rationale:**
- **Service Isolation**: Separate containers for API server and analysis workers
- **Independent Scaling**: Scale analysis workers based on processing demand
- **Resource Management**: Dedicated resource allocation for CPU-intensive tasks
- **Security**: Analysis workers run in isolated environment for malware safety

**Container Architecture:**
```
├── api-container/          # FastAPI application server
│   ├── Dockerfile
│   └── requirements.txt
├── worker-container/       # Analysis processing workers
│   ├── Dockerfile
│   ├── radare2 installation
│   └── analysis dependencies
├── redis-container/        # Redis cache service
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
│   ├── analysis/           # Binary analysis logic
│   │   ├── engines/        # radare2 integration
│   │   ├── parsers/        # File format handlers
│   │   └── processors/     # Analysis workflows
│   ├── llm/                # LLM integration
│   │   ├── clients/        # Ollama client
│   │   ├── prompts/        # Prompt templates
│   │   └── translators/    # Assembly-to-text logic
│   ├── models/             # Data models
│   │   ├── api/           # Request/Response models
│   │   ├── analysis/      # Analysis result models
│   │   └── config/        # Configuration models
│   ├── cache/              # Redis integration
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
import redis
import r2pipe

# Local application imports
from src.models.analysis import AnalysisRequest, AnalysisResult
from src.core.config import settings
```

### Coding Patterns

**API Design Patterns:**
```python
# Consistent endpoint structure
@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_binary(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    cache: Redis = Depends(get_redis)
) -> AnalysisResponse:
    """Analyze binary file with configurable depth."""
    # Implementation
```

**Error Handling Patterns:**
```python
# Custom exception hierarchy
class BinaryAnalysisException(Exception):
    """Base exception for analysis errors."""
    pass

class UnsupportedFormatException(BinaryAnalysisException):
    """Raised when binary format is not supported."""
    pass

# Consistent error responses
@app.exception_handler(BinaryAnalysisException)
async def analysis_exception_handler(request: Request, exc: BinaryAnalysisException):
    return JSONResponse(
        status_code=400,
        content={"error": "analysis_error", "message": str(exc)}
    )
```

**Async Patterns:**
- Use `async/await` for all I/O operations (file processing, Redis, LLM calls)
- Background tasks for long-running analysis operations
- Proper resource cleanup with context managers

### Quality Requirements

**Testing Coverage Expectations:**
- **Unit Tests**: 85% coverage minimum for core business logic
- **Integration Tests**: All external service integrations (radare2, Ollama, Redis)
- **API Tests**: All endpoints with various input scenarios
- **Performance Tests**: Analysis time benchmarks for different file sizes

**Code Review Standards:**
- All code changes require self-review using GitHub PR templates
- Type hints required for all function signatures
- Docstrings required for all public functions and classes
- No direct commits to main branch - all changes via feature branches

**Documentation Requirements:**
- API documentation auto-generated via FastAPI OpenAPI
- README with setup instructions and usage examples
- Architecture diagrams for complex workflows
- Inline comments for complex analysis logic

## Architecture Principles

### Core Design Principles

1. **API-First Design**: All functionality exposed through well-documented REST endpoints
2. **Stateless Operations**: No server-side session state, enabling horizontal scaling
3. **Fail-Fast Validation**: Early validation of inputs with clear error messages
4. **Separation of Concerns**: Clear boundaries between API, analysis, and LLM components
5. **Testability**: Design enables easy unit and integration testing

### Security Requirements

**Input Validation:**
- All file uploads validated for size, format, and safety
- Pydantic models enforce request schema validation
- File type detection beyond extension checking

**Execution Safety:**
- Binary analysis runs in sandboxed container environment
- No persistent storage of uploaded binary files
- Resource limits prevent denial-of-service attacks
- Secure handling of potentially malicious code samples

**Data Protection:**
- No logging of binary file contents or sensitive analysis details
- Temporary file cleanup after analysis completion
- Redis configured without persistence to prevent data leakage

### Scalability Considerations

**Horizontal Scaling Design:**
- Stateless API servers enable load balancing
- Independent analysis workers can scale based on demand
- Redis clustering support for high-availability caching

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
- `fastapi[all]`: Web framework with all optional dependencies
- `uvicorn[standard]`: ASGI server with performance optimizations
- `pydantic`: Data validation and serialization
- `redis`: Cache and session storage
- `r2pipe`: radare2 Python integration
- `httpx`: Async HTTP client for Ollama integration

**Development Dependencies:**
- `pytest`: Testing framework
- `pytest-asyncio`: Async test support
- `pytest-cov`: Coverage reporting
- `black`: Code formatting
- `isort`: Import sorting
- `mypy`: Static type checking
- `pre-commit`: Git hooks for code quality

**Container Dependencies:**
- `radare2`: Binary analysis engine
- `ollama`: Local LLM server

### Package Selection Criteria

1. **Maintenance**: Active development and community support
2. **Documentation**: Comprehensive documentation and examples
3. **Performance**: Suitable for production API workloads
4. **Security**: Regular security updates and vulnerability management
5. **License**: Compatible with commercial use (MIT, Apache, BSD)

### Version Management Strategy

- **Pinned Dependencies**: Exact versions in requirements.txt for reproducible builds
- **Dependency Updates**: Monthly review of security updates and minor versions
- **Breaking Changes**: Major version updates require testing and approval
- **Lock Files**: Use pip-tools for dependency resolution and locking

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
REDIS_URL=redis://localhost:6379
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
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
  
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
class AnalysisRequest(BaseModel):
    file: UploadFile = Field(..., description="Binary file to analyze")
    analysis_depth: AnalysisDepth = Field(default=AnalysisDepth.STANDARD)
    timeout_seconds: int = Field(default=300, ge=30, le=1200)
    
    @validator('file')
    def validate_file_size(cls, v):
        if v.size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {v.size} bytes")
        return v
```

**Output Sanitization:**
- Remove potential code injection from analysis results
- Sanitize file paths and system information
- Redact sensitive assembly code patterns

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
- Redis cache: 256MB RAM
- Total system: < 4GB RAM, < 4 CPU cores

### Optimization Strategies

**Caching Implementation:**
```python
# Analysis result caching
@cache_result(ttl=3600)  # 1 hour cache
async def get_analysis_result(file_hash: str, depth: AnalysisDepth) -> AnalysisResult:
    """Get cached analysis result or compute new one."""
    # Implementation
```

**Async Processing:**
- Background task queues for long-running analysis
- Streaming responses for large analysis results
- Connection pooling for Redis and external services

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

**Redis-Only vs Database + Cache:**
- **Chosen**: Redis-only for simplicity and security (no persistent storage)
- **Rejected**: PostgreSQL/SQLite for prototype complexity
- **Risk**: Limited query capabilities, but sufficient for cache-first design

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
**Last Updated:** 2025-08-15  
**Document Version:** 1.0