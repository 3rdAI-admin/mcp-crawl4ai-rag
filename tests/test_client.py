#!/usr/bin/env python3
"""Test script for MCP Crawl4AI client."""

import asyncio
import json
import logging
from mcp_client import MCPCrawl4AIClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_client():
    """Test the MCP client by listing tools and calling a simple tool."""
    client = None
    try:
        # Create and connect the client
        client = MCPCrawl4AIClient(base_url="http://localhost:8054")
        await client.connect()
        
        # List available tools
        logger.info("Listing available tools...")
        try:
            tools = await client.list_tools()
            print("\n=== Available Tools ===")
            if not tools:
                print("No tools found or error retrieving tools.")
            else:
                for tool in tools:
                    print(f"- {tool.get('name')}: {tool.get('description')}")
                
                # Test calling the first tool as an example
                if tools:
                    tool_name = tools[0].get('name')
                    logger.info(f"\nTesting tool: {tool_name}")
                    
                    # Prepare parameters based on the tool name
                    params = {}
                    if "crawl" in tool_name.lower():
                        params = {"url": "https://example.com", "max_pages": 1}
                    elif "extract" in tool_name.lower():
                        params = {"url": "https://example.com"}
                    elif "search" in tool_name.lower():
                        params = {"query": "test search"}
                    else:
                        params = {}
                    
                    # Call the tool
                    print(f"\n=== Testing {tool_name} ===")
                    print(f"Parameters: {json.dumps(params, indent=2)}")
                    
                    try:
                        result = await client.call_tool(tool_name, params)
                        print(f"\nResult from {tool_name}:")
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error calling {tool_name}: {e}")
        except Exception as e:
            print(f"Error listing tools: {e}")
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)
    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    asyncio.run(test_mcp_client())
