import asyncio
import aiohttp
import json

async def check_server():
    base_url = "http://localhost:8054"
    
    async with aiohttp.ClientSession() as session:
        try:
            # Try to connect to SSE endpoint
            print("Connecting to SSE endpoint...")
            async with session.get(
                f"{base_url}/sse",
                headers={"Accept": "text/event-stream"},
                timeout=5
            ) as sse:
                if sse.status != 200:
                    print(f"❌ Failed to connect to SSE: {sse.status}")
                    return
                
                print("✅ Connected to SSE endpoint")
                
                # Try to get session ID
                session_id = None
                async for line in sse.content:
                    line = line.decode().strip()
                    if line.startswith('data: '):
                        data = line[6:].strip()
                        print(f"Received: {data}")
                        if 'session_id=' in data:
                            session_id = data.split('session_id=')[1].split('&')[0]
                            print(f"✅ Got session ID: {session_id}")
                            break
                
                if not session_id:
                    print("❌ No session ID received")
                    return
                
                # Try to list tools
                print("\nSending list_tools request...")
                msg_id = "test_123"
                async with session.post(
                    f"{base_url}/messages/?session_id={session_id}",
                    json={
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "method": "list_tools"
                    }
                ) as resp:
                    print(f"✅ Tool list request sent. Status: {resp.status}")
                
                # Wait for response
                print("\nWaiting for responses...")
                async for line in sse.content:
                    line = line.decode().strip()
                    if line.startswith('data: '):
                        try:
                            data = json.loads(line[6:])
                            print(f"📨 Received: {json.dumps(data, indent=2)}")
                            if data.get('id') == msg_id:
                                print("\n✅ Successfully received tool list response!")
                                return
                        except json.JSONDecodeError:
                            print(f"⚠️  Could not parse: {line}")
        
        except asyncio.TimeoutError:
            print("❌ Connection timed out")
        except Exception as e:
            print(f"❌ Error: {e}")

print("Testing MCP server...")
asyncio.run(check_server())
