#!/usr/bin/env python3
"""
Enhanced daily update script with improved bill selection distribution.
Uses last_updated tracking to ensure all bills eventually get processed.
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
from sqlalchemy import text, or_, and_

# Add scripts to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))
from setup_db import BillSubject

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedDailySponsorsCosponsorsUpdater:
    """Enhanced daily updater with better bill selection distribution."""
    
    def __init__(self):
        self.congressgov_api_key = os.getenv('CONGRESSGOV_API_KEY', 'DEMO_KEY')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional-Coalitions/1.0 (https://github.com/jmknapp/congressional-coalitions)'
        })
    
    def get_bills_to_update_enhanced(self, congress: int = 119, max_bills: int = 100) -> List[str]:
        """Get bills using enhanced selection with last_updated tracking."""
        
        with get_db_session() as session:
            bill_ids = set()
            
            # Priority 1: Bills with no sponsor (highest priority - up to 25)
            no_sponsor_bills = session.execute(text("""
                SELECT bill_id FROM bills 
                WHERE congress = :congress 
                AND chamber = 'house'
                AND sponsor_bioguide IS NULL
                ORDER BY introduced_date DESC
                LIMIT 25
            """), {'congress': congress}).fetchall()
            
            for bill in no_sponsor_bills:
                bill_ids.add(bill.bill_id)
            
            logger.info(f"Priority 1 - Bills without sponsors: {len(no_sponsor_bills)}")
            
            # Priority 2: Bills never updated (up to 35)
            never_updated_bills = session.execute(text("""
                SELECT bill_id FROM bills 
                WHERE congress = :congress 
                AND chamber = 'house'
                AND last_updated IS NULL
                AND sponsor_bioguide IS NOT NULL
                ORDER BY introduced_date DESC
                LIMIT 35
            """), {'congress': congress}).fetchall()
            
            for bill in never_updated_bills:
                bill_ids.add(bill.bill_id)
            
            logger.info(f"Priority 2 - Never updated bills: {len(never_updated_bills)}")
            
            # Priority 3: Bills with recent cosponsor activity but not updated recently (up to 25)
            recent_activity_bills = session.execute(text("""
                SELECT DISTINCT b.bill_id, MAX(c.date) as latest_cosponsor_date
                FROM bills b
                JOIN cosponsors c ON b.bill_id = c.bill_id
                WHERE b.congress = :congress 
                AND b.chamber = 'house'
                AND c.date >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                AND (b.last_updated IS NULL OR b.last_updated < DATE_SUB(NOW(), INTERVAL 3 DAY))
                GROUP BY b.bill_id
                ORDER BY latest_cosponsor_date DESC
                LIMIT 25
            """), {'congress': congress}).fetchall()
            
            for bill in recent_activity_bills:
                bill_ids.add(bill.bill_id)
            
            logger.info(f"Priority 3 - Recent activity bills: {len(recent_activity_bills)}")
            
            # Priority 4: Oldest updated bills (fill remaining slots)
            remaining_slots = max_bills - len(bill_ids)
            if remaining_slots > 0:
                oldest_bills = session.execute(text("""
                    SELECT bill_id FROM bills 
                    WHERE congress = :congress 
                    AND chamber = 'house'
                    AND bill_id NOT IN :existing_ids
                    ORDER BY last_updated ASC
                    LIMIT :limit
                """), {
                    'congress': congress,
                    'existing_ids': tuple(bill_ids) if bill_ids else ('',),
                    'limit': remaining_slots
                }).fetchall()
                
                for bill in oldest_bills:
                    bill_ids.add(bill.bill_id)
                
                logger.info(f"Priority 4 - Oldest updated bills: {len(oldest_bills)}")
            
            logger.info(f"Total bills selected for update: {len(bill_ids)}")
            return list(bill_ids)
    
    def update_bill_last_updated(self, bill_id: str):
        """Update the last_updated timestamp for a bill."""
        try:
            with get_db_session() as session:
                session.execute(text("""
                    UPDATE bills 
                    SET last_updated = NOW() 
                    WHERE bill_id = :bill_id
                """), {'bill_id': bill_id})
                session.commit()
        except Exception as e:
            logger.error(f"Failed to update last_updated for {bill_id}: {e}")
    
    def fetch_bill_from_congressgov(self, bill_id: str) -> Optional[Dict]:
        """Fetch bill data from Congress.gov API."""
        # Convert bill_id format: hr-1234-119 -> 119/hr/1234
        try:
            parts = bill_id.split('-')
            if len(parts) >= 3:
                bill_type = parts[0]
                bill_number = parts[1]
                congress = parts[2]
                congressgov_id = f"{congress}/{bill_type}/{bill_number}"
            else:
                return None
        except:
            return None
        
        url = f"https://api.congress.gov/v3/bill/{congressgov_id}"
        headers = {'X-API-Key': self.congressgov_api_key}
        
        try:
            response = self.session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                bill_data = response.json()
                
                # Also fetch subjects if this is new bill data
                subjects = self.fetch_bill_subjects(congressgov_id)
                if subjects:
                    bill_data['subjects'] = subjects
                
                return bill_data
            elif response.status_code == 429:
                logger.warning(f"Rate limit hit for {bill_id}")
                return "RATE_LIMIT"
            else:
                logger.warning(f"Failed to fetch {bill_id}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching {bill_id}: {e}")
        
        return None
    
    def fetch_bill_subjects(self, congressgov_id: str) -> List[str]:
        """Fetch bill subjects from Congress.gov API."""
        subjects = []
        subjects_url = f"https://api.congress.gov/v3/bill/{congressgov_id}/subjects"
        headers = {'X-API-Key': self.congressgov_api_key}
        
        try:
            response = self.session.get(subjects_url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'subjects' in data and 'legislativeSubjects' in data['subjects']:
                    for subject in data['subjects']['legislativeSubjects']:
                        if 'name' in subject:
                            subjects.append(subject['name'])
                logger.debug(f"Found {len(subjects)} subjects for {congressgov_id}")
            else:
                logger.debug(f"Failed to fetch subjects for {congressgov_id}: {response.status_code}")
        except Exception as e:
            logger.debug(f"Error fetching subjects for {congressgov_id}: {e}")
        
        return subjects
    
    def update_bill_data(self, bill_id: str, bill_data: Dict) -> bool:
        """Update bill sponsor, cosponsors, policy area, and subjects data."""
        try:
            with get_db_session() as session:
                # Update sponsor if available
                sponsor_updated = False
                if 'sponsors' in bill_data.get('bill', {}):
                    sponsors = bill_data['bill']['sponsors']
                    if sponsors and len(sponsors) > 0:
                        sponsor_bioguide = sponsors[0].get('bioguideId')
                        if sponsor_bioguide:
                            session.execute(text("""
                                UPDATE bills 
                                SET sponsor_bioguide = :sponsor_bioguide 
                                WHERE bill_id = :bill_id
                            """), {
                                'sponsor_bioguide': sponsor_bioguide,
                                'bill_id': bill_id
                            })
                            sponsor_updated = True
                
                # Update policy area if available
                policy_area_updated = False
                if 'policyArea' in bill_data.get('bill', {}):
                    policy_area = bill_data['bill']['policyArea'].get('name')
                    if policy_area:
                        session.execute(text("""
                            UPDATE bills 
                            SET policy_area = :policy_area 
                            WHERE bill_id = :bill_id
                        """), {
                            'policy_area': policy_area,
                            'bill_id': bill_id
                        })
                        policy_area_updated = True
                        logger.debug(f"Updated policy area for {bill_id}: {policy_area}")
                
                # Update subjects if available
                subjects_updated = False
                if 'subjects' in bill_data:
                    subjects = bill_data['subjects']
                    if subjects:
                        # Delete existing subjects first
                        session.execute(text("""
                            DELETE FROM bill_subjects WHERE bill_id = :bill_id
                        """), {'bill_id': bill_id})
                        
                        # Add new subjects
                        for subject in subjects:
                            bill_subject = BillSubject(
                                bill_id=bill_id,
                                subject_term=subject
                            )
                            session.add(bill_subject)
                        
                        subjects_updated = True
                        logger.debug(f"Updated {len(subjects)} subjects for {bill_id}")
                
                # Update last_updated timestamp
                session.execute(text("""
                    UPDATE bills 
                    SET last_updated = NOW() 
                    WHERE bill_id = :bill_id
                """), {'bill_id': bill_id})
                
                session.commit()
                
                # Log what was updated
                updates = []
                if sponsor_updated:
                    updates.append("sponsor")
                if policy_area_updated:
                    updates.append("policy_area")
                if subjects_updated:
                    updates.append(f"{len(subjects)} subjects")
                
                if updates:
                    logger.info(f"Updated {bill_id}: {', '.join(updates)}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to update bill data for {bill_id}: {e}")
            return False
    
    def enhanced_daily_update(self, congress: int = 119, max_bills: int = 100):
        """Run enhanced daily update with better bill distribution."""
        logger.info(f"Starting enhanced daily update for Congress {congress}")
        
        # Get bills to update using enhanced selection
        bills_to_update = self.get_bills_to_update_enhanced(congress, max_bills)
        
        if not bills_to_update:
            logger.info("No bills to update")
            return True
        
        updated_count = 0
        rate_limit_hit = False
        
        for i, bill_id in enumerate(bills_to_update):
            logger.info(f"Updating bill {i+1}/{len(bills_to_update)}: {bill_id}")
            
            # Fetch from API
            bill_data = self.fetch_bill_from_congressgov(bill_id)
            
            if bill_data == "RATE_LIMIT":
                logger.warning("Rate limit hit! Stopping update.")
                rate_limit_hit = True
                break
            
            if bill_data and 'bill' in bill_data:
                if self.update_bill_data(bill_id, bill_data):
                    updated_count += 1
            else:
                # Even if no data, update the last_updated timestamp
                self.update_bill_last_updated(bill_id)
            
            # Rate limiting
            time.sleep(2)
        
        logger.info(f"Enhanced daily update completed:")
        logger.info(f"  - Bills processed: {len(bills_to_update)}")
        logger.info(f"  - Bills updated: {updated_count}")
        logger.info(f"  - Rate limit hit: {rate_limit_hit}")
        
        return not rate_limit_hit

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced daily update with better bill distribution')
    parser.add_argument('--congress', type=int, default=119, help='Congress number (default: 119)')
    parser.add_argument('--max-bills', type=int, default=100, help='Maximum bills to process (default: 100)')
    parser.add_argument('--api-key', help='Congress.gov API key')
    
    args = parser.parse_args()
    
    # Set API key if provided
    if args.api_key:
        os.environ['CONGRESSGOV_API_KEY'] = args.api_key
    
    updater = EnhancedDailySponsorsCosponsorsUpdater()
    success = updater.enhanced_daily_update(args.congress, args.max_bills)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
