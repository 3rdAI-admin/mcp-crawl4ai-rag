import asyncio
import httpx
import json
import logging
import time
from typing import Dict, Any, Optional, AsyncGenerator
import uuid

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_debug.log')
    ]
)
logger = logging.getLogger(__name__)

# Enable debug logging for httpx and httpcore
logging.getLogger('httpx').setLevel(logging.DEBUG)
logging.getLogger('httpcore').setLevel(logging.DEBUG)
logging.getLogger('asyncio').setLevel(logging.DEBUG)

class MCPDebugger:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.sse_url = f"{self.base_url}/sse"
        self.messages_url = f"{self.base_url}/messages/"
        self.session_id: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.message_id = 1
        self.received_messages = asyncio.Queue()
        self.sse_task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        if self.sse_task:
            self.sse_task.cancel()
            try:
                await self.sse_task
            except asyncio.CancelledError:
                pass
        await self.client.aclose()

    async def start_sse_listener(self):
        """Start listening for SSE events in the background"""
        logger.info("Starting SSE listener...")
        self.sse_task = asyncio.create_task(self._sse_listener())
        
        # Wait for session ID
        try:
            self.session_id = await asyncio.wait_for(self._wait_for_session_id(), timeout=10.0)
            logger.info(f"✅ Session ID: {self.session_id}")
            return True
        except asyncio.TimeoutError:
            logger.error("❌ Timeout waiting for session ID")
            return False

    async def _wait_for_session_id(self) -> str:
        """Wait until we receive a session ID from the SSE stream"""
        while not self.stop_event.is_set():
            try:
                message = await asyncio.wait_for(self.received_messages.get(), timeout=0.1)
                if 'session_id=' in message:
                    return message.split('session_id=')[1].split('&')[0]
            except asyncio.TimeoutError:
                continue
        raise asyncio.CancelledError()

    async def _sse_listener(self):
        """Background task to listen for SSE events"""
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
        
        logger.debug(f"Starting SSE listener with headers: {headers}")
        
        while not self.stop_event.is_set():
            try:
                logger.debug(f"Connecting to SSE endpoint: {self.sse_url}")
                async with self.client.stream("GET", self.sse_url, headers=headers) as response:
                    if response.status_code != 200:
                        logger.error(f"SSE connection failed: {response.status_code}")
                        await asyncio.sleep(1)
                        continue
                        
                    logger.info(f"Connected to SSE stream. Status: {response.status_code}")
                    logger.debug(f"Response headers: {dict(response.headers)}")
                    
                    buffer = ""
                    chunk_count = 0
                    
                    async for chunk in response.aiter_bytes():
                        if self.stop_event.is_set():
                            logger.debug("Stop event set, breaking SSE loop")
                            break
                            
                        chunk_count += 1
                        chunk_text = chunk.decode()
                        logger.debug(f"Chunk {chunk_count} received: {chunk_text!r}")
                        
                        buffer += chunk_text
                        
                        while "\n\n" in buffer:
                            event, _, buffer = buffer.partition("\n\n")
                            logger.debug(f"Processing SSE event: {event}")
                            await self._process_sse_event(event)
                        
                        # If we've received many chunks without a complete message, log the buffer
                        if chunk_count % 10 == 0 and buffer:
                            logger.debug(f"Buffer after {chunk_count} chunks: {buffer!r}")
                            
                    logger.debug(f"SSE stream ended. Buffer: {buffer!r}")
                            
            except Exception as e:
                if not self.stop_event.is_set():
                    logger.error(f"SSE error: {e}")
                    await asyncio.sleep(1)

    async def _process_sse_event(self, event_data: str):
        """Process a single SSE event"""
        try:
            event_type = None
            data = None
            
            logger.debug(f"Raw SSE event: {event_data!r}")
            
            # Parse the SSE event
            for line in event_data.splitlines():
                logger.debug(f"Processing line: {line!r}")
                if line.startswith('event: '):
                    event_type = line[7:]
                    logger.debug(f"Found event type: {event_type}")
                elif line.startswith('data: '):
                    data = line[6:]
                    logger.debug(f"Found data: {data!r}")
                elif line.startswith(':'):
                    logger.debug(f"SSE comment: {line[1:]}")
                elif line.strip():
                    logger.debug(f"Unrecognized SSE line: {line!r}")
            
            if not data:
                logger.debug("No data in SSE event")
                return
                
            logger.info(f"📨 SSE Event: {event_type or 'message'}")
            logger.debug(f"Full event data: {data}")
            
            try:
                # Try to parse as JSON
                json_data = json.loads(data)
                logger.info(f"📝 Data: {json.dumps(json_data, indent=2)}")
                
                # If this is a response to a message we sent
                if isinstance(json_data, dict) and "id" in json_data:
                    msg_id = json_data["id"]
                    logger.info(f"✅ Got response for message {msg_id}")
                    
            except json.JSONDecodeError:
                logger.info(f"📝 Raw data: {data}")
                
                # Check if this is a session ID in the endpoint URL
                if 'session_id=' in data:
                    await self.received_messages.put(data)
            
        except Exception as e:
            logger.error(f"Error processing SSE event: {e}")

    async def send_json_rpc(self, method: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Send a JSON-RPC message to the server"""
        if not self.session_id:
            raise ValueError("No active session")
            
        msg_id = self.message_id
        self.message_id += 1
        
        message = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
            "params": params or {}
        }
        
        url = f"{self.messages_url}?session_id={self.session_id}"
        
        try:
            # Log the request
            logger.info(f"📤 Sending {method} (ID: {msg_id})")
            logger.debug(f"URL: {url}")
            logger.debug(f"Request: {json.dumps(message, indent=2)}")
            
            # Send the request
            start_time = time.time()
            response = await self.client.post(
                url,
                json=message,
                headers={"Content-Type": "application/json"}
            )
            
            # Log the response
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response body: {response.text}")
            
            if response.status_code != 202:
                error_msg = f"Unexpected status code: {response.status_code}"
                logger.error(error_msg)
                return {"error": error_msg}
                
            # Wait for the SSE response
            logger.info(f"⏳ Waiting for response to {method} (ID: {msg_id})...")
            
            # Wait for up to 10 seconds for a response
            start_wait = time.time()
            while time.time() - start_wait < 10:
                try:
                    # Check if we have any messages in the queue
                    async with asyncio.timeout(0.1):
                        msg = await self.received_messages.get()
                        try:
                            data = json.loads(msg)
                            if isinstance(data, dict) and data.get("id") == msg_id:
                                logger.info(f"✅ Got response for {method} (ID: {msg_id})")
                                return data
                        except json.JSONDecodeError:
                            continue
                except asyncio.TimeoutError:
                    pass
                    
                await asyncio.sleep(0.1)
                
            error_msg = f"Timeout waiting for response to {method}"
            logger.error(error_msg)
            return {"error": error_msg}
            
        except Exception as e:
            error_msg = f"Error sending {method}: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

async def test_mcp_server(base_url: str):
    """Test the MCP server's functionality"""
    logger.info("\n" + "="*50)
    logger.info(f"🔍 Testing MCP server at {base_url}")
    logger.info("="*50 + "\n")

    async with MCPDebugger(base_url) as mcp:
        # Start the SSE listener
        if not await mcp.start_sse_listener():
            logger.error("❌ Failed to establish SSE connection")
            return
            
        # Give it a moment to establish the connection
        await asyncio.sleep(1)
        
        # Send initialize message
        logger.info("\n1. Sending initialize message...")
        init_response = await mcp.send_json_rpc("initialize", {
            "protocolVersion": "1.0.0",
            "clientInfo": {
                "name": "mcp-tester",
                "version": "0.1.0"
            },
            "capabilities": {
                "tools": {
                    "dynamicRegistration": True,
                    "dynamicHandler": True
                }
            }
        })
        
        logger.info("\nInitialize response:")
        print(json.dumps(init_response, indent=2))
        
        if "error" in init_response:
            logger.error(f"❌ Initialize failed: {init_response['error']}")
            return
            
        logger.info("✅ Initialize successful")
        
        # Send listTools message
        logger.info("\n2. Sending listTools message...")
        tools_response = await mcp.send_json_rpc("listTools")
        
        logger.info("\nlistTools response:")
        print(json.dumps(tools_response, indent=2))
        
        if "result" in tools_response and isinstance(tools_response["result"], list):
            logger.info(f"✅ Found {len(tools_response['result'])} tools")
            for i, tool in enumerate(tools_response["result"], 1):
                logger.info(f"  Tool {i}: {tool.get('name', 'unnamed')}")
                if "description" in tool:
                    logger.info(f"     Description: {tool['description']}")
                if "parameters" in tool:
                    logger.info(f"     Parameters: {json.dumps(tool['parameters'], indent=4)}")
        else:
            logger.error("❌ No tools list found in response")
            if "error" in tools_response:
                logger.error(f"Error: {tools_response['error']}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    else:
        server_url = "http://localhost:8054"  # Default to localhost
        
    try:
        asyncio.run(test_mcp_server(server_url))
    except KeyboardInterrupt:
        logger.info("\nInvestigation stopped by user")
    except Exception as e:
        logger.exception("Fatal error during investigation")
