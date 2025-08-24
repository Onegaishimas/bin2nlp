# Technical Design Document: Phase 1 Integrated System
## Multi-Platform Binary Analysis Engine + RESTful API Interface

## Executive Summary

This Technical Design Document outlines the integrated system architecture for Phase 1 of the bin2nlp project, combining the Multi-Platform Binary Analysis Engine with the RESTful API Interface. The design implements a hybrid PostgreSQL + File Storage architecture that provides both relational data management and efficient file-based caching for optimal performance and simplicity.

### Business Goals to Technical Approach Alignment

**Primary Business Goals:**
- 90% time reduction in binary analysis → Automated processing with efficient file-based caching
- Quality analysis insights → Structured output with confidence scoring stored in PostgreSQL
- Technical feasibility demonstration → Production-ready containerized architecture
- Foundation for SaaS commercialization → Stateless, horizontally scalable design

**Technical Strategy:**
The system uses a hybrid PostgreSQL + File Storage architecture that provides both relational data management and efficient file-based caching. PostgreSQL handles job metadata and structured data, while file-based storage enables fast result caching and session management. This approach provides simplicity, reliability, and eliminates external dependencies while maintaining performance.

## System Architecture

### High-Level Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   File Storage  │    │   Monitoring    │
│    (Optional)   │    │   (Local FS)    │    │   & Logging     │
└─────────┬───────┘    └─────────┬───────┘    └─────────────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Service   │◄───┤   PostgreSQL    │───►│ Analysis Engine │
│   (FastAPI)     │    │   Database      │    │  (Integrated)   │
│                 │    │                 │    │                 │
│   • Auth        │    │ • Job Metadata  │    │ • radare2       │
│   • File Upload │    │ • User Data     │    │ • File Proc     │
│   • Job Mgmt    │    │ • Sessions      │    │ • Security Scan │
│   • Results     │    │ • Rate Limits   │    │ • Result Cache  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Component Relationships and Data Flow

**File Upload & Analysis Request Flow:**
1. **Client** uploads binary file to API via direct upload endpoint
2. **API Service** validates file, creates job metadata in PostgreSQL database
3. **Analysis Engine** processes job immediately or via background task queue
4. **Analysis Engine** stores structured results in file-based cache with TTL
5. **API Service** retrieves results from file cache and returns to client

**Component Communication Patterns:**
- **API ↔ PostgreSQL**: Direct connection for job metadata, user data, sessions
- **API ↔ File Storage**: Direct filesystem access for result caching and temp files
- **Analysis Engine ↔ File Storage**: Binary file processing and temporary file management
- **API ↔ Storage**: File validation and metadata extraction

### Integration Points with Future Systems

**LLM Integration Readiness:**
- Result cache provides structured analysis data for LLM processing
- PostgreSQL job metadata enables LLM provider tracking and cost management
- File-based storage supports intermediate LLM translation caching

**Scalability Expansion Points:**
- PostgreSQL connection pooling enables horizontal API scaling
- File storage can be migrated to distributed storage systems
- Background job processing ready for dedicated worker containers

## Technical Stack

### Core Technologies and Justification

**Web Framework:**
- **FastAPI**: Modern Python web framework with automatic OpenAPI documentation
- **Uvicorn**: High-performance ASGI server with async support
- **Pydantic**: Data validation and serialization with type hints

**Analysis Engine:**
- **radare2**: Comprehensive binary analysis framework with Python bindings
- **r2pipe**: Python integration with radare2 for analysis automation
- **asyncio**: Non-blocking I/O for file processing and external service calls
- **structlog**: Structured logging with context propagation

**Infrastructure:**
- **PostgreSQL 15+**: Primary database for job metadata, user data, sessions
- **File Storage**: Local filesystem for result caching and temporary files
- **Docker Compose**: Multi-container orchestration for development and deployment
- **Python 3.11+**: Modern async features, performance improvements, type hints

**Testing & Quality:**
- **pytest**: Unit and integration testing with async support
- **pytest-asyncio**: Async test execution and fixture management
- **pytest-cov**: Coverage reporting with branch analysis
- **black + isort + mypy**: Code formatting, import sorting, type checking

### Dependencies and Version Requirements

**Python Package Dependencies:**
```python
# Core Application
fastapi[all] >= 0.104.0
uvicorn[standard] >= 0.24.0
pydantic >= 2.4.0
asyncpg >= 0.29.0
databases[postgresql] >= 0.8.0
r2pipe >= 1.9.0

# Async & Concurrency
aiofiles >= 23.2.0
httpx >= 0.25.0

# Logging & Monitoring
structlog >= 23.2.0

# Development & Testing
pytest >= 7.4.0
pytest-asyncio >= 0.21.0
pytest-cov >= 4.1.0
black >= 23.11.0
isort >= 5.12.0
mypy >= 1.7.0
```

**System Dependencies:**
```bash
# Binary Analysis Tools
radare2 >= 5.8.0

# Database
postgresql >= 15.0

# Container Runtime
docker >= 24.0.0
docker-compose >= 2.20.0
```

**Container Resource Requirements:**
- **API Service**: 512MB RAM, 1 CPU core
- **PostgreSQL**: 1GB RAM, 1 CPU core
- **Analysis Engine**: 2GB RAM, 2 CPU cores (integrated with API)
- **Storage**: 10GB disk space minimum

## Data Design

### PostgreSQL Database Schema

**Core Tables:**

```sql
-- Job Management
CREATE TABLE analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    filename VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB,
    INDEX (user_id, created_at),
    INDEX (status, priority, created_at),
    INDEX (file_hash)
);

-- User Management
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    api_key_hash VARCHAR(64) NOT NULL,
    rate_limit_tier VARCHAR(50) DEFAULT 'standard',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true
);

-- Session Management
CREATE TABLE upload_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    file_count INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rate Limiting
CREATE TABLE rate_limits (
    user_id VARCHAR(255) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    requests_count INTEGER DEFAULT 0,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (user_id, endpoint, window_start)
);
```

### File Storage Organization

**Directory Structure:**
```
/var/lib/app/data/
├── cache/
│   ├── results/          # Analysis result cache (JSON files)
│   │   └── {job_id}.json
│   ├── sessions/         # Upload session data
│   │   └── {session_id}.json
│   └── temp/            # Temporary processing files
│       └── {job_id}/
├── uploads/             # User uploaded files
│   └── {user_id}/
│       └── {file_hash}
└── logs/               # Application logs
    ├── api.log
    ├── analysis.log
    └── error.log
```

**File Storage Patterns:**
- **Result Cache**: JSON files with TTL-based cleanup
- **Upload Storage**: Organized by user ID and file hash for deduplication
- **Temporary Files**: Job-specific directories with automatic cleanup
- **Session Data**: JSON files with expiration timestamps

### Data Relationship Patterns

**Job Processing Flow:**
1. **Upload** → File stored in `/uploads/{user_id}/{file_hash}`
2. **Job Creation** → Metadata stored in PostgreSQL `analysis_jobs` table
3. **Processing** → Temporary files in `/temp/{job_id}/`
4. **Results** → Cached in `/cache/results/{job_id}.json`
5. **Cleanup** → Temporary files removed after job completion

**User Data Flow:**
- **Authentication** → API key validation against PostgreSQL `users` table
- **Rate Limiting** → Request counts stored in PostgreSQL `rate_limits` table
- **Session Management** → Session data in both PostgreSQL and file cache

### Validation Strategy and Consistency

**Data Integrity:**
- PostgreSQL foreign key constraints ensure referential integrity
- File existence validation before job processing
- Hash-based file deduplication to prevent storage bloat
- Atomic job status updates with transaction isolation

**Consistency Patterns:**
- PostgreSQL ACID compliance for critical job metadata
- File cache invalidation based on TTL and job completion
- Background cleanup processes for expired data
- Health checks to verify database and file system consistency

## API Design

### API Design Patterns and Conventions

**RESTful Resource Design:**
```python
# Job Management
POST   /api/v1/jobs                # Create analysis job
GET    /api/v1/jobs/{job_id}       # Get job status and results
GET    /api/v1/jobs                # List user's jobs
DELETE /api/v1/jobs/{job_id}       # Cancel/delete job

# File Management
POST   /api/v1/files/upload        # Upload file for analysis
GET    /api/v1/files/{file_id}     # Download file
DELETE /api/v1/files/{file_id}     # Delete uploaded file

# User Management
GET    /api/v1/users/profile       # Get user profile
PUT    /api/v1/users/profile       # Update profile
GET    /api/v1/users/usage         # Get usage statistics

# System Status
GET    /api/v1/health              # System health check
GET    /api/v1/status              # Detailed system status
```

**Request/Response Patterns:**
```python
# Standard Response Format
{
    "success": true,
    "data": {...},
    "metadata": {
        "timestamp": "2024-01-01T12:00:00Z",
        "request_id": "uuid",
        "version": "1.0.0"
    }
}

# Error Response Format
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "File size exceeds maximum limit",
        "details": {...}
    },
    "metadata": {...}
}
```

### Data Flow and Transformation Strategy

**Request Processing Pipeline:**
1. **Authentication** → API key validation against PostgreSQL
2. **Rate Limiting** → Check limits in PostgreSQL rate_limits table
3. **Validation** → Pydantic model validation and business rules
4. **Processing** → Core business logic execution
5. **Response** → Structured JSON response with metadata

**File Processing Pipeline:**
1. **Upload Validation** → File type, size, and security checks
2. **Storage** → Save to `/uploads/{user_id}/{file_hash}`
3. **Job Creation** → Insert job metadata into PostgreSQL
4. **Analysis** → radare2 processing with structured output
5. **Caching** → Results stored in `/cache/results/{job_id}.json`

### Error Handling Strategy and Consistency

**Error Categories:**
```python
class ErrorCodes:
    # Client Errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    
    # Server Errors (5xx)
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
```

**Error Handling Patterns:**
- Structured error responses with consistent format
- PostgreSQL transaction rollback on errors
- File cleanup on failed operations
- Comprehensive error logging with correlation IDs

## Component Architecture

### Component Organization and Hierarchy

**Application Structure:**
```
src/
├── api/                 # FastAPI application
│   ├── main.py         # Application entry point
│   ├── routes/         # API endpoint definitions
│   │   ├── jobs.py
│   │   ├── files.py
│   │   ├── users.py
│   │   └── health.py
│   └── middleware/     # Request/response middleware
│       ├── auth.py
│       ├── rate_limiting.py
│       └── error_handling.py
├── core/               # Core business logic
│   ├── analysis/       # Analysis engine integration
│   ├── database/       # PostgreSQL operations
│   ├── storage/        # File storage operations
│   └── auth/          # Authentication logic
├── models/            # Data models and schemas
│   ├── api/           # API request/response models
│   ├── database/      # PostgreSQL table models
│   └── analysis/      # Analysis result models
└── utils/             # Shared utilities
    ├── logging.py
    ├── validation.py
    └── config.py
```

### Data Flow and Communication Patterns

**Service Layer Architecture:**
```python
# Service interfaces for clean separation
class AnalysisService:
    async def create_job(self, file_data: bytes) -> JobResult
    async def get_job_status(self, job_id: str) -> JobStatus
    async def get_job_results(self, job_id: str) -> AnalysisResult

class DatabaseService:
    async def create_job(self, job_data: JobData) -> str
    async def update_job_status(self, job_id: str, status: str)
    async def get_user_jobs(self, user_id: str) -> List[JobSummary]

class StorageService:
    async def store_file(self, file_data: bytes) -> str
    async def get_file(self, file_id: str) -> bytes
    async def cache_results(self, job_id: str, results: dict)
    async def get_cached_results(self, job_id: str) -> dict
```

**Dependency Injection Pattern:**
- FastAPI dependency injection for service instances
- Configuration-based service initialization
- Mock services for testing environments

## Security Considerations

### Authentication and Authorization Strategy

**API Key Authentication:**
- SHA-256 hashed API keys stored in PostgreSQL
- Bearer token authentication for all API endpoints
- Rate limiting based on API key tier (basic, premium, enterprise)

**Authorization Levels:**
```python
# User permission levels
class UserTier:
    BASIC = "basic"        # 100 requests/day, 10MB files
    PREMIUM = "premium"    # 1000 requests/day, 100MB files
    ENTERPRISE = "enterprise"  # Unlimited requests, 1GB files
```

**Security Headers:**
- CORS configuration for web client support
- Security headers (HSTS, CSP, X-Frame-Options)
- Request ID tracking for audit trails

### Data Validation and Sanitization

**Input Validation:**
```python
# File upload validation
class FileUploadRequest:
    file: bytes = Field(..., max_length=100_000_000)  # 100MB limit
    filename: str = Field(..., regex=r'^[a-zA-Z0-9._-]+$')
    content_type: str = Field(..., regex=r'^application/.*')

# Job creation validation  
class JobCreateRequest:
    analysis_type: AnalysisType = Field(...)
    priority: int = Field(default=0, ge=0, le=10)
    options: Dict[str, Any] = Field(default_factory=dict)
```

**File Security:**
- Magic number validation for uploaded files
- Sandboxed analysis execution
- Temporary file cleanup after processing
- Path traversal prevention in file operations

## Performance & Scalability

### Performance Optimization Principles

**Database Optimization:**
- Connection pooling for PostgreSQL connections
- Indexed queries for job lookups and user operations
- JSONB fields for flexible metadata storage
- Query optimization with EXPLAIN ANALYZE

**File System Optimization:**
- Hash-based file deduplication
- TTL-based cache cleanup processes
- Efficient file streaming for large uploads
- Asynchronous file I/O operations

**Memory Management:**
- Streaming file processing for large binaries
- Limited concurrent analysis jobs
- Garbage collection optimization for long-running processes

### Caching Strategy and Implementation

**Multi-Level Caching:**
```python
# Result caching layers
class CacheStrategy:
    MEMORY_CACHE = "memory"      # In-process cache for hot data
    FILE_CACHE = "file"          # Disk-based cache for results
    DATABASE_CACHE = "database"  # PostgreSQL query result cache
```

**Cache Policies:**
- **Analysis Results**: 24-hour TTL in file cache
- **User Sessions**: 1-hour TTL in memory cache
- **Rate Limit Data**: 1-minute TTL in database
- **File Metadata**: 6-hour TTL in memory cache

**Cache Invalidation:**
- Time-based expiration for all cache levels
- Event-driven invalidation for critical updates
- Background cleanup processes for expired data

### Scalability Design Considerations

**Horizontal Scaling Readiness:**
- Stateless API design for load balancer compatibility
- PostgreSQL connection pooling for multiple API instances
- Shared file storage for multi-instance deployments
- Configuration-based service discovery

**Resource Scaling Patterns:**
```yaml
# Docker Compose scaling configuration
services:
  api:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
  
  database:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

## Testing Strategy

### Testing Approach and Coverage Philosophy

**Testing Pyramid:**
- **Unit Tests (70%)**: Individual component testing with mocks
- **Integration Tests (20%)**: PostgreSQL and file system integration
- **End-to-End Tests (10%)**: Complete API workflow testing

**Test Categories:**
```python
# Test markers for different test types
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.security
@pytest.mark.api
```

### Test Organization and Dependency Management

**Test Structure:**
```
tests/
├── unit/               # Unit tests with mocks
│   ├── api/           # API endpoint tests
│   ├── services/      # Business logic tests
│   └── models/        # Data model tests
├── integration/       # Integration tests
│   ├── database/      # PostgreSQL integration
│   ├── storage/       # File system integration
│   └── analysis/      # Analysis engine integration
├── performance/       # Load and performance tests
└── fixtures/          # Test data and utilities
    ├── files/         # Sample binary files
    ├── database/      # Test database fixtures
    └── responses/     # Expected API responses
```

**Test Data Management:**
- PostgreSQL test database with isolated transactions
- Temporary file system for upload/storage tests
- Mock external dependencies (radare2 in unit tests)
- Cleanup fixtures to maintain test isolation

## Deployment & DevOps

### Deployment Pipeline Architecture

**Docker Compose Configuration:**
```yaml
version: '3.8'
services:
  database:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: bin2nlp
      POSTGRES_USER: bin2nlp
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bin2nlp"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    ports:
      - "8000:8000"
    environment:
      - DATABASE_HOST=database
      - DATABASE_PORT=5432
      - DATABASE_NAME=bin2nlp
      - DATABASE_USER=bin2nlp
      - DATABASE_PASSWORD=${DB_PASSWORD}
    volumes:
      - app_data:/var/lib/app/data
      - app_logs:/var/log/app
    depends_on:
      database:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  app_data:
  app_logs:
```

**Environment Configuration:**
```bash
# Production environment variables
DATABASE_HOST=database
DATABASE_PORT=5432
DATABASE_NAME=bin2nlp
DATABASE_USER=bin2nlp
DATABASE_PASSWORD=secure_password_here

# Application settings
ENVIRONMENT=production
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000

# Security settings
API_KEY_SECRET=your_secret_here
CORS_ORIGINS=["https://yourdomain.com"]
SECURITY_REQUIRE_HTTPS=true
```

### Monitoring and Logging Requirements

**Structured Logging:**
```python
import structlog

logger = structlog.get_logger(__name__)

# Request logging with correlation ID
logger.info(
    "api_request",
    endpoint="/api/v1/jobs",
    method="POST",
    user_id="user123",
    request_id="req-abc123",
    duration_ms=245
)
```

**Health Check Endpoints:**
```python
@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database": await check_database_health(),
        "storage": await check_storage_health()
    }
```

**Monitoring Metrics:**
- Request rate and response times
- Database connection pool status
- File storage usage and performance
- Analysis job queue depth and processing times
- Error rates by endpoint and user

## Risk Assessment

### Technical Risks and Mitigation Strategies

**High Priority Risks:**

1. **Database Performance Degradation**
   - *Risk*: PostgreSQL performance issues with large job volumes
   - *Mitigation*: Connection pooling, query optimization, database monitoring
   - *Fallback*: Read replicas and query result caching

2. **File Storage Disk Space Exhaustion**
   - *Risk*: Uploaded files and cache data consuming all disk space
   - *Mitigation*: Automated cleanup processes, storage monitoring, file size limits
   - *Fallback*: External storage integration (S3, GCS)

3. **Analysis Engine Resource Exhaustion**
   - *Risk*: Large or malicious files causing memory/CPU exhaustion
   - *Mitigation*: Resource limits, timeouts, sandboxing, job queuing
   - *Fallback*: Dedicated worker containers with resource isolation

**Medium Priority Risks:**

1. **PostgreSQL Database Corruption**
   - *Risk*: Data loss or corruption affecting job metadata
   - *Mitigation*: Regular backups, WAL archiving, replication
   - *Fallback*: Point-in-time recovery procedures

2. **File System Corruption**
   - *Risk*: Cache or upload file corruption affecting results
   - *Mitigation*: File integrity checks, redundant storage
   - *Fallback*: Re-analysis capability for corrupted results

### Dependencies and Potential Blockers

**Critical Dependencies:**
- **PostgreSQL**: Core dependency for all job and user data
- **radare2**: Essential for binary analysis functionality
- **Docker**: Required for containerized deployment

**Potential Blockers:**
- PostgreSQL version compatibility issues
- radare2 API changes or installation problems
- File system permission issues in containerized environments

## Development Phases

### High-Level Implementation Phases

**Phase 1: Core Infrastructure (Week 1-2)**
- PostgreSQL database schema implementation
- Basic API structure with FastAPI
- File storage system with upload/download
- Docker containerization setup

**Phase 2: Analysis Integration (Week 3-4)**
- radare2 integration and job processing
- Analysis result caching system
- Background job management
- Error handling and logging

**Phase 3: User Management (Week 5-6)**
- API key authentication system
- Rate limiting implementation
- User data management
- Security hardening

**Phase 4: Testing & Optimization (Week 7-8)**
- Comprehensive test suite implementation
- Performance optimization and profiling
- Documentation and deployment guides
- Production readiness validation

### Milestone Definitions

**M1: Database & API Foundation**
- ✅ PostgreSQL schema deployed and tested
- ✅ Basic CRUD API endpoints functional
- ✅ File upload/download working
- ✅ Docker containers running

**M2: Analysis Engine Integration**
- ✅ radare2 processing pipeline complete
- ✅ Job status tracking implemented
- ✅ Result caching system operational
- ✅ Error handling comprehensive

**M3: Authentication & Security**
- ✅ API key system fully functional
- ✅ Rate limiting enforced
- ✅ Security tests passing
- ✅ User management complete

**M4: Production Readiness**
- ✅ All tests passing (>90% coverage)
- ✅ Performance benchmarks met
- ✅ Documentation complete
- ✅ Deployment automated

This technical design provides a comprehensive foundation for the Phase 1 integrated system, focusing on the hybrid PostgreSQL + File Storage architecture that eliminates external dependencies while maintaining high performance and scalability.