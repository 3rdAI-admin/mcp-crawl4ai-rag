#!/usr/bin/env python3
"""
List sources from Crawl4AI MCP server using the working connection pattern.
"""
import asyncio
import json
import logging
from urllib.parse import urljoin
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
    # Server URL and endpoint - using the Docker container on port 8052
    base_url = "http://localhost:8052"
    endpoint = "/messages/"
    url = urljoin(base_url, endpoint)
    
    # Client information
    client_info = Implementation(name="crawl4ai-sources-client", version="1.0.0")
    
    try:
        logger.info(f"Connecting to Crawl4AI MCP server at: {url}")
        
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
                logger.info(f"Available tools: {[tool.name for tool in tools.tools]}")
                
                # Call get_available_sources tool
                logger.info("Getting available sources...")
                result = await session.call_tool("get_available_sources", {})
                logger.info("✓ Sources retrieved successfully")
                
                return result
                
    except Exception as e:
        logger.error(f"Failed to connect to MCP server: {e}")
        return None

def format_sources_output(result):
    """Format the sources result for display."""
    print("=" * 70)
    print("CRAWL4AI MCP SERVER - AVAILABLE DATA SOURCES")
    print("=" * 70)
    
    if not result:
        print("❌ Failed to retrieve sources from server")
        return
    
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
    print("💡 Usage Examples:")
    print("   • Web crawling: Use 'web' source for crawling websites")
    print("   • Document parsing: Use 'document' source for PDF/DOCX files")  
    print("   • Web search: Use 'search' source for web search queries")
    print("   • Database queries: Use 'database' source for structured data")
    print("=" * 70)

async def main():
    """Main function."""
    print("Crawl4AI MCP Server - List Available Sources")
    print("=" * 50)
    
    # Get sources from the server
    result = await list_crawl4ai_sources()
    
    # Format and display the results
    format_sources_output(result)
    
    # Show raw result for debugging if needed
    if result and logger.isEnabledFor(logging.DEBUG):
        print("\n" + "=" * 70)
        print("DEBUG: RAW SERVER RESPONSE")
        print("=" * 70)
        print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
