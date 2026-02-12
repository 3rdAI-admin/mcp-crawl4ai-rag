#!/usr/bin/env python3
"""
Direct SSE connection test for MCP server.
This script connects to the MCP server's SSE endpoint and processes events.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional
import httpx
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('direct_sse_test.log')
    ]
)
logger = logging.getLogger(__name__)

class MCPSSETester:
    def __init__(self, base_url: str = "http://localhost:8054"):
        self.base_url = base_url.rstrip('/')
        self.sse_url = f"{self.base_url}/sse"
        self.session_id: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
        self.stop_event = asyncio.Event()
        self._session_id_event = asyncio.Event()
        self.message_id = 1
        self.available_tools: Dict[str, dict] = {}
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._logger = logging.getLogger('MCPSSETester')
        self._logger.setLevel(logging.DEBUG)

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self

    async def wait_for_session_id(self, timeout: int = 10) -> bool:
        """Wait for the session ID to be available"""
        logger.info("⏳ Waiting for session ID...")
        
        # Ensure we have an event object
        if not hasattr(self, '_session_id_event'):
            logger.debug("Creating new _session_id_event in wait_for_session_id")
            self._session_id_event = asyncio.Event()
        
        try:
            # Log the current state of the event before waiting
            logger.debug(f"🔍 Before wait - _session_id_event is set: {self._session_id_event.is_set()}")
            
            # Wait for the event to be set with a timeout
            logger.debug(f"⏱️ Waiting for _session_id_event for up to {timeout} seconds...")
            await asyncio.wait_for(self._session_id_event.wait(), timeout=timeout)
            
            # Log the state after waiting
            logger.debug(f"🔍 After wait - _session_id_event is set: {self._session_id_event.is_set()}")
            
            if not self.session_id:
                logger.error("❌ Session ID event was set but session_id is still None")
                return False
                
            logger.info(f"✅ Successfully retrieved session ID: {self.session_id}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Timeout waiting for session ID after {timeout} seconds")
            logger.debug("This could be due to:")
            logger.debug("1. The MCP server not sending the endpoint event")
            logger.debug("2. The SSE connection not being established properly")
            logger.debug("3. The session ID extraction logic not working as expected")
            
            # Log the current state for debugging
            logger.debug(f"Current session_id: {self.session_id}")
            if hasattr(self, '_session_id_event'):
                logger.debug(f"_session_id_event is set: {self._session_id_event.is_set()}")
            else:
                logger.debug("_session_id_event does not exist")
                
            return False
        except Exception as e:
            logger.error(f"❌ Error while waiting for session ID: {e}", exc_info=True)
            return False
            
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        if self.client:
            await self.client.aclose()

    async def connect_sse(self) -> bool:
        """Connect to the SSE endpoint and extract session ID"""
        if not self.client:
            raise RuntimeError("Client not initialized")

        logger.info(f"🔌 Connecting to SSE endpoint: {self.sse_url}")
        
        try:
            # Make initial SSE connection
            logger.debug("Creating SSE connection...")
            async with self.client.stream(
                "GET",
                self.sse_url,
                headers={
                    "Accept": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                },
                timeout=30.0
            ) as response:
                logger.debug("SSE connection established, checking response...")
                
                if response.status_code != 200:
                    logger.error(f"❌ SSE connection failed: {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return False
                
                logger.info("✅ SSE connection established successfully")
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                # Process the SSE stream
                await self._read_sse_stream(response)
                
                logger.info("🔌 SSE stream ended")
                return True
                
        except Exception as e:
            logger.error(f"Error in SSE connection: {e}")
            return False

    async def _read_sse_stream(self, response):
        """Read and process the SSE stream"""
        try:
            logger.info("📡 Starting to read SSE stream...")
            
            # Read the response in chunks
            async for chunk in response.aiter_bytes():
                logger.debug("\n" + "="*60)
                logger.debug(f"📦 RAW CHUNK RECEIVED: {chunk!r}")
                
                # Process the chunk as text
                try:
                    chunk_text = chunk.decode('utf-8')
                    logger.debug(f"📝 DECODED CHUNK: {chunk_text!r}")
                    
                    # Split by double newlines to separate events
                    events = chunk_text.split('\n\n')
                    logger.debug(f"🔍 FOUND {len(events)} EVENTS IN CHUNK")
                    
                    for i, event_data in enumerate(events, 1):
                        if not event_data.strip():
                            logger.debug(f"  🔹 Event {i}: Empty, skipping")
                            continue
                            
                        logger.debug(f"\n  🔄 PROCESSING EVENT {i}:")
                        logger.debug("  " + "-"*50)
                        logger.debug(f"  {event_data}")
                        logger.debug("  " + "-"*50)
                        
                        # Process the event
                        try:
                            await self._process_sse_event(event_data)
                            logger.debug(f"  ✅ Successfully processed event {i}")
                        except Exception as e:
                            logger.error(f"  ❌ Error processing event {i}: {e}", exc_info=True)
                        
                        # Check if we should stop
                        if self.stop_event.is_set():
                            logger.info("🛑 Stop event set, closing connection")
                            return
                            
                except UnicodeDecodeError as e:
                    logger.error(f"❌ Error decoding chunk: {e}")
                    continue
                    
                except Exception as e:
                    logger.error(f"❌ Error processing chunk: {e}", exc_info=True)
                    continue
                        
        except asyncio.CancelledError:
            logger.info("🔌 SSE stream cancelled")
            raise
            
        except Exception as e:
            logger.error(f"❌ Error reading SSE stream: {e}", exc_info=True)
            
        finally:
            logger.info("🔌 SSE stream ended")

    async def _process_sse_event(self, event_data: str):
        """Process a single SSE event"""
        try:
            logger.debug("\n" + "="*80)
            logger.debug(f"🔍 [PROCESS_SSE_EVENT] Instance: {id(self)}")
            logger.debug(f"🔍 Raw event data: {event_data!r}")
            
            if not event_data.strip():
                logger.debug("❌ Empty event data, skipping")
                return
            
            # Initialize variables to hold parsed data
            event_type = None
            data = None
            
            # Parse the SSE event line by line
            for line in event_data.splitlines():
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('event:'):
                    event_type = line[6:].strip()
                    logger.debug(f"🔹 Event type: {event_type}")
                elif line.startswith('data:'):
                    data = line[5:].strip()
                    logger.debug(f"🔹 Data: {data}")
            
            # Log the parsed event
            logger.info(f"📨 [EVENT] Type: {event_type or 'message'}, Data: {data or 'None'}")
            
            # Handle the session ID from the endpoint event
            if event_type == 'endpoint' and data:
                await self._handle_endpoint_event(data)
            # Handle incoming messages
            elif event_type == 'message' and data:
                await self._handle_message_event(data)
            
            logger.debug("-"*80 + "\n")
            
        except Exception as e:
            logger.error(f"❌ [ERROR] Unexpected error in _process_sse_event: {e}", exc_info=True)
    
    async def _handle_endpoint_event(self, data: str):
        """Handle the endpoint event containing session ID"""
        try:
            logger.info("\n🔑 [PROCESS_ENDPOINT] Processing endpoint event")
            
            # Extract session_id from the URL
            if 'session_id=' in data:
                session_part = data.split('session_id=')[1]
                self.session_id = session_part.split('&')[0] if '&' in session_part else session_part
                self.session_id = self.session_id.strip('\"\'')
                
                logger.info(f"✅ [SESSION_ID] Extracted: {self.session_id}")
                
                # Initialize event if it doesn't exist
                if not hasattr(self, '_session_id_event'):
                    logger.debug("Creating new _session_id_event")
                    self._session_id_event = asyncio.Event()
                
                # Set the event to notify we have a session ID
                logger.debug(f"Before set - _session_id_event is set: {self._session_id_event.is_set()}")
                self._session_id_event.set()
                logger.info("✅ [EVENT] _session_id_event set")
                logger.debug(f"After set - _session_id_event is set: {self._session_id_event.is_set()}")
                
                # Log instance state for debugging
                logger.debug("Instance state:")
                for attr, value in self.__dict__.items():
                    logger.debug(f"  {attr}: {value}")
            else:
                logger.error("❌ [ERROR] No session_id found in endpoint data")
                
        except Exception as e:
            logger.error(f"❌ [ERROR] Failed to process endpoint event: {e}", exc_info=True)
    
    async def _handle_message_event(self, data: str):
        """Handle incoming message events"""
        try:
            # Try to parse as JSON
            try:
                json_data = json.loads(data)
                logger.info("📝 [MESSAGE] Received JSON-RPC message")
                logger.debug(f"Message content:\n{json.dumps(json_data, indent=2)}")
                
                # Handle different types of messages
                if 'method' in json_data and 'params' in json_data:
                    # This is a request from the server
                    await self._handle_server_request(json_data)
                elif 'id' in json_data:
                    # This is a response to our request
                    if 'result' in json_data:
                        await self._handle_response(json_data)
                    elif 'error' in json_data:
                        await self._handle_error_response(json_data)
                
            except json.JSONDecodeError:
                logger.warning("⚠️ Could not parse message as JSON")
                logger.debug(f"Raw message: {data}")
                
        except Exception as e:
            logger.error(f"❌ [ERROR] Failed to process message event: {e}", exc_info=True)
    
    async def _handle_server_request(self, request: dict):
        """Handle incoming server requests"""
        method = request.get('method', '')
        logger.info(f"🔄 [REQUEST] Method: {method}")
        
        # Add your request handling logic here
        # Example: if method == 'some_method':
        #     await self._handle_some_method(request)
    
    async def _handle_response(self, response: dict):
        """Handle successful responses"""
        response_id = response.get('id')
        result = response.get('result', {})
        
        logger.info(f"✅ [RESPONSE] ID: {response_id}")
        logger.debug(f"Full response: {json.dumps(response, indent=2, ensure_ascii=False)}")
        
        # Check if this is the initialization response
        if response_id == 1:  # initialize response
            logger.info("🔍 Processing initialization response")
            
            # Log server information if available
            if 'serverInfo' in result:
                server_info = result['serverInfo']
                logger.info(f"ℹ️ Connected to {server_info.get('name', 'unknown')} "
                           f"(version: {server_info.get('version', 'unknown')})")
            
            # Check capabilities
            if 'capabilities' in result:
                caps = result['capabilities']
                logger.info("ℹ️ Server capabilities:")
                for cap, value in caps.items():
                    if isinstance(value, dict):
                        logger.info(f"  - {cap}: {', '.join([k for k, v in value.items() if v]) or 'None'}")
                    else:
                        logger.info(f"  - {cap}: {value}")
                
                # Some servers include tools in capabilities
                if 'tools' in caps and caps['tools']:
                    logger.info("ℹ️ Found tools in server capabilities")
                    await self._handle_list_tools_response({'tools': caps['tools']})
                    return
            
            # If no tools in initialization, try to list them
            logger.info("ℹ️ No tools found in initialization, sending listTools...")
            await self.list_tools()
        
        # Handle listTools response
        elif response_id == 2:  # listTools request ID is 2 (after initialize)
            logger.info("🔍 Processing listTools response")
            
            # Check for tools in various possible locations
            tools = None
            
            # Case 1: Direct tools array
            if 'tools' in result and isinstance(result['tools'], list):
                tools = result['tools']
            # Case 2: Nested under result key
            elif 'result' in result and 'tools' in result['result']:
                tools = result['result']['tools']
            # Case 3: Flat structure with tool information
            elif isinstance(result, dict) and any(k for k in result.keys() if 'tool' in k.lower()):
                tools = [result]
            
            if tools:
                await self._handle_list_tools_response({'tools': tools})
            else:
                logger.warning("⚠️ No tools found in listTools response")
                logger.debug(f"Response content: {json.dumps(result, indent=2, ensure_ascii=False)}")
                # Try to discover tools through other means
                await self._discover_tools()
        
        # Handle tool execution results
        elif 'result' in result and isinstance(result['result'], dict):
            await self._handle_tool_result(response_id, result['result'])
        
        # Handle other responses
        else:
            logger.info(f"📦 Received response for request ID {response_id}")
            logger.debug(f"Response content: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # If we get here and still no tools, try to discover them
            if not self.available_tools:
                await self._discover_tools()
    
    async def _discover_tools(self):
        """Try to discover tools through alternative methods"""
        logger.info("🔍 Attempting to discover tools through alternative methods...")
        
        # Method 1: Try to get tools from the server info endpoint
        try:
            info_url = f"{self.base_url}/.well-known/mcp/info"
            logger.info(f"🔍 [1/3] Checking server info at {info_url}")
            
            response = await self.client.get(info_url, timeout=5.0)
            if response.status_code == 200:
                info = response.json()
                logger.debug(f"Server info: {json.dumps(info, indent=2)}")
                if 'tools' in info:
                    logger.info("✅ Found tools in server info endpoint")
                    await self._handle_list_tools_response({'tools': info['tools']})
                    return
                else:
                    logger.info("ℹ️ No tools found in server info")
        except Exception as e:
            logger.debug(f"Could not fetch server info: {e}")
        
        # Method 2: Try to get tools from the root endpoint
        try:
            logger.info("🔍 [2/3] Checking root endpoint for tool information")
            response = await self.client.get(self.base_url, timeout=5.0)
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.debug(f"Root endpoint response: {json.dumps(data, indent=2)}")
                    if 'tools' in data:
                        logger.info("✅ Found tools in root endpoint")
                        await self._handle_list_tools_response({'tools': data['tools']})
                        return
                except json.JSONDecodeError:
                    logger.debug("Root endpoint did not return JSON")
        except Exception as e:
            logger.debug(f"Could not fetch root endpoint: {e}")
        
        # Method 3: Try to get tools from the OpenAPI/Swagger endpoint
        try:
            openapi_url = f"{self.base_url}/openapi.json"
            logger.info(f"🔍 [3/3] Checking OpenAPI endpoint at {openapi_url}")
            
            response = await self.client.get(openapi_url, timeout=5.0)
            if response.status_code == 200:
                openapi = response.json()
                if 'paths' in openapi:
                    # Look for tool-related endpoints
                    tools_endpoints = [path for path in openapi['paths'] if 'tool' in path.lower()]
                    if tools_endpoints:
                        logger.info(f"✅ Found potential tool endpoints: {', '.join(tools_endpoints)}")
                        # Try to get tools from each endpoint
                        for endpoint in tools_endpoints:
                            try:
                                tool_url = f"{self.base_url}{endpoint}"
                                logger.info(f"🔍 Checking tool endpoint: {tool_url}")
                                tool_resp = await self.client.get(tool_url, timeout=5.0)
                                if tool_resp.status_code == 200:
                                    tools = tool_resp.json()
                                    if isinstance(tools, list):
                                        await self._handle_list_tools_response({'tools': tools})
                                        return
                            except Exception as e:
                                logger.debug(f"Error checking tool endpoint {endpoint}: {e}")
        except Exception as e:
            logger.debug(f"Could not fetch OpenAPI spec: {e}")
        
        logger.warning("⚠️ Could not discover any tools from the server using standard methods")
        logger.info("\nNext steps:")
        logger.info("1. Check if the server is configured to expose tools")
        logger.info("2. Verify if authentication is required to access tools")
        logger.info("3. Consult the server's documentation for tool discovery")
        logger.info("4. Try using specific tool names if you know them in advance")
    
    async def _handle_error_response(self, response: dict):
        """Handle error responses"""
        error = response.get('error', {})
        logger.error(f"❌ [ERROR] {error.get('message', 'Unknown error')}")
        logger.debug(f"Error details: {json.dumps(error, indent=2)}")
    
    async def _handle_list_tools_response(self, result: dict):
        """Handle the response from listTools request"""
        tools = result.get('tools', [])
        if not tools and isinstance(result, dict) and 'result' in result:
            # Some servers might nest tools under a result key
            tools = result.get('result', {}).get('tools', [])
        
        if not tools:
            logger.warning("⚠️ No tools found in the response")
            return
            
        self.available_tools = {tool['name']: tool for tool in tools}
        
        logger.info(f"🔧 [TOOLS] Found {len(tools)} available tools:")
        for tool in tools:
            params = tool.get('parameters', {})
            param_desc = ", ".join([f"{name}: {p.get('type', 'any')}" 
                                 for name, p in params.items()])
            logger.info(f"  - {tool.get('name')}: {tool.get('description', 'No description')}")
            if param_desc:
                logger.info(f"    Parameters: {param_desc}")
        
        # If we have tools, log how to use them
        if self.available_tools:
            tool_names = list(self.available_tools.keys())
            logger.info(f"\n🛠️  You can now execute tools using:"
                       f"\n    await tester.execute_tool('{tool_names[0]}', {{'param': 'value'}})")
            
            # Example of executing the first tool with default parameters
            # tool_name = tool_names[0]
            # example_params = {}
            # logger.info(f"\n🚀 Example: Executing {tool_name} with {example_params}")
            # result = await self.execute_tool(tool_name, example_params)
            # if result:
            #     logger.info(f"✅ Tool execution result: {json.dumps(result, indent=2)}")
    
    async def _handle_tool_result(self, request_id: int, result: dict):
        """Handle the result of a tool execution"""
        logger.info(f"🛠️  [TOOL_RESULT] Request ID: {request_id}")
        logger.info(f"Result: {json.dumps(result, indent=2)}")
        
        # If there's a pending future for this request, set the result
        if request_id in self._pending_requests:
            future = self._pending_requests.pop(request_id)
            if not future.done():
                future.set_result(result)
    
    async def execute_tool(self, tool_name: str, params: dict, timeout: float = 30.0) -> Optional[dict]:
        """
        Execute a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to execute
            params: Parameters to pass to the tool
            timeout: Maximum time to wait for the tool to complete (in seconds)
            
        Returns:
            The tool execution result, or None if the execution failed
        """
        if not self.session_id or not self.client:
            logger.error("❌ Cannot execute tool: no session ID or client")
            return None
            
        if tool_name not in self.available_tools:
            logger.error(f"❌ Tool '{tool_name}' not found in available tools")
            return None
            
        # Create a future to track the response
        request_id = self.message_id
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        # Prepare the execute message
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "execute",
            "params": {
                "tool": tool_name,
                "parameters": params
            }
        }
        
        try:
            logger.info(f"🛠️  [TOOL_EXEC] Executing tool: {tool_name}")
            logger.debug(f"Tool parameters: {json.dumps(params, indent=2)}")
            
            # Send the execute message
            await self._send_message(message)
            
            # Wait for the response with a timeout
            try:
                result = await asyncio.wait_for(future, timeout=timeout)
                logger.info(f"✅ [TOOL_DONE] Tool '{tool_name}' executed successfully")
                return result
            except asyncio.TimeoutError:
                logger.error(f"⌛ [TIMEOUT] Tool '{tool_name}' execution timed out after {timeout} seconds")
                return None
                
        except Exception as e:
            logger.error(f"❌ [TOOL_ERROR] Failed to execute tool '{tool_name}': {e}", exc_info=True)
            return None
        finally:
            # Clean up the pending request
            self._pending_requests.pop(request_id, None)

    async def initialize_session(self):
        """Send the initialize message to the MCP server"""
        if not self.session_id or not self.client:
            logger.error("Cannot initialize: no session ID or client")
            return
            
        message = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "1.0.0",
                "clientInfo": {
                    "name": "mcp-tester",
                    "version": "0.1.0"
                },
                "capabilities": {}
            }
        }
        
        await self._send_message(message)
        
    async def list_tools(self) -> bool:
        """
        Send the listTools message to the MCP server
        
        Returns:
            bool: True if the request was sent successfully, False otherwise
        """
        if not self.session_id or not self.client:
            logger.error("❌ Cannot list tools: no session ID or client")
            return False
            
        message = {
            "jsonrpc": "2.0",
            "id": 2,  # Fixed ID for listTools to make it easier to track
            "method": "listTools",
            "params": {}
        }
        
        logger.info(f"📋 Sending listTools request (ID: {message['id']})")
        return await self._send_message(message)
    
    async def _send_message(self, message: Dict[str, Any]) -> bool:
        """
        Send a JSON-RPC message to the MCP server
        
        Args:
            message: The JSON-RPC message to send
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        if not self.session_id or not self.client:
            logger.error("❌ Cannot send message: no session ID or client")
            return False
            
        url = f"{self.base_url}/messages/?session_id={self.session_id}"
        
        try:
            method = message.get('method', 'unknown')
            msg_id = message.get('id', 'unknown')
            logger.info(f"📤 Sending {method} request (ID: {msg_id})...")
            logger.debug(f"Request URL: {url}")
            logger.debug(f"Request body: {json.dumps(message, indent=2)}")
            
            response = await self.client.post(
                url,
                json=message,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=10.0
            )
            
            logger.info(f"✅ {method} response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            if response.status_code != 202:
                logger.error(f"❌ Unexpected status code: {response.status_code}")
                logger.debug(f"Response body: {response.text}")
                return False
                
            logger.debug(f"Request {msg_id} accepted by server")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}", exc_info=True)
            return False

async def test_known_tools(tester):
    """Test the known tools directly"""
    logger.info("\n🔧 Testing known tools directly...")
    
    # Test dummy_tool
    logger.info("\n🛠️  Testing dummy_tool...")
    dummy_result = await tester.execute_tool(
        "dummy_tool", 
        {"test_param": "test_value"}
    )
    logger.info(f"dummy_tool result: {dummy_result}")
    
    # Test store_page
    logger.info("\n💾 Testing store_page...")
    store_result = await tester.execute_tool(
        "store_page",
        {
            "url": "https://example.com",
            "content": "This is a test page content",
            "chunk_number": 0,
            "metadata": {"test": "data"}
        }
    )
    logger.info(f"store_page result: {store_result}")
    
    # If store was successful, try to retrieve the page
    if store_result and 'url' in store_result:
        logger.info("\n📖 Testing get_page...")
        get_result = await tester.execute_tool(
            "get_page",
            {
                "url": store_result['url'],
                "chunk_number": 0,
                "source_id": store_result.get('source_id', 'test-source')
            }
        )
        logger.info(f"get_page result: {get_result}")

async def main():
    """Main function to test the MCP server"""
    logger.info("🚀 Starting MCP SSE Tester")
    
    async with MCPSSETester() as tester:
        try:
            # Start the SSE connection
            connect_task = asyncio.create_task(tester.connect_sse())
            
            # Wait for session ID with a timeout
            logger.info("⏳ Waiting for session ID...")
            if not await tester.wait_for_session_id(timeout=10.0):
                logger.error("❌ Failed to retrieve session ID")
                tester.stop_event.set()
                await connect_task
                return 1  # Exit with error code
                
            logger.info(f"✅ Successfully connected with session ID: {tester.session_id}")
            
            # Send initialize message
            logger.info("📤 Sending initialize message...")
            await tester.initialize_session()
            
            # Try to list tools first
            logger.info("🔍 Attempting to list tools...")
            await tester.list_tools()
            
            # Wait a moment for the response
            await asyncio.sleep(2)
            
            # If no tools were discovered, try the known tools directly
            if not tester.available_tools:
                logger.warning("⚠️ No tools discovered through listTools, trying known tools...")
                await test_known_tools(tester)
            
            # Keep running to receive responses
            logger.info("\n⏳ Waiting for responses (press Ctrl+C to exit)...")
            
            # Check for tools periodically
            while not tester.stop_event.is_set():
                if not tester.available_tools:
                    logger.info("\n🔍 No tools discovered yet, sending listTools request...")
                    await tester.list_tools()
                    
                    # Also try to discover tools through alternative methods
                    await tester._discover_tools()
                
                # Wait before checking again
                await asyncio.sleep(10)
                
                # Check if we should exit (e.g., if we've discovered tools and completed our task)
                if tester.available_tools and not tester.stop_event.is_set():
                    # Uncomment to automatically execute the first tool
                    # tool_name = next(iter(tester.available_tools))
                    # logger.info(f"\n🛠️  Executing tool: {tool_name}")
                    # result = await tester.execute_tool(tool_name, {"example_param": "value"})
                    # if result:
                    #     logger.info(f"✅ Tool result: {json.dumps(result, indent=2)}")
                    # tester.stop_event.set()  # Exit after first tool execution
                    pass
                
        except asyncio.CancelledError:
            logger.info("\n🛑 Shutting down...")
        except Exception as e:
            logger.error(f"❌ Error in main: {e}", exc_info=True)
        finally:
            tester.stop_event.set()
            if 'connect_task' in locals():
                await connect_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
