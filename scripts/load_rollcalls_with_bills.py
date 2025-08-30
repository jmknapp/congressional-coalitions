#!/usr/bin/env python3
"""
Load House and Senate roll call votes with bill associations from Congress.gov API.

This script:
- Fetches roll calls from Congress.gov API
- Extracts bill information from vote details
- Links roll calls to bills in the database
- Updates existing roll calls with bill associations
"""

import os
import sys
import time
import datetime
import argparse
import requests
import logging
from typing import List, Dict, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote, Member, Bill

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Congress.gov API configuration
API_KEY = os.environ.get('CONGRESS_GOV_API_KEY', '')
BASE_URL = 'https://api.congress.gov/v3'
HEADERS = {'Accept': 'application/json'}

if not API_KEY:
    logger.error("CONGRESS_GOV_API_KEY environment variable not set")
    sys.exit(1)


def normalize_vote_code(code: Optional[str]) -> Optional[str]:
    """Normalize vote codes to standard format."""
    if not code:
        return None
    c = code.strip().lower()
    if c in ('yea', 'aye', 'yes', 'y'):
        return 'Yea'
    if c in ('nay', 'no', 'n'):
        return 'Nay'
    if c in ('present', 'present - announced'):
        return 'Present'
    return None


def parse_date(date_str: Optional[str]) -> datetime.date:
    """Parse date string to date object."""
    if not date_str:
        return datetime.date.today()
    date_str = date_str.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y'):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except Exception:
            continue
    return datetime.date.today()


def safe_int(value, default: int) -> int:
    """Safely convert value to integer."""
    try:
        return int(value)
    except Exception:
        return default


def extract_bill_info(vote_data: Dict) -> Optional[Dict]:
    """Extract bill information from vote data."""
    try:
        # Check for legislation fields (Congress.gov API format)
        legislation_type = vote_data.get('legislationType', '').strip().lower()
        legislation_number = vote_data.get('legislationNumber')
        
        if legislation_type and legislation_number and str(legislation_number).isdigit():
            congress = vote_data.get('congress', 119)
            bill_id = f"{legislation_type}-{int(legislation_number)}-{congress}"
            return {
                'bill_id': bill_id,
                'type': legislation_type.upper(),
                'number': int(legislation_number),
                'congress': congress,
                'title': f"{legislation_type.upper()} {legislation_number}",
                'chamber': 'house'  # Default to house for now
            }
        
        # Fallback: Check for bill information in various fields
        bill_info = vote_data.get('bill') or {}
        if not bill_info:
            # Check for bill in vote details
            vote_details = vote_data.get('voteDetails', {})
            bill_info = vote_details.get('bill') or {}
        
        if not bill_info:
            return None
            
        bill_type = bill_info.get('type', '').strip().lower()
        bill_number = bill_info.get('number')
        
        if bill_type and bill_number and str(bill_number).isdigit():
            congress = vote_data.get('congress', 119)
            bill_id = f"{bill_type}-{int(bill_number)}-{congress}"
            return {
                'bill_id': bill_id,
                'type': bill_type.upper(),
                'number': int(bill_number),
                'congress': congress,
                'title': bill_info.get('title', ''),
                'chamber': bill_info.get('originChamber', 'house')
            }
    except Exception as e:
        logger.warning(f"Error extracting bill info: {e}")
    
    return None


def fetch_house_vote(congress: int, session: int, roll_number: int) -> Optional[Dict]:
    """Fetch a single House vote from Congress.gov API."""
    url = f'{BASE_URL}/house-vote/{congress}/{session}/{roll_number}?api_key={API_KEY}&format=json'
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        
        data = response.json()
        vote_data = data.get('houseRollCallVote') or data.get('houseVote') or data.get('vote') or data
        
        if not vote_data:
            return None
            
        # Debug: Log the first few votes to see the structure
        if roll_number <= 5:
            logger.info(f"House vote {congress}-{session}-{roll_number} data keys: {list(vote_data.keys())}")
            if 'legislationType' in vote_data:
                logger.info(f"Legislation type: {vote_data['legislationType']}, number: {vote_data.get('legislationNumber')}")
            if 'bill' in vote_data:
                logger.info(f"Bill info: {vote_data['bill']}")
            if 'voteDetails' in vote_data:
                logger.info(f"Vote details: {vote_data['voteDetails']}")
            
        # Extract basic vote information
        roll_number = safe_int(
            vote_data.get('rollCallNumber') or vote_data.get('rollNumber') or roll_number,
            roll_number
        )
        
        question = (vote_data.get('voteQuestion') or vote_data.get('questionText') or '').strip()
        
        # Parse date
        start_date = vote_data.get('startDate') or vote_data.get('date')
        date_portion = (start_date or '').split('T', 1)[0] if start_date else None
        vote_date = parse_date(date_portion)
        
        # Extract bill information
        bill_info = extract_bill_info(vote_data)
        
        return {
            'rollcall_id': f'rc-{roll_number}-{congress}',
            'congress': congress,
            'chamber': 'house',
            'session': session,
            'rc_number': roll_number,
            'question': question,
            'date': vote_date,
            'bill_info': bill_info
        }
        
    except Exception as e:
        logger.warning(f"Error fetching House vote {congress}-{session}-{roll_number}: {e}")
        return None


def fetch_senate_vote(congress: int, session: int, roll_number: int) -> Optional[Dict]:
    """Fetch a single Senate vote from Congress.gov API."""
    url = f'{BASE_URL}/senate-vote/{congress}/{session}/{roll_number}?api_key={API_KEY}&format=json'
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        
        data = response.json()
        vote_data = data.get('senateRollCallVote') or data.get('senateVote') or data.get('vote') or data
        
        if not vote_data:
            return None
            
        # Debug: Log the first few Senate votes to see the structure
        if roll_number <= 5:
            logger.info(f"Senate vote {congress}-{session}-{roll_number} data keys: {list(vote_data.keys())}")
            if 'legislationType' in vote_data:
                logger.info(f"Senate legislation type: {vote_data['legislationType']}, number: {vote_data.get('legislationNumber')}")
            if 'bill' in vote_data:
                logger.info(f"Senate bill info: {vote_data['bill']}")
            if 'voteDetails' in vote_data:
                logger.info(f"Senate vote details: {vote_data['voteDetails']}")
            
        # Extract basic vote information
        roll_number = safe_int(
            vote_data.get('rollCallNumber') or vote_data.get('rollNumber') or roll_number,
            roll_number
        )
        
        question = (vote_data.get('voteQuestion') or vote_data.get('questionText') or '').strip()
        
        # Parse date
        start_date = vote_data.get('startDate') or vote_data.get('date')
        date_portion = (start_date or '').split('T', 1)[0] if start_date else None
        vote_date = parse_date(date_portion)
        
        # Extract bill information
        bill_info = extract_bill_info(vote_data)
        
        return {
            'rollcall_id': f'rc-{roll_number}-{congress}',
            'congress': congress,
            'chamber': 'senate',
            'session': session,
            'rc_number': roll_number,
            'question': question,
            'date': vote_date,
            'bill_info': bill_info
        }
        
    except Exception as e:
        logger.warning(f"Error fetching Senate vote {congress}-{session}-{roll_number}: {e}")
        return None


def update_rollcall_with_bill(session_db, rollcall_id: str, bill_info: Dict) -> bool:
    """Update an existing rollcall with bill information."""
    try:
        # Find the rollcall
        rollcall = session_db.query(Rollcall).filter(Rollcall.rollcall_id == rollcall_id).first()
        if not rollcall:
            logger.warning(f"Rollcall {rollcall_id} not found")
            return False
        
        # Check if bill exists, create if not
        bill = session_db.query(Bill).filter(Bill.bill_id == bill_info['bill_id']).first()
        if not bill:
            # Create placeholder bill
            bill = Bill(
                bill_id=bill_info['bill_id'],
                congress=bill_info['congress'],
                chamber=bill_info['chamber'],
                type=bill_info['type'],
                number=bill_info['number'],
                title=bill_info['title'] or f"{bill_info['type']} {bill_info['number']}",
                sponsor_bioguide=None,  # Will need to be updated later
                introduced_date=None
            )
            session_db.add(bill)
            logger.info(f"Created placeholder bill {bill_info['bill_id']}")
        
        # Update rollcall with bill_id
        rollcall.bill_id = bill_info['bill_id']
        session_db.commit()
        
        logger.info(f"Updated rollcall {rollcall_id} with bill {bill_info['bill_id']}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating rollcall {rollcall_id}: {e}")
        session_db.rollback()
        return False


def load_congress_rollcalls(congress: int, max_roll: int = 200, sleep_sec: float = 0.2) -> None:
    """Load roll calls for a Congress with bill associations."""
    logger.info(f"Loading roll calls for Congress {congress} with bill associations...")
    
    total_updated = 0
    total_bills_created = 0
    
    with get_db_session() as session_db:
        for session_num in (1, 2):
            logger.info(f"Processing session {session_num}...")
            
            for roll_number in range(1, max_roll + 1):
                # Try House vote
                house_vote = fetch_house_vote(congress, session_num, roll_number)
                if house_vote and house_vote.get('bill_info'):
                    if update_rollcall_with_bill(session_db, house_vote['rollcall_id'], house_vote['bill_info']):
                        total_updated += 1
                        total_bills_created += 1
                
                # Try Senate vote
                senate_vote = fetch_senate_vote(congress, session_num, roll_number)
                if senate_vote and senate_vote.get('bill_info'):
                    if update_rollcall_with_bill(session_db, senate_vote['rollcall_id'], senate_vote['bill_info']):
                        total_updated += 1
                        total_bills_created += 1
                
                time.sleep(sleep_sec)
    
    logger.info(f"Completed: Updated {total_updated} roll calls with bill associations")
    logger.info(f"Created {total_bills_created} placeholder bills")


def main():
    parser = argparse.ArgumentParser(description='Load roll calls with bill associations from Congress.gov API')
    parser.add_argument('--congress', type=int, required=True, help='Congress number (e.g., 119)')
    parser.add_argument('--max-roll', type=int, default=200, help='Maximum roll number to check per session')
    parser.add_argument('--sleep', type=float, default=0.2, help='Sleep time between API calls (seconds)')
    
    args = parser.parse_args()
    
    if not API_KEY:
        logger.error("CONGRESS_GOV_API_KEY environment variable not set")
        sys.exit(1)
    
    load_congress_rollcalls(args.congress, max_roll=args.max_roll, sleep_sec=args.sleep)


if __name__ == '__main__':
    main()
