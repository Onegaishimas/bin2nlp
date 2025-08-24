# bin2nlp - Binary Decompilation & Multi-LLM Translation Service

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)

**bin2nlp** is a production-ready API service that transforms binary reverse engineering into automated decompilation and natural language translation, providing rich, human-readable explanations of binary functionality through configurable LLM providers.

## 🎯 What It Does

**bin2nlp** converts binary files into structured, natural language explanations by:

1. **Decompiling** binary files using radare2 to extract functions, imports, and strings
2. **Translating** assembly code into human-readable explanations using multiple LLM providers
3. **Structuring** results as clean JSON for consumption by security tools, documentation generators, and analysis systems

## ✨ Key Features

### 🧠 Multi-LLM Provider Support
- **OpenAI GPT-4**: Technical, structured explanations
- **Anthropic Claude**: Detailed, context-aware analysis  
- **Google Gemini**: Balanced, practical translations
- **Ollama**: Local inference with privacy and cost control
- **Intelligent fallback** chains and provider selection

### 📊 Comprehensive Binary Support
- **Windows**: PE executables (.exe), DLLs (.dll)
- **Linux**: ELF executables, shared libraries (.so)
- **macOS**: Mach-O executables (.app), dynamic libraries (.dylib)
- **Multi-architecture**: x86, x86_64, ARM, ARM64

### 🚀 Production-Ready Architecture
- **FastAPI** with automatic OpenAPI documentation
- **File-based caching** with configurable TTL
- **Async processing** with background job queues
- **Docker containerization** for scalable deployment
- **Comprehensive testing** including real LLM integration

### 🔧 Advanced Configuration
- **Cost management** with daily/monthly spending limits
- **Rate limiting** and provider health monitoring
- **Quality assessment** with translation scoring
- **Flexible prompting** with provider-specific optimization

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- PostgreSQL (included in Docker setup)
- API keys for desired LLM providers

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-org/bin2nlp.git
cd bin2nlp
```

2. **Set up environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure LLM providers**
```bash
cp .env.example .env
# Edit .env with your API keys
```

4. **Start services**
```bash
docker-compose up -d  # Start PostgreSQL and other services
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

5. **Verify installation**
```bash
curl http://localhost:8000/health
```

## 📖 API Usage

### Basic Decompilation + Translation

```bash
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.exe" \
  -F "llm_provider=openai" \
  -F "translation_detail=standard"
```

### Response Structure

```json
{
  "job_id": "uuid-here",
  "status": "completed",
  "decompilation_results": {
    "metadata": {
      "file_hash": "sha256-hash",
      "file_format": "pe",
      "architecture": "x86_64",
      "total_functions": 45,
      "total_imports": 23,
      "processing_time": 12.5
    },
    "functions": [
      {
        "name": "main",
        "address": "0x401000",
        "disassembly": "push rbp; mov rbp, rsp; ...",
        "decompiled_code": "int main() { ... }"
      }
    ],
    "imports": [
      {
        "library": "kernel32.dll",
        "function": "CreateFileW",
        "address": "0x402000"
      }
    ],
    "strings": [
      {
        "content": "Configuration loaded",
        "address": "0x403000",
        "encoding": "utf-8"
      }
    ]
  },
  "translation_results": {
    "overall_summary": {
      "program_purpose": "This appears to be a configuration management utility...",
      "key_behaviors": [
        "Reads configuration files from multiple sources",
        "Validates configuration syntax and structure",
        "Provides command-line interface for configuration management"
      ],
      "security_considerations": "Uses standard Windows APIs with proper error handling..."
    },
    "function_translations": [
      {
        "function_name": "main",
        "natural_language": "This is the main entry point that initializes the configuration system...",
        "purpose": "Application entry point and initialization",
        "parameters": ["argc: command line argument count", "argv: command line arguments"]
      }
    ],
    "llm_provider": "openai",
    "llm_model": "gpt-4",
    "total_tokens_used": 2847,
    "estimated_cost": 0.14,
    "processing_time": 8.2
  }
}
```

### Configuration Options

| Parameter | Description | Options |
|-----------|-------------|---------|
| `llm_provider` | LLM provider for translation | `openai`, `anthropic`, `gemini`, `ollama` |
| `llm_model` | Specific model (optional) | `gpt-4`, `claude-3-sonnet-20240229`, `gemini-pro` |
| `translation_detail` | Level of explanation detail | `brief`, `standard`, `comprehensive` |
| `decompilation_depth` | Analysis thoroughness | `basic`, `standard`, `comprehensive` |
| `timeout_seconds` | Processing timeout | `60-1800` (1-30 minutes) |

## 🔧 Configuration

### LLM Provider Setup

Create a `.env` file with your API keys:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4
OPENAI_DAILY_SPEND_LIMIT=100.0

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
ANTHROPIC_MODEL=claude-3-sonnet-20240229
ANTHROPIC_DAILY_SPEND_LIMIT=150.0

# Google Gemini Configuration
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-pro
GEMINI_DAILY_SPEND_LIMIT=75.0

# Ollama Configuration (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=huihui_ai/phi4-abliterated

# System Configuration
DATABASE_URL=postgresql://bin2nlp:bin2nlp_password@localhost:5432/bin2nlp
MAX_FILE_SIZE_MB=100
ANALYSIS_TIMEOUT_SECONDS=1800
LOG_LEVEL=INFO
```

### Provider-Specific Setup

#### OpenAI
1. Get API key from [OpenAI Platform](https://platform.openai.com)
2. Set `OPENAI_API_KEY` in environment
3. Configure spending limits and model preferences

#### Anthropic Claude
1. Get API key from [Anthropic Console](https://console.anthropic.com)
2. Set `ANTHROPIC_API_KEY` in environment
3. Note: Requires separate billing account

#### Google Gemini
1. Get API key from [Google AI Studio](https://makersuite.google.com)
2. Set `GEMINI_API_KEY` in environment
3. Enable Generative AI APIs in Google Cloud Console

#### Ollama (Local)
1. Install [Ollama](https://ollama.ai)
2. Pull desired model: `ollama pull huihui_ai/phi4-abliterated`
3. Start Ollama service: `ollama serve`

### Cost Management

All providers support cost controls:

```python
# Daily spending limits
OPENAI_DAILY_SPEND_LIMIT=100.0
ANTHROPIC_DAILY_SPEND_LIMIT=150.0
GEMINI_DAILY_SPEND_LIMIT=75.0

# Monthly limits
OPENAI_MONTHLY_SPEND_LIMIT=1000.0
ANTHROPIC_MONTHLY_SPEND_LIMIT=1500.0

# Alert thresholds (percentage of limit)
COST_ALERT_THRESHOLDS=25,50,75,90
```

## 🐳 Docker Deployment

### Development Setup

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Scale workers
docker-compose up -d --scale decompiler-worker=3
```

### Production Deployment

```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://bin2nlp:bin2nlp_password@database:5432/bin2nlp
    ports:
      - "8000:8000"
    depends_on:
      - database
      - decompiler-worker
    restart: unless-stopped

  decompiler-worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - DATABASE_URL=postgresql://bin2nlp:bin2nlp_password@database:5432/bin2nlp
    depends_on:
      - database
    restart: unless-stopped
    deploy:
      replicas: 3

  database:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: bin2nlp
      POSTGRES_USER: bin2nlp
      POSTGRES_PASSWORD: bin2nlp_password
    volumes:
      - postgres-data:/var/lib/postgresql/data
    restart: unless-stopped
```

## 🧪 Testing

### Run Test Suite

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires services)
docker-compose up -d
pytest tests/integration/ -v --slow

# Performance tests
pytest tests/performance/ -v

# Full test suite with coverage
pytest tests/ -v --cov=src --cov-report=html
```

### Test with Real LLM Providers

```bash
# Test with OpenAI (requires API key)
pytest tests/integration/test_openai_integration.py -v

# Test with Ollama (requires local Ollama)
pytest tests/integration/test_ollama_integration.py -v
```

## 📊 Performance & Scaling

### Expected Performance

| File Size | Processing Time | Memory Usage | Cost (OpenAI) |
|-----------|----------------|--------------|---------------|
| ≤10MB     | 30-60 seconds  | 512MB        | $0.10-0.50    |
| ≤30MB     | 2-5 minutes    | 1GB          | $0.50-2.00    |
| ≤100MB    | 5-20 minutes   | 2GB          | $2.00-8.00    |

### Scaling Configuration

```bash
# Horizontal scaling
docker-compose up -d --scale api=3 --scale decompiler-worker=5

# Resource limits
docker-compose.override.yml:
services:
  api:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
  decompiler-worker:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
```

## 🔍 Monitoring & Debugging

### Health Endpoints

```bash
# System health
curl http://localhost:8000/health

# LLM provider status
curl http://localhost:8000/api/v1/llm-providers/health

# Cache status
curl http://localhost:8000/api/v1/cache/stats
```

### Logging Configuration

```python
# src/core/config.py
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json  # json, text
STRUCTURED_LOGGING=true
```

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export ENVIRONMENT=development

# Start with auto-reload
uvicorn src.api.main:app --reload --log-level debug
```

## 🛡️ Security Considerations

### API Security
- **Input validation** via Pydantic models
- **File type verification** using Magika ML-based detection
- **Size limits** and timeout protection
- **Sandboxed execution** in isolated containers

### Data Privacy
- **No persistent storage** of binary files
- **Temporary file cleanup** after processing
- **File storage TTL** ensures automatic data expiration
- **Optional local LLM** support via Ollama

### LLM Provider Security
- **API key validation** and rotation support
- **Rate limiting** to prevent abuse
- **Cost controls** with automatic cutoffs
- **Provider health monitoring** with fallback

## 🤝 Contributing

### Development Setup

1. **Fork and clone** the repository
2. **Create virtual environment**: `python -m venv venv`
3. **Install dev dependencies**: `pip install -r requirements-dev.txt`
4. **Set up pre-commit hooks**: `pre-commit install`
5. **Run tests**: `pytest`

### Code Standards

- **Python 3.11+** with type hints
- **Black** code formatting
- **isort** import sorting
- **mypy** static type checking
- **pytest** for testing (85% coverage minimum)

### Pull Request Process

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes with tests: `pytest tests/`
3. Run code quality checks: `make lint`
4. Submit PR with clear description

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- **API Documentation**: http://localhost:8000/docs (when running)
- **Project PRDs**: [/prds/](./prds/)
- **Architecture Decisions**: [/adrs/](./adrs/)

### Issues
- **Bug Reports**: [GitHub Issues](https://github.com/your-org/bin2nlp/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/your-org/bin2nlp/discussions)

### Community
- **Discord**: [Join our community](https://discord.gg/your-invite)
- **Twitter**: [@bin2nlp](https://twitter.com/bin2nlp)

---

**Built with ❤️ for the reverse engineering and security analysis community**