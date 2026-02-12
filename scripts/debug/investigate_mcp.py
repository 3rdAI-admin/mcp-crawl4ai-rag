import asyncio
import httpx
import json
import logging
from typing import Dict, Any, Optional
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_investigation.log')
    ]
)
logger = logging.getLogger(__name__)

class MCPInvestigator:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.session_id: Optional[str] = None
        self.message_id = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def connect_sse(self) -> bool:
        """Establish an SSE connection and extract session ID"""
        sse_url = f"{self.base_url}/sse"
        logger.info(f"Connecting to SSE endpoint: {sse_url}")
        
        try:
            # First, make a GET request to the SSE endpoint
            async with self.client.stream(
                "GET",
                sse_url,
                headers={
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache"
                }
            ) as response:
                if response.status_code != 200:
                    logger.error(f"Failed to connect to SSE: {response.status_code}")
                    return False
                
                # Look for the first event which should contain the session ID
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        logger.debug(f"SSE data: {data}")
                        
                        # Try to extract session ID from the endpoint URL
                        if 'session_id=' in data:
                            self.session_id = data.split('session_id=')[1].split('&')[0]
                            logger.info(f"Extracted session_id: {self.session_id}")
                            return True
                            
        except Exception as e:
            logger.error(f"Error connecting to SSE: {e}")
            return False
            
        return False

    async def send_json_rpc(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Send a JSON-RPC message to the server"""
        if not self.session_id:
            raise ValueError("No active session")
            
        message = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params or {}
        }
        self.message_id += 1
        
        url = f"{self.base_url}/messages/?session_id={self.session_id}"
        
        try:
            logger.info(f"Sending {method} request...")
            logger.debug(f"Request: {json.dumps(message, indent=2)}")
            
            response = await self.client.post(
                url,
                json=message,
                headers={"Content-Type": "application/json"}
            )
            
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response body: {response.text}")
            
            if response.status_code != 202:
                return {"error": f"Unexpected status code: {response.status_code}"}
                
            # For SSE responses, we need to read the event stream
            if "text/event-stream" in response.headers.get("content-type", ""):
                return await self._read_sse_response()
            else:
                try:
                    return response.json()
                except ValueError:
                    return {"raw_response": response.text}
                    
        except Exception as e:
            logger.error(f"Error sending request: {e}")
            return {"error": str(e)}

    async def _read_sse_response(self, timeout: float = 10.0) -> Dict[str, Any]:
        """Read the SSE response for the current session"""
        if not self.session_id:
            return {"error": "No active session"}
            
        sse_url = f"{self.base_url}/sse"
        start_time = time.time()
        
        try:
            logger.info(f"Opening new SSE connection to {sse_url}")
            async with self.client.stream(
                "GET",
                sse_url,
                headers={
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache"
                },
                timeout=30.0
            ) as response:
                logger.info(f"SSE connection status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    error_msg = f"SSE connection failed: {response.status_code}"
                    logger.error(error_msg)
                    return {"error": error_msg}
                
                buffer = ""
                event_type = "message"
                
                async for line in response.aiter_lines():
                    if time.time() - start_time > timeout:
                        error_msg = "Timeout waiting for SSE response"
                        logger.error(error_msg)
                        return {"error": error_msg}
                        
                    line = line.strip()
                    logger.debug(f"SSE Line: {line}")
                    
                    if not line:
                        continue
                        
                    if line.startswith(":"):  # Comment line
                        continue
                        
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                        logger.debug(f"SSE Event Type: {event_type}")
                        continue
                        
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        buffer = data  # Reset buffer for new data
                        
                        try:
                            parsed = json.loads(data)
                            logger.debug(f"Parsed JSON from SSE: {json.dumps(parsed, indent=2)}")
                            return parsed
                        except json.JSONDecodeError:
                            logger.warning(f"Non-JSON SSE data: {data}")
                            # Keep the raw data in case it's a partial message
                            buffer = data
                    
                    # Check if we have a complete message in buffer
                    if buffer:
                        try:
                            parsed = json.loads(buffer)
                            logger.debug(f"Parsed buffered JSON: {json.dumps(parsed, indent=2)}")
                            return parsed
                        except json.JSONDecodeError:
                            # Not a complete JSON yet, wait for more data
                            continue
                            
        except Exception as e:
            error_msg = f"Error reading SSE response: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
            
        error_msg = "No data received from SSE"
        logger.error(error_msg)
        return {"error": error_msg}

async def test_mcp_server(base_url: str):
    """Test the MCP server's listTools functionality"""
    logger.info("\n" + "="*50)
    logger.info(f"Testing MCP server at {base_url}")
    logger.info("="*50)
    
    async with MCPInvestigator(base_url) as mcp:
        # Step 1: Connect to SSE and get session ID
        logger.info("\n1. Connecting to SSE endpoint...")
        if not await mcp.connect_sse():
            logger.error("❌ Failed to establish SSE connection")
            return
        logger.info("✅ Successfully connected to SSE")
            
        # Step 2: Send initialize message
        logger.info("\n2. Sending initialize message...")
        init_params = {
            "protocolVersion": "1.0.0",
            "clientInfo": {
                "name": "mcp-tester",
                "version": "0.1.0"
            },
            "capabilities": {}
        }
        logger.debug(f"Initialize params: {json.dumps(init_params, indent=2)}")
        init_response = await mcp.send_json_rpc("initialize", init_params)
        logger.info("Initialize response:")
        print(json.dumps(init_response, indent=2))
        
        # Step 3: Send listTools message
        logger.info("\n3. Sending listTools message...")
        tools_response = await mcp.send_json_rpc("listTools")
        logger.info("listTools response:")
        print(json.dumps(tools_response, indent=2))
        
        # Step 4: Check if we got a tools list
        if "result" in tools_response and isinstance(tools_response["result"], list):
            logger.info(f"✅ Found {len(tools_response['result'])} tools")
            for i, tool in enumerate(tools_response["result"], 1):
                logger.info(f"  Tool {i}: {tool.get('name', 'unnamed')}")
                if "description" in tool:
                    logger.info(f"     Description: {tool['description']}")
                if "parameters" in tool:
                    logger.info(f"     Parameters: {json.dumps(tool['parameters'], indent=4)}")
        else:
            logger.warning("❌ No tools list found in response")
            if "error" in tools_response:
                logger.error(f"Error from server: {tools_response['error']}")
            else:
                logger.debug("Raw response does not contain a 'result' field with a list of tools")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    else:
        server_url = "http://localhost:8054"  # Default to localhost
        
    try:
        asyncio.run(test_mcp_server(server_url))
    except KeyboardInterrupt:
        logger.info("Investigation stopped by user")
    except Exception as e:
        logger.exception("Fatal error during investigation")
