"""Optional live checks against a running MCP SSE server.

Run the server first, then::

    MCP_LIVE_TEST=1 MCP_LIVE_PORT=18054 pytest tests/test_stack_live.py -v

Requires dev deps: pip install pytest pytest-asyncio
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

pytest.importorskip("pytest_asyncio")

_requires_live = pytest.mark.skipif(
    os.environ.get("MCP_LIVE_TEST") != "1",
    reason="Set MCP_LIVE_TEST=1 with server running (see module docstring)",
)


def _live_base() -> str:
    port = os.environ.get("MCP_LIVE_PORT", "18054")
    return f"http://127.0.0.1:{port}"


@_requires_live
@pytest.mark.asyncio
async def test_health_http():
    import httpx

    base = _live_base()
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{base}/health", timeout=10)
        r.raise_for_status()
        data = r.json()
        assert data.get("status") == "ok"


@_requires_live
@pytest.mark.asyncio
async def test_mcp_tools_roundtrip():
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client

    url = f"{_live_base()}/sse"
    async with sse_client(url, timeout=30, sse_read_timeout=120) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert "health_check" in names
            assert "search_web" in names
            assert "crawl_website" in names

            res = await session.call_tool("health_check", {})
            assert not res.isError
            payload: dict[str, Any] = json.loads(res.content[0].text)
            assert payload.get("status") == "ok"

            res2 = await session.call_tool("search_web", {"query": "python", "limit": 1})
            assert not res2.isError
            s = json.loads(res2.content[0].text)
            assert s.get("status") == "success"
            assert len(s.get("results") or []) >= 1


@_requires_live
@pytest.mark.asyncio
async def test_crawl_example_com():
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client

    url = f"{_live_base()}/sse"
    async with sse_client(url, timeout=60, sse_read_timeout=180) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "crawl_website",
                {"url": "https://example.com", "max_pages": 1},
            )
            assert not res.isError
            data = json.loads(res.content[0].text)
            assert data.get("status") == "success"
            assert (data.get("content") or "").strip()
