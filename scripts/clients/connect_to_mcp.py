import asyncio
import logging
from urllib.parse import urljoin

import httpx
from httpx_sse import aconnect_sse
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import Implementation

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def message_handler(message):
    """Handle incoming messages from the server."""
    if isinstance(message, Exception):
        logger.error(f"Error: {message}")
        return
    
    logger.info(f"Received message: {message}")

async def main():
    # Server URL and endpoint
    base_url = "http://localhost:8054"
    endpoint = "/messages/"
    url = urljoin(base_url, endpoint)
    
    # Client information
    client_info = Implementation(name="test-client", version="0.1.0")
    
    # Create SSE client and connect to the server
    async with sse_client(url) as (read_stream, write_stream):
        # Create a client session
        async with ClientSession(
            read_stream,
            write_stream,
            message_handler=message_handler,
            client_info=client_info,
        ) as session:
            # Initialize the session
            logger.info("Initializing session...")
            await session.initialize()
            
            # List available tools
            logger.info("Listing available tools...")
            tools = await session.list_tools()
            logger.info(f"Available tools: {tools}")
            
            # Call get_available_sources tool
            logger.info("Getting available sources...")
            result = await session.call_tool("get_available_sources", {})
            logger.info(f"Available sources: {result}")
            
            # Keep the connection open for a while to receive messages
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
