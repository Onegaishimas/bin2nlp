# bin2nlp Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the bin2nlp Binary Decompilation & LLM Translation Service in various environments, from development to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Docker Deployment](#docker-deployment)
- [Scaling and Load Balancing](#scaling-and-load-balancing)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Backup and Recovery](#backup-and-recovery)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 10GB available space
- Network: Internet access for LLM provider API calls

**Recommended Production Requirements:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ SSD
- Network: High-bandwidth connection (1Gbps+)

### Software Dependencies

**Required:**
- Docker 24.0+ and Docker Compose 2.0+
- Python 3.11+ (for local development)
- Redis 7.0+ (can be containerized)
- Git (for deployment from source)

**Optional:**
- Nginx (for reverse proxy in production)
- Let's Encrypt (for SSL certificates)
- Prometheus (for metrics collection)
- Grafana (for dashboards)

### External Services

**LLM Provider APIs (choose one or more):**
- OpenAI API key (recommended)
- Anthropic Claude API key
- Google Gemini API key
- Local Ollama instance (optional)

**Domain and SSL:**
- Domain name for production deployment
- SSL certificate (Let's Encrypt recommended)

## Environment Configuration

### Environment Variables

Create a `.env` file based on the provided template:

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your configuration
nano .env
```

#### Core Configuration

```bash
# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_CORS_ORIGINS=["https://yourdomain.com"]

# Security
ENFORCE_HTTPS=true
DEFAULT_RATE_LIMIT_PER_MINUTE=100
DEFAULT_RATE_LIMIT_PER_DAY=5000

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=your_secure_password_here

# File Processing
MAX_FILE_SIZE_MB=100
DEFAULT_TIMEOUT_SECONDS=300
MAX_TIMEOUT_SECONDS=1800
```

#### LLM Provider Configuration

**OpenAI Configuration:**
```bash
# OpenAI
LLM_OPENAI_ENABLED=true
LLM_OPENAI_API_KEY=sk-your-openai-api-key-here
LLM_OPENAI_MODEL=gpt-4
LLM_OPENAI_BASE_URL=https://api.openai.com/v1
LLM_OPENAI_REQUESTS_PER_MINUTE=60
LLM_OPENAI_TOKENS_PER_MINUTE=90000
```

**Anthropic Configuration:**
```bash
# Anthropic Claude
LLM_ANTHROPIC_ENABLED=true
LLM_ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
LLM_ANTHROPIC_MODEL=claude-3-sonnet-20240229
LLM_ANTHROPIC_REQUESTS_PER_MINUTE=50
LLM_ANTHROPIC_TOKENS_PER_MINUTE=100000
```

**Google Gemini Configuration:**
```bash
# Google Gemini
LLM_GEMINI_ENABLED=true
LLM_GEMINI_API_KEY=AIza-your-gemini-key-here
LLM_GEMINI_MODEL=gemini-pro
LLM_GEMINI_REQUESTS_PER_MINUTE=60
LLM_GEMINI_TOKENS_PER_MINUTE=120000
```

## Development Deployment

### Quick Local Setup

1. **Clone and Setup:**
```bash
git clone https://github.com/your-org/bin2nlp.git
cd bin2nlp

# Create virtual environment
python3 -m venv .env-bin2nlp
source .env-bin2nlp/bin/activate

# Install dependencies
pip install -r requirements.txt
```

2. **Configure Environment:**
```bash
# Copy and edit environment file
cp .env.example .env
# Edit .env with your configuration
```

3. **Start Dependencies:**
```bash
# Start Redis with Docker
docker run -d --name bin2nlp-redis -p 6379:6379 redis:7-alpine

# Or start full development stack
docker-compose -f docker-compose.dev.yml up -d
```

4. **Run Application:**
```bash
# Start the API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Or use the development script
./scripts/dev-start.sh
```

5. **Verify Installation:**
```bash
# Check health endpoint
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

## Production Deployment

### Option 1: Docker Compose (Recommended)

#### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Reboot to apply group changes
sudo reboot
```

#### 2. Application Deployment

```bash
# Create application directory
sudo mkdir -p /opt/bin2nlp
sudo chown $USER:$USER /opt/bin2nlp
cd /opt/bin2nlp

# Clone repository
git clone https://github.com/your-org/bin2nlp.git .

# Create production environment file
cp .env.example .env.prod
nano .env.prod  # Configure your settings

# Create data directories
mkdir -p data/{redis,logs,uploads}
sudo chown -R 1000:1000 data/

# Generate strong passwords
openssl rand -base64 32 > .redis_password
chmod 600 .redis_password
```

#### 3. SSL Certificate Setup (Let's Encrypt)

```bash
# Install certbot
sudo apt install snapd
sudo snap install --classic certbot

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com

# Setup auto-renewal
sudo systemctl enable --now snap.certbot.timer
```

#### 4. Start Production Services

```bash
# Start the full production stack
docker-compose -f docker-compose.prod.yml up -d

# Verify all services are running
docker-compose ps

# Check logs
docker-compose logs -f api
```

### Option 2: Manual Installation

#### 1. System Setup

```bash
# Install Python and system dependencies
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx redis-server

# Create application user
sudo useradd -m -s /bin/bash bin2nlp
sudo usermod -aG www-data bin2nlp
```

#### 2. Application Setup

```bash
# Switch to application user
sudo -u bin2nlp -i

# Create application directory
mkdir -p /home/bin2nlp/app
cd /home/bin2nlp/app

# Clone and setup
git clone https://github.com/your-org/bin2nlp.git .
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env.prod
# Edit .env.prod with your settings
```

#### 3. System Service Setup

Create systemd service file:

```bash
sudo tee /etc/systemd/system/bin2nlp.service > /dev/null <<EOF
[Unit]
Description=bin2nlp Binary Decompilation API
After=network.target redis.service
Requires=redis.service

[Service]
Type=exec
User=bin2nlp
Group=bin2nlp
WorkingDirectory=/home/bin2nlp/app
Environment=PATH=/home/bin2nlp/app/venv/bin
ExecStart=/home/bin2nlp/app/venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000
ExecReload=/bin/kill -HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable bin2nlp
sudo systemctl start bin2nlp
sudo systemctl status bin2nlp
```

#### 4. Nginx Configuration

```bash
sudo tee /etc/nginx/sites-available/bin2nlp > /dev/null <<EOF
upstream bin2nlp_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    # Security Headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Rate Limiting
    limit_req_zone \$binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    # Proxy Settings
    location / {
        proxy_pass http://bin2nlp_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # File Upload
        client_max_body_size 100M;
    }

    # Health Check (bypass rate limiting)
    location /health {
        proxy_pass http://bin2nlp_backend;
        limit_req off;
    }

    # Static files (if any)
    location /static/ {
        alias /home/bin2nlp/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/bin2nlp /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Docker Deployment

### Docker Compose Configuration

#### Production Docker Compose

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379/0
    env_file:
      - .env.prod
    ports:
      - "8000:8000"
    volumes:
      - ./data/logs:/app/logs
      - ./data/uploads:/app/uploads
    depends_on:
      - redis
    networks:
      - bin2nlp-network
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '1.0'
          memory: 512M

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - ./data/redis:/data
    networks:
      - bin2nlp-network
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - ./data/logs/nginx:/var/log/nginx
    depends_on:
      - api
    networks:
      - bin2nlp-network

networks:
  bin2nlp-network:
    driver: bridge

volumes:
  redis-data:
    driver: local
```

### Multi-Stage Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=app:app . .

# Development stage
FROM base as development
ENV ENVIRONMENT=development
ENV DEBUG=true
USER app
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base as production
ENV ENVIRONMENT=production
ENV DEBUG=false
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## Scaling and Load Balancing

### Horizontal Scaling

#### Docker Swarm

```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.swarm.yml bin2nlp

# Scale services
docker service scale bin2nlp_api=3
docker service scale bin2nlp_redis=1  # Redis should not be scaled
```

#### Kubernetes Deployment

```yaml
# k8s/deployment.yaml
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
          value: redis://redis:6379/0
        - name: ENVIRONMENT
          value: production
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: bin2nlp-service
spec:
  selector:
    app: bin2nlp-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Load Balancing Configuration

#### Nginx Load Balancer

```nginx
upstream bin2nlp_cluster {
    least_conn;
    server api1.bin2nlp.local:8000 weight=3 max_fails=3 fail_timeout=30s;
    server api2.bin2nlp.local:8000 weight=3 max_fails=3 fail_timeout=30s;
    server api3.bin2nlp.local:8000 weight=2 max_fails=3 fail_timeout=30s;
    
    # Health check
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name api.bin2nlp.com;

    location / {
        proxy_pass http://bin2nlp_cluster;
        proxy_next_upstream error timeout http_502 http_503 http_504;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring and Health Checks

### Health Check Endpoints

The application provides several health check endpoints:

```bash
# Basic health check
curl https://yourdomain.com/health

# Detailed health with component status
curl https://yourdomain.com/health/detailed

# Readiness probe
curl https://yourdomain.com/health/ready

# Liveness probe  
curl https://yourdomain.com/health/live
```

### Prometheus Integration

#### Metrics Endpoint

```bash
# Prometheus metrics
curl https://yourdomain.com/api/v1/admin/monitoring/prometheus
```

#### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'bin2nlp'
    static_configs:
      - targets: ['api.bin2nlp.com:443']
    scheme: https
    metrics_path: /api/v1/admin/monitoring/prometheus
    bearer_token: your_admin_api_key_here
    scrape_interval: 30s
```

### Grafana Dashboard

Import the pre-built Grafana dashboard from `monitoring/grafana-dashboard.json`:

1. Open Grafana
2. Go to Dashboards > Import
3. Upload `monitoring/grafana-dashboard.json`
4. Configure Prometheus data source

### Alerting Rules

```yaml
# alerts.yml
groups:
  - name: bin2nlp
    rules:
    - alert: HighErrorRate
      expr: rate(bin2nlp_operations_total{status="failed"}[5m]) > 0.1
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: High error rate detected
        description: "Error rate is {{ $value }} requests per second"

    - alert: ServiceDown
      expr: up{job="bin2nlp"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: bin2nlp service is down
        description: "bin2nlp service has been down for more than 1 minute"
```

## Backup and Recovery

### Redis Backup

```bash
# Automated backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/bin2nlp/backups"
REDIS_HOST="localhost"
REDIS_PORT="6379"

mkdir -p $BACKUP_DIR

# Create Redis dump
redis-cli -h $REDIS_HOST -p $REDIS_PORT BGSAVE

# Wait for backup to complete
while [ $(redis-cli -h $REDIS_HOST -p $REDIS_PORT LASTSAVE) -eq $LAST_SAVE ]; do
    sleep 1
done

# Copy backup file
cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis_backup_$DATE.rdb

# Compress and clean up old backups
gzip $BACKUP_DIR/redis_backup_$DATE.rdb
find $BACKUP_DIR -name "redis_backup_*.rdb.gz" -mtime +7 -delete
```

### Configuration Backup

```bash
# Backup configuration files
tar -czf /opt/bin2nlp/backups/config_backup_$(date +%Y%m%d).tar.gz \
    .env.prod \
    docker-compose.prod.yml \
    nginx/
```

### Recovery Procedures

#### Redis Recovery

```bash
# Stop Redis
docker-compose stop redis

# Restore backup
gunzip -c /opt/bin2nlp/backups/redis_backup_YYYYMMDD.rdb.gz > /opt/bin2nlp/data/redis/dump.rdb

# Start Redis
docker-compose start redis
```

#### Full System Recovery

```bash
# 1. Restore configuration
tar -xzf config_backup_YYYYMMDD.tar.gz

# 2. Restore Redis data
# (see Redis Recovery above)

# 3. Restart services
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify system health
curl https://yourdomain.com/health/detailed
```

## Security Considerations

### Network Security

1. **Firewall Configuration:**
```bash
# UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

2. **Docker Security:**
```bash
# Run containers as non-root
USER app in Dockerfile

# Limit resources
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'

# Use secrets for sensitive data
echo "your_redis_password" | docker secret create redis_password -
```

### API Security

1. **Rate Limiting:** Configured via environment variables
2. **Authentication:** API key-based authentication
3. **HTTPS Only:** Force HTTPS in production
4. **CORS Policy:** Restrict origins in production

### Data Security

1. **Encryption at Rest:** Use encrypted storage volumes
2. **Encryption in Transit:** HTTPS/TLS for all communications
3. **Secret Management:** Use Docker secrets or Kubernetes secrets
4. **No Persistent Binary Storage:** Files are processed and discarded

## Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check logs
docker-compose logs api

# Common causes:
# 1. Environment variables missing
# 2. Redis connection failed
# 3. LLM provider API keys invalid
# 4. Port conflicts
```

#### High Memory Usage

```bash
# Monitor memory usage
docker stats

# Check for memory leaks
curl https://yourdomain.com/api/v1/admin/monitoring/health-summary

# Solutions:
# 1. Increase container memory limits
# 2. Reduce worker processes
# 3. Check for memory leaks in application logs
```

#### LLM Provider Failures

```bash
# Check circuit breaker status
curl https://yourdomain.com/api/v1/admin/circuit-breakers

# Check provider health
curl https://yourdomain.com/llm/providers/health

# Solutions:
# 1. Verify API keys
# 2. Check rate limits
# 3. Reset circuit breakers if needed
```

### Performance Optimization

1. **Database Tuning:**
```redis
# Redis optimization
maxmemory-policy allkeys-lru
tcp-keepalive 60
timeout 0
```

2. **Application Tuning:**
```bash
# Increase worker processes for CPU-bound work
API_WORKERS=8

# Tune timeouts
DEFAULT_TIMEOUT_SECONDS=300
MAX_TIMEOUT_SECONDS=1800
```

3. **System Tuning:**
```bash
# Increase file descriptor limits
echo "fs.file-max = 100000" >> /etc/sysctl.conf
echo "* soft nofile 100000" >> /etc/security/limits.conf
echo "* hard nofile 100000" >> /etc/security/limits.conf
```

### Support Resources

- **Logs Location:** `./data/logs/` (Docker) or `/var/log/bin2nlp/` (systemd)
- **Health Dashboard:** `https://yourdomain.com/dashboard/`
- **API Documentation:** `https://yourdomain.com/docs`
- **Metrics Endpoint:** `https://yourdomain.com/api/v1/admin/monitoring/prometheus`

For additional support, check the troubleshooting guide at `docs/troubleshooting.md`.

---

**Last Updated:** 2025-08-19  
**Version:** 1.0.0  
**Status:** Production Ready