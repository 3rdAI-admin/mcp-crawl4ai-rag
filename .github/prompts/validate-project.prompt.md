---
agent: agent
description: Validate Crawl4AI RAG MCP Server (project-specific)
---

# Validate Project (Crawl4AI RAG MCP Server)

> **Generated for this codebase:** Crawl4AI RAG MCP Server — a Python MCP server providing web crawling and RAG capabilities via SSE transport. Docker-based with PostgreSQL, Neo4j, PostgREST. Python 3.12+, uv, FastMCP, uvicorn. Port 8054.
>
> **Setup:** Run `uv sync --all-extras` once to install dev tools (ruff, mypy, pytest). Ensure Docker Desktop is running for E2E tests.

**Execute ONLY the validation in this file.** Do not run another project's validation. Use **`/validate-project`** (not `/validate`) to avoid conflicts with team/global commands.

## Phase 1: Python Linting

Run ruff linter on source and knowledge graph modules:

```bash
uv run ruff check src/ knowledge_graphs/
```

## Phase 2: Python Type Checking

Run mypy on core source (warnings acceptable, ensure no critical errors):

```bash
uv run mypy src/crawl4ai_mcp.py src/utils.py run_mcp_server.py --ignore-missing-imports
```

## Phase 3: Python Style Checking

Verify Python code formatting with ruff:

```bash
uv run ruff format --check src/ knowledge_graphs/ run_mcp_server.py
```

## Phase 4: Python Import Verification

Verify core application imports resolve correctly:

```bash
python3 -c "from src.crawl4ai_mcp import mcp; print('OK: src.crawl4ai_mcp imports')"
```

```bash
python3 -c "from src.utils.neo4j_web_graph import WebGraphNeo4j; print('OK: neo4j_web_graph imports')"
```

## Phase 5: Shell Script Validation

Verify shell scripts have correct syntax. Try shellcheck first; fall back to bash -n.

### With shellcheck (preferred)

```bash
shellcheck startup.sh run_container.sh
```

### Without shellcheck (fallback)

```bash
bash -n startup.sh
```

```bash
bash -n run_container.sh
```

## Phase 6: Docker & Configuration Validation

### Dockerfile syntax

```bash
docker build --check -f Dockerfile . 2>&1 || echo "WARN: --check not supported, skipping Dockerfile lint"
```

### docker-compose.yml validity

```bash
docker compose -f docker-compose.yml config --quiet
```

### Environment file

Verify `.env.example` exists and documents required variables. Use file tools to check `.env.example` contains:
- OPENAI_API_KEY
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_DB
- NEO4J_USER
- NEO4J_PASSWORD

### SQL schema

Verify `crawled_pages.sql` exists and is non-empty.

## Phase 7: Project Structure

Use file tools (Glob, Read, LS) to verify — do NOT use compound shell commands with `&&` / `||` / `for`.

### Core Files

Verify these exist and are non-empty:
- README.md
- LICENSE
- pyproject.toml
- requirements.txt
- Dockerfile
- docker-compose.yml
- crawled_pages.sql
- .cursorrules
- .env.example
- .gitignore
- .dockerignore

### Source Code

Verify these exist:
- src/crawl4ai_mcp.py (main MCP server)
- src/utils.py (helper functions)
- src/utils/neo4j_web_graph.py
- run_mcp_server.py (Docker entry point)

### Knowledge Graphs

Verify these exist:
- knowledge_graphs/parse_repo_into_neo4j.py
- knowledge_graphs/ai_script_analyzer.py
- knowledge_graphs/knowledge_graph_validator.py
- knowledge_graphs/hallucination_reporter.py
- knowledge_graphs/query_knowledge_graph.py

### Scripts

Verify these directories exist and contain .py files:
- scripts/debug/
- scripts/clients/
- scripts/runners/

### Documentation

Verify these exist:
- docs/SETUP.md
- docs/MCP_CONNECTION_GUIDE.md
- docs/integrate_archon_crawl4ai.md

### Shell Scripts Executable

Verify these are executable:
- startup.sh
- run_container.sh

## Phase 8: Documentation Cross-References

### README Sections

Use Grep to verify README.md mentions these key items:
- crawl_website
- extract_content
- search_web
- get_available_sources
- docker-compose
- 8054
- docs/SETUP.md

### Port Consistency

Verify no stale port references remain:

```bash
grep -rn "localhost:8051" src/ knowledge_graphs/ run_mcp_server.py Dockerfile docker-compose.yml docs/ || echo "OK: No stale 8051 references"
```

```bash
grep -rn "localhost:8052" src/ knowledge_graphs/ run_mcp_server.py Dockerfile docker-compose.yml docs/ || echo "OK: No stale 8052 references"
```

## Phase 9: E2E Workflow Validation

Test complete user workflows from documentation. **Requires Docker Desktop running.**

### Workflow 1: Docker Build

Verify the Docker image builds successfully:

```bash
docker compose build mcp-crawl4ai-rag
```

### Workflow 2: Container Startup

Start all services and wait for health:

```bash
docker compose up -d
```

```bash
timeout 60 bash -c 'until curl -sf http://localhost:8054/health; do sleep 3; done' && echo "OK: Server healthy" || echo "FAIL: Server did not become healthy in 60s"
```

### Workflow 3: Health Check Endpoint

```bash
curl -sf http://localhost:8054/health
```

### Workflow 4: SSE Endpoint Availability

Verify the SSE endpoint responds (connect and read first event):

```bash
timeout 5 curl -sf -N -H "Accept: text/event-stream" http://localhost:8054/sse 2>&1 | head -5 || echo "OK: SSE endpoint responded"
```

### Workflow 5: MCP Tool Discovery

Verify MCP tools are discoverable via Python SDK:

```bash
python3 -c "
import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def check():
    async with sse_client('http://localhost:8054/sse') as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = [t.name for t in tools.tools]
            assert 'crawl_website' in names, f'Missing crawl_website in {names}'
            assert 'get_available_sources' in names, f'Missing get_available_sources in {names}'
            assert 'search_web' in names, f'Missing search_web in {names}'
            print(f'OK: {len(names)} tools available: {names}')

asyncio.run(check())
"
```

### Workflow 6: Database Connectivity

Verify PostgreSQL is accessible:

```bash
docker exec postgres pg_isready -U postgres -d agentic_rag
```

Verify Neo4j is accessible:

```bash
docker exec neo4j cypher-shell -u neo4j -p crawl4aidb "RETURN 1" 2>&1 || echo "WARN: Neo4j not responding"
```

### Cleanup (optional)

If you started containers just for validation:

```bash
docker compose down
```

## Summary

Report results for each phase:
- **P1 (Python Lint):** OK/FAIL
- **P2 (Python Types):** OK/WARN/FAIL
- **P3 (Python Style):** OK/FAIL
- **P4 (Import Check):** OK/FAIL
- **P5 (Shell):** OK/WARN/FAIL
- **P6 (Docker/Config):** OK/FAIL
- **P7 (Structure):** OK/FAIL
- **P8 (Docs):** OK/FAIL
- **P9 (E2E):** OK/FAIL

Count total errors (E) and warnings (W). Pass = 0 errors. Warn = 0 errors but warnings present.

## Journal Entry (Required)

After validation completes:

1. **Ensure journal/ exists:**

```bash
mkdir -p journal
```

2. **Append one line to `journal/YYYY-MM-DD.md`** (today's date, ISO format):

   ```
   HH:MM | Pass/Fail | E:N W:M | P1:OK P2:OK ... P9:OK | optional note
   ```

3. **Update `journal/README.md`** with one line per date for that day's latest outcome, e.g.:

   ```
   YYYY-MM-DD: N runs, last Pass (E:0 W:1)
   ```

**Example entry:**

```
13:30 | Pass | E:0 W:1 | P1:OK P2:WARN P3:OK P4:OK P5:OK P6:OK P7:OK P8:OK P9:OK | Clean validation
```
