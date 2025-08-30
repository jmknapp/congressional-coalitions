#!/usr/bin/env python3
import sys, requests, xml.etree.ElementTree as ET, datetime, re
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote

def clean_xml_content(content_str):
    """Clean XML content to fix common issues."""
    # Remove null bytes and other problematic characters
    content_str = content_str.replace('\x00', '')
    
    # Remove any characters that aren't valid in XML
    content_str = re.sub(r'[^\x09\x0A\x0D\x20-\x7E\x85\xA0-\xFF]', '', content_str)
    
    # Fix common XML issues
    content_str = re.sub(r'&(?![a-zA-Z]+;)', '&amp;', content_str)
    
    # Remove JavaScript code that's embedded in XML (common in Senate.gov files)
    # Look for script tags and remove their content
    content_str = re.sub(r'<script[^>]*>.*?</script>', '', content_str, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove any standalone JavaScript code blocks
    content_str = re.sub(r'for\s*\([^)]*\)\s*\{[^}]*\}', '', content_str)
    
    # Remove any lines that look like JavaScript
    lines = content_str.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip lines that look like JavaScript
        if re.search(r'eval\s*\(|\.location\s*=|for\s*\([^)]*\)', line):
            continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def extract_xml_from_html(content_str):
    """Extract XML content from HTML page."""
    # Look for XML content within the HTML
    # Try to find the main XML content
    xml_patterns = [
        r'<vote_summary>.*?</vote_summary>',
        r'<roll_call_vote>.*?</roll_call_vote>',
        r'<vote>.*?</vote>'
    ]
    
    for pattern in xml_patterns:
        match = re.search(pattern, content_str, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(0)
    
    # If no XML found, return the original content
    return content_str

def debug_content(content_str, url):
    """Debug function to see what content we're getting."""
    print(f"Content preview for {url}:")
    print(f"First 500 chars: {content_str[:500]}")
    print(f"Contains 'vote_summary': {'vote_summary' in content_str}")
    print(f"Contains 'vote_number': {'vote_number' in content_str}")
    print(f"Contains '<html': {'<html' in content_str.lower()}")
    print("---")

def norm(c):
    c=(c or '').strip().lower()
    if c in ('yea','aye','yes','y'): return 'Yea'
    if c in ('nay','no','n'): return 'Nay'
    if c in ('present','present - announced'): return 'Present'
    return None

def load_menu(sess):
    url=f'https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_119_{sess}.xml'
    print(f"Fetching Senate menu from: {url}")
    try:
        r=requests.get(url,timeout=60); r.raise_for_status()
        text=r.text
        print(f"Got response, length: {len(text)}")
        
        # Check if it's HTML instead of XML
        if text.strip().startswith('<!DOCTYPE html'):
            print(f"Session {sess} returned HTML instead of XML")
            return []
        
        # Try XML parsing
        try:
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
            print(f"XML parsing failed: {e}")
            return []
            
    except Exception as e:
        print(f"Error fetching Senate menu: {e}")
        return []

def load_vote(url):
    try:
        r=requests.get(url,timeout=60); r.raise_for_status()
        content = r.content
        
        # Try to fix common XML issues
        content_str = content.decode('utf-8', errors='ignore')
        
        # Debug the content for the first few votes
        if '00499' in url or '00498' in url:
            debug_content(content_str, url)
        
        # Extract XML from HTML if needed
        content_str = extract_xml_from_html(content_str)
        
        # Clean the XML content
        content_str = clean_xml_content(content_str)
        
        # Try to parse the XML
        try:
            root=ET.fromstring(content_str)
        except ET.ParseError as e:
            print(f"XML parse error for {url}: {e}")
            
            # Debug: Let's see what's around line 34
            lines = content_str.split('\n')
            if len(lines) >= 34:
                print(f"Line 34 content: {repr(lines[33])}")
                if len(lines) >= 35:
                    print(f"Line 35 content: {repr(lines[34])}")
            
            # Try to extract basic info from the content
            if 'vote_number' in content_str:
                # Extract vote number using regex as fallback
                import re
                vote_match = re.search(r'<vote_number>(\d+)</vote_number>', content_str)
                if vote_match:
                    num = int(vote_match.group(1))
                    rc_id = f'rc-{num}-119'
                    print(f"Extracted vote number {num} from malformed XML")
                    
                    # Create basic rollcall record without detailed parsing
                    with get_db_session() as s:
                        if not s.query(Rollcall).filter(Rollcall.rollcall_id==rc_id).first():
                            sess = 1 if 'vote119_1' in url else 2
                            s.add(Rollcall(rollcall_id=rc_id, congress=119, chamber='senate',
                                           session=sess, rc_number=num, question='Senate Vote', bill_id=None, date=None))
                            s.commit()
                            print(f"Created basic rollcall record for {rc_id}")
            return
        
        def get(p):
            n=root.find(p); return (n.text or '').strip() if n is not None and n.text else ''
        num=int(get('.//vote_number') or get('.//vote-number') or '0')
        if not num: return
        rc_id=f'rc-{num}-119'
        q=get('.//question') or get('.//vote_question_text')
        dt=get('.//vote_date') or get('.//date')
        rc_date=None
        for fmt in ('%B %d, %Y','%Y-%m-%d'):
            try: rc_date=datetime.datetime.strptime(dt,fmt).date(); break
            except: pass
        bill_id=None
        btype=(get('.//bill/type') or '').lower()
        bnum=(get('.//bill/number') or '')
        if btype and bnum.isdigit(): bill_id=f'{btype}-{int(bnum)}-119'
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
                sess = 1 if 'vote119_1' in url else 2
                s.add(Rollcall(rollcall_id=rc_id, congress=119, chamber='senate',
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
    for sess in (1,2):
        print(f"Loading session {sess}...")
        urls=load_menu(sess)
        print(f"Found {len(urls)} Senate roll calls for session {sess}")
        for u in urls:
            try: 
                load_vote(u)
                print(f"Loaded vote from {u}")
            except Exception as e: 
                print(f"Error loading {u}: {e}")
                continue

if __name__ == '__main__':
    main()
