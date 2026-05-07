import os
import logging
import asyncio
import json
import urllib.request
from urllib.parse import parse_qs, unquote, urlparse
import datetime
from contextlib import asynccontextmanager
from typing import Dict, Callable, Any, List, Optional, Type
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
import time
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from crawl4ai import (
        AsyncWebCrawler,
        CrawlResult,
        BrowserConfig,
        CrawlerRunConfig,
    )
    from crawl4ai.extraction_strategy import (
        ExtractionStrategy,
        LLMExtractionStrategy,
        JsonCssExtractionStrategy,
        JsonXPathExtractionStrategy,
        JsonLxmlExtractionStrategy,
    )
    CRAWL4AI_AVAILABLE = True
except ImportError as e:
    AsyncWebCrawler = None  # type: ignore[misc, assignment]
    CrawlResult = object  # type: ignore[misc, assignment]
    BrowserConfig = None  # type: ignore[misc, assignment]
    CrawlerRunConfig = None  # type: ignore[misc, assignment]
    ExtractionStrategy = object  # type: ignore[misc, assignment]
    LLMExtractionStrategy = None  # type: ignore[misc, assignment]
    JsonCssExtractionStrategy = None  # type: ignore[misc, assignment]
    JsonXPathExtractionStrategy = None  # type: ignore[misc, assignment]
    JsonLxmlExtractionStrategy = None  # type: ignore[misc, assignment]
    CRAWL4AI_AVAILABLE = False
    _import_err = e
else:
    _import_err = None

from utils.neo4j_web_graph import WebGraphNeo4j
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crawl4ai_mcp")
logger.info("Starting Crawl4AI MCP server")
if _import_err:
    logger.error("Failed to import Crawl4AI components: %s", _import_err)


def _crawl_result_title(result: CrawlResult) -> Optional[str]:
    md = getattr(result, "metadata", None)
    if isinstance(md, dict):
        for key in ("title", "og:title", "page_title"):
            v = md.get(key)
            if v:
                return str(v)
    html = getattr(result, "html", None) or ""
    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                return soup.title.string.strip()
        except Exception:
            pass
    return None


def _result_to_markdown_text(result: CrawlResult) -> str:
    md = getattr(result, "markdown", None)
    if md is not None:
        raw = getattr(md, "raw_markdown", None)
        if raw:
            return str(raw)
        return str(md)
    return (getattr(result, "cleaned_html", None) or getattr(result, "html", None) or "") or ""


def _extraction_strategy_for_name(name: str):
    st = (name or "llm").lower()
    if st == "css":
        return JsonCssExtractionStrategy()
    if st == "xpath":
        return JsonXPathExtractionStrategy()
    if st == "lxml":
        return JsonLxmlExtractionStrategy()
    return LLMExtractionStrategy()

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
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
            browser_config = BrowserConfig(
                headless=True,
                verbose=False,
                user_agent=user_agent,
                headers=headers,
                ignore_https_errors=False,
            )
            logger.info("Creating AsyncWebCrawler instance...")
            self.crawler = AsyncWebCrawler(config=browser_config)
            logger.info("AsyncWebCrawler initialized successfully")
        except Exception as e:
            logger.error(
                "Error initializing AsyncWebCrawler with full configuration: %s", str(e)
            )
            logger.info("Attempting to initialize with minimal configuration...")
            try:
                self.crawler = AsyncWebCrawler(
                    config=BrowserConfig(headless=True, verbose=False)
                )
                logger.warning(
                    "Fallback AsyncWebCrawler initialized with minimal configuration."
                )
            except Exception as e2:
                error_msg = f"Failed to initialize fallback AsyncWebCrawler: {str(e2)}"
                logger.error(error_msg)
                self.crawler = None
                raise RuntimeError(
                    "Failed to initialize web crawler. Please check logs for details."
                ) from e2

# Create a global context instance
crawl4ai_context = None

@asynccontextmanager
async def crawl4ai_lifespan(server: FastMCP):
    global crawl4ai_context
    
    logger.info("Initializing Crawl4AI MCP server...")
    
    if not CRAWL4AI_AVAILABLE:
        logger.error("Crawl4AI components not available. Check if crawl4ai is properly installed.")
        raise ImportError("Crawl4AI components not available")
    
    try:
        # Initialize the global context
        crawl4ai_context = Crawl4AIContext()
        logger.info("Crawl4AI context initialized")
        
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


def _removed_register_tools_placeholder(server: FastMCP):
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
            
            # Extract content (Crawl4AI 0.8+: arun + CrawlerRunConfig)
            logger.info(f"Crawling URL: {url}")
            run_cfg = CrawlerRunConfig(extraction_strategy=extraction_strategy)
            result = await crawl4ai_context.crawler.arun(url=url, config=run_cfg)

            if not result or not getattr(result, "success", False):
                error_msg = f"No content extracted from {url}"
                logger.error(error_msg)
                return {
                    "status": "error",
                    "error": error_msg,
                    "request_id": request_id
                }

            title = _crawl_result_title(result)
            body = result.extracted_content or _result_to_markdown_text(result)
            extracted_content = {
                "status": "success",
                "url": url,
                "title": title,
                "content": body,
                "metadata": result.metadata,
                "strategy": strategy,
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_id
            }
            
            # --- Web Knowledge Graph Integration ---
            if os.getenv("ENABLE_WEB_KG", "false").lower() == "true":
                try:
                    graph = WebGraphNeo4j()
                    # Upsert the page node
                    graph.upsert_page(url, title)
                    # Parse HTML for tables (demo)
                    soup_html = result.html or body or ""
                    soup = BeautifulSoup(soup_html, "html.parser")
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
                    run_cfg = CrawlerRunConfig(extraction_strategy=extraction_strategy)
                    result = await crawl4ai_context.crawler.arun(
                        url=search_url, config=run_cfg
                    )
                except Exception as e:
                    error_msg = f"Search request failed: {str(e)}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg) from e

                snippet = (
                    (result.extracted_content or _result_to_markdown_text(result) or "")
                    if result
                    else ""
                )
                if not result or not getattr(result, "success", False) or not snippet:
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
                        "title": _crawl_result_title(result) or f"Search Results for: {query}",
                        "url": search_url,
                        "snippet": snippet[:500] + ('...' if len(snippet) > 500 else ''),
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
    instructions="MCP server for web crawling and content extraction with Crawl4AI",
    lifespan=crawl4ai_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8054")),
)


def _normalize_search_result_url(raw: str) -> str:
    """Turn DDG redirect / protocol-relative links into real https URLs."""
    if not raw:
        return raw
    u = raw.strip()
    if u.startswith("//"):
        u = "https:" + u
    if "uddg=" in u:
        try:
            q = urlparse(u).query.replace("&amp;", "&")
            inner = (parse_qs(q).get("uddg") or [None])[0]
            if inner:
                return unquote(inner)
        except Exception:
            pass
    return u


def duckduckgo_web_search_sync(query: str, limit: int) -> Dict[str, Any]:
    """Real web search via DuckDuckGo. Runs in a thread from async search_web."""
    limit = max(1, min(20, int(limit)))
    q = (query or "").strip()
    if not q:
        return {"status": "error", "error": "No search query provided", "results": []}

    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(q, max_results=limit):
                href = (r.get("href") or r.get("url") or "").strip()
                title = (r.get("title") or "").strip()
                body = (r.get("body") or r.get("snippet") or "").strip()
                href = _normalize_search_result_url(href)
                if href:
                    results.append({"title": title, "url": href, "snippet": body})
        if results:
            return {
                "status": "success",
                "query": q,
                "results": results,
                "source": "duckduckgo",
            }
    except Exception as e:
        logger.warning("duckduckgo_search (DDGS) failed: %s", e)

    try:
        import re as _re

        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; crawl4ai-rag-mcp/2.0; +https://github.com)"
        }
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": q},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        blocks = _re.findall(
            r'class="result__title".*?href="([^"]+)"[^>]*>([^<]+).*?class="result__snippet"[^>]*>([^<]+)',
            resp.text,
            _re.DOTALL,
        )
        results = []
        for url, title, snippet in blocks[:limit]:
            url, title, snippet = url.strip(), title.strip(), snippet.strip()
            url = _normalize_search_result_url(url)
            if url:
                results.append({"title": title, "url": url, "snippet": snippet})
        if results:
            return {
                "status": "success",
                "query": q,
                "results": results,
                "source": "duckduckgo_html",
            }
    except Exception as e:
        logger.warning("DuckDuckGo HTML fallback failed: %s", e)

    return {
        "status": "error",
        "query": q,
        "error": "Search returned no results. Check container network egress and dependencies (duckduckgo-search, requests).",
        "results": [],
    }


# Tool registrations using decorators
@mcp.tool()
async def get_available_sources() -> Dict[str, Any]:
    """List available data sources (capabilities)."""
    try:
        logger.info("Getting available sources...")
        sources = [
            {
                "id": "web",
                "name": "Web Crawler",
                "description": "Crawl and extract content from web pages",
                "type": "web",
                "capabilities": ["crawl", "extract_text", "extract_metadata"],
            },
            {
                "id": "document",
                "name": "Document Parser",
                "description": "Extract content from documents (PDF, DOCX, etc.)",
                "type": "document",
                "capabilities": ["extract_text", "extract_metadata", "convert_to_markdown"],
            },
            {
                "id": "search",
                "name": "Web Search",
                "description": "Search the web via DuckDuckGo (search_web)",
                "type": "web_search",
                "capabilities": ["search", "extract_snippets"],
            },
            {
                "id": "database",
                "name": "Database Connector",
                "description": "Query structured data from databases",
                "type": "database",
                "capabilities": ["query", "schema_discovery"],
            },
        ]
        return {"success": True, "sources": sources, "count": len(sources)}
    except Exception as e:
        logger.exception("Error getting available sources: %s", e)
        return {"success": False, "error": str(e)}


@mcp.tool()
async def health_check() -> Dict[str, Any]:
    """Lightweight tool health check."""
    logger.info("health_check tool called")
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat()}


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

        # Use arun (async run) - no LLM strategy needed, use markdown extraction
        result = await crawler.arun(url=url)

        if not result or not getattr(result, "success", False):
            err = getattr(result, "error_message", "Unknown error")
            return json.dumps({
                "status": "error",
                "message": f"Crawl failed for {url}: {err}"
            })

        # Extract markdown content (primary) or fall back to cleaned_html / html
        combined = _result_to_markdown_text(result)
        if not combined:
            return json.dumps({
                "status": "error",
                "message": f"No content extracted from {url}"
            })

        metadata_list = [getattr(result, "metadata", {})]

        return json.dumps({
            "status": "success",
            "url": url,
            "pages_crawled": 1,
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
        extraction_strategy = _extraction_strategy_for_name(st)

        try:
            run_cfg = CrawlerRunConfig(extraction_strategy=extraction_strategy)
            result = await crawler.arun(url=url, config=run_cfg)

            if result and getattr(result, "success", False):
                body = result.extracted_content or _result_to_markdown_text(result)
                return json.dumps({
                    "status": "success",
                    "url": url,
                    "strategy": st,
                    "title": _crawl_result_title(result),
                    "content": body,
                    "metadata": getattr(result, "metadata", {}) or {},
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
async def search_web(query: str, limit: int = 5) -> str:
    """
    Search the web for the given query.

    Args:
        query: Search query
        limit: Maximum number of results to return (default: 5)

    Returns:
        str: JSON string containing search results or error message
    """
    payload = await asyncio.to_thread(duckduckgo_web_search_sync, query, limit)
    return json.dumps(payload, indent=2)

