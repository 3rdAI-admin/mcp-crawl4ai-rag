import asyncio
import httpx
from httpx_sse import aconnect_sse
import json
import re

async def sse_listener(client, sse_url, session_id_queue, tool_result_queue):
    try:
        async with aconnect_sse(client, "GET", sse_url, timeout=30.0) as event_source:
            async for sse in event_source.aiter_sse():
                print(f"[SSE] event: {sse.event}, data: {sse.data}")
                if sse.event == "endpoint":
                    m = re.search(r"session_id=([a-fA-F0-9]+)", sse.data)
                    if m:
                        await session_id_queue.put(m.group(1))
                elif sse.event == "message":
                    await tool_result_queue.put(sse.data)
                elif sse.event:  # Any non-standard event
                    print(f"[SSE] Non-standard event: {sse.event}")
                    await tool_result_queue.put(None)
                    break
    except Exception as e:
        print(f"[SSE] Exception: {e}")
        await tool_result_queue.put(None)

async def try_sse_variant(base_url, variant):
    sse_url = f"{base_url}{variant}"
    print(f"\n=== Trying SSE endpoint: {sse_url} ===")
    session_id_queue = asyncio.Queue()
    tool_result_queue = asyncio.Queue()
    async with httpx.AsyncClient() as client:
        try:
            listener_task = asyncio.create_task(sse_listener(client, sse_url, session_id_queue, tool_result_queue))
            # Wait for session_id from SSE (with timeout)
            try:
                session_id = await asyncio.wait_for(session_id_queue.get(), timeout=10.0)
            except asyncio.TimeoutError:
                print(f"[ERROR] Timed out waiting for session_id from {sse_url}")
                listener_task.cancel()
                return False
            endpoint_url = f"{base_url}/messages/?session_id={session_id}"
            print(f"Extracted session_id: {session_id}")
            print(f"POST endpoint: {endpoint_url}")

            # Send JSON-RPC initialize message
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "1.0.0",
                    "clientInfo": {
                        "name": "cascade-minimal-test",
                        "version": "0.1.0"
                    },
                    "capabilities": {},
                }
            }
            headers = {"Content-Type": "application/json"}
            print(f"POSTing initialize message to {endpoint_url} ...")
            resp = await client.post(endpoint_url, json=payload, headers=headers, timeout=10.0)
            print(f"POST status: {resp.status_code}")
            print(f"POST response: {resp.text}")

            # Wait for handshake response (first message event)
            try:
                handshake_result = await asyncio.wait_for(tool_result_queue.get(), timeout=10.0)
                print(f"[HANDSHAKE RESULT] {handshake_result}")
                # Only proceed with tool calls after handshake result is received
            except asyncio.TimeoutError:
                print(f"[ERROR] Timed out waiting for handshake result from {sse_url}")
                listener_task.cancel()
                return False

            # Now safe to send list_tools call
            print("Sending list_tools call...")
            tool_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            tool_resp = await client.post(endpoint_url, json=tool_payload, headers=headers, timeout=10.0)
            print(f"POST list_tools status: {tool_resp.status_code}")
            print(f"POST list_tools response: {tool_resp.text}")

            # Wait for tool result (second message event)
            try:
                tool_result = await asyncio.wait_for(tool_result_queue.get(), timeout=10.0)
                print(f"[LIST TOOLS RESULT] {tool_result}")
            except asyncio.TimeoutError:
                print(f"[ERROR] Timed out waiting for tool result from {sse_url}")

            # Example: Compose and send a crawl_website tool call
            print("Sending crawl_website tool call...")
            crawl_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "crawl_website",
                    "arguments": {"url": "https://ai.pydantic.dev"}
                }
            }
            crawl_resp = await client.post(endpoint_url, json=crawl_payload, headers=headers, timeout=10.0)
            print(f"POST crawl_website status: {crawl_resp.status_code}")
            print(f"POST crawl_website response: {crawl_resp.text}")

            # Wait for crawl result (third message event)
            try:
                crawl_result = await asyncio.wait_for(tool_result_queue.get(), timeout=10.0)
                print(f"[CRAWL TOOL RESULT] {crawl_result}")
            except asyncio.TimeoutError:
                print(f"[ERROR] Timed out waiting for crawl result from {sse_url}")

            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass
            return True
        except Exception as e:
            print(f"[ERROR] Exception for {sse_url}: {e}")
            return False

async def main():
    # Try both variants for both MCP servers
    servers = [
        ("http://localhost:8054", "crawl4ai-mcp"),
        ("http://localhost:8058", "agentic-rag-kg")
    ]
    variants = ["/sse", "/sse/"]
    for base_url, label in servers:
        print(f"\n\n=== Testing server: {label} ({base_url}) ===")
        for variant in variants:
            await try_sse_variant(base_url, variant)

if __name__ == "__main__":
    asyncio.run(main())
