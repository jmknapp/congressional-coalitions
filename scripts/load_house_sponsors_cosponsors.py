#!/usr/bin/env python3
"""
Load sponsors and co-sponsors data for House members and bills.

This script:
1. Sets sponsors for bills using Congress.gov API
2. Loads co-sponsors data using Congress.gov API
3. Handles rate limiting and error recovery
4. Provides progress tracking and validation
5. Supports batch processing with offset for resuming
"""

import sys
import os
import requests
import json
import time
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import random

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Bill, Cosponsor, Member

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HouseSponsorsCosponsorsLoader:
    """Loader for House sponsors and co-sponsors data using Congress.gov API."""
    
    def __init__(self):
        self.congressgov_api_key = os.getenv('CONGRESSGOV_API_KEY', 'DEMO_KEY')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional-Coalitions/1.0 (https://github.com/jmknapp/congressional-coalitions)'
        })
    
    def convert_bill_id_to_congressgov_format(self, bill_id: str) -> Optional[str]:
        """Convert our bill ID format to Congress.gov format."""
        # Our format: "hr-1-119" -> Congress.gov format: "119/hr/1"
        try:
            parts = bill_id.split('-')
            if len(parts) >= 3:
                bill_type = parts[0]  # hr, s, hjres, etc.
                bill_number = parts[1]  # 1, 2, etc.
                congress = parts[2]  # 119, 118, etc.
                
                # Convert to Congress.gov format
                congressgov_id = f"{congress}/{bill_type}/{bill_number}"
                return congressgov_id
        except:
            pass
        return None
    
    def fetch_bill_from_congressgov(self, bill_id: str) -> Optional[Dict]:
        """Fetch bill data from Congress.gov API."""
        congressgov_id = self.convert_bill_id_to_congressgov_format(bill_id)
        if not congressgov_id:
            logger.warning(f"Could not convert bill ID {bill_id} to Congress.gov format")
            return None
        
        url = f"https://api.congress.gov/v3/bill/{congressgov_id}"
        headers = {'X-API-Key': self.congressgov_api_key}
        
        try:
            response = self.session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data
            elif response.status_code == 429:
                logger.warning(f"Rate limit hit for {bill_id}")
                return "RATE_LIMIT"
            else:
                logger.warning(f"Failed to fetch {bill_id} from Congress.gov: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching {bill_id} from Congress.gov: {e}")
        
        return None
    
    def fetch_cosponsors_from_congressgov(self, bill_id: str) -> Optional[List[Dict]]:
        """Fetch co-sponsors data from Congress.gov API."""
        congressgov_id = self.convert_bill_id_to_congressgov_format(bill_id)
        if not congressgov_id:
            logger.warning(f"Could not convert bill ID {bill_id} to Congress.gov format")
            return None
        
        url = f"https://api.congress.gov/v3/bill/{congressgov_id}/cosponsors"
        headers = {'X-API-Key': self.congressgov_api_key}
        
        try:
            response = self.session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'cosponsors' in data:
                    return data['cosponsors']
                else:
                    logger.warning(f"No cosponsors field in response for {bill_id}")
                    return []
            elif response.status_code == 429:
                logger.warning(f"Rate limit hit for {bill_id} cosponsors")
                return "RATE_LIMIT"
            else:
                logger.warning(f"Failed to fetch cosponsors for {bill_id} from Congress.gov: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching cosponsors for {bill_id} from Congress.gov: {e}")
        
        return None
    
    def set_bill_sponsor(self, bill_id: str, sponsor_bioguide: str) -> bool:
        """Set the sponsor for a bill."""
        try:
            with get_db_session() as session:
                bill = session.query(Bill).filter(Bill.bill_id == bill_id).first()
                if bill:
                    bill.sponsor_bioguide = sponsor_bioguide
                    session.commit()
                    logger.info(f"Set sponsor for {bill_id}: {sponsor_bioguide}")
                    return True
                else:
                    logger.warning(f"Bill {bill_id} not found in database")
                    return False
        except Exception as e:
            logger.error(f"Error setting sponsor for {bill_id}: {e}")
            return False
    
    def add_cosponsor(self, bill_id: str, member_bioguide: str, cosponsor_date: Optional[date] = None, is_original: bool = False) -> bool:
        """Add a cosponsor to a bill."""
        try:
            with get_db_session() as session:
                # Check if cosponsorship already exists
                existing = session.query(Cosponsor).filter(
                    Cosponsor.bill_id == bill_id,
                    Cosponsor.member_id_bioguide == member_bioguide
                ).first()
                
                if not existing:
                    cosponsor = Cosponsor(
                        bill_id=bill_id,
                        member_id_bioguide=member_bioguide,
                        date=cosponsor_date or date.today(),
                        is_original=is_original
                    )
                    session.add(cosponsor)
                    session.commit()
                    logger.info(f"Added cosponsor for {bill_id}: {member_bioguide}")
                    return True
                else:
                    logger.debug(f"Cosponsorship already exists for {bill_id}: {member_bioguide}")
                    return False
        except Exception as e:
            logger.error(f"Error adding cosponsor for {bill_id}: {e}")
            return False
    
    def process_bill_sponsors(self, bill_id: str) -> bool:
        """Process sponsors for a single bill using Congress.gov API."""
        bill_data = self.fetch_bill_from_congressgov(bill_id)
        
        if bill_data == "RATE_LIMIT":
            return False
        
        if bill_data and 'bill' in bill_data and 'sponsors' in bill_data['bill']:
            sponsors = bill_data['bill']['sponsors']
            if sponsors and len(sponsors) > 0:
                sponsor_bioguide = sponsors[0].get('bioguideId')
                if sponsor_bioguide:
                    return self.set_bill_sponsor(bill_id, sponsor_bioguide)
        
        return False
    
    def process_bill_cosponsors(self, bill_id: str) -> int:
        """Process co-sponsors for a single bill using Congress.gov API."""
        cosponsors_added = 0
        
        bill_data = self.fetch_bill_from_congressgov(bill_id)
        
        if bill_data == "RATE_LIMIT":
            return 0
        
        if bill_data and 'bill' in bill_data and 'cosponsors' in bill_data['bill']:
            cosponsors_data = bill_data['bill']['cosponsors']
            if isinstance(cosponsors_data, list):
                for cosponsor in cosponsors_data:
                    cosponsor_bioguide = cosponsor.get('bioguideId')
                    if cosponsor_bioguide:
                        # Try to parse date
                        cosponsor_date = None
                        if 'date' in cosponsor:
                            try:
                                cosponsor_date = datetime.strptime(cosponsor['date'], '%Y-%m-%d').date()
                            except:
                                pass
                        
                        if self.add_cosponsor(bill_id, cosponsor_bioguide, cosponsor_date):
                            cosponsors_added += 1
        
        return cosponsors_added
    
    def count_bills_to_process(self, congress: int = 119, skip_processed: bool = False) -> int:
        """Count how many bills still need to be processed."""
        with get_db_session() as session:
            query = session.query(Bill).filter(
                Bill.congress == congress,
                Bill.chamber == 'house'
            )
            
            if skip_processed:
                query = query.filter(Bill.sponsor_bioguide.is_(None))
            
            return query.count()
    
    def load_house_sponsors_and_cosponsors(self, congress: int = 119, limit: Optional[int] = None, offset: int = 0, skip_processed: bool = False):
        """Load sponsors and co-sponsors for House bills using Congress.gov API."""
        logger.info(f"Loading sponsors and co-sponsors for House bills in Congress {congress}")
        logger.info(f"Using Congress.gov API with real API key")
        
        # Count total bills that need processing
        total_bills_to_process = self.count_bills_to_process(congress, skip_processed)
        logger.info(f"Total bills that need processing: {total_bills_to_process}")
        
        if offset > 0:
            logger.info(f"Starting from offset {offset}")
        if skip_processed:
            logger.info(f"Skipping bills that already have sponsors set")
        
        with get_db_session() as session:
            # Get House bills for the specified Congress
            query = session.query(Bill).filter(
                Bill.congress == congress,
                Bill.chamber == 'house'
            )
            
            # Skip processed bills if requested
            if skip_processed:
                # Only skip bills that have sponsors set
                # (We'll always check for co-sponsor updates)
                query = query.filter(Bill.sponsor_bioguide.is_(None))
            
            # Apply offset and limit
            if offset > 0:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            bills = query.all()
            logger.info(f"Found {len(bills)} House bills to process")
            
            # Extract bill IDs while still in session
            bill_ids = [bill.bill_id for bill in bills]
        
        sponsors_set = 0
        cosponsors_added = 0
        rate_limit_hits = 0
        
        for i, bill_id in enumerate(bill_ids):
            logger.info(f"Processing bill {offset + i + 1}: {bill_id}")
            
            # Process sponsors and co-sponsors in one API call
            bill_data = self.fetch_bill_from_congressgov(bill_id)
            
            if bill_data == "RATE_LIMIT":
                rate_limit_hits += 1
                logger.warning(f"Rate limit hit! Stopping processing.")
                logger.info(f"Processed {i} bills before hitting rate limit.")
                logger.info(f"Next run should use --offset {offset + i}")
                logger.info(f"Completed processing {i} House bills (offset: {offset}):")
                logger.info(f"  - Sponsors set: {sponsors_set}")
                logger.info(f"  - Cosponsors added: {cosponsors_added}")
                logger.info(f"  - Rate limit hits: {rate_limit_hits}")
                return  # Exit gracefully
            
            if bill_data and 'bill' in bill_data:
                # Process sponsors
                if 'sponsors' in bill_data['bill']:
                    sponsors = bill_data['bill']['sponsors']
                    if sponsors and len(sponsors) > 0:
                        sponsor_bioguide = sponsors[0].get('bioguideId')
                        if sponsor_bioguide:
                            if self.set_bill_sponsor(bill_id, sponsor_bioguide):
                                sponsors_set += 1
                
                # Process co-sponsors from separate endpoint
                logger.info(f"Fetching co-sponsors for {bill_id}...")
                cosponsors_data = self.fetch_cosponsors_from_congressgov(bill_id)
                
                if cosponsors_data == "RATE_LIMIT":
                    logger.warning(f"Rate limit hit while fetching co-sponsors for {bill_id}")
                elif cosponsors_data and isinstance(cosponsors_data, list):
                    logger.info(f"Found {len(cosponsors_data)} co-sponsors for {bill_id}")
                    for cosponsor in cosponsors_data:
                        cosponsor_bioguide = cosponsor.get('bioguideId')
                        if cosponsor_bioguide:
                            # Try to parse date
                            cosponsor_date = None
                            if 'date' in cosponsor:
                                try:
                                    cosponsor_date = datetime.strptime(cosponsor['date'], '%Y-%m-%d').date()
                                except:
                                    pass
                            
                            if self.add_cosponsor(bill_id, cosponsor_bioguide, cosponsor_date):
                                cosponsors_added += 1
                else:
                    logger.info(f"No co-sponsors found for {bill_id}")
            
            # Rate limiting - wait 2 seconds between requests (conservative for daily limits)
            time.sleep(2)
            
            # Progress update every 5 bills
            if i > 0 and i % 5 == 0:
                logger.info(f"Progress: {i}/{len(bill_ids)} bills processed (offset: {offset})")
                logger.info(f"  - Sponsors set: {sponsors_set}")
                logger.info(f"  - Cosponsors added: {cosponsors_added}")
                logger.info(f"  - Rate limit hits: {rate_limit_hits}")
        
        logger.info(f"Completed processing {len(bill_ids)} House bills (offset: {offset}):")
        logger.info(f"  - Sponsors set: {sponsors_set}")
        logger.info(f"  - Cosponsors added: {cosponsors_added}")
        logger.info(f"  - Rate limit hits: {rate_limit_hits}")
    
    def generate_sample_cosponsors(self, congress: int = 119, limit: int = 50, offset: int = 0):
        """Generate sample co-sponsors data for testing (when APIs are rate limited)."""
        logger.info(f"Generating sample co-sponsors for {limit} House bills in Congress {congress}")
        if offset > 0:
            logger.info(f"Starting from offset {offset}")
        
        with get_db_session() as session:
            # Get House bills and members
            query = session.query(Bill).filter(
                Bill.congress == congress,
                Bill.chamber == 'house'
            )
            
            # Apply offset and limit
            if offset > 0:
                query = query.offset(offset)
            query = query.limit(limit)
            
            bills = query.all()
            
            members = session.query(Member).filter(
                Member.district.isnot(None)  # House members only
            ).all()
            
            logger.info(f"Found {len(bills)} bills and {len(members)} House members")
            
            sponsors_set = 0
            cosponsors_added = 0
            
            for i, bill in enumerate(bills):
                logger.info(f"Processing bill {offset + i + 1}: {bill.bill_id}")
                
                # Set a random sponsor
                if not bill.sponsor_bioguide:
                    sponsor = random.choice(members)
                    bill.sponsor_bioguide = sponsor.member_id_bioguide
                    sponsors_set += 1
                    logger.info(f"Set sponsor for {bill.bill_id}: {sponsor.member_id_bioguide}")
                
                # Add random co-sponsors (0-15 per bill)
                num_cosponsors = random.randint(0, 15)
                selected_cosponsors = random.sample(members, min(num_cosponsors, len(members)))
                
                for cosponsor in selected_cosponsors:
                    # Random date within the last year
                    days_ago = random.randint(0, 365)
                    cosponsor_date = date.today() - timedelta(days=days_ago)
                    
                    # Check if cosponsorship already exists
                    existing = session.query(Cosponsor).filter(
                        Cosponsor.bill_id == bill.bill_id,
                        Cosponsor.member_id_bioguide == cosponsor.member_id_bioguide
                    ).first()
                    
                    if not existing:
                        new_cosponsor = Cosponsor(
                            bill_id=bill.bill_id,
                            member_id_bioguide=cosponsor.member_id_bioguide,
                            date=cosponsor_date,
                            is_original=False
                        )
                        session.add(new_cosponsor)
                        cosponsors_added += 1
                        logger.info(f"Added cosponsor for {bill.bill_id}: {cosponsor.member_id_bioguide}")
                
                # Commit every 10 bills to avoid long transactions
                if (i + 1) % 10 == 0:
                    session.commit()
                    logger.info(f"Committed batch {offset + i + 1}")
            
            # Final commit
            session.commit()
        
        logger.info(f"Generated sample data (offset: {offset}):")
        logger.info(f"  - Sponsors set: {sponsors_set}")
        logger.info(f"  - Cosponsors added: {cosponsors_added}")

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Load House sponsors and co-sponsors data')
    parser.add_argument('--congress', type=int, default=119, help='Congress number (default: 119)')
    parser.add_argument('--limit', type=int, help='Limit number of bills to process')
    parser.add_argument('--offset', type=int, default=0, help='Offset to start from (for batch processing)')
    parser.add_argument('--skip-processed', action='store_true', help='Skip bills that already have sponsors set')
    parser.add_argument('--sample', action='store_true', help='Generate sample data instead of using APIs')
    parser.add_argument('--api-key', help='Congress.gov API key')
    
    args = parser.parse_args()
    
    # Set API key if provided
    if args.api_key:
        os.environ['CONGRESSGOV_API_KEY'] = args.api_key
    
    loader = HouseSponsorsCosponsorsLoader()
    
    if args.sample:
        loader.generate_sample_cosponsors(args.congress, args.limit or 50, args.offset)
    else:
        loader.load_house_sponsors_and_cosponsors(args.congress, args.limit, args.offset, args.skip_processed)

if __name__ == "__main__":
    main()
