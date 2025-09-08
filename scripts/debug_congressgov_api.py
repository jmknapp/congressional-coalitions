#!/usr/bin/env python3
"""
Debug script to test Congress.gov API connectivity and endpoints.
"""

import os
import requests
import json
from datetime import datetime, date, timedelta

def test_api_connectivity():
    """Test basic API connectivity and endpoints."""
    api_key = os.getenv('CONGRESSGOV_API_KEY', 'DEMO_KEY')
    
    print(f"API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else 'SHORT'}")
    print(f"API Key length: {len(api_key)}")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Congressional-Coalitions/1.0 (https://github.com/jmknapp/congressional-coalitions)'
    })
    
    # Test 1: Basic API connectivity
    print("\n=== Test 1: Basic API Connectivity ===")
    test_url = "https://api.congress.gov/v3/bill/119/hr/1"
    params = {'api_key': api_key, 'format': 'json'}
    
    try:
        response = session.get(test_url, params=params, timeout=30)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✓ Basic API connectivity works")
        else:
            print(f"✗ Basic API failed: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Connection error: {e}")
    
    # Test 2: Roll call endpoint structure
    print("\n=== Test 2: Roll Call Endpoint Structure ===")
    
    # Try different endpoint formats
    endpoints_to_test = [
        "https://api.congress.gov/v3/roll-call-vote/119/house",
        "https://api.congress.gov/v3/roll-call-vote/118/house",  # Try 118th Congress
        "https://api.congress.gov/v3/roll-call-vote/119/house/1",  # Try with session
        "https://api.congress.gov/v3/roll-call-vote/119/house/1/1",  # Try with session and roll number
    ]
    
    for endpoint in endpoints_to_test:
        print(f"\nTesting: {endpoint}")
        try:
            response = session.get(endpoint, params=params, timeout=30)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ Success! Keys: {list(data.keys())}")
                if 'rollCallVotes' in data:
                    print(f"  Roll calls found: {len(data['rollCallVotes'])}")
                break
            else:
                print(f"  ✗ Failed: {response.text[:100]}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    # Test 3: Check available Congresses
    print("\n=== Test 3: Available Congresses ===")
    congress_url = "https://api.congress.gov/v3/congress"
    try:
        response = session.get(congress_url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print("✓ Congress endpoint works")
            if 'congresses' in data:
                congresses = data['congresses']
                print(f"Available Congresses: {[c.get('number') for c in congresses]}")
        else:
            print(f"✗ Congress endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Congress endpoint error: {e}")
    
    # Test 4: Check roll call vote endpoint documentation
    print("\n=== Test 4: Roll Call Vote Endpoint Info ===")
    rollcall_info_url = "https://api.congress.gov/v3/roll-call-vote"
    try:
        response = session.get(rollcall_info_url, params=params, timeout=30)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("✓ Roll call endpoint accessible")
            print(f"Response keys: {list(data.keys())}")
        else:
            print(f"✗ Roll call endpoint failed: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Roll call endpoint error: {e}")

if __name__ == "__main__":
    test_api_connectivity()
