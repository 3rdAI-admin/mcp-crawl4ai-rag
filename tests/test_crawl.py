#!/usr/bin/env python3
"""
Test script to crawl a website using the MCP Crawl4AI server.
"""
import asyncio
import json
import logging
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_crawl")

async def crawl_website(url: str, max_pages: int = 1):
    """Crawl a website using the MCP Crawl4AI server."""
    mcp_url = "http://localhost:8054"
    
    try:
        logger.info(f"Connecting to MCP server at {mcp_url}...")
        
        # Create a client session with SSE transport
        async with sse_client(f"{mcp_url}/sse") as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("Connected to MCP server")
                
                logger.info(f"Crawling {url}...")
                
                # First, list available tools to verify the server is working
                tools = await session.list_tools()
                logger.info(f"Available tools: {tools}")
                
                # Call the crawl_website tool
                result = await session.call_tool(
                    "crawl_website",
                    {
                        "url": url,
                        "max_pages": max_pages,
                        "extract_metadata": True
                    }
                )
        
        # Print the result
        print("\nCrawl Results:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Save to file
        with open("crawl_results.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to crawl_results.json")
        
    except Exception as e:
        logger.error(f"Error during crawling: {e}")
        raise

if __name__ == "__main__":
    import sys
    
    # Default URL to crawl
    url = "https://ai.pydantic.dev"
    
    # Use command line argument if provided
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    asyncio.run(crawl_website(url))
