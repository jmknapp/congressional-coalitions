#!/usr/bin/env python3
import sys, requests, xml.etree.ElementTree as ET, datetime, re
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

def load_menu_118(sess):
    """Load Senate menu for 118th Congress."""
    url=f'https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_118_{sess}.xml'
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
                # Construct the vote URL manually
                vote_url = f'https://www.senate.gov/legislative/LIS/roll_call_votes/vote118_{sess}/vote_118_{sess}_{vote_num.zfill(5)}.xml'
                vote_numbers.append(vote_url)
        
        print(f"Found {len(vote_numbers)} Senate votes via XML parsing")
        return vote_numbers
        
    except Exception as e:
        print(f"Error fetching Senate menu: {e}")
        return []

def load_vote_118(url):
    """Load a single Senate vote from 118th Congress."""
    try:
        r=requests.get(url,timeout=60); r.raise_for_status()
        content = r.content
        content_str = content.decode('utf-8', errors='ignore')
        
        # Try to parse the XML
        try:
            root=ET.fromstring(content_str)
        except ET.ParseError as e:
            print(f"XML parse error for {url}: {e}")
            return
        
        def get(p):
            n=root.find(p); return (n.text or '').strip() if n is not None and n.text else ''
        
        num=int(get('.//vote_number') or get('.//vote-number') or '0')
        if not num: return
        
        # Create rollcall ID for 118th Congress
        rc_id=f'rc-{num}-118'
        q=get('.//question') or get('.//vote_question_text')
        dt=get('.//vote_date') or get('.//date')
        
        rc_date=None
        for fmt in ('%B %d, %Y','%Y-%m-%d'):
            try: rc_date=datetime.datetime.strptime(dt,fmt).date(); break
            except: pass
        
        bill_id=None
        btype=(get('.//bill/type') or '').lower()
        bnum=(get('.//bill/number') or '')
        if btype and bnum.isdigit(): bill_id=f'{btype}-{int(bnum)}-118'
        
        members=[]
        # handle both member list shapes
        for m in root.iter():
            tag=m.tag.lower()
            if tag.endswith('member'):
                bid=(m.findtext('bioguide_id') or m.findtext('member_id') or '').strip()
                v=norm(m.findtext('vote_cast') or m.findtext('vote_position') or m.findtext('value'))
                if bid and v: members.append((bid,v))
        
        with get_db_session() as s:
            if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
                sess = 1 if 'vote118_1' in url else 2
                s.add(Rollcall(rollcall_id=rc_id, congress=118, chamber='senate',
                               session=sess, rc_number=num, question=q, bill_id=bill_id, date=rc_date))
                s.flush()
            
            for bid,v in members:
                if not s.query(Vote).filter(Vote.rollcall_id==rc_id, Vote.member_id_bioguide==bid).first():
                    s.add(Vote(rollcall_id=rc_id, member_id_bioguide=bid, vote_code=v))
            s.commit()
            print(f"Successfully loaded vote {rc_id} with {len(members)} member votes")
            
    except Exception as e:
        print(f"Error loading {url}: {e}")

def main():
    """Load Senate roll calls from 118th Congress."""
    print("Loading Senate roll calls from 118th Congress...")
    
    # Load session 2 (which we know has data)
    print("Loading session 2...")
    votes = load_menu_118(2)
    print(f"Found {len(votes)} Senate roll calls for session 2")
    
    # Load first 10 votes as a test
    for i, vote_url in enumerate(votes[:10]):
        print(f"Loading vote {i+1}/10: {vote_url}")
        load_vote_118(vote_url)
    
    print("Completed loading Senate roll calls from 118th Congress")

if __name__ == "__main__":
    main()
