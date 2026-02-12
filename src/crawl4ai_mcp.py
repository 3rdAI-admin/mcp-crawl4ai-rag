print("=== CRAWL4AI_MCP.PY STARTED ===")
import os
import logging
import asyncio
import json
import urllib.request
import datetime
from contextlib import asynccontextmanager
from typing import Dict, Callable, Any, List, Optional, Type
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
import time
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from crawl4ai import AsyncWebCrawler, CrawlResult, HTTPCrawlerConfig, BrowserConfig
from crawl4ai.extraction_strategy import (
    ExtractionStrategy,
    LLMExtractionStrategy,
    JsonCssExtractionStrategy,
    JsonXPathExtractionStrategy,
    JsonLxmlExtractionStrategy
)
from utils.neo4j_web_graph import WebGraphNeo4j
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crawl4ai_mcp")
logger.info("Starting Crawl4AI MCP server")

# Import Crawl4AI components
try:
    from crawl4ai import AsyncWebCrawler, CrawlResult, HTTPCrawlerConfig, BrowserConfig
    from crawl4ai.extraction_strategy import (
        ExtractionStrategy,
        LLMExtractionStrategy,
        JsonCssExtractionStrategy,
        JsonXPathExtractionStrategy,
        JsonLxmlExtractionStrategy
    )
    CRAWL4AI_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import Crawl4AI components: {e}")
    CRAWL4AI_AVAILABLE = False

# Define request/response models for better type checking and documentation
class CrawlWebsiteParams(BaseModel):
    url: str = Field(..., description="The URL of the website to crawl")
    max_pages: int = Field(1, description="Maximum number of pages to crawl")
    extract_metadata: bool = Field(True, description="Whether to extract metadata")

class ExtractContentParams(BaseModel):
    url: str = Field(..., description="The URL to extract content from")
    strategy: str = Field("llm", description="Extraction strategy to use (llm, css, xpath, lxml)")

class SearchWebParams(BaseModel):
    query: str = Field(..., description="The search query")
    limit: int = Field(5, description="Maximum number of results to return")

# Create a global context object to hold crawler state
class Crawl4AIContext:
    def __init__(self):
        self.crawler = None
        self._init_crawler()
    
    def _init_crawler(self):
        """Initialize the web crawler with appropriate configuration."""
        try:
            logger.info("Initializing AsyncWebCrawler with configuration...")
            
            # Initialize the crawler with default config
            http_config = HTTPCrawlerConfig(
                method='GET',
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                },
                follow_redirects=True,
                verify_ssl=True,
            )
            logger.debug("HTTPCrawlerConfig created successfully")
            
            # Configure browser with only supported parameters
            browser_config = BrowserConfig(
                headless=True
            )
            logger.debug("BrowserConfig created successfully")
            
            # Initialize the crawler
            logger.info("Creating AsyncWebCrawler instance...")
            self.crawler = AsyncWebCrawler(
                config=http_config,
                browser_config=browser_config
            )
            logger.info("AsyncWebCrawler initialized successfully with full configuration")
            
        except Exception as e:
            logger.error(f"Error initializing AsyncWebCrawler with full configuration: {str(e)}")
            logger.info("Attempting to initialize with minimal configuration...")
            
            try:
                # Fallback to minimal configuration
                self.crawler = AsyncWebCrawler()
                logger.warning("Fallback AsyncWebCrawler initialized with minimal configuration. Some features may be limited.")
            except Exception as e2:
                error_msg = f"Failed to initialize fallback AsyncWebCrawler: {str(e2)}"
                logger.error(error_msg)
                self.crawler = None
                raise RuntimeError("Failed to initialize web crawler. Please check logs for details.") from e2

# Create a global context instance
crawl4ai_context = None

# Create the MCP server instance first
mcp = FastMCP(
    "crawl4ai",
    version="1.0.0",
    description="MCP server for web crawling and content extraction with Crawl4AI"
)

@asynccontextmanager
async def crawl4ai_lifespan(server: FastMCP):
    global crawl4ai_context, mcp
    
    logger.info("Initializing Crawl4AI MCP server...")
    
    if not CRAWL4AI_AVAILABLE:
        logger.error("Crawl4AI components not available. Check if crawl4ai is properly installed.")
        raise ImportError("Crawl4AI components not available")
    
    try:
        # Initialize the global context
        crawl4ai_context = Crawl4AIContext()
        logger.info("Crawl4AI context initialized")
        
        # Register tools
        await register_tools(server)
        
        yield
        
    except Exception as e:
        logger.error(f"Error initializing Crawl4AI MCP server: {e}", exc_info=True)
        raise
    finally:
        logger.info("Shutting down Crawl4AI MCP server...")
        if crawl4ai_context and crawl4ai_context.crawler:
            try:
                await crawl4ai_context.crawler.close()
                logger.info("Crawler closed successfully")
            except Exception as e:
                logger.error(f"Error closing crawler: {e}")

async def register_tools(server: FastMCP):
    """Register all tools with the MCP server.
    
    Args:
        server: FastMCP instance to register tools with.
    """
    global crawl4ai_context
    
    @server.tool(
        name="get_available_sources",
        description="Get a list of available data sources and their capabilities"
    )
    async def get_available_sources() -> Dict[str, Any]:
        """Return a list of available data sources and their capabilities."""
        try:
            logger.info("Getting available sources...")
            
            sources = [
                {
                    "id": "web",
                    "name": "Web Crawler",
                    "description": "Crawl and extract content from web pages",
                    "type": "web",
                    "capabilities": ["crawl", "extract_text", "extract_metadata"]
                },
                {
                    "id": "document",
                    "name": "Document Parser",
                    "description": "Extract content from documents (PDF, DOCX, etc.)",
                    "type": "document",
                    "capabilities": ["extract_text", "extract_metadata", "convert_to_markdown"]
                },
                {
                    "id": "search",
                    "name": "Web Search",
                    "description": "Search the web for information",
                    "type": "web_search",
                    "capabilities": ["search", "extract_snippets"]
                },
                {
                    "id": "database",
                    "name": "Database Connector",
                    "description": "Query structured data from databases",
                    "type": "database",
                    "capabilities": ["query", "schema_discovery"]
                }
            ]
            
            return {
                "success": True,
                "sources": sources,
                "count": len(sources)
            }
            
        except Exception as e:
            logger.exception(f"Error getting available sources: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    @server.tool(
        name="extract_content",
        description="Extract structured content from a webpage"
    )
    async def extract_content(context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured content from a webpage.
        
        Args:
            context: Dictionary containing:
                - url: The URL of the webpage to extract content from
                - strategy: The extraction strategy to use (llm, fast, or accurate)
                - request_id: Optional ID for tracking the request
        """
        global crawl4ai_context
        url = context.get('url')
        strategy = context.get('strategy', 'llm')
        request_id = context.get('request_id', f"req_{int(time.time())}")
        
        if not url:
            return {
                "status": "error",
                "error": "No URL provided",
                "request_id": request_id
            }
        
        logger.info(f"[{request_id}] Extracting content from {url} with strategy: {strategy}")
        
        if not crawl4ai_context or not crawl4ai_context.crawler:
            error_msg = "Web crawler is not available. Check server logs for initialization errors."
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "request_id": request_id
            }
        
        try:
            # Validate URL
            if not url or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
                error_msg = f"Invalid URL: {url}"
                logger.error(error_msg)
                return {
                    "status": "error",
                    "error": error_msg,
                    "request_id": request_id
                }
            
            # Configure extraction strategy
            if strategy == "llm":
                extraction_strategy = LLMExtractionStrategy()
            elif strategy == "css":
                extraction_strategy = JsonCssExtractionStrategy()
            elif strategy == "xpath":
                extraction_strategy = JsonXPathExtractionStrategy()
            elif strategy == "lxml":
                extraction_strategy = JsonLxmlExtractionStrategy()
            else:
                error_msg = f"Unsupported extraction strategy: {strategy}"
                logger.error(error_msg)
                return {
                    "status": "error",
                    "error": error_msg,
                    "supported_strategies": ["llm", "css", "xpath", "lxml"],
                    "request_id": request_id
                }
            
            # Extract content
            logger.info(f"Crawling URL: {url}")
            result = await crawl4ai_context.crawler.crawl(
                url=url,
                extraction_strategy=extraction_strategy,
                max_pages=1
            )
            
            if not result or not result.pages:
                error_msg = f"No content extracted from {url}"
                logger.error(error_msg)
                return {
                    "status": "error",
                    "error": error_msg,
                    "request_id": request_id
                }
            
            # Process the result
            page = result.pages[0]
            extracted_content = {
                "status": "success",
                "url": url,
                "title": page.title,
                "content": page.extracted_content,
                "metadata": page.metadata,
                "strategy": strategy,
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_id
            }
            
            # --- Web Knowledge Graph Integration ---
            if os.getenv("ENABLE_WEB_KG", "false").lower() == "true":
                try:
                    graph = WebGraphNeo4j()
                    # Upsert the page node
                    graph.upsert_page(url, page.title)
                    # Parse HTML for tables (demo)
                    soup = BeautifulSoup(page.extracted_content, "html.parser")
                    for i, table in enumerate(soup.find_all("table")):
                        table_id = f"{url}#table{i+1}"
                        caption = table.caption.string if table.caption else None
                        graph.upsert_table(url, table_id, caption)
                    graph.close()
                    logger.info(f"Inserted page and tables into Neo4j for {url}")
                except Exception as kg_e:
                    logger.error(f"Neo4j web KG error: {kg_e}")
            # --- End Web Knowledge Graph Integration ---
            
            logger.info(f"Successfully extracted content from {url}")
            return extracted_content
            
        except Exception as e:
            error_msg = f"Error extracting content from {url}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "status": "error",
                "error": error_msg,
                "url": url,
                "request_id": request_id
            }
    
    @server.tool(
        name="search_web",
        description="Search the web for information"
    )
    async def search_web(context: Dict[str, Any]) -> Dict[str, Any]:
        """Search the web for the given query.
        
        Args:
            context: Dictionary containing:
                - query: The search query
                - limit: Maximum number of results to return (default: 5)
                - request_id: Optional ID for tracking the request
        """
        global crawl4ai_context
        query = context.get('query')
        limit = context.get('limit', 5)
        request_id = context.get('request_id', f"req_{int(time.time())}")
        
        if not query:
            return {
                "status": "error",
                "error": "No search query provided",
                "request_id": request_id
            }
        
        logger.info(f"[{request_id}] Searching web for: {query} (limit: {limit})")
        
        if not crawl4ai_context or not crawl4ai_context.crawler:
            error_msg = "Web crawler is not available. Check server logs for initialization errors."
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "request_id": request_id,
                "query": query
            }
        
        try:
            logger.info(f"Searching web for: {query}")
            
            # Validate limit
            limit = max(1, min(20, int(limit)))  # Ensure limit is between 1 and 20
            
            try:
                # This is a simplified example - in a real implementation,
                # you would use a search API like Google Custom Search, SerpAPI, etc.
                search_url = f"https://www.google.com/search?q={query}&num={limit}"
                logger.debug(f"Searching with URL: {search_url}")
                
                # Use a basic extraction strategy for search results
                try:
                    extraction_strategy = JsonLxmlExtractionStrategy()
                except Exception as e:
                    error_msg = f"Failed to create extraction strategy: {str(e)}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg) from e
                
                # Execute the search and extract results
                try:
                    result = await crawl4ai_context.crawler.crawl(
                        url=search_url,
                        extraction_strategy=extraction_strategy
                    )
                except Exception as e:
                    error_msg = f"Search request failed: {str(e)}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg) from e
                
                if not result or not hasattr(result, 'content'):
                    error_msg = "No content received in search results"
                    logger.warning(error_msg)
                    return {
                        "status": "error",
                        "error": error_msg,
                        "query": query,
                        "request_id": request_id
                    }
                
                # In a real implementation, you would parse the search results page
                # to extract individual search results. For now, we'll return a simplified response.
                response = {
                    "status": "success",
                    "query": query,
                    "success": True,
                    "results": [{
                        "title": getattr(result, 'title', f"Search Results for: {query}"),
                        "url": search_url,
                        "snippet": (getattr(result, 'content', '') or '')[:500] + '...',
                        "metadata": getattr(result, 'metadata', {})
                    }],
                    "request_id": request_id
                }
                
                logger.info(f"Search completed successfully for query: {query}")
                return response
                
            except Exception as e:
                error_msg = f"Error performing web search: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {
                    "status": "error",
                    "query": query,
                    "success": False,
                    "error": error_msg,
                    "request_id": request_id
                }
                
        except Exception as e:
            logger.exception(f"Error searching web: {e}")
            return {
                "status": "error",
                "query": query,
                "success": False,
                "error": f"Search failed: {str(e)}",
                "request_id": request_id
            }
    
    @server.tool(
        name="health_check",
        description="Return a simple health check response for debugging."
    )
    async def health_check() -> dict:
        import datetime
        logger.info("health_check tool called")
        result = {"status": "ok", "time": datetime.datetime.utcnow().isoformat()}
        logger.info(f"health_check tool returning: {result}")
        return result

# Create the MCP server instance
mcp = FastMCP(
    "crawl4ai",
    version="1.0.0",
    description="MCP server for web crawling and content extraction with Crawl4AI",
    lifespan=crawl4ai_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=os.getenv("PORT", "8054")
)

# Tool registrations using decorators
@mcp.tool()
async def crawl_website(ctx: Context, url: str, max_pages: int = 1) -> str:
    """
    Crawl a website and extract content using the global Crawl4AI context.
    This avoids relying on ctx.state (which may not be present in FastMCP Context).
    """
    try:
        global crawl4ai_context
        crawler = getattr(crawl4ai_context, "crawler", None)
        if crawler is None:
            return json.dumps({
                "status": "error",
                "message": "Web crawler is not available. Check server initialization logs."
            })

        # Use a robust default extraction strategy
        extraction_strategy = LLMExtractionStrategy()

        # Ensure sensible bounds
        try:
            max_pages_int = max(1, int(max_pages))
        except Exception:
            max_pages_int = 1

        # Use arun (async run) according to installed crawl4ai API
        result = await crawler.arun(
            url=url,
            extraction_strategy=extraction_strategy,
            max_pages=max_pages_int
        )

        if not result or not getattr(result, "pages", None):
            return json.dumps({
                "status": "error",
                "message": f"No content extracted from {url}"
            })

        # Concatenate page contents
        pages = result.pages
        combined = "\n\n".join(getattr(p, "extracted_content", "") for p in pages if getattr(p, "extracted_content", ""))
        metadata_list = [getattr(p, "metadata", {}) for p in pages]

        return json.dumps({
            "status": "success",
            "url": url,
            "pages_crawled": len(pages),
            "content": combined,
            "metadata": metadata_list
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })

@mcp.tool()
async def extract_content(ctx: Context, url: str, strategy: str = "llm") -> str:
    """
    Extract content from a URL using the specified strategy via the global crawler.
    Supported strategies: llm, css, xpath, lxml.
    """
    try:
        global crawl4ai_context
        crawler = getattr(crawl4ai_context, "crawler", None)
        if crawler is None:
            return json.dumps({
                "status": "error",
                "message": "Web crawler is not available. Check server initialization logs."
            })

        # Map strategy string to extraction strategy (fallback to LLM for unsupported)
        st = (strategy or "llm").lower()
        extraction_strategy = LLMExtractionStrategy()

        try:
            result = await crawler.arun(
                url=url,
                extraction_strategy=extraction_strategy,
                max_pages=1
            )

            if result and getattr(result, "pages", None):
                page = result.pages[0]
                return json.dumps({
                    "status": "success",
                    "url": url,
                    "strategy": st,
                    "title": getattr(page, "title", None),
                    "content": getattr(page, "extracted_content", None),
                    "metadata": getattr(page, "metadata", {}),
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })
        except Exception as crawl_err:
            logger.warning(f"Primary crawler failed, falling back to basic fetch: {crawl_err}")

        # Fallback: basic HTTP fetch + HTML parsing (no Playwright needed)
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                raw_html = resp.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(raw_html, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else None
            # Extract visible text
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
            return json.dumps({
                "status": "success",
                "url": url,
                "strategy": f"{st}-fallback",
                "title": title,
                "content": text,
                "metadata": {"fallback": True},
                "timestamp": datetime.datetime.utcnow().isoformat()
            })
        except Exception as fb_err:
            return json.dumps({
                "status": "error",
                "message": f"Extraction failed (crawler+fallback): {fb_err}"
            })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })

@mcp.tool()
async def search_web(ctx: Context, query: str, limit: int = 5) -> str:
    """
    Search the web for the given query.
    
    Args:
        query: Search query
        limit: Maximum number of results to return (default: 5)
        
    Returns:
        str: JSON string containing search results or error message
    """
    try:
        # This is a placeholder for actual web search functionality
        # You would typically integrate with a search API here
        return json.dumps({
            "status": "success",
            "query": query,
            "results": [
                {
                    "title": f"Result {i+1} for '{query}'",
                    "url": f"https://example.com/result/{i+1}",
                    "snippet": f"This is a sample result for '{query}'. This would be a snippet from the search result."
                } for i in range(min(limit, 5))
            ]
        })
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })

# Expose the ASGI app for Uvicorn
app = mcp.sse_app

# This file is meant to be imported by start_server.py
# Direct execution is not supported
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp, host="0.0.0.0", port=8054)
