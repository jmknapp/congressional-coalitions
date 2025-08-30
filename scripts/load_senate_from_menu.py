#!/usr/bin/env python3
import sys, requests, xml.etree.ElementTree as ET, datetime, re
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.database import get_db_session
from scripts.setup_db import Rollcall

def parse_date(date_str):
    """Parse Senate date format like '02-Aug' or '21-Dec'."""
    if not date_str:
        return None
    
    try:
        # Senate format: "02-Aug" or "21-Dec"
        # We'll assume 2024 for 118th Congress, 2025 for 119th Congress
        if '119' in date_str:  # 119th Congress
            year = 2025
        else:  # 118th Congress
            year = 2024
            
        # Parse the date
        date_obj = datetime.datetime.strptime(f"{date_str}-{year}", "%d-%b-%Y")
        return date_obj.date()
    except:
        return None

def load_senate_from_menu(congress, session):
    """Load Senate roll calls from menu data only."""
    url = f'https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{congress}_{session}.xml'
    print(f"Fetching Senate menu from: {url}")
    
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        text = r.text
        print(f"Got response, length: {len(text)}")
        
        # Check if it's HTML instead of XML
        if text.strip().startswith('<!DOCTYPE html'):
            print(f"Session {session} returned HTML instead of XML")
            return 0
        
        # Parse XML
        root = ET.fromstring(text)
        votes_loaded = 0
        
        # Process each vote in the menu
        for vote_elem in root.findall('.//vote'):
            try:
                # Extract vote information from menu
                vote_num_elem = vote_elem.find('vote_number')
                vote_date_elem = vote_elem.find('vote_date')
                issue_elem = vote_elem.find('issue')
                question_elem = vote_elem.find('question')
                result_elem = vote_elem.find('result')
                title_elem = vote_elem.find('title')
                
                if not vote_num_elem or not vote_num_elem.text:
                    continue
                
                vote_num = vote_num_elem.text.strip()
                vote_date = vote_date_elem.text.strip() if vote_date_elem and vote_date_elem.text else None
                issue = issue_elem.text.strip() if issue_elem and issue_elem.text else None
                question = question_elem.text.strip() if question_elem and question_elem.text else None
                result = result_elem.text.strip() if result_elem and result_elem.text else None
                title = title_elem.text.strip() if title_elem and title_elem.text else None
                
                # Create rollcall ID
                rc_id = f'rc-{vote_num}-{congress}'
                
                # Parse date
                rc_date = parse_date(vote_date)
                
                # Extract bill information from issue field
                bill_id = None
                if issue and issue.startswith(('H.R.', 'S.', 'H.J.Res.', 'S.J.Res.', 'H.Con.Res.', 'S.Con.Res.')):
                    # Parse bill reference like "H.R. 10545" or "S. 1234"
                    parts = issue.split()
                    if len(parts) >= 2:
                        bill_type = parts[0].lower().replace('.', '')
                        bill_number = parts[1]
                        if bill_number.isdigit():
                            bill_id = f'{bill_type}-{bill_number}-{congress}'
                
                # Create question text
                question_text = question or title or f"Senate Vote {vote_num}"
                if issue:
                    question_text = f"{issue}: {question_text}"
                
                # Save to database
                with get_db_session() as s:
                    if not s.query(Rollcall).filter(Rollcall.rollcall_id == rc_id).first():
                        s.add(Rollcall(
                            rollcall_id=rc_id,
                            congress=congress,
                            chamber='senate',
                            session=session,
                            rc_number=int(vote_num),
                            question=question_text,
                            bill_id=bill_id,
                            date=rc_date
                        ))
                        s.commit()
                        votes_loaded += 1
                        print(f"Created rollcall {rc_id}: {question_text[:50]}...")
                
            except Exception as e:
                print(f"Error processing vote {vote_num}: {e}")
                continue
        
        print(f"Successfully loaded {votes_loaded} Senate roll calls from menu")
        return votes_loaded
        
    except Exception as e:
        print(f"Error fetching Senate menu: {e}")
        return 0

def main():
    """Load Senate roll calls from menu data for both 118th and 119th Congress."""
    print("Loading Senate roll calls from menu data...")
    
    total_loaded = 0
    
    # Try 118th Congress, Session 2 (we know this has data)
    print("\nLoading 118th Congress, Session 2...")
    loaded_118_2 = load_senate_from_menu(118, 2)
    total_loaded += loaded_118_2
    
    # Try 119th Congress, Session 1 (we know this has data)
    print("\nLoading 119th Congress, Session 1...")
    loaded_119_1 = load_senate_from_menu(119, 1)
    total_loaded += loaded_119_1
    
    print(f"\nTotal Senate roll calls loaded: {total_loaded}")
    print("Note: These roll calls do not include individual member votes due to XML parsing issues.")

if __name__ == "__main__":
    main()
