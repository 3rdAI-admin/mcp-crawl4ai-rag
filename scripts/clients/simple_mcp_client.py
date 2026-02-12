import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

import httpx
from mcp.types import JSONRPCResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Define MCP request and response types
@dataclass
class MCPRequest:
    jsonrpc: str = "2.0"
    id: str = "1"
    method: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
            "params": self.params or {}
        }

@dataclass
class MCPResponse:
    jsonrpc: str = "2.0"
    id: str = ""
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPResponse':
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id", ""),
            result=data.get("result"),
            error=data.get("error")
        )


async def send_rpc_request(client: httpx.AsyncClient, url: str, request: MCPRequest) -> MCPResponse:
    """Send an RPC request to the MCP server and return the response."""
    try:
        logger.debug(f"Sending RPC request: {request.method}")
        response = await client.post(
            url,
            json=request.to_dict(),
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return MCPResponse.from_dict(response.json())
    except Exception as e:
        logger.error(f"Error sending RPC request: {e}")
        raise


async def get_sse_endpoint(client: httpx.AsyncClient, base_url: str) -> Tuple[str, str]:
    """Get the SSE endpoint and message endpoint from the MCP server."""
    # The SSE endpoint is fixed for this example
    sse_endpoint = f"{base_url}/sse"
    
    # Verify the SSE endpoint is accessible
    try:
        logger.info(f"Connecting to SSE endpoint: {sse_endpoint}")
        # First, try with a HEAD request to check accessibility
        response = await client.head(sse_endpoint, follow_redirects=True)
        response.raise_for_status()
        
        # If we got here, the endpoint is accessible, but we need to get the final URL after redirects
        final_url = str(response.url)
        logger.info(f"SSE endpoint is accessible at: {final_url}")
        
        # Update the message endpoint based on the final URL
        if final_url.endswith('/'):
            message_endpoint = f"{final_url}message"
        else:
            message_endpoint = f"{final_url}/message"
            
        logger.info(f"Using message endpoint: {message_endpoint}")
        return final_url, message_endpoint
    except Exception as e:
        logger.error(f"Error setting up SSE endpoint: {e}")
        raise

async def process_sse_stream(response, request_id):
    """Process the SSE stream and handle events."""
    try:
        logger.info("Connected to SSE stream. Waiting for events... (press Ctrl+C to exit)")
        
        # Process the SSE stream
        buffer = ""
        async for chunk in response.aiter_bytes():
            chunk = chunk.decode('utf-8', errors='replace')
            buffer += chunk
            
            # Process complete SSE messages (separated by double newlines)
            while "\n\n" in buffer:
                event_data, buffer = buffer.split("\n\n", 1)
                
                # Skip empty events and ping messages
                if not event_data.strip() or event_data.startswith(':'):
                    continue
                    
                logger.debug(f"Raw event data: {event_data}")
                
                # Parse the SSE event
                event = {}
                for line in event_data.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        event[key.strip().lower()] = value.strip()
                
                logger.info(f"Received event: {event}")
                
                # Process the event data
                if 'data' in event:
                    try:
                        data = json.loads(event['data'])
                        logger.info(f"Parsed message:\n{json.dumps(data, indent=2)}")
                        
                        # Check if this is a response to our request
                        if isinstance(data, dict) and 'id' in data and data.get('id') == request_id:
                            # If this is a response to our list_tools request, print the tools
                            if 'result' in data and 'tools' in data['result']:
                                tools = data['result']['tools']
                                logger.info("\n=== Available Tools ===")
                                for tool in tools:
                                    logger.info(f"\nName: {tool.get('name', 'Unnamed tool')}")
                                    logger.info(f"Description: {tool.get('description', 'No description')}")
                                    if 'parameters' in tool:
                                        logger.info("Parameters:")
                                        for param_name, param_info in tool['parameters'].get('properties', {}).items():
                                            logger.info(f"  - {param_name}: {param_info.get('type', 'any')} - {param_info.get('description', 'No description')}")
                                
                                return True
                            
                            # Handle error responses
                            elif 'error' in data:
                                error = data['error']
                                logger.error(f"Error from server: {error.get('message', 'Unknown error')} (code: {error.get('code', 'unknown')})")
                                return False
                    
                    except json.JSONDecodeError as e:
                        logger.warning(f"Could not parse message as JSON: {event.get('data')}")
                        logger.debug(f"JSON decode error: {e}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)
        
        return False
        
    except asyncio.CancelledError:
        logger.info("SSE stream processing cancelled")
        return False
    except Exception as e:
        logger.error(f"Error processing SSE stream: {e}", exc_info=True)
        return False

async def main():
    # Connect to the MCP server with the correct endpoints
    base_url = "http://localhost:8054"
    max_retries = 3
    retry_delay = 2  # seconds
    request_id = "1"
    
    logger.info(f"Connecting to MCP server at {base_url}")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Create an HTTP client for the SSE connections with a longer timeout
    timeout = httpx.Timeout(300.0, connect=30.0)  # 5 minutes for read, 30 seconds for connect
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_retries):
            try:
                # Get the SSE and message endpoints
                logger.info(f"Attempt {attempt + 1}/{max_retries}: Connecting to server...")
                sse_endpoint, message_endpoint = await get_sse_endpoint(client, base_url)
                
                # Connect to the SSE endpoint
                logger.info(f"Connecting to SSE stream at {sse_endpoint}...")
                sse_response = await client.get(
                    sse_endpoint,
                    headers={
                        "Accept": "text/event-stream",
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive"
                    },
                    timeout=timeout
                )
                sse_response.raise_for_status()
                
                # Log SSE connection established
                logger.info("SSE connection established. Sending list_tools request...")
                
                # Send a message to list tools
                list_tools_request = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "list_tools",
                    "params": {}
                }
                
                logger.info(f"Sending request to {message_endpoint}:")
                logger.info(f"{json.dumps(list_tools_request, indent=2)}")
                
                # Send the request to the message endpoint
                try:
                    response = await client.post(
                        message_endpoint,
                        json=list_tools_request,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive"
                        }
                    )
                    response.raise_for_status()
                    logger.info(f"List tools response status: {response.status_code} - {response.reason_phrase}")
                    logger.debug(f"Response headers: {response.headers}")
                    logger.debug(f"Response body: {response.text}")
                    
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error when listing tools: {e.response.status_code} - {e.response.text}")
                    sse_task.cancel()
                    continue
                except Exception as e:
                    logger.error(f"Error sending list_tools request: {e}")
                    sse_task.cancel()
                    continue
                
                # Process the SSE stream
                try:
                    # Process the SSE stream
                    success = await process_sse_stream(sse_response, request_id)
                    if success:
                        logger.info("Successfully retrieved tools list.")
                        break
                    
                    logger.warning("SSE stream ended without receiving tools list.")
                    
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error in SSE stream: {e.response.status_code} - {e.response.text}")
                except httpx.RequestError as e:
                    logger.error(f"Request failed: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error in SSE stream: {e}", exc_info=True)
                finally:
                    # Close the SSE response
                    await sse_response.aclose()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"Request failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
            finally:
                # Cancel any pending SSE task
                if 'sse_task' in locals() and not sse_task.done():
                    sse_task.cancel()
                    try:
                        await sse_task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.debug(f"Error cancelling SSE task: {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
        
        logger.info("MCP client finished")

if __name__ == "__main__":
    asyncio.run(main())
