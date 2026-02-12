#!/usr/bin/env python3
"""
Direct HTTP call to get sources from MCP server.
"""
import json
import requests
import uuid
import asyncio
import httpx
from httpx_sse import aconnect_sse

async def test_sse_direct():
    """Test SSE connection directly."""
    print("Testing direct SSE connection...")
    
    try:
        async with httpx.AsyncClient() as client:
            async with aconnect_sse(client, "GET", "http://localhost:8052/sse") as event_source:
                print("✓ SSE connected")
                
                # Get the first few events
                count = 0
                async for sse_event in event_source.aiter_sse():
                    print(f"Event {count}: {sse_event.event} - {sse_event.data}")
                    count += 1
                    if count >= 3:  # Just get first few events
                        break
                        
    except Exception as e:
        print(f"SSE test failed: {e}")

def test_direct_http_call():
    """Test direct HTTP call to the container."""
    print("Testing direct HTTP call to get sources...")
    
    # Try different approaches
    base_url = "http://localhost:8052"
    
    # Test 1: Direct tool call (might not work without MCP protocol)
    try:
        response = requests.get(f"{base_url}/tools", timeout=10)
        print(f"Tools endpoint: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"Tools endpoint failed: {e}")
    
    # Test 2: Try health endpoint variations
    health_endpoints = ["/health", "/healthz", "/status", "/ping"]
    for endpoint in health_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=5)
            print(f"{endpoint}: {response.status_code} - {response.text[:100]}")
        except Exception as e:
            print(f"{endpoint} failed: {e}")
    
    # Test 3: Try to get server info
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        print(f"Root endpoint: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"Root endpoint failed: {e}")

async def test_manual_mcp_call():
    """Test manual MCP protocol call."""
    print("Testing manual MCP protocol call...")
    
    try:
        # First, get session from SSE
        print("1. Getting SSE session...")
        async with httpx.AsyncClient() as client:
            sse_response = await client.get("http://localhost:8052/sse", 
                                          headers={"Accept": "text/event-stream"},
                                          timeout=10)
            
            if sse_response.status_code == 200:
                print("✓ SSE endpoint accessible")
                
                # Extract session ID from the response
                content = sse_response.text
                print(f"SSE response preview: {content[:200]}...")
                
                # Look for session ID in the response
                if "session_id=" in content:
                    session_start = content.find("session_id=") + len("session_id=")
                    session_end = content.find("\n", session_start)
                    if session_end == -1:
                        session_end = len(content)
                    session_id = content[session_start:session_end].strip()
                    print(f"Found session ID: {session_id}")
                    
                    # Now try to call the tool with session ID
                    print("2. Calling get_available_sources tool...")
                    
                    tool_request = {
                        "jsonrpc": "2.0",
                        "id": str(uuid.uuid4()),
                        "method": "tools/call",
                        "params": {
                            "name": "get_available_sources",
                            "arguments": {}
                        }
                    }
                    
                    messages_url = f"http://localhost:8052/messages/?session_id={session_id}"
                    tool_response = await client.post(
                        messages_url,
                        json=tool_request,
                        headers={"Content-Type": "application/json"},
                        timeout=15
                    )
                    
                    print(f"Tool call response: {tool_response.status_code}")
                    print(f"Response content: {tool_response.text}")
                    
                else:
                    print("❌ No session ID found in SSE response")
            else:
                print(f"❌ SSE endpoint failed: {sse_response.status_code}")
                
    except Exception as e:
        print(f"Manual MCP call failed: {e}")

async def main():
    """Run all tests."""
    print("=" * 60)
    print("DIRECT CRAWL4AI SOURCES TEST")
    print("=" * 60)
    
    # Test 1: Direct HTTP calls
    test_direct_http_call()
    
    print("\n" + "=" * 60)
    
    # Test 2: SSE connection test
    await test_sse_direct()
    
    print("\n" + "=" * 60)
    
    # Test 3: Manual MCP protocol
    await test_manual_mcp_call()

if __name__ == "__main__":
    asyncio.run(main())
