#!/usr/bin/env python3
"""
Simple script to run the MCP Crawl4AI RAG server.
"""
import asyncio
import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

async def run_server():
    """Run the MCP server with SSE transport."""
    try:
        # Import the MCP instance
        from crawl4ai_mcp import mcp
        
        logger.info("Starting MCP Crawl4AI RAG server...")
        
        # Run the server with SSE transport
        # This is a blocking call
        mcp.run(transport='sse')
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception("Error running MCP server:")
    finally:
        logger.info("MCP server stopped")

if __name__ == "__main__":
    try:
        # Run the server in an asyncio event loop
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception("Unexpected error:")
        sys.exit(1)
