import asyncio
import json
import logging
import sys
from typing import Any, Dict, Optional

import httpx
from httpx_sse import aconnect_sse

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8054"):
        self.base_url = base_url.rstrip('/')
        self.sse_url = f"{self.base_url}/sse"
        self.messages_url = f"{self.base_url}/messages/"
        self.session_id: Optional[str] = None
        self.client = httpx.AsyncClient()
        self._stop_event = asyncio.Event()
        self._message_queue = asyncio.Queue()

    async def _handle_sse_events(self, event_source):
        """Handle incoming SSE events."""
        try:
            async for sse in event_source.aiter_sse():
                logger.debug(f"SSE Event - Type: {sse.event}, Data: {sse.data}")
                if sse.event == "session":
                    try:
                        data = json.loads(sse.data)
                        self.session_id = data.get("session_id")
                        if self.session_id:
                            logger.info(f"Session established with ID: {self.session_id}")
                            await self._message_queue.put({"type": "session", "data": data})
                        else:
                            logger.error("No session_id in server response")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse session data: {e}")
                elif sse.event == "message":
                    try:
                        data = json.loads(sse.data)
                        await self._message_queue.put({"type": "message", "data": data})
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse message data: {e}")
                else:
                    logger.warning(f"Unhandled event type: {sse.event}")
        except Exception as e:
            logger.error(f"Error in SSE event handler: {e}")
            await self._message_queue.put({"type": "error", "error": str(e)})
        finally:
            logger.info("SSE event handler finished")
            self._stop_event.set()

    async def connect(self):
        """Establish an SSE connection to the MCP server."""
        logger.info(f"Connecting to MCP server at {self.sse_url}")
        
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        
        try:
            async with aconnect_sse(
                self.client,
                "GET",
                self.sse_url,
                headers=headers,
                timeout=30.0,
            ) as event_source:
                logger.info("SSE connection established")
                
                # Start the SSE event handler
                task = asyncio.create_task(self._handle_sse_events(event_source))
                
                # Wait for session to be established
                while not self._stop_event.is_set():
                    try:
                        event = await asyncio.wait_for(self._message_queue.get(), timeout=10.0)
                        if event["type"] == "session":
                            self.session_id = event["data"].get("session_id")
                            if self.session_id:
                                logger.info(f"Session established with ID: {self.session_id}")
                                return
                            else:
                                raise ConnectionError("Failed to establish session")
                        elif event["type"] == "error":
                            raise ConnectionError(f"Error during connection: {event['error']}")
                    except asyncio.TimeoutError:
                        logger.warning("Timeout waiting for session establishment")
                        break
                
                # Wait for the task to complete
                await task
                
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise

    async def call_method(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call an MCP method."""
        if not self.session_id:
            await self.connect()
            if not self.session_id:
                raise ConnectionError("No active session")
        
        # Generate a unique request ID
        request_id = "test_" + str(hash(f"{method}_{params}"))
        
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Session-ID": self.session_id
        }
        
        logger.info(f"Calling method: {method} with params: {params}")
        
        try:
            # Send the request
            response = await self.client.post(
                f"{self.messages_url}?session_id={self.session_id}",
                json=payload,
                headers=headers,
                timeout=30.0
            )
            
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            logger.debug(f"Response body: {response.text}")
            
            response.raise_for_status()
            
            # For SSE, the response will be empty, and we'll get the result via SSE
            if response.status_code == 202 and not response.text:
                logger.info("Request accepted, waiting for response via SSE...")
                
                # Wait for the response via SSE
                while not self._stop_event.is_set():
                    try:
                        event = await asyncio.wait_for(self._message_queue.get(), timeout=10.0)
                        if event["type"] == "message":
                            message = event["data"]
                            if message.get("id") == request_id:
                                if "error" in message:
                                    error = message["error"]
                                    logger.error(f"Error from server: {error}")
                                    raise Exception(error)
                                return message.get("result", {})
                        elif event["type"] == "error":
                            raise ConnectionError(f"Error during request: {event['error']}")
                    except asyncio.TimeoutError:
                        logger.warning("Timeout waiting for response")
                        break
                
                raise TimeoutError("Timed out waiting for response")
            else:
                # Handle non-SSE response
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
        self._stop_event.set()
        await self.client.aclose()

async def main():
    """Test connection to the MCP server and call methods."""
    client = MCPClient()
    
    try:
        # Connect to the server
        await client.connect()
        
        # List available tools
        print("\n=== Listing available tools ===")
        try:
            tools = await client.call_method("tools/list")
            print("Available tools:", json.dumps(tools, indent=2))
        except Exception as e:
            print(f"Error listing tools: {e}")
        
        # Get available sources
        print("\n=== Getting available sources ===")
        try:
            sources = await client.call_method("get_available_sources")
            print("Available sources:", json.dumps(sources, indent=2))
        except Exception as e:
            print(f"Error getting sources: {e}")
        
        # List available resources
        print("\n=== Listing available resources ===")
        try:
            resources = await client.call_method("resources/list")
            print("Available resources:", json.dumps(resources, indent=2))
        except Exception as e:
            print(f"Error listing resources: {e}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await client.close()
        print("\nDisconnected from MCP server")

if __name__ == "__main__":
    asyncio.run(main())
