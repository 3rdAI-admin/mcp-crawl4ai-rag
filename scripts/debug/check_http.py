import requests

def check_server():
    base_url = "http://localhost:8054"
    
    try:
        # Try to get server info
        print("Checking server info...")
        response = requests.get(f"{base_url}/api/info", timeout=5)
        print(f"Server info: {response.status_code}")
        if response.status_code == 200:
            print(response.json())
        
        # Try to list tools
        print("\nListing tools...")
        response = requests.get(f"{base_url}/api/tools", timeout=5)
        print(f"Tools status: {response.status_code}")
        if response.status_code == 200:
            print(response.json())
        
        # Try to list resources
        print("\nListing resources...")
        response = requests.get(f"{base_url}/api/resources", timeout=5)
        print(f"Resources status: {response.status_code}")
        if response.status_code == 200:
            print(response.json())
            
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_server()
