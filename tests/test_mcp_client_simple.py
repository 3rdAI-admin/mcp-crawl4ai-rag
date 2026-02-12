import asyncio
import json
import logging
from urllib.parse import urljoin

import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import Implementation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def message_handler(message):
    """Handle incoming messages from the server."""
    if hasattr(message, 'to_dict'):
        logger.info(f"Received message: {json.dumps(message.to_dict(), indent=2)}")
    elif hasattr(message, 'model_dump'):
        logger.info(f"Received message: {json.dumps(message.model_dump(), indent=2)}")
    else:
        logger.info(f"Received message: {message}")

async def main():
    """Test connection to the MCP server using the mcp package."""
    url = "http://localhost:8054/sse"
    
    logger.info(f"Connecting to MCP server at {url}")
    
    try:
        # Create an SSE client connection
        async with sse_client(url) as (read_stream, write_stream):
            logger.info("SSE connection established")
            
            # Create a client session
            client_info = Implementation(name="mcp-test-client", version="0.1.0")
            async with ClientSession(
                read_stream,
                write_stream,
                message_handler=message_handler,
                client_info=client_info
            ) as session:
                logger.info("Client session created")
                
                # Initialize the session
                logger.info("Initializing session...")
                await session.initialize()
                logger.info("Session initialized")
                
                # List available tools
                logger.info("Listing available tools...")
                tools = await session.list_tools()
                logger.info(f"Available tools: {tools}")
                
                # Try to call a method
                try:
                    logger.info("Calling get_available_sources...")
                    result = await session.call("get_available_sources")
                    logger.info(f"Result: {result}")
                except Exception as e:
                    logger.error(f"Error calling get_available_sources: {e}")
                
                # List available resources
                try:
                    logger.info("Listing available resources...")
                    resources = await session.list_resources()
                    logger.info(f"Available resources: {resources}")
                except Exception as e:
                    logger.error(f"Error listing resources: {e}")
                
                # Keep the connection open for a while to receive messages
                logger.info("Listening for server messages (press Ctrl+C to exit)...")
                await asyncio.sleep(30)
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        logger.info("Disconnected from MCP server")

if __name__ == "__main__":
    asyncio.run(main())
