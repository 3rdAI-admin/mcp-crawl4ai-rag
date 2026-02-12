import asyncio
import json
import logging
from typing import Any, Dict, Optional

import httpx
from httpx_sse import aconnect_sse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8054"):
        self.base_url = base_url.rstrip('/')
        self.sse_url = f"{self.base_url}/sse"
        self.messages_url = f"{self.base_url}/messages/"
        self.session_id: Optional[str] = None
        self.client = httpx.AsyncClient()

    async def connect(self):
        """Establish an SSE connection to the MCP server."""
        logger.info(f"Connecting to MCP server at {self.sse_url}")
        
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        
        async with aconnect_sse(
            self.client,
            "GET",
            self.sse_url,
            headers=headers,
            timeout=30.0,
        ) as event_source:
            logger.info("SSE connection established")
            
            # The first message should contain the session ID
            async for sse in event_source.aiter_sse():
                if sse.event == "session":
                    try:
                        data = json.loads(sse.data)
                        self.session_id = data.get("session_id")
                        if self.session_id:
                            logger.info(f"Session established with ID: {self.session_id}")
                            return self.session_id
                        else:
                            logger.error("No session_id in server response")
                            break
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse session data: {e}")
                        break
                else:
                    logger.warning(f"Unexpected event type: {sse.event}")
        
        raise ConnectionError("Failed to establish SSE connection")

    async def call_method(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call an MCP method."""
        if not self.session_id:
            await self.connect()
            if not self.session_id:
                raise ConnectionError("No active session")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Session-ID": self.session_id
        }
        
        logger.info(f"Calling method: {method} with params: {params}")
        
        try:
            response = await self.client.post(
                self.messages_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            if "error" in result:
                logger.error(f"Error from server: {result['error']}")
                raise Exception(result["error"])
                
            return result.get("result", {})
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            try:
                error_detail = e.response.json()
                logger.error(f"Error details: {error_detail}")
            except:
                logger.error(f"Response: {e.response.text}")
            raise
            
        except Exception as e:
            logger.error(f"Error calling method {method}: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

async def main():
    """Test connection to the MCP server and call a method."""
    client = MCPClient()
    
    try:
        # Connect to the server
        await client.connect()
        
        # List available tools
        tools = await client.call_method("tools/list")
        print("Available tools:", json.dumps(tools, indent=2))
        
        # Get available sources
        sources = await client.call_method("get_available_sources")
        print("Available sources:", json.dumps(sources, indent=2))
        
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
