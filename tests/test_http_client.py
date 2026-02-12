#!/usr/bin/env python3
"""
Simple HTTP client to test MCP server endpoints.
"""
import asyncio
import json
import logging
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_endpoints():
    """Test the MCP server endpoints."""
    base_url = "http://localhost:8054"
    
    async with httpx.AsyncClient() as client:
        # Test health check endpoint
        try:
            logger.info(f"Testing health check endpoint at {base_url}/health")
            health_response = await client.get(f"{base_url}/health")
            health_response.raise_for_status()
            logger.info(f"Health check response: {health_response.json()}")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
        
        # Test SSE endpoint
        try:
            logger.info(f"Testing SSE endpoint at {base_url}/sse")
            sse_response = await client.get(
                f"{base_url}/sse",
                headers={"Accept": "text/event-stream"},
                timeout=10.0
            )
            logger.info(f"SSE response status: {sse_response.status_code}")
            logger.info(f"SSE response headers: {sse_response.headers}")
            logger.info(f"SSE response text: {sse_response.text[:500]}...")
        except Exception as e:
            logger.error(f"SSE test failed: {e}")
        
        # Test tools endpoint
        try:
            logger.info(f"Testing tools endpoint at {base_url}/sse/tools")
            tools_response = await client.get(f"{base_url}/sse/tools")
            tools_response.raise_for_status()
            logger.info(f"Tools response: {json.dumps(tools_response.json(), indent=2)}")
        except Exception as e:
            logger.error(f"Tools endpoint test failed: {e}")
        
        # Test message endpoint
        try:
            logger.info(f"Testing message endpoint at {base_url}/sse/message")
            message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "listTools",
                "params": {}
            }
            message_response = await client.post(
                f"{base_url}/sse/message",
                json=message,
                timeout=10.0
            )
            message_response.raise_for_status()
            logger.info(f"Message response: {json.dumps(message_response.json(), indent=2)}")
        except Exception as e:
            logger.error(f"Message endpoint test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
