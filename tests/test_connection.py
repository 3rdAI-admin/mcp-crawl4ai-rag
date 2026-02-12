import httpx
import asyncio
import json

async def test_connection():
    # The MCP server's base URL
    base_url = "http://localhost:8054"
    
    # Test the root endpoint
    async with httpx.AsyncClient() as client:
        try:
            # Test the root endpoint
            response = await client.get(f"{base_url}/")
            print(f"Root endpoint status: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Test the tools endpoint
            response = await client.get(f"{base_url}/tools")
            print(f"\nTools endpoint status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            
        except Exception as e:
            print(f"Error connecting to MCP server: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_connection())
