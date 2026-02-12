#!/usr/bin/env python3
"""
Script to list available tools and crawl a website using the MCP server.
"""
import asyncio
import json
import logging
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_crawl")

def serialize_tools(tools_result):
    """Convert ListToolsResult to a serializable format."""
    tools = []
    for tool in tools_result.tools:
        tool_dict = {
            "name": tool.name,
            "description": tool.description
        }
        
        # Try to get parameters if they exist
        try:
            if hasattr(tool, 'parameters') and tool.parameters:
                tool_dict["parameters"] = {
                    "type": getattr(tool.parameters, 'type', None),
                    "properties": getattr(tool.parameters, 'properties', None),
                    "required": getattr(tool.parameters, 'required', None)
                }
        except Exception as e:
            logger.debug(f"Could not get parameters for tool {tool.name}: {e}")
            
        tools.append(tool_dict)
    
    return {"tools": tools}

async def main():
    try:
        logger.info("Connecting to MCP server...")
        async with sse_client('http://localhost:8054/sse') as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the session
                logger.info("Initializing session...")
                await session.initialize()
                
                # List available tools
                logger.info("Listing available tools...")
                tools_result = await session.list_tools()
                tools_json = serialize_tools(tools_result)
                print("\n=== Available Tools ===")
                print(json.dumps(tools_json, indent=2))
                
                # First, check if the crawler is available
                logger.info("Checking crawler status...")
                check_result = await session.call_tool(
                    "get_available_sources",
                    {"self": None}  # Required by Pydantic model
                )
                logger.info(f"Available sources: {check_result}")
                
                # Try to initialize the crawler explicitly
                logger.info("\nInitializing crawler...")
                try:
                    init_result = await session.call_tool(
                        "get_available_sources",
                        {"self": None, "force_init": True}  # Try to force crawler initialization
                    )
                    logger.info(f"Crawler initialization result: {init_result}")
                except Exception as e:
                    logger.error(f"Failed to initialize crawler: {e}")
                
                # Now try to crawl the website
                logger.info("\nCrawling website...")
                try:
                    crawl_result = await session.call_tool(
                        "crawl_website",
                        {
                            "self": None,  # Required by Pydantic model
                            "url": "https://ai.pydantic.dev",
                            "max_pages": 1,
                            "extract_metadata": True
                        }
                    )
                except Exception as e:
                    logger.error(f"Error during crawl: {e}")
                    # Get detailed error information
                    error_result = await session.call_tool(
                        "get_available_sources",
                        {"self": None}
                    )
                    logger.error(f"Current crawler state: {error_result}")
                    logger.error("\nTroubleshooting steps:")
                    logger.error("1. Check if the MCP server has the required dependencies installed")
                    logger.error("2. Verify that the crawler configuration in the MCP server is correct")
                    logger.error("3. Check the MCP server logs for any crawler initialization errors")
                    logger.error("4. Ensure the target website is accessible from the MCP server")
                    raise
                
                # Convert CallToolResult to dict for serialization
                try:
                    if hasattr(crawl_result, 'result'):
                        result_data = crawl_result.result
                    else:
                        result_data = str(crawl_result)
                    
                    # Print the result
                    print("\n=== Crawl Result ===")
                    print(json.dumps(result_data, indent=2, default=str))
                    
                    # Save the result to a file
                    with open("crawl_result.json", "w") as f:
                        json.dump(result_data, f, indent=2, default=str)
                    logger.info("Results saved to crawl_result.json")
                    
                except Exception as e:
                    logger.error(f"Error processing crawl result: {e}")
                    logger.info(f"Raw crawl result: {crawl_result}")
                
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
