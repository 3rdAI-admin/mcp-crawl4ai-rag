import asyncio
import json
import httpx
from mcp.client.session import ClientSession
from mcp.client.sse import aconnect_sse

async def test_mcp_session():
    # Create an HTTP client
    async with httpx.AsyncClient() as client:
        # Connect to the MCP server using SSE
        async with aconnect_sse(
            client=client,
            method="GET",
            url="http://localhost:8054/sse"
        ) as event_source:
            # Create a client session with the event source
            async with ClientSession(event_source, event_source) as session:
                print("Connected to MCP server")
                
                # List available tools
                print("\n=== Listing available tools ===")
                tools = await session.list_tools()
                for tool in tools:
                    print(f"- {tool.name}: {tool.description}")
                
                # Test crawl_website tool
                print("\n=== Testing crawl_website tool ===")
                try:
                    result = await session.call_tool(
                        name="crawl_website",
                        params={"url": "https://example.com"}
                    )
                    print(f"Result: {json.dumps(result, indent=2)}")
                except Exception as e:
                    print(f"Error calling crawl_website: {str(e)}")
                
                # Test get_available_sources tool
                print("\n=== Testing get_available_sources tool ===")
                try:
                    result = await session.call_tool(
                        name="get_available_sources",
                        params={}
                    )
                    print(f"Result: {json.dumps(result, indent=2)}")
                except Exception as e:
                    print(f"Error calling get_available_sources: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_mcp_session())
