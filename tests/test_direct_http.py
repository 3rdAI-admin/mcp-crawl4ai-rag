import asyncio
import json
import httpx

async def test_direct_http():
    base_url = "http://localhost:8054"
    
    async with httpx.AsyncClient() as client:
        # Test the root endpoint
        try:
            response = await client.get(f"{base_url}/")
            print(f"Root endpoint status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error connecting to root endpoint: {str(e)}")
        
        # Test the tools endpoint
        try:
            response = await client.get(f"{base_url}/tools")
            print(f"\nTools endpoint status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error connecting to tools endpoint: {str(e)}")
        
        # Test the SSE endpoint
        try:
            async with client.stream("GET", f"{base_url}/sse") as response:
                print(f"\nSSE endpoint status: {response.status_code}")
                print("Headers:", response.headers)
                
                # Read a few lines from the SSE stream
                count = 0
                async for line in response.aiter_lines():
                    print(f"SSE line {count}: {line}")
                    count += 1
                    if count >= 5:  # Limit the number of lines we read
                        break
        except Exception as e:
            print(f"Error connecting to SSE endpoint: {str(e)}")
        
        # Test calling a tool directly via HTTP POST
        try:
            response = await client.post(
                f"{base_url}/call",
                json={
                    "jsonrpc": "2.0",
                    "method": "get_available_sources",
                    "params": {},
                    "id": 1
                }
            )
            print(f"\nCall tool status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error calling tool: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_direct_http())
