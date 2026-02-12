import asyncio
import json
import uuid
import httpx
import re
from typing import Dict, Any, Optional, AsyncIterator, Tuple

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8054"):
        self.base_url = base_url
        self.session_id = str(uuid.uuid4())
        self.message_counter = 1
        self.client = httpx.AsyncClient()
        self.response_queues = {}
    
    async def __aenter__(self):
        # First, connect to the SSE endpoint to get the session ID
        async with self.client.stream("GET", f"{self.base_url}/sse") as response:
            if response.status_code != 200:
                raise Exception(f"Failed to connect to SSE endpoint: {response.status_code}")
            
            # Read the first few lines to get the session ID
            async for line in response.aiter_lines():
                if line.startswith("event: endpoint"):
                    continue
                if line.startswith("data: "):
                    endpoint = line[6:].strip()
                    if endpoint.startswith("/messages/?session_id="):
                        self.session_id = endpoint.split("=")[1]
                        print(f"Using session ID: {self.session_id}")
                        break
        
        # Start a background task to read SSE messages
        self.sse_task = asyncio.create_task(self._read_sse_messages())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cancel the SSE reading task
        self.sse_task.cancel()
        try:
            await self.sse_task
        except asyncio.CancelledError:
            pass
        
        await self.client.aclose()
    
    async def _read_sse_messages(self):
        """Read messages from the SSE stream and put them in the appropriate queues."""
        try:
            async with self.client.stream("GET", f"{self.base_url}/sse") as response:
                if response.status_code != 200:
                    print(f"Failed to connect to SSE stream: {response.status_code}")
                    return
                
                current_message = {}
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        # Empty line indicates the end of a message
                        if 'id' in current_message and 'data' in current_message:
                            message_id = current_message.get('id')
                            if message_id in self.response_queues:
                                await self.response_queues[message_id].put(current_message['data'])
                        current_message = {}
                    elif ':' in line:
                        # Parse the SSE message field
                        field, value = line.split(':', 1)
                        field = field.strip()
                        value = value.strip()
                        current_message[field] = value
        except Exception as e:
            print(f"Error reading SSE messages: {str(e)}")
    
    async def send_message(self, message_type: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to the MCP server and return the response."""
        message_id = str(self.message_counter)
        self.message_counter += 1
        
        # Create a queue to store the response
        self.response_queues[message_id] = asyncio.Queue()
        
        message = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": message_type,
            "params": content
        }
        
        try:
            # Send the message to the server
            response = await self.client.post(
                f"{self.base_url}/messages/?session_id={self.session_id}",
                json=message,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 202:
                return {"error": f"Unexpected status code: {response.status_code}", "response": response.text}
            
            # Wait for the response from the SSE stream
            try:
                response_data = await asyncio.wait_for(self.response_queues[message_id].get(), timeout=10.0)
                return json.loads(response_data)
            except asyncio.TimeoutError:
                return {"error": "Timeout waiting for response", "message_id": message_id}
            except json.JSONDecodeError as e:
                return {"error": f"Invalid JSON in response: {str(e)}", "raw_response": response_data}
            
        finally:
            # Clean up the response queue
            if message_id in self.response_queues:
                del self.response_queues[message_id]
    
    async def list_tools(self) -> Dict[str, Any]:
        """List all available tools on the server."""
        return await self.send_message("list_tools", {})
    
    async def call_tool(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the server."""
        return await self.send_message("call_tool", {
            "name": name,
            "params": params
        })

async def test_mcp_protocol():
    async with MCPClient() as client:
        print(f"Connected to MCP server with session ID: {client.session_id}")
        
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
        
        # Test crawl_website tool
        print("\n=== Testing crawl_website tool ===")
        try:
            result = await client.call_tool("crawl_website", {
                "url": "https://example.com"
            })
            print(f"Result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Error calling crawl_website: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_mcp_protocol())
