# Connecting Your App to the Crawl4AI RAG MCP Server

This guide walks you through connecting any MCP-compatible application to the Crawl4AI RAG MCP server.

## Prerequisites

- The Crawl4AI RAG MCP server must be running (see [Starting the Server](#1-start-the-server) below)
- Your application must support the [Model Context Protocol (MCP)](https://modelcontextprotocol.io)

---

## 1. Start the Server

Make sure the MCP server is running before connecting your app.

### Option A: Docker (Recommended)

```bash
cd /path/to/mcp_crawl4ai_rag
./startup.sh
```

Or manually:

```bash
docker-compose up -d
```

### Option B: Python (without Docker)

```bash
cd /path/to/mcp_crawl4ai_rag
uv run src/crawl4ai_mcp.py
```

### Verify the Server is Running

```bash
curl http://localhost:8054/health
```

You should get a JSON response confirming the server is healthy.

---

## 2. Connection Details

| Property       | Value                            |
|----------------|----------------------------------|
| **Transport**  | SSE (Server-Sent Events)         |
| **Base URL**   | `http://localhost:8054`          |
| **SSE Endpoint** | `http://localhost:8054/sse`    |
| **Health Check** | `http://localhost:8054/health` |

> **Running your app in a separate Docker container?**
> Replace `localhost` with `host.docker.internal` (e.g., `http://host.docker.internal:8054/sse`).

---

## 3. MCP Client Configuration

Add the following to your app's MCP configuration file. The exact file location depends on your client.

### SSE Transport (most common)

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "transport": "sse",
      "url": "http://localhost:8054/sse"
    }
  }
}
```

### Code Companion

Add an entry to **`mcpClients`** in **`.cc-config.json`** (see **`docs/CC-CONFIG.md`** in the Code Companion repo). Use **`transport`: `"sse"`** and **`url`**: **`http://127.0.0.1:8054/sse`** (include `/sse`; prefer `127.0.0.1` over `localhost`). See **`docs/CRAWL4AI-RAG-MCP.md`** in Code Companion for compose prerequisites and troubleshooting.

### Client-Specific Notes

**Windsurf** — use `serverUrl` instead of `url`:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "transport": "sse",
      "serverUrl": "http://localhost:8054/sse"
    }
  }
}
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "transport": "sse",
      "url": "http://localhost:8054/sse"
    }
  }
}
```

**Claude Code** — run from terminal:

```bash
claude mcp add-json crawl4ai-rag '{"type":"http","url":"http://localhost:8054/sse"}' --scope user
```

**n8n / Docker-based clients** — use the Docker internal hostname:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "transport": "sse",
      "url": "http://host.docker.internal:8054/sse"
    }
  }
}
```

### Stdio Transport (alternative)

If your client doesn't support SSE, use stdio transport:

```json
{
  "mcpServers": {
    "crawl4ai-rag": {
      "command": "python",
      "args": ["/path/to/mcp_crawl4ai_rag/src/crawl4ai_mcp.py"],
      "env": {
        "TRANSPORT": "stdio",
        "OPENAI_API_KEY": "your_openai_api_key",
        "SUPABASE_URL": "your_supabase_url",
        "SUPABASE_SERVICE_KEY": "your_supabase_service_key"
      }
    }
  }
}
```

---

## 4. Available Tools

Once connected, your app will have access to these tools:

### Core Tools (always available)

| Tool                  | Description                                                              |
|-----------------------|--------------------------------------------------------------------------|
| `crawl_website`       | Crawl websites and store content in the vector database                 |
| `extract_content`     | Extract content from web pages                                          |
| `search_web`          | Search the web for relevant content                                     |
| `get_available_sources`| List all available sources (domains) in the database                   |
| `health_check`        | Basic server health check for debugging                                 |

### Conditional Tools

| Tool                         | Requires                      | Description                                      |
|------------------------------|-------------------------------|--------------------------------------------------|
| `search_code_examples`       | `USE_AGENTIC_RAG=true`       | Search for code examples from crawled docs       |
| `parse_github_repository`    | `USE_KNOWLEDGE_GRAPH=true`   | Parse a GitHub repo into a Neo4j knowledge graph |
| `check_ai_script_hallucinations` | `USE_KNOWLEDGE_GRAPH=true` | Validate AI-generated code against the graph   |
| `query_knowledge_graph`      | `USE_KNOWLEDGE_GRAPH=true`   | Explore the Neo4j knowledge graph               |

---

## 5. Quick Test with Python

You can verify the connection programmatically:

```python
import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.types import Implementation

async def test_connection():
    async with sse_client("http://localhost:8054/sse") as (read, write):
        async with ClientSession(read, write, Implementation("my-app", "1.0.0")) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:")
            for tool in tools:
                print(f"  - {tool.name}")

            # Test a simple query
            result = await session.call_tool("get_available_sources", {})
            print(f"\nSources: {result}")

asyncio.run(test_connection())
```

Install the required package first:

```bash
pip install mcp httpx-sse
```

---

## 6. Example Workflows

### Crawl a website

```python
# Crawl a documentation site
await session.call_tool("crawl_website", {
    "url": "https://docs.example.com"
})
```

### Extract content from a page

```python
result = await session.call_tool("extract_content", {
    "url": "https://example.com/getting-started"
})
```

### Search the web

```python
result = await session.call_tool("search_web", {
    "query": "How do I authenticate with the API?"
})
```

---

## Troubleshooting

| Issue                          | Solution                                                                 |
|--------------------------------|--------------------------------------------------------------------------|
| Connection refused             | Ensure the server is running: `docker-compose ps`                       |
| Port already in use            | Check for conflicts: `lsof -i :8054`                                    |
| Timeout on first request       | The server needs ~30s to start. Check: `curl http://localhost:8054/health` |
| Tools not appearing            | Verify your MCP config JSON is valid and restart your client            |
| Docker networking issues       | Use `host.docker.internal` instead of `localhost`                       |
| Server logs                    | View with: `docker-compose logs -f mcp-crawl4ai-rag`                   |
