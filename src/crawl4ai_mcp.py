print("=== CRAWL4AI_MCP.PY STARTED ===")
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

# Create the MCP server instance
mcp = FastMCP(
    "crawl4ai",
    version="1.0.0",
    description="MCP server for web crawling and content extraction with Crawl4AI",
    lifespan=crawl4ai_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=os.getenv("PORT", "8054")
)

def _normalize_search_result_url(raw: str) -> str:
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
            return {"status": "success", "query": q, "results": results, "source": "duckduckgo"}
    except Exception as e:
        logger.warning("duckduckgo_search (DDGS) failed: %s", e)
    try:
        import re as _re
        import requests
        headers = {"User-Agent": "Mozilla/5.0 (compatible; crawl4ai-rag-mcp/2.0; +https://github.com)"}
        resp = requests.get("https://html.duckduckgo.com/html/", params={"q": q}, headers=headers, timeout=15)
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
            return {"status": "success", "query": q, "results": results, "source": "duckduckgo_html"}
    except Exception as e:
        logger.warning("DuckDuckGo HTML fallback failed: %s", e)
    return {
        "status": "error",
        "query": q,
        "error": "Search returned no results.",
        "results": [],
    }


@mcp.tool()
async def get_available_sources() -> Dict[str, Any]:
    try:
        logger.info("Getting available sources...")
        sources = [
            {"id": "web", "name": "Web Crawler", "description": "Crawl web pages", "type": "web", "capabilities": ["crawl", "extract_text"]},
            {"id": "search", "name": "Web Search", "description": "DuckDuckGo search (search_web)", "type": "web_search", "capabilities": ["search"]},
        ]
        return {"success": True, "sources": sources, "count": len(sources)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def health_check() -> Dict[str, Any]:
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat()}


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
async def search_web(query: str, limit: int = 5) -> str:
    """Web search via DuckDuckGo."""
    payload = await asyncio.to_thread(duckduckgo_web_search_sync, query, limit)
    return json.dumps(payload, indent=2)

# Expose the ASGI app for Uvicorn
app = mcp.sse_app

# This file is meant to be imported by start_server.py
# Direct execution is not supported
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp, host="0.0.0.0", port=8054)
