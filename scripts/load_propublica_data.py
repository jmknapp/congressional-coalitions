#!/usr/bin/env python3
"""
Script to load real congressional data from ProPublica Congress API.
"""

import os
import sys
import logging
import requests
import json
from datetime import datetime, date
from typing import Dict, List, Optional

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote, Cosponsor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProPublicaLoader:
    """Loader for ProPublica Congress API data."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('PROPUBLICA_API_KEY')
        self.base_url = "https://api.propublica.org/congress/v1"
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({'X-API-Key': self.api_key})
        else:
            logger.warning("No ProPublica API key provided. Some endpoints may not work.")
    
    def get_members(self, congress: int, chamber: str) -> List[Dict]:
        """Get members for a specific Congress and chamber."""
        url = f"{self.base_url}/{congress}/{chamber}/members.json"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            members = []
            for member in data['results'][0]['members']:
                members.append({
                    'member_id_bioguide': member.get('id'),
                    'first': member.get('first_name', ''),
                    'last': member.get('last_name', ''),
                    'party': member.get('party', ''),
                    'state': member.get('state', ''),
                    'district': member.get('district'),
                    'start_date': date(2023, 1, 3)  # Approximate start date
                })
            
            logger.info(f"Retrieved {len(members)} {chamber} members for Congress {congress}")
            return members
            
        except Exception as e:
            logger.error(f"Failed to get members: {e}")
            return []
    
    def get_bills(self, congress: int, chamber: str, limit: int = 10) -> List[Dict]:
        """Get bills for a specific Congress and chamber."""
        url = f"{self.base_url}/{congress}/bills/{chamber}.json"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            bills = []
            for bill in data['results'][:limit]:
                bills.append({
                    'bill_id': bill.get('bill_id', ''),
                    'congress': congress,
                    'chamber': chamber,
                    'number': int(bill.get('number', 0)),
                    'type': bill.get('bill_type', ''),
                    'title': bill.get('title', ''),
                    'introduced_date': datetime.strptime(bill.get('introduced_date', '2023-01-01'), '%Y-%m-%d').date(),
                    'sponsor_bioguide': bill.get('sponsor_id', '')
                })
            
            logger.info(f"Retrieved {len(bills)} {chamber} bills for Congress {congress}")
            return bills
            
        except Exception as e:
            logger.error(f"Failed to get bills: {e}")
            return []
    
    def get_votes(self, congress: int, chamber: str, limit: int = 5) -> List[Dict]:
        """Get recent votes for a specific Congress and chamber."""
        url = f"{self.base_url}/{congress}/{chamber}/votes/recent.json"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            
            votes = []
            for vote in data['results']['votes'][:limit]:
                rollcall_id = f"{congress}-{vote.get('session', 1)}-{vote.get('roll_call', 0):03d}"
                
                votes.append({
                    'rollcall_id': rollcall_id,
                    'congress': congress,
                    'chamber': chamber,
                    'session': vote.get('session', 1),
                    'rc_number': vote.get('roll_call', 0),
                    'date': datetime.strptime(vote.get('date', '2023-01-01'), '%Y-%m-%d').date(),
                    'question': vote.get('question', ''),
                    'bill_id': vote.get('bill', {}).get('bill_id', '')
                })
            
            logger.info(f"Retrieved {len(votes)} {chamber} votes for Congress {congress}")
            return votes
            
        except Exception as e:
            logger.error(f"Failed to get votes: {e}")
            return []

def load_propublica_data(congress: int = 118, limit: int = 10):
    """Load data from ProPublica API."""
    loader = ProPublicaLoader()
    
    # Load members
    house_members = loader.get_members(congress, 'house')
    senate_members = loader.get_members(congress, 'senate')
    
    # Load bills
    house_bills = loader.get_bills(congress, 'house', limit)
    senate_bills = loader.get_bills(congress, 'senate', limit)
    
    # Load votes
    house_votes = loader.get_votes(congress, 'house', limit)
    senate_votes = loader.get_votes(congress, 'senate', limit)
    
    # Store in database
    with get_db_session() as session:
        # Store members
        for member_data in house_members + senate_members:
            if member_data['member_id_bioguide']:
                member = Member(**member_data)
                session.add(member)
        
        # Store bills
        for bill_data in house_bills + senate_bills:
            if bill_data['bill_id']:
                bill = Bill(**bill_data)
                session.add(bill)
        
        # Store rollcalls
        for vote_data in house_votes + senate_votes:
            if vote_data['rollcall_id']:
                rollcall = Rollcall(**vote_data)
                session.add(rollcall)
        
        session.commit()
        
        # Show counts
        member_count = session.query(Member).count()
        bill_count = session.query(Bill).count()
        rollcall_count = session.query(Rollcall).count()
        
        logger.info(f"Loaded from ProPublica API:")
        logger.info(f"  - {member_count} members")
        logger.info(f"  - {bill_count} bills")
        logger.info(f"  - {rollcall_count} rollcalls")

def main():
    """Main function."""
    logger.info("Loading data from ProPublica Congress API...")
    
    # Note: ProPublica API requires an API key for most endpoints
    # You can get one at https://www.propublica.org/datastore/api/propublica-congress-api
    load_propublica_data(congress=118, limit=5)
    
    logger.info("ProPublica data loading complete!")

if __name__ == '__main__':
    main()
