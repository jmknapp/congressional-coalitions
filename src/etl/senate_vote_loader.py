"""
Senate vote loader for congressional roll-call vote data.

This module handles the ingestion of Senate roll-call vote data from the LIS XML feeds.
"""

import os
import sys
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
import click
from tqdm import tqdm
import pandas as pd

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote, Member

logger = logging.getLogger(__name__)

class SenateVoteLoader:
    """Loader for Senate roll-call vote data."""
    
    def __init__(self):
        self.base_url = "https://www.senate.gov/legislative/LIS/roll_call_votes"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional Coalition Tracker/1.0'
        })
    
    def get_congress_votes(self, congress: int) -> List[Tuple[int, int]]:
        """
        Get list of roll-call vote numbers for a specific Congress.
        
        Args:
            congress: Congress number (e.g., 119)
        
        Returns:
            List of (session, vote_number) tuples
        """
        votes = []
        
        # Senate LIS provides votes by Congress and session
        # Most Congresses have 2 sessions, but some have 1 or 3
        sessions = [1, 2]  # Could be extended to handle special sessions
        
        for session in sessions:
            url = f"{self.base_url}/vote{congress}{session}/vote_{congress}_{session}.xml"
            try:
                response = self.session.get(url)
                response.raise_for_status()
                
                root = ET.fromstring(response.content)
                
                # Find all vote elements
                for vote_elem in root.findall('.//vote'):
                    vote_number = int(vote_elem.get('vote_number', 0))
                    if vote_number > 0:
                        votes.append((session, vote_number))
                
                logger.info(f"Found {len([v for v in votes if v[0] == session])} Senate votes in Congress {congress}, Session {session}")
                
            except Exception as e:
                logger.warning(f"Failed to fetch Senate votes for Congress {congress}, Session {session}: {e}")
        
        return votes
    
    def parse_vote_xml(self, xml_content: str) -> Dict:
        """
        Parse a single roll-call vote's XML content into structured data.
        
        Args:
            xml_content: XML string for a single roll-call vote
        
        Returns:
            Dictionary with parsed vote data
        """
        try:
            root = ET.fromstring(xml_content)
            vote_data = {}
            
            # Basic roll call info
            vote_elem = root.find('.//vote')
            if vote_elem is not None:
                vote_data['congress'] = int(vote_elem.get('congress', 0))
                vote_data['session'] = int(vote_elem.get('session', 0))
                vote_data['vote_number'] = int(vote_elem.get('vote_number', 0))
                
                # Parse vote date
                vote_date = vote_elem.get('vote_date')
                if vote_date:
                    try:
                        vote_data['date'] = datetime.strptime(vote_date, '%Y-%m-%d').date()
                    except ValueError:
                        pass
            
            # Vote question
            question_elem = root.find('.//vote_question')
            if question_elem is not None:
                vote_data['question'] = question_elem.text
            
            # Vote result
            result_elem = root.find('.//vote_result')
            if result_elem is not None:
                vote_data['result'] = result_elem.text
            
            # Bill information (if available)
            bill_elem = root.find('.//vote_document')
            if bill_elem is not None:
                bill_type = bill_elem.get('bill_type')
                bill_number = bill_elem.get('bill_number')
                if bill_type and bill_number:
                    vote_data['bill_id'] = f"{bill_type}{bill_number}-{vote_data['congress']}"
            
            # Individual votes
            votes = []
            for member_elem in root.findall('.//member'):
                member_data = {
                    'bioguide_id': member_elem.get('lis_member_id'),  # Senate uses LIS IDs
                    'vote_code': member_elem.get('vote_cast'),
                    'state': member_elem.get('state'),
                    'party': member_elem.get('party')
                }
                votes.append(member_data)
            
            vote_data['votes'] = votes
            
            return vote_data
            
        except Exception as e:
            logger.error(f"Failed to parse vote XML: {e}")
            return {}
    
    def load_vote(self, congress: int, session: int, vote_number: int) -> bool:
        """
        Load a single roll-call vote into the database.
        
        Args:
            congress: Congress number
            session: Session number
            vote_number: Roll-call vote number
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Fetch vote XML
            url = f"{self.base_url}/vote{congress}{session}/vote_{congress}_{session}_{vote_number:03d}.xml"
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse vote data
            vote_data = self.parse_vote_xml(response.text)
            if not vote_data:
                return False
            
            # Create rollcall ID
            rollcall_id = f"s{vote_data['congress']}-{vote_data['session']}-{vote_data['vote_number']}"
            
            # Store in database
            with get_db_session() as session:
                # Check if rollcall already exists
                existing_rollcall = session.query(Rollcall).filter(Rollcall.rollcall_id == rollcall_id).first()
                if existing_rollcall:
                    logger.debug(f"Rollcall {rollcall_id} already exists, skipping")
                    return True
                
                # Create rollcall record
                rollcall = Rollcall(
                    rollcall_id=rollcall_id,
                    congress=vote_data['congress'],
                    chamber='senate',
                    session=vote_data['session'],
                    rc_number=vote_data['vote_number'],
                    date=vote_data.get('date'),
                    question=vote_data.get('question'),
                    bill_id=vote_data.get('bill_id')
                )
                session.add(rollcall)
                
                # Add individual votes
                for vote_info in vote_data.get('votes', []):
                    # Map vote codes to our enum
                    vote_code = vote_info['vote_code']
                    if vote_code in ['Yea', 'Aye']:
                        vote_code = 'Yea'
                    elif vote_code in ['Nay', 'No']:
                        vote_code = 'Nay'
                    elif vote_code in ['Present', 'Present/Not Voting']:
                        vote_code = 'Present'
                    else:
                        vote_code = 'Not Voting'
                    
                    vote = Vote(
                        rollcall_id=rollcall_id,
                        member_id_bioguide=vote_info['bioguide_id'],
                        vote_code=vote_code
                    )
                    session.add(vote)
                
                session.commit()
                logger.info(f"Successfully loaded Senate vote {rollcall_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load Senate vote {congress}-{session}-{vote_number}: {e}")
            return False
    
    def load_congress_votes(self, congress: int, limit: Optional[int] = None):
        """
        Load all roll-call votes for a specific Congress.
        
        Args:
            congress: Congress number
            limit: Maximum number of votes to load (for testing)
        """
        logger.info(f"Loading Senate votes for Congress {congress}")
        
        # Get list of votes
        vote_tuples = self.get_congress_votes(congress)
        if limit:
            vote_tuples = vote_tuples[:limit]
        
        logger.info(f"Found {len(vote_tuples)} votes to load")
        
        # Load votes with progress bar
        successful = 0
        failed = 0
        
        for session, vote_number in tqdm(vote_tuples, desc=f"Loading Congress {congress} Senate votes"):
            if self.load_vote(congress, session, vote_number):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Congress {congress} Senate votes loading complete: {successful} successful, {failed} failed")

@click.command()
@click.option('--congress', type=int, required=True, help='Congress number (e.g., 119)')
@click.option('--limit', type=int, help='Maximum number of votes to load (for testing)')
def main(congress: int, limit: Optional[int]):
    """Load Senate roll-call vote data from LIS feeds."""
    logging.basicConfig(level=logging.INFO)
    
    loader = SenateVoteLoader()
    loader.load_congress_votes(congress, limit)

if __name__ == '__main__':
    main()


