# 🎯 Comprehensive User Acceptance Test (UAT) Plan - bin2nlp API

## Executive Summary

This document provides a comprehensive User Acceptance Test plan for the bin2nlp Binary Decompilation & LLM Translation Service API. The plan covers all 34 identified endpoints across 6 functional categories with detailed test scenarios, automated test frameworks, and performance validation criteria.

### Test Coverage Overview
- **34 API endpoints** across 6 functional categories
- **End-to-end workflows** from binary upload to result retrieval
- **Authentication and authorization** testing for all protected endpoints
- **Performance validation** against PRD requirements
- **Error handling and edge cases** for robust system validation
- **Automated test framework** using pytest and Python requests

## 🏗️ Test Architecture & Framework

### Automated Test Framework Structure
```
tests/uat/
├── conftest.py                    # Pytest fixtures and configuration
├── test_01_health_system.py       # Health & System endpoints
├── test_02_decompilation_core.py  # Core decompilation workflow
├── test_03_llm_providers.py       # LLM provider management
├── test_04_admin_auth.py          # Admin authentication & API keys
├── test_05_admin_monitoring.py    # Admin monitoring & metrics
├── test_06_admin_circuit_alerts.py # Circuit breakers & alerts
├── test_99_end_to_end.py          # Complete user journeys
├── utils/
│   ├── api_client.py              # Centralized API client
│   ├── test_data.py               # Test binary files and data
│   ├── assertions.py              # Common test assertions
│   └── performance.py             # Performance validation utilities
└── data/
    ├── test_binaries/             # Sample binary files for testing
    │   ├── ssh-keygen             # Known working binary
    │   ├── hello_world.exe        # Simple Windows executable
    │   ├── malformed.bin          # Invalid/corrupted file
    │   └── large_binary.elf       # Large file for performance testing
    └── expected_responses/        # Expected API response templates
```

### Test Environment Requirements
- **API Server**: Running at http://localhost:8000
- **Redis**: Available for cache/queue operations
- **Test Data**: Sample binaries of various sizes and formats
- **Authentication**: Development API keys for testing
- **Network**: Stable connection for LLM provider health checks

## 📋 Detailed Test Specifications by Category

## 🏥 Category 1: Health & System Endpoints (4 tests)

### TEST-H01: Basic Health Check
**Endpoint:** `GET /api/v1/health`
**Purpose:** Validate system health reporting and component status

#### Test Scenarios:
```python
def test_health_basic():
    """Test basic health endpoint functionality"""
    response = client.get("/api/v1/health")
    
    # Status validation
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    
    # Response structure validation
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "components" in data
    assert "version" in data
    
    # Component health validation
    components = data["components"]
    assert "redis" in components
    assert "decompilation_engine" in components
    
    # Performance validation
    assert response.elapsed.total_seconds() < 2.0  # PRD requirement
```

#### Expected Response Format:
```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2025-01-01T00:00:00Z",
  "version": "1.0.0",
  "components": {
    "redis": {"status": "healthy", "response_time_ms": 5},
    "decompilation_engine": {"status": "healthy", "version": "r2-5.8.0"},
    "llm_providers": {"openai": "healthy", "anthropic": "healthy"}
  },
  "uptime_seconds": 3600
}
```

### TEST-H02: Kubernetes Readiness Check
**Endpoint:** `GET /api/v1/health/ready`
**Purpose:** Validate readiness probe for container orchestration

#### Test Scenarios:
```python
def test_readiness_when_ready():
    """Test readiness endpoint when system is ready"""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200

def test_readiness_when_not_ready():
    """Test readiness endpoint when dependencies unavailable"""
    # Simulate Redis unavailability
    with mock_redis_down():
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
```

### TEST-H03: Kubernetes Liveness Check  
**Endpoint:** `GET /api/v1/health/live`
**Purpose:** Validate liveness probe for container restart decisions

#### Test Scenarios:
```python
def test_liveness_always_healthy():
    """Test liveness endpoint always returns healthy unless app broken"""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
```

### TEST-H04: System Information & Capabilities
**Endpoint:** `GET /api/v1/system/info`  
**Purpose:** Validate system capability reporting

#### Test Scenarios:
```python
def test_system_info_complete():
    """Test system info returns complete capability information"""
    response = client.get("/api/v1/system/info")
    
    assert response.status_code == 200
    data = response.json()
    
    # Validate required fields from PRD
    assert "supported_formats" in data
    assert "max_file_size_mb" in data
    assert "analysis_depths" in data  
    assert "llm_providers" in data
    
    # Validate supported formats match PRD requirements
    formats = data["supported_formats"]
    assert "exe" in formats  # Windows
    assert "elf" in formats  # Linux
    assert "dll" in formats  # Windows libraries
    assert "so" in formats   # Linux libraries
```

## 🔄 Category 2: Core Decompilation Workflow (4 tests)

### TEST-D01: Submit Decompilation Job
**Endpoint:** `POST /api/v1/decompile`
**Purpose:** Validate binary file upload and job creation

#### Test Parameters Analysis (from code):
```python
# From src/api/routes/decompilation.py:128-137
UPLOAD_PARAMETERS = {
    "file": "UploadFile - Binary file (required)",
    "analysis_depth": "str - basic|standard|comprehensive (default: standard)",
    "llm_provider": "Optional[str] - openai|anthropic|gemini|ollama",
    "llm_model": "Optional[str] - Model name for chosen provider", 
    "llm_endpoint_url": "Optional[str] - Custom endpoint URL",
    "llm_api_key": "Optional[str] - Provider API key",
    "translation_detail": "str - basic|standard|detailed (default: standard)"
}
```

#### Test Scenarios:
```python
def test_decompile_submit_minimal():
    """Test minimal decompilation job submission"""
    with open("tests/uat/data/test_binaries/ssh-keygen", "rb") as f:
        files = {"file": ("ssh-keygen", f, "application/octet-stream")}
        response = client.post("/api/v1/decompile", files=files)
    
    # Validate successful submission
    assert response.status_code == 202  # Accepted for async processing
    data = response.json()
    
    # Validate response structure
    assert data["success"] is True
    assert "job_id" in data
    assert data["status"] == "queued"
    assert "check_status_url" in data
    
    # Validate job ID format (UUID-like)
    job_id = data["job_id"]
    assert len(job_id) == 36  # UUID format
    assert job_id.count("-") == 4

def test_decompile_submit_all_parameters():
    """Test decompilation with all parameters specified"""
    with open("tests/uat/data/test_binaries/hello_world.exe", "rb") as f:
        files = {"file": ("hello_world.exe", f, "application/octet-stream")}
        data = {
            "analysis_depth": "comprehensive",
            "llm_provider": "openai",
            "llm_model": "gpt-4",
            "translation_detail": "detailed"
        }
        response = client.post("/api/v1/decompile", files=files, data=data)
    
    assert response.status_code == 202
    response_data = response.json()
    
    # Validate configuration echoed back
    config = response_data["config"]
    assert config["analysis_depth"] == "comprehensive"
    assert config["llm_provider"] == "openai"
    assert config["translation_detail"] == "detailed"

def test_decompile_file_size_validation():
    """Test file size limits from settings"""
    # Test oversized file rejection
    large_data = b"A" * (101 * 1024 * 1024)  # 101MB > 100MB limit
    files = {"file": ("large_file.bin", large_data, "application/octet-stream")}
    
    response = client.post("/api/v1/decompile", files=files)
    assert response.status_code == 413  # Payload Too Large
    
    error_data = response.json()
    assert "File too large" in error_data["detail"]
    assert "100MB" in error_data["detail"]

def test_decompile_invalid_analysis_depth():
    """Test invalid analysis depth parameter"""
    with open("tests/uat/data/test_binaries/ssh-keygen", "rb") as f:
        files = {"file": ("ssh-keygen", f, "application/octet-stream")}
        data = {"analysis_depth": "invalid_depth"}
        
        response = client.post("/api/v1/decompile", files=files, data=data)
        assert response.status_code == 422  # Validation Error
```

#### Expected Response Format:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "message": "Decompilation job submitted successfully",
  "file_info": {
    "filename": "ssh-keygen",
    "size_bytes": 829616,
    "content_type": "application/octet-stream"
  },
  "config": {
    "analysis_depth": "standard",
    "llm_provider": null,
    "translation_detail": "standard"
  },
  "estimated_completion": "5-10 minutes",
  "check_status_url": "/api/v1/decompile/550e8400-e29b-41d4-a716-446655440000"
}
```

### TEST-D02: Test Endpoint Connectivity
**Endpoint:** `GET /api/v1/decompile/test`
**Purpose:** Validate decompilation service availability

#### Test Scenarios:
```python
def test_decompile_test_endpoint():
    """Test decompilation API connectivity"""
    response = client.get("/api/v1/decompile/test")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Decompilation API is working" in data["message"]
```

### TEST-D03: Get Job Status & Results
**Endpoint:** `GET /api/v1/decompile/{job_id}`
**Purpose:** Validate job progress tracking and result retrieval

#### Test Parameters Analysis:
```python
# From src/api/routes/decompilation.py:232-234
RESULT_PARAMETERS = {
    "job_id": "str - UUID job identifier (path parameter)",
    "include_raw_data": "bool - Include raw analysis data (default: false)"
}
```

#### Test Scenarios:
```python
def test_get_job_status_queued():
    """Test job status for newly submitted job"""
    # Submit job first
    job_id = submit_test_job()
    
    response = client.get(f"/api/v1/decompile/{job_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] in ["queued", "processing"]
    assert "progress_percentage" in data
    assert "current_stage" in data

def test_get_job_status_completed():
    """Test job status and results for completed job"""
    # Submit job and wait for completion
    job_id = submit_test_job_and_wait()
    
    response = client.get(f"/api/v1/decompile/{job_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "completed"
    assert "results" in data
    
    # Validate result structure from cache analysis
    results = data["results"]
    assert "success" in results
    assert "function_count" in results
    assert "import_count" in results
    assert "string_count" in results
    assert "duration_seconds" in results

def test_get_job_nonexistent():
    """Test retrieval of non-existent job"""
    fake_job_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/decompile/{fake_job_id}")
    
    assert response.status_code == 404
    error_data = response.json()
    assert "Job not found" in error_data["detail"]

def test_get_job_with_raw_data():
    """Test job results with raw data inclusion"""
    job_id = submit_test_job_and_wait()
    
    response = client.get(f"/api/v1/decompile/{job_id}?include_raw_data=true")
    assert response.status_code == 200
    
    # Raw data should include additional fields
    data = response.json()
    assert "results" in data
```

#### Expected Response Formats:

**Queued/Processing Job:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress_percentage": 45.0,
  "current_stage": "Decompiling functions",
  "worker_id": "background-worker",
  "updated_at": "2025-01-01T00:05:00Z",
  "message": "Decompilation in progress: Decompiling functions"
}
```

**Completed Job:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000", 
  "status": "completed",
  "progress_percentage": 100.0,
  "current_stage": "Decompilation complete",
  "worker_id": "background-worker",
  "updated_at": "2025-01-01T00:15:00Z",
  "results": {
    "success": true,
    "function_count": 351,
    "import_count": 89,
    "string_count": 2680,
    "duration_seconds": 13.5,
    "decompilation_id": "dec_550e8400"
  },
  "message": "Decompilation completed successfully"
}
```

### TEST-D04: Cancel Decompilation Job
**Endpoint:** `DELETE /api/v1/decompile/{job_id}`
**Purpose:** Validate job cancellation functionality

#### Test Scenarios:
```python
def test_cancel_pending_job():
    """Test cancellation of pending job"""
    job_id = submit_test_job()
    
    response = client.delete(f"/api/v1/decompile/{job_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert "cancelled successfully" in data["message"]
    
    # Verify job is actually cancelled
    status_response = client.get(f"/api/v1/decompile/{job_id}")
    status_data = status_response.json()
    assert status_data["status"] == "cancelled"

def test_cancel_nonexistent_job():
    """Test cancellation of non-existent job"""
    fake_job_id = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/api/v1/decompile/{fake_job_id}")
    
    assert response.status_code == 400
    error_data = response.json()
    assert "could not be cancelled" in error_data["detail"]
```

## 🤖 Category 3: LLM Provider Management (3 tests)

### TEST-L01: List Available LLM Providers
**Endpoint:** `GET /api/v1/llm-providers`
**Purpose:** Validate LLM provider discovery and status reporting

#### Test Scenarios:
```python
def test_list_llm_providers():
    """Test listing all available LLM providers"""
    response = client.get("/api/v1/llm-providers")
    assert response.status_code == 200
    
    data = response.json()
    assert "providers" in data
    
    # Validate expected providers from PRD
    providers = data["providers"]
    provider_ids = [p["provider_id"] for p in providers]
    
    # Should include major providers mentioned in PRD
    expected_providers = ["openai", "anthropic", "gemini", "ollama"]
    for expected in expected_providers:
        assert any(expected in pid for pid in provider_ids)
    
    # Validate provider structure
    for provider in providers:
        assert "provider_id" in provider
        assert "name" in provider
        assert "status" in provider
        assert "available_models" in provider
        assert "health_status" in provider
```

#### Expected Response Format:
```json
{
  "providers": [
    {
      "provider_id": "openai",
      "name": "OpenAI",
      "status": "active",
      "health_status": "healthy",
      "available_models": ["gpt-4", "gpt-3.5-turbo"],
      "cost_per_1k_tokens": 0.03,
      "max_context_tokens": 8192
    },
    {
      "provider_id": "anthropic", 
      "name": "Anthropic Claude",
      "status": "active",
      "health_status": "healthy",
      "available_models": ["claude-3-opus", "claude-3-sonnet"],
      "cost_per_1k_tokens": 0.015,
      "max_context_tokens": 200000
    }
  ],
  "total_providers": 4,
  "healthy_providers": 3
}
```

### TEST-L02: Get LLM Provider Details
**Endpoint:** `GET /api/v1/llm-providers/{provider_id}`
**Purpose:** Validate detailed provider information retrieval

#### Test Scenarios:
```python
def test_get_provider_details_openai():
    """Test detailed information for OpenAI provider"""
    response = client.get("/api/v1/llm-providers/openai")
    assert response.status_code == 200
    
    data = response.json()
    assert data["provider_id"] == "openai"
    assert "health_metrics" in data
    assert "recent_performance" in data
    assert "configuration" in data
    assert "circuit_breaker_status" in data

def test_get_provider_details_nonexistent():
    """Test details for non-existent provider"""
    response = client.get("/api/v1/llm-providers/nonexistent")
    assert response.status_code == 404
```

### TEST-L03: LLM Provider Health Check
**Endpoint:** `POST /api/v1/llm-providers/{provider_id}/health-check`
**Purpose:** Validate provider connectivity testing

#### Test Scenarios:
```python
def test_provider_health_check_success():
    """Test successful health check of available provider"""
    response = client.post("/api/v1/llm-providers/openai/health-check")
    assert response.status_code == 200
    
    data = response.json()
    assert "health_status" in data
    assert "response_time_ms" in data
    assert "test_timestamp" in data

def test_provider_health_check_failure():
    """Test health check of unavailable provider"""
    # This test may need to mock provider unavailability
    with mock_provider_down("anthropic"):
        response = client.post("/api/v1/llm-providers/anthropic/health-check")
        assert response.status_code == 200
        
        data = response.json()
        assert data["health_status"] == "unhealthy"
        assert "error_message" in data
```

## 🔐 Category 4: Admin Authentication & API Key Management (4 tests)

### Authentication Setup
All admin endpoints require authentication. Test setup must include:

```python
@pytest.fixture
def admin_headers():
    """Fixture providing admin API key headers"""
    # Create development API key
    response = client.post("/api/v1/admin/dev/create-api-key?user_id=test_admin")
    api_key = response.json()["api_key"]
    
    return {"Authorization": f"Bearer {api_key}"}

@pytest.fixture  
def standard_headers():
    """Fixture providing standard user API key headers"""
    response = client.post("/api/v1/admin/dev/create-api-key?user_id=test_user")
    api_key = response.json()["api_key"]
    
    return {"Authorization": f"Bearer {api_key}"}
```

### TEST-A01: Create API Key
**Endpoint:** `POST /api/v1/admin/api-keys`
**Purpose:** Validate API key creation with proper validation

#### Test Parameters Analysis:
```python
# From src/api/routes/admin.py:40-47
CREATE_API_KEY_PARAMS = {
    "user_id": "str - User identifier (required, 1-100 chars)",
    "tier": "str - basic|standard|premium|enterprise (default: basic)",
    "permissions": "List[str] - Permission list (default: ['read'])",
    "expires_days": "Optional[int] - Expiry days (1-3650, default: None)",
    "description": "Optional[str] - Key description (max 255 chars)"
}
```

#### Test Scenarios:
```python
def test_create_api_key_minimal(admin_headers):
    """Test API key creation with minimal parameters"""
    request_data = {
        "user_id": "test_user_123"
    }
    
    response = client.post("/api/v1/admin/api-keys", 
                          json=request_data, headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "api_key" in data
    assert "key_info" in data
    
    key_info = data["key_info"]
    assert key_info["user_id"] == "test_user_123"
    assert key_info["tier"] == "basic"  # default
    assert key_info["permissions"] == ["read"]  # default

def test_create_api_key_full_params(admin_headers):
    """Test API key creation with all parameters"""
    request_data = {
        "user_id": "premium_user",
        "tier": "premium", 
        "permissions": ["read", "write", "admin"],
        "expires_days": 90,
        "description": "Premium user API key for testing"
    }
    
    response = client.post("/api/v1/admin/api-keys",
                          json=request_data, headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    key_info = data["key_info"]
    assert key_info["tier"] == "premium"
    assert set(key_info["permissions"]) == {"read", "write", "admin"}
    assert key_info["expires_at"] is not None

def test_create_api_key_validation_errors(admin_headers):
    """Test API key creation validation"""
    # Test invalid tier
    invalid_tier_data = {"user_id": "test", "tier": "invalid_tier"}
    response = client.post("/api/v1/admin/api-keys", 
                          json=invalid_tier_data, headers=admin_headers)
    assert response.status_code == 422
    
    # Test invalid expires_days
    invalid_expires_data = {"user_id": "test", "expires_days": 5000}
    response = client.post("/api/v1/admin/api-keys",
                          json=invalid_expires_data, headers=admin_headers) 
    assert response.status_code == 422

def test_create_api_key_unauthorized():
    """Test API key creation without admin permission"""
    request_data = {"user_id": "test_user"}
    
    # No headers (unauthenticated)
    response = client.post("/api/v1/admin/api-keys", json=request_data)
    assert response.status_code == 401
    
    # Standard user headers (insufficient permission)
    response = client.post("/api/v1/admin/api-keys", 
                          json=request_data, headers=standard_headers)
    assert response.status_code == 403
```

#### Expected Response Format:
```json
{
  "success": true,
  "api_key": "sk-bin2nlp-abc123def456...",
  "key_info": {
    "key_id": "key_550e8400",
    "user_id": "premium_user",
    "tier": "premium",
    "permissions": ["read", "write", "admin"],
    "status": "active",
    "created_at": "2025-01-01T00:00:00Z",
    "last_used_at": null,
    "expires_at": "2025-04-01T00:00:00Z"
  },
  "warning": "Store this API key securely. It cannot be retrieved again."
}
```

### TEST-A02: List User API Keys
**Endpoint:** `GET /api/v1/admin/api-keys/{user_id}`
**Purpose:** Validate API key listing for users

#### Test Scenarios:
```python
def test_list_user_api_keys(admin_headers):
    """Test listing API keys for specific user"""
    user_id = "test_user_with_keys"
    
    # Create some keys first
    create_test_api_keys(user_id, count=3)
    
    response = client.get(f"/api/v1/admin/api-keys/{user_id}", 
                         headers=admin_headers)
    assert response.status_code == 200
    
    keys = response.json()
    assert len(keys) == 3
    
    for key in keys:
        assert key["user_id"] == user_id
        assert "key_id" in key
        assert "tier" in key
        assert "status" in key
        assert "created_at" in key

def test_list_user_api_keys_empty(admin_headers):
    """Test listing API keys for user with no keys"""
    user_id = "user_with_no_keys"
    
    response = client.get(f"/api/v1/admin/api-keys/{user_id}",
                         headers=admin_headers)
    assert response.status_code == 200
    
    keys = response.json()
    assert len(keys) == 0
```

### TEST-A03: Revoke API Key
**Endpoint:** `DELETE /api/v1/admin/api-keys/{user_id}/{key_id}`
**Purpose:** Validate API key revocation

#### Test Scenarios:
```python
def test_revoke_api_key_success(admin_headers):
    """Test successful API key revocation"""
    user_id = "test_user"
    key_id = create_test_api_key(user_id)
    
    response = client.delete(f"/api/v1/admin/api-keys/{user_id}/{key_id}",
                           headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["revoked"] is True
    
    # Verify key is revoked by trying to use it
    # ... implementation depends on key validation system

def test_revoke_nonexistent_key(admin_headers):
    """Test revocation of non-existent key"""
    user_id = "test_user"
    fake_key_id = "nonexistent_key"
    
    response = client.delete(f"/api/v1/admin/api-keys/{user_id}/{fake_key_id}",
                           headers=admin_headers)
    assert response.status_code == 404
```

### TEST-A04: Create Development API Key
**Endpoint:** `POST /api/v1/admin/dev/create-api-key`
**Purpose:** Validate development key creation (debug mode only)

#### Test Scenarios:
```python
def test_create_dev_api_key():
    """Test development API key creation"""
    response = client.post("/api/v1/admin/dev/create-api-key?user_id=dev_test")
    assert response.status_code == 200
    
    data = response.json()
    assert "api_key" in data
    assert "user_id" in data
    assert data["user_id"] == "dev_test"

def test_create_dev_api_key_default_user():
    """Test development API key with default user"""
    response = client.post("/api/v1/admin/dev/create-api-key")
    assert response.status_code == 200
    
    data = response.json()
    assert data["user_id"] == "dev_user"  # default from code
```

## 📊 Category 5: Admin Monitoring & Metrics (11 tests)

### TEST-M01: System Statistics
**Endpoint:** `GET /api/v1/admin/stats`
**Purpose:** Validate comprehensive system statistics

#### Test Scenarios:
```python
def test_get_system_stats(admin_headers):
    """Test system statistics retrieval"""
    response = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "redis_stats" in data
    assert "rate_limit_stats" in data  
    assert "api_key_stats" in data
    assert "system_health" in data
    
    # Validate Redis stats structure
    redis_stats = data["redis_stats"]
    assert "connected_clients" in redis_stats
    assert "used_memory" in redis_stats
    
    # Validate API key stats
    api_key_stats = data["api_key_stats"]
    assert "total_keys" in api_key_stats
    assert "active_keys" in api_key_stats
```

### TEST-M02: System Configuration
**Endpoint:** `GET /api/v1/admin/config`
**Purpose:** Validate system configuration reporting (non-sensitive)

#### Test Scenarios:
```python
def test_get_system_config(admin_headers):
    """Test system configuration retrieval"""
    response = client.get("/api/v1/admin/config", headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    
    # Should include non-sensitive configuration
    assert "max_file_size_mb" in data
    assert "supported_formats" in data
    assert "analysis_timeout_seconds" in data
    
    # Should NOT include sensitive data
    assert "api_keys" not in data
    assert "database_passwords" not in data
    assert "secret_key" not in data
```

### TEST-M03: User Rate Limits
**Endpoint:** `GET /api/v1/admin/rate-limits/{user_id}`
**Purpose:** Validate rate limit status reporting

#### Test Scenarios:
```python
def test_get_user_rate_limits(admin_headers):
    """Test user rate limit status"""
    user_id = "test_user_rate_limits"
    
    response = client.get(f"/api/v1/admin/rate-limits/{user_id}",
                         headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "current_usage" in data
    assert "limits" in data
    assert "reset_time" in data
    
    # Validate rate limit structure
    limits = data["limits"]
    assert "requests_per_minute" in limits
    assert "requests_per_hour" in limits
```

### TEST-M04-M11: Metrics Endpoints
**Endpoints:** Various metrics endpoints
**Purpose:** Validate comprehensive metrics collection

#### Test Scenarios:
```python
def test_current_metrics(admin_headers):
    """Test current metrics snapshot"""
    response = client.get("/api/v1/admin/metrics/current", headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    # Validate metrics structure based on code analysis
    assert "counters" in data or "metrics" in data

def test_performance_metrics(admin_headers):
    """Test performance metrics with parameters"""
    response = client.get("/api/v1/admin/metrics/performance?operation_type=decompilation&time_window_minutes=30",
                         headers=admin_headers)
    assert response.status_code == 200

def test_decompilation_metrics(admin_headers):
    """Test decompilation-specific metrics"""
    response = client.get("/api/v1/admin/metrics/decompilation?time_window_minutes=60",
                         headers=admin_headers)
    assert response.status_code == 200

def test_llm_metrics(admin_headers):
    """Test LLM provider metrics"""
    response = client.get("/api/v1/admin/metrics/llm?time_window_minutes=60",
                         headers=admin_headers)
    assert response.status_code == 200

def test_dashboard_overview(admin_headers):
    """Test dashboard overview"""
    response = client.get("/api/v1/admin/dashboards/overview", headers=admin_headers)
    assert response.status_code == 200

def test_dashboard_performance(admin_headers):
    """Test performance dashboard"""  
    response = client.get("/api/v1/admin/dashboards/performance", headers=admin_headers)
    assert response.status_code == 200

def test_prometheus_metrics(admin_headers):
    """Test Prometheus metrics export"""
    response = client.get("/api/v1/admin/monitoring/prometheus", headers=admin_headers)
    assert response.status_code == 200
    
    # Should return Prometheus format
    assert response.headers["content-type"].startswith("text/plain")

def test_health_summary(admin_headers):
    """Test health summary"""
    response = client.get("/api/v1/admin/monitoring/health-summary", headers=admin_headers)
    assert response.status_code == 200
```

## ⚡ Category 6: Admin Circuit Breakers & Alerts (9 tests)

### TEST-C01: Circuit Breaker Status
**Endpoint:** `GET /api/v1/admin/circuit-breakers`
**Purpose:** Validate circuit breaker status reporting

#### Test Scenarios:
```python
def test_get_all_circuit_breakers(admin_headers):
    """Test listing all circuit breaker status"""
    response = client.get("/api/v1/admin/circuit-breakers", headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, dict)
    
    # Should include circuit breakers for LLM providers
    expected_circuits = ["openai", "anthropic", "gemini", "ollama"]
    for circuit in expected_circuits:
        if circuit in data:
            circuit_data = data[circuit]
            assert "state" in circuit_data  # closed/open/half_open
            assert "failure_count" in circuit_data
            assert "last_failure_time" in circuit_data

def test_get_specific_circuit_breaker(admin_headers):
    """Test specific circuit breaker details"""
    circuit_name = "openai"
    response = client.get(f"/api/v1/admin/circuit-breakers/{circuit_name}",
                         headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["circuit_name"] == circuit_name
    assert "state" in data
    assert "configuration" in data
    assert "statistics" in data

def test_get_nonexistent_circuit_breaker(admin_headers):
    """Test non-existent circuit breaker"""
    response = client.get("/api/v1/admin/circuit-breakers/nonexistent",
                         headers=admin_headers)
    assert response.status_code == 404
```

### TEST-C02: Circuit Breaker Control
**Endpoints:** Reset and force-open circuit breakers
**Purpose:** Validate circuit breaker control operations

#### Test Scenarios:
```python
def test_reset_circuit_breaker(admin_headers):
    """Test circuit breaker reset"""
    circuit_name = "openai"
    
    response = client.post(f"/api/v1/admin/circuit-breakers/{circuit_name}/reset",
                          headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "success" in data or "reset" in data

def test_force_open_circuit_breaker(admin_headers):
    """Test forcing circuit breaker open"""
    circuit_name = "anthropic"
    
    response = client.post(f"/api/v1/admin/circuit-breakers/{circuit_name}/force-open",
                          headers=admin_headers)
    assert response.status_code == 200
    
    # Verify circuit breaker is now open
    status_response = client.get(f"/api/v1/admin/circuit-breakers/{circuit_name}",
                                headers=admin_headers)
    status_data = status_response.json()
    assert status_data["state"] == "open"

def test_health_check_all_circuits(admin_headers):
    """Test health checking all circuit breakers"""
    response = client.get("/api/v1/admin/circuit-breakers/health-check/all",
                         headers=admin_headers)
    assert response.status_code == 200
```

### TEST-C03: Alert Management
**Endpoints:** Alert listing, checking, acknowledgment, resolution
**Purpose:** Validate alert management system

#### Test Scenarios:
```python
def test_list_alerts(admin_headers):
    """Test listing active alerts"""
    response = client.get("/api/v1/admin/alerts", headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "alerts" in data
    assert "total_alerts" in data
    
    if data["alerts"]:
        alert = data["alerts"][0]
        assert "alert_id" in alert
        assert "severity" in alert
        assert "message" in alert
        assert "created_at" in alert

def test_trigger_alert_check(admin_headers):
    """Test triggering manual alert check"""
    response = client.post("/api/v1/admin/alerts/check", headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert "alerts_checked" in data or "check_completed" in data

def test_acknowledge_alert(admin_headers):
    """Test acknowledging an alert"""
    # First create or find an alert
    alert_id = create_test_alert()
    
    response = client.post(f"/api/v1/admin/alerts/{alert_id}/acknowledge",
                          headers=admin_headers)
    assert response.status_code == 200

def test_resolve_alert(admin_headers):
    """Test resolving an alert"""  
    alert_id = create_test_alert()
    
    response = client.post(f"/api/v1/admin/alerts/{alert_id}/resolve",
                          headers=admin_headers)
    assert response.status_code == 200
```

## 🔄 Category 7: End-to-End User Journeys (5 tests)

### TEST-E01: Complete Decompilation Workflow
**Purpose:** Validate entire user journey from upload to results

#### Test Scenarios:
```python
def test_complete_decompilation_workflow():
    """Test complete binary decompilation workflow"""
    # Step 1: Check system health
    health_response = client.get("/api/v1/health")
    assert health_response.status_code == 200
    
    # Step 2: Check system capabilities
    info_response = client.get("/api/v1/system/info")
    assert info_response.status_code == 200
    
    # Step 3: Submit binary for analysis
    with open("tests/uat/data/test_binaries/ssh-keygen", "rb") as f:
        files = {"file": ("ssh-keygen", f, "application/octet-stream")}
        data = {"analysis_depth": "standard", "llm_provider": "openai"}
        
        submit_response = client.post("/api/v1/decompile", files=files, data=data)
    
    assert submit_response.status_code == 202
    job_data = submit_response.json()
    job_id = job_data["job_id"]
    
    # Step 4: Poll for job completion (with timeout)
    start_time = time.time()
    timeout = 300  # 5 minutes max wait
    
    while time.time() - start_time < timeout:
        status_response = client.get(f"/api/v1/decompile/{job_id}")
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        if status_data["status"] == "completed":
            break
        elif status_data["status"] == "failed":
            pytest.fail(f"Job failed: {status_data.get('error_message', 'Unknown error')}")
        
        time.sleep(5)  # Wait 5 seconds before next check
    
    # Step 5: Verify completion and results
    final_response = client.get(f"/api/v1/decompile/{job_id}")
    final_data = final_response.json()
    
    assert final_data["status"] == "completed"
    assert "results" in final_data
    
    results = final_data["results"]
    assert results["success"] is True
    assert results["function_count"] > 0
    assert results["import_count"] > 0
    assert results["duration_seconds"] > 0

def test_performance_requirements_validation():
    """Test that processing meets PRD performance requirements"""
    test_cases = [
        {
            "file": "small_binary.exe",  # ≤10MB
            "max_time_seconds": 30,
            "description": "Small file performance"
        },
        {
            "file": "medium_binary.elf",  # ≤30MB  
            "max_time_seconds": 300,  # 5 minutes
            "description": "Medium file performance"
        },
        {
            "file": "large_binary.exe",  # ≤100MB
            "max_time_seconds": 1200,  # 20 minutes
            "description": "Large file performance"
        }
    ]
    
    for test_case in test_cases:
        start_time = time.time()
        
        # Submit and wait for completion
        job_id = submit_binary_and_wait(test_case["file"])
        
        total_time = time.time() - start_time
        
        # Validate performance requirement
        assert total_time <= test_case["max_time_seconds"], \
            f"{test_case['description']} exceeded {test_case['max_time_seconds']}s limit: {total_time:.2f}s"

def test_error_handling_workflow():
    """Test error handling throughout the workflow"""
    # Test 1: Invalid file format
    invalid_file = b"This is not a binary file"
    files = {"file": ("invalid.txt", invalid_file, "text/plain")}
    
    response = client.post("/api/v1/decompile", files=files)
    # Should either reject immediately or fail gracefully
    if response.status_code == 202:
        job_id = response.json()["job_id"]
        final_status = wait_for_job_completion(job_id)
        assert final_status["status"] == "failed"
    else:
        assert response.status_code in [400, 415, 422]  # Client error codes
    
    # Test 2: Oversized file
    large_file = b"A" * (101 * 1024 * 1024)  # 101MB
    files = {"file": ("large.bin", large_file, "application/octet-stream")}
    
    response = client.post("/api/v1/decompile", files=files)
    assert response.status_code == 413  # Payload Too Large

def test_llm_provider_failover():
    """Test LLM provider failover functionality"""
    # Submit job with primary provider
    with open("tests/uat/data/test_binaries/hello_world.exe", "rb") as f:
        files = {"file": ("hello_world.exe", f, "application/octet-stream")}
        data = {"llm_provider": "openai"}  # Primary provider
        
        response = client.post("/api/v1/decompile", files=files, data=data)
    
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    
    # Wait for completion and verify success despite potential provider issues
    final_status = wait_for_job_completion(job_id)
    
    # Should complete successfully even if primary provider fails
    # (depends on failover implementation)
    assert final_status["status"] in ["completed", "partial_success"]

def test_concurrent_job_processing():
    """Test multiple concurrent decompilation jobs"""
    job_ids = []
    num_concurrent_jobs = 3
    
    # Submit multiple jobs simultaneously
    for i in range(num_concurrent_jobs):
        with open("tests/uat/data/test_binaries/ssh-keygen", "rb") as f:
            files = {"file": (f"ssh-keygen-{i}", f, "application/octet-stream")}
            
            response = client.post("/api/v1/decompile", files=files)
            assert response.status_code == 202
            job_ids.append(response.json()["job_id"])
    
    # Wait for all jobs to complete
    completed_jobs = 0
    start_time = time.time()
    timeout = 600  # 10 minutes for multiple jobs
    
    while completed_jobs < num_concurrent_jobs and time.time() - start_time < timeout:
        for job_id in job_ids:
            status_response = client.get(f"/api/v1/decompile/{job_id}")
            status_data = status_response.json()
            
            if status_data["status"] == "completed":
                completed_jobs += 1
        
        time.sleep(10)  # Check every 10 seconds
    
    # Verify all jobs completed successfully
    assert completed_jobs == num_concurrent_jobs, f"Only {completed_jobs}/{num_concurrent_jobs} jobs completed"
```

## 🚀 Automated Test Framework Implementation

### TEST-F01: Core Test Framework Files

#### `tests/uat/conftest.py` - Pytest Configuration
```python
"""
UAT Test Configuration and Fixtures
"""
import pytest
import requests
import time
import os
from typing import Dict, Any, Optional

# Test configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_TIMEOUT = 30

class APIClient:
    """Centralized API client for UAT tests"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.timeout = API_TIMEOUT
    
    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make API request with proper error handling"""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, **kwargs)
            return response
        except requests.RequestException as e:
            pytest.fail(f"Request failed: {method} {url} - {str(e)}")
    
    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)
    
    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)
    
    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

@pytest.fixture(scope="session")
def client():
    """API client fixture"""
    return APIClient()

@pytest.fixture(scope="session")
def admin_api_key(client):
    """Create admin API key for testing"""
    response = client.post("/api/v1/admin/dev/create-api-key?user_id=uat_admin")
    if response.status_code != 200:
        pytest.skip("Cannot create admin API key - server may not be in dev mode")
    
    return response.json()["api_key"]

@pytest.fixture(scope="session")
def admin_headers(admin_api_key):
    """Admin authorization headers"""
    return {"Authorization": f"Bearer {admin_api_key}"}

@pytest.fixture(scope="session") 
def standard_api_key(client):
    """Create standard API key for testing"""
    response = client.post("/api/v1/admin/dev/create-api-key?user_id=uat_user")
    if response.status_code != 200:
        pytest.skip("Cannot create standard API key")
    
    return response.json()["api_key"]

@pytest.fixture(scope="session")
def standard_headers(standard_api_key):
    """Standard user authorization headers"""
    return {"Authorization": f"Bearer {standard_api_key}"}

@pytest.fixture
def test_binary_ssh_keygen():
    """SSH keygen binary file path"""
    binary_path = "tests/uat/data/test_binaries/ssh-keygen"
    if not os.path.exists(binary_path):
        pytest.skip(f"Test binary not found: {binary_path}")
    return binary_path

def wait_for_job_completion(client: APIClient, job_id: str, timeout: int = 300) -> Dict[str, Any]:
    """Wait for decompilation job to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = client.get(f"/api/v1/decompile/{job_id}")
        assert response.status_code == 200
        
        data = response.json()
        status = data["status"]
        
        if status in ["completed", "failed", "cancelled"]:
            return data
        
        time.sleep(5)  # Poll every 5 seconds
    
    pytest.fail(f"Job {job_id} did not complete within {timeout} seconds")

def submit_test_job(client: APIClient, binary_path: str, **params) -> str:
    """Submit a test decompilation job and return job ID"""
    with open(binary_path, "rb") as f:
        files = {"file": (os.path.basename(binary_path), f, "application/octet-stream")}
        
        response = client.post("/api/v1/decompile", files=files, data=params)
    
    assert response.status_code == 202, f"Job submission failed: {response.text}"
    
    job_data = response.json()
    return job_data["job_id"]

# Test data validation
@pytest.fixture(autouse=True)
def verify_server_running(client):
    """Verify API server is running before each test"""
    try:
        response = client.get("/api/v1/health/live")
        if response.status_code != 200:
            pytest.skip("API server is not running or not ready")
    except:
        pytest.skip("Cannot connect to API server")
```

#### `tests/uat/utils/api_client.py` - Enhanced API Client
```python
"""
Enhanced API Client with UAT-specific functionality
"""
import requests
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class TestResult:
    """Test result data structure"""
    success: bool
    response: requests.Response
    duration_seconds: float
    error_message: Optional[str] = None

class UATAPIClient:
    """Enhanced API client for comprehensive UAT testing"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results: List[TestResult] = []
    
    def execute_test_scenario(self, 
                            method: str, 
                            path: str, 
                            expected_status: int = 200,
                            **kwargs) -> TestResult:
        """Execute test scenario with timing and result tracking"""
        start_time = time.time()
        
        try:
            response = self.session.request(method, f"{self.base_url}{path}", **kwargs)
            duration = time.time() - start_time
            
            success = response.status_code == expected_status
            error_msg = None if success else f"Expected {expected_status}, got {response.status_code}"
            
            result = TestResult(
                success=success,
                response=response,
                duration_seconds=duration,
                error_message=error_msg
            )
            
            self.test_results.append(result)
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            
            result = TestResult(
                success=False,
                response=None,
                duration_seconds=duration,
                error_message=str(e)
            )
            
            self.test_results.append(result)
            return result
    
    def validate_response_schema(self, response: requests.Response, required_fields: List[str]) -> bool:
        """Validate response contains required fields"""
        try:
            data = response.json()
            return all(field in data for field in required_fields)
        except:
            return False
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of all executed tests"""
        if not self.test_results:
            return {}
        
        durations = [r.duration_seconds for r in self.test_results]
        successes = sum(1 for r in self.test_results if r.success)
        
        return {
            "total_tests": len(self.test_results),
            "successful_tests": successes,
            "success_rate": successes / len(self.test_results),
            "avg_response_time": sum(durations) / len(durations),
            "min_response_time": min(durations),
            "max_response_time": max(durations),
            "failed_tests": [r.error_message for r in self.test_results if not r.success]
        }
```

#### `tests/uat/utils/test_data.py` - Test Data Management
```python
"""
Test Data Management and Validation
"""
import os
import hashlib
from typing import Dict, List, Any

class TestDataManager:
    """Manages test binary files and expected responses"""
    
    def __init__(self, data_dir: str = "tests/uat/data"):
        self.data_dir = data_dir
        self.binaries_dir = os.path.join(data_dir, "test_binaries")
        self.expected_dir = os.path.join(data_dir, "expected_responses")
    
    def get_test_binaries(self) -> Dict[str, Dict[str, Any]]:
        """Get information about available test binaries"""
        binaries = {}
        
        if not os.path.exists(self.binaries_dir):
            return binaries
        
        for filename in os.listdir(self.binaries_dir):
            file_path = os.path.join(self.binaries_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                
                with open(file_path, "rb") as f:
                    content_hash = hashlib.sha256(f.read()).hexdigest()
                
                binaries[filename] = {
                    "path": file_path,
                    "size_bytes": stat.st_size,
                    "size_category": self._categorize_file_size(stat.st_size),
                    "sha256": content_hash
                }
        
        return binaries
    
    def _categorize_file_size(self, size_bytes: int) -> str:
        """Categorize file size according to PRD performance requirements"""
        mb = size_bytes / (1024 * 1024)
        
        if mb <= 10:
            return "small"  # ≤10MB: 30 seconds max
        elif mb <= 30:
            return "medium"  # ≤30MB: 5 minutes max
        elif mb <= 100:
            return "large"   # ≤100MB: 20 minutes max
        else:
            return "oversized"  # >100MB: should be rejected
    
    def get_performance_expectations(self, filename: str) -> Dict[str, Any]:
        """Get performance expectations for a test file"""
        binaries = self.get_test_binaries()
        
        if filename not in binaries:
            return {}
        
        binary_info = binaries[filename]
        category = binary_info["size_category"]
        
        expectations = {
            "small": {"max_time_seconds": 30, "description": "Small file (≤10MB)"},
            "medium": {"max_time_seconds": 300, "description": "Medium file (≤30MB)"},
            "large": {"max_time_seconds": 1200, "description": "Large file (≤100MB)"},
            "oversized": {"should_reject": True, "description": "Oversized file (>100MB)"}
        }
        
        return expectations.get(category, {})

# Test parameter combinations for comprehensive testing
TEST_PARAMETER_COMBINATIONS = [
    # Minimal parameters
    {},
    
    # Analysis depth variations
    {"analysis_depth": "basic"},
    {"analysis_depth": "standard"},  
    {"analysis_depth": "comprehensive"},
    
    # LLM provider variations
    {"llm_provider": "openai"},
    {"llm_provider": "anthropic"},
    {"llm_provider": "gemini"},
    {"llm_provider": "ollama"},
    
    # Translation detail variations
    {"translation_detail": "basic"},
    {"translation_detail": "standard"},
    {"translation_detail": "detailed"},
    
    # Comprehensive combinations
    {"analysis_depth": "comprehensive", "llm_provider": "openai", "translation_detail": "detailed"},
    {"analysis_depth": "standard", "llm_provider": "anthropic", "translation_detail": "standard"},
    {"analysis_depth": "basic", "llm_provider": "ollama", "translation_detail": "basic"},
]

# Expected response schemas for validation
EXPECTED_SCHEMAS = {
    "health_check": ["status", "timestamp", "components", "version"],
    "system_info": ["supported_formats", "max_file_size_mb", "analysis_depths", "llm_providers"],
    "job_submission": ["success", "job_id", "status", "message", "file_info", "config"],
    "job_status": ["job_id", "status", "progress_percentage", "current_stage", "updated_at"],
    "job_results": ["job_id", "status", "results", "message"],
    "llm_providers": ["providers", "total_providers"],
    "api_key_creation": ["success", "api_key", "key_info"],
}
```

## 📈 Performance Validation Framework

### `tests/uat/utils/performance.py` - Performance Testing
```python
"""
Performance Validation Utilities
"""
import time
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class PerformanceMetrics:
    """Performance metrics for test validation"""
    operation: str
    duration_seconds: float
    success: bool
    expected_max_duration: float
    file_size_bytes: int
    meets_requirements: bool

class PerformanceValidator:
    """Validates system performance against PRD requirements"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        
        # PRD performance requirements
        self.requirements = {
            "api_response": 2.0,      # API responses < 2 seconds
            "small_file": 30.0,       # ≤10MB files < 30 seconds
            "medium_file": 300.0,     # ≤30MB files < 5 minutes  
            "large_file": 1200.0,     # ≤100MB files < 20 minutes
        }
    
    def measure_operation(self, operation: str, expected_max: float, file_size: int = 0):
        """Context manager to measure operation performance"""
        return PerformanceMeasurement(self, operation, expected_max, file_size)
    
    def add_metric(self, metric: PerformanceMetrics):
        """Add performance metric"""
        self.metrics.append(metric)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance validation report"""
        if not self.metrics:
            return {"status": "no_data"}
        
        total_tests = len(self.metrics)
        successful_tests = sum(1 for m in self.metrics if m.success)
        meeting_requirements = sum(1 for m in self.metrics if m.meets_requirements)
        
        # Group by operation type
        by_operation = {}
        for metric in self.metrics:
            if metric.operation not in by_operation:
                by_operation[metric.operation] = []
            by_operation[metric.operation].append(metric)
        
        operation_summaries = {}
        for op_name, op_metrics in by_operation.items():
            durations = [m.duration_seconds for m in op_metrics]
            operation_summaries[op_name] = {
                "total_tests": len(op_metrics),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "meets_requirements": sum(1 for m in op_metrics if m.meets_requirements),
                "success_rate": sum(1 for m in op_metrics if m.success) / len(op_metrics)
            }
        
        return {
            "status": "complete",
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": successful_tests / total_tests,
                "meeting_requirements": meeting_requirements,
                "performance_compliance": meeting_requirements / total_tests
            },
            "operations": operation_summaries,
            "failed_requirements": [
                {
                    "operation": m.operation,
                    "duration": m.duration_seconds,
                    "expected_max": m.expected_max_duration,
                    "file_size_mb": m.file_size_bytes / (1024*1024)
                }
                for m in self.metrics if not m.meets_requirements
            ]
        }

class PerformanceMeasurement:
    """Context manager for measuring operation performance"""
    
    def __init__(self, validator: PerformanceValidator, operation: str, expected_max: float, file_size: int):
        self.validator = validator
        self.operation = operation
        self.expected_max = expected_max
        self.file_size = file_size
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        success = exc_type is None
        meets_requirements = success and duration <= self.expected_max
        
        metric = PerformanceMetrics(
            operation=self.operation,
            duration_seconds=duration,
            success=success,
            expected_max_duration=self.expected_max,
            file_size_bytes=self.file_size,
            meets_requirements=meets_requirements
        )
        
        self.validator.add_metric(metric)
```

## 🎯 Test Execution Plan

### Execution Phases

**Phase 1: Infrastructure Validation (15 minutes)**
- Health checks and system info endpoints
- Basic connectivity and authentication

**Phase 2: Core Functionality Testing (45 minutes)**  
- Decompilation workflow with various parameters
- LLM provider integration testing
- Error handling validation

**Phase 3: Admin & Monitoring Testing (30 minutes)**
- API key management
- System metrics and monitoring
- Circuit breaker functionality

**Phase 4: Performance Validation (60 minutes)**
- Performance requirements testing with different file sizes
- Concurrent job processing
- Load testing scenarios

**Phase 5: End-to-End Integration (30 minutes)**
- Complete user journeys
- Multi-provider failover testing
- System stress testing

### Command Line Execution

```bash
# Install dependencies
pip install pytest requests

# Run all UAT tests
pytest tests/uat/ -v --tb=short

# Run specific test categories
pytest tests/uat/test_01_health_system.py -v
pytest tests/uat/test_02_decompilation_core.py -v
pytest tests/uat/test_99_end_to_end.py -v

# Run performance validation only
pytest tests/uat/ -v -k "performance"

# Generate detailed report
pytest tests/uat/ -v --tb=long --html=uat_report.html
```

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Analyze result storage mechanism in the codebase", "status": "completed"}, {"content": "Fetch and analyze API documentation from http://localhost:8000/docs", "status": "completed"}, {"content": "Review !xcc/ project documentation files for requirements", "status": "completed"}, {"content": "Map all API routes and their parameters from code", "status": "completed"}, {"content": "Create comprehensive UAT test plan covering all routes and features", "status": "completed"}, {"content": "Design automated test execution approach", "status": "completed"}]