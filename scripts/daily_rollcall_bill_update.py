#!/usr/bin/env python3
"""
Daily update script for roll calls, votes, and bill metadata.
This script fetches the latest voting data and bill information to keep the database current.

Usage:
    python3 scripts/daily_rollcall_bill_update.py [--congress CONGRESS] [--chamber CHAMBER] [--days-back DAYS]

Example:
    python3 scripts/daily_rollcall_bill_update.py --congress 119 --chamber house --days-back 7
"""

import sys
import os
import requests
import json
import time
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
import argparse

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Bill, Rollcall, Vote, Member, Action

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DailyRollcallBillUpdater:
    """Daily updater for roll calls, votes, and bill metadata."""
    
    def __init__(self):
        self.congressgov_api_key = os.getenv('CONGRESSGOV_API_KEY', 'DEMO_KEY')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional-Coalitions/1.0 (https://github.com/jmknapp/congressional-coalitions)'
        })
    
    def get_recent_rollcalls(self, congress: int = 119, chamber: str = 'house', days_back: int = 7) -> List[Dict]:
        """Get recent roll calls by probing for new roll call numbers."""
        logger.info(f"Probing for recent roll calls for Congress {congress}, {chamber} from last {days_back} days")
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        # Get the highest roll call number we already have in the database
        with get_db_session() as session:
            max_existing_roll = session.query(Rollcall.rc_number).filter(
                Rollcall.congress == congress,
                Rollcall.chamber == chamber
            ).order_by(Rollcall.rc_number.desc()).first()
            
            start_roll = (max_existing_roll[0] + 1) if max_existing_roll else 1
            logger.info(f"Starting probe from roll call {start_roll}")
        
        # Probe for new roll calls using a more efficient approach
        new_rollcalls = []
        
        # Check roll calls in our date range with early termination
        for session_num in [1, 2]:  # Check both sessions
            consecutive_misses = 0
            for roll_num in range(start_roll, start_roll + 20):  # Limit to 20 checks max
                try:
                    # Try to fetch this roll call
                    rc_details = self.get_rollcall_details(congress, chamber, session_num, roll_num)
                    if rc_details:
                        consecutive_misses = 0  # Reset miss counter
                        
                        # Handle different response formats
                        rc_data = (rc_details.get('houseRollCallVote') or 
                                  rc_details.get('houseVote') or 
                                  rc_details.get('senateVote') or 
                                  rc_details.get('vote') or 
                                  rc_details)
                        
                        # Check if this roll call is within our date range
                        rc_date_str = rc_data.get('date') or rc_data.get('startDate')
                        if rc_date_str:
                            try:
                                # Handle both date formats
                                if 'T' in rc_date_str:
                                    rc_date = datetime.strptime(rc_date_str.split('T')[0], '%Y-%m-%d').date()
                                else:
                                    rc_date = datetime.strptime(rc_date_str, '%Y-%m-%d').date()
                                
                                if start_date <= rc_date <= end_date:
                                    logger.info(f"Found recent roll call {roll_num} on {rc_date}")
                                    new_rollcalls.append({
                                        'session': session_num,
                                        'rollNumber': roll_num,
                                        'date': rc_date.isoformat(),
                                        'question': rc_data.get('voteQuestion', ''),
                                        'result': rc_data.get('result', ''),
                                        'details': rc_data
                                    })
                                elif rc_date < start_date:
                                    # If we hit a roll call older than our range, we can stop
                                    logger.info(f"Roll call {roll_num} is older than date range, stopping probe")
                                    break
                            except ValueError:
                                # Skip if date parsing fails
                                continue
                        else:
                            # No date, but roll call exists - include it
                            new_rollcalls.append({
                                'session': session_num,
                                'rollNumber': roll_num,
                                'date': None,
                                'question': rc_data.get('voteQuestion', ''),
                                'result': rc_data.get('result', ''),
                                'details': rc_data
                            })
                    else:
                        consecutive_misses += 1
                        if consecutive_misses >= 5:  # Stop after 5 consecutive misses
                            logger.info(f"Stopping after {consecutive_misses} consecutive misses")
                            break
                    
                    time.sleep(0.1)  # Rate limiting
                    
                except requests.exceptions.RequestException:
                    # 404 or other error - roll call doesn't exist
                    consecutive_misses += 1
                    if consecutive_misses >= 5:  # Stop after 5 consecutive misses
                        logger.info(f"Stopping after {consecutive_misses} consecutive 404s")
                        break
                    continue
                except Exception as e:
                    logger.warning(f"Error checking roll call {roll_num}: {e}")
                    continue
        
        logger.info(f"Found {len(new_rollcalls)} new roll calls to process")
        return new_rollcalls
    
    def get_existing_rollcalls_to_fix(self, congress: int = 119, chamber: str = 'house', days_back: int = 7) -> List[Dict]:
        """Get existing roll calls that need fixing (missing votes or bill data)."""
        logger.info(f"Finding existing roll calls that need fixing for Congress {congress}, {chamber}")
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        with get_db_session() as session:
            # Find roll calls that either have no votes or no bill data
            existing_rollcalls = session.query(Rollcall).filter(
                Rollcall.congress == congress,
                Rollcall.chamber == chamber,
                Rollcall.date >= start_date,
                Rollcall.date <= end_date
            ).all()
            
            rollcalls_to_fix = []
            for rc in existing_rollcalls:
                # Check if this roll call needs fixing
                vote_count = session.query(Vote).filter(Vote.rollcall_id == rc.rollcall_id).count()
                needs_fixing = False
                
                if vote_count == 0:
                    logger.info(f"Roll call {rc.rc_number} has no votes, needs fixing")
                    needs_fixing = True
                elif rc.bill_id is None:
                    logger.info(f"Roll call {rc.rc_number} has no bill ID, needs fixing")
                    needs_fixing = True
                elif rc.bill_id and not session.query(Bill).filter(Bill.bill_id == rc.bill_id).first():
                    logger.info(f"Roll call {rc.rc_number} references missing bill {rc.bill_id}, needs fixing")
                    needs_fixing = True
                
                if needs_fixing:
                    rollcalls_to_fix.append({
                        'session': rc.session,
                        'rollNumber': rc.rc_number,
                        'date': rc.date.isoformat() if rc.date else None,
                        'question': rc.question,
                        'result': None,  # Will be fetched from API
                        'details': None  # Will be fetched from API
                    })
            
            logger.info(f"Found {len(rollcalls_to_fix)} existing roll calls that need fixing")
            return rollcalls_to_fix
    
    def _extract_clerk_members(self, source_url: str) -> List[Tuple[str, str]]:
        """Extract member votes from Clerk XML source URL."""
        try:
            response = self.session.get(source_url, timeout=30)
            if response.status_code != 200:
                return []
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            def normalize_vote_code(code: str) -> str:
                if not code:
                    return 'Not Voting'
                c = code.strip().lower()
                if c in ('yea', 'aye', 'yes', 'y'):
                    return 'Yea'
                if c in ('nay', 'no', 'n'):
                    return 'Nay'
                if c in ('present', 'present - announced'):
                    return 'Present'
                return 'Not Voting'
            
            members = []
            # Look for recorded-vote elements
            for vote_elem in root.findall('.//recorded-vote'):
                # Get the legislator element
                legislator_elem = vote_elem.find('legislator')
                vote_elem_child = vote_elem.find('vote')
                
                if legislator_elem is not None and vote_elem_child is not None:
                    bioguide = legislator_elem.get('name-id')
                    vote_code = vote_elem_child.text
                    if bioguide and vote_code:
                        members.append((bioguide, normalize_vote_code(vote_code)))
            
            return members
            
        except Exception as e:
            logger.warning(f"Error extracting Clerk XML from {source_url}: {e}")
            return []
    
    def _ensure_member(self, session, bioguide: str):
        """Create a placeholder Member row if missing."""
        exists = session.query(Member).filter(Member.member_id_bioguide == bioguide).first()
        if not exists:
            session.add(Member(
                member_id_bioguide=bioguide,
                icpsr=None, 
                lis_id=None,
                first='',
                last='',
                party=None,
                state='',
                district=None,
                start_date=None,
                end_date=None
            ))
    
    def get_rollcall_details(self, congress: int, chamber: str, session_num: int, roll_num: int) -> Optional[Dict]:
        """Get detailed roll call information including votes."""
        # Use the correct endpoint format based on the existing working script
        if chamber == 'house':
            url = f"https://api.congress.gov/v3/house-vote/{congress}/{session_num}/{roll_num}"
        else:
            url = f"https://api.congress.gov/v3/senate-vote/{congress}/{session_num}/{roll_num}"
            
        params = {
            'api_key': self.congressgov_api_key,
            'format': 'json'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching roll call details for {congress}/{chamber}/{session_num}/{roll_num}: {e}")
            return None
    
    def get_bill_details(self, congress: int, bill_id: str) -> Optional[Dict]:
        """Get detailed bill information including actions and status."""
        # Convert bill ID format if needed
        if '-' in bill_id:
            parts = bill_id.split('-')
            if len(parts) >= 3:
                bill_type = parts[0].upper()
                bill_number = parts[1]
                bill_congress = parts[2]
                congressgov_bill_id = f"{bill_congress}/{bill_type}/{bill_number}"
            else:
                return None
        else:
            congressgov_bill_id = bill_id
        
        url = f"https://api.congress.gov/v3/bill/{congressgov_bill_id}"
        params = {
            'api_key': self.congressgov_api_key,
            'format': 'json'
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching bill details for {bill_id}: {e}")
            return None
    
    def update_rollcall_data(self, rollcalls: List[Dict], congress: int, chamber: str):
        """Update roll call and vote data in database."""
        logger.info(f"Updating {len(rollcalls)} roll calls in database")
        
        with get_db_session() as session:
            updated_count = 0
            new_count = 0
            
            for rc in rollcalls:
                try:
                    # Extract roll call details
                    session_num = rc.get('session')
                    roll_num = rc.get('rollNumber')
                    
                    if not session_num or not roll_num:
                        continue
                    
                    # Check if roll call already exists
                    existing_rc = session.query(Rollcall).filter(
                        Rollcall.congress == congress,
                        Rollcall.chamber == chamber,
                        Rollcall.session == session_num,
                        Rollcall.rc_number == roll_num
                    ).first()
                    
                    # Use the details we already fetched, or fetch them if needed
                    rc_data = rc.get('details', {})
                    if not rc_data:
                        # Fetch details from API if not already available
                        logger.info(f"Fetching details from API for roll call {roll_num}")
                        rc_details = self.get_rollcall_details(congress, chamber, session_num, roll_num)
                        if not rc_details:
                            continue
                        rc_data = (rc_details.get('houseRollCallVote') or 
                                  rc_details.get('houseVote') or 
                                  rc_details.get('senateVote') or 
                                  rc_details.get('vote') or 
                                  rc_details)
                        if not rc_data:
                            continue
                        logger.info(f"Fetched API data for roll call {roll_num}, bill data: {rc_data.get('bill', 'NO BILL DATA')}")
                    
                    # Parse date with fallback
                    rc_date = date.today()  # Default fallback
                    date_str = rc_data.get('date') or rc_data.get('startDate')
                    if date_str:
                        try:
                            # Handle both date formats
                            if 'T' in date_str:
                                rc_date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d').date()
                            else:
                                rc_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        except ValueError:
                            # If date parsing fails, use today's date
                            rc_date = date.today()
                    
                    # Create bill record if it doesn't exist
                    bill_id = None
                    # Check for bill information in the API response
                    legislation_type = rc_data.get('legislationType', '')
                    legislation_number = rc_data.get('legislationNumber', '')
                    
                    if legislation_type and legislation_number:
                        # Construct bill ID from legislation type and number
                        bill_type = legislation_type.lower()
                        bill_number = legislation_number
                        bill_id = f"{bill_type}-{bill_number}-{congress}"
                        logger.info(f"Processing bill {bill_id} for roll call {roll_num}")
                        
                        # Create bill data structure for consistency
                        bill_data = {
                            'type': legislation_type,
                            'number': legislation_number,
                            'title': '',  # Will be fetched later
                            'shortTitle': '',
                            'summary': {},
                            'latestAction': {}
                        }
                        
                        # Ensure bill exists in database
                        existing_bill = session.query(Bill).filter(Bill.bill_id == bill_id).first()
                        if not existing_bill:
                            # Create basic bill record
                            logger.info(f"Creating new bill {bill_id} with title: {bill_data.get('title', 'NO TITLE')}")
                            # Determine chamber from bill type
                            bt_lower = (bill_data.get('type') or '').lower()
                            if bt_lower in ['hr', 'hjres', 'hconres', 'hres']:
                                chamber_value = 'house'
                            elif bt_lower in ['s', 'sjres', 'sconres', 'sres']:
                                chamber_value = 'senate'
                            else:
                                chamber_value = 'house'  # safe default, but types above should cover

                            new_bill = Bill(
                                bill_id=bill_id,
                                congress=congress,
                                chamber=chamber_value,
                                type=bt_lower,
                                number=int(bill_data.get('number', 0)) if str(bill_data.get('number', '')).isdigit() else 0,
                                title=bill_data.get('title', ''),
                                introduced_date=None,
                                sponsor_bioguide=None,
                                policy_area=None,
                                summary_short=''
                            )
                            session.add(new_bill)
                            session.flush()
                        else:
                            logger.info(f"Bill {bill_id} already exists with title: {existing_bill.title}")
                    
                    # Create or update roll call record
                    if existing_rc:
                        # Update existing
                        existing_rc.date = rc_date
                        existing_rc.question = rc_data.get('voteQuestion', '')
                        existing_rc.bill_id = bill_id
                        rollcall_id = existing_rc.rollcall_id
                        updated_count += 1
                    else:
                        # Create new
                        new_rc = Rollcall(
                            rollcall_id=f'rc-{roll_num}-{congress}',
                            congress=congress,
                            chamber=chamber,
                            session=session_num,
                            rc_number=roll_num,
                            date=rc_date,
                            question=rc_data.get('voteQuestion', ''),
                            bill_id=bill_id
                        )
                        session.add(new_rc)
                        session.flush()  # Get the ID
                        rollcall_id = new_rc.rollcall_id
                        new_count += 1
                    
                    # Update votes by fetching from Clerk XML
                    source_url = rc_data.get('sourceDataURL')
                    logger.info(f"Processing roll call {roll_num}, source URL: {source_url}")
                    if source_url:
                        members = self._extract_clerk_members(source_url)
                        logger.info(f"Extracted {len(members)} votes from Clerk XML for roll call {roll_num}")
                        if members:
                            # Clear existing votes for this roll call
                            deleted_count = session.query(Vote).filter(Vote.rollcall_id == rollcall_id).count()
                            session.query(Vote).filter(Vote.rollcall_id == rollcall_id).delete()
                            logger.info(f"Deleted {deleted_count} existing votes for roll call {roll_num}")
                            
                            # Add new votes
                            vote_count = 0
                            for bioguide, vote_code in members:
                                # Ensure member exists
                                self._ensure_member(session, bioguide)
                                
                                vote = Vote(
                                    rollcall_id=rollcall_id,
                                    member_id_bioguide=bioguide,
                                    vote_code=vote_code
                                )
                                session.add(vote)
                                vote_count += 1
                            logger.info(f"Added {vote_count} new votes for roll call {roll_num}")
                        else:
                            logger.warning(f"No votes extracted from Clerk XML for roll call {roll_num}")
                    else:
                        logger.warning(f"No source URL found for roll call {roll_num}")
                    
                    session.commit()
                    time.sleep(0.1)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error updating roll call {rc}: {e}")
                    session.rollback()
                    continue
            
            logger.info(f"Roll call update complete: {new_count} new, {updated_count} updated")
    
    def update_bill_metadata(self, bill_ids: List[str], congress: int):
        """Update bill metadata including actions and status."""
        logger.info(f"Updating metadata for {len(bill_ids)} bills")
        
        with get_db_session() as session:
            updated_count = 0
            
            for bill_id in bill_ids:
                try:
                    # Get bill details from API
                    bill_details = self.get_bill_details(congress, bill_id)
                    if not bill_details:
                        continue
                    
                    bill_data = bill_details.get('bill', {})
                    
                    # Find existing bill
                    existing_bill = session.query(Bill).filter(Bill.bill_id == bill_id).first()
                    if not existing_bill:
                        continue
                    
                    # Update bill metadata
                    existing_bill.title = bill_data.get('title')
                    existing_bill.short_title = bill_data.get('shortTitle')
                    existing_bill.summary = bill_data.get('summary', {}).get('text')
                    existing_bill.latest_action = bill_data.get('latestAction', {}).get('text')
                    existing_bill.latest_action_date = datetime.strptime(
                        bill_data.get('latestAction', {}).get('actionDate', ''), '%Y-%m-%d'
                    ).date() if bill_data.get('latestAction', {}).get('actionDate') else None
                    
                    # Update actions
                    actions_data = bill_data.get('actions', [])
                    if actions_data:
                        # Clear existing actions
                        session.query(Action).filter(Action.bill_id == bill_id).delete()
                        
                        # Add new actions
                        for action_data in actions_data:
                            action = Action(
                                bill_id=bill_id,
                                action_date=datetime.strptime(action_data.get('actionDate', ''), '%Y-%m-%d').date() if action_data.get('actionDate') else None,
                                action_text=action_data.get('text'),
                                action_type=action_data.get('type')
                            )
                            session.add(action)
                    
                    session.commit()
                    updated_count += 1
                    time.sleep(0.1)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Error updating bill {bill_id}: {e}")
                    session.rollback()
                    continue
            
            logger.info(f"Bill metadata update complete: {updated_count} bills updated")
    
    def run_daily_update(self, congress: int = 119, chamber: str = 'house', days_back: int = 7, fix_existing: bool = False):
        """Run the complete daily update process."""
        logger.info("="*60)
        logger.info("DAILY ROLLCALL AND BILL UPDATE")
        logger.info("="*60)
        logger.info(f"Congress: {congress}")
        logger.info(f"Chamber: {chamber}")
        logger.info(f"Days back: {days_back}")
        logger.info(f"Started at: {datetime.now()}")
        
        try:
            # Step 1: Get recent roll calls
            rollcalls = self.get_recent_rollcalls(congress, chamber, days_back)
            
            # Step 1.5: If fix_existing is True, also get existing roll calls that need fixing
            if fix_existing:
                existing_rollcalls = self.get_existing_rollcalls_to_fix(congress, chamber, days_back)
                rollcalls.extend(existing_rollcalls)
                logger.info(f"Added {len(existing_rollcalls)} existing roll calls to fix")
            
            if rollcalls:
                # Step 2: Update roll call and vote data
                self.update_rollcall_data(rollcalls, congress, chamber)
                
                # Step 3: Collect bill IDs from roll calls
                bill_ids = []
                for rc in rollcalls:
                    rc_data = rc.get('details', {})
                    if not rc_data:
                        # If no details, fetch them fresh
                        rc_details = self.get_rollcall_details(congress, chamber, rc.get('session'), rc.get('rollNumber'))
                        if rc_details:
                            rc_data = (rc_details.get('houseRollCallVote') or 
                                      rc_details.get('houseVote') or 
                                      rc_details.get('senateVote') or 
                                      rc_details.get('vote') or 
                                      rc_details)
                    
                    if rc_data:
                        # Check for bill information in the API response
                        legislation_type = rc_data.get('legislationType', '')
                        legislation_number = rc_data.get('legislationNumber', '')
                        
                        if legislation_type and legislation_number:
                            # Construct bill ID from legislation type and number
                            bill_type = legislation_type.lower()
                            bill_number = legislation_number
                            bill_id = f"{bill_type}-{bill_number}-{congress}"
                            bill_ids.append(bill_id)
                
                # Step 4: Update bill metadata
                if bill_ids:
                    logger.info(f"Updating metadata for {len(bill_ids)} bills: {bill_ids}")
                    self.update_bill_metadata(bill_ids, congress)
                else:
                    logger.info("No bill IDs found to update")
            else:
                logger.info("No recent roll calls found")
            
            logger.info("✓ Daily update completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Daily update failed: {e}")
            logger.exception("Full traceback:")
            return False

def main():
    """Main function for command line execution."""
    parser = argparse.ArgumentParser(description='Daily roll call and bill metadata update')
    parser.add_argument('--congress', type=int, default=119, 
                       help='Congress number (default: 119)')
    parser.add_argument('--chamber', type=str, default='house',
                       choices=['house', 'senate'],
                       help='Chamber to update (default: house)')
    parser.add_argument('--days-back', type=int, default=7,
                       help='Number of days back to check for updates (default: 7)')
    parser.add_argument('--fix-existing', action='store_true',
                       help='Also fix existing roll calls that are missing votes or bill data')
    
    args = parser.parse_args()
    
    updater = DailyRollcallBillUpdater()
    success = updater.run_daily_update(
        congress=args.congress,
        chamber=args.chamber,
        days_back=args.days_back,
        fix_existing=args.fix_existing
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
