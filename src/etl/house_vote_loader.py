"""
House vote loader for congressional roll-call vote data.

This module handles the ingestion of House roll-call vote data from the Clerk's XML/CSV feeds.
"""

import os
import sys
import logging
import requests
import xml.etree.ElementTree as ET
import csv
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

class HouseVoteLoader:
    """Loader for House roll-call vote data."""
    
    def __init__(self):
        self.base_url = "https://clerk.house.gov/evs"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional Coalition Tracker/1.0'
        })
    
    def get_congress_votes(self, congress: int) -> List[str]:
        """
        Get list of roll-call vote numbers for a specific Congress.
        
        Args:
            congress: Congress number (e.g., 119)
        
        Returns:
            List of roll-call vote numbers
        """
        votes = []
        
        # House Clerk provides votes by Congress
        url = f"{self.base_url}/{congress}/roll"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse the roll call directory page
            # This is a simplified approach - in practice, you might need to scrape the directory
            # or use a different method to get the list of votes
            
            # For now, we'll try to get votes by testing common patterns
            # House typically has votes numbered 1-1000+ per Congress
            for vote_num in range(1, 1001):  # Reasonable upper limit
                vote_url = f"{self.base_url}/{congress}/roll{vote_num:03d}.xml"
                try:
                    test_response = self.session.head(vote_url)
                    if test_response.status_code == 200:
                        votes.append(str(vote_num))
                except:
                    continue
                
                # Stop if we haven't found any votes in the last 50 attempts
                if len(votes) > 0 and vote_num > 50 and vote_num - int(votes[-1]) > 50:
                    break
            
            logger.info(f"Found {len(votes)} House votes in Congress {congress}")
            
        except Exception as e:
            logger.error(f"Failed to fetch House votes for Congress {congress}: {e}")
        
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
            rollcall = root.find('.//rollcall-vote')
            if rollcall is not None:
                vote_data['congress'] = int(rollcall.get('congress', 0))
                vote_data['session'] = int(rollcall.get('session', 0))
                vote_data['year'] = int(rollcall.get('year', 0))
                vote_data['roll'] = int(rollcall.get('roll', 0))
                
                # Parse vote date
                vote_date = rollcall.get('vote-date')
                if vote_date:
                    try:
                        vote_data['date'] = datetime.strptime(vote_date, '%Y-%m-%d').date()
                    except ValueError:
                        pass
            
            # Vote question
            question_elem = root.find('.//vote-question')
            if question_elem is not None:
                vote_data['question'] = question_elem.text
            
            # Vote result
            result_elem = root.find('.//vote-result')
            if result_elem is not None:
                vote_data['result'] = result_elem.text
            
            # Bill information (if available)
            bill_elem = root.find('.//vote-document')
            if bill_elem is not None:
                bill_type = bill_elem.get('bill-type')
                bill_number = bill_elem.get('bill-number')
                if bill_type and bill_number:
                    vote_data['bill_id'] = f"{bill_type}{bill_number}-{vote_data['congress']}"
            
            # Individual votes
            votes = []
            for vote_elem in root.findall('.//recorded-vote'):
                member_data = {
                    'bioguide_id': vote_elem.get('bioguide-id'),
                    'vote_code': vote_elem.get('vote'),
                    'state': vote_elem.get('state'),
                    'district': vote_elem.get('district')
                }
                votes.append(member_data)
            
            vote_data['votes'] = votes
            
            return vote_data
            
        except Exception as e:
            logger.error(f"Failed to parse vote XML: {e}")
            return {}
    
    def load_vote(self, congress: int, vote_number: str) -> bool:
        """
        Load a single roll-call vote into the database.
        
        Args:
            congress: Congress number
            vote_number: Roll-call vote number
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Fetch vote XML
            url = f"{self.base_url}/{congress}/roll{vote_number.zfill(3)}.xml"
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse vote data
            vote_data = self.parse_vote_xml(response.text)
            if not vote_data:
                return False
            
            # Create rollcall ID
            rollcall_id = f"h{vote_data['congress']}-{vote_data['session']}-{vote_data['roll']}"
            
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
                    chamber='house',
                    session=vote_data['session'],
                    rc_number=vote_data['roll'],
                    date=vote_data.get('date'),
                    question=vote_data.get('question'),
                    bill_id=vote_data.get('bill_id')
                )
                session.add(rollcall)
                
                # Add individual votes
                for vote_info in vote_data.get('votes', []):
                    # Map vote codes to our enum
                    vote_code = vote_info['vote_code']
                    if vote_code in ['Aye', 'Yea']:
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
                logger.info(f"Successfully loaded House vote {rollcall_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load House vote {congress}-{vote_number}: {e}")
            return False
    
    def load_congress_votes(self, congress: int, limit: Optional[int] = None):
        """
        Load all roll-call votes for a specific Congress.
        
        Args:
            congress: Congress number
            limit: Maximum number of votes to load (for testing)
        """
        logger.info(f"Loading House votes for Congress {congress}")
        
        # Get list of votes
        vote_numbers = self.get_congress_votes(congress)
        if limit:
            vote_numbers = vote_numbers[:limit]
        
        logger.info(f"Found {len(vote_numbers)} votes to load")
        
        # Load votes with progress bar
        successful = 0
        failed = 0
        
        for vote_number in tqdm(vote_numbers, desc=f"Loading Congress {congress} House votes"):
            if self.load_vote(congress, vote_number):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Congress {congress} House votes loading complete: {successful} successful, {failed} failed")

@click.command()
@click.option('--congress', type=int, required=True, help='Congress number (e.g., 119)')
@click.option('--limit', type=int, help='Maximum number of votes to load (for testing)')
def main(congress: int, limit: Optional[int]):
    """Load House roll-call vote data from Clerk feeds."""
    logging.basicConfig(level=logging.INFO)
    
    loader = HouseVoteLoader()
    loader.load_congress_votes(congress, limit)

if __name__ == '__main__':
    main()


