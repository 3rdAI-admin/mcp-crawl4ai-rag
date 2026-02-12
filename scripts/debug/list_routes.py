import asyncio
import httpx
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def list_routes():
    """List all available routes from the FastAPI application."""
    base_url = "http://localhost:8054"
    openapi_url = f"{base_url}/openapi.json"
    
    async with httpx.AsyncClient() as client:
        try:
            # First, try to get the OpenAPI schema
            logger.info(f"Fetching OpenAPI schema from {openapi_url}")
            response = await client.get(openapi_url)
            response.raise_for_status()
            
            openapi_schema = response.json()
            
            # Extract and print routes
            paths = openapi_schema.get('paths', {})
            if paths:
                logger.info("\nAvailable routes:")
                for path, methods in paths.items():
                    for method in methods.keys():
                        if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                            logger.info(f"{method.upper()} {path}")
                            # Print the summary if available
                            if 'summary' in methods[method]:
                                logger.info(f"  Summary: {methods[method]['summary']}")
                            # Print the description if available
                            if 'description' in methods[method]:
                                logger.info(f"  Description: {methods[method]['description']}")
                            logger.info("")
            else:
                logger.warning("No routes found in OpenAPI schema")
                
            # Also try to get the docs page
            docs_url = f"{base_url}/docs"
            logger.info(f"\nYou can also check the API documentation at: {docs_url}")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(list_routes())
