#!/bin/bash

# Exit on error
set -e

COMPOSE_FILE="docker-compose.yml"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  MCP Crawl4AI RAG - Startup Script"
echo "=========================================="

# Step 1: Gracefully shut down existing crawl4ai containers
echo -e "\n[1/4] Gracefully shutting down existing containers..."
cd "$PROJECT_DIR"

if docker-compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | grep -q .; then
    echo "  Stopping running containers..."
    docker-compose -f "$COMPOSE_FILE" down --timeout 30
    echo "  Containers stopped."
else
    echo "  No running containers found."
fi

# Step 2: Pull latest images for services using pre-built images
echo -e "\n[2/4] Checking for image updates..."
docker-compose -f "$COMPOSE_FILE" pull --ignore-pull-failures 2>/dev/null || true
echo "  Image check complete."

# Step 3: Rebuild the mcp-crawl4ai-rag service image
echo -e "\n[3/4] Building mcp-crawl4ai-rag image..."
docker-compose -f "$COMPOSE_FILE" build mcp-crawl4ai-rag
echo "  Build complete."

# Step 4: Start all containers
echo -e "\n[4/4] Starting containers..."
docker-compose -f "$COMPOSE_FILE" up -d
echo "  Containers started."

# Show status
echo -e "\n=========================================="
echo "  Container Status"
echo "=========================================="
docker-compose -f "$COMPOSE_FILE" ps

echo -e "\nStartup complete. Tailing logs (Ctrl+C to exit)..."
docker-compose -f "$COMPOSE_FILE" logs -f
