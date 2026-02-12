import asyncio
import logging
import signal

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def handle_signal(signum, frame):
    logger.info(f"Received signal {signum}, shutting down...")
    # This will be caught by the asyncio event loop
    raise KeyboardInterrupt()

async def main():
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Import and run the MCP server
    from crawl4ai_mcp import mcp
    
    try:
        logger.info("Starting MCP server...")
        # Run the server with SSE transport
        mcp.run(transport='sse')
    except KeyboardInterrupt:
        logger.info("Server shutdown requested...")
    except Exception as e:
        logger.exception("Error in MCP server:")
    finally:
        logger.info("MCP server stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception("Unexpected error:")
