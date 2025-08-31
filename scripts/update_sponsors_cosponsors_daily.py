#!/usr/bin/env python3
"""
Daily update script for sponsors and co-sponsors data.

This script:
1. Updates sponsors for new bills (last 7 days)
2. Re-checks co-sponsors for bills with recent activity
3. Uses efficient change detection to minimize API calls
4. Handles rate limits gracefully
"""

import sys
import os
import requests
import json
import time
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
import hashlib

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

class DailySponsorsCosponsorsUpdater:
    """Daily updater for sponsors and co-sponsors data."""
    
    def __init__(self):
        self.congressgov_api_key = os.getenv('CONGRESSGOV_API_KEY', 'DEMO_KEY')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional-Coalitions/1.0 (https://github.com/jmknapp/congressional-coalitions)'
        })
    
    def convert_bill_id_to_congressgov_format(self, bill_id: str) -> Optional[str]:
        """Convert our bill ID format to Congress.gov format."""
        try:
            parts = bill_id.split('-')
            if len(parts) >= 3:
                bill_type = parts[0]
                bill_number = parts[1]
                congress = parts[2]
                congressgov_id = f"{congress}/{bill_type}/{bill_number}"
                return congressgov_id
        except:
            pass
        return None
    
    def fetch_bill_from_congressgov(self, bill_id: str) -> Optional[Dict]:
        """Fetch bill data from Congress.gov API."""
        congressgov_id = self.convert_bill_id_to_congressgov_format(bill_id)
        if not congressgov_id:
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
    
    def get_cosponsors_hash(self, bill_id: str) -> str:
        """Get a hash of current co-sponsors for change detection."""
        try:
            with get_db_session() as session:
                cosponsors = session.query(Cosponsor).filter(
                    Cosponsor.bill_id == bill_id
                ).all()
                
                # Create hash from co-sponsor data
                cosponsor_data = []
                for cosp in cosponsors:
                    cosponsor_data.append(f"{cosp.member_id_bioguide}:{cosp.date}:{cosp.is_original}")
                
                cosponsor_data.sort()  # Sort for consistent hashing
                data_string = "|".join(cosponsor_data)
                return hashlib.md5(data_string.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error getting co-sponsors hash for {bill_id}: {e}")
            return ""
    
    def update_bill_sponsor(self, bill_id: str, sponsor_bioguide: str) -> bool:
        """Update the sponsor for a bill."""
        try:
            with get_db_session() as session:
                bill = session.query(Bill).filter(Bill.bill_id == bill_id).first()
                if bill:
                    if bill.sponsor_bioguide != sponsor_bioguide:
                        bill.sponsor_bioguide = sponsor_bioguide
                        session.commit()
                        logger.info(f"Updated sponsor for {bill_id}: {sponsor_bioguide}")
                        return True
                    else:
                        logger.debug(f"Sponsor unchanged for {bill_id}")
                        return False
                else:
                    logger.warning(f"Bill {bill_id} not found in database")
                    return False
        except Exception as e:
            logger.error(f"Error updating sponsor for {bill_id}: {e}")
            return False
    
    def sync_cosponsors(self, bill_id: str, api_cosponsors: List[Dict]) -> int:
        """Sync co-sponsors from API with database, returning number of changes."""
        changes = 0
        
        try:
            with get_db_session() as session:
                # Get current co-sponsors
                current_cosponsors = session.query(Cosponsor).filter(
                    Cosponsor.bill_id == bill_id
                ).all()
                current_bioguides = {cosp.member_id_bioguide for cosp in current_cosponsors}
                
                # Process API co-sponsors
                api_bioguides = set()
                for cosponsor in api_cosponsors:
                    cosponsor_bioguide = cosponsor.get('bioguideId')
                    if cosponsor_bioguide:
                        api_bioguides.add(cosponsor_bioguide)
                        
                        # Check if this co-sponsor exists
                        existing = session.query(Cosponsor).filter(
                            Cosponsor.bill_id == bill_id,
                            Cosponsor.member_id_bioguide == cosponsor_bioguide
                        ).first()
                        
                        if not existing:
                            # Add new co-sponsor
                            cosponsor_date = None
                            if 'date' in cosponsor:
                                try:
                                    cosponsor_date = datetime.strptime(cosponsor['date'], '%Y-%m-%d').date()
                                except:
                                    pass
                            
                            new_cosponsor = Cosponsor(
                                bill_id=bill_id,
                                member_id_bioguide=cosponsor_bioguide,
                                date=cosponsor_date or date.today(),
                                is_original=False
                            )
                            session.add(new_cosponsor)
                            changes += 1
                            logger.info(f"Added cosponsor for {bill_id}: {cosponsor_bioguide}")
                
                # Remove co-sponsors that are no longer in API
                for current_cosp in current_cosponsors:
                    if current_cosp.member_id_bioguide not in api_bioguides:
                        session.delete(current_cosp)
                        changes += 1
                        logger.info(f"Removed cosponsor for {bill_id}: {current_cosp.member_id_bioguide}")
                
                if changes > 0:
                    session.commit()
                
        except Exception as e:
            logger.error(f"Error syncing cosponsors for {bill_id}: {e}")
        
        return changes
    
    def discover_new_bills(self, congress: int = 119, days_back: int = 7) -> List[str]:
        """Discover new bills introduced in the last N days."""
        logger.info(f"Discovering new bills for Congress {congress} (last {days_back} days)")
        
        cutoff_date = date.today() - timedelta(days=days_back)
        new_bill_ids = []
        
        # Get existing bill IDs to avoid duplicates
        with get_db_session() as session:
            existing_bills = {bill.bill_id for bill in session.query(Bill).filter(
                Bill.congress == congress,
                Bill.chamber == 'house'
            ).all()}
        
        logger.info(f"Found {len(existing_bills)} existing bills in database")
        
        # Query Congress.gov for recent bills
        url = f"https://api.congress.gov/v3/bill"
        headers = {'X-API-Key': self.congressgov_api_key}
        
        # Check all bill types
        bill_types = ['hr', 'hconres', 'hjres', 'hres']
        
        for bill_type in bill_types:
            logger.info(f"Checking for new {bill_type} bills...")
            
            params = {
                'congress': congress,
                'billType': bill_type,
                'introducedDate': cutoff_date.isoformat(),
                'format': 'json',
                'limit': 250  # Increased limit to get more bills
            }
            
            try:
                response = self.session.get(url, headers=headers, params=params, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    if 'bills' in data:
                        for bill_data in data['bills']:
                            bill_id = bill_data.get('billId')
                            if bill_id:
                                # Convert Congress.gov format to our format
                                # Congress.gov: "119/hr/1234" -> Our format: "hr-1234-119"
                                parts = bill_id.split('/')
                                if len(parts) == 3:
                                    congress_num, bill_type, bill_number = parts
                                    our_bill_id = f"{bill_type}-{bill_number}-{congress_num}"
                                    
                                    # Only add if not already in database
                                    if our_bill_id not in existing_bills:
                                        new_bill_ids.append(our_bill_id)
                                        logger.info(f"Discovered new bill: {our_bill_id}")
                                    else:
                                        logger.debug(f"Bill already exists: {our_bill_id}")
                
                time.sleep(1)  # Rate limiting between bill type queries
                
            except Exception as e:
                logger.error(f"Error discovering {bill_type} bills: {e}")
        
        logger.info(f"Discovered {len(new_bill_ids)} new bills not in database")
        return new_bill_ids
    
    def add_new_bills_to_database(self, bill_ids: List[str], congress: int = 119) -> int:
        """Add new bills to the database."""
        added_count = 0
        
        with get_db_session() as session:
            for bill_id in bill_ids:
                # Check if bill already exists
                existing = session.query(Bill).filter(Bill.bill_id == bill_id).first()
                if not existing:
                    # Parse bill ID to get components
                    parts = bill_id.split('-')
                    if len(parts) >= 3:
                        bill_type = parts[0]
                        bill_number = parts[1]
                        congress_num = parts[2]
                        
                        # Create new bill record
                        new_bill = Bill(
                            bill_id=bill_id,
                            congress=int(congress_num),
                            bill_type=bill_type,
                            bill_number=bill_number,
                            chamber='house',
                            title=f"New {bill_type.upper()} {bill_number}",
                            introduced_date=date.today()  # Approximate
                        )
                        session.add(new_bill)
                        added_count += 1
                        logger.info(f"Added new bill to database: {bill_id}")
            
            session.commit()
        
        logger.info(f"Added {added_count} new bills to database")
        return added_count
    
    def get_bills_to_update(self, congress: int = 119, days_back: int = 7) -> List[str]:
        """Get bills that need updating (new bills + recently active bills)."""
        cutoff_date = date.today() - timedelta(days=days_back)
        
        with get_db_session() as session:
            # Get new bills (no sponsor set)
            new_bills = session.query(Bill).filter(
                Bill.congress == congress,
                Bill.chamber == 'house',
                Bill.sponsor_bioguide.is_(None)
            ).limit(50).all()
            
            # Get bills with recent co-sponsor activity
            recent_bills = session.query(Bill).join(Cosponsor).filter(
                Bill.congress == congress,
                Bill.chamber == 'house',
                Cosponsor.date >= cutoff_date
            ).distinct().limit(100).all()
            
            # Get bills that haven't been updated recently (no last_updated field, so skip this for now)
            # stale_bills = session.query(Bill).filter(
            #     Bill.congress == congress,
            #     Bill.chamber == 'house',
            #     Bill.last_updated.is_(None)
            # ).limit(50).all()
            stale_bills = []
            
            bill_ids = set()
            for bill in new_bills + recent_bills + stale_bills:
                bill_ids.add(bill.bill_id)
            
            return list(bill_ids)
    
    def update_daily(self, congress: int = 119, max_bills: int = 50, discover_new: bool = True):
        """Perform daily update of sponsors and co-sponsors."""
        logger.info(f"Starting daily update for Congress {congress}")
        
        # Step 1: Discover and add new bills
        new_bills_added = 0
        if discover_new:
            new_bill_ids = self.discover_new_bills(congress, days_back=7)
            if new_bill_ids:
                new_bills_added = self.add_new_bills_to_database(new_bill_ids, congress)
                logger.info(f"Added {new_bills_added} new bills to database")
        
        # Step 2: Get bills to update
        bills_to_update = self.get_bills_to_update(congress)
        if len(bills_to_update) > max_bills:
            bills_to_update = bills_to_update[:max_bills]
        
        logger.info(f"Found {len(bills_to_update)} bills to update")
        
        sponsors_updated = 0
        cosponsors_changed = 0
        rate_limit_hit = False
        
        for i, bill_id in enumerate(bills_to_update):
            logger.info(f"Updating bill {i+1}/{len(bills_to_update)}: {bill_id}")
            
            # Get current state hash for change detection
            current_hash = self.get_cosponsors_hash(bill_id)
            
            # Fetch from API
            bill_data = self.fetch_bill_from_congressgov(bill_id)
            
            if bill_data == "RATE_LIMIT":
                logger.warning(f"Rate limit hit! Stopping daily update.")
                logger.info(f"Updated {i} bills before hitting rate limit.")
                rate_limit_hit = True
                break
            
            if bill_data and 'bill' in bill_data:
                # Update sponsor
                if 'sponsors' in bill_data['bill']:
                    sponsors = bill_data['bill']['sponsors']
                    if sponsors and len(sponsors) > 0:
                        sponsor_bioguide = sponsors[0].get('bioguideId')
                        if sponsor_bioguide:
                            if self.update_bill_sponsor(bill_id, sponsor_bioguide):
                                sponsors_updated += 1
                
                # Update co-sponsors
                if 'cosponsors' in bill_data['bill']:
                    cosponsors_data = bill_data['bill']['cosponsors']
                    if isinstance(cosponsors_data, list):
                        changes = self.sync_cosponsors(bill_id, cosponsors_data)
                        cosponsors_changed += changes
            
            # Rate limiting
            time.sleep(2)
        
        logger.info(f"Daily update completed:")
        logger.info(f"  - New bills added: {new_bills_added}")
        logger.info(f"  - Bills processed: {len(bills_to_update)}")
        logger.info(f"  - Sponsors updated: {sponsors_updated}")
        logger.info(f"  - Co-sponsor changes: {cosponsors_changed}")
        logger.info(f"  - Rate limit hit: {rate_limit_hit}")
        
        return rate_limit_hit

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Daily update of House sponsors and co-sponsors')
    parser.add_argument('--congress', type=int, default=119, help='Congress number (default: 119)')
    parser.add_argument('--max-bills', type=int, default=50, help='Maximum bills to process (default: 50)')
    parser.add_argument('--no-discover', action='store_true', help='Skip new bill discovery')
    parser.add_argument('--api-key', help='Congress.gov API key')
    
    args = parser.parse_args()
    
    # Set API key if provided
    if args.api_key:
        os.environ['CONGRESSGOV_API_KEY'] = args.api_key
    
    updater = DailySponsorsCosponsorsUpdater()
    rate_limit_hit = updater.update_daily(args.congress, args.max_bills, discover_new=not args.no_discover)
    
    # Exit with error code if rate limit was hit
    if rate_limit_hit:
        sys.exit(1)

if __name__ == "__main__":
    main()
