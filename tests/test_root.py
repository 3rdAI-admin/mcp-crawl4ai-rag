import asyncio
import json
import logging
import httpx

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_endpoint(url):
    """Test a single endpoint and return the response."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            return {
                "url": url,
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": response.text
            }
    except Exception as e:
        return {
            "url": url,
            "error": str(e)
        }

async def main():
    """Test various endpoints on the MCP server."""
    base_url = "http://localhost:8054"
    endpoints = [
        "/",
        "/sse",
        "/messages/",
        "/docs",
        "/openapi.json"
    ]
    
    print(f"Testing endpoints on {base_url}...\n")
    
    # Test each endpoint
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        print(f"Testing {url}...")
        result = await test_endpoint(url)
        
        if "error" in result:
            print(f"  Error: {result['error']}")
        else:
            print(f"  Status: {result['status']}")
            print(f"  Content-Type: {result['headers'].get('content-type', 'N/A')}")
            
            # Print a preview of the response body
            body = result['body']
            if len(body) > 100:
                body = body[:100] + "..."
            print(f"  Body: {body}")
        
        print()  # Add a blank line between endpoints

if __name__ == "__main__":
    asyncio.run(main())
