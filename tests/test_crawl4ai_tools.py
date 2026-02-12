import asyncio
import json
import logging
from mcp.client.session import ClientSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_tools():
    url = "http://localhost:8054"
    
    try:
        # Connect to the MCP server
        logger.info(f"Connecting to MCP server at {url}...")
        async with ClientSession(url, transport="sse") as session:
            # List available tools
            logger.info("Listing available tools...")
            tools = await session.list_tools()
            logger.info("Available tools:")
            for tool in tools:
                logger.info(f"- {tool['name']}: {tool.get('description', 'No description')}")
            
            # Test crawl_website
            logger.info("\nTesting crawl_website...")
            crawl_result = await session.call(
                "crawl_website",
                params={"url": "https://example.com"}
            )
            logger.info("Crawl result:")
            print(json.dumps(crawl_result, indent=2))
            
            # Test extract_content
            logger.info("\nTesting extract_content...")
            extract_result = await session.call(
                "extract_content",
                params={"url": "https://example.com"}
            )
            logger.info("Extract result:")
            print(json.dumps(extract_result, indent=2))
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_tools())
