# bin2nlp Deployment Guide

Complete guide for deploying the bin2nlp binary decompilation API service using Docker.

## 🚀 Quick Start

### Development Deployment
```bash
# Clone the repository
git clone <repository-url>
cd bin2nlp

# Start development environment
./scripts/deploy.sh

# Or manually with docker-compose
docker-compose up -d
```

### Production Deployment
```bash
# Set up environment configuration
cp .env.template .env
# Edit .env with your production settings

# Deploy in production mode
./scripts/deploy.sh -e production -b

# Or manually with docker-compose
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 📋 Prerequisites

### System Requirements
- **Docker**: 20.10+ with Docker Compose
- **Memory**: Minimum 4GB RAM (8GB+ recommended for production)
- **Storage**: 10GB+ free space for images and data
- **Network**: Internet access for LLM API calls

### Required API Keys
For full functionality, you'll need API keys from LLM providers:
- **OpenAI**: Get from https://platform.openai.com/api-keys
- **Anthropic**: Get from https://console.anthropic.com/
- **Google Gemini**: Get from https://makersuite.google.com/app/apikey

## 🔧 Configuration

### Environment Variables

Copy `.env.template` to `.env` and configure:

```bash
# Essential settings
APP_ENV=production
WORKERS=4

# LLM Provider API Keys (at least one required)
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here

# Security settings
API_CORS_ORIGINS=["https://yourdomain.com"]
REQUIRE_API_KEYS=true
ENFORCE_HTTPS=true
```

### Docker Compose Configurations

#### Development (`docker-compose.yml` + `docker-compose.override.yml`)
- Auto-reload enabled
- Debug mode on
- Authentication disabled
- Relaxed rate limiting
- Source code mounted for live editing

#### Production (`docker-compose.yml` + `docker-compose.prod.yml`)
- Multi-worker deployment
- Authentication required
- Strict rate limiting
- Nginx reverse proxy
- Resource limits
- Health monitoring

## 🏗️ Architecture

### Services

#### API Service
- **Image**: `bin2nlp:latest`
- **Port**: 8000
- **Resources**: 2GB RAM, 2 CPU cores
- **Health Check**: `/api/v1/health`

#### Redis Cache
- **Image**: `redis:7.2-alpine`
- **Port**: 6379 (internal)
- **Resources**: 512MB RAM
- **Data**: Persistent volume

#### Nginx Proxy (Production)
- **Image**: `nginx:1.25-alpine`
- **Ports**: 80, 443
- **Features**: Load balancing, SSL termination, rate limiting

#### Background Worker (Production)
- **Image**: `bin2nlp:latest`
- **Command**: `python -m src.workers.decompilation_worker`
- **Resources**: 4GB RAM, 2 CPU cores

### Data Volumes
```
data/
├── redis/          # Redis persistence
├── uploads/        # Temporary file uploads
├── logs/           # Application logs
└── nginx/          # Nginx logs (production)
```

## 🚀 Deployment Commands

### Using Deployment Script

```bash
# Development deployment
./scripts/deploy.sh

# Production deployment with rebuild
./scripts/deploy.sh -e production -b

# Production with latest base images
./scripts/deploy.sh -e production -b -p
```

### Using Docker Compose Directly

```bash
# Development
docker-compose up -d

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# With build
docker-compose build && docker-compose up -d
```

### Using Docker Utils

```bash
# Build images
./scripts/docker-utils.sh build

# Start services
./scripts/docker-utils.sh start

# Check health
./scripts/docker-utils.sh health

# View logs
./scripts/docker-utils.sh logs api

# Open shell
./scripts/docker-utils.sh shell

# Run tests
./scripts/docker-utils.sh test
```

## 🔍 Monitoring & Health Checks

### Health Endpoints
- **API Health**: `GET /api/v1/health`
- **System Info**: `GET /api/v1/system/info`
- **Service Status**: `./scripts/docker-utils.sh health`

### Log Monitoring
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api

# Follow API logs
./scripts/docker-utils.sh logs api
```

### Performance Monitoring
- **API Metrics**: Built-in request/response time tracking
- **Redis Monitoring**: Redis INFO command via CLI
- **Resource Usage**: `docker stats`

## 🔐 Security Configuration

### Production Security Checklist
- [ ] Set strong API keys for all LLM providers
- [ ] Configure CORS origins for your domains only
- [ ] Enable HTTPS enforcement
- [ ] Set appropriate rate limits
- [ ] Use secrets management for sensitive data
- [ ] Configure firewall rules
- [ ] Enable container security scanning

### API Key Management
```bash
# Create API key using CLI
docker-compose exec api python src/cli.py create-key username premium

# List user keys
docker-compose exec api python src/cli.py list-keys username

# Connect to admin endpoints
curl -H "Authorization: Bearer your_api_key" http://localhost:8000/api/v1/admin/stats
```

## 🔧 Troubleshooting

### Common Issues

#### Container Won't Start
```bash
# Check logs
./scripts/docker-utils.sh logs api

# Check system resources
docker system df
docker system prune  # Clean up if needed
```

#### API Health Check Fails
```bash
# Test directly
curl http://localhost:8000/api/v1/health

# Check if port is bound
netstat -tlnp | grep 8000

# Restart API service
./scripts/docker-utils.sh restart api
```

#### Redis Connection Issues
```bash
# Test Redis connectivity
./scripts/docker-utils.sh redis-cli
PING

# Check Redis logs
./scripts/docker-utils.sh logs redis

# Restart Redis
./scripts/docker-utils.sh restart redis
```

#### File Upload Issues
```bash
# Check upload directory permissions
ls -la data/uploads/

# Check file size limits
grep MAX_FILE_SIZE_MB .env

# Test with small file first
curl -X POST -F "file=@small_test.exe" http://localhost:8000/api/v1/decompile
```

### Performance Issues

#### High Memory Usage
```bash
# Check container stats
docker stats

# Reduce worker count
# Edit docker-compose.yml: WORKERS=2

# Increase memory limits
# Edit docker-compose.yml: memory: 4G
```

#### Slow Response Times
```bash
# Check API logs for slow requests
./scripts/docker-utils.sh logs api | grep "slow"

# Monitor Redis performance
./scripts/docker-utils.sh redis-cli
INFO stats

# Check LLM provider latency
curl -H "Authorization: Bearer key" http://localhost:8000/api/v1/llm-providers
```

## 🔄 Updates and Maintenance

### Updating the Service
```bash
# Pull latest code
git pull origin main

# Rebuild and restart
./scripts/deploy.sh -e production -b

# Or manually
docker-compose build
docker-compose up -d
```

### Data Backup
```bash
# Backup Redis data
docker-compose exec redis redis-cli BGSAVE

# Copy Redis dump
docker cp $(docker-compose ps -q redis):/data/dump.rdb ./backup/

# Backup configuration
cp .env ./backup/
cp docker-compose*.yml ./backup/
```

### Log Rotation
```bash
# Manual log cleanup
docker-compose exec api find /var/log/app -name "*.log" -mtime +7 -delete

# Set up automatic rotation (add to crontab)
0 2 * * * cd /path/to/bin2nlp && docker-compose exec api logrotate /etc/logrotate.conf
```

## 📊 Scaling

### Horizontal Scaling
```bash
# Scale API workers
docker-compose up -d --scale api=3

# Scale background workers
docker-compose up -d --scale worker=2
```

### Load Balancing
- Configure multiple API replicas in `docker-compose.prod.yml`
- Use nginx upstream configuration
- Consider external load balancer for multi-host deployment

### Resource Optimization
- Monitor CPU/memory usage with `docker stats`
- Adjust worker count based on load
- Tune Redis memory settings
- Configure container resource limits

## 🆘 Support

### Getting Help
- Check this deployment guide
- Review logs: `./scripts/docker-utils.sh logs`
- Test health: `./scripts/docker-utils.sh health`
- Run diagnostics: `python src/cli.py health`

### Reporting Issues
- Include deployment environment (dev/prod)
- Attach relevant logs
- Describe steps to reproduce
- Include system information: OS, Docker version, resources