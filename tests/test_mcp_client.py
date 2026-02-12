#!/usr/bin/env python3
"""
Test script to interact with the MCP Crawl4AI RAG server.
"""
import asyncio
import logging
from mcp.client.client import MCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_mcp_server():
    """Test the MCP server by listing tools and making a simple request."""
    # Connect to the MCP server
    server_url = "http://localhost:8054"
    logger.info(f"Connecting to MCP server at {server_url}")
    
    async with MCPClient(server_url) as client:
        try:
            # List available tools
            logger.info("Listing available tools...")
            tools = await client.list_tools()
            logger.info(f"Available tools: {[tool.name for tool in tools]}")
            
            # Get tool schema for crawl_website
            crawl_tool = next((t for t in tools if t.name == "crawl_website"), None)
            if crawl_tool:
                logger.info(f"Found crawl_website tool: {crawl_tool}")
                
                # Call the crawl_website tool
                logger.info("Calling crawl_website tool...")
                result = await client.call_tool(
                    "crawl_website",
                    {"url": "https://example.com", "max_pages": 1, "extract_metadata": True}
                )
                logger.info(f"Crawl result: {result}")
            else:
                logger.warning("crawl_website tool not found")
            
            # Try to search the web
            search_tool = next((t for t in tools if t.name == "search_web"), None)
            if search_tool:
                logger.info(f"Found search_web tool: {search_tool}")
                
                # Call the search_web tool
                logger.info("Calling search_web tool...")
                result = await client.call_tool(
                    "search_web",
                    {"query": "MCP Crawl4AI RAG server", "limit": 3}
                )
                logger.info(f"Search result: {result}")
            else:
                logger.warning("search_web tool not found")
                
        except Exception as e:
            logger.error(f"Error testing MCP server: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_mcp_server())
