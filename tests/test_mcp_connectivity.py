#!/usr/bin/env python3
"""
Comprehensive MCP server connectivity test script.
Tests various connection methods and server functionality.
"""
import asyncio
import json
import logging
import time
import httpx
import subprocess
import sys
import os
from typing import Dict, Any, Optional
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MCPConnectivityTester:
    """Test connectivity to the MCP Crawl4AI RAG server."""
    
    def __init__(self, base_url: str = "http://localhost:8054"):
        """Initialize the connectivity tester.
        
        Args:
            base_url: Base URL of the MCP server
        """
        self.base_url = base_url.rstrip('/')
        self.sse_url = f"{self.base_url}/sse"
        self.messages_url = f"{self.base_url}/messages/"
        self.health_url = f"{self.base_url}/health"
        self.results = {}
    
    async def test_basic_http_connectivity(self) -> bool:
        """Test basic HTTP connectivity to the server."""
        logger.info("Testing basic HTTP connectivity...")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url)
                
                if response.status_code in [200, 404, 405]:  # Server is responding
                    logger.info(f"✓ Server is responding (status: {response.status_code})")
                    self.results['http_connectivity'] = True
                    return True
                else:
                    logger.warning(f"✗ Server responded with unexpected status: {response.status_code}")
                    self.results['http_connectivity'] = False
                    return False
                    
        except httpx.ConnectError:
            logger.error("✗ Connection refused - server may not be running")
            self.results['http_connectivity'] = False
            return False
        except Exception as e:
            logger.error(f"✗ HTTP connectivity test failed: {e}")
            self.results['http_connectivity'] = False
            return False
    
    async def test_health_endpoint(self) -> bool:
        """Test the health check endpoint."""
        logger.info("Testing health endpoint...")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.health_url)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✓ Health endpoint working: {data}")
                    self.results['health_endpoint'] = True
                    return True
                else:
                    logger.warning(f"✗ Health endpoint returned status: {response.status_code}")
                    self.results['health_endpoint'] = False
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Health endpoint test failed: {e}")
            self.results['health_endpoint'] = False
            return False
    
    async def test_sse_endpoint(self) -> bool:
        """Test SSE endpoint connectivity."""
        logger.info("Testing SSE endpoint...")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.sse_url,
                    headers={'Accept': 'text/event-stream'}
                )
                
                if response.status_code == 200:
                    logger.info("✓ SSE endpoint is accessible")
                    self.results['sse_endpoint'] = True
                    return True
                else:
                    logger.warning(f"✗ SSE endpoint returned status: {response.status_code}")
                    self.results['sse_endpoint'] = False
                    return False
                    
        except Exception as e:
            logger.error(f"✗ SSE endpoint test failed: {e}")
            self.results['sse_endpoint'] = False
            return False
    
    async def test_messages_endpoint(self) -> bool:
        """Test messages endpoint."""
        logger.info("Testing messages endpoint...")
        
        try:
            # Test with a simple POST request
            test_message = {
                "jsonrpc": "2.0",
                "id": "test-message",
                "method": "ping",
                "params": {}
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.messages_url,
                    json=test_message,
                    headers={'Content-Type': 'application/json'}
                )
                
                # Accept various response codes as the endpoint is working
                if response.status_code in [200, 202, 400, 405]:
                    logger.info(f"✓ Messages endpoint responding (status: {response.status_code})")
                    self.results['messages_endpoint'] = True
                    return True
                else:
                    logger.warning(f"✗ Messages endpoint returned unexpected status: {response.status_code}")
                    self.results['messages_endpoint'] = False
                    return False
                    
        except Exception as e:
            logger.error(f"✗ Messages endpoint test failed: {e}")
            self.results['messages_endpoint'] = False
            return False
    
    async def test_mcp_client_connection(self) -> bool:
        """Test MCP client connection using the official MCP SDK."""
        logger.info("Testing MCP client connection...")
        
        try:
            from mcp.client.sse import sse_client
            from mcp.client.session import ClientSession
            from mcp.types import Implementation
            
            # Client information
            client_info = Implementation(name="connectivity-test", version="1.0.0")
            
            # Test connection with a short timeout
            async with sse_client(self.messages_url, timeout=10.0) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    client_info=client_info
                ) as session:
                    # Try to initialize
                    await asyncio.wait_for(session.initialize(), timeout=5.0)
                    
                    # Try to list tools
                    tools = await asyncio.wait_for(session.list_tools(), timeout=5.0)
                    
                    logger.info(f"✓ MCP client connected successfully")
                    logger.info(f"  Available tools: {len(tools.tools) if hasattr(tools, 'tools') else 'Unknown'}")
                    
                    self.results['mcp_client'] = True
                    self.results['available_tools'] = len(tools.tools) if hasattr(tools, 'tools') else 0
                    
                    return True
                    
        except asyncio.TimeoutError:
            logger.error("✗ MCP client connection timed out")
            self.results['mcp_client'] = False
            return False
        except ImportError:
            logger.error("✗ MCP SDK not available (pip install mcp)")
            self.results['mcp_client'] = False
            return False
        except Exception as e:
            logger.error(f"✗ MCP client connection failed: {e}")
            self.results['mcp_client'] = False
            return False
    
    async def test_tool_call(self) -> bool:
        """Test calling a tool through the MCP interface."""
        logger.info("Testing tool call...")
        
        try:
            from mcp.client.sse import sse_client
            from mcp.client.session import ClientSession
            from mcp.types import Implementation
            
            # Client information
            client_info = Implementation(name="connectivity-test", version="1.0.0")
            
            async with sse_client(self.messages_url, timeout=15.0) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    client_info=client_info
                ) as session:
                    # Initialize session
                    await asyncio.wait_for(session.initialize(), timeout=5.0)
                    
                    # Try to call a simple tool (health_check if available)
                    try:
                        result = await asyncio.wait_for(
                            session.call_tool("health_check", {}), 
                            timeout=10.0
                        )
                        
                        logger.info(f"✓ Tool call successful: {result}")
                        self.results['tool_call'] = True
                        return True
                        
                    except Exception as tool_error:
                        # Try get_available_sources as backup
                        try:
                            result = await asyncio.wait_for(
                                session.call_tool("get_available_sources", {}), 
                                timeout=10.0
                            )
                            
                            logger.info(f"✓ Tool call successful: {result}")
                            self.results['tool_call'] = True
                            return True
                            
                        except Exception as backup_error:
                            logger.warning(f"✗ Tool calls failed: {tool_error}, {backup_error}")
                            self.results['tool_call'] = False
                            return False
                    
        except Exception as e:
            logger.error(f"✗ Tool call test failed: {e}")
            self.results['tool_call'] = False
            return False
    
    def check_server_process(self) -> bool:
        """Check if the MCP server process is running."""
        logger.info("Checking for running server process...")
        
        try:
            # Check for processes listening on port 8054
            result = subprocess.run(
                ['lsof', '-i', ':8054'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                logger.info("✓ Process found listening on port 8054")
                logger.info(f"  Process info: {result.stdout.strip()}")
                self.results['server_process'] = True
                return True
            else:
                logger.warning("✗ No process found listening on port 8054")
                self.results['server_process'] = False
                return False
                
        except subprocess.TimeoutExpired:
            logger.warning("✗ Timeout checking for server process")
            self.results['server_process'] = False
            return False
        except FileNotFoundError:
            logger.warning("✗ lsof command not available (install lsof for process checking)")
            self.results['server_process'] = False
            return False
        except Exception as e:
            logger.error(f"✗ Error checking server process: {e}")
            self.results['server_process'] = False
            return False
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all connectivity tests."""
        logger.info("=" * 60)
        logger.info("MCP Crawl4AI RAG Server Connectivity Test")
        logger.info("=" * 60)
        
        # Check if server process is running
        self.check_server_process()
        
        # Test basic connectivity
        await self.test_basic_http_connectivity()
        
        # Test specific endpoints
        await self.test_health_endpoint()
        await self.test_sse_endpoint()
        await self.test_messages_endpoint()
        
        # Test MCP protocol
        await self.test_mcp_client_connection()
        await self.test_tool_call()
        
        # Summary
        logger.info("=" * 60)
        logger.info("CONNECTIVITY TEST SUMMARY")
        logger.info("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result is True)
        
        for test_name, result in self.results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"{test_name:25}: {status}")
        
        logger.info("-" * 40)
        logger.info(f"Tests passed: {passed_tests}/{total_tests}")
        
        if passed_tests == total_tests:
            logger.info("🎉 All tests passed! MCP server is fully functional.")
        elif passed_tests >= total_tests * 0.5:
            logger.info("⚠️  Some tests failed. Server is partially functional.")
        else:
            logger.info("❌ Most tests failed. Server may not be running or configured correctly.")
        
        return self.results
    
    def print_connection_instructions(self):
        """Print instructions for connecting to the MCP server."""
        logger.info("=" * 60)
        logger.info("CONNECTION INSTRUCTIONS")
        logger.info("=" * 60)
        
        logger.info("""
1. START THE SERVER:
   
   Option A - Using run_mcp_server.py:
   python run_mcp_server.py
   
   Option B - Using uvicorn directly:
   uvicorn src.crawl4ai_mcp:app --host 0.0.0.0 --port 8054
   
   Option C - Using Docker:
   docker-compose up

2. CONNECTION ENDPOINTS:
   
   Base URL:     http://localhost:8054
   SSE Endpoint: http://localhost:8054/sse  
   Messages:     http://localhost:8054/messages/
   Health:       http://localhost:8054/health

3. CONNECT WITH PYTHON CLIENT:
   
   from mcp.client.sse import sse_client
   from mcp.client.session import ClientSession
   from mcp.types import Implementation
   
   async with sse_client("http://localhost:8054/messages/") as (read, write):
       async with ClientSession(read, write, Implementation("my-client", "1.0.0")) as session:
           await session.initialize()
           tools = await session.list_tools()
           result = await session.call_tool("health_check", {})

4. AVAILABLE TOOLS:
   - health_check: Simple health check
   - get_available_sources: List available data sources
   - extract_content: Extract content from web pages
   - crawl_website: Crawl websites
   - search_web: Search the web

5. TROUBLESHOOTING:
   - Ensure port 8054 is not in use by another process
   - Check server logs for initialization errors
   - Verify crawl4ai dependencies are installed
   - Try running tests: python test_mcp_connectivity.py
        """)

async def main():
    """Main function to run connectivity tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test MCP server connectivity")
    parser.add_argument(
        "--url", 
        default="http://localhost:8054",
        help="Base URL of the MCP server (default: http://localhost:8054)"
    )
    parser.add_argument(
        "--instructions-only",
        action="store_true",
        help="Only show connection instructions without running tests"
    )
    
    args = parser.parse_args()
    
    tester = MCPConnectivityTester(args.url)
    
    if args.instructions_only:
        tester.print_connection_instructions()
        return
    
    try:
        results = await tester.run_all_tests()
        tester.print_connection_instructions()
        
        # Exit with appropriate code
        passed_tests = sum(1 for result in results.values() if result is True)
        total_tests = len(results)
        
        if passed_tests == total_tests:
            sys.exit(0)  # All tests passed
        elif passed_tests >= total_tests * 0.5:
            sys.exit(1)  # Some tests failed
        else:
            sys.exit(2)  # Most tests failed
            
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(3)

if __name__ == "__main__":
    asyncio.run(main())
