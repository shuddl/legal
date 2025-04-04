# Multi-stage build for Perera Construction Lead Scraper
# Stage 1: Builder - installs dependencies and sets up environment
FROM python:3.9-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-privileged user
RUN groupadd -g 1000 scraper && \
    useradd -u 1000 -g scraper -s /bin/bash -m scraper

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime - smaller image without build dependencies
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=UTC

# Create required directories
RUN mkdir -p /app/data /app/exports /app/logs

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    tini \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-privileged user
RUN groupadd -g 1000 scraper && \
    useradd -u 1000 -g scraper -s /bin/bash -m scraper

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

# Copy application code
COPY src /app/src
COPY scripts/entrypoint.sh /app/entrypoint.sh
COPY scripts/healthcheck.sh /app/healthcheck.sh

# Make scripts executable
RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh

# Set proper ownership
RUN chown -R scraper:scraper /app

# Switch to non-root user
USER scraper

# Create volume mount points owned by scraper user
VOLUME ["/app/data", "/app/exports", "/app/logs"]

# Expose the API port
EXPOSE 8000

# Set up health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/app/healthcheck.sh"]

# Use tini as init system
ENTRYPOINT ["/usr/bin/tini", "--"]

# Set default command
CMD ["/app/entrypoint.sh"]