#!/usr/bin/env python3
"""
Simple MCP server connectivity test using only built-in Python libraries.
"""
import json
import socket
import subprocess
import sys
import urllib.request
import urllib.error
from urllib.parse import urljoin

def test_port_connectivity(host="localhost", port=8054):
    """Test if the server port is accessible."""
    print(f"Testing port connectivity to {host}:{port}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✓ Port {port} is open and accessible")
            return True
        else:
            print(f"✗ Port {port} is not accessible (connection refused)")
            return False
            
    except Exception as e:
        print(f"✗ Error testing port connectivity: {e}")
        return False

def test_http_endpoint(url):
    """Test HTTP endpoint using urllib."""
    print(f"Testing HTTP endpoint: {url}")
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            status_code = response.getcode()
            
            if status_code in [200, 404, 405]:  # Server is responding
                print(f"✓ HTTP endpoint responding (status: {status_code})")
                return True
            else:
                print(f"✗ HTTP endpoint returned unexpected status: {status_code}")
                return False
                
    except urllib.error.URLError as e:
        if "Connection refused" in str(e):
            print("✗ Connection refused - server is not running")
        else:
            print(f"✗ HTTP request failed: {e}")
        return False
    except Exception as e:
        print(f"✗ HTTP endpoint test failed: {e}")
        return False

def check_server_process():
    """Check if a process is listening on port 8054."""
    print("Checking for server process...")
    
    try:
        # Use netstat to check for listening processes
        result = subprocess.run(
            ['netstat', '-an'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if ":8054" in result.stdout:
            print("✓ Process found listening on port 8054")
            return True
        else:
            print("✗ No process found listening on port 8054")
            return False
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("✗ Could not check for server process (netstat unavailable)")
        return False
    except Exception as e:
        print(f"✗ Error checking server process: {e}")
        return False

def main():
    """Run basic connectivity tests."""
    print("=" * 60)
    print("MCP Crawl4AI RAG Server - Basic Connectivity Test")
    print("=" * 60)
    
    base_url = "http://localhost:8054"
    
    # Test results
    results = {}
    
    # Check if server process is running
    results['process'] = check_server_process()
    
    # Test port connectivity
    results['port'] = test_port_connectivity()
    
    # Test HTTP endpoints
    results['http_base'] = test_http_endpoint(base_url)
    results['http_health'] = test_http_endpoint(f"{base_url}/health")
    results['http_sse'] = test_http_endpoint(f"{base_url}/sse")
    
    # Summary
    print("\n" + "=" * 60)
    print("CONNECTIVITY TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result is True)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:15}: {status}")
    
    print("-" * 40)
    print(f"Tests passed: {passed_tests}/{total_tests}")
    
    print("\n" + "=" * 60)
    print("HOW TO CONNECT TO THE MCP SERVER")
    print("=" * 60)
    
    if passed_tests > 0:
        print("🎉 Server appears to be running!")
        print("\nConnection Information:")
        print(f"  Base URL:     {base_url}")
        print(f"  SSE Endpoint: {base_url}/sse")
        print(f"  Messages:     {base_url}/messages/")
        print(f"  Health:       {base_url}/health")
    else:
        print("❌ Server does not appear to be running.")
        print("\nTo start the server:")
        
    print("""
STARTING THE SERVER:

1. Option A - Using run_mcp_server.py:
   python run_mcp_server.py

2. Option B - Using uvicorn:
   uvicorn src.crawl4ai_mcp:app --host 0.0.0.0 --port 8054

3. Option C - Using Docker:
   docker-compose up

CONNECTING WITH PYTHON:

1. Install MCP dependencies:
   pip install mcp

2. Use MCP client:
   ```python
   from mcp.client.sse import sse_client
   from mcp.client.session import ClientSession
   from mcp.types import Implementation
   
   async with sse_client("http://localhost:8054/messages/") as (read, write):
       async with ClientSession(read, write, Implementation("my-client", "1.0")) as session:
           await session.initialize()
           tools = await session.list_tools()
           result = await session.call_tool("health_check", {})
   ```

AVAILABLE TOOLS:
- health_check: Simple health check
- get_available_sources: List available data sources  
- extract_content: Extract content from web pages
- crawl_website: Crawl websites
- search_web: Search the web

TROUBLESHOOTING:
- Ensure port 8054 is not in use by another process
- Check server logs for initialization errors  
- Verify crawl4ai dependencies are installed
- Make sure you're in the right directory when starting the server
""")

if __name__ == "__main__":
    main()
