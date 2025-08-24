# Redis Removal & Analysis Structure Cleanup Tasks

## 🎯 **Objective**
Remove Redis dependencies and collapse "analysis" structure into "decompilation" structure to simplify architecture and improve deployment reliability.

## 📊 **REDIS REMOVAL TASKS**

### **Configuration Files**
- [ ] **Task R01**: Remove Redis from `docker-compose.yml`
  - File: `/home/sean/app/bin2nlp/docker-compose.yml`
  - Remove: Redis service, networks, volumes
  
- [ ] **Task R02**: Remove Redis from `.env` file
  - File: `/home/sean/app/bin2nlp/.env`  
  - Remove: All REDIS_* environment variables
  
- [ ] **Task R03**: Remove Redis configuration file
  - File: `/home/sean/app/bin2nlp/config/redis.conf`
  - Action: Delete entire file
  
- [ ] **Task R04**: Remove Redis from Kubernetes deployment
  - File: `/home/sean/app/bin2nlp/k8s-deployment.yaml`
  - Remove: Redis deployment, service, config references

### **Core Source Files - Cache Module (Replace with File Storage)**
- [ ] **Task R05**: Replace `src/cache/base.py` 
  - File: `/home/sean/app/bin2nlp/src/cache/base.py`
  - Action: Replace RedisClient with FileStorage equivalent
  
- [ ] **Task R06**: Replace `src/cache/result_cache.py`
  - File: `/home/sean/app/bin2nlp/src/cache/result_cache.py` 
  - Action: Replace Redis result caching with file-based storage
  
- [ ] **Task R07**: Replace `src/cache/job_queue.py`
  - File: `/home/sean/app/bin2nlp/src/cache/job_queue.py`
  - Action: Replace Redis job queue with file-based queue
  
- [ ] **Task R08**: Replace `src/cache/session.py`  
  - File: `/home/sean/app/bin2nlp/src/cache/session.py`
  - Action: Replace Redis sessions with file-based sessions
  
- [ ] **Task R09**: Replace `src/cache/rate_limiter.py`
  - File: `/home/sean/app/bin2nlp/src/cache/rate_limiter.py` 
  - Action: Replace Redis rate limiting with file-based counters
  
- [ ] **Task R10**: Update `src/cache/__init__.py`
  - File: `/home/sean/app/bin2nlp/src/cache/__init__.py`
  - Action: Update exports to use file storage classes

### **Core Source Files - Configuration & Exceptions**
- [ ] **Task R11**: Remove Redis from `src/core/config.py`
  - File: `/home/sean/app/bin2nlp/src/core/config.py`
  - Remove: Redis configuration classes, connection settings
  
- [ ] **Task R12**: Remove Redis exceptions from `src/core/exceptions.py`
  - File: `/home/sean/app/bin2nlp/src/core/exceptions.py`
  - Remove: CacheException, CacheConnectionError, CacheTimeoutError
  
- [ ] **Task R13**: Update `src/core/config_validation.py`
  - File: `/home/sean/app/bin2nlp/src/core/config_validation.py`  
  - Remove: Redis configuration validation

### **API Layer**
- [ ] **Task R14**: Update `src/api/main.py`
  - File: `/home/sean/app/bin2nlp/src/api/main.py`
  - Remove: Redis client initialization, lifespan events
  
- [ ] **Task R15**: Update `src/api/routes/decompilation.py`
  - File: `/home/sean/app/bin2nlp/src/api/routes/decompilation.py`
  - Replace: Redis result storage with file storage (lines 155-162)
  
- [ ] **Task R16**: Update `src/api/routes/admin.py`
  - File: `/home/sean/app/bin2nlp/src/api/routes/admin.py`
  - Replace: Redis health checks and admin operations
  
- [ ] **Task R17**: Update `src/api/routes/health.py`  
  - File: `/home/sean/app/bin2nlp/src/api/routes/health.py`
  - Remove: Redis health check components
  
- [ ] **Task R18**: Update `src/api/middleware/auth.py`
  - File: `/home/sean/app/bin2nlp/src/api/middleware/auth.py`  
  - Replace: Redis-based API key storage with file-based
  
- [ ] **Task R19**: Update `src/api/middleware/rate_limiting.py`
  - File: `/home/sean/app/bin2nlp/src/api/middleware/rate_limiting.py`
  - Replace: Redis rate limiting with file-based counters

### **CLI Tools** 
- [ ] **Task R20**: Update `src/cli/admin.py`
  - File: `/home/sean/app/bin2nlp/src/cli/admin.py`
  - Replace: Redis admin commands with file storage equivalents
  
- [ ] **Task R21**: Update `src/cli.py`
  - File: `/home/sean/app/bin2nlp/src/cli.py`  
  - Remove: Redis CLI integration

### **Dependencies**
- [ ] **Task R22**: Update `requirements.txt`
  - File: `/home/sean/app/bin2nlp/requirements.txt`
  - Remove: redis, redis[hiredis] dependencies
  
- [ ] **Task R23**: Update `pyproject.toml` 
  - File: `/home/sean/app/bin2nlp/pyproject.toml`
  - Remove: Redis dependencies if present

## 📊 **ANALYSIS STRUCTURE COLLAPSE TASKS**

### **Remove Analysis Module Entirely**
- [ ] **Task A01**: Delete `src/analysis/` directory
  - Directory: `/home/sean/app/bin2nlp/src/analysis/`
  - Files to delete:
    - `src/analysis/__init__.py`
    - `src/analysis/engines/__init__.py` 
    - `src/analysis/engines/base.py`
    - `src/analysis/workers/__init__.py`
    - `src/analysis/error_recovery.py`

### **Remove Analysis Models**  
- [ ] **Task A02**: Delete `src/models/analysis/` directory
  - Directory: `/home/sean/app/bin2nlp/src/models/analysis/`
  - Files to delete:
    - `src/models/analysis/__init__.py`
    - `src/models/analysis/basic_results.py` 
    - `src/models/analysis/config.py`
    - `src/models/analysis/files.py`
    - `src/models/analysis/results.py`
    - `src/models/analysis/serialization.py`

### **Update Import References**
- [ ] **Task A03**: Update imports in decompilation module
  - Files: `src/decompilation/engine.py`, `src/decompilation/r2_session.py`
  - Action: Remove analysis imports, use decompilation models directly
  
- [ ] **Task A04**: Update imports in LLM module  
  - Files: All files in `src/llm/` directory
  - Action: Replace analysis model imports with decompilation models
  
- [ ] **Task A05**: Update imports in API routes
  - Files: `src/api/routes/decompilation.py`, others as needed
  - Action: Replace analysis imports with decompilation equivalents

### **Update API Models**
- [ ] **Task A06**: Update `src/models/api/decompilation.py`
  - File: `/home/sean/app/bin2nlp/src/models/api/decompilation.py`
  - Remove: Analysis model references, use decompilation models only
  
- [ ] **Task A07**: Update `src/models/api/jobs.py`  
  - File: `/home/sean/app/bin2nlp/src/models/api/jobs.py`
  - Remove: Analysis job types, keep decompilation job types only

## 📊 **TEST CLEANUP TASKS**

### **Remove Redis Tests**
- [ ] **Task T01**: Delete Redis integration tests
  - File: `/home/sean/app/bin2nlp/tests/integration/test_redis_integration.py`
  - Action: Delete entire file
  
- [ ] **Task T02**: Delete Redis unit tests
  - Files: All files in `/home/sean/app/bin2nlp/tests/unit/cache/`
  - Files to delete:
    - `test_base.py`
    - `test_rate_limiter.py` 
    - `test_result_cache.py`
    - `test_job_queue.py`
    - `test_session.py`

### **Remove Analysis Tests**  
- [ ] **Task T03**: Delete analysis integration tests
  - File: `/home/sean/app/bin2nlp/tests/integration/test_analysis_engine.py`
  - Action: Delete entire file
  
- [ ] **Task T04**: Update other integration tests
  - Files: `test_api_integration.py`, `test_end_to_end_production.py`, etc.
  - Remove: Analysis test cases, keep decompilation tests
  
- [ ] **Task T05**: Update UAT tests
  - Files: `tests/uat/test_04_admin_auth.py`, `test_01_health_system.py`  
  - Remove: Redis health checks, analysis test cases

### **Update Test Fixtures**
- [ ] **Task T06**: Update test fixtures
  - Files: `tests/fixtures/test_binaries.py`, `tests/fixtures/llm_responses.py`
  - Remove: Analysis-specific fixtures, keep decompilation fixtures

## 📊 **DOCUMENTATION CLEANUP TASKS**

### **Update Core Documentation**
- [ ] **Task D01**: Update `CLAUDE.md`  
  - File: `/home/sean/app/bin2nlp/CLAUDE.md`
  - Remove: Redis references, analysis structure references
  - Update: Technology stack to show file-based storage
  
- [ ] **Task D02**: Update `README.md`
  - File: `/home/sean/app/bin2nlp/README.md` 
  - Remove: Redis setup instructions, analysis references
  - Update: Deployment to single-container setup
  
- [ ] **Task D03**: Update deployment documentation
  - Files: `DEPLOYMENT.md`, `docs/deployment.md`, `docs/DOCKER_DEPLOYMENT.md`
  - Remove: Redis deployment steps, multi-container instructions
  - Update: Single-container deployment process

### **Update Technical Documentation**  
- [ ] **Task D04**: Update architecture documents  
  - Files: `0xcc/adrs/000_PADR|bin2nlp.md`, `0xcc/tdds/001_FTDD|Phase1_Integrated_System.md`
  - Remove: Redis architecture decisions, analysis module designs
  - Update: File storage architecture decisions
  
- [ ] **Task D05**: Update PRDs and task documents
  - Files: All files in `0xcc/prds/`, `0xcc/tasks/`, `0xcc/tids/`
  - Remove: Redis requirements, analysis structure references
  - Update: File storage requirements

### **Update Operational Documentation**
- [ ] **Task D06**: Update runbooks
  - File: `/home/sean/app/bin2nlp/docs/runbooks.md` 
  - Remove: Redis operational procedures
  - Update: File storage operational procedures
  
- [ ] **Task D07**: Update troubleshooting guide
  - File: `/home/sean/app/bin2nlp/docs/troubleshooting.md`
  - Remove: Redis troubleshooting sections  
  - Update: File storage troubleshooting
  
- [ ] **Task D08**: Update API documentation
  - File: `/home/sean/app/bin2nlp/docs/API_USAGE_EXAMPLES.md`
  - Remove: Analysis API examples
  - Keep: Only decompilation API examples

## 📊 **SCRIPT & DEPLOYMENT CLEANUP**

### **Update Deployment Scripts**
- [ ] **Task S01**: Update deployment scripts
  - Files: `scripts/deploy.sh`, `scripts/docker-utils.sh`, `scripts/test-deployment.sh`  
  - Remove: Redis deployment commands, multi-container orchestration
  - Update: Single-container deployment commands
  
### **Update OpenAPI Specification**  
- [ ] **Task S02**: Update OpenAPI spec
  - File: `/home/sean/app/bin2nlp/docs/openapi_comprehensive.json`
  - Remove: Analysis endpoints, Redis health endpoints
  - Keep: Only decompilation endpoints

## 📊 **VALIDATION TASKS**

### **Verify Cleanup Completion**
- [ ] **Task V01**: Search for remaining Redis references
  - Action: `grep -r -i redis /home/sean/app/bin2nlp/src/`
  - Expected: No results
  
- [ ] **Task V02**: Search for remaining analysis references  
  - Action: `grep -r -i "analysis" /home/sean/app/bin2nlp/src/ | grep -v comment`
  - Expected: Only documentation comments
  
- [ ] **Task V03**: Verify imports
  - Action: Check all Python files import successfully
  - Command: `python -m py_compile src/**/*.py`
  
- [ ] **Task V04**: Run tests with new structure
  - Action: `pytest tests/unit/ -v`
  - Expected: All tests pass with file storage
  
- [ ] **Task V05**: Test deployment  
  - Action: `docker-compose up --build`
  - Expected: Single container starts successfully

## 📋 **EXECUTION ORDER**

1. **Phase 1: Redis Removal** (Tasks R01-R23)
2. **Phase 2: Analysis Structure Collapse** (Tasks A01-A07)  
3. **Phase 3: Test Cleanup** (Tasks T01-T06)
4. **Phase 4: Documentation Update** (Tasks D01-D08)
5. **Phase 5: Scripts & Deployment** (Tasks S01-S02)
6. **Phase 6: Validation** (Tasks V01-V05)

## 📊 **SUCCESS CRITERIA**

- ✅ Zero Redis dependencies in codebase
- ✅ No analysis module references  
- ✅ Single-container deployment working
- ✅ File-based storage fully functional
- ✅ All tests passing
- ✅ Documentation updated and consistent
- ✅ Deployment simplified and reliable