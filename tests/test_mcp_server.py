#!/usr/bin/env python3
"""
Test script to verify MCP Crawl4AI RAG server functionality.
"""
import asyncio
import logging
import sys
import signal
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from src.crawl4ai_mcp import crawl4ai_lifespan, mcp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_mcp_server.log')
    ]
)
logger = logging.getLogger(__name__)

# Global variable to store the server task
server_task = None

async def list_tools():
    """List available tools from the MCP server."""
    try:
        logger.info("Listing available tools...")
        tools = await mcp.list_tools()
        logger.info(f"Available tools: {[tool.name for tool in tools]}")
        return tools
    except Exception as e:
        logger.error(f"Error listing tools: {e}", exc_info=True)
        return []

async def test_tool(tool_name, **kwargs):
    """Test a specific tool with the given parameters."""
    try:
        logger.info(f"Testing tool: {tool_name}")
        logger.info(f"Parameters: {kwargs}")
        
        # Call the tool
        result = await mcp.call_tool(tool_name, **kwargs)
        logger.info(f"Tool result: {result}")
        return True
    except Exception as e:
        logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
        return False

async def run_tests():
    """Run tests against the MCP server."""
    global server_task
    
    try:
        # List available tools
        tools = await list_tools()
        if not tools:
            logger.error("No tools found")
            return False
        
        # Test each tool with appropriate parameters
        test_results = {}
        
        # Test crawl_website if available
        if any(tool.name == "crawl_website" for tool in tools):
            test_results["crawl_website"] = await test_tool(
                "crawl_website",
                url="https://example.com",
                max_pages=1,
                extract_metadata=True
            )
        
        # Test extract_content if available
        if any(tool.name == "extract_content" for tool in tools):
            test_results["extract_content"] = await test_tool(
                "extract_content",
                url="https://example.com",
                strategy="llm"
            )
        
        # Test search_web if available
        if any(tool.name == "search_web" for tool in tools):
            test_results["search_web"] = await test_tool(
                "search_web",
                query="MCP Crawl4AI RAG",
                limit=3
            )
        
        # Log test results
        logger.info("\nTest Results:")
        for tool_name, success in test_results.items():
            status = "PASSED" if success else "FAILED"
            logger.info(f"{tool_name}: {status}")
        
        return all(test_results.values())
    
    except Exception as e:
        logger.error(f"Error running tests: {e}", exc_info=True)
        return False

async def start_server():
    """Start the MCP server."""
    global server_task
    
    logger.info("Starting MCP server...")
    server_task = asyncio.create_task(mcp.run(transport='sse'))
    
    # Give the server some time to start
    await asyncio.sleep(2)
    logger.info("MCP server started")

async def stop_server():
    """Stop the MCP server."""
    global server_task
    
    if server_task and not server_task.done():
        logger.info("Stopping MCP server...")
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            logger.info("MCP server stopped")

async def main():
    """Main function to run the tests."""
    # Set up signal handler for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(sig)))
    
    try:
        # Start the server
        await start_server()
        
        # Run the tests
        success = await run_tests()
        
        # Stop the server
        await stop_server()
        
        return success
    
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        return False

async def shutdown(sig):
    """Shutdown the application gracefully."""
    logger.info(f"Received exit signal {sig.name}...")
    
    # Stop the server
    await stop_server()
    
    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_event_loop().stop()

if __name__ == "__main__":
    try:
        logger.info("Starting MCP server test...")
        success = asyncio.run(main())
        
        if success:
            logger.info("MCP server test completed successfully")
            sys.exit(0)
        else:
            logger.error("MCP server test failed")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(0)
    
    except Exception as e:
        logger.critical(f"Unhandled exception in MCP server test: {e}", exc_info=True)
        sys.exit(1)
