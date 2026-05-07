# Use official Python runtime as a parent image
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gcc \
    python3-dev \
    # Required for building Python packages
    build-essential \
    # Required for SSL
    libssl-dev \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Copy only the necessary files for dependency installation
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
RUN pip install --user -r requirements.txt

# Second stage - copy only necessary files
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH="/app:/app/src" \
    PORT=8054 \
    HOST=0.0.0.0 \
    LOG_LEVEL=INFO \
    TRANSPORT=sse

# Set the working directory
WORKDIR /app

# Root CA + TLS for DuckDuckGo / HTTPS from slim image
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Make sure scripts in .local are usable
ENV PATH="/root/.local/bin:${PATH}"

# Playwright system libraries + Chromium (required for Crawl4AI / crawl_website in Docker)
RUN playwright install-deps chromium \
    && playwright install chromium

# Create log directory with proper permissions
RUN mkdir -p /app/logs /app/.cache \
    && chmod -R 777 /app/logs /app/.cache

# Expose the port the app runs on
EXPOSE 8054

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8054/health')" || exit 1

# Command to run the MCP server
CMD ["python", "run_mcp_server.py"]
