#!/usr/bin/env python3
"""
Test script to crawl a website using the MCP server with SSE transport.
"""
import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional

import httpx
import sse_starlette.sse as sse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sse_crawl")

class SSEClient:
    def __init__(self, url: str):
        self.url = url
        self.session_id = str(uuid.uuid4())
        self.client = httpx.AsyncClient()
        
    async def __aenter__(self):
        self.stream = self.client.stream(
            "GET",
            self.url,
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
            timeout=30.0,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def read_events(self):
        """Read events from the SSE stream."""
        async with self.stream as response:
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])  # Remove 'data: ' prefix
                        logger.debug(f"Received SSE data: {data}")
                        yield data
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse SSE data: {line}")
                        logger.debug(f"JSON decode error: {e}")

async def crawl_website(url: str, max_pages: int = 1, extract_metadata: bool = True):
    """Crawl a website using the MCP server with SSE transport."""
    sse_url = "http://localhost:8054/sse"
    
    async with SSEClient(sse_url) as client:
        logger.info(f"Connected to SSE stream at {sse_url}")
        
        # Send initialization message
        init_msg = {
            "type": "initialize",
            "data": {
                "protocolVersion": "1.0.0",
                "clientInfo": {
                    "name": "SSE Crawl Tester",
                    "version": "0.1.0"
                }
            }
        }
        
        # Send crawl request
        crawl_msg = {
            "type": "call_tool",
            "data": {
                "tool": "crawl_website",
                "arguments": {
                    "url": url,
                    "max_pages": max_pages,
                    "extract_metadata": extract_metadata
                }
            }
        }
        
        # Process SSE events
        async for event in client.read_events():
            logger.info(f"Received event: {json.dumps(event, indent=2)}")
            
            if event.get("type") == "tool_response":
                result = event.get("data", {})
                logger.info(f"Crawl result: {json.dumps(result, indent=2)}")
                return result
    
    return {"error": "No response received from server"}

async def main():
    # Default URL to crawl
    url = "https://ai.pydantic.dev"
    
    try:
        logger.info(f"Starting crawl of {url}...")
        result = await crawl_website(url)
        
        # Print the result
        print("\nCrawl Results:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Save to file
        with open("sse_crawl_results.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info("Results saved to sse_crawl_results.json")
        
    except Exception as e:
        logger.error(f"Error during crawling: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
