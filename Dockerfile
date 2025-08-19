# Multi-stage Dockerfile for bin2nlp Production Deployment
# Creates optimized containers for the binary decompilation API service

# Stage 1: Build environment with all build tools
FROM python:3.11-slim as builder

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies and radare2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    wget \
    curl \
    pkg-config \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install radare2 from source for latest features
RUN git clone https://github.com/radareorg/radare2.git /tmp/radare2 \
    && cd /tmp/radare2 \
    && ./sys/install.sh \
    && rm -rf /tmp/radare2

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /tmp/requirements.txt

# Stage 2: Production runtime image
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    WORKERS=4

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy radare2 installation from builder
COPY --from=builder /usr/local/bin/r* /usr/local/bin/
COPY --from=builder /usr/local/lib/libr* /usr/local/lib/
COPY --from=builder /usr/local/share/radare2 /usr/local/share/radare2
COPY --from=builder /usr/local/include/libr /usr/local/include/libr

# Update library cache
RUN ldconfig

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1001 appuser \
    && mkdir -p /app /tmp/uploads /var/log/app \
    && chown -R appuser:appgroup /app /tmp/uploads /var/log/app

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appgroup . .

# Install the application in development mode
RUN pip install -e .

# Create startup script with proper error handling
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Check if radare2 is working\n\
echo "Checking radare2 installation..."\n\
r2 -v || (echo "ERROR: radare2 not working" && exit 1)\n\
\n\
# Check Python environment\n\
echo "Checking Python environment..."\n\
python -c "from src.api.main import create_app; print('\''API ready'\'')" || (echo "ERROR: API not working" && exit 1)\n\
\n\
# Start the application\n\
echo "Starting bin2nlp API server..."\n\
if [ "$APP_ENV" = "development" ]; then\n\
    echo "Running in development mode"\n\
    uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload\n\
else\n\
    echo "Running in production mode with $WORKERS workers"\n\
    uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8000 --workers $WORKERS\n\
fi\n' > /app/start.sh \
    && chmod +x /app/start.sh \
    && chown appuser:appgroup /app/start.sh

# Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command
CMD ["/app/start.sh"]

# Labels for metadata
LABEL org.opencontainers.image.title="bin2nlp" \
      org.opencontainers.image.description="Binary Decompilation & Multi-LLM Translation API Service" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="bin2nlp development team" \
      org.opencontainers.image.source="https://github.com/example/bin2nlp" \
      org.opencontainers.image.documentation="https://github.com/example/bin2nlp/blob/main/README.md"