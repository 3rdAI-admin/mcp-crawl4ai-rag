import asyncio
import json
from mcp.client.session import ClientSession
from mcp.client.sse import aconnect_sse
import httpx

async def test_client_session():
    # Create an HTTP client for the SSE connection
    async with httpx.AsyncClient() as http_client:
        print("Connecting to MCP server...")
        
        try:
            # Connect to the SSE endpoint
            async with aconnect_sse(
                client=http_client,
                method="GET",
                url="http://localhost:8054/sse"
            ) as event_source:
                print("Connected to SSE endpoint")
                
                # Create a client session
                async with ClientSession(event_source, event_source) as session:
                    print("Client session created")
                    
                    # List available tools
                    print("\n=== Listing available tools ===")
                    try:
                        tools = await session.list_tools()
                        print(f"Found {len(tools)} tools:")
                        for tool in tools:
                            print(f"- {tool.name}: {tool.description}")
                    except Exception as e:
                        print(f"Error listing tools: {str(e)}")
                    
                    # Test get_available_sources tool
                    print("\n=== Testing get_available_sources tool ===")
                    try:
                        result = await session.call("get_available_sources", {})
                        print("get_available_sources result:")
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error calling get_available_sources: {str(e)}")
                    
                    # Test crawl_website tool
                    print("\n=== Testing crawl_website tool ===")
                    try:
                        result = await session.call("crawl_website", {
                            "url": "https://example.com"
                        })
                        print("crawl_website result:")
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error calling crawl_website: {str(e)}")
                        
        except Exception as e:
            print(f"Error during test: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_client_session())
