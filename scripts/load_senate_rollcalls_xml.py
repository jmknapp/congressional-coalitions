#!/usr/bin/env python3
import sys, requests, datetime, re
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote
import xml.etree.ElementTree as ET

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

def load_vote_xml(url):
    """Load a single Senate vote from proper XML format."""
    try:
        r=requests.get(url,timeout=60); r.raise_for_status()
        content = r.content
        content_str = content.decode('utf-8', errors='ignore')
        
        # Parse the XML
        root = ET.fromstring(content_str)
        
        def get(p):
            n=root.find(p); return (n.text or '').strip() if n is not None and n.text else ''
        
        # Extract vote information from proper XML structure
        num = int(get('.//vote_number') or '0')
        if not num: 
            print(f"Could not extract vote number from {url}")
            return
        
        rc_id = f'rc-{num}-119'
        
        # Get question and document text
        question_text = get('.//vote_question_text')
        document_text = get('.//vote_document_text')
        vote_title = get('.//vote_title')
        
        # Combine question components
        q = question_text or vote_title or 'Senate Vote'
        if document_text:
            q = f"{q}: {document_text}"
        
        # Parse date
        dt = get('.//vote_date')
        rc_date = None
        if dt:
            try:
                # Parse date like "August 2, 2025, 09:40 PM"
                date_part = dt.split(',')[0] + ', ' + dt.split(',')[1]
                rc_date = datetime.datetime.strptime(date_part, '%B %d, %Y').date()
            except:
                pass
        
        # Extract bill/nomination information
        bill_id = None
        doc_type = get('.//document/document_type')
        doc_number = get('.//document/document_number')
        if doc_type and doc_number:
            # Handle nominations (PN) and bills
            if doc_type == 'PN':
                bill_id = f"pn-{doc_number}-119"
            else:
                bill_id = f"{doc_type.lower()}-{doc_number}-119"
        
        # Parse member votes - look for member elements
        members = []
        for member_elem in root.findall('.//member'):
            bioguide_id = member_elem.findtext('bioguide_id') or member_elem.findtext('member_id')
            vote_position = member_elem.findtext('vote_cast') or member_elem.findtext('vote_position')
            
            if bioguide_id and vote_position:
                normalized_vote = norm(vote_position)
                if normalized_vote:
                    members.append((bioguide_id.strip(), normalized_vote))
        
        # Save to database
        with get_db_session() as s:
            if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
                sess = 1 if 'vote1191' in url else 2
                s.add(Rollcall(
                    rollcall_id=rc_id,
                    congress=119,
                    chamber='senate',
                    session=sess,
                    rc_number=num,
                    question=q,
                    bill_id=bill_id,
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
    """Load Senate roll calls from proper XML format."""
    print("Loading Senate roll calls from XML format...")
    
    # Load session 1 (which we know has data)
    print("Loading session 1...")
    urls = load_menu(1)
    print(f"Found {len(urls)} Senate roll calls for session 1")
    
    # Load first 10 votes as a test
    for i, url in enumerate(urls[:10]):
        print(f"Loading vote {i+1}/10: {url}")
        load_vote_xml(url)
    
    print("Completed loading Senate roll calls")

if __name__ == "__main__":
    main()

