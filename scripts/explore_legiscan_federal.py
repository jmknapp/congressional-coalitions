#!/usr/bin/env python3
import requests
import sys

def explore_legiscan_federal():
    """Explore LegiScan API for federal Congressional data."""
    
    api_key = "5360b7973d27c12c971a27ff32665137"
    base_url = "https://api.legiscan.com"
    
    # Test different federal endpoints
    endpoints = [
        f"{base_url}/?key={api_key}&op=getSessionList&state=US",
        f"{base_url}/?key={api_key}&op=getMasterList&id=119&state=US",
        f"{base_url}/?key={api_key}&op=getMasterList&id=119&state=DC",
        f"{base_url}/?key={api_key}&op=getMasterList&id=119&state=FED",
        f"{base_url}/?key={api_key}&op=getMasterList&id=119&state=CONGRESS",
        f"{base_url}/?key={api_key}&op=getMasterList&id=119&state=UNITED_STATES",
        # Try different session IDs
        f"{base_url}/?key={api_key}&op=getMasterList&id=118&state=US",
        f"{base_url}/?key={api_key}&op=getMasterList&id=117&state=US",
        # Try roll call specific endpoints
        f"{base_url}/?key={api_key}&op=getRollCall&id=123456&state=US",
        f"{base_url}/?key={api_key}&op=getRollCall&id=123456&state=DC",
    ]
    
    for url in endpoints:
        print(f"\nTesting: {url}")
        try:
            response = requests.get(url, timeout=30)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    
                    # Check if it contains federal data
                    if 'masterlist' in data:
                        masterlist = data['masterlist']
                        if isinstance(masterlist, dict):
                            print(f"Masterlist keys: {list(masterlist.keys())}")
                            # Check first few items to see if they're federal
                            items = list(masterlist.items())[:3]
                            for key, item in items:
                                if isinstance(item, dict):
                                    print(f"  Item {key}: {item.get('number', 'N/A')} - {item.get('title', 'N/A')[:50]}...")
                    
                    # Check for roll call data
                    if 'roll_call' in data:
                        rollcall = data['roll_call']
                        if isinstance(rollcall, dict):
                            print(f"Roll call data: {rollcall}")
                    
                except Exception as e:
                    print(f"JSON parsing error: {e}")
                    print(f"Raw response: {response.text[:500]}")
            else:
                print(f"Failed with status {response.status_code}")
                print(f"Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"Error: {e}")

def test_specific_rollcalls():
    """Test specific roll call IDs that might be federal."""
    api_key = "5360b7973d27c12c971a27ff32665137"
    base_url = "https://api.legiscan.com"
    
    # Try some common roll call ID patterns
    rollcall_ids = [1, 10, 100, 1000, 10000, 100000]
    
    for rollcall_id in rollcall_ids:
        url = f"{base_url}/?key={api_key}&op=getRollCall&id={rollcall_id}"
        print(f"\nTesting roll call ID {rollcall_id}: {url}")
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'roll_call' in data:
                    rollcall = data['roll_call']
                    print(f"Found roll call: {rollcall.get('question', 'N/A')[:50]}...")
                    print(f"  State: {rollcall.get('state', 'N/A')}")
                    print(f"  Session: {rollcall.get('session', 'N/A')}")
                else:
                    print("No roll call data found")
            else:
                print(f"Failed: {response.status_code}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("LegiScan Federal Data Exploration")
    explore_legiscan_federal()
    test_specific_rollcalls()
