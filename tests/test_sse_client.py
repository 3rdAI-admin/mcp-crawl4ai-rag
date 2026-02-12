import asyncio
import json
import uuid
from typing import Any, Dict, Optional

import aiohttp
from pydantic import BaseModel

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8054"):
        self.base_url = base_url.rstrip("/")
        self.session_id: Optional[str] = None
        self.sse_url = f"{self.base_url}/sse"
        self.message_counter = 1
        self.response_queues: Dict[str, asyncio.Queue] = {}

    async def connect(self):
        """Connect to the MCP server and establish an SSE session."""
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        
        # Create a new session for SSE
        self.session = aiohttp.ClientSession()
        
        # Connect to the SSE endpoint
        self.sse_session = await self.session.get(self.sse_url, headers=headers)
        
        if self.sse_session.status != 200:
            raise Exception(f"Failed to connect to SSE endpoint: {self.sse_session.status}")
        
        # Start a background task to process SSE events
        self.sse_task = asyncio.create_task(self._process_sse_events())
        
        # Wait for the endpoint message with the session ID
        await asyncio.sleep(1)  # Give some time for the connection to establish
        
        if not self.session_id:
            raise Exception("Failed to establish SSE session: no session ID received")
        
        print(f"Connected to MCP server with session ID: {self.session_id}")
    
    async def _process_sse_events(self):
        """Process incoming SSE events."""
        async for line in self.sse_session.content:
            line = line.decode().strip()
            if not line:
                continue
                
            if line.startswith("event: endpoint"):
                # The next line should be the data with the message endpoint
                continue
            elif line.startswith("data: "):
                data = line[6:].strip()
                if data.startswith("{"):
                    # This is a JSON message, parse it
                    try:
                        message = json.loads(data)
                        if "id" in message and message["id"] in self.response_queues:
                            await self.response_queues[message["id"]].put(message)
                        else:
                            print(f"Received message without matching ID: {message}")
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse message: {e}, data: {data}")
                elif "/messages/" in data:
                    # This is the endpoint message with the session ID
                    self.message_url = data
                    self.session_id = data.split("session_id=")[1]
                    print(f"Received message URL: {self.message_url}")
    
    async def send_message(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a JSON-RPC message to the MCP server."""
        if not self.session_id:
            raise Exception("Not connected to MCP server")
        
        message_id = str(self.message_counter)
        self.message_counter += 1
        
        # Create a queue to store the response
        self.response_queues[message_id] = asyncio.Queue()
        
        # Prepare the JSON-RPC message
        message = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params or {}
        }
        
        # Send the message to the server
        url = f"{self.base_url}/messages/?session_id={self.session_id}"
        headers = {"Content-Type": "application/json"}
        
        try:
            async with self.session.post(url, json=message, headers=headers) as response:
                if response.status != 202:
                    error_text = await response.text()
                    raise Exception(f"Server returned status {response.status}: {error_text}")
                
                # Wait for the response from the SSE stream
                try:
                    response_data = await asyncio.wait_for(
                        self.response_queues[message_id].get(), 
                        timeout=10.0
                    )
                    return response_data
                except asyncio.TimeoutError:
                    raise Exception("Timeout waiting for response from server")
                finally:
                    # Clean up the response queue
                    if message_id in self.response_queues:
                        del self.response_queues[message_id]
        except Exception as e:
            # Clean up the response queue in case of errors
            if message_id in self.response_queues:
                del self.response_queues[message_id]
            raise e
    
    async def list_tools(self) -> Dict[str, Any]:
        """List all available tools on the server."""
        return await self.send_message("list_tools")
    
    async def call_tool(self, name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a tool on the server."""
        return await self.send_message("call_tool", {"name": name, "arguments": params or {}})
    
    async def close(self):
        """Close the connection to the MCP server."""
        if hasattr(self, 'sse_task') and not self.sse_task.done():
            self.sse_task.cancel()
            try:
                await self.sse_task
            except asyncio.CancelledError:
                pass
        
        if hasattr(self, 'session') and not self.session.closed:
            await self.session.close()

async def test_mcp_client():
    client = MCPClient()
    
    try:
        # Connect to the MCP server
        print("Connecting to MCP server...")
        await client.connect()
        
        # List available tools
        print("\n=== Listing available tools ===")
        try:
            tools = await client.list_tools()
            print(f"Tools response: {json.dumps(tools, indent=2)}")
        except Exception as e:
            print(f"Error listing tools: {str(e)}")
        
        # Test get_available_sources tool
        print("\n=== Testing get_available_sources tool ===")
        try:
            result = await client.call_tool("get_available_sources", {})
            print(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Error calling get_available_sources: {str(e)}")
        
        # Test crawl_website tool with a simple URL
        print("\n=== Testing crawl_website tool ===")
        try:
            result = await client.call_tool("crawl_website", {
                "url": "https://example.com"
            })
            print(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Error calling crawl_website: {str(e)}")
    
    finally:
        # Ensure the client is properly closed
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_mcp_client())
