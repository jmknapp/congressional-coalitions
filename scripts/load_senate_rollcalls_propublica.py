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

def fetch_senate_votes(congress, session):
    """Fetch Senate roll call votes from ProPublica Congress API."""
    # ProPublica Congress API endpoint for Senate votes
    url = f"https://api.propublica.org/congress/v1/{congress}/senate/sessions/{session}/votes.json"
    
    # Note: ProPublica API requires an API key
    # You would need to get one from https://www.propublica.org/datastore/api/propublica-congress-api
    headers = {
        'X-API-Key': 'YOUR_API_KEY_HERE'  # Replace with actual API key
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Senate votes from ProPublica: {e}")
        return None

def load_senate_vote(vote_data):
    """Load a single Senate vote into the database."""
    try:
        # Extract vote information
        vote_id = vote_data.get('vote_id')
        roll_call = vote_data.get('roll_call')
        question = vote_data.get('question', '')
        description = vote_data.get('description', '')
        date = vote_data.get('date')
        
        # Parse date
        rc_date = None
        if date:
            try:
                rc_date = datetime.datetime.strptime(date, '%Y-%m-%d').date()
            except:
                pass
        
        # Create rollcall ID
        rc_id = f'rc-{roll_call}-119'
        
        # Extract bill information if available
        bill_id = None
        if 'bill' in vote_data and vote_data['bill']:
            bill = vote_data['bill']
            bill_type = bill.get('bill_type', '').lower()
            bill_number = bill.get('number')
            if bill_type and bill_number:
                bill_id = f'{bill_type}-{bill_number}-119'
        
        # Get member votes
        members = []
        if 'positions' in vote_data:
            for position in vote_data['positions']:
                member_id = position.get('member_id')
                vote_position = position.get('vote_position')
                if member_id and vote_position:
                    normalized_vote = norm(vote_position)
                    if normalized_vote:
                        members.append((member_id, normalized_vote))
        
        # Save to database
        with get_db_session() as s:
            if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
                s.add(Rollcall(
                    rollcall_id=rc_id, 
                    congress=119, 
                    chamber='senate',
                    session=1,  # Default to session 1
                    rc_number=roll_call, 
                    question=question or description, 
                    bill_id=bill_id, 
                    date=rc_date
                ))
                s.flush()
            
            for member_id, vote_code in members:
                if not s.query(Vote).filter(Vote.rollcall_id==rc_id, Vote.member_id_bioguide==member_id).first():
                    s.add(Vote(rollcall_id=rc_id, member_id_bioguide=member_id, vote_code=vote_code))
            
            s.commit()
            print(f"Loaded Senate vote {rc_id} with {len(members)} member votes")
            
    except Exception as e:
        print(f"Error loading Senate vote: {e}")

def main():
    """Main function to load Senate roll calls."""
    print("Loading Senate roll calls from ProPublica Congress API...")
    
    # Note: This requires a ProPublica API key
    # You can get one from: https://www.propublica.org/datastore/api/propublica-congress-api
    
    congress = 119
    session = 1
    
    # Fetch Senate votes
    votes_data = fetch_senate_votes(congress, session)
    
    if not votes_data:
        print("Failed to fetch Senate votes. You may need to:")
        print("1. Get a ProPublica API key from https://www.propublica.org/datastore/api/propublica-congress-api")
        print("2. Replace 'YOUR_API_KEY_HERE' in the script with your actual API key")
        return
    
    # Process votes
    votes = votes_data.get('results', {}).get('votes', [])
    print(f"Found {len(votes)} Senate votes")
    
    for vote in votes:
        load_senate_vote(vote)
    
    print("Completed loading Senate roll calls")

if __name__ == "__main__":
    main()
