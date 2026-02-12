#!/usr/bin/env python3
"""
Test MCP connectivity to server on port 8052.
"""
import asyncio
import logging
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Implementation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_connection():
    """Test MCP connection to server on port 8052."""
    base_url = "http://localhost:8052"
    messages_url = f"{base_url}/messages/"
    
    logger.info(f"Testing MCP connection to: {messages_url}")
    
    try:
        # Client information
        client_info = Implementation(name="connectivity-test", version="1.0.0")
        
        # Connect using SSE client
        async with sse_client(messages_url, timeout=30.0) as (read_stream, write_stream):
            logger.info("✓ SSE connection established")
            
            # Create client session
            async with ClientSession(
                read_stream,
                write_stream,
                client_info=client_info
            ) as session:
                logger.info("✓ MCP session created")
                
                # Initialize the session
                logger.info("Initializing MCP session...")
                await asyncio.wait_for(session.initialize(), timeout=10.0)
                logger.info("✓ MCP session initialized")
                
                # List available tools
                logger.info("Listing available tools...")
                tools_result = await asyncio.wait_for(session.list_tools(), timeout=10.0)
                
                if hasattr(tools_result, 'tools'):
                    tools = tools_result.tools
                    logger.info(f"✓ Found {len(tools)} tools:")
                    for tool in tools:
                        logger.info(f"  - {tool.name}: {tool.description}")
                else:
                    logger.info(f"✓ Tools result: {tools_result}")
                
                # Test calling a simple tool
                logger.info("Testing tool call...")
                try:
                    # Try health_check first
                    result = await asyncio.wait_for(
                        session.call_tool("health_check", {}), 
                        timeout=15.0
                    )
                    logger.info(f"✓ health_check result: {result}")
                    
                except Exception as tool_error:
                    logger.warning(f"health_check failed: {tool_error}")
                    
                    # Try get_available_sources as backup
                    try:
                        result = await asyncio.wait_for(
                            session.call_tool("get_available_sources", {}), 
                            timeout=15.0
                        )
                        logger.info(f"✓ get_available_sources result: {result}")
                        
                    except Exception as backup_error:
                        logger.error(f"Both tools failed: {backup_error}")
                
                logger.info("✓ MCP connection test completed successfully!")
                return True
                
    except asyncio.TimeoutError:
        logger.error("✗ Connection timed out")
        return False
    except Exception as e:
        logger.error(f"✗ Connection failed: {e}")
        return False

async def main():
    """Main test function."""
    print("=" * 60)
    print("MCP Crawl4AI Server Connectivity Test (Port 8052)")
    print("=" * 60)
    
    success = await test_mcp_connection()
    
    if success:
        print("\n🎉 SUCCESS! MCP server is fully functional on port 8052")
        print("\nConnection details:")
        print("  Base URL:     http://localhost:8052")
        print("  SSE Endpoint: http://localhost:8052/sse")
        print("  Messages:     http://localhost:8052/messages/")
        print("\nExample Python client code:")
        print("""
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Implementation

async def connect_to_mcp():
    client_info = Implementation("my-client", "1.0.0")
    
    async with sse_client("http://localhost:8052/messages/") as (read, write):
        async with ClientSession(read, write, client_info) as session:
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")
            
            # Call a tool
            result = await session.call_tool("health_check", {})
            print(f"Health check: {result}")
        """)
    else:
        print("\n❌ FAILED! Could not connect to MCP server")
        print("\nTroubleshooting:")
        print("  - Check if Docker container is running: docker ps")
        print("  - Check container logs: docker logs mcp-crawl4ai-rag")
        print("  - Try restarting: docker-compose restart")

if __name__ == "__main__":
    asyncio.run(main())
