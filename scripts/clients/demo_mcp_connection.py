#!/usr/bin/env python3
"""
Working demo of connecting to the MCP Crawl4AI server.
"""
import asyncio
import logging
from urllib.parse import urljoin
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Implementation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def message_handler(message):
    """Handle incoming messages from the server."""
    if isinstance(message, Exception):
        logger.error(f"Error: {message}")
        return
    
    logger.info(f"Received message: {message}")

async def demo_connection():
    """Demonstrate MCP connection and tool usage."""
    # Server URL and endpoint - using port 8052 where Docker container is running
    base_url = "http://localhost:8052"
    endpoint = "/messages/"
    url = urljoin(base_url, endpoint)
    
    # Client information
    client_info = Implementation(name="demo-client", version="1.0.0")
    
    logger.info(f"Connecting to MCP server at: {url}")
    
    try:
        # Create SSE client and connect to the server
        async with sse_client(url) as (read_stream, write_stream):
            logger.info("✓ SSE connection established")
            
            # Create a client session
            async with ClientSession(
                read_stream,
                write_stream,
                message_handler=message_handler,
                client_info=client_info,
            ) as session:
                logger.info("✓ MCP session created")
                
                # Initialize the session
                logger.info("Initializing session...")
                await session.initialize()
                logger.info("✓ Session initialized")
                
                # List available tools
                logger.info("Listing available tools...")
                tools = await session.list_tools()
                logger.info(f"✓ Found tools: {tools}")
                
                # Call health_check tool
                logger.info("Testing health_check tool...")
                try:
                    result = await session.call_tool("health_check", {})
                    logger.info(f"✓ Health check result: {result}")
                except Exception as e:
                    logger.warning(f"Health check failed: {e}")
                
                # Call get_available_sources tool
                logger.info("Getting available sources...")
                try:
                    result = await session.call_tool("get_available_sources", {})
                    logger.info(f"✓ Available sources: {result}")
                except Exception as e:
                    logger.warning(f"Get sources failed: {e}")
                
                # Test extract_content tool with a simple URL
                logger.info("Testing extract_content tool...")
                try:
                    result = await session.call_tool("extract_content", {
                        "url": "https://example.com",
                        "strategy": "llm"
                    })
                    logger.info(f"✓ Extract content result: {result}")
                except Exception as e:
                    logger.warning(f"Extract content failed: {e}")
                
                logger.info("✓ Demo completed successfully!")
                
                # Keep the connection open for a moment
                await asyncio.sleep(2)
                
    except Exception as e:
        logger.error(f"✗ Connection failed: {e}")
        raise

async def main():
    """Main function."""
    print("=" * 60)
    print("MCP Crawl4AI Server Connection Demo")
    print("=" * 60)
    
    try:
        await demo_connection()
        
        print("\n🎉 SUCCESS! Connection to MCP server working!")
        print("\nServer Information:")
        print("  - Docker container: mcp-crawl4ai-rag")
        print("  - Base URL: http://localhost:8052")
        print("  - SSE Endpoint: http://localhost:8052/sse")
        print("  - Messages: http://localhost:8052/messages/")
        
        print("\nAvailable Tools:")
        print("  - health_check: Basic server health check")
        print("  - get_available_sources: List data sources")
        print("  - extract_content: Extract content from URLs")
        print("  - crawl_website: Crawl websites")
        print("  - search_web: Web search functionality")
        
        print("\nExample Usage:")
        print("""
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Implementation

async def use_mcp():
    client_info = Implementation("my-app", "1.0")
    
    async with sse_client("http://localhost:8052/messages/") as (read, write):
        async with ClientSession(read, write, client_info=client_info) as session:
            await session.initialize()
            
            # Extract content from a webpage
            result = await session.call_tool("extract_content", {
                "url": "https://example.com",
                "strategy": "llm"
            })
            print(result)
        """)
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        print("\nTroubleshooting:")
        print("  1. Check Docker container status: docker ps")
        print("  2. Check container logs: docker logs mcp-crawl4ai-rag")
        print("  3. Restart container: docker-compose restart")
        print("  4. Check if port 8052 is accessible: curl http://localhost:8052/sse")

if __name__ == "__main__":
    asyncio.run(main())
