#!/usr/bin/env python3
"""
List available sources from the MCP Crawl4AI server.
"""
import asyncio
import json
import logging
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Implementation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def list_sources():
    """List available sources from the MCP server."""
    # Server connection details
    base_url = "http://localhost:8052"
    messages_url = f"{base_url}/messages/"
    
    # Client information
    client_info = Implementation(name="list-sources-client", version="1.0.0")
    
    try:
        logger.info(f"Connecting to MCP server at: {messages_url}")
        
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
                await asyncio.wait_for(session.initialize(), timeout=10.0)
                logger.info("✓ Session initialized")
                
                # Call get_available_sources tool
                logger.info("Fetching available sources...")
                result = await asyncio.wait_for(
                    session.call_tool("get_available_sources", {}), 
                    timeout=15.0
                )
                
                return result
                
    except Exception as e:
        logger.error(f"Failed to list sources: {e}")
        return None

def format_sources(sources_result):
    """Format the sources result for display."""
    if not sources_result:
        return "❌ Failed to retrieve sources"
    
    # Handle different response formats
    if isinstance(sources_result, dict):
        if 'content' in sources_result:
            # Extract content if it's wrapped
            content = sources_result['content']
            if isinstance(content, list) and len(content) > 0:
                content = content[0]
            if isinstance(content, dict) and 'text' in content:
                try:
                    data = json.loads(content['text'])
                except (json.JSONDecodeError, KeyError):
                    data = content
            else:
                data = content
        else:
            data = sources_result
    else:
        data = sources_result
    
    # Format output
    output = []
    output.append("=" * 60)
    output.append("AVAILABLE DATA SOURCES")
    output.append("=" * 60)
    
    if isinstance(data, dict):
        if 'success' in data and data['success']:
            sources = data.get('sources', [])
            count = data.get('count', len(sources))
            
            output.append(f"Found {count} available sources:\n")
            
            for i, source in enumerate(sources, 1):
                output.append(f"{i}. {source.get('name', 'Unknown')}")
                output.append(f"   ID: {source.get('id', 'N/A')}")
                output.append(f"   Type: {source.get('type', 'N/A')}")
                output.append(f"   Description: {source.get('description', 'N/A')}")
                
                capabilities = source.get('capabilities', [])
                if capabilities:
                    output.append(f"   Capabilities: {', '.join(capabilities)}")
                
                output.append("")  # Empty line
        else:
            error = data.get('error', 'Unknown error')
            output.append(f"❌ Error: {error}")
    else:
        output.append(f"Raw response: {data}")
    
    output.append("=" * 60)
    return "\n".join(output)

async def main():
    """Main function."""
    print("Crawl4AI MCP Server - List Sources")
    print("=" * 40)
    
    # Get sources
    sources_result = await list_sources()
    
    # Format and display
    formatted_output = format_sources(sources_result)
    print(formatted_output)
    
    # Also show raw result for debugging
    if sources_result:
        print("\n" + "=" * 60)
        print("RAW RESPONSE (for debugging)")
        print("=" * 60)
        print(json.dumps(sources_result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
