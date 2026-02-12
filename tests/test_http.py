import httpx
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_connection():
    url = "http://localhost:8054"
    
    try:
        # Test if the server is responding
        async with httpx.AsyncClient() as client:
            # Simple health check
            health_check = await client.get(f"{url}/health")
            logger.info(f"Health check status: {health_check.status_code}")
            logger.info(f"Health check response: {health_check.text}")
            
            # List available tools
            logger.info("\nListing available tools...")
            response = await client.post(
                f"{url}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "list_tools",
                    "id": 1
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Available tools: {json.dumps(result, indent=2)}")
            else:
                logger.error(f"Error listing tools: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_connection())
