# bin2nlp Troubleshooting Guide

## Overview

This comprehensive troubleshooting guide covers common issues, known problems, and their solutions for the bin2nlp Binary Decompilation & LLM Translation Service. Issues are organized by category with step-by-step diagnostic and resolution procedures.

## Table of Contents

- [Quick Diagnostic Commands](#quick-diagnostic-commands)
- [Service Startup Issues](#service-startup-issues)
- [API Connectivity Issues](#api-connectivity-issues)
- [LLM Provider Problems](#llm-provider-problems)
- [Performance Issues](#performance-issues)
- [Redis/Cache Issues](#rediscache-issues)
- [File Upload Issues](#file-upload-issues)
- [Authentication Problems](#authentication-problems)
- [Docker and Container Issues](#docker-and-container-issues)
- [Configuration Issues](#configuration-issues)
- [Known Issues and Limitations](#known-issues-and-limitations)
- [Error Code Reference](#error-code-reference)
- [Log Analysis Guide](#log-analysis-guide)

---

## Quick Diagnostic Commands

### System Health Check

```bash
# Quick system status
curl -f https://api.bin2nlp.com/health || echo "Service unreachable"

# Detailed health with components
curl -H "Authorization: Bearer $API_KEY" \
     https://api.bin2nlp.com/health/detailed | jq .

# Docker container status
docker-compose ps

# Service logs (last 50 lines)
docker-compose logs --tail=50
```

### Performance Check

```bash
# Response time test
time curl -f https://api.bin2nlp.com/health

# Resource usage
docker stats --no-stream

# Current metrics snapshot
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/metrics/current | jq .
```

---

## Service Startup Issues

### Issue: Service Fails to Start

**Symptoms:**
- `docker-compose up` fails
- Containers exit immediately
- "Service unavailable" errors

#### Diagnostic Steps

1. **Check Container Status:**
```bash
docker-compose ps
docker-compose logs api
```

2. **Check Port Conflicts:**
```bash
sudo netstat -tulpn | grep :8000
sudo netstat -tulpn | grep :6379
```

3. **Validate Configuration:**
```bash
# Check environment variables
docker-compose config

# Validate environment file
cat .env | grep -v '^#' | grep -v '^$'
```

#### Common Causes and Solutions

**Missing Environment Variables:**
```bash
# Ensure all required variables are set
cp .env.example .env
nano .env  # Set all required values

# Verify critical variables
echo "Required variables:"
echo "REDIS_URL: $REDIS_URL"
echo "LLM_OPENAI_API_KEY: ${LLM_OPENAI_API_KEY:0:10}..."
```

**Port Already in Use:**
```bash
# Kill process using port 8000
sudo fuser -k 8000/tcp

# Or change port in docker-compose.yml
ports:
  - "8080:8000"  # Use port 8080 instead
```

**Redis Connection Failed:**
```bash
# Start Redis first
docker-compose up redis -d

# Check Redis connectivity
docker-compose exec redis redis-cli ping

# Check Redis logs
docker-compose logs redis
```

### Issue: Application Starts but Crashes

**Symptoms:**
- Container starts then exits
- Memory errors in logs
- Import errors

#### Diagnostic Steps

1. **Check Application Logs:**
```bash
docker-compose logs api --tail=100
```

2. **Check Resource Limits:**
```bash
docker stats
free -h
df -h
```

3. **Test Dependencies:**
```bash
# Test Python imports
docker-compose exec api python -c "import src.api.main"

# Test Redis connection
docker-compose exec api python -c "from src.cache.base import get_redis_client; import asyncio; asyncio.run(get_redis_client().ping())"
```

#### Solutions

**Memory Issues:**
```bash
# Increase memory limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 2G  # Increase from 1G
```

**Missing Dependencies:**
```bash
# Rebuild container with dependencies
docker-compose build --no-cache api
```

**Python Import Errors:**
```bash
# Check Python path and file permissions
docker-compose exec api ls -la /app/src/
docker-compose exec api python -c "import sys; print(sys.path)"
```

---

## API Connectivity Issues

### Issue: HTTP 502 Bad Gateway

**Symptoms:**
- Nginx returns 502 errors
- API not responding to requests
- Gateway timeouts

#### Diagnostic Steps

1. **Check API Service:**
```bash
# Test API directly (bypass Nginx)
curl http://localhost:8000/health

# Check API logs
docker-compose logs api --tail=50
```

2. **Check Nginx Configuration:**
```bash
# Test Nginx config
sudo nginx -t

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log

# Check upstream status
curl -I http://localhost:8000/health
```

#### Solutions

**API Service Down:**
```bash
# Restart API service
docker-compose restart api

# Check for resource exhaustion
docker stats api
```

**Nginx Configuration Issues:**
```bash
# Verify upstream configuration in nginx.conf
upstream bin2nlp_backend {
    server 127.0.0.1:8000;  # Ensure correct port
}

# Reload Nginx
sudo systemctl reload nginx
```

### Issue: HTTP 504 Gateway Timeout

**Symptoms:**
- Requests timeout after 60+ seconds
- Large file uploads fail
- Complex decompilation timeouts

#### Diagnostic Steps

1. **Check Timeout Settings:**
```bash
# Check API timeout configuration
grep -i timeout .env

# Check Nginx timeout settings
grep -i timeout /etc/nginx/sites-available/bin2nlp
```

2. **Monitor Request Processing:**
```bash
# Watch API logs during request
docker-compose logs -f api &
curl -X POST -F "file=@large_binary.exe" https://api.bin2nlp.com/api/v1/analyze
```

#### Solutions

**Increase Timeout Values:**
```bash
# API timeouts (in .env)
DEFAULT_TIMEOUT_SECONDS=1200  # 20 minutes
MAX_TIMEOUT_SECONDS=3600      # 1 hour

# Nginx timeouts
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
```

**Optimize Processing:**
```bash
# Enable background processing for large files
ENABLE_BACKGROUND_PROCESSING=true
BACKGROUND_PROCESS_THRESHOLD_MB=50
```

---

## LLM Provider Problems

### Issue: LLM Provider API Failures

**Symptoms:**
- "LLM provider unavailable" errors
- Circuit breaker open warnings
- Translation failures

#### Diagnostic Steps

1. **Check Provider Status:**
```bash
# Check all providers
curl -H "Authorization: Bearer $API_KEY" \
     https://api.bin2nlp.com/llm/providers/health | jq .

# Check specific provider
curl -H "Authorization: Bearer $API_KEY" \
     https://api.bin2nlp.com/llm/providers/openai/health | jq .
```

2. **Test API Keys Directly:**
```bash
# Test OpenAI key
curl -H "Authorization: Bearer $LLM_OPENAI_API_KEY" \
     https://api.openai.com/v1/models

# Test Anthropic key
curl -H "x-api-key: $LLM_ANTHROPIC_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"claude-3-haiku-20240307","max_tokens":10,"messages":[{"role":"user","content":"test"}]}' \
     https://api.anthropic.com/v1/messages
```

3. **Check Circuit Breakers:**
```bash
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers | jq .
```

#### Solutions

**Invalid API Keys:**
```bash
# Regenerate API keys from provider dashboards
# Update environment variables
nano .env
docker-compose restart api
```

**Rate Limiting:**
```bash
# Check rate limit status
curl -I -H "Authorization: Bearer $LLM_OPENAI_API_KEY" \
     https://api.openai.com/v1/models

# Reduce request rate
LLM_OPENAI_REQUESTS_PER_MINUTE=30  # Reduce from 60
docker-compose restart api
```

**Circuit Breaker Stuck Open:**
```bash
# Reset circuit breaker
curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/openai/reset

# Monitor for re-opening
watch -n 10 'curl -s -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/openai | jq .state'
```

### Issue: Poor Translation Quality

**Symptoms:**
- Nonsensical translations
- Incomplete responses
- Inconsistent results

#### Diagnostic Steps

1. **Check Model Configuration:**
```bash
# Review current model settings
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/config | jq '.llm'
```

2. **Test Different Providers:**
```bash
# Test with different providers
curl -X POST -H "Authorization: Bearer $API_KEY" \
     -d '{"provider":"openai","text":"test"}' \
     https://api.bin2nlp.com/api/v1/llm/translate

curl -X POST -H "Authorization: Bearer $API_KEY" \
     -d '{"provider":"anthropic","text":"test"}' \
     https://api.bin2nlp.com/api/v1/llm/translate
```

#### Solutions

**Optimize Model Settings:**
```bash
# Use higher-quality models
LLM_OPENAI_MODEL=gpt-4           # Instead of gpt-3.5-turbo
LLM_ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Adjust temperature for consistency
LLM_OPENAI_TEMPERATURE=0.1       # Lower for more consistent results
```

**Improve Prompts:**
```bash
# Enable verbose prompting
LLM_VERBOSE_PROMPTS=true
LLM_INCLUDE_CONTEXT=true
```

---

## Performance Issues

### Issue: Slow Response Times

**Symptoms:**
- API responses > 30 seconds
- User complaints about slowness
- Timeout errors

#### Diagnostic Steps

1. **Check Response Times:**
```bash
# Measure API response time
time curl https://api.bin2nlp.com/health

# Check performance metrics
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     "https://api.bin2nlp.com/api/v1/admin/metrics/performance?time_window_minutes=60" | jq .
```

2. **Check System Resources:**
```bash
docker stats --no-stream
htop
iostat 1 5
```

3. **Analyze Bottlenecks:**
```bash
# Check decompilation performance
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/metrics/decompilation | jq .

# Check LLM performance  
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/metrics/llm | jq .
```

#### Solutions

**Scale Resources:**
```bash
# Increase API workers
API_WORKERS=8  # Increase from 4

# Increase container resources
deploy:
  resources:
    limits:
      cpus: '4.0'    # Increase from 2.0
      memory: 4G     # Increase from 2G
```

**Optimize Configuration:**
```bash
# Use faster models for simple tasks
LLM_OPENAI_MODEL=gpt-3.5-turbo  # Faster than gpt-4

# Reduce token limits
LLM_OPENAI_MAX_TOKENS=1024      # Reduce from 2048

# Enable caching
ENABLE_RESPONSE_CACHING=true
CACHE_TTL_SECONDS=3600
```

**Database Optimization:**
```bash
# Optimize Redis
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG SET tcp-keepalive 60
```

### Issue: High Memory Usage

**Symptoms:**
- OOM (Out of Memory) kills
- Memory usage > 90%
- Swap usage high

#### Diagnostic Steps

1. **Check Memory Usage:**
```bash
free -h
cat /proc/meminfo
docker stats --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}"
```

2. **Analyze Memory Patterns:**
```bash
# Check for memory leaks in logs
docker-compose logs api | grep -i "memory\|oom"

# Monitor memory over time
watch -n 5 'docker stats --no-stream api'
```

#### Solutions

**Increase Memory Limits:**
```bash
# Increase container memory
deploy:
  resources:
    limits:
      memory: 4G  # Increase from 2G

# Add swap if needed
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**Optimize Memory Usage:**
```bash
# Reduce worker processes
API_WORKERS=2  # Reduce if memory-bound

# Enable garbage collection optimization
PYTHON_GC_OPTIMIZATION=true

# Clear Redis cache periodically
redis-cli FLUSHDB
```

---

## Redis/Cache Issues

### Issue: Redis Connection Failures

**Symptoms:**
- "Redis connection failed" errors
- Cache misses increase
- Performance degradation

#### Diagnostic Steps

1. **Test Redis Connectivity:**
```bash
# Test from host
redis-cli -h localhost -p 6379 ping

# Test from container
docker-compose exec api redis-cli -h redis -p 6379 ping

# Check Redis status
docker-compose ps redis
docker-compose logs redis
```

2. **Check Network Configuration:**
```bash
# Check Docker network
docker network ls
docker network inspect $(docker-compose ps -q redis | head -1)

# Test network connectivity
docker-compose exec api ping redis
```

#### Solutions

**Restart Redis:**
```bash
docker-compose restart redis

# If Redis container won't start
docker-compose stop redis
docker-compose rm redis
docker-compose up -d redis
```

**Fix Network Issues:**
```bash
# Recreate network
docker-compose down
docker-compose up -d
```

**Check Configuration:**
```bash
# Verify Redis URL in environment
echo $REDIS_URL

# Test Redis authentication
redis-cli -h localhost -p 6379 -a $REDIS_PASSWORD ping
```

### Issue: Redis Memory Problems

**Symptoms:**
- Redis memory warnings
- Evicted keys in logs
- Cache performance degradation

#### Diagnostic Steps

1. **Check Memory Usage:**
```bash
redis-cli info memory
redis-cli config get maxmemory
redis-cli info stats | grep evicted
```

2. **Analyze Key Distribution:**
```bash
redis-cli --bigkeys
redis-cli dbsize
redis-cli info keyspace
```

#### Solutions

**Increase Memory:**
```bash
# Set higher memory limit
redis-cli config set maxmemory 1gb

# Or update docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
```

**Optimize Memory Usage:**
```bash
# Better eviction policy
redis-cli config set maxmemory-policy allkeys-lru

# Reduce TTL for cache entries
DEFAULT_TTL_SECONDS=1800  # 30 minutes instead of 1 hour
```

---

## File Upload Issues

### Issue: File Upload Fails

**Symptoms:**
- HTTP 413 "Request Entity Too Large"
- Upload timeouts
- File corruption errors

#### Diagnostic Steps

1. **Check File Size Limits:**
```bash
# Check application limits
grep MAX_FILE_SIZE .env

# Check Nginx limits
grep client_max_body_size /etc/nginx/sites-available/bin2nlp
```

2. **Test Upload Process:**
```bash
# Test small file
curl -X POST -F "file=@small_test.exe" \
     -H "Authorization: Bearer $API_KEY" \
     https://api.bin2nlp.com/api/v1/analyze

# Check upload logs
docker-compose logs api | grep -i upload
```

#### Solutions

**Increase Size Limits:**
```bash
# Application limit
MAX_FILE_SIZE_MB=500  # Increase from 100

# Nginx limit
client_max_body_size 500M;

# Restart services
docker-compose restart api
sudo systemctl reload nginx
```

**Optimize Upload Handling:**
```bash
# Enable streaming uploads
ENABLE_STREAMING_UPLOAD=true

# Increase timeout for large files
UPLOAD_TIMEOUT_SECONDS=1800  # 30 minutes
```

### Issue: File Format Not Supported

**Symptoms:**
- "Unsupported file format" errors
- File type detection fails
- Analysis returns empty results

#### Diagnostic Steps

1. **Check Supported Formats:**
```bash
curl -H "Authorization: Bearer $API_KEY" \
     https://api.bin2nlp.com/api/v1/supported-formats | jq .
```

2. **Test File Detection:**
```bash
# Check file type with system tools
file your_binary.exe
hexdump -C your_binary.exe | head -5

# Test with Magika (if available)
python -c "from magika import Magika; m = Magika(); print(m.identify_path('your_binary.exe'))"
```

#### Solutions

**Add Format Support:**
```bash
# Add format to supported list
SUPPORTED_FORMATS=["pe", "elf", "macho", "java", "dotnet"]

# Update file detection
ENABLE_EXTENDED_FORMAT_DETECTION=true
```

**Manual Format Override:**
```bash
# Force format in API request
curl -X POST -F "file=@binary.exe" \
     -F "format=pe" \
     -H "Authorization: Bearer $API_KEY" \
     https://api.bin2nlp.com/api/v1/analyze
```

---

## Authentication Problems

### Issue: API Key Authentication Fails

**Symptoms:**
- HTTP 401 "Unauthorized" errors
- "Invalid API key" messages
- Authentication headers rejected

#### Diagnostic Steps

1. **Verify API Key Format:**
```bash
# Check key format
echo $API_KEY | wc -c  # Should be appropriate length

# Test key with admin endpoint
curl -H "Authorization: Bearer $API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/api-keys/validate
```

2. **Check Key Status:**
```bash
# List keys (admin only)
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/api-keys/all | jq .
```

#### Solutions

**Generate New API Key:**
```bash
# For development (if debug mode enabled)
curl -X POST https://api.bin2nlp.com/api/v1/admin/dev/create-api-key

# For production (admin required)
curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"user_id":"your_user","tier":"standard"}' \
     https://api.bin2nlp.com/api/v1/admin/api-keys
```

**Fix Header Format:**
```bash
# Correct format
Authorization: Bearer your-api-key-here

# Not: 
Authorization: your-api-key-here  # Missing "Bearer"
```

### Issue: Rate Limiting Triggers

**Symptoms:**
- HTTP 429 "Too Many Requests"
- Rate limit warnings in logs
- Requests blocked

#### Diagnostic Steps

1. **Check Rate Limit Status:**
```bash
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     "https://api.bin2nlp.com/api/v1/admin/rate-limits/user/your-user-id" | jq .
```

2. **Monitor Request Patterns:**
```bash
# Check request logs
docker-compose logs api | grep -E "(429|rate.limit)"

# Monitor current requests
docker-compose logs -f api | grep -E "POST|PUT|DELETE"
```

#### Solutions

**Adjust Request Rate:**
```bash
# Add delays between requests
for i in {1..10}; do
  curl -H "Authorization: Bearer $API_KEY" https://api.bin2nlp.com/health
  sleep 1
done
```

**Request Rate Limit Increase:**
```bash
# Contact admin to increase limits
# Or upgrade API key tier
curl -X PUT -H "Authorization: Bearer $ADMIN_API_KEY" \
     -d '{"tier":"premium"}' \
     https://api.bin2nlp.com/api/v1/admin/api-keys/user/your-user-id/tier
```

---

## Docker and Container Issues

### Issue: Container Build Failures

**Symptoms:**
- `docker build` fails
- Missing dependencies
- Python package installation errors

#### Diagnostic Steps

1. **Check Build Context:**
```bash
# Verify Dockerfile and requirements
cat Dockerfile
cat requirements.txt

# Check for large files in context
du -sh .
```

2. **Build with Verbose Output:**
```bash
docker build --no-cache --progress=plain -t bin2nlp:debug .
```

#### Solutions

**Clear Build Cache:**
```bash
# Clear Docker build cache
docker builder prune -f

# Rebuild from scratch
docker-compose build --no-cache
```

**Fix Dependencies:**
```bash
# Update requirements.txt
pip freeze > requirements.txt

# Test requirements locally
python -m venv test-env
source test-env/bin/activate
pip install -r requirements.txt
```

### Issue: Container Resource Exhaustion

**Symptoms:**
- Containers killed by OOM
- CPU throttling
- Disk space errors

#### Diagnostic Steps

1. **Check Resource Usage:**
```bash
docker stats
df -h
free -h
```

2. **Check Docker System Usage:**
```bash
docker system df
docker system events &  # Monitor events
```

#### Solutions

**Increase Resource Limits:**
```bash
# Edit docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 4G
    reservations:
      cpus: '2.0'
      memory: 2G
```

**Clean Up Docker Resources:**
```bash
# Clean up unused resources
docker system prune -f
docker volume prune -f
docker image prune -f

# Remove unused images
docker image ls | grep "<none>" | awk '{print $3}' | xargs docker rmi
```

---

## Configuration Issues

### Issue: Environment Variables Not Loading

**Symptoms:**
- Default values used instead of configured values
- Configuration changes not applied
- Service behavior inconsistent

#### Diagnostic Steps

1. **Verify Environment Files:**
```bash
# Check if .env file exists and is readable
ls -la .env*
cat .env | grep -v '^#' | grep -v '^$'

# Check docker-compose configuration
docker-compose config
```

2. **Check Variable Loading:**
```bash
# Check environment variables inside container
docker-compose exec api env | grep LLM_
docker-compose exec api python -c "import os; print(os.environ.get('LLM_OPENAI_API_KEY', 'NOT SET'))"
```

#### Solutions

**Fix Environment File Loading:**
```bash
# Ensure .env is in correct location
ls -la .env

# Check docker-compose.yml env_file configuration
env_file:
  - .env

# Restart containers to reload environment
docker-compose restart
```

**Variable Precedence Issues:**
```bash
# Check for conflicting environment variables
env | grep LLM_OPENAI_API_KEY

# Unset system environment variables if conflicting
unset LLM_OPENAI_API_KEY
```

### Issue: Configuration Validation Failures

**Symptoms:**
- "Invalid configuration" errors
- Service won't start with config errors
- Validation warnings in logs

#### Diagnostic Steps

1. **Run Configuration Validation:**
```bash
# Test configuration syntax
docker-compose exec api python -m src.core.config_validation

# Check specific configuration sections
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/config/validate | jq .
```

2. **Check Configuration Values:**
```bash
# Review current configuration
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/config | jq .
```

#### Solutions

**Fix Configuration Syntax:**
```bash
# Common configuration fixes
API_PORT=8000                    # Must be integer
DEBUG=false                      # Must be boolean
CORS_ORIGINS='["http://localhost"]'  # Must be valid JSON array
```

**Validate Required Fields:**
```bash
# Ensure all required fields are set
grep -E "REDIS_URL|LLM_.*_API_KEY" .env
```

---

## Known Issues and Limitations

### Known Issues

#### Issue: Memory Leak in Long-Running Sessions
- **Affects:** Continuous operation > 24 hours
- **Symptoms:** Gradual memory increase
- **Workaround:** Restart containers daily
- **Status:** Under investigation
- **Tracking:** Issue #123

#### Issue: Large Binary Files (>500MB) Cause Timeouts
- **Affects:** Files larger than 500MB
- **Symptoms:** Request timeouts, incomplete processing
- **Workaround:** Split large files or increase timeouts
- **Status:** Architecture limitation
- **Tracking:** Enhancement #456

#### Issue: Circuit Breaker False Positives During High Load
- **Affects:** High-traffic periods (>100 requests/min)
- **Symptoms:** Circuit breakers open unnecessarily
- **Workaround:** Adjust thresholds or reset manually
- **Status:** Configuration issue
- **Tracking:** Issue #789

### Current Limitations

#### File Format Support
- **Supported:** PE, ELF, Mach-O, Java bytecode
- **Not Supported:** Packed executables, custom formats, encrypted binaries
- **Planned:** Additional format support in v2.0

#### LLM Provider Limitations
- **Token Limits:** Vary by provider (1K-8K tokens)
- **Context Windows:** Limited for very large functions
- **Cost Control:** Daily/monthly limits enforced

#### Performance Constraints
- **Concurrent Processing:** Limited to 20 simultaneous requests
- **Memory Usage:** Peak usage ~4GB for large files
- **Processing Time:** Complex binaries may take 10+ minutes

### Breaking Changes History

#### Version 1.0.0 → 1.1.0 (Upcoming)
- **API Changes:** New authentication header format
- **Configuration:** Environment variable renaming
- **Migration Guide:** Available at docs/migration-v1.1.md

#### Version 0.9.x → 1.0.0
- **Breaking:** Removed legacy analysis endpoints
- **Migration:** Updated to decompilation-focused API
- **Impact:** All API clients need updates

---

## Error Code Reference

### HTTP Status Codes

| Code | Meaning | Common Cause | Solution |
|------|---------|--------------|----------|
| **400** | Bad Request | Invalid input format | Check request format and parameters |
| **401** | Unauthorized | Missing/invalid API key | Verify API key and header format |
| **403** | Forbidden | Insufficient permissions | Check API key tier and permissions |
| **404** | Not Found | Resource doesn't exist | Verify endpoint URL and resource ID |
| **413** | Payload Too Large | File size exceeds limit | Reduce file size or increase limits |
| **422** | Unprocessable Entity | Unsupported file format | Check file format support |
| **429** | Too Many Requests | Rate limit exceeded | Reduce request rate or wait |
| **500** | Internal Server Error | Application error | Check logs, restart service |
| **502** | Bad Gateway | Service unavailable | Check service status, restart |
| **503** | Service Unavailable | System overloaded | Wait and retry, check resources |
| **504** | Gateway Timeout | Request timeout | Increase timeout or optimize request |

### Application Error Codes

| Code | Category | Description | Solution |
|------|----------|-------------|----------|
| **BIN001** | File Processing | Invalid binary format | Use supported file format |
| **BIN002** | File Processing | File corruption detected | Re-upload file |
| **BIN003** | File Processing | File size too large | Reduce file size |
| **LLM001** | LLM Provider | API key invalid | Update API key |
| **LLM002** | LLM Provider | Rate limit exceeded | Reduce request rate |
| **LLM003** | LLM Provider | Provider unavailable | Try different provider |
| **LLM004** | LLM Provider | Token limit exceeded | Reduce input size |
| **CACHE001** | Redis | Connection failed | Check Redis status |
| **CACHE002** | Redis | Memory limit exceeded | Increase Redis memory |
| **AUTH001** | Authentication | Invalid credentials | Check API key |
| **AUTH002** | Authentication | Permissions insufficient | Upgrade API key tier |

---

## Log Analysis Guide

### Log Levels and Their Meanings

| Level | Purpose | When to Check |
|-------|---------|---------------|
| **DEBUG** | Detailed execution flow | Development, deep troubleshooting |
| **INFO** | Normal operations | Monitoring, audit trail |
| **WARNING** | Potential issues | Performance monitoring, maintenance |
| **ERROR** | Operation failures | Issue investigation |
| **CRITICAL** | System failures | Emergency response |

### Common Log Patterns

#### Normal Operation Patterns
```bash
# Successful request pattern
INFO: Request received: POST /api/v1/analyze
INFO: File validated: binary.exe (1.2MB, PE format)
INFO: Decompilation started: job_id=abc123
INFO: LLM translation started: provider=openai
INFO: Request completed: job_id=abc123, duration=45.2s
```

#### Error Patterns to Look For
```bash
# LLM Provider issues
ERROR: OpenAI API error: rate_limit_exceeded
WARNING: Circuit breaker opened: openai_translate_function
INFO: Failing over to provider: anthropic

# Memory issues
WARNING: High memory usage detected: 85%
ERROR: Out of memory: container killed
CRITICAL: Service restart required

# Redis connection issues
ERROR: Redis connection failed: connection timeout
WARNING: Cache unavailable, performance degraded
INFO: Redis connection restored
```

### Log Analysis Commands

#### Find Specific Issues
```bash
# Find all errors in last hour
docker-compose logs api --since 1h | grep ERROR

# Find memory-related issues
docker-compose logs | grep -i "memory\|oom\|killed"

# Find LLM provider issues
docker-compose logs | grep -E "(LLM|circuit|provider)" | grep -E "(ERROR|WARNING)"

# Find performance issues
docker-compose logs | grep -E "(timeout|slow|performance)" | tail -50
```

#### Analyze Request Patterns
```bash
# Count requests by type
docker-compose logs api | grep "Request received" | awk '{print $NF}' | sort | uniq -c

# Find slow requests
docker-compose logs api | grep "Request completed" | grep -E "duration=[5-9][0-9]\."

# Monitor real-time requests
docker-compose logs -f api | grep -E "(Request received|Request completed)"
```

---

## Getting Help

### Self-Service Resources

1. **Documentation:**
   - [Deployment Guide](deployment.md)
   - [Operational Runbooks](runbooks.md)
   - [LLM Provider Setup](llm-providers.md)
   - [API Documentation](https://api.bin2nlp.com/docs)

2. **Monitoring Tools:**
   - Health Dashboard: https://api.bin2nlp.com/dashboard/
   - API Explorer: https://api.bin2nlp.com/dashboard/api
   - Prometheus Metrics: https://api.bin2nlp.com/api/v1/admin/monitoring/prometheus

3. **Diagnostic Tools:**
   - Configuration Validator: `python -m src.core.config_validation`
   - Health Check: `curl https://api.bin2nlp.com/health/detailed`
   - System Stats: `curl https://api.bin2nlp.com/api/v1/admin/stats`

### Support Escalation

**For Production Issues:**
1. Check this troubleshooting guide first
2. Gather diagnostic information using commands above
3. Check service status and recent changes
4. Contact support with: logs, error codes, reproduction steps

**For Development Issues:**
1. Verify environment setup
2. Check configuration validity
3. Test with minimal examples
4. Review documentation for API changes

### Reporting Issues

**Include in Issue Reports:**
- bin2nlp version
- Operating system and Docker version
- Full error messages and stack traces
- Steps to reproduce
- Environment configuration (redacted)
- Relevant log snippets

---

**Last Updated:** 2025-08-19  
**Version:** 1.0.0  
**Next Review:** 2025-09-19

This troubleshooting guide is continuously updated based on user feedback and new issues discovered in production environments.