#!/usr/bin/env python3
"""
Check and ensure data consistency between Senate rollcall data and database.

This script:
1. Checks what member IDs are used in Senate rollcall data
2. Checks what bill IDs are used in Senate rollcall data  
3. Ensures they match the database format
4. Creates missing members/bills as needed
"""

import os
import sys
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import Dict, List, Optional, Set
import re
import click

# Add project root src to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.utils.database import get_db_session
from scripts.setup_db import Bill, Member, Rollcall, Vote

logger = logging.getLogger(__name__)

class SenateDataConsistencyChecker:
    """Check and fix data consistency issues between Senate data and database."""
    
    def __init__(self):
        self.base_url = "https://www.senate.gov/legislative/LIS"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional Coalition Tracker/1.0'
        })
        
        # Track what we find
        self.senate_member_ids = set()
        self.senate_bill_ids = set()
        self.missing_members = set()
        self.missing_bills = set()

    def load_senate_vote_menu(self, congress: int, session: int) -> List[str]:
        """Load Senate vote menu to get list of vote URLs."""
        url = f"{self.base_url}/roll_call_lists/vote_menu_{congress}_{session}.xml"
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            vote_urls = []
            
            for vote_elem in root.findall('.//vote'):
                vote_num_elem = vote_elem.find('vote_number')
                if vote_num_elem is not None and vote_num_elem.text:
                    vote_num = vote_num_elem.text.strip()
                    vote_url = f"{self.base_url}/roll_call_votes/vote{congress}{session}/vote_{congress}_{session}_{vote_num.zfill(5)}.xml"
                    vote_urls.append(vote_url)
            
            logger.info(f"Found {len(vote_urls)} Senate votes for Congress {congress}, Session {session}")
            return vote_urls
            
        except Exception as e:
            logger.error(f"Failed to load Senate vote menu: {e}")
            return []

    def analyze_senate_vote(self, url: str) -> Dict:
        """Analyze a single Senate vote to extract member and bill IDs."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Debug: Let's see what we're getting
            content = response.text
            logger.debug(f"Vote content length: {len(content)}")
            
            # Try to parse XML
            try:
                root = ET.fromstring(content)
            except ET.ParseError as e:
                logger.warning(f"XML parse error for {url}: {e}")
                # Try to extract basic info from text
                return self._extract_from_text(content, url)
            
            # Extract vote information
            vote_data = {
                'rollcall_id': None,
                'bill_id': None,
                'member_ids': set(),
                'vote_date': None
            }
            
            # Get rollcall ID
            vote_num_elem = root.find('.//vote_number')
            if vote_num_elem is not None and vote_num_elem.text:
                vote_num = int(vote_num_elem.text.strip())
                congress = 119  # Hardcoded for now
                vote_data['rollcall_id'] = f'rc-{vote_num}-{congress}'
            
            # Get bill information - Senate.gov uses document structure
            bill_type_elem = root.find('.//document/document_type')
            bill_num_elem = root.find('.//document/document_number')
            
            if bill_type_elem is not None and bill_num_elem is not None:
                bill_type = bill_type_elem.text.strip().lower()
                bill_num = bill_num_elem.text.strip()
                
                logger.debug(f"Found bill info: type={bill_type}, number={bill_num}")
                
                if bill_type == 'PN':  # Presidential Nomination
                    vote_data['bill_id'] = f"pn-{bill_num}-119"
                elif bill_type and bill_num.isdigit():
                    vote_data['bill_id'] = f"{bill_type}-{bill_num}-119"
                elif bill_type and bill_num:  # Handle non-numeric bill numbers
                    vote_data['bill_id'] = f"{bill_type}-{bill_num}-119"
            
            # Get member IDs - Senate.gov uses lis_member_id
            for member_elem in root.findall('.//member'):
                lis_member_id = member_elem.findtext('lis_member_id')
                if lis_member_id:
                    vote_data['member_ids'].add(lis_member_id.strip())
            
            # Get vote date
            date_elem = root.find('.//vote_date')
            if date_elem is not None and date_elem.text:
                try:
                    date_str = date_elem.text.strip()
                    # Parse date like "August 2, 2025, 09:40 PM"
                    date_part = date_str.split(',')[0] + ', ' + date_str.split(',')[1]
                    vote_data['vote_date'] = datetime.strptime(date_part, '%B %d, %Y').date()
                except:
                    pass
            
            logger.debug(f"Extracted from {url}: {len(vote_data['member_ids'])} members, bill_id: {vote_data['bill_id']}")
            return vote_data
            
        except Exception as e:
            logger.error(f"Failed to analyze Senate vote {url}: {e}")
            return {'rollcall_id': None, 'bill_id': None, 'member_ids': set(), 'vote_date': None}

    def _extract_from_text(self, content: str, url: str) -> Dict:
        """Extract information from text when XML parsing fails."""
        vote_data = {
            'rollcall_id': None,
            'bill_id': None,
            'member_ids': set(),
            'vote_date': None
        }
        
        # Try to extract vote number using regex
        import re
        vote_match = re.search(r'<vote_number>(\d+)</vote_number>', content)
        if vote_match:
            vote_num = int(vote_match.group(1))
            congress = 119
            vote_data['rollcall_id'] = f'rc-{vote_num}-{congress}'
        
        # Try to extract member IDs using regex - Senate.gov uses lis_member_id
        member_matches = re.findall(r'<lis_member_id>([^<]+)</lis_member_id>', content)
        for match in member_matches:
            vote_data['member_ids'].add(match.strip())
        
        # Try to extract bill information
        bill_type_match = re.search(r'<document_type>([^<]+)</document_type>', content)
        bill_num_match = re.search(r'<document_number>([^<]+)</document_number>', content)
        
        if bill_type_match and bill_num_match:
            bill_type = bill_type_match.group(1).strip().lower()
            bill_num = bill_num_match.group(1).strip()
            
            if bill_type == 'PN':
                vote_data['bill_id'] = f"pn-{bill_num}-119"
            elif bill_type and bill_num.isdigit():
                vote_data['bill_id'] = f"{bill_type}-{bill_num}-119"
        
        logger.debug(f"Extracted from text for {url}: {len(vote_data['member_ids'])} members, bill_id: {vote_data['bill_id']}")
        return vote_data

    def check_database_consistency(self):
        """Check what's in the database vs what we found in Senate data."""
        with get_db_session() as session_db:
            # Check existing members
            existing_members = {m.member_id_bioguide for m in session_db.query(Member).all()}
            logger.info(f"Database has {len(existing_members)} members")
            
            # Check existing bills
            existing_bills = {b.bill_id for b in session_db.query(Bill).all()}
            logger.info(f"Database has {len(existing_bills)} bills")
            
            # Find missing members
            self.missing_members = self.senate_member_ids - existing_members
            logger.info(f"Missing {len(self.missing_members)} members: {list(self.missing_members)[:10]}")
            
            # Find missing bills
            self.missing_bills = self.senate_bill_ids - existing_bills
            logger.info(f"Missing {len(self.missing_bills)} bills: {list(self.missing_bills)[:10]}")

    def create_missing_members(self):
        """Create placeholder members for missing member IDs."""
        if not self.missing_members:
            logger.info("No missing members to create")
            return
        
        logger.info(f"Creating {len(self.missing_members)} placeholder members")
        
        with get_db_session() as session_db:
            for member_id in self.missing_members:
                try:
                    # Create placeholder member
                    member = Member(
                        member_id_bioguide=member_id,
                        first="Unknown",
                        last="Senator",
                        party="U",  # Use single character for unknown
                        state="XX",  # Use 2-character code for unknown
                        district=None,  # Senators don't have districts
                        start_date=date(2023, 1, 3)
                    )
                    session_db.add(member)
                    logger.info(f"Created placeholder member: {member_id}")
                except Exception as e:
                    logger.error(f"Failed to create member {member_id}: {e}")
                    session_db.rollback()
                    continue
            
            session_db.commit()
            logger.info(f"Successfully created {len(self.missing_members)} placeholder members")

    def create_missing_bills(self):
        """Create placeholder bills for missing bill IDs."""
        if not self.missing_bills:
            logger.info("No missing bills to create")
            return
        
        logger.info(f"Creating {len(self.missing_bills)} placeholder bills")
        
        with get_db_session() as session_db:
            for bill_id in self.missing_bills:
                try:
                    # Parse bill_id to get components
                    parts = bill_id.split('-')
                    if len(parts) == 3:
                        bill_type, bill_number, congress = parts
                        
                        # Create placeholder bill
                        bill = Bill(
                            bill_id=bill_id,
                            congress=int(congress),
                            chamber='senate',
                            number=int(bill_number),
                            type=bill_type,
                            title=f"{bill_type.upper()} {bill_number} ({congress}th Congress)",
                            introduced_date=None,
                            sponsor_bioguide=None
                        )
                        session_db.add(bill)
                        logger.info(f"Created placeholder bill: {bill_id}")
                    else:
                        logger.warning(f"Invalid bill_id format: {bill_id}")
                        
                except Exception as e:
                    logger.error(f"Failed to create bill {bill_id}: {e}")
                    session_db.rollback()
                    continue
            
            session_db.commit()
            logger.info(f"Successfully created {len(self.missing_bills)} placeholder bills")

    def analyze_senate_data(self, congress: int = 119, max_votes: int = 50):
        """Analyze Senate data to check consistency."""
        logger.info(f"Analyzing Senate data for Congress {congress}")
        
        # Analyze both sessions
        for session in [1, 2]:
            logger.info(f"Analyzing session {session}")
            
            # Get vote URLs
            vote_urls = self.load_senate_vote_menu(congress, session)
            
            # Analyze first few votes
            for i, url in enumerate(vote_urls[:max_votes//2]):
                logger.info(f"Analyzing vote {i+1}/{min(max_votes//2, len(vote_urls))}: {url}")
                
                vote_data = self.analyze_senate_vote(url)
                
                # Log what we found
                logger.info(f"  Found {len(vote_data['member_ids'])} members, bill_id: {vote_data['bill_id']}")
                if vote_data['member_ids']:
                    logger.info(f"  Sample member IDs: {list(vote_data['member_ids'])[:5]}")
                
                # Collect member IDs
                self.senate_member_ids.update(vote_data['member_ids'])
                
                # Collect bill ID
                if vote_data['bill_id']:
                    self.senate_bill_ids.add(vote_data['bill_id'])
        
        logger.info(f"Found {len(self.senate_member_ids)} unique member IDs in Senate data")
        logger.info(f"Found {len(self.senate_bill_ids)} unique bill IDs in Senate data")
        
        # Check consistency with database
        self.check_database_consistency()
        
        # Create missing data
        self.create_missing_members()
        self.create_missing_bills()

@click.command()
@click.option('--congress', default=119, type=int, help='Congress number')
@click.option('--max-votes', default=50, type=int, help='Maximum votes to analyze')
def main(congress, max_votes):
    """Check and fix Senate data consistency."""
    
    checker = SenateDataConsistencyChecker()
    checker.analyze_senate_data(congress, max_votes)
    
    logger.info("Senate data consistency check completed!")

if __name__ == '__main__':
    main()
