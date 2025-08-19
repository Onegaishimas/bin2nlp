# bin2nlp Operational Runbooks

## Overview

This document provides step-by-step runbooks for common operational scenarios when managing the bin2nlp Binary Decompilation & LLM Translation Service. Each runbook includes detection, diagnosis, and resolution procedures.

## Table of Contents

- [Service Health Monitoring](#service-health-monitoring)
- [Performance Issues](#performance-issues)
- [LLM Provider Issues](#llm-provider-issues)
- [Circuit Breaker Management](#circuit-breaker-management)
- [Redis Issues](#redis-issues)
- [Deployment and Updates](#deployment-and-updates)
- [Security Incidents](#security-incidents)
- [Capacity Planning](#capacity-planning)
- [Backup and Recovery](#backup-and-recovery)
- [Emergency Procedures](#emergency-procedures)

---

## Service Health Monitoring

### Daily Health Check

**Frequency:** Daily (automated)  
**Duration:** 5 minutes  
**Prerequisites:** Admin API access

#### Procedure

1. **Check Overall Health:**
```bash
# Basic health check
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/health/detailed

# Expected: HTTP 200, all components "healthy"
```

2. **Review System Dashboard:**
```bash
# Access web dashboard
https://api.bin2nlp.com/dashboard/

# Check key metrics:
# - Active alerts (should be 0)
# - Circuit breaker health (should be 100%)
# - Performance metrics (within thresholds)
```

3. **Monitor Prometheus Metrics:**
```bash
# Get Prometheus metrics
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/monitoring/prometheus

# Key metrics to check:
# - bin2nlp_operations_total (increasing)
# - bin2nlp_current_value (circuit breakers closed)
# - bin2nlp_info (service version)
```

#### Alert Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| Health endpoint returns 5xx | Critical | Follow [Service Down](#service-down) runbook |
| Active alerts > 0 | Warning | Review alert details and follow specific runbooks |
| Circuit breakers open | High | Follow [Circuit Breaker Issues](#circuit-breaker-issues) runbook |

---

## Performance Issues

### Slow Response Times

**Detection:** Response times > 30 seconds, timeout errors  
**Impact:** User experience degradation  

#### Diagnosis

1. **Check Performance Metrics:**
```bash
# Get detailed performance data
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     "https://api.bin2nlp.com/api/v1/admin/metrics/performance?time_window_minutes=60"

# Look for:
# - avg_duration_ms > 30000 (30 seconds)
# - success_rate < 95%
# - high p99 response times
```

2. **Check System Resources:**
```bash
# Docker resource usage
docker stats

# System resources
htop
free -h
df -h
```

3. **Review Application Logs:**
```bash
# Check for errors or timeouts
docker-compose logs api --tail=100

# Look for:
# - Timeout errors
# - Memory allocation errors
# - Database connection issues
```

#### Resolution Steps

**Immediate Actions:**

1. **Restart Slow Components:**
```bash
# Restart API containers
docker-compose restart api

# Monitor improvement
watch -n 5 'curl -w "@curl-format.txt" -s https://api.bin2nlp.com/health'
```

2. **Scale Up Resources:**
```bash
# Increase API replicas
docker-compose up --scale api=3 -d

# Or increase resource limits
# Edit docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 2G
      cpus: '2.0'
```

**Long-term Actions:**

1. **Optimize Configuration:**
```bash
# Increase worker processes
API_WORKERS=8

# Tune timeouts
DEFAULT_TIMEOUT_SECONDS=600
MAX_TIMEOUT_SECONDS=1800
```

2. **Database Optimization:**
```bash
# Redis performance tuning
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG SET tcp-keepalive 60
```

### High Memory Usage

**Detection:** Memory usage > 80%, OOM kills  
**Impact:** Service instability, crashes

#### Diagnosis

1. **Check Memory Usage:**
```bash
# Container memory usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# System memory
free -h
cat /proc/meminfo
```

2. **Analyze Memory Patterns:**
```bash
# Check for memory leaks in logs
docker-compose logs api | grep -i "memory\|oom\|killed"

# Monitor memory over time
watch -n 5 'docker stats --no-stream'
```

#### Resolution Steps

1. **Immediate Relief:**
```bash
# Restart high-memory containers
docker-compose restart api

# Clear Redis cache if necessary
redis-cli FLUSHDB
```

2. **Resource Adjustment:**
```bash
# Increase memory limits
# Edit docker-compose.yml
deploy:
  resources:
    limits:
      memory: 4G  # Increase from 2G
```

3. **Configuration Tuning:**
```bash
# Reduce worker processes if memory-bound
API_WORKERS=2

# Enable memory monitoring
ENABLE_MEMORY_PROFILING=true
```

---

## LLM Provider Issues

### Provider API Failures

**Detection:** High failure rates in LLM requests, circuit breakers opening  
**Impact:** Translation services degraded or unavailable

#### Diagnosis

1. **Check Provider Health:**
```bash
# Get LLM provider status
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/llm/providers/health

# Check individual providers
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/llm/providers/openai/health
```

2. **Review Circuit Breakers:**
```bash
# Get circuit breaker status
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers

# Look for OPEN state providers
```

3. **Check Rate Limits:**
```bash
# Review LLM metrics
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/metrics/llm

# Look for rate limit errors
```

#### Resolution Steps

**For API Key Issues:**

1. **Verify API Keys:**
```bash
# Test OpenAI API key directly
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models

# Test Anthropic API key
curl -H "x-api-key: $ANTHROPIC_API_KEY" \
     https://api.anthropic.com/v1/messages \
     -d '{"model":"claude-3-sonnet-20240229","max_tokens":10,"messages":[{"role":"user","content":"test"}]}'
```

2. **Rotate API Keys:**
```bash
# Update environment variables
nano .env.prod

# Restart services
docker-compose restart api
```

**For Rate Limiting:**

1. **Check Current Usage:**
```bash
# Review rate limit status
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/rate-limits/system

# Wait for rate limit reset or reduce request rate
```

2. **Adjust Rate Limits:**
```bash
# Reduce requests per minute
LLM_OPENAI_REQUESTS_PER_MINUTE=30  # Reduce from 60
LLM_ANTHROPIC_REQUESTS_PER_MINUTE=25  # Reduce from 50

# Restart to apply changes
docker-compose restart api
```

**For Circuit Breaker Issues:**

1. **Manual Reset:**
```bash
# Reset specific circuit breaker
curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/openai_translate_function/reset

# Check if it stays closed
sleep 30
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/openai_translate_function
```

2. **Provider Failover:**
```bash
# Temporarily disable problematic provider
LLM_OPENAI_ENABLED=false
LLM_ANTHROPIC_ENABLED=true
LLM_GEMINI_ENABLED=true

docker-compose restart api
```

### Provider Performance Degradation

**Detection:** Slow LLM response times, timeouts  
**Impact:** Overall system slowdown

#### Diagnosis

1. **Check Response Times:**
```bash
# Get LLM performance metrics
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     "https://api.bin2nlp.com/api/v1/admin/metrics/llm?time_window_minutes=30"

# Look for:
# - avg_duration_ms > 10000 (10 seconds)
# - High p99 latencies
```

2. **Test Provider Directly:**
```bash
# Time a direct API call
time curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"gpt-4","messages":[{"role":"user","content":"Hello"}],"max_tokens":10}' \
     https://api.openai.com/v1/chat/completions
```

#### Resolution Steps

1. **Switch to Faster Provider:**
```bash
# Change default provider temporarily
LLM_DEFAULT_PROVIDER=anthropic  # Switch from openai

docker-compose restart api
```

2. **Adjust Timeouts:**
```bash
# Increase LLM timeout settings
LLM_REQUEST_TIMEOUT_SECONDS=60  # Increase from 30
LLM_MAX_RETRIES=2  # Reduce from 3

docker-compose restart api
```

---

## Circuit Breaker Management

### Circuit Breaker Stuck Open

**Detection:** Circuit breaker remains OPEN despite provider being healthy  
**Impact:** Service degradation, reduced functionality

#### Diagnosis

1. **Check Circuit Status:**
```bash
# Get detailed circuit breaker info
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/CIRCUIT_NAME

# Review failure count and timestamps
```

2. **Test Underlying Service:**
```bash
# Health check all circuits
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/health-check/all
```

#### Resolution Steps

1. **Manual Reset:**
```bash
# Reset the circuit breaker
curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/CIRCUIT_NAME/reset

# Verify it stays closed
watch -n 10 'curl -s -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/CIRCUIT_NAME | jq .state'
```

2. **Investigate Root Cause:**
```bash
# Check application logs for errors
docker-compose logs api | grep -i "circuit\|breaker\|CIRCUIT_NAME"

# Review recent performance metrics
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     "https://api.bin2nlp.com/api/v1/admin/metrics/performance?time_window_minutes=120"
```

### Frequent Circuit Breaker Trips

**Detection:** Circuit breakers frequently changing state  
**Impact:** Service instability, inconsistent performance

#### Diagnosis

1. **Analyze Trip Patterns:**
```bash
# Check circuit breaker logs
docker-compose logs api | grep -i "circuit.*open\|circuit.*closed"

# Monitor state changes
watch -n 5 'curl -s -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers'
```

2. **Check Error Rates:**
```bash
# Get error metrics
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/metrics/current | jq '.metrics.counters'

# Look for high failure counts
```

#### Resolution Steps

1. **Adjust Circuit Breaker Thresholds:**
```bash
# Temporarily increase failure threshold
# Edit configuration or environment:
CIRCUIT_BREAKER_FAILURE_THRESHOLD=10  # Increase from 5
CIRCUIT_BREAKER_TIMEOUT_SECONDS=120   # Increase from 60

docker-compose restart api
```

2. **Fix Underlying Issues:**
```bash
# Address root causes:
# - API key issues
# - Network connectivity
# - Service overload
# - Rate limiting
```

---

## Redis Issues

### Redis Connection Failures

**Detection:** "Redis connection failed" errors, cache misses  
**Impact:** Degraded performance, increased LLM usage

#### Diagnosis

1. **Test Redis Connectivity:**
```bash
# Test from application container
docker-compose exec api redis-cli -h redis -p 6379 ping

# Test from host
redis-cli -h localhost -p 6379 ping

# Check Redis logs
docker-compose logs redis
```

2. **Check Redis Status:**
```bash
# Redis info
redis-cli -h localhost -p 6379 info server
redis-cli -h localhost -p 6379 info memory
redis-cli -h localhost -p 6379 info clients
```

#### Resolution Steps

1. **Restart Redis:**
```bash
# Restart Redis container
docker-compose restart redis

# Check if connection restored
redis-cli -h localhost -p 6379 ping
```

2. **Check Network Connectivity:**
```bash
# Test network connectivity
docker network ls
docker network inspect bin2nlp_default

# Restart networking if needed
docker-compose down
docker-compose up -d
```

### Redis Memory Issues

**Detection:** Redis memory warnings, evicted keys  
**Impact:** Cache inefficiency, increased LLM costs

#### Diagnosis

1. **Check Memory Usage:**
```bash
# Redis memory info
redis-cli -h localhost -p 6379 info memory

# Key statistics
redis-cli -h localhost -p 6379 info stats | grep evicted
redis-cli -h localhost -p 6379 dbsize
```

2. **Analyze Key Patterns:**
```bash
# Sample large keys
redis-cli -h localhost -p 6379 --bigkeys

# Check TTL distribution
redis-cli -h localhost -p 6379 --scan | head -100 | \
  xargs -I {} redis-cli -h localhost -p 6379 ttl {}
```

#### Resolution Steps

1. **Increase Memory Limit:**
```bash
# Increase Redis memory limit
redis-cli -h localhost -p 6379 CONFIG SET maxmemory 512mb

# Or edit docker-compose.yml for persistence
deploy:
  resources:
    limits:
      memory: 512M  # Increase from 256M
```

2. **Optimize Memory Usage:**
```bash
# Set better eviction policy
redis-cli -h localhost -p 6379 CONFIG SET maxmemory-policy allkeys-lru

# Reduce default TTL if needed
DEFAULT_TTL_SECONDS=3600  # Reduce from 7200
```

---

## Deployment and Updates

### Zero-Downtime Deployment

**Objective:** Deploy new version without service interruption  
**Duration:** 10-15 minutes

#### Prerequisites

- New Docker image built and tested
- Database migrations ready (if any)
- Rollback plan prepared

#### Procedure

1. **Pre-deployment Checks:**
```bash
# Verify current system health
curl https://api.bin2nlp.com/health/detailed

# Backup current configuration
cp docker-compose.prod.yml docker-compose.prod.yml.backup
cp .env.prod .env.prod.backup
```

2. **Deploy New Version:**
```bash
# Pull new images
docker-compose pull

# Update containers one by one (for multi-instance)
docker-compose up --scale api=2 -d  # Scale up temporarily
sleep 30  # Allow warm-up
docker-compose stop api_1  # Stop old instance
docker-compose rm -f api_1  # Remove old container
docker-compose up --scale api=1 -d  # Scale back down
```

3. **Verify Deployment:**
```bash
# Check health after deployment
curl https://api.bin2nlp.com/health/detailed

# Monitor metrics for 5 minutes
watch -n 30 'curl -s https://api.bin2nlp.com/api/v1/admin/metrics/current'

# Check for new errors
docker-compose logs --tail=100
```

#### Rollback Procedure

```bash
# If deployment fails, rollback immediately:

# 1. Restore previous configuration
cp docker-compose.prod.yml.backup docker-compose.prod.yml
cp .env.prod.backup .env.prod

# 2. Deploy previous version
docker-compose down
docker-compose up -d

# 3. Verify rollback
curl https://api.bin2nlp.com/health/detailed
```

### Configuration Updates

**Objective:** Update configuration without rebuilding images  
**Duration:** 2-5 minutes (with restart)

#### Hot Configuration Updates (No Restart Required)

```bash
# Update rate limits via API
curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"requests_per_minute": 120}' \
     https://api.bin2nlp.com/api/v1/admin/config/rate-limits
```

#### Cold Configuration Updates (Restart Required)

```bash
# 1. Update configuration file
nano .env.prod

# 2. Restart services
docker-compose restart api

# 3. Verify changes
curl https://api.bin2nlp.com/api/v1/admin/config | jq .
```

---

## Security Incidents

### Suspicious API Activity

**Detection:** Unusual traffic patterns, failed authentication attempts  
**Impact:** Potential security breach, service abuse

#### Immediate Response

1. **Assess Threat:**
```bash
# Check recent API access logs
docker-compose logs api | grep -E "(401|403|429)" | tail -100

# Monitor current requests
docker-compose logs -f api | grep -E "(POST|PUT|DELETE)"

# Check rate limiting triggers
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/stats | jq '.rate_limit_stats'
```

2. **Block Suspicious IPs:**
```bash
# Add firewall rules
sudo ufw deny from SUSPICIOUS_IP

# Or update Nginx configuration
# Add to nginx.conf:
deny SUSPICIOUS_IP;

# Reload Nginx
sudo systemctl reload nginx
```

3. **Revoke Compromised Keys:**
```bash
# List all API keys
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/api-keys/all

# Revoke specific key
curl -X DELETE -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/api-keys/USER_ID/KEY_ID
```

### Data Breach Response

**Detection:** Unauthorized access to sensitive data  
**Impact:** CRITICAL - potential data compromise

#### Emergency Response

1. **Isolate Systems:**
```bash
# Immediately stop all services
docker-compose down

# Block all external access
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw allow ssh
sudo ufw enable
```

2. **Assess Damage:**
```bash
# Check for data exfiltration
grep -r "api_key\|password\|token" /var/log/

# Review access logs
docker-compose logs api > security_incident_logs_$(date +%Y%m%d).txt

# Check Redis for sensitive data
redis-cli --scan | grep -E "(api_key|password|secret)"
```

3. **Containment:**
```bash
# Rotate all secrets immediately
# Generate new API keys
# Update all LLM provider keys
# Change Redis passwords

# Update and restart with new credentials
nano .env.prod  # Update all secrets
docker-compose up -d
```

4. **Recovery:**
```bash
# Implement additional security measures
# - Enable audit logging
# - Implement IP whitelisting
# - Add MFA for admin access
# - Increase monitoring sensitivity
```

---

## Capacity Planning

### Usage Growth Monitoring

**Objective:** Monitor service usage trends for capacity planning  
**Frequency:** Weekly

#### Key Metrics to Track

1. **Request Volume:**
```bash
# Weekly request trends
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     "https://api.bin2nlp.com/api/v1/admin/metrics/current" | \
     jq '.metrics.counters | to_entries[] | select(.key | contains("total")) | {metric: .key, value: .value}'
```

2. **Resource Utilization:**
```bash
# CPU and memory trends
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Storage usage
df -h
du -sh /opt/bin2nlp/data/
```

3. **LLM Usage and Costs:**
```bash
# LLM provider usage statistics
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/metrics/llm | jq '.llm_performance'
```

#### Capacity Planning Actions

**Scale-Up Triggers:**
- CPU usage > 80% sustained
- Memory usage > 85% sustained
- Response times > 10 seconds average
- Error rate > 5%

**Scale-Up Procedures:**
```bash
# Horizontal scaling
docker-compose up --scale api=3 -d

# Vertical scaling
# Edit docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 4G  # Increase from 2G
      cpus: '4.0' # Increase from 2.0
```

---

## Emergency Procedures

### Service Down (Complete Outage)

**Detection:** Health checks fail, service unreachable  
**Impact:** CRITICAL - complete service unavailability  
**Response Time:** < 5 minutes

#### Emergency Response

1. **Immediate Assessment:**
```bash
# Quick status check
curl -I https://api.bin2nlp.com/health
systemctl status nginx
docker-compose ps

# Check system resources
free -h
df -h
uptime
```

2. **Emergency Restart:**
```bash
# Full system restart
docker-compose down
docker system prune -f
docker-compose up -d

# Monitor restart
watch -n 5 'docker-compose ps'
```

3. **Verify Recovery:**
```bash
# Check all endpoints
curl https://api.bin2nlp.com/health
curl https://api.bin2nlp.com/health/detailed
curl https://api.bin2nlp.com/llm/providers

# Test functionality
curl -X POST -H "Content-Type: application/json" \
     -H "Authorization: Bearer $TEST_API_KEY" \
     -d '{"text":"test"}' \
     https://api.bin2nlp.com/api/v1/test-endpoint
```

### Database Corruption (Redis)

**Detection:** Redis errors, data inconsistency  
**Impact:** HIGH - cache unavailable, performance degraded

#### Emergency Response

1. **Stop Application:**
```bash
# Stop API to prevent further corruption
docker-compose stop api
```

2. **Assess Redis Status:**
```bash
# Check Redis logs
docker-compose logs redis | tail -100

# Try to connect
redis-cli -h localhost -p 6379 ping
redis-cli -h localhost -p 6379 info server
```

3. **Recovery Options:**

**Option A: Redis Restart (Data Loss)**
```bash
# Restart Redis (loses all cache data)
docker-compose restart redis
redis-cli -h localhost -p 6379 ping

# Restart API
docker-compose start api
```

**Option B: Restore from Backup**
```bash
# Stop Redis
docker-compose stop redis

# Restore from latest backup
gunzip -c /opt/bin2nlp/backups/redis_backup_latest.rdb.gz > \
    /opt/bin2nlp/data/redis/dump.rdb

# Start Redis
docker-compose start redis

# Verify data
redis-cli -h localhost -p 6379 dbsize

# Start API
docker-compose start api
```

### Critical Alert Storm

**Detection:** Multiple critical alerts firing simultaneously  
**Impact:** CRITICAL - system instability, potential cascading failures

#### Emergency Response

1. **Triage Alerts:**
```bash
# Get all active alerts
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/alerts | jq '.active_alerts'

# Identify root cause alerts vs. cascading alerts
# Focus on: circuit_open, service_down, high_error_rate
```

2. **Emergency Stabilization:**
```bash
# Restart all services
docker-compose restart

# Reset all circuit breakers
curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/circuit-breakers/all/reset
```

3. **Systematic Recovery:**
```bash
# Address issues in priority order:
# 1. Infrastructure (Redis, networking)
# 2. API services
# 3. LLM providers
# 4. Monitoring systems
```

---

## Escalation Procedures

### Alert Severity Levels

| Severity | Response Time | Escalation | Example |
|----------|---------------|------------|---------|
| **Critical** | < 15 minutes | Page on-call engineer | Service down, security breach |
| **High** | < 2 hours | Notify team lead | Circuit breaker open, high error rate |
| **Medium** | < 24 hours | Create ticket | Performance degradation |
| **Low** | < 1 week | Include in weekly review | Minor configuration drift |

### Contact Information

**On-Call Engineer:** +1-XXX-XXX-XXXX  
**Team Lead:** email@company.com  
**Security Team:** security@company.com  
**Escalation Matrix:** [Internal documentation link]

### Communication Templates

**Critical Issue Communication:**
```
CRITICAL: bin2nlp service outage
Status: Investigating/Mitigating/Resolved
Impact: [Describe user impact]
ETA: [Estimated resolution time]
Actions: [What is being done]
Next Update: [When next update will be sent]
```

---

**Last Updated:** 2025-08-19  
**Version:** 1.0.0  
**Next Review:** 2025-09-19