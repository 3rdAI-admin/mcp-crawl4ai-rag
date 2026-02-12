import asyncio
import json
from mcp.client.session import ClientSession

async def test_mcp_client():
    # Create a client session
    async with ClientSession("http://localhost:8054") as session:
        print("Connected to MCP server")
        
        # List available tools
        print("\n=== Listing available tools ===")
        try:
            tools = await session.list_tools()
            for tool in tools:
                print(f"- {tool.name}: {tool.description}")
        except Exception as e:
            print(f"Error listing tools: {str(e)}")
            return
        
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

if __name__ == "__main__":
    asyncio.run(test_mcp_client())
