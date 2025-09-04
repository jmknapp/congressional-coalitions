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
        """Get bills using simple sequential processing with last_updated tracking."""
        
        with get_db_session() as session:
            # Simple approach: get bills that need updates, ordered by bill_id
            # This ensures we process bills in a consistent order and pick up where we left off
            bills_to_update = session.execute(text("""
                SELECT bill_id FROM bills 
                WHERE congress = :congress 
                AND chamber = 'house'
                AND (policy_area IS NULL OR sponsor_bioguide IS NULL OR last_updated IS NULL OR last_updated < DATE_SUB(NOW(), INTERVAL 7 DAY))
                ORDER BY bill_id ASC
                LIMIT :limit
            """), {
                'congress': congress,
                'limit': max_bills
            }).fetchall()
            
            bill_ids = [bill.bill_id for bill in bills_to_update]
            logger.info(f"Selected {len(bill_ids)} bills for update (bills needing updates or stale data)")
            
            return bill_ids
    
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
                
                # Also fetch subjects and actions if this is new bill data
                subjects = self.fetch_bill_subjects(congressgov_id)
                if subjects:
                    bill_data['subjects'] = subjects
                
                actions = self.fetch_bill_actions(congressgov_id)
                if actions:
                    bill_data['actions'] = actions
                
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

    def fetch_bill_actions(self, congressgov_id: str) -> List[Dict]:
        """Fetch bill actions from Congress.gov API."""
        actions = []
        actions_url = f"https://api.congress.gov/v3/bill/{congressgov_id}/actions"
        headers = {'X-API-Key': self.congressgov_api_key}
        
        try:
            response = self.session.get(actions_url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'actions' in data:
                    for action in data['actions']:
                        actions.append({
                            'action_date': action.get('actionDate'),
                            'action_code': self._map_action_code(action.get('text', '')),
                            'text': action.get('text', ''),
                            'committee_code': action.get('committee', {}).get('systemCode', '') if action.get('committee') else None
                        })
                logger.debug(f"Found {len(actions)} actions for {congressgov_id}")
            else:
                logger.debug(f"Failed to fetch actions for {congressgov_id}: {response.status_code}")
        except Exception as e:
            logger.debug(f"Error fetching actions for {congressgov_id}: {e}")
        
        return actions

    def _map_action_code(self, action_text: str) -> str:
        """Map action text to standardized action codes."""
        text = action_text.upper()
        
        if 'PASSED' in text and 'HOUSE' in text:
            return 'PASSED_HOUSE'
        elif 'PASSED' in text and 'SENATE' in text:
            return 'PASSED_SENATE'
        elif 'ENACTED' in text or ('SIGNED' in text and 'PRESIDENT' in text):
            return 'ENACTED'
        elif 'VETOED' in text or 'RETURNED' in text or 'POCKET' in text:
            return 'VETOED'
        elif 'INTRODUCED' in text:
            return 'INTRODUCED'
        elif 'REFERRED' in text:
            return 'REFERRED'
        elif 'REPORTED' in text:
            return 'REPORTED'
        elif 'RECEIVED' in text and 'SENATE' in text:
            return 'RECEIVED_SENATE'
        elif 'RECEIVED' in text and 'HOUSE' in text:
            return 'RECEIVED_HOUSE'
        else:
            return 'OTHER'
    
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
                
                # Update actions if available
                actions_updated = False
                if 'actions' in bill_data:
                    actions = bill_data['actions']
                    if actions:
                        # Delete existing actions first
                        session.execute(text("""
                            DELETE FROM actions WHERE bill_id = :bill_id
                        """), {'bill_id': bill_id})
                        
                        # Add new actions
                        for action in actions:
                            session.execute(text("""
                                INSERT INTO actions (bill_id, action_date, action_code, text, committee_code)
                                VALUES (:bill_id, :action_date, :action_code, :text, :committee_code)
                            """), {
                                'bill_id': bill_id,
                                'action_date': action['action_date'],
                                'action_code': action['action_code'],
                                'text': action['text'],
                                'committee_code': action['committee_code']
                            })
                        
                        actions_updated = True
                        logger.debug(f"Updated {len(actions)} actions for {bill_id}")
                
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
                if actions_updated:
                    updates.append(f"{len(actions)} actions")
                
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
