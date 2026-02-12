import asyncio
from mcp.client import Client
from mcp.types import InitializeRequest, ClientCapabilities

async def main():
    # Create a client that connects to the MCP server
    async with Client("http://localhost:8054") as client:
        # Initialize the client
        init_request = InitializeRequest(
            client_info={"name": "test-client", "version": "0.1.0"},
            capabilities=ClientCapabilities()
        )
        init_response = await client.send_request(init_request)
        print(f"Initialized: {init_response}")
        
        # Call the get_available_sources method
        response = await client.call("get_available_sources", {})
        print(f"Response: {response}")

if __name__ == "__main__":
    asyncio.run(main())
