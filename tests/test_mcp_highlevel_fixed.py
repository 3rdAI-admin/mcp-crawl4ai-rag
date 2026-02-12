import asyncio
import json
from mcp.client import Client

async def test_highlevel():
    # Create a client instance with the correct URL
    async with Client("http://localhost:8054") as client:
        print("Connected to MCP server")
        
        # List available tools
        print("\n=== Listing available tools ===")
        try:
            tools = await client.list_tools()
            print(f"Found {len(tools)} tools:")
            for tool in tools:
                print(f"- {tool.name}: {tool.description}")
                print(f"  Parameters: {json.dumps(tool.parameters, indent=4)}")
        except Exception as e:
            print(f"Error listing tools: {str(e)}")
        
        # Test get_available_sources tool
        print("\n=== Testing get_available_sources tool ===")
        try:
            result = await client.call_tool("get_available_sources", {})
            print("get_available_sources result:")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Error calling get_available_sources: {str(e)}")
        
        # Test crawl_website tool with a simple URL
        print("\n=== Testing crawl_website tool ===")
        try:
            result = await client.call_tool("crawl_website", {
                "url": "https://example.com"
            })
            print("crawl_website result:")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Error calling crawl_website: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_highlevel())
