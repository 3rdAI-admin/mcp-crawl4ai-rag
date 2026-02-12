import asyncio
import httpx
from httpx_sse import aconnect_sse, ServerSentEvent
import json
import logging
from typing import AsyncGenerator, Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_debug.log')
    ]
)
logger = logging.getLogger(__name__)

class MCPDebugger:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.sse_url = f"{self.base_url}/sse"
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.session_id: Optional[str] = None
        self.message_id = 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def listen_for_events(self) -> AsyncGenerator[ServerSentEvent, None]:
        """Listen for SSE events from the server"""
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache"
        }
        
        logger.info(f"Connecting to SSE endpoint: {self.sse_url}")
        
        try:
            async with aconnect_sse(
                self.client,
                "GET",
                self.sse_url,
                headers=headers
            ) as event_source:
                logger.info("Successfully connected to SSE endpoint")
                
                async for sse in event_source.aiter_sse():
                    # Log all events with appropriate level
                    log_msg = f"[SSE] Event: {sse.event}"
                    if sse.event == "message":
                        try:
                            data = json.loads(sse.data)
                            log_msg += f"\n{json.dumps(data, indent=2)}"
                            logger.info(log_msg)
                        except json.JSONDecodeError:
                            logger.info(f"{log_msg}\nData: {sse.data}")
                    else:
                        logger.info(f"{log_msg}, Data: {sse.data}")
                    
                    # Extract session_id from endpoint event
                    if sse.event == "endpoint" and not self.session_id:
                        if 'session_id=' in sse.data:
                            self.session_id = sse.data.split('session_id=')[1].split('&')[0]
                            logger.info(f"Extracted session_id: {self.session_id}")
                    
                    yield sse
                    
        except Exception as e:
            logger.error(f"Error in SSE listener: {e}", exc_info=True)
            raise

    async def send_message(self, method: str, params: Optional[Dict] = None) -> Dict:
        """Send a JSON-RPC message to the server"""
        if not self.session_id:
            raise ValueError("No session_id available. Connect to SSE first.")
            
        message = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params or {}
        }
        self.message_id += 1
        
        url = f"{self.base_url}/messages/?session_id={self.session_id}"
        headers = {"Content-Type": "application/json"}
        
        logger.debug(f"Sending message to {url}: {json.dumps(message, indent=2)}")
        
        try:
            response = await self.client.post(
                url,
                json=message,
                headers=headers
            )
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response body: {response.text}")
            
            if response.status_code != 202:
                logger.error(f"Unexpected status code: {response.status_code}")
                
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text
            }
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

async def main():
    server_url = "http://localhost:8054"  # Update this to your MCP server URL
    
    async with MCPDebugger(server_url) as debugger:
        # Create a queue to collect all events
        events_queue = asyncio.Queue()
        
        async def collect_events():
            try:
                async for event in debugger.listen_for_events():
                    await events_queue.put(event)
            except Exception as e:
                logger.error(f"Error in event collection: {e}")
                await events_queue.put(None)  # Signal error
        
        # Start listening for events in the background
        listener_task = asyncio.create_task(collect_events())
        
        try:
            # Wait for session ID with a timeout
            logger.info("Waiting for session ID...")
            session_timeout = 10.0
            start_time = asyncio.get_event_loop().time()
            
            while debugger.session_id is None:
                if asyncio.get_event_loop().time() - start_time > session_timeout:
                    logger.error("Timed out waiting for session ID")
                    return
                await asyncio.sleep(0.1)
            
            logger.info(f"Got session ID: {debugger.session_id}")
            
            # Send initialize message
            logger.info("Sending initialize message...")
            init_params = {
                "protocolVersion": "1.0.0",
                "clientInfo": {
                    "name": "mcp-debugger",
                    "version": "0.1.0"
                },
                "capabilities": {}
            }
            await debugger.send_message("initialize", init_params)
            
            # Wait for initialization response
            logger.info("Waiting for initialization response...")
            init_response = await asyncio.wait_for(events_queue.get(), timeout=10.0)
            logger.info(f"Initialization response: {init_response}")
            
            # Send list_tools message
            logger.info("Sending list_tools message...")
            await debugger.send_message("listTools")
            
            # Wait for tools response with a timeout
            try:
                tools_response = await asyncio.wait_for(events_queue.get(), timeout=10.0)
                logger.info(f"Tools response: {tools_response}")
            except asyncio.TimeoutError:
                logger.error("Timed out waiting for tools response")
            
            # Keep running to process events
            logger.info("Listening for additional events (press Ctrl+C to exit)...")
            while True:
                try:
                    event = await asyncio.wait_for(events_queue.get(), timeout=1.0)
                    if event is None:  # Error signal from collector
                        break
                    logger.info(f"Received event: {event}")
                except asyncio.TimeoutError:
                    pass  # Continue waiting for events
                except Exception as e:
                    logger.error(f"Error processing event: {e}")
                    break
                
        except asyncio.TimeoutError:
            logger.error("Timed out waiting for session ID")
        except asyncio.CancelledError:
            logger.info("Shutting down...")
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
        finally:
            if 'listener_task' in locals():
                listener_task.cancel()
                try:
                    await listener_task
                except (asyncio.CancelledError, StopAsyncIteration):
                    pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Debugger stopped by user")
    except Exception as e:
        logger.exception("Fatal error in debugger")
