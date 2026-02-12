#!/usr/bin/env python3
"""
MCP client to connect to the MCP Crawl4AI RAG server.
"""
import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from mcp.client.sse import sse_client

class MCPCrawl4AIClient:
    """Client for interacting with the MCP Crawl4AI RAG server."""
    
    def __init__(self, base_url: str = "http://localhost:8054"):
        """Initialize the MCP client.
        
        Args:
            base_url: Base URL of the MCP server (e.g., "http://localhost:8054")
        """
        self.base_url = base_url.rstrip('/')
        self.sse_url = f"{self.base_url}/sse"
        self.client = None
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def connect(self):
        """Connect to the MCP server."""
        logger.info(f"Connecting to MCP server at {self.sse_url}")
        
        # Connect to the SSE endpoint
        self.sse = sse_client(
            self.sse_url,
            timeout=30.0
        )
        
        # Store the session and message queue
        self.session, self.message_queue = await self.sse.__aenter__()
        self.post_url = f"{self.base_url}/messages/"
        logger.info(f"Connected to MCP server")
    
    async def close(self):
        """Close the connection to the MCP server."""
        if self.sse:
            logger.info("Disconnecting from MCP server...")
            await self.sse.__aexit__(None, None, None)
            self.sse = None
            self.session = None
            logger.info("Disconnected from MCP server")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from the MCP server."""
        try:
            # Send a list_tools request
            request_id = str(uuid.uuid4())
            
            # Prepare the request message
            request = {
                "type": "list_tools",
                "request_id": request_id
            }
            
            # Send the request via HTTP POST
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.post_url,
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
            
            # Wait for the response from the message queue
            start_time = asyncio.get_event_loop().time()
            timeout = 10.0  # 10 seconds timeout
            
            while True:
                # Check for timeout
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.warning("Timeout waiting for tool list response")
                    return []
                
                # Check for messages in the queue
                try:
                    message = self.message_queue.get_nowait()
                    if message.event == "tool_list" and message.data.get("request_id") == request_id:
                        return message.data.get("tools", [])
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.1)  # Small sleep to prevent busy waiting
                    continue
            
            # If we get here, we didn't receive a response
            logger.warning("No response received for list_tools request")
            return []
            
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server.
        
        Args:
            tool_name: The name of the tool to call
            parameters: A dictionary of parameters to pass to the tool
            
        Returns:
            A dictionary containing the tool's response or an error message
        """
        try:
            # Generate a unique request ID
            request_id = str(uuid.uuid4())
            
            # Prepare the tool call request
            request = {
                "type": "call_tool",
                "request_id": request_id,
                "tool": tool_name,
                "parameters": parameters
            }
            
            # Send the request via HTTP POST
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.post_url,
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
            
            # Wait for the response from the message queue
            start_time = asyncio.get_event_loop().time()
            timeout = 30.0  # 30 seconds timeout for tool calls
            
            while True:
                # Check for timeout
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.warning(f"Timeout waiting for tool call response: {tool_name}")
                    return {"error": f"Timeout waiting for response from tool: {tool_name}"}
                
                # Check for messages in the queue
                try:
                    message = self.message_queue.get_nowait()
                    if message.event == "tool_result" and message.data.get("request_id") == request_id:
                        return message.data.get("result", {})
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.1)  # Small sleep to prevent busy waiting
                    continue
            
            # If we get here, we didn't receive a response
            logger.warning(f"No response received for tool call: {tool_name}")
            return {"error": f"No response received for tool call: {tool_name}"}
            
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def crawl_website(self, url: str, max_pages: int = 1, extract_metadata: bool = True) -> Dict[str, Any]:
        """Crawl a website using the crawl_website tool.
        
        Args:
            url: URL of the website to crawl
            max_pages: Maximum number of pages to crawl (default: 1)
            extract_metadata: Whether to extract metadata (default: True)
            
        Returns:
            Dictionary with crawl results
        """
        return await self.call_tool(
            "crawl_website",
            url=url,
            max_pages=max_pages,
            extract_metadata=extract_metadata
        )
    
    async def extract_content(self, url: str, strategy: str = "llm") -> Dict[str, Any]:
        """Extract content from a URL using the extract_content tool.
        
        Args:
            url: URL to extract content from
            strategy: Extraction strategy to use (default: "llm")
            
        Returns:
            Dictionary with extracted content
        """
        return await self.call_tool(
            "extract_content",
            url=url,
            strategy=strategy
        )
    
    async def search_web(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Search the web using the search_web tool.
        
        Args:
            query: Search query
            limit: Maximum number of results to return (default: 5)
            
        Returns:
            Dictionary with search results
        """
        return await self.call_tool(
            "search_web",
            query=query,
            limit=limit
        )

async def main():
    """Main function to test the MCP client."""
    async with MCPCrawl4AIClient() as client:
        # List available tools
        tools = await client.list_tools()
        print("\nAvailable tools:")
        for tool in tools:
            print(f"- {tool['name']}: {tool['description']}")
        
        # Test crawling a website
        print("\nCrawling example.com...")
        try:
            crawl_result = await client.crawl_website("https://example.com", max_pages=1)
            print(f"Crawl result: {json.dumps(crawl_result, indent=2, default=str)}")
        except Exception as e:
            print(f"Error crawling website: {e}")
        
        # Test extracting content
        print("\nExtracting content from example.com...")
        try:
            extract_result = await client.extract_content("https://example.com")
            print(f"Extract result: {json.dumps(extract_result, indent=2, default=str)}")
        except Exception as e:
            print(f"Error extracting content: {e}")
        
        # Test web search
        print("\nSearching the web...")
        try:
            search_result = await client.search_web("MCP Crawl4AI RAG", limit=3)
            print(f"Search result: {json.dumps(search_result, indent=2, default=str)}")
        except Exception as e:
            print(f"Error searching web: {e}")

if __name__ == "__main__":
    asyncio.run(main())
