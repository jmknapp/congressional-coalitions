#!/usr/bin/env python3
"""
Test script to check what Senate votes are available in Congress.gov API.
"""

import os
import requests
import json

API_KEY = os.environ.get('CONGRESS_GOV_API_KEY', '')
BASE_URL = 'https://api.congress.gov/v3'
HEADERS = {'Accept': 'application/json'}

def test_senate_votes():
    """Test different Senate vote endpoints to see what's available."""
    
    # Test different Senate vote patterns
    test_patterns = [
        # Standard pattern
        f'{BASE_URL}/senate-vote/119/1/1?api_key={API_KEY}&format=json',
        # Alternative patterns
        f'{BASE_URL}/senate-vote/119/1/001?api_key={API_KEY}&format=json',
        f'{BASE_URL}/senate-vote/119/1/1?api_key={API_KEY}',
        # Try different session
        f'{BASE_URL}/senate-vote/119/2/1?api_key={API_KEY}&format=json',
        # Try different Congress
        f'{BASE_URL}/senate-vote/118/1/1?api_key={API_KEY}&format=json',
    ]
    
    for i, url in enumerate(test_patterns):
        print(f"\nTest {i+1}: {url}")
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Keys: {list(data.keys())}")
                if 'senateRollCallVote' in data:
                    vote_data = data['senateRollCallVote']
                    print(f"Vote keys: {list(vote_data.keys())}")
                elif 'senateVote' in data:
                    vote_data = data['senateVote']
                    print(f"Vote keys: {list(vote_data.keys())}")
                else:
                    print(f"Data: {json.dumps(data, indent=2)[:500]}...")
            else:
                print(f"Response: {response.text[:200]}...")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    if not API_KEY:
        print("CONGRESS_GOV_API_KEY environment variable not set")
        exit(1)
    
    test_senate_votes()
