import sys
print('PYTHON EXECUTABLE:', sys.executable)
print('PYTHONPATH:', sys.path)
print("=== RUN_MCP_SERVER.PY STARTED ===")
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("run_mcp_server")
logger.info("Starting run_mcp_server")

#!/usr/bin/env python3
"""
Script to run the MCP Crawl4AI RAG server with the correct transport.
"""
import asyncio
import os
import uvicorn
from starlette.responses import JSONResponse
from starlette.routing import Route
from src.crawl4ai_mcp import mcp

async def main():
    """Run the MCP server with the configured transport."""
    transport = os.getenv("TRANSPORT", "sse").lower()
    
    if transport == 'sse':
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8054"))
        print(f"Starting MCP Crawl4AI RAG server on {host}:{port} with SSE transport")
        logger.info(f"Starting MCP Crawl4AI RAG server on {host}:{port} with SSE transport")
        
        # Get the Starlette app from the MCP instance
        app = mcp.sse_app()

        # Add /health endpoint for Docker healthcheck
        async def health(request):
            import datetime
            return JSONResponse({"status": "ok", "time": datetime.datetime.utcnow().isoformat()})

        app.routes.insert(0, Route("/health", health))
        
        # Configure and run the Uvicorn server
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="debug"
        )
        server = uvicorn.Server(config)
        await server.serve()
    else:
        print("Starting MCP Crawl4AI RAG server with stdio transport")
        logger.info("Starting MCP Crawl4AI RAG server with stdio transport")
        await mcp.run_stdio_async()

if __name__ == "__main__":
    asyncio.run(main())
