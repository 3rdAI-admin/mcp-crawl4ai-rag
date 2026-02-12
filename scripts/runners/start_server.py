#!/usr/bin/env python3
"""
Start script for the MCP Crawl4AI RAG server.
"""
import os
import sys
import logging
import uvicorn
import asyncio
import json
from datetime import datetime
from fastapi import FastAPI, Request, status, APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from contextlib import asynccontextmanager
import requests
from bs4 import BeautifulSoup

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/mcp_server.log')
    ]
)
logger = logging.getLogger(__name__)

# Set log levels for libraries
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# Create a new FastAPI app
app = FastAPI(
    title="Crawl4AI MCP Server",
    description="MCP server for Crawl4AI RAG functionality",
    version="1.0.0",
    lifespan=None # No specific lifespan needed as we manage our own event loop
)

# Add CORS middleware to the app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session management for SSE
session_streams = {}  # session_id -> asyncio.Queue

def generate_session_id():
    import uuid
    return uuid.uuid4().hex

async def sse_send(session_id, event):
    stream = session_streams.get(session_id)
    if stream:
        await stream.put(f"event: message\ndata: {json.dumps(event)}\n\n")

# Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint to verify the server is running."""
    try:
        # Check if the MCP server is reachable
        if hasattr(mcp, 'is_healthy') and callable(mcp.is_healthy):
            is_healthy = await mcp.is_healthy()
            if not is_healthy:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"status": "unhealthy", "error": "MCP server is not healthy"}
                )
        
        # Check if Crawl4AI is available
        if not CRAWL4AI_AVAILABLE:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "error": "Crawl4AI is not available"}
            )
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "mcp_server": "running",
                "crawl4ai": "available" if CRAWL4AI_AVAILABLE else "unavailable"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )

# Root endpoint that provides basic information and links to documentation
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint that provides basic information about the server"""
    return {
        "message": "Crawl4AI MCP Server is running.",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "mcp": "/mcp"
        }
    }

@app.get("/sse")
async def sse_endpoint(request: Request):
    session_id = generate_session_id()
    queue = asyncio.Queue()
    session_streams[session_id] = queue

    async def event_generator():
        # Send the initial session_id event
        yield f"event: endpoint\ndata: /messages/?session_id={session_id}\n\n"
        while True:
            data = await queue.get()
            yield data

    return EventSourceResponse(event_generator())

# --- Tool Implementations (replace with your real logic) ---
async def extract_content(args):
    url = args.get("url")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return {"status": "success", "content": text[:2000]}  # Limit for demo
    except Exception as e:
        return {"status": "error", "error": str(e)}

async def crawl_website(args):
    url = args.get("url")
    max_pages = args.get("max_pages", 1)
    # For demo, just extract the main page and return as single-page crawl
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return {"status": "success", "pages": [{"url": url, "content": text[:2000]}]}
    except Exception as e:
        return {"status": "error", "error": str(e)}
# --- End Tool Implementations ---

@app.post("/messages/")
async def handle_message(request: Request):
    try:
        message = await request.json()
        session_id = request.query_params.get("session_id")
        method = message.get("method")
        request_id = message.get("id")

        # MCP handshake: initialize
        if method == "initialize":
            initialized_event = {
                "jsonrpc": "2.0",
                "method": "initialized",
                "params": {
                    "capabilities": {},
                    "session_id": session_id
                }
            }
            await sse_send(session_id, initialized_event)
            return JSONResponse(status_code=202, content={"status": "accepted"})

        # MCP list_tools
        elif method == "list_tools":
            tools = [
                {
                    "name": "extract_content",
                    "description": "Extract content from a URL.",
                    "parameters": {
                        "url": {"type": "string", "description": "The URL to extract content from."}
                    }
                },
                {
                    "name": "crawl_website",
                    "description": "Crawl a website and return a list of pages.",
                    "parameters": {
                        "url": {"type": "string", "description": "The URL to crawl."},
                        "max_pages": {"type": "integer", "description": "Maximum number of pages to crawl.", "default": 1}
                    }
                }
            ]
            list_tools_event = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            }
            await sse_send(session_id, list_tools_event)
            return JSONResponse(status_code=202, content={"status": "accepted"})

        # MCP tool call
        elif method == "tools/call":
            params = message.get("params", {})
            tool_name = params.get("tool_name")
            arguments = params.get("arguments", {})

            tool_map = {
                "extract_content": extract_content,
                "crawl_website": crawl_website,
                # Add more tools here
            }

            if tool_name in tool_map:
                try:
                    tool_func = tool_map[tool_name]
                    tool_result = await tool_func(arguments)
                    tool_result_event = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": tool_result
                    }
                    await sse_send(session_id, tool_result_event)
                    return JSONResponse(status_code=202, content={"status": "accepted"})
                except Exception as e:
                    error_event = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": f"Tool error: {str(e)}"
                        }
                    }
                    await sse_send(session_id, error_event)
                    return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})
            else:
                error_event = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool {tool_name} not found"
                    }
                }
                await sse_send(session_id, error_event)
                return JSONResponse(status_code=400, content={"status": "error", "error": f"Tool {tool_name} not found"})

        else:
            error_event = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method {method} not found"
                }
            }
            await sse_send(session_id, error_event)
            return JSONResponse(status_code=400, content={"status": "error", "error": "Unknown method"})

    except Exception as e:
        error_event = {
            "jsonrpc": "2.0",
            "id": message.get("id") if 'message' in locals() else None,
            "error": {
                "code": -32000,
                "message": str(e)
            }
        }
        session_id = request.query_params.get("session_id")
        await sse_send(session_id, error_event)
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})

if __name__ == "__main__":
    import asyncio
    import sys
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8052"))
    
    logger.info("=" * 60)
    logger.info(f"Starting MCP Crawl4AI RAG server on {host}:{port}")
    logger.info(f"Python version: {sys.version}")
    logger.info("=" * 60)
    
    # Remove any existing event loop policy
    try:
        import asyncio
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        else:
            asyncio.set_event_loop_policy(None)
    except Exception as e:
        logger.warning(f"Could not set event loop policy: {e}")
    
    # Create a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Import the MCP server's SSE transport
        from mcp.server.sse import SseServerTransport
        from sse_starlette.sse import EventSourceResponse
        
        # Create an SSE transport instance
        sse_transport = SseServerTransport("/messages/")
        
        # Add SSE route to the FastAPI app
        @app.api_route("/sse", methods=["GET", "POST"])
        async def sse_endpoint(request: Request):
            # Log the request method and headers for debugging
            logger.info(f"SSE connection requested via {request.method} method")
            logger.debug(f"Request headers: {request.headers}")
            
            # If it's a POST request, read and log the body
            if request.method == "POST":
                try:
                    body = await request.body()
                    if body:
                        logger.debug(f"POST body: {body.decode()}")
                except Exception as e:
                    logger.warning(f"Error reading POST body: {e}")
            
            async def event_generator():
                try:
                    # Create a simple event stream that sends a ping every 10 seconds
                    while True:
                        # Send a ping to keep the connection alive
                        yield {
                            "event": "ping",
                            "data": "ping"
                        }
                        await asyncio.sleep(10)
                except asyncio.CancelledError:
                    logger.info("SSE connection closed by client")
                except Exception as e:
                    logger.error(f"SSE connection error: {e}")
            
            return EventSourceResponse(
                event_generator(),
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "text/event-stream"
                }
            )
        
        # Add message handler route
        @app.post("/messages/")
        async def handle_message(request: Request):
            try:
                # Get the message from the request
                message = await request.json()
                logger.info(f"Received message: {message}")
                
                # Create a base response
                request_id = message.get("request_id", f"req_{int(datetime.utcnow().timestamp())}")
                response = {
                    "type": "response",
                    "request_id": request_id,
                    "status": "processing"
                }
                
                # For list_tools request, return the available tools
                if message.get("type") == "list_tools":
                    tools = [
                        {
                            "name": "crawl_website",
                            "description": "Crawl a website and extract content",
                            "parameters": {
                                "url": {"type": "string", "description": "URL to crawl"},
                                "max_pages": {"type": "integer", "description": "Maximum pages to crawl", "default": 1}
                            }
                        },
                        {
                            "name": "extract_content",
                            "description": "Extract content from a URL",
                            "parameters": {
                                "url": {"type": "string", "description": "URL to extract content from"},
                                "strategy": {"type": "string", "enum": ["llm", "css", "xpath", "lxml"], "default": "llm"}
                            }
                        },
                        {
                            "name": "search_web",
                            "description": "Search the web",
                            "parameters": {
                                "query": {"type": "string", "description": "Search query"},
                                "limit": {"type": "integer", "description": "Maximum results to return", "default": 5}
                            }
                        }
                    ]
                    response.update({
                        "type": "tool_list",
                        "status": "success",
                        "tools": tools
                    })
                
                # Handle extract_content command
                elif message.get("type") == "extract_content":
                    params = message.get("parameters", {})
                    url = params.get("url")
                    strategy = params.get("strategy", "llm")
                    
                    if not url:
                        response.update({
                            "status": "error",
                            "error": "URL parameter is required"
                        })
                    else:
                        try:
                            # Use the MCP server to process the request
                            from mcp.server.sse import SseServerTransport
                            from sse_starlette.sse import EventSourceResponse
                            
                            # Run the extraction in a background task
                            async def process_extraction():
                                try:
                                    # Get the tool function by name
                                    tool_func = getattr(mcp, "extract_content", None)
                                    if callable(tool_func):
                                        try:
                                            # Execute the tool function with the context
                                            context = {
                                                "url": url,
                                                "strategy": strategy,
                                                "request_id": request_id
                                            }
                                            result = await tool_func(context)
                                            logger.info(f"Extraction completed for {url}")
                                            logger.debug(f"Extraction result: {result}")
                                            
                                            # Send the result back to the client via SSE if possible
                                            if result and hasattr(request, 'app') and hasattr(request.app, 'sse_queues'):
                                                await request.app.sse_queues[request_id].put({
                                                    "type": "extraction_result",
                                                    "request_id": request_id,
                                                    "status": "completed",
                                                    "result": result
                                                })
                                        except Exception as e:
                                            error_msg = f"Error executing extract_content tool: {str(e)}"
                                            logger.error(error_msg, exc_info=True)
                                            if hasattr(request, 'app') and hasattr(request.app, 'sse_queues'):
                                                await request.app.sse_queues[request_id].put({
                                                    "type": "error",
                                                    "request_id": request_id,
                                                    "error": error_msg
                                                })
                                    else:
                                        error_msg = "Tool 'extract_content' not found"
                                        logger.error(error_msg)
                                        if hasattr(request, 'app') and hasattr(request.app, 'sse_queues'):
                                            await request.app.sse_queues[request_id].put({
                                                "type": "error",
                                                "request_id": request_id,
                                                "error": error_msg
                                            })
                                except Exception as e:
                                    logger.error(f"Error in extraction task: {e}", exc_info=True)
                            
                            # Start the background task
                            asyncio.create_task(process_extraction())
                            
                            response.update({
                                "status": "processing",
                                "message": f"Extraction started for {url} with {strategy} strategy"
                            })
                            
                        except Exception as e:
                            logger.error(f"Error processing extract_content: {e}", exc_info=True)
                            response.update({
                                "status": "error",
                                "error": str(e)
                            })
                
                # Handle crawl_website command
                elif message.get("type") == "crawl_website":
                    params = message.get("parameters", {})
                    url = params.get("url")
                    max_pages = params.get("max_pages", 1)
                    
                    if not url:
                        response.update({
                            "status": "error",
                            "error": "URL parameter is required"
                        })
                    else:
                        try:
                            from mcp.server.sse import SseServerTransport
                            from sse_starlette.sse import EventSourceResponse
                            
                            async def process_crawl():
                                try:
                                    # Get the tool function by name
                                    tool_func = getattr(mcp, "crawl_website", None)
                                    if callable(tool_func):
                                        try:
                                            # Execute the tool function with the context
                                            context = {
                                                "url": url,
                                                "max_pages": max_pages,
                                                "request_id": request_id
                                            }
                                            result = await tool_func(context)
                                            logger.info(f"Crawl completed for {url}")
                                            logger.debug(f"Crawl result: {result}")
                                            
                                            # Send the result back to the client via SSE if possible
                                            if result and hasattr(request, 'app') and hasattr(request.app, 'sse_queues'):
                                                await request.app.sse_queues[request_id].put({
                                                    "type": "crawl_result",
                                                    "request_id": request_id,
                                                    "status": "completed",
                                                    "result": result
                                                })
                                        except Exception as e:
                                            error_msg = f"Error executing crawl_website tool: {str(e)}"
                                            logger.error(error_msg, exc_info=True)
                                            if hasattr(request, 'app') and hasattr(request.app, 'sse_queues'):
                                                await request.app.sse_queues[request_id].put({
                                                    "type": "error",
                                                    "request_id": request_id,
                                                    "error": error_msg
                                                })
                                    else:
                                        error_msg = "Tool 'crawl_website' not found"
                                        logger.error(error_msg)
                                        if hasattr(request, 'app') and hasattr(request.app, 'sse_queues'):
                                            await request.app.sse_queues[request_id].put({
                                                "type": "error",
                                                "request_id": request_id,
                                                "error": error_msg
                                            })
                                except Exception as e:
                                    logger.error(f"Error in crawl task: {e}", exc_info=True)
                            
                            asyncio.create_task(process_crawl())
                            
                            response.update({
                                "status": "processing",
                                "message": f"Crawl started for {url} (max {max_pages} pages)"
                            })
                            
                        except Exception as e:
                            logger.error(f"Error processing crawl_website: {e}", exc_info=True)
                            response.update({
                                "status": "error",
                                "error": str(e)
                            })
                
                return response
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in request")
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "error": "Invalid JSON in request"}
                )
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "error": str(e)}
                )
                return {"status": "error", "message": str(e)}
        
        # Start the FastAPI server
        logger.info(f"Starting FastAPI server on {host}:{port}...")
        logger.info("Mounted SSE endpoint at /sse")
        logger.info("Mounted message handler at /messages/")
        
        # Configure uvicorn
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level=os.getenv("LOG_LEVEL", "info").lower(),
            loop="asyncio",
            reload=False,
            # Enable multi-processing
            workers=int(os.getenv("WEB_CONCURRENCY", 1)),
            # Timeout for keep-alive connections
            timeout_keep_alive=30,
            # Enable HTTP/2
            http="h11",
        )
        
        # Create server instance
        server = uvicorn.Server(config)
        
        # Run the server
        try:
            logger.info("Starting Uvicorn server...")
            loop.run_until_complete(server.serve())
        except Exception as e:
            logger.error(f"Error starting server: {e}", exc_info=True)
            raise
        finally:
            logger.info("Server shutting down...")
        
    except Exception as e:
        logger.critical(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    finally:
        # Clean up the event loop
        loop.close()
        sys.exit(0)
