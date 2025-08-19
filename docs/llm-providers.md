# LLM Provider Setup and Configuration Guide

## Overview

This guide provides comprehensive instructions for setting up and configuring LLM (Large Language Model) providers with the bin2nlp service. The service supports multiple providers for redundancy, cost optimization, and quality comparison.

## Table of Contents

- [Supported Providers](#supported-providers)
- [Provider Selection Strategy](#provider-selection-strategy)
- [OpenAI Configuration](#openai-configuration)
- [Anthropic Claude Configuration](#anthropic-claude-configuration)
- [Google Gemini Configuration](#google-gemini-configuration)
- [OpenAI-Compatible Endpoints](#openai-compatible-endpoints)
- [Multi-Provider Setup](#multi-provider-setup)
- [Rate Limiting and Cost Management](#rate-limiting-and-cost-management)
- [Health Monitoring and Circuit Breakers](#health-monitoring-and-circuit-breakers)
- [Testing and Validation](#testing-and-validation)
- [Troubleshooting](#troubleshooting)

---

## Supported Providers

The bin2nlp service supports the following LLM providers:

| Provider | Models | Strengths | Use Cases |
|----------|---------|-----------|-----------|
| **OpenAI** | GPT-4, GPT-4 Turbo, GPT-3.5 Turbo | Excellent code understanding, fast responses | General decompilation, function analysis |
| **Anthropic Claude** | Claude-3 Sonnet, Claude-3 Haiku, Claude-3 Opus | Long context, constitutional AI | Complex binaries, detailed analysis |
| **Google Gemini** | Gemini Pro, Gemini Pro Vision | Multimodal capabilities, competitive pricing | Cost-effective translation, future vision features |
| **OpenAI-Compatible** | Various (Ollama, LM Studio, etc.) | Local deployment, privacy, cost control | On-premises deployment, sensitive data |

---

## Provider Selection Strategy

### Recommended Configuration

**Production Setup:**
- **Primary:** OpenAI (GPT-4) - Best balance of quality and speed
- **Secondary:** Anthropic Claude - Long context for complex functions
- **Tertiary:** Google Gemini - Cost optimization for simple translations
- **Fallback:** Local Ollama instance - Offline capability

**Development/Testing Setup:**
- **Primary:** OpenAI (GPT-3.5 Turbo) - Fast and cost-effective
- **Secondary:** Local Ollama - No API costs during development

### Selection Criteria

1. **Quality Requirements:**
   - Critical applications: GPT-4, Claude-3 Opus
   - Standard applications: GPT-3.5 Turbo, Claude-3 Sonnet
   - Development/testing: Gemini Pro, Local models

2. **Cost Optimization:**
   - Highest cost: GPT-4, Claude-3 Opus
   - Moderate cost: GPT-3.5 Turbo, Claude-3 Sonnet
   - Low cost: Gemini Pro, Local models

3. **Performance Requirements:**
   - Fastest: GPT-3.5 Turbo, Gemini Pro
   - Moderate: GPT-4, Claude-3 Sonnet
   - Slower: Claude-3 Opus, Local models

---

## OpenAI Configuration

### Prerequisites

1. **OpenAI Account Setup:**
   - Sign up at [platform.openai.com](https://platform.openai.com)
   - Add billing information
   - Set usage limits and alerts

2. **API Key Generation:**
   ```bash
   # Navigate to API Keys in OpenAI Dashboard
   # Create new secret key with appropriate permissions
   # Copy the key (starts with 'sk-')
   ```

### Configuration

#### Environment Variables

```bash
# Enable OpenAI provider
LLM_OPENAI_ENABLED=true

# API credentials
LLM_OPENAI_API_KEY=sk-your-openai-api-key-here

# Model configuration
LLM_OPENAI_MODEL=gpt-4                    # or gpt-3.5-turbo
LLM_OPENAI_TEMPERATURE=0.1                # Low temperature for consistency
LLM_OPENAI_MAX_TOKENS=2048               # Maximum response tokens

# API endpoint (usually default)
LLM_OPENAI_BASE_URL=https://api.openai.com/v1

# Rate limiting (adjust based on your plan)
LLM_OPENAI_REQUESTS_PER_MINUTE=60        # Adjust per tier
LLM_OPENAI_TOKENS_PER_MINUTE=90000       # Adjust per tier
LLM_OPENAI_REQUESTS_PER_DAY=10000        # Daily limit

# Timeout and retry settings
LLM_OPENAI_TIMEOUT_SECONDS=30
LLM_OPENAI_MAX_RETRIES=3
LLM_OPENAI_RETRY_DELAY_SECONDS=2

# Cost management
LLM_OPENAI_DAILY_SPEND_LIMIT=50.00       # USD
LLM_OPENAI_MONTHLY_SPEND_LIMIT=1000.00   # USD
```

#### Advanced Configuration

```bash
# Organization (if using organization account)
LLM_OPENAI_ORGANIZATION=org-your-org-id

# Custom headers (if needed)
LLM_OPENAI_CUSTOM_HEADERS='{"Custom-Header": "value"}'

# Prompt optimization
LLM_OPENAI_SYSTEM_MESSAGE_PREFIX="You are an expert binary analysis assistant."
```

### Model Recommendations

#### Production Environments

**GPT-4 (Recommended for Production):**
```bash
LLM_OPENAI_MODEL=gpt-4
LLM_OPENAI_MAX_TOKENS=2048
LLM_OPENAI_TEMPERATURE=0.1
```

**GPT-4 Turbo (For High Volume):**
```bash
LLM_OPENAI_MODEL=gpt-4-1106-preview
LLM_OPENAI_MAX_TOKENS=4096
LLM_OPENAI_TEMPERATURE=0.1
```

#### Development Environments

**GPT-3.5 Turbo (Cost-Effective):**
```bash
LLM_OPENAI_MODEL=gpt-3.5-turbo
LLM_OPENAI_MAX_TOKENS=1024
LLM_OPENAI_TEMPERATURE=0.2
```

---

## Anthropic Claude Configuration

### Prerequisites

1. **Anthropic Account Setup:**
   - Sign up at [console.anthropic.com](https://console.anthropic.com)
   - Complete verification process
   - Add payment method

2. **API Key Generation:**
   ```bash
   # Navigate to API Keys in Anthropic Console
   # Generate new API key
   # Copy the key (starts with 'sk-ant-')
   ```

### Configuration

#### Environment Variables

```bash
# Enable Anthropic provider
LLM_ANTHROPIC_ENABLED=true

# API credentials
LLM_ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here

# Model configuration
LLM_ANTHROPIC_MODEL=claude-3-sonnet-20240229  # or claude-3-haiku-20240307
LLM_ANTHROPIC_MAX_TOKENS=2048
LLM_ANTHROPIC_TEMPERATURE=0.1

# API endpoint (usually default)
LLM_ANTHROPIC_BASE_URL=https://api.anthropic.com

# Rate limiting (adjust based on your tier)
LLM_ANTHROPIC_REQUESTS_PER_MINUTE=50     # Tier-dependent
LLM_ANTHROPIC_TOKENS_PER_MINUTE=100000   # Tier-dependent
LLM_ANTHROPIC_REQUESTS_PER_DAY=8000      # Daily limit

# Timeout and retry settings
LLM_ANTHROPIC_TIMEOUT_SECONDS=45         # Longer for complex responses
LLM_ANTHROPIC_MAX_RETRIES=3
LLM_ANTHROPIC_RETRY_DELAY_SECONDS=3

# Cost management
LLM_ANTHROPIC_DAILY_SPEND_LIMIT=75.00
LLM_ANTHROPIC_MONTHLY_SPEND_LIMIT=1500.00
```

### Model Recommendations

#### For Complex Analysis

**Claude-3 Opus (Highest Quality):**
```bash
LLM_ANTHROPIC_MODEL=claude-3-opus-20240229
LLM_ANTHROPIC_MAX_TOKENS=4096
LLM_ANTHROPIC_TEMPERATURE=0.05
```

**Claude-3 Sonnet (Balanced):**
```bash
LLM_ANTHROPIC_MODEL=claude-3-sonnet-20240229
LLM_ANTHROPIC_MAX_TOKENS=2048
LLM_ANTHROPIC_TEMPERATURE=0.1
```

#### For Fast Processing

**Claude-3 Haiku (Speed Optimized):**
```bash
LLM_ANTHROPIC_MODEL=claude-3-haiku-20240307
LLM_ANTHROPIC_MAX_TOKENS=1024
LLM_ANTHROPIC_TEMPERATURE=0.2
```

---

## Google Gemini Configuration

### Prerequisites

1. **Google Cloud Account:**
   - Set up Google Cloud account
   - Enable Generative AI API
   - Configure billing

2. **API Key Generation:**
   ```bash
   # Go to Google AI Studio (aistudio.google.com)
   # Or use Google Cloud Console
   # Generate API key
   # Copy the key (starts with 'AIza')
   ```

### Configuration

#### Environment Variables

```bash
# Enable Gemini provider
LLM_GEMINI_ENABLED=true

# API credentials
LLM_GEMINI_API_KEY=AIza-your-gemini-key-here

# Model configuration
LLM_GEMINI_MODEL=gemini-pro               # or gemini-pro-vision
LLM_GEMINI_TEMPERATURE=0.1
LLM_GEMINI_MAX_TOKENS=2048

# Rate limiting
LLM_GEMINI_REQUESTS_PER_MINUTE=60
LLM_GEMINI_TOKENS_PER_MINUTE=120000
LLM_GEMINI_REQUESTS_PER_DAY=15000

# Timeout settings
LLM_GEMINI_TIMEOUT_SECONDS=30
LLM_GEMINI_MAX_RETRIES=3
LLM_GEMINI_RETRY_DELAY_SECONDS=2

# Cost management
LLM_GEMINI_DAILY_SPEND_LIMIT=25.00       # Lower cost provider
LLM_GEMINI_MONTHLY_SPEND_LIMIT=500.00
```

### Safety Settings

```bash
# Content safety (adjust as needed)
LLM_GEMINI_SAFETY_HARASSMENT=BLOCK_MEDIUM_AND_ABOVE
LLM_GEMINI_SAFETY_HATE_SPEECH=BLOCK_MEDIUM_AND_ABOVE
LLM_GEMINI_SAFETY_SEXUALLY_EXPLICIT=BLOCK_MEDIUM_AND_ABOVE
LLM_GEMINI_SAFETY_DANGEROUS_CONTENT=BLOCK_ONLY_HIGH
```

---

## OpenAI-Compatible Endpoints

### Supported Services

1. **Local Ollama**
2. **Azure OpenAI Service**
3. **LM Studio**
4. **vLLM**
5. **Custom OpenAI-compatible APIs**

### Ollama Local Setup

#### Installation

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama2                        # 7B model
ollama pull codellama                     # Code-specialized model
ollama pull mistral                       # Alternative model

# Start Ollama server
ollama serve
```

#### Configuration

```bash
# Enable local Ollama as OpenAI-compatible
LLM_OPENAI_ENABLED=true
LLM_OPENAI_BASE_URL=http://localhost:11434/v1
LLM_OPENAI_API_KEY=ollama                 # Dummy key for compatibility
LLM_OPENAI_MODEL=codellama               # Use code-specialized model

# Adjust for local performance
LLM_OPENAI_TIMEOUT_SECONDS=120           # Longer timeout for local
LLM_OPENAI_MAX_TOKENS=1024              # Conservative token limit
LLM_OPENAI_REQUESTS_PER_MINUTE=10        # Limit concurrent requests

# No cost limits for local
LLM_OPENAI_DAILY_SPEND_LIMIT=0
LLM_OPENAI_MONTHLY_SPEND_LIMIT=0
```

### Azure OpenAI Setup

```bash
# Azure-specific configuration
LLM_OPENAI_ENABLED=true
LLM_OPENAI_BASE_URL=https://your-resource.openai.azure.com/
LLM_OPENAI_API_KEY=your-azure-api-key
LLM_OPENAI_MODEL=gpt-4                   # Your deployed model name

# Azure-specific headers
LLM_OPENAI_API_TYPE=azure
LLM_OPENAI_API_VERSION=2024-02-01        # API version
```

---

## Multi-Provider Setup

### Provider Priority Configuration

```bash
# Enable multiple providers
LLM_OPENAI_ENABLED=true
LLM_ANTHROPIC_ENABLED=true
LLM_GEMINI_ENABLED=true

# Set default provider
LLM_DEFAULT_PROVIDER=openai

# Fallback chain
LLM_FALLBACK_PROVIDERS=["anthropic", "gemini"]

# Provider selection strategy
LLM_SELECTION_STRATEGY=cost_optimized     # or quality_optimized, round_robin
```

### Load Balancing

```bash
# Round-robin distribution
LLM_LOAD_BALANCING=round_robin

# Weighted distribution
LLM_PROVIDER_WEIGHTS='{"openai": 50, "anthropic": 30, "gemini": 20}'

# Quality-based routing
LLM_QUALITY_ROUTING='{"complex_functions": "anthropic", "simple_functions": "gemini"}'
```

### Failover Configuration

```bash
# Circuit breaker thresholds
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5      # Failures before opening
CIRCUIT_BREAKER_SUCCESS_THRESHOLD=3      # Successes to close
CIRCUIT_BREAKER_TIMEOUT_SECONDS=60       # Time before retry

# Health check intervals
LLM_HEALTH_CHECK_INTERVAL_SECONDS=300    # 5 minutes
LLM_HEALTH_CHECK_TIMEOUT_SECONDS=30

# Automatic failover
LLM_AUTO_FAILOVER=true
LLM_FAILOVER_THRESHOLD_SECONDS=30        # Switch provider after timeout
```

---

## Rate Limiting and Cost Management

### Rate Limit Configuration

#### Per-Provider Limits

```bash
# OpenAI (adjust based on tier)
LLM_OPENAI_REQUESTS_PER_MINUTE=60
LLM_OPENAI_TOKENS_PER_MINUTE=90000
LLM_OPENAI_REQUESTS_PER_DAY=10000

# Anthropic (adjust based on tier)
LLM_ANTHROPIC_REQUESTS_PER_MINUTE=50
LLM_ANTHROPIC_TOKENS_PER_MINUTE=100000
LLM_ANTHROPIC_REQUESTS_PER_DAY=8000

# Gemini (generous free tier)
LLM_GEMINI_REQUESTS_PER_MINUTE=60
LLM_GEMINI_TOKENS_PER_MINUTE=120000
LLM_GEMINI_REQUESTS_PER_DAY=15000
```

#### Global Limits

```bash
# Overall system limits
GLOBAL_LLM_REQUESTS_PER_MINUTE=150       # Sum across providers
GLOBAL_LLM_REQUESTS_PER_DAY=25000
GLOBAL_CONCURRENT_REQUESTS=20            # Prevent overload
```

### Cost Management

#### Spending Limits

```bash
# Daily limits (USD)
LLM_OPENAI_DAILY_SPEND_LIMIT=50.00
LLM_ANTHROPIC_DAILY_SPEND_LIMIT=75.00
LLM_GEMINI_DAILY_SPEND_LIMIT=25.00
GLOBAL_DAILY_SPEND_LIMIT=150.00

# Monthly limits (USD)
LLM_OPENAI_MONTHLY_SPEND_LIMIT=1000.00
LLM_ANTHROPIC_MONTHLY_SPEND_LIMIT=1500.00
LLM_GEMINI_MONTHLY_SPEND_LIMIT=500.00
GLOBAL_MONTHLY_SPEND_LIMIT=3000.00
```

#### Cost Tracking

```bash
# Enable detailed cost tracking
ENABLE_COST_TRACKING=true
COST_TRACKING_PRECISION=4                # Decimal places

# Cost alerts
COST_ALERT_THRESHOLDS='[25, 50, 75, 90]' # Percentage thresholds
COST_ALERT_EMAIL=admin@yourcompany.com

# Budget controls
ENABLE_BUDGET_ENFORCEMENT=true           # Stop at limit
BUDGET_GRACE_PERIOD_HOURS=24            # Grace period for overruns
```

---

## Health Monitoring and Circuit Breakers

### Health Check Configuration

```bash
# Health check settings
LLM_HEALTH_CHECK_ENABLED=true
LLM_HEALTH_CHECK_INTERVAL_SECONDS=300    # 5 minutes
LLM_HEALTH_CHECK_TIMEOUT_SECONDS=30
LLM_HEALTH_CHECK_REQUEST_TIMEOUT=15

# Health check prompts
LLM_HEALTH_CHECK_PROMPT="Test: respond with 'OK'"
LLM_HEALTH_CHECK_EXPECTED_RESPONSE="OK"
```

### Circuit Breaker Settings

#### Per-Provider Circuit Breakers

```bash
# OpenAI circuit breaker
CIRCUIT_BREAKER_OPENAI_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_OPENAI_SUCCESS_THRESHOLD=3
CIRCUIT_BREAKER_OPENAI_TIMEOUT_SECONDS=60

# Anthropic circuit breaker
CIRCUIT_BREAKER_ANTHROPIC_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_ANTHROPIC_SUCCESS_THRESHOLD=3
CIRCUIT_BREAKER_ANTHROPIC_TIMEOUT_SECONDS=60

# Gemini circuit breaker
CIRCUIT_BREAKER_GEMINI_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_GEMINI_SUCCESS_THRESHOLD=3
CIRCUIT_BREAKER_GEMINI_TIMEOUT_SECONDS=60
```

#### Circuit Breaker Actions

```bash
# What to do when circuit opens
CIRCUIT_BREAKER_ON_OPEN_ACTION=log_and_alert
CIRCUIT_BREAKER_ALERT_WEBHOOK=https://your-alerting-system.com/webhook

# Auto-recovery settings
CIRCUIT_BREAKER_AUTO_RECOVERY=true
CIRCUIT_BREAKER_RECOVERY_INTERVAL_SECONDS=600  # 10 minutes
```

---

## Testing and Validation

### Provider Connectivity Test

```bash
# Test all configured providers
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/llm/providers/health

# Test specific provider
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/llm/providers/openai/health
```

### API Key Validation

```bash
# Direct API key test for OpenAI
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
     https://api.openai.com/v1/models

# Direct API key test for Anthropic
curl -H "x-api-key: $ANTHROPIC_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"claude-3-haiku-20240307","max_tokens":10,"messages":[{"role":"user","content":"test"}]}' \
     https://api.anthropic.com/v1/messages

# Direct API key test for Gemini
curl -H "Content-Type: application/json" \
     -d '{"contents":[{"parts":[{"text":"test"}]}]}' \
     "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=$GEMINI_API_KEY"
```

### End-to-End Testing

```bash
# Test translation functionality with each provider
curl -X POST -H "Authorization: Bearer $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "provider": "openai",
       "text": "int main() { return 0; }",
       "context": "Simple C program"
     }' \
     https://api.bin2nlp.com/api/v1/llm/translate

# Test provider fallback
curl -X POST -H "Authorization: Bearer $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{
       "providers": ["openai", "anthropic", "gemini"],
       "text": "Complex assembly code here",
       "fallback_on_error": true
     }' \
     https://api.bin2nlp.com/api/v1/llm/translate-with-fallback
```

---

## Troubleshooting

### Common Issues

#### Authentication Errors

**Problem:** "Invalid API key" errors

**Solutions:**
1. **Verify API Key Format:**
   ```bash
   # OpenAI keys start with 'sk-'
   echo $LLM_OPENAI_API_KEY | head -c 3  # Should output 'sk-'
   
   # Anthropic keys start with 'sk-ant-'
   echo $LLM_ANTHROPIC_API_KEY | head -c 7  # Should output 'sk-ant-'
   
   # Gemini keys start with 'AIza'
   echo $LLM_GEMINI_API_KEY | head -c 4  # Should output 'AIza'
   ```

2. **Test API Keys Directly:**
   ```bash
   # Use the validation commands from Testing section
   ```

3. **Check Environment Variables:**
   ```bash
   # Verify environment variables are set
   env | grep LLM_
   ```

#### Rate Limiting Issues

**Problem:** "Rate limit exceeded" errors

**Solutions:**
1. **Check Current Usage:**
   ```bash
   curl -H "Authorization: Bearer $ADMIN_API_KEY" \
        https://api.bin2nlp.com/api/v1/admin/rate-limits/system
   ```

2. **Adjust Rate Limits:**
   ```bash
   # Reduce requests per minute
   LLM_OPENAI_REQUESTS_PER_MINUTE=30  # Reduce from 60
   ```

3. **Monitor Rate Limit Status:**
   ```bash
   # Check rate limit headers in responses
   curl -I -H "Authorization: Bearer $API_KEY" \
        https://api.openai.com/v1/models
   ```

#### Circuit Breaker Issues

**Problem:** Circuit breakers stuck open

**Solutions:**
1. **Check Circuit Status:**
   ```bash
   curl -H "Authorization: Bearer $ADMIN_API_KEY" \
        https://api.bin2nlp.com/api/v1/admin/circuit-breakers
   ```

2. **Manual Reset:**
   ```bash
   curl -X POST -H "Authorization: Bearer $ADMIN_API_KEY" \
        https://api.bin2nlp.com/api/v1/admin/circuit-breakers/openai/reset
   ```

3. **Adjust Thresholds:**
   ```bash
   # Increase failure threshold temporarily
   CIRCUIT_BREAKER_FAILURE_THRESHOLD=10  # Increase from 5
   ```

#### Performance Issues

**Problem:** Slow LLM responses

**Solutions:**
1. **Check Response Times:**
   ```bash
   curl -H "Authorization: Bearer $ADMIN_API_KEY" \
        https://api.bin2nlp.com/api/v1/admin/metrics/llm
   ```

2. **Optimize Model Settings:**
   ```bash
   # Reduce max tokens for faster responses
   LLM_OPENAI_MAX_TOKENS=1024  # Reduce from 2048
   
   # Use faster models
   LLM_OPENAI_MODEL=gpt-3.5-turbo  # Instead of gpt-4
   ```

3. **Enable Caching:**
   ```bash
   # Enable response caching
   LLM_ENABLE_RESPONSE_CACHE=true
   LLM_CACHE_TTL_SECONDS=3600
   ```

### Diagnostic Commands

#### Provider Status Check

```bash
# Comprehensive provider health check
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/llm/providers/status | jq .
```

#### Configuration Validation

```bash
# Validate current LLM configuration
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/config | jq .llm
```

#### Usage Analytics

```bash
# Get detailed usage statistics
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
     https://api.bin2nlp.com/api/v1/admin/analytics/llm/usage | jq .
```

---

## Best Practices

### Security

1. **API Key Management:**
   - Use environment variables, never hardcode keys
   - Rotate API keys regularly (quarterly)
   - Use different keys for different environments
   - Monitor API key usage for anomalies

2. **Network Security:**
   - Use HTTPS for all API communications
   - Implement proper firewall rules
   - Consider VPN for sensitive deployments

### Performance

1. **Model Selection:**
   - Use appropriate model for task complexity
   - Consider cost vs. quality trade-offs
   - Test different models for your use cases

2. **Caching Strategy:**
   - Enable response caching for repeated queries
   - Use appropriate cache TTL values
   - Monitor cache hit rates

3. **Resource Management:**
   - Set appropriate timeout values
   - Limit concurrent requests
   - Monitor token usage patterns

### Cost Optimization

1. **Provider Mix:**
   - Use cheaper providers for simple tasks
   - Reserve premium providers for complex analysis
   - Monitor cost per operation

2. **Usage Monitoring:**
   - Set up cost alerts
   - Review usage patterns monthly
   - Optimize prompt efficiency

---

## Configuration Templates

### Production Template

```bash
# Production LLM Configuration Template
# Copy to .env.prod and customize

# Provider Selection (enable 2-3 for redundancy)
LLM_OPENAI_ENABLED=true
LLM_ANTHROPIC_ENABLED=true
LLM_GEMINI_ENABLED=false

# Default provider
LLM_DEFAULT_PROVIDER=openai

# OpenAI Configuration
LLM_OPENAI_API_KEY=sk-your-production-key-here
LLM_OPENAI_MODEL=gpt-4
LLM_OPENAI_REQUESTS_PER_MINUTE=100
LLM_OPENAI_DAILY_SPEND_LIMIT=100.00

# Anthropic Configuration
LLM_ANTHROPIC_API_KEY=sk-ant-your-production-key-here
LLM_ANTHROPIC_MODEL=claude-3-sonnet-20240229
LLM_ANTHROPIC_REQUESTS_PER_MINUTE=75
LLM_ANTHROPIC_DAILY_SPEND_LIMIT=150.00

# Circuit Breakers (production-tuned)
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_TIMEOUT_SECONDS=300

# Monitoring
ENABLE_COST_TRACKING=true
ENABLE_PERFORMANCE_MONITORING=true
```

### Development Template

```bash
# Development LLM Configuration Template
# Copy to .env.dev and customize

# Provider Selection (cost-optimized for development)
LLM_OPENAI_ENABLED=true
LLM_ANTHROPIC_ENABLED=false
LLM_GEMINI_ENABLED=true

# Default provider
LLM_DEFAULT_PROVIDER=openai

# OpenAI Configuration (cost-optimized)
LLM_OPENAI_API_KEY=sk-your-development-key-here
LLM_OPENAI_MODEL=gpt-3.5-turbo
LLM_OPENAI_REQUESTS_PER_MINUTE=30
LLM_OPENAI_DAILY_SPEND_LIMIT=10.00

# Gemini Configuration (free tier)
LLM_GEMINI_API_KEY=AIza-your-development-key-here
LLM_GEMINI_MODEL=gemini-pro
LLM_GEMINI_REQUESTS_PER_MINUTE=30
LLM_GEMINI_DAILY_SPEND_LIMIT=5.00

# Circuit Breakers (development-tuned)
CIRCUIT_BREAKER_FAILURE_THRESHOLD=10
CIRCUIT_BREAKER_TIMEOUT_SECONDS=60

# Monitoring
ENABLE_COST_TRACKING=true
ENABLE_PERFORMANCE_MONITORING=false
```

---

**Last Updated:** 2025-08-19  
**Version:** 1.0.0  
**Next Review:** 2025-09-19

For additional support, refer to:
- [Deployment Guide](deployment.md)
- [Operational Runbooks](runbooks.md)
- [Troubleshooting Guide](troubleshooting.md)