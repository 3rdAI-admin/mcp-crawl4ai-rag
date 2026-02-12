# MCP Crawl4AI Server Connection Guide

## Server Status ✅

**Good news!** Your MCP Crawl4AI server is already running and accessible.

## Connection Details

- **Status**: ✅ Running in Docker
- **Container**: `mcp-crawl4ai-rag`
- **Base URL**: `http://localhost:8054`
- **SSE Endpoint**: `http://localhost:8054/sse`
- **Messages Endpoint**: `http://localhost:8054/messages/`
- **Health Check**: `http://localhost:8054/health`

## Available Tools

Based on the container logs, the following tools are available:

1. **`health_check`** - Basic server health check
2. **`get_available_sources`** - List available data sources 
3. **`extract_content`** - Extract content from web pages
4. **`crawl_website`** - Crawl websites
5. **`search_web`** - Search the web

## How to Connect

### Method 1: Using MCP Python SDK (Recommended)

```python
import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Implementation

async def connect_to_mcp():
    # Client information
    client_info = Implementation(name="my-client", version="1.0.0")
    
    # Connect to the server
    async with sse_client("http://localhost:8054/sse") as (read_stream, write_stream):
        async with ClientSession(
            read_stream, 
            write_stream, 
            client_info=client_info
        ) as session:
            # Initialize session
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")
            
            # Call a tool
            result = await session.call_tool("health_check", {})
            print(f"Health check: {result}")
            
            # Extract content from a webpage
            content = await session.call_tool("extract_content", {
                "url": "https://example.com",
                "strategy": "llm"
            })
            print(f"Extracted content: {content}")

# Run the connection
asyncio.run(connect_to_mcp())
```

### Method 2: Using the Existing Client Classes

You can also use the existing `MCPCrawl4AIClient` class:

```python
import asyncio
from scripts.clients.mcp_client import MCPCrawl4AIClient

async def use_existing_client():
    async with MCPCrawl4AIClient("http://localhost:8054") as client:
        # List tools
        tools = await client.list_tools()
        print(f"Available tools: {tools}")
        
        # Crawl a website
        result = await client.crawl_website("https://example.com")
        print(f"Crawl result: {result}")
        
        # Extract content
        content = await client.extract_content("https://example.com", strategy="llm")
        print(f"Content: {content}")

asyncio.run(use_existing_client())
```

## Testing Connectivity

### Quick Test Scripts

1. **Basic connectivity**: `python tests/simple_connectivity_test.py`
2. **Full MCP test**: `python scripts/clients/demo_mcp_connection.py`
3. **SSE endpoint test**: `curl -H "Accept: text/event-stream" http://localhost:8054/sse`

### Manual Testing

```bash
# Check if server is running
docker ps | grep mcp-crawl4ai-rag

# Check container logs
docker logs mcp-crawl4ai-rag

# Test SSE endpoint
curl -N -H "Accept: text/event-stream" http://localhost:8054/sse
```

## Troubleshooting

### Common Issues

1. **Connection Refused**: 
   - Check if Docker container is running: `docker ps`
   - Restart if needed: `docker-compose restart`

2. **400 Bad Request**:
   - This is normal for the `/messages/` endpoint without proper MCP protocol
   - Use the MCP SDK as shown above

3. **404 Errors**:
   - The server exposes `/sse`, `/messages/`, and `/health` endpoints
   - Other paths will return 404

4. **Tool Call Failures**:
   - Check container logs: `docker logs mcp-crawl4ai-rag`
   - Some tools may have initialization issues (visible in logs)

### Container Management

```bash
# Check status
docker ps

# View logs
docker logs mcp-crawl4ai-rag --tail 50

# Restart container
docker-compose restart

# Stop and start
docker stop mcp-crawl4ai-rag
docker start mcp-crawl4ai-rag
```

## Installation Requirements

To connect to the MCP server, you need:

```bash
pip install mcp httpx-sse
```

## Server Architecture

- **Framework**: FastMCP (MCP server framework)
- **Transport**: Server-Sent Events (SSE)
- **Container**: Docker with uvicorn
- **Crawler**: Crawl4AI for web scraping
- **Port**: 8054 (mapped from internal 8054)

## Next Steps

1. **Install MCP SDK**: `pip install mcp httpx-sse`
2. **Use the Python examples** above to connect
3. **Check the container logs** if you encounter issues
4. **Explore the available tools** using `session.list_tools()`

Your MCP server is working! The main hurdle was understanding that it's running on port 8054 via Docker.
