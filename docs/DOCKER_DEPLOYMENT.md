# Docker Deployment Guide

This guide covers containerized deployment of bin2nlp for development, staging, and production environments with multi-LLM provider support.

## 📋 Overview

bin2nlp uses a multi-container architecture for scalable, secure deployment:

- **API Container**: FastAPI application with LLM provider integrations
- **Worker Containers**: radare2-enabled decompilation processors  
- **Redis Container**: Cache and job queue management
- **Load Balancer**: nginx for production deployments

## 🏗️ Architecture

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │     (nginx)     │
                    └──────┬──────────┘
                           │
                  ┌────────┴────────┐
                  │   API Servers   │
                  │   (FastAPI)     │
                  │  ┌─────┐ ┌─────┐│
                  │  │ API │ │ API ││
                  │  │  1  │ │  2  ││
                  │  └─────┘ └─────┘│
                  └────────┬────────┘
                           │
                    ┌──────┴──────┐
                    │    Redis    │
                    │   (Cache)   │
                    └──────┬──────┘
                           │
                  ┌────────┴────────┐
                  │    Workers      │
                  │  ┌─────┐ ┌─────┐│
                  │  │ W1  │ │ W2  ││
                  │  │(r2) │ │(r2) ││
                  │  └─────┘ └─────┘│
                  └─────────────────┘
```

## 🚀 Quick Start

### Development Setup

```bash
# Clone repository
git clone https://github.com/your-org/bin2nlp.git
cd bin2nlp

# Create environment file
cp .env.example .env
# Edit .env with your LLM provider API keys

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Test the service
curl http://localhost:8000/health
```

### Production Setup

```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale api=3 --scale worker=5

# Monitor
docker-compose -f docker-compose.prod.yml logs -f
```

## 📁 Docker Files

### Main Application Dockerfile

```dockerfile
# Dockerfile.api
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY pyproject.toml pytest.ini ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Worker Dockerfile

```dockerfile  
# Dockerfile.worker
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including radare2
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    pkg-config \
    libssl-dev \
    && wget -O - https://github.com/radareorg/radare2/releases/download/5.8.8/radare2_5.8.8_amd64.deb \
    && dpkg -i radare2_5.8.8_amd64.deb \
    && rm radare2_5.8.8_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY pyproject.toml ./

# Create non-root user with radare2 access
RUN useradd --create-home --shell /bin/bash worker \
    && chown -R worker:worker /app
USER worker

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD python -c "import redis; r=redis.from_url('redis://redis:6379'); r.ping()" || exit 1

# Run worker
CMD ["python", "-m", "src.decompilation.worker"]
```

## 🐳 Docker Compose Configurations

### Development (docker-compose.yml)

```yaml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=DEBUG
    env_file:
      - .env
    depends_on:
      - redis
    volumes:
      - .:/app  # Mount for development
      - /tmp:/tmp  # Temporary files
    restart: unless-stopped
    networks:
      - bin2nlp-network

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - ENVIRONMENT=development
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=DEBUG
    env_file:
      - .env
    depends_on:
      - redis
    volumes:
      - /tmp:/tmp  # Temporary files
    restart: unless-stopped
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '1.0'
    networks:
      - bin2nlp-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
    networks:
      - bin2nlp-network
    command: redis-server --save "" --appendonly no  # No persistence for development

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.dev.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - api
    restart: unless-stopped
    networks:
      - bin2nlp-network

volumes:
  redis-data:

networks:
  bin2nlp-network:
    driver: bridge
```

### Production (docker-compose.prod.yml)

```yaml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    env_file:
      - .env.prod
    depends_on:
      - redis
    restart: unless-stopped
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - bin2nlp-network

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    env_file:
      - .env.prod
    depends_on:
      - redis
    restart: unless-stopped
    deploy:
      replicas: 5
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '1.0'
    networks:
      - bin2nlp-network

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
    networks:
      - bin2nlp-network
    command: redis-server /usr/local/etc/redis/redis.conf

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: unless-stopped
    networks:
      - bin2nlp-network

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    restart: unless-stopped
    networks:
      - bin2nlp-network

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    restart: unless-stopped
    networks:
      - bin2nlp-network

volumes:
  redis-data:
  prometheus-data:
  grafana-data:

networks:
  bin2nlp-network:
    driver: bridge
```

## ⚙️ Configuration Files

### nginx Development Configuration

```nginx
# nginx.dev.conf
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    server {
        listen 80;
        
        client_max_body_size 100M;
        
        location / {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeout settings for large file uploads
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }
        
        location /health {
            proxy_pass http://api/health;
            access_log off;
        }
    }
}
```

### nginx Production Configuration

```nginx
# nginx.prod.conf
events {
    worker_connections 1024;
}

http {
    upstream api {
        least_conn;
        server api_1:8000 weight=3 max_fails=3 fail_timeout=30s;
        server api_2:8000 weight=3 max_fails=3 fail_timeout=30s;
        server api_3:8000 weight=3 max_fails=3 fail_timeout=30s;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    # SSL configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;
        
        client_max_body_size 100M;
        
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        
        location / {
            limit_req zone=api burst=20 nodelay;
            
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeout settings
            proxy_connect_timeout 60s;
            proxy_send_timeout 300s;
            proxy_read_timeout 300s;
        }
        
        location /health {
            proxy_pass http://api/health;
            access_log off;
        }
        
        location /metrics {
            proxy_pass http://api/metrics;
            allow 10.0.0.0/8;
            deny all;
        }
    }
}
```

### Redis Configuration

```conf
# redis.conf
# Network
bind 0.0.0.0
port 6379
protected-mode no

# Memory
maxmemory 200mb
maxmemory-policy allkeys-lru

# Persistence (disabled for production cache)
save ""
appendonly no

# Logging
loglevel notice

# Security
requirepass your-redis-password

# Performance
tcp-keepalive 60
timeout 300
```

## 🔐 Environment Configuration

### Development (.env)

```env
# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Redis
REDIS_URL=redis://redis:6379

# LLM Providers
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GEMINI_API_KEY=your-gemini-key
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Cost Management
OPENAI_DAILY_SPEND_LIMIT=10.0
ANTHROPIC_DAILY_SPEND_LIMIT=15.0
GEMINI_DAILY_SPEND_LIMIT=5.0

# System Settings
MAX_FILE_SIZE_MB=100
ANALYSIS_TIMEOUT_SECONDS=1800
WORKER_CONCURRENCY=2
```

### Production (.env.prod)

```env
# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO

# Redis
REDIS_URL=redis://:your-redis-password@redis:6379

# LLM Providers (use secret management in production)
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
GEMINI_API_KEY=${GEMINI_API_KEY}

# Cost Management
OPENAI_DAILY_SPEND_LIMIT=100.0
ANTHROPIC_DAILY_SPEND_LIMIT=150.0
GEMINI_DAILY_SPEND_LIMIT=75.0

# System Settings
MAX_FILE_SIZE_MB=100
ANALYSIS_TIMEOUT_SECONDS=1800
WORKER_CONCURRENCY=5

# Security
SECRET_KEY=${SECRET_KEY}
CORS_ORIGINS=https://your-frontend.com

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
```

## 🚀 Deployment Commands

### Development Deployment

```bash
# Start development environment
docker-compose up -d

# View logs
docker-compose logs -f

# Scale workers
docker-compose up -d --scale worker=4

# Restart specific service
docker-compose restart api

# Stop all services
docker-compose down
```

### Production Deployment

```bash
# Initial deployment
docker-compose -f docker-compose.prod.yml up -d

# Rolling update
docker-compose -f docker-compose.prod.yml up -d --no-deps api

# Scale for high load
docker-compose -f docker-compose.prod.yml up -d --scale api=5 --scale worker=10

# Health check
docker-compose -f docker-compose.prod.yml exec api curl http://localhost:8000/health

# View metrics
curl http://localhost:9090/metrics
```

### Zero-Downtime Deployment

```bash
#!/bin/bash
# deploy.sh - Zero-downtime deployment script

set -e

echo "Starting zero-downtime deployment..."

# Build new images
docker-compose -f docker-compose.prod.yml build

# Deploy with rolling update
docker-compose -f docker-compose.prod.yml up -d --no-deps --scale api=6 api
sleep 30

# Health check new instances
for i in {1..6}; do
  if ! docker-compose -f docker-compose.prod.yml exec -T api curl -f http://localhost:8000/health; then
    echo "Health check failed for new instance"
    exit 1
  fi
done

# Scale down old instances
docker-compose -f docker-compose.prod.yml up -d --no-deps --scale api=3 api

echo "Deployment completed successfully"
```

## 🔍 Monitoring and Logging

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'bin2nlp-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:80']
```

### Logging Configuration

```yaml
# logging.yml
version: 1
formatters:
  json:
    class: pythonjsonlogger.jsonlogger.JsonFormatter
    format: '%(asctime)s %(name)s %(levelname)s %(message)s'
  
handlers:
  console:
    class: logging.StreamHandler
    formatter: json
    stream: ext://sys.stdout
  
loggers:
  src:
    level: INFO
    handlers: [console]
    propagate: false
    
root:
  level: WARNING
  handlers: [console]
```

### Docker Logging

```bash
# Configure log rotation
echo '{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}' | sudo tee /etc/docker/daemon.json

# View logs with timestamps
docker-compose logs -f -t api

# Export logs for analysis
docker-compose logs --no-color api > api.log
```

## 🛡️ Security Considerations

### Container Security

```dockerfile
# Security best practices in Dockerfile
FROM python:3.11-slim

# Update packages
RUN apt-get update && apt-get upgrade -y

# Create non-root user
RUN groupadd -r app && useradd -r -g app app

# Set secure file permissions
COPY --chown=app:app src/ ./src/
USER app

# Use specific versions
RUN pip install --no-cache-dir -r requirements.txt

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

### Network Security

```yaml
# Network isolation in docker-compose
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access

services:
  nginx:
    networks:
      - frontend
      
  api:
    networks:
      - frontend
      - backend
      
  worker:
    networks:
      - backend  # No external access
      
  redis:
    networks:
      - backend  # No external access
```

### Secret Management

```bash
# Using Docker secrets (Docker Swarm)
echo "your-openai-key" | docker secret create openai_api_key -

# In docker-compose.yml
services:
  api:
    secrets:
      - openai_api_key
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key

secrets:
  openai_api_key:
    external: true
```

## 📊 Performance Optimization

### Resource Allocation

```yaml
# Optimized resource limits
services:
  api:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
      
  worker:
    deploy:
      resources:
        limits:
          memory: 2G      # radare2 needs more memory
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '1.0'
          
  redis:
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
```

### Scaling Guidelines

```bash
# Auto-scaling based on metrics
# CPU usage > 70% for 2 minutes
docker service update --replicas=5 bin2nlp_api

# Memory usage > 80%
docker service update --replicas=3 bin2nlp_worker

# Queue length > 50 jobs
docker-compose up -d --scale worker=10
```

## 🐛 Troubleshooting

### Common Issues

#### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Check resource usage
docker stats

# Rebuild image
docker-compose build --no-cache api
```

#### High Memory Usage

```bash
# Monitor memory by container
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Adjust resource limits
# In docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 1G
```

#### Network Connectivity Issues

```bash
# Test container networking
docker-compose exec api ping redis

# Check port bindings
docker-compose ps

# Inspect network
docker network inspect bin2nlp_default
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Redis health
docker-compose exec redis redis-cli ping

# Worker health
docker-compose exec worker python -c "import redis; r=redis.from_url('redis://redis:6379'); print('OK' if r.ping() else 'FAIL')"
```

### Performance Monitoring

```bash
# Monitor container resources
docker stats

# Check API response times
curl -w "@curl-format.txt" -s -o /dev/null http://localhost:8000/api/v1/decompile

# Monitor Redis performance
docker-compose exec redis redis-cli --latency-history

# Check nginx access logs
docker-compose logs nginx | grep "POST /api/v1/decompile"
```

## 🚀 Advanced Deployments

### Kubernetes Deployment

```yaml
# k8s-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bin2nlp-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: bin2nlp-api
  template:
    metadata:
      labels:
        app: bin2nlp-api
    spec:
      containers:
      - name: api
        image: bin2nlp:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis:6379"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: openai-key
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Cloud Deployment

```bash
# AWS ECS deployment
aws ecs create-cluster --cluster-name bin2nlp

# Build and push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker build -t bin2nlp-api -f Dockerfile.api .
docker tag bin2nlp-api:latest $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/bin2nlp-api:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/bin2nlp-api:latest

# Deploy service
aws ecs create-service --cluster bin2nlp --service-name bin2nlp-api --task-definition bin2nlp-api --desired-count 3
```

---

## 📚 Additional Resources

- **Docker Documentation**: [https://docs.docker.com](https://docs.docker.com)
- **Docker Compose Reference**: [https://docs.docker.com/compose](https://docs.docker.com/compose)
- **nginx Configuration**: [https://nginx.org/en/docs](https://nginx.org/en/docs)
- **Redis Configuration**: [https://redis.io/documentation](https://redis.io/documentation)
- **Prometheus Monitoring**: [https://prometheus.io/docs](https://prometheus.io/docs)

For deployment issues, check our [Troubleshooting Guide](./TROUBLESHOOTING.md) or [GitHub Issues](https://github.com/your-org/bin2nlp/issues).

*Last updated: 2025-08-18*