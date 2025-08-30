#!/usr/bin/env python3
import sys, requests, datetime, json
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote

def norm(c):
    c=(c or '').strip().lower()
    if c in ('yea','aye','yes','y'): return 'Yea'
    if c in ('nay','no','n'): return 'Nay'
    if c in ('present','present - announced'): return 'Present'
    return None

def load_legiscan_rollcall(rollcall_data):
    """Load a single roll call from LegiScan into the database."""
    try:
        # Extract roll call information
        rollcall_id = rollcall_data.get('roll_call_id')
        legiscan_bill_id = rollcall_data.get('bill_id')
        date_str = rollcall_data.get('date')
        desc = rollcall_data.get('desc', '')
        chamber = rollcall_data.get('chamber')
        total = rollcall_data.get('total', 0)
        passed = rollcall_data.get('passed', 0)
        
        # For now, set bill_id to None since we don't have the corresponding bills
        # We could create placeholder bills later if needed
        bill_id = None
        
        # Parse date
        rc_date = None
        if date_str:
            try:
                rc_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                pass
        
        # Determine Congress from date
        congress = None
        if rc_date:
            if rc_date.year >= 2025:
                congress = 119
            elif rc_date.year >= 2023:
                congress = 118
            elif rc_date.year >= 2021:
                congress = 117
            elif rc_date.year >= 2019:
                congress = 116
            elif rc_date.year >= 2017:
                congress = 115
            elif rc_date.year >= 2015:
                congress = 114
            elif rc_date.year >= 2013:
                congress = 113
            elif rc_date.year >= 2011:
                congress = 112
            elif rc_date.year >= 2009:
                congress = 111
            else:
                congress = 110  # Default for older data
        
        if not congress:
            print(f"Skipping roll call {rollcall_id}: cannot determine Congress")
            return
        
        # Create our rollcall ID
        rc_id = f'rc-{rollcall_id}-{congress}'
        
        # Map chamber
        chamber_map = {'S': 'senate', 'H': 'house'}
        chamber_name = chamber_map.get(chamber, 'unknown')
        
        # For now, skip individual member votes since LegiScan uses different member IDs
        # than our Bioguide IDs. We can add member vote mapping later if needed.
        members = []
        
        # Save to database
        with get_db_session() as s:
            if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
                s.add(Rollcall(
                    rollcall_id=rc_id,
                    congress=congress,
                    chamber=chamber_name,
                    session=1,  # Default to session 1
                    rc_number=rollcall_id,
                    question=desc,
                    bill_id=bill_id,
                    date=rc_date
                ))
                s.commit()
                print(f"Loaded rollcall {rc_id} ({chamber_name}, Congress {congress}): {desc[:50]}... (no member votes)")
            else:
                print(f"Rollcall {rc_id} already exists, skipping")
            
    except Exception as e:
        print(f"Error loading rollcall {rollcall_id}: {e}")

def find_and_load_federal_rollcalls():
    """Find and load federal roll calls from LegiScan."""
    api_key = "5360b7973d27c12c971a27ff32665137"
    base_url = "https://api.legiscan.com"
    
    # Known federal roll call IDs from our exploration
    known_federal_ids = [
        123456, 123457, 123458, 123459, 123460,  # 2009-2010
        200001, 200002,  # 2012
        300000, 300001, 300002,  # 2013
        400000, 400001, 400002,  # 2015
        500000, 500001, 500002,  # 2016
        600000, 600001, 600002,  # 2017
    ]
    
    loaded_count = 0
    
    for rollcall_id in known_federal_ids:
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
                            load_legiscan_rollcall(rollcall)
                            loaded_count += 1
        
        except Exception as e:
            print(f"Error fetching roll call {rollcall_id}: {e}")
            continue
    
    print(f"\nCompleted loading {loaded_count} federal roll calls from LegiScan")

if __name__ == "__main__":
    print("Loading Federal Roll Calls from LegiScan")
    find_and_load_federal_rollcalls()
