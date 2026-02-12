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

async def test_connection():
    url = "http://localhost:8054"
    
    try:
        logger.info(f"Connecting to MCP server at {url}...")
        
        # Create a simple in-memory stream for testing
        send_stream = asyncio.StreamReader()
        receive_stream = asyncio.StreamWriter()
        
        # Initialize the client session with the required parameters
        async with ClientSession(
            write_stream=receive_stream,
            read_stream=send_stream,
            server_url=url
        ) as session:
            # List available tools
            logger.info("Listing available tools...")
            tools = await session.list_tools()
            logger.info(f"Available tools: {json.dumps(tools, indent=2)}")
            
            # Test get_available_sources
            logger.info("\nTesting get_available_sources...")
            sources = await session.call("get_available_sources", {})
            logger.info(f"Available sources: {json.dumps(sources, indent=2)}")
            
            # Test crawl_website
            logger.info("\nTesting crawl_website...")
            crawl_result = await session.call(
                "crawl_website",
                params={"url": "https://example.com"}
            )
            logger.info(f"Crawl result: {json.dumps(crawl_result, indent=2)}")
            
            # Test extract_content
            logger.info("\nTesting extract_content...")
            extract_result = await session.call(
                "extract_content",
                params={"url": "https://example.com"}
            )
            logger.info(f"Extract result: {json.dumps(extract_result, indent=2)}")
            
            # Test search_web
            logger.info("\nTesting search_web...")
            search_result = await session.call(
                "search_web",
                params={"query": "What is Crawl4AI?"}
            )
            logger.info(f"Search result: {json.dumps(search_result, indent=2)}")
            
    except Exception as e:
        logger.error(f"Error during test: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_connection())
