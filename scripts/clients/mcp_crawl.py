#!/usr/bin/env python3
"""
Patched: Test script to crawl a website using the MCP server with proper session_id and JSON-RPC protocol.
"""
import asyncio
import json
import logging
import uuid
import argparse
import re
import requests
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_crawl")

class MCPClient:
    def __init__(self, base_url: str = "http://localhost:8054"):
        self.base_url = base_url.rstrip('/')
        self.session_id = None
        self.message_id = 1
        self.initialized_sessions = set()

    def get_session_id(self):
        sse_url = f"{self.base_url}/sse"
        logger.info(f"Connecting to SSE endpoint: {sse_url}")
        response = requests.get(sse_url, stream=True)
        for line in response.iter_lines():
            if line:
                decoded = line.decode()
                if decoded.startswith('data:') and 'session_id=' in decoded:
                    match = re.search(r"session_id=([a-f0-9\-]+)", decoded)
                    if match:
                        self.session_id = match.group(1)
                        logger.info(f"Extracted session_id: {self.session_id}")
                        return self.session_id
        raise RuntimeError("Could not extract session_id from SSE stream.")

    async def _send_jsonrpc_request(self, method: str, params: dict) -> dict:
        if not self.session_id:
            self.get_session_id()
        # Always initialize session if not already done
        if self.session_id not in self.initialized_sessions and method == "tools/call":
            # Send initialize handshake
            await self._send_jsonrpc_request(
                "initialize",
                {
                    "protocolVersion": "1.0.0",
                    "clientInfo": {
                        "name": "MCP Crawl Tester",
                        "version": "0.1.0"
                    },
                    "capabilities": {}
                }
            )
            self.initialized_sessions.add(self.session_id)
        url = f"{self.base_url}/messages/?session_id={self.session_id}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params
        }
        self.message_id += 1
        async with httpx.AsyncClient() as client:
            try:
                logger.debug(f"Sending request: {json.dumps(payload, indent=2)}")
                response = await client.post(url, headers=headers, json=payload)
                logger.debug(f"Response status: {response.status_code}")
                if response.status_code == 202:
                    logger.info(f"Request {method} accepted (202). Results will be streamed via SSE at /sse.")
                    return None
                if not response.content:
                    logger.warning(f"Empty response content for {method} (status {response.status_code})")
                    return None
                return response.json()
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise

    async def crawl_website(self, url: str, strategy: str = "llm", max_pages: int = 1, extract_metadata: bool = True) -> dict:
        # Send initialize handshake with required capabilities before crawl
        init_response = await self._send_jsonrpc_request(
            "initialize",
            {
                "protocolVersion": "1.0.0",
                "clientInfo": {
                    "name": "MCP Crawl Tester",
                    "version": "0.1.0"
                },
                "capabilities": {}
            }
        )
        # Optionally log or check init_response here
        # Call the crawl_website tool and return its result
        return await self._send_jsonrpc_request(
            "tools/call",
            {
                "name": "crawl_website",
                "arguments": {
                    "url": url,
                    "strategy": strategy,
                    "max_pages": max_pages,
                    "extract_metadata": extract_metadata
                }
            }
        )

def parse_args():
    parser = argparse.ArgumentParser(description="Crawl4AI MCP Client")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", type=str, help="URL to crawl")
    group.add_argument("--health-check", action="store_true", help="Call health_check tool and exit")
    parser.add_argument("--strategy", type=str, default="llm", help="Extraction strategy")
    parser.add_argument("--max-pages", type=int, default=1, help="Max pages to crawl")
    parser.add_argument("--print", action="store_true", help="Print results")
    parser.add_argument("--base_url", default="http://localhost:8054", help="Base URL for the MCP server")
    args = parser.parse_args()
    return args

async def main():
    args = parse_args()
    client = MCPClient(base_url=args.base_url)
    try:
        logger.info(f"Crawling {args.url} with strategy {args.strategy}...")
        if args.health_check:
            result = await client._send_jsonrpc_request("tools/call", {"name": "health_check", "arguments": {}})
            print("Health check result:", result)
            return
        if not args.url:
            print("No URL provided. Use --url to specify a URL.")
            return
        result = await client.crawl_website(args.url, strategy=args.strategy, max_pages=args.max_pages)
        if isinstance(result, dict) and result.get("status") == "accepted":
            print("\n✅ Crawl request accepted. Results will be streamed via SSE at /sse.")
            print(f"Session ID: {result.get('session_id')}")
            print("Monitor the SSE stream for crawl results.")
        else:
            if args.print:
                print("\nCrawl Results:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
            with open("crawl_results.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info("Results saved to crawl_results.json")
    except Exception as e:
        logger.error(f"Error during crawling: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
