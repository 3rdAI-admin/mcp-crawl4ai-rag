import asyncio
from mcp.client import streamable_http

async def test_connection():
    async with streamable_http.streamablehttp_client("http://localhost:8054") as streams:
        print("Connected to MCP server")
        print("Streams type:", type(streams))
        print("Streams dir:", [attr for attr in dir(streams) if not attr.startswith('_')])
        
        # Get the read and write streams
        read_stream = streams[0]
        write_stream = streams[1]
        
        # Send a test message
        message = {
            "jsonrpc": "2.0",
            "method": "mcp.list_tools",
            "params": {},
            "id": 1
        }
        
        await write_stream.send(message)
        print("Sent message:", message)
        
        # Wait for a response
        response = await read_stream.receive()
        print("Received response:", response)

if __name__ == "__main__":
    asyncio.run(test_connection())
