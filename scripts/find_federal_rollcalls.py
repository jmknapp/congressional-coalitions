#!/usr/bin/env python3
import requests
import sys

def find_federal_rollcalls():
    """Find federal Congressional roll calls in LegiScan."""
    
    api_key = "5360b7973d27c12c971a27ff32665137"
    base_url = "https://api.legiscan.com"
    
    # Try different roll call ID ranges to find federal ones
    # Start with some known ranges that might contain federal data
    rollcall_ranges = [
        (100000, 200000),  # 2009-2010 range
        (200000, 300000),  # 2011-2012 range
        (300000, 400000),  # 2013-2014 range
        (400000, 500000),  # 2015-2016 range
        (500000, 600000),  # 2017-2018 range
        (600000, 700000),  # 2019-2020 range
        (700000, 800000),  # 2021-2022 range
        (800000, 900000),  # 2023-2024 range
        (900000, 1000000), # 2025+ range
    ]
    
    federal_rollcalls = []
    
    for start_id, end_id in rollcall_ranges:
        print(f"\nSearching range {start_id}-{end_id}...")
        
        # Sample a few IDs from each range
        sample_ids = [start_id, start_id + 1000, start_id + 2000, start_id + 5000, start_id + 10000]
        
        for rollcall_id in sample_ids:
            url = f"{base_url}/?key={api_key}&op=getRollCall&id={rollcall_id}"
            
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if 'roll_call' in data:
                        rollcall = data['roll_call']
                        
                        # Check if this is federal data
                        if rollcall.get('chamber') in ['S', 'H']:  # Senate or House
                            date = rollcall.get('date', '')
                            if date and (date.startswith('20') or date.startswith('19')):  # Recent dates
                                federal_rollcalls.append({
                                    'id': rollcall_id,
                                    'chamber': rollcall.get('chamber'),
                                    'date': rollcall.get('date'),
                                    'desc': rollcall.get('desc', '')[:50],
                                    'total': rollcall.get('total'),
                                    'passed': rollcall.get('passed')
                                })
                                print(f"  Found federal roll call {rollcall_id}: {rollcall.get('chamber')} - {rollcall.get('date')} - {rollcall.get('desc', '')[:50]}")
                
            except Exception as e:
                continue
    
    print(f"\nFound {len(federal_rollcalls)} federal roll calls")
    return federal_rollcalls

def test_specific_federal_rollcalls():
    """Test some specific roll call IDs that might be federal."""
    api_key = "5360b7973d27c12c971a27ff32665137"
    base_url = "https://api.legiscan.com"
    
    # Test some roll call IDs that might be from recent Congresses
    test_ids = [
        123456,  # We know this one works
        123457, 123458, 123459, 123460,
        200000, 200001, 200002,
        300000, 300001, 300002,
        400000, 400001, 400002,
        500000, 500001, 500002,
        600000, 600001, 600002,
        700000, 700001, 700002,
        800000, 800001, 800002,
        900000, 900001, 900002,
    ]
    
    federal_rollcalls = []
    
    for rollcall_id in test_ids:
        url = f"{base_url}/?key={api_key}&op=getRollCall&id={rollcall_id}"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'roll_call' in data:
                    rollcall = data['roll_call']
                    
                    # Check if this is federal data
                    if rollcall.get('chamber') in ['S', 'H']:
                        date = rollcall.get('date', '')
                        if date and (date.startswith('20') or date.startswith('19')):
                            federal_rollcalls.append({
                                'id': rollcall_id,
                                'chamber': rollcall.get('chamber'),
                                'date': rollcall.get('date'),
                                'desc': rollcall.get('desc', '')[:50],
                                'total': rollcall.get('total'),
                                'passed': rollcall.get('passed')
                            })
                            print(f"Found federal roll call {rollcall_id}: {rollcall.get('chamber')} - {rollcall.get('date')} - {rollcall.get('desc', '')[:50]}")
        
        except Exception as e:
            continue
    
    return federal_rollcalls

if __name__ == "__main__":
    print("Finding Federal Roll Calls in LegiScan")
    
    # Test specific IDs first
    print("\nTesting specific roll call IDs...")
    federal_rollcalls = test_specific_federal_rollcalls()
    
    if federal_rollcalls:
        print(f"\nFound {len(federal_rollcalls)} federal roll calls in specific test")
        for rc in federal_rollcalls:
            print(f"  {rc['id']}: {rc['chamber']} - {rc['date']} - {rc['desc']}")
    
    # Then do systematic search
    print("\nDoing systematic search...")
    systematic_results = find_federal_rollcalls()
    
    print(f"\nTotal federal roll calls found: {len(federal_rollcalls) + len(systematic_results)}")
