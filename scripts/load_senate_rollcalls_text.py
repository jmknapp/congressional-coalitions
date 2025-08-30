#!/usr/bin/env python3
import sys, requests, datetime, re
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote

def norm(c):
    c=(c or '').strip().lower()
    if c in ('yea','aye','yes','y'): return 'Yea'
    if c in ('nay','no','n'): return 'Nay'
    if c in ('present','present - announced'): return 'Present'
    if c in ('not voting', 'not voting'): return 'Not Voting'
    return None

def load_menu(sess):
    """Load Senate menu for 119th Congress."""
    url=f'https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_{sess}.xml'
    print(f"Fetching Senate menu from: {url}")
    try:
        r=requests.get(url,timeout=60); r.raise_for_status()
        text=r.text
        print(f"Got response, length: {len(text)}")
        
        # Parse XML
        import xml.etree.ElementTree as ET
        root=ET.fromstring(text)
        vote_numbers = []
        
        # Look for vote_number elements
        for vote_elem in root.findall('.//vote'):
            vote_num_elem = vote_elem.find('vote_number')
            if vote_num_elem is not None and vote_num_elem.text:
                vote_num = vote_num_elem.text.strip()
                # Construct the vote URL manually - correct format is vote1191 (no underscore)
                vote_url = f'https://www.senate.gov/legislative/LIS/roll_call_votes/vote119{sess}/vote_119_{sess}_{vote_num.zfill(5)}.xml'
                vote_numbers.append(vote_url)
        
        print(f"Found {len(vote_numbers)} Senate votes via XML parsing")
        return vote_numbers
        
    except Exception as e:
        print(f"Error fetching Senate menu: {e}")
        return []

def load_vote_text(url):
    """Load a single Senate vote from plain text format."""
    try:
        r=requests.get(url,timeout=60); r.raise_for_status()
        content = r.content
        content_str = content.decode('utf-8', errors='ignore')
        
        # Parse the plain text content
        lines = content_str.split('\n')
        
        # Extract vote information
        vote_info = {}
        members = []
        vote_num = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Extract vote number from first line
            if not vote_num and re.match(r'^\d+\s+\d+\s+\d+\s+\d+', line):
                parts = line.split()
                if len(parts) >= 4:
                    vote_num = int(parts[3])  # 4th field is vote number
                    
            # Parse vote header info
            if 'On the Nomination' in line or 'On Passage' in line or 'On Motion' in line:
                vote_info['question'] = line
            elif 'Confirmed' in line or 'Passed' in line or 'Rejected' in line:
                vote_info['result'] = line
            elif 'August' in line or 'September' in line or 'October' in line or 'November' in line or 'December' in line:
                try:
                    # Parse date like "August 2, 2025, 09:40 PM"
                    date_part = line.split(',')[0] + ', ' + line.split(',')[1]
                    vote_info['date'] = datetime.datetime.strptime(date_part, '%B %d, %Y').date()
                except:
                    pass
            
            # Parse member votes - look for lines with Bioguide IDs
            # Format: "Alsobrooks (D-MD) Alsobrooks Angela D MD Yea S428"
            if '(' in line and ')' in line and any(vote in line for vote in ['Yea', 'Nay', 'Not Voting']):
                parts = line.split()
                if len(parts) >= 6:
                    # Extract Bioguide ID (last part)
                    bioguide_id = parts[-1]
                    # Extract vote position
                    vote_position = None
                    for vote in ['Yea', 'Nay', 'Not Voting']:
                        if vote in line:
                            vote_position = vote
                            break
                    
                    if bioguide_id and vote_position:
                        normalized_vote = norm(vote_position)
                        if normalized_vote:
                            members.append((bioguide_id, normalized_vote))
        
        if not vote_num:
            print(f"Could not extract vote number from {url}")
            return
        
        # Create rollcall ID
        rc_id = f'rc-{vote_num}-119'
        
        # Get question and other info
        q = vote_info.get('question', 'Senate Vote')
        result = vote_info.get('result', '')
        if result:
            q = f"{q} - {result}"
        
        rc_date = vote_info.get('date')
        
        # Save to database
        with get_db_session() as s:
            if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
                sess = 1 if 'vote1191' in url else 2
                s.add(Rollcall(
                    rollcall_id=rc_id,
                    congress=119,
                    chamber='senate',
                    session=sess,
                    rc_number=vote_num,
                    question=q,
                    bill_id=None,  # We'll need to extract this from question text
                    date=rc_date
                ))
                s.flush()
            
            for bid, v in members:
                if not s.query(Vote).filter(Vote.rollcall_id==rc_id, Vote.member_id_bioguide==bid).first():
                    s.add(Vote(rollcall_id=rc_id, member_id_bioguide=bid, vote_code=v))
            
            s.commit()
            print(f"Successfully loaded vote {rc_id} with {len(members)} member votes")
            
    except Exception as e:
        print(f"Error loading {url}: {e}")

def main():
    """Load Senate roll calls from plain text format."""
    print("Loading Senate roll calls from plain text format...")
    
    # Load session 1 (which we know has data)
    print("Loading session 1...")
    urls = load_menu(1)
    print(f"Found {len(urls)} Senate roll calls for session 1")
    
    # Load first 10 votes as a test
    for i, url in enumerate(urls[:10]):
        print(f"Loading vote {i+1}/10: {url}")
        load_vote_text(url)
    
    print("Completed loading Senate roll calls")

if __name__ == "__main__":
    main()


