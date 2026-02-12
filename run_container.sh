#!/bin/bash

# Exit on error
set -e

echo "Building MCP Crawl4AI RAG container..."
docker-compose build --no-cache

echo -e "\nStarting container..."
docker-compose up -d

echo -e "\nContainer started. Tailing logs (Ctrl+C to exit):"
docker-compose logs -f
