#!/usr/bin/env python3
"""
Test connectivity to MCP server on port 8052.
"""
import json
import socket
import urllib.request
import urllib.error

def test_endpoints():
    """Test various endpoints on port 8052."""
    base_url = "http://localhost:8052"
    endpoints = [
        f"{base_url}",
        f"{base_url}/health", 
        f"{base_url}/sse",
        f"{base_url}/messages/",
        f"{base_url}/docs"  # FastAPI auto-docs
    ]
    
    print("Testing MCP Crawl4AI server on port 8052...")
    print("=" * 50)
    
    for url in endpoints:
        print(f"\nTesting: {url}")
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                status = response.getcode()
                content_type = response.getheader('content-type', 'unknown')
                
                if status == 200:
                    print(f"✓ SUCCESS (200) - Content-Type: {content_type}")
                    
                    # Try to read a bit of content
                    if 'application/json' in content_type:
                        try:
                            data = json.loads(response.read().decode())
                            print(f"  JSON Response: {data}")
                        except:
                            print("  (Could not parse JSON)")
                    elif 'text/html' in content_type:
                        content = response.read().decode()[:200]
                        print(f"  HTML Preview: {content[:100]}...")
                    
                else:
                    print(f"✓ ACCESSIBLE ({status}) - Content-Type: {content_type}")
                    
        except urllib.error.HTTPError as e:
            print(f"✗ HTTP Error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            print(f"✗ URL Error: {e.reason}")
        except Exception as e:
            print(f"✗ Error: {e}")

if __name__ == "__main__":
    test_endpoints()
