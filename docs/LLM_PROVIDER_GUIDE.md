# LLM Provider Setup & Configuration Guide

This guide provides comprehensive instructions for configuring and optimizing all supported LLM providers in bin2nlp.

## 📋 Overview

bin2nlp supports multiple LLM providers to ensure flexibility, cost optimization, and reliability:

- **OpenAI GPT-4**: Industry-leading technical analysis and structured explanations
- **Anthropic Claude**: Detailed, context-aware analysis with strong reasoning capabilities
- **Google Gemini**: Fast, cost-effective translations with balanced detail
- **Ollama**: Local inference for privacy, security, and zero API costs

## 🔧 Configuration Hierarchy

### 1. Environment Variables (.env)
Primary configuration method for API keys and global settings:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4
OPENAI_BASE_URL=https://api.openai.com/v1  # Optional for custom endpoints
OPENAI_ORGANIZATION=org-your-org-id  # Optional

# Anthropic Configuration  
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
ANTHROPIC_MODEL=claude-3-sonnet-20240229
ANTHROPIC_BASE_URL=https://api.anthropic.com  # Optional

# Google Gemini Configuration
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-pro

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=huihui_ai/phi4-abliterated
```

### 2. Runtime Configuration
Override per-request via API parameters:

```json
{
  "file": "binary-file-here",
  "llm_provider": "anthropic",
  "llm_model": "claude-3-haiku-20240307",
  "translation_detail": "comprehensive"
}
```

### 3. Cost Management
Configure spending limits and alerts:

```env
# Daily spending limits (USD)
OPENAI_DAILY_SPEND_LIMIT=100.0
ANTHROPIC_DAILY_SPEND_LIMIT=150.0
GEMINI_DAILY_SPEND_LIMIT=75.0

# Monthly limits (USD)
OPENAI_MONTHLY_SPEND_LIMIT=1000.0
ANTHROPIC_MONTHLY_SPEND_LIMIT=1500.0
GEMINI_MONTHLY_SPEND_LIMIT=750.0

# Alert thresholds (percentage of limit)
COST_ALERT_THRESHOLDS=25,50,75,90
```

## 🌐 Provider-Specific Setup

### OpenAI GPT-4

#### Account Setup
1. **Create Account**: Visit [OpenAI Platform](https://platform.openai.com)
2. **Billing**: Add payment method and set usage limits
3. **API Key**: Generate API key from [API Keys page](https://platform.openai.com/api-keys)

#### Configuration
```env
OPENAI_API_KEY=sk-proj-1234567890abcdef...  # Your API key
OPENAI_MODEL=gpt-4  # Recommended for best quality
OPENAI_ORGANIZATION=org-1234567890  # Optional: for organization accounts
OPENAI_DAILY_SPEND_LIMIT=100.0
OPENAI_MAX_TOKENS=4096
OPENAI_TEMPERATURE=0.1  # Low temperature for consistent technical explanations
OPENAI_TIMEOUT=30
OPENAI_MAX_RETRIES=3
```

#### Advanced Configuration
```env
# Custom endpoints (e.g., Azure OpenAI)
OPENAI_BASE_URL=https://your-resource.openai.azure.com/
OPENAI_API_VERSION=2024-02-15-preview  # For Azure
OPENAI_DEPLOYMENT_NAME=gpt-4  # Azure deployment name

# Rate limiting
OPENAI_REQUESTS_PER_MINUTE=3000
OPENAI_TOKENS_PER_MINUTE=250000
```

#### Model Selection
| Model | Best For | Cost | Speed | Quality |
|-------|----------|------|-------|---------|
| `gpt-4` | Complex binaries, detailed analysis | High | Slow | Excellent |
| `gpt-4-turbo` | Balanced performance and cost | Medium | Fast | Very Good |
| `gpt-3.5-turbo` | Simple binaries, quick analysis | Low | Very Fast | Good |

#### Troubleshooting
```bash
# Test OpenAI connection
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  https://api.openai.com/v1/models

# Common errors:
# - 401: Invalid API key
# - 429: Rate limit exceeded
# - 400: Invalid request format
```

### Anthropic Claude

#### Account Setup
1. **Create Account**: Visit [Anthropic Console](https://console.anthropic.com)
2. **API Access**: Request API access (may require approval)
3. **Billing**: Set up billing and usage limits
4. **API Key**: Generate key from Console

#### Configuration
```env
ANTHROPIC_API_KEY=sk-ant-api03-1234567890...  # Your API key
ANTHROPIC_MODEL=claude-3-sonnet-20240229  # Recommended for balanced performance
ANTHROPIC_DAILY_SPEND_LIMIT=150.0
ANTHROPIC_MAX_TOKENS=4096
ANTHROPIC_TEMPERATURE=0.1
ANTHROPIC_TIMEOUT=45  # Longer timeout for detailed responses
ANTHROPIC_MAX_RETRIES=3
```

#### Model Selection
| Model | Best For | Cost | Speed | Quality |
|-------|----------|------|-------|---------|
| `claude-3-opus-20240229` | Most complex analysis | High | Slow | Excellent |
| `claude-3-sonnet-20240229` | Balanced analysis | Medium | Medium | Very Good |
| `claude-3-haiku-20240307` | Quick analysis, simple binaries | Low | Fast | Good |

#### Troubleshooting
```bash
# Test Anthropic connection
curl -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  https://api.anthropic.com/v1/messages

# Common errors:
# - 401: Invalid API key or missing anthropic-version header
# - 429: Rate limit exceeded
# - 400: Message format issues
```

### Google Gemini

#### Account Setup
1. **Google Cloud Account**: Set up [Google Cloud Console](https://console.cloud.google.com)
2. **Enable APIs**: Enable Generative AI APIs
3. **API Key**: Create API key in [Google AI Studio](https://makersuite.google.com/app/apikey)

#### Configuration
```env
GEMINI_API_KEY=AIzaSyC1234567890...  # Your API key
GEMINI_MODEL=gemini-pro  # Primary model
GEMINI_DAILY_SPEND_LIMIT=75.0
GEMINI_MAX_TOKENS=2048
GEMINI_TEMPERATURE=0.2
GEMINI_TIMEOUT=30
GEMINI_MAX_RETRIES=2
```

#### Model Selection
| Model | Best For | Cost | Speed | Quality |
|-------|----------|------|-------|---------|
| `gemini-pro` | General purpose analysis | Low | Fast | Good |
| `gemini-pro-vision` | Binary analysis with visual elements | Medium | Medium | Good |
| `gemini-flash` | Quick, lightweight analysis | Very Low | Very Fast | Fair |

#### Troubleshooting
```bash
# Test Gemini connection
curl -H "Content-Type: application/json" \
  "https://generativelanguage.googleapis.com/v1/models?key=$GEMINI_API_KEY"

# Common errors:
# - 403: API key invalid or APIs not enabled
# - 429: Quota exceeded
# - 400: Request format issues
```

### Ollama (Local Inference)

#### Installation
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull recommended model
ollama pull huihui_ai/phi4-abliterated
```

#### Configuration
```env
OLLAMA_BASE_URL=http://localhost:11434  # Local Ollama server
OLLAMA_MODEL=huihui_ai/phi4-abliterated  # Recommended for code analysis
OLLAMA_TIMEOUT=120  # Longer timeout for local inference
OLLAMA_MAX_RETRIES=2
OLLAMA_CONCURRENT_REQUESTS=2  # Limit concurrent requests for local hardware
```

#### Model Selection
| Model | Best For | Size | RAM Required | Speed |
|-------|----------|------|--------------|-------|
| `huihui_ai/phi4-abliterated` | Code analysis | 7GB | 16GB | Medium |
| `deepseek-coder:6.7b` | Code understanding | 4GB | 8GB | Fast |
| `codellama:13b` | General code analysis | 7GB | 16GB | Medium |
| `llama2:7b` | Lightweight analysis | 4GB | 8GB | Fast |

#### Hardware Requirements
```yaml
Minimum:
  CPU: 4 cores
  RAM: 8GB
  Storage: 10GB

Recommended:
  CPU: 8+ cores
  RAM: 16GB+
  GPU: Optional (CUDA/Metal support)
  Storage: 50GB+ (for multiple models)
```

#### Troubleshooting
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# List running models
ollama list

# Check model info
ollama show huihui_ai/phi4-abliterated

# Monitor resources
ollama ps

# Common issues:
# - Connection refused: Ollama service not running
# - Out of memory: Insufficient RAM for model
# - Slow responses: CPU-bound inference
```

## ⚡ Performance Optimization

### Provider Selection Strategy

#### For Different Use Cases
```python
# Quick analysis (small files, simple binaries)
PREFERRED_PROVIDER = "gemini"  # Fast, cost-effective

# Detailed analysis (large files, complex binaries)  
PREFERRED_PROVIDER = "anthropic"  # Best reasoning capabilities

# Batch processing (many files)
PREFERRED_PROVIDER = "ollama"  # No API costs

# Production deployment
FALLBACK_CHAIN = ["openai", "anthropic", "gemini", "ollama"]
```

#### Cost Optimization
```python
# Cost per 1K tokens (approximate, as of 2024)
PROVIDER_COSTS = {
    "openai": {"gpt-4": 0.03, "gpt-3.5-turbo": 0.002},
    "anthropic": {"claude-3-opus": 0.015, "claude-3-sonnet": 0.003, "claude-3-haiku": 0.0003},
    "gemini": {"gemini-pro": 0.0005, "gemini-flash": 0.0001},
    "ollama": {"all-models": 0.0}  # No API costs
}
```

### Caching Strategy

```env
# Cache configuration
REDIS_URL=redis://localhost:6379
CACHE_TTL_SECONDS=3600  # 1 hour
CACHE_BY_FILE_HASH=true  # Cache by file hash for efficiency
CACHE_BY_PROVIDER=true  # Separate cache per provider
```

### Rate Limiting

```env
# Global rate limits
GLOBAL_REQUESTS_PER_MINUTE=100
GLOBAL_CONCURRENT_REQUESTS=10

# Provider-specific limits
OPENAI_REQUESTS_PER_MINUTE=60
ANTHROPIC_REQUESTS_PER_MINUTE=30
GEMINI_REQUESTS_PER_MINUTE=60
OLLAMA_CONCURRENT_REQUESTS=2  # Local hardware limitation
```

## 🛡️ Security & Best Practices

### API Key Management

```bash
# Use environment variables (recommended)
export OPENAI_API_KEY="sk-..."

# Use .env file (development)
echo "OPENAI_API_KEY=sk-..." >> .env

# Use secret management (production)
# AWS: AWS Secrets Manager
# Azure: Azure Key Vault
# GCP: Google Secret Manager
```

### Key Rotation

```python
# Implement key rotation
OLD_OPENAI_KEY = os.environ.get("OPENAI_API_KEY_OLD")
NEW_OPENAI_KEY = os.environ.get("OPENAI_API_KEY_NEW")

# Test new key before switching
if test_api_key(NEW_OPENAI_KEY):
    os.environ["OPENAI_API_KEY"] = NEW_OPENAI_KEY
```

### Access Control

```env
# Restrict provider access
ALLOWED_PROVIDERS=openai,anthropic  # Comma-separated list
BLOCKED_MODELS=gpt-4-32k  # Expensive models

# User-specific limits
USER_DAILY_SPEND_LIMIT=50.0
USER_REQUESTS_PER_HOUR=100
```

## 📊 Monitoring & Logging

### Health Checks

```bash
# Check all provider health
curl http://localhost:8000/api/v1/llm-providers/health

# Check specific provider
curl http://localhost:8000/api/v1/llm-providers/openai/health
```

### Metrics Collection

```env
# Enable metrics
ENABLE_METRICS=true
METRICS_PORT=9090

# Provider-specific metrics
TRACK_RESPONSE_TIMES=true
TRACK_TOKEN_USAGE=true
TRACK_COSTS=true
TRACK_ERROR_RATES=true
```

### Logging Configuration

```env
# Structured logging
LOG_FORMAT=json
LOG_LEVEL=INFO

# Provider-specific logging
LOG_LLM_REQUESTS=true  # Log all LLM requests
LOG_LLM_RESPONSES=false  # Don't log responses (sensitive data)
LOG_COSTS=true  # Track spending
```

## 🔧 Advanced Configuration

### Custom Prompts

```python
# Override default prompts per provider
CUSTOM_PROMPTS = {
    "openai": {
        "function_translation": "You are a senior reverse engineer...",
        "import_explanation": "Analyze these imported functions..."
    },
    "anthropic": {
        "function_translation": "As an expert in binary analysis...",
        "overall_summary": "Provide a comprehensive overview..."
    }
}
```

### Provider-Specific Settings

```env
# OpenAI-specific
OPENAI_FREQUENCY_PENALTY=0.0
OPENAI_PRESENCE_PENALTY=0.0
OPENAI_TOP_P=1.0

# Anthropic-specific
ANTHROPIC_STOP_SEQUENCES=["Human:", "Assistant:"]

# Gemini-specific
GEMINI_SAFETY_SETTINGS=BLOCK_MEDIUM_AND_ABOVE
GEMINI_CANDIDATE_COUNT=1
```

### Fallback Configuration

```python
# Fallback chain with conditions
FALLBACK_CONFIG = {
    "primary": "openai",
    "fallbacks": [
        {"provider": "anthropic", "condition": "rate_limit_or_error"},
        {"provider": "gemini", "condition": "cost_limit_exceeded"},
        {"provider": "ollama", "condition": "all_providers_failed"}
    ]
}
```

## 🐛 Troubleshooting Guide

### Common Issues

#### Authentication Errors
```bash
# Check API key format
echo $OPENAI_API_KEY | cut -c1-7  # Should show "sk-proj" or "sk-"

# Test key validity
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

#### Rate Limiting
```bash
# Check current usage
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/usage

# Implement exponential backoff
RETRY_DELAYS = [1, 2, 4, 8, 16]  # seconds
```

#### High Costs
```bash
# Monitor spending
curl http://localhost:8000/api/v1/usage/costs

# Optimize with cheaper models
COST_OPTIMIZATION = {
    "use_gpt_3_5_for_simple_files": True,
    "use_gemini_for_batch_processing": True,
    "use_ollama_for_development": True
}
```

#### Poor Translation Quality
```python
# Tune prompts for better results
QUALITY_IMPROVEMENTS = {
    "increase_context_length": True,
    "use_examples_in_prompts": True,
    "implement_chain_of_thought": True,
    "add_validation_steps": True
}
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export DEBUG_LLM_REQUESTS=true

# Run with debug info
uvicorn src.api.main:app --log-level debug
```

## 📈 Scaling Recommendations

### Production Deployment

```yaml
# Kubernetes deployment example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bin2nlp-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-keys
              key: openai-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### Load Balancing

```nginx
# nginx configuration for multiple providers
upstream llm_providers {
    least_conn;
    server openai-proxy:8000 weight=3;
    server anthropic-proxy:8001 weight=2;
    server gemini-proxy:8002 weight=3;
    server ollama-proxy:8003 weight=1;
}
```

### Monitoring at Scale

```python
# Implement comprehensive monitoring
MONITORING_CONFIG = {
    "prometheus_metrics": True,
    "grafana_dashboards": True,
    "alerting_rules": {
        "high_error_rate": "> 5%",
        "high_costs": "> $100/day",
        "slow_responses": "> 30s p95"
    }
}
```

## 📚 Additional Resources

### Official Documentation
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Anthropic Claude API](https://docs.anthropic.com/claude/reference)
- [Google Gemini API](https://ai.google.dev/docs)
- [Ollama Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)

### Community Resources
- [bin2nlp Discord Server](https://discord.gg/your-invite)
- [Provider Comparison Benchmarks](./BENCHMARKS.md)
- [Cost Optimization Guide](./COST_OPTIMIZATION.md)

### Support
For provider-specific issues:
- **OpenAI**: [Platform Support](https://platform.openai.com/docs/support)
- **Anthropic**: [Support Center](https://support.anthropic.com)
- **Google**: [AI Support](https://ai.google.dev/support)
- **Ollama**: [GitHub Issues](https://github.com/ollama/ollama/issues)

---

*Last updated: 2025-08-18 - Version 1.0*