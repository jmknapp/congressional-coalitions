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

def fetch_legiscan_rollcalls(api_key, congress=119):
    """Fetch roll call votes from LegiScan API."""
    base_url = "https://api.legiscan.com"
    
    # Get master list for the Congress
    url = f"{base_url}/?key={api_key}&op=getMasterList&id={congress}"
    
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if 'result' in data and 'rollcalls' in data['result']:
            return data['result']['rollcalls']
        else:
            print(f"No rollcalls found in response: {data}")
            return []
            
    except Exception as e:
        print(f"Error fetching LegiScan rollcalls: {e}")
        return []

def fetch_rollcall_details(api_key, rollcall_id):
    """Fetch detailed roll call information from LegiScan."""
    base_url = "https://api.legiscan.com"
    url = f"{base_url}/?key={api_key}&op=getRollCall&id={rollcall_id}"
    
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching rollcall details: {e}")
        return None

def load_legiscan_rollcall(rollcall_data, congress=119):
    """Load a single roll call from LegiScan into the database."""
    try:
        # Extract basic roll call information
        rollcall_id = rollcall_data.get('roll_call_id')
        question = rollcall_data.get('question', '')
        date = rollcall_data.get('date')
        bill_id = rollcall_data.get('bill_id')
        
        # Parse date
        rc_date = None
        if date:
            try:
                rc_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
            except:
                pass
        
        # Create our rollcall ID
        rc_id = f'rc-{rollcall_id}-{congress}'
        
        # Get member votes
        members = []
        if 'votes' in rollcall_data:
            for vote in rollcall_data['votes']:
                member_id = vote.get('people_id')
                vote_position = vote.get('vote_text')
                if member_id and vote_position:
                    normalized_vote = norm(vote_position)
                    if normalized_vote:
                        members.append((member_id, normalized_vote))
        
        # Save to database
        with get_db_session() as s:
            if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
                s.add(Rollcall(
                    rollcall_id=rc_id,
                    congress=congress,
                    chamber='senate',  # LegiScan might have both chambers
                    session=1,  # Default to session 1
                    rc_number=rollcall_id,
                    question=question,
                    bill_id=bill_id,
                    date=rc_date
                ))
                s.flush()
            
            for member_id, vote_code in members:
                if not s.query(Vote).filter(Vote.rollcall_id==rc_id, Vote.member_id_bioguide==member_id).first():
                    s.add(Vote(rollcall_id=rc_id, member_id_bioguide=member_id, vote_code=vote_code))
            
            s.commit()
            print(f"Loaded rollcall {rc_id} with {len(members)} member votes")
            
    except Exception as e:
        print(f"Error loading rollcall: {e}")

def main():
    """Load Senate roll calls from LegiScan API."""
    print("Loading Senate roll calls from LegiScan API...")
    
    # You need to get an API key from: https://legiscan.com/legiscan
    api_key = "5360b7973d27c12c971a27ff32665137"  # Your API key
    
    congress = 119
    
    # Fetch roll calls
    rollcalls = fetch_legiscan_rollcalls(api_key, congress)
    
    if not rollcalls:
        print("No roll calls found or API key is invalid")
        return
    
    print(f"Found {len(rollcalls)} roll calls")
    
    # Load first 10 roll calls as a test
    for i, rollcall in enumerate(rollcalls[:10]):
        print(f"Loading rollcall {i+1}/10: {rollcall.get('roll_call_id')}")
        
        # Get detailed roll call information
        details = fetch_rollcall_details(api_key, rollcall['roll_call_id'])
        if details and 'result' in details:
            load_legiscan_rollcall(details['result'], congress)
    
    print("Completed loading roll calls from LegiScan")

if __name__ == "__main__":
    main()
