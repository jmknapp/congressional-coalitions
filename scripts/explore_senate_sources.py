#!/usr/bin/env python3
import requests
import sys

def explore_senate_sources():
    """Explore different Senate.gov data sources for roll call votes."""
    
    # List of potential Senate.gov endpoints to try
    endpoints = [
        "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_1.xml",
        "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_2.xml",
        "https://www.senate.gov/legislative/LIS/roll_call_votes/vote119_1/vote_119_1_00001.xml",
        "https://www.senate.gov/legislative/LIS/roll_call_votes/vote119_1/vote_119_1_00499.xml",
        "https://www.senate.gov/legislative/LIS/roll_call_votes/vote119_2/vote_119_2_00001.xml",
        # Alternative Senate.gov endpoints
        "https://www.senate.gov/legislative/votes.htm",
        "https://www.senate.gov/legislative/LIS/roll_call_votes/",
        # Try some older Congress endpoints
        "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_118_2.xml",
        "https://www.senate.gov/legislative/LIS/roll_call_votes/vote118_2/vote_118_2_00400.xml",
    ]
    
    for url in endpoints:
        print(f"\nTesting: {url}")
        try:
            response = requests.get(url, timeout=30)
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status_code == 200:
                content = response.text[:500]
                print(f"First 500 chars: {content}")
                
                if 'vote_summary' in content or 'vote_number' in content:
                    print("*** CONTAINS VOTE DATA ***")
                elif 'Roll Call Vote Unavailable' in content:
                    print("*** VOTE UNAVAILABLE ***")
                elif '<html' in content.lower():
                    print("*** HTML PAGE ***")
                else:
                    print("*** UNKNOWN CONTENT ***")
            else:
                print(f"Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    explore_senate_sources()
