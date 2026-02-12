#!/usr/bin/env python3
"""
Direct tool test for MCP server.
This script directly calls known tools on the MCP server.
"""
import asyncio
import json
import logging
import os
import time
import uuid
import httpx
import sseclient
import requests
from typing import Dict, Any, Optional, AsyncGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('direct_tool_test.log')
    ]
)
logger = logging.getLogger('MCPToolTester')

class SSESession:
    """Synchronous SSE session handler"""
    def __init__(self, url: str):
        self.url = url
        self.session = requests.Session()
        self.response = None
        self.sse_client = None
        self.session_id = None
        
    def __enter__(self):
        logger.info(f"🔌 Connecting to SSE endpoint: {self.url}")
        self.response = self.session.get(
            self.url,
            stream=True,
            headers={
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            },
            timeout=30.0
        )
        
        # Check if the response is valid
        if self.response.status_code != 200:
            logger.error(f"❌ Failed to connect to SSE endpoint: {self.response.status_code}")
            return self
            
        # Initialize SSE client
        self.sse_client = sseclient.SSEClient(self.response)
        
        # Try to get session ID from headers
        self.session_id = self.response.headers.get('x-session-id')
        if self.session_id:
            logger.info(f"✅ Got session ID from headers: {self.session_id}")
            return self
            
        # If no session ID in headers, try to get it from the first event
        try:
            logger.info("No session ID in headers, checking SSE events...")
            event = next(self.sse_client.events())
            logger.info(f"Received SSE event: {event.event}")
            
            if event.event == 'endpoint' and event.data:
                from urllib.parse import urlparse, parse_qs
                url = urlparse(event.data)
                params = parse_qs(url.query)
                self.session_id = params.get('session_id', [None])[0]
                if self.session_id:
                    logger.info(f"✅ Got session ID from SSE event: {self.session_id}")
        except Exception as e:
            logger.error(f"Error processing SSE event: {e}")
            
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.response:
            self.response.close()
        if self.session:
            self.session.close()
            
    def get_session_id(self) -> Optional[str]:
        """Get the session ID from the SSE connection"""
        return self.session_id

class MCPToolTester:
    def __init__(self, base_url: str = "http://localhost:8054"):
        self.base_url = base_url.rstrip('/')
        self.session_id: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.message_id = 1
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.sse_task: Optional[asyncio.Task] = None
        self.sse_connected = asyncio.Event()
        self.sse_messages = asyncio.Queue()

    async def __aenter__(self):
        self.client = httpx.AsyncClient()
        # Start the SSE listener in the background
        self.sse_task = asyncio.create_task(self._listen_for_responses())
        # Wait for SSE connection to be established
        try:
            await asyncio.wait_for(self.sse_connected.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.error("Timeout waiting for SSE connection")
            raise
            
        # Wait for session to be fully initialized
        try:
            await asyncio.wait_for(self._wait_for_session_ready(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for session to be ready, continuing anyway...")
            
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cancel the SSE listener task
        if self.sse_task and not self.sse_task.done():
            self.sse_task.cancel()
            try:
                await self.sse_task
            except asyncio.CancelledError:
                pass
        
        # Close the HTTP client
        if self.client:
            await self.client.aclose()

    async def get_session_id(self) -> bool:
        """Get a session ID from the SSE endpoint"""
        try:
            # Use the synchronous SSESession in a thread
            def _get_session_id() -> Optional[str]:
                with SSESession(f"{self.base_url}/sse") as sse_client:
                    return sse_client.get_session_id()
            
            # Run the synchronous code in a thread
            loop = asyncio.get_event_loop()
            session_id = await loop.run_in_executor(None, _get_session_id)
            
            if session_id:
                self.session_id = session_id
                logger.info(f"✅ Successfully obtained session ID: {session_id}")
                return True
            else:
                logger.error("❌ Failed to get session ID")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error getting session ID: {e}", exc_info=True)
            return False

    async def run_tests(self) -> None:
        """Run the MCP tool tests"""
        try:
            # First, wait for the server to be ready
            logger.info("⏳ Waiting for MCP server to be ready...")
            
            # Give the server extra time to initialize
            await asyncio.sleep(10.0)
            
            if not await self.wait_for_server_ready():
                logger.error("❌ MCP server is not ready, aborting tests")
                return
                
            logger.info("✅ MCP server is ready, starting SSE listener...")
            
            # Give the server a moment to stabilize
            await asyncio.sleep(5.0)
            
            # Start the SSE listener
            await self.start_sse_listener()
            
            # Wait for the session to be ready
            logger.info("⏳ Waiting for session to be ready...")
            await self._wait_for_session_ready()
            
            # Get a session ID from the SSE endpoint
            logger.info("⏳ Getting session ID...")
            if not await self.get_session_id():
                logger.error("❌ Failed to get session ID from SSE endpoint")
                return
                
            logger.info(f"✅ Successfully obtained session ID: {self.session_id}")
            
            # Give the server a moment to process the session
            logger.info("⏳ Giving server a moment to process the session...")
            await asyncio.sleep(5.0)
            
            # Test the dummy tool
            logger.info("\n🛠️  Testing dummy_tool...")
            result = await self.test_tool(
                "dummy_tool",
                {"test_param": "test_value"},
                timeout=15.0  # Increased timeout
            )
            logger.info(f"dummy_tool result: {result}")
            
            # Test the store_page tool
            logger.info("\n💾 Testing store_page...")
            result = await self.test_tool(
                "store_page",
                {
                    "url": "https://example.com",
                    "content": "This is a test page content",
                    "chunk_number": 0,
                    "metadata": {"test": "data"}
                },
                timeout=15.0  # Increased timeout
            )
            logger.info(f"store_page result: {result}")
            
            # Test the get_page tool
            logger.info("\n📄 Testing get_page...")
            result = await self.test_tool(
                "get_page",
                {"url": "https://example.com"},
                timeout=15.0  # Increased timeout
            )
            logger.info(f"get_page result: {result}")
            
            return True
                
        except Exception as e:
            logger.error(f"❌ Error running tests: {e}", exc_info=True)
            return False
        finally:
            # Clean up
            await self.cleanup()

    async def wait_for_server_ready(self, timeout: float = 120.0) -> bool:
        """Wait for the MCP server to be ready to accept connections"""
        start_time = time.time()
        logger.info("⏳ Waiting for MCP server to be ready...")
        
        while time.time() - start_time < timeout:
            try:
                # Try to connect to the server using the root endpoint
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/",
                        timeout=5.0,
                        follow_redirects=True
                    )
                    
                    # If we get any response, the server is up
                    if response.status_code < 500:
                        logger.info("✅ MCP server is responding")
                        # Give the server a moment to fully initialize
                        await asyncio.sleep(5.0)
                        return True
                        
            except Exception as e:
                logger.debug(f"Server not ready yet: {e}")
                
            # Wait a bit before trying again
            await asyncio.sleep(1.0)
            
        logger.error("❌ Timeout waiting for MCP server to be ready")
        return False
        
    async def _wait_for_session_ready(self) -> None:
        """Wait for the session to be fully initialized"""
        logger.info("⏳ Waiting for session to be ready...")
        start_time = time.time()
        
        # First, wait for the SSE connection to be established
        try:
            logger.info("⏳ Waiting for SSE connection to be established...")
            await asyncio.wait_for(self.sse_connected.wait(), timeout=30.0)
            logger.info("✅ SSE connection established")
        except asyncio.TimeoutError:
            logger.warning("❌ Timeout waiting for SSE connection")
            return
        
        # Give the server extra time to process the connection
        logger.info("⏳ Giving server time to process the connection...")
        await asyncio.sleep(5.0)
            
        # Now wait for the session to be fully initialized
        # by listening for the initialization complete message
        logger.info("SSE connected, waiting for session initialization...")
        
        # Set a timeout for the entire initialization process
        init_timeout = 120.0  # 120 seconds max
        last_message_time = time.time()
        last_log_time = time.time()
        
        while time.time() - start_time < init_timeout:
            try:
                # Log progress every 5 seconds
                current_time = time.time()
                if current_time - last_log_time >= 5.0:
                    elapsed = int(current_time - start_time)
                    logger.info(f"⏳ Still waiting for session initialization... ({elapsed}s elapsed)")
                    last_log_time = current_time
                
                # Try to get a message from the SSE stream with a short timeout
                try:
                    message = await asyncio.wait_for(
                        self.sse_messages.get(),
                        timeout=2.0
                    )
                    
                    last_message_time = time.time()
                    logger.debug(f"Received message during init: {message}")
                    
                    # Check if this is a session initialization message
                    if message.get('method') == 'session/initialized':
                        logger.info("✅ Session is ready")
                        # Give the server extra time to process the initialization
                        logger.info("⏳ Giving server time to finalize initialization...")
                        await asyncio.sleep(5.0)
                        return
                        
                except asyncio.TimeoutError:
                    # No message received, continue waiting
                    if time.time() - last_message_time > 15.0:
                        logger.warning("No messages received for 15 seconds, continuing...")
                        last_message_time = time.time()
                    continue
                
                # Send a ping to keep the connection alive
                try:
                    ping_response = await self.client.get(
                        f"{self.base_url}/health",
                        timeout=5.0
                    )
                    logger.debug(f"Ping response: {ping_response.status_code}")
                except Exception as e:
                    logger.warning(f"Ping failed: {e}")
                
            except Exception as e:
                logger.warning(f"Error during session init check: {e}")
                
            await asyncio.sleep(1.0)
            
        logger.error("❌ Timeout waiting for session to be ready")
        
    async def _listen_for_responses(self, max_retries: int = 3, retry_delay: float = 5.0) -> None:
        """Background task to listen for SSE responses with reconnection logic"""
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                url = f"{self.base_url}/sse"
                params = {'session_id': self.session_id} if self.session_id else None
                
                logger.info("👂 Starting SSE listener for session %s (attempt %d/%d)", 
                          self.session_id or 'new', retry_count + 1, max_retries)
                
                async with self.client.stream(
                    'GET', 
                    url,
                    params=params,
                    timeout=30.0,
                    follow_redirects=True
                ) as response:
                    if response.status_code != 200:
                        logger.error(f"❌ Failed to connect to SSE endpoint: {response.status_code}")
                        raise ConnectionError(f"SSE endpoint returned status {response.status_code}")
                    
                    self.sse_connected.set()
                    logger.info("✅ SSE listener connected")
                    retry_count = 0  # Reset retry count on successful connection
                    
                    buffer = ""
                    async for chunk in response.aiter_text():
                        if not chunk.strip():
                            continue
                            
                        buffer += chunk
                        
                        # Process complete events (separated by double newlines)
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            event_str = event_str.strip()
                            if not event_str:
                                continue
                                
                            logger.debug(f"📨 Received SSE event: {event_str}")
                            
                            # Parse the event
                            event_data = {}
                            for line in event_str.split('\n'):
                                line = line.strip()
                                if ': ' in line:
                                    key, value = line.split(': ', 1)
                                    event_data[key] = value
                            
                            # Handle the event data
                            if 'data' in event_data:
                                try:
                                    data = json.loads(event_data['data'])
                                    logger.debug(f"📨 Received SSE data: {json.dumps(data, indent=2)}")
                                    
                                    # Check if this is a response to a pending request
                                    if 'id' in data and data['id'] in self.pending_requests:
                                        future = self.pending_requests.pop(data['id'])
                                        future.set_result(data)
                                    # Check if this is a notification (no id)
                                    elif 'method' in data and data.get('id') is None:
                                        logger.info(f"📨 Received notification: {data.get('method')}")
                                        await self.sse_messages.put(data)
                                    else:
                                        logger.debug(f"Unhandled SSE data: {data}")
                                        
                                except json.JSONDecodeError as e:
                                    logger.warning(f"⚠️ Failed to parse SSE data: {event_data['data']}, error: {e}")
                
            except (httpx.ReadTimeout, httpx.ConnectError) as e:
                logger.warning(f"⚠️ SSE connection error: {e}, reconnecting...")
                
            except asyncio.CancelledError:
                logger.info("SSE listener cancelled")
                raise
                
            except Exception as e:
                logger.error(f"❌ Error in SSE listener: {e}", exc_info=True)
                
            # If we get here, the connection was lost or an error occurred
            self.sse_connected.clear()
            retry_count += 1
            
            if retry_count < max_retries:
                logger.info(f"⏳ Reconnecting in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                
        if retry_count >= max_retries:
            logger.error(f"❌ Max retries ({max_retries}) reached for SSE listener")
    
    async def wait_for_response(self, request_id: int, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """Wait for a response to a specific request"""
        if request_id not in self.pending_requests:
            self.pending_requests[request_id] = asyncio.Future()
            
        try:
            logger.info(f"⏳ Waiting for response to request {request_id}...")
            return await asyncio.wait_for(self.pending_requests[request_id], timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response to request {request_id}")
            self.pending_requests.pop(request_id, None)
            return None
        except Exception as e:
            logger.error(f"Error waiting for response: {e}", exc_info=True)
            self.pending_requests.pop(request_id, None)
            return None

    async def send_message(self, method: str, params: Dict[str, Any], timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC message to the MCP server"""
        if not self.session_id:
            logger.error("❌ No session ID available")
            return None
        
        if not self.sse_connected.is_set():
            logger.error("❌ SSE listener is not connected")
            return None
            
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Create the tool call message
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": method,
                "arguments": params
            }
        }
        
        logger.info(f"📤 Sending {method} request (ID: {request_id})...")
        logger.debug(f"Request body: {json.dumps(message, indent=2)}")
        
        try:
            # Create a future for this request
            future = asyncio.Future()
            self.pending_requests[request_id] = future
            
            # Send the request
            response = await self.client.post(
                f"{self.base_url}/messages/?session_id={self.session_id}",
                json=message,
                timeout=timeout
            )
            
            logger.info(f"✅ {method} response status: {response.status_code}")
            
            if response.status_code == 202:
                logger.info(f"Request {request_id} accepted by server")
                
                # Wait for the response with a timeout
                try:
                    result = await asyncio.wait_for(future, timeout=timeout)
                    logger.info(f"✅ Received response for {method}:")
                    logger.info(json.dumps(result, indent=2))
                    return result
                except asyncio.TimeoutError:
                    logger.warning(f"❌ Timeout waiting for response to request {request_id}")
                    return None
                
            else:
                logger.error(f"❌ Error calling {method}: {response.status_code} - {response.text}")
                return None
                
        except httpx.TimeoutException:
            logger.error(f"❌ Timeout while calling {method}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error calling {method}: {str(e)}", exc_info=True)
            return None
            
        finally:
            # Clean up the future
            self.pending_requests.pop(request_id, None)
            
    async def test_tool(self, tool_name: str, params: Dict[str, Any], timeout: float = 30.0, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """Test a specific tool with the given parameters"""
        logger.info(f"\n🛠️  Testing {tool_name}...")
        
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"📤 Sending {tool_name} request (attempt {attempt}/{max_retries})...")
                
                # Send the tool call
                result = await self.send_message(tool_name, params, timeout=timeout)
                
                if result is not None:
                    logger.info(f"✅ {tool_name} succeeded on attempt {attempt}")
                    logger.debug(f"{tool_name} result: {json.dumps(result, indent=2)}")
                    return result
                else:
                    logger.warning(f"⚠️  {tool_name} returned no result on attempt {attempt}")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️  {tool_name} failed on attempt {attempt}: {e}")
                
                # If we have retries left, wait a bit before trying again
                if attempt < max_retries:
                    retry_delay = 2 ** attempt  # Exponential backoff
                    logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
        
        # If we get here, all retries failed
        logger.error(f"❌ {tool_name} failed after {max_retries} attempts")
        if last_error:
            logger.error(f"Last error: {last_error}")
            
        return None

    async def test_dummy_tool(self) -> Optional[Dict[str, Any]]:
        """Test the dummy_tool"""
        logger.info("\n🛠️  Testing dummy_tool...")
        result = await self.test_tool("dummy_tool", {"test_param": "test_value"})
        logger.info(f"dummy_tool result: {json.dumps(result, indent=2) if result else 'No response'}")
        return result

    async def test_store_page(self):
        """Test the store_page tool"""
        logger.info("\n💾 Testing store_page...")
        result = await self.test_tool("store_page", {
            "url": "https://example.com",
            "content": "This is a test page content",
            "chunk_number": 0,
            "metadata": {"test": "data"}
        })
        logger.info(f"store_page result: {json.dumps(result, indent=2) if result else 'No response'}")
        return result

    async def test_get_page(self, url: str, chunk_number: int = 0, source_id: str = "test-source"):
        """Test the get_page tool"""
        logger.info("\n📖 Testing get_page...")
        result = await self.send_message("get_page", {
            "url": url,
            "chunk_number": chunk_number,
            "source_id": source_id
        })
        logger.info(f"get_page result: {json.dumps(result, indent=2) if result else 'No response'}")
        return result

async def main():
    """Main function to test the MCP server tools"""
    logger.info("🚀 Starting MCP Tool Tester")
    
    async with MCPToolTester() as tester:
        # First, get a session ID
        if not await tester.get_session_id():
            logger.error("Failed to get session ID, aborting")
            return 1
        
        # Test the dummy tool
        await tester.test_dummy_tool()
        
        # Test storing a page
        store_result = await tester.test_store_page()
        
        # If store was successful, try to retrieve the page
        if store_result and 'result' in store_result and 'url' in store_result['result']:
            result_data = store_result['result']
            await tester.test_get_page(
                url=result_data['url'],
                chunk_number=result_data.get('chunk_number', 0),
                source_id=result_data.get('source_id', 'test-source')
            )
    
    return 0

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Exiting...")
    except Exception as e:
        logger.error(f"❌ Unhandled exception: {e}", exc_info=True)
