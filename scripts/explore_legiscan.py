#!/usr/bin/env python3
import requests
import sys

def explore_legiscan():
    """Explore LegiScan API for Senate roll call data."""
    
    # LegiScan API base URL
    base_url = "https://api.legiscan.com"
    
    # Note: LegiScan API requires an API key
    # You can get one from: https://legiscan.com/legiscan
    
    api_key = input("Enter your LegiScan API key: ").strip()
    
    # Test endpoints
    endpoints = [
        f"{base_url}/?key={api_key}&op=getSessionList&state=US",
        f"{base_url}/?key={api_key}&op=getMasterList&id=119",  # 119th Congress
        f"{base_url}/?key={api_key}&op=getRollCall&id=123456",  # Example roll call ID
        f"{base_url}/?key={api_key}&op=getBill&id=123456",  # Example bill ID
    ]
    
    for url in endpoints:
        print(f"\nTesting: {url}")
        try:
            response = requests.get(url, timeout=30)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    
                    # Check for specific data
                    if 'sessionlist' in str(data).lower():
                        print("*** SESSION LIST DATA ***")
                    elif 'rollcall' in str(data).lower():
                        print("*** ROLL CALL DATA ***")
                    elif 'bill' in str(data).lower():
                        print("*** BILL DATA ***")
                    else:
                        print("*** OTHER DATA ***")
                        
                except Exception as e:
                    print(f"JSON parsing error: {e}")
                    print(f"Raw response: {response.text[:500]}")
            else:
                print(f"Failed with status {response.status_code}")
                print(f"Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"Error: {e}")

def test_legiscan_rollcalls():
    """Test specific LegiScan roll call endpoints."""
    api_key = input("Enter your LegiScan API key: ").strip()
    
    # Test getting roll calls for 119th Congress
    url = f"https://api.legiscan.com/?key={api_key}&op=getMasterList&id=119"
    
    print(f"\nTesting LegiScan roll calls: {url}")
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")
        else:
            print(f"Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("LegiScan API Exploration")
    print("Note: You need an API key from https://legiscan.com/legiscan")
    print("Replace 'YOUR_API_KEY_HERE' in the script with your actual API key")
    
    explore_legiscan()
    test_legiscan_rollcalls()
