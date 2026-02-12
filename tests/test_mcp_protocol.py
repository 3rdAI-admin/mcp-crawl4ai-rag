import asyncio
import json
import uuid
import httpx
from typing import Dict, Any, Optional

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8054"):
        self.base_url = base_url
        self.session_id = str(uuid.uuid4())
        self.message_counter = 1
        self.client = httpx.AsyncClient()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _send_message(self, message_type: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to the MCP server and return the response."""
        message_id = str(self.message_counter)
        self.message_counter += 1
        
        message = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": message_type,
            "params": content
        }
        
        # Send the message to the server
        response = await self.client.post(
            f"{self.base_url}/messages/?session_id={self.session_id}",
            json=message,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 202:
            raise Exception(f"Unexpected status code: {response.status_code}")
        
        # For simplicity, we'll just return the response status
        # In a real implementation, you would need to handle the SSE stream
        return {"status": "accepted", "message_id": message_id}
    
    async def list_tools(self) -> Dict[str, Any]:
        """List all available tools on the server."""
        return await self._send_message("list_tools", {})
    
    async def call_tool(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the server."""
        return await self._send_message("call_tool", {
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
