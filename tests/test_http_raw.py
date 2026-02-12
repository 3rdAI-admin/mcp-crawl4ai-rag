import asyncio
import json
import httpx

async def test_http_raw():
    base_url = "http://localhost:8054"
    
    async with httpx.AsyncClient() as client:
        # Test the root endpoint
        print("Testing root endpoint...")
        try:
            response = await client.get(f"{base_url}/")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {str(e)}")
        
        # Test the SSE endpoint
        print("\nTesting SSE endpoint...")
        try:
            async with client.stream("GET", f"{base_url}/sse") as response:
                print(f"Status: {response.status_code}")
                print("Headers:", response.headers)
                
                # Read a few lines from the SSE stream
                count = 0
                async for line in response.aiter_lines():
                    print(f"SSE line {count}: {line}")
                    count += 1
                    if count >= 5:  # Limit the number of lines we read
                        break
        except Exception as e:
            print(f"Error: {str(e)}")
        
        # Test calling a tool directly via HTTP POST
        print("\nTesting tool call...")
        try:
            # First, we need to create a session
            session_response = await client.post(
                f"{base_url}/sessions",
                json={"client_info": {"name": "test-client"}}
            )
            print(f"Create session status: {session_response.status_code}")
            session_data = session_response.json()
            print(f"Session data: {json.dumps(session_data, indent=2)}")
            
            # Extract session ID
            session_id = session_data.get("session_id")
            if not session_id:
                print("No session ID in response")
                return
            
            # Now try to call a tool
            tool_response = await client.post(
                f"{base_url}/sessions/{session_id}/messages",
                json={
                    "type": "call_tool",
                    "name": "get_available_sources",
                    "params": {}
                }
            )
            print(f"Tool call status: {tool_response.status_code}")
            print(f"Tool response: {tool_response.text}")
            
        except Exception as e:
            print(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_http_raw())
