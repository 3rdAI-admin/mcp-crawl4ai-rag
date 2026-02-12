#!/usr/bin/env python3
"""
List sources from Crawl4AI MCP server using the SSE endpoint directly.
"""
import asyncio
import json
import logging
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
    
    logger.debug(f"Received message: {message}")

async def list_crawl4ai_sources():
    """List available sources from the Crawl4AI MCP server."""
    # Use the exact URL from your mcp.json configuration
    sse_url = "http://192.168.50.7:8052/sse"
    
    # Client information
    client_info = Implementation(name="crawl4ai-sources-client", version="1.0.0")
    
    try:
        logger.info(f"Connecting to Crawl4AI MCP server SSE endpoint: {sse_url}")
        logger.info("Using exact URL from mcp.json configuration")
        
        # Create SSE client and connect to the server using the SSE endpoint directly
        async with sse_client(sse_url) as (read_stream, write_stream):
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
                
                # List available tools first
                logger.info("Listing available tools...")
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                logger.info(f"Available tools: {tool_names}")
                
                # Call get_available_sources tool
                logger.info("Getting available sources...")
                result = await session.call_tool("get_available_sources", {})
                logger.info("✓ Sources retrieved successfully")
                
                return result, tool_names
                
    except Exception as e:
        logger.error(f"Failed to connect to MCP server: {e}")
        logger.exception("Full error details:")
        return None, []

def format_sources_output(result, tool_names):
    """Format the sources result for display."""
    print("=" * 70)
    print("CRAWL4AI MCP SERVER - AVAILABLE DATA SOURCES")
    print(f"SSE Endpoint: http://192.168.50.7:8052/sse")
    print("=" * 70)
    
    if not result:
        print("❌ Failed to retrieve sources from server")
        if tool_names:
            print(f"🛠️  But we did find these tools: {', '.join(tool_names)}")
        return
    
    # Show available tools first
    if tool_names:
        print(f"🛠️  Available Tools: {', '.join(tool_names)}")
        print()
    
    # Extract the actual result data
    sources_data = None
    if hasattr(result, 'content') and result.content:
        # Handle MCP tool result format
        content = result.content[0] if isinstance(result.content, list) else result.content
        if hasattr(content, 'text'):
            try:
                sources_data = json.loads(content.text)
            except json.JSONDecodeError:
                sources_data = {"raw_text": content.text}
        else:
            sources_data = content
    else:
        sources_data = result
    
    if isinstance(sources_data, dict) and sources_data.get('success'):
        sources = sources_data.get('sources', [])
        count = sources_data.get('count', len(sources))
        
        print(f"✅ Successfully found {count} available data sources:\n")
        
        for i, source in enumerate(sources, 1):
            print(f"{i}. 📊 {source.get('name', 'Unknown Source')}")
            print(f"   🆔 ID: {source.get('id', 'N/A')}")
            print(f"   🏷️  Type: {source.get('type', 'N/A')}")
            print(f"   📝 Description: {source.get('description', 'N/A')}")
            
            capabilities = source.get('capabilities', [])
            if capabilities:
                print(f"   ⚡ Capabilities: {', '.join(capabilities)}")
            
            print()  # Empty line between sources
            
    elif isinstance(sources_data, dict) and not sources_data.get('success'):
        error = sources_data.get('error', 'Unknown error')
        print(f"❌ Server returned error: {error}")
    else:
        print("📄 Raw server response:")
        print(json.dumps(sources_data, indent=2, default=str))
    
    print("=" * 70)
    print("💡 Connection successful! You can now use:")
    print("   • Cursor MCP integration with this server")
    print("   • Direct Python scripts to call tools")  
    print("   • The available tools listed above")
    print("=" * 70)

# Also create a simple test function
async def test_basic_connection():
    """Test basic connection without tool calls."""
    sse_url = "http://192.168.50.7:8052/sse"
    client_info = Implementation(name="test-client", version="1.0.0")
    
    try:
        logger.info("Testing basic SSE connection...")
        async with sse_client(sse_url) as (read_stream, write_stream):
            logger.info("✓ Basic SSE connection successful")
            
            async with ClientSession(read_stream, write_stream, client_info=client_info) as session:
                logger.info("✓ Session creation successful")
                await session.initialize()
                logger.info("✓ Session initialization successful")
                
                return True
    except Exception as e:
        logger.error(f"Basic connection test failed: {e}")
        return False

async def main():
    """Main function."""
    print("Crawl4AI MCP Server - List Available Sources")
    print("Configuration: Using SSE endpoint from mcp.json")
    print("=" * 50)
    
    # First test basic connection
    basic_ok = await test_basic_connection()
    
    if basic_ok:
        print("✅ Basic connection test passed!")
        print()
        
        # Get sources from the server
        result, tool_names = await list_crawl4ai_sources()
        
        # Format and display the results
        format_sources_output(result, tool_names)
    else:
        print("❌ Basic connection test failed!")
        print("Troubleshooting:")
        print("  1. Check if Docker container is running: docker ps")
        print("  2. Check container logs: docker logs mcp-crawl4ai-rag")
        print("  3. Verify IP address is accessible: ping 192.168.50.7")
        print("  4. Test SSE endpoint: curl http://192.168.50.7:8052/sse")

if __name__ == "__main__":
    asyncio.run(main())
