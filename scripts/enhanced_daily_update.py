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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from sqlalchemy import text, or_, and_

# Add scripts to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))
from setup_db import Bill, BillSubject, Member

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
        # Robust retry/backoff for transient errors and timeouts
        retries = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)
    
    def get_bills_to_update_enhanced(self, congress: int = 119, max_bills: int = 100, days_back: int = 7) -> List[str]:
        """Prioritize recently introduced 'stub' bills, then fall back to stale items."""
        
        with get_db_session() as session:
            selected: List[str] = []

            # 1) Recent 'stubs' (missing key fields) in the last N days
            recent_stubs = session.execute(text("""
                SELECT bill_id FROM bills 
                WHERE congress = :congress 
                  AND (
                        title IS NULL OR title = ''
                     OR policy_area IS NULL
                     OR sponsor_bioguide IS NULL
                  )
                  AND (
                        introduced_date IS NULL
                     OR introduced_date >= DATE_SUB(CURDATE(), INTERVAL :days_back DAY)
                  )
                ORDER BY (introduced_date IS NULL) ASC, introduced_date DESC
                LIMIT :limit
            """), {
                'congress': congress,
                'days_back': days_back,
                'limit': max_bills
            }).fetchall()
            
            selected.extend([r.bill_id for r in recent_stubs])

            # 2) If room remains, include other missing/stale items
            remaining = max_bills - len(selected)
            if remaining > 0:
                stale_or_missing = session.execute(text("""
                    SELECT bill_id FROM bills
                    WHERE congress = :congress
                      AND (
                            title IS NULL OR title = ''
                         OR policy_area IS NULL
                         OR sponsor_bioguide IS NULL
                         OR updated_at IS NULL
                         OR updated_at < DATE_SUB(NOW(), INTERVAL 7 DAY)
                      )
                    ORDER BY updated_at IS NULL DESC, updated_at ASC, bill_id ASC
                    LIMIT :limit
                """), {
                    'congress': congress,
                    'limit': remaining
                }).fetchall()

                for r in stale_or_missing:
                    if r.bill_id not in selected:
                        selected.append(r.bill_id)

            logger.info(f"Selected {len(selected)} bills for update (recent stubs first, then stale/missing)")
            return selected
    
    def discover_new_bills(self, congress: int = 119, days_back: int = 7) -> List[str]:
        """Discover new bills in the last N days using a date-filtered query.

        Uses the root /v3/bill endpoint with fromDateTime to ensure we get the most
        recently updated/introduced items without scanning thousands of older pages.
        """
        logger.info(f"Discovering new bills for Congress {congress} (last {days_back} days)")

        cutoff_date = date.today() - timedelta(days=days_back)
        # Congress.gov expects Zulu time format: YYYY-MM-DDTHH:MM:SSZ
        from_dt = f"{cutoff_date.strftime('%Y-%m-%d')}T00:00:00Z"
        new_bill_ids: List[str] = []

        # Get existing bill IDs to avoid duplicates
        with get_db_session() as session:
            existing_bills = {bill.bill_id for bill in session.query(Bill).filter(
                Bill.congress == congress
            ).all()}

        logger.info(f"Found {len(existing_bills)} existing bills in database")

        base_url = "https://api.congress.gov/v3/bill"
        headers = {'X-API-Key': self.congressgov_api_key}

        # We page through results ordered by updateDate desc (server default when fromDateTime is provided)
        offset = 0
        page_limit = 250  # higher limit to reduce pagination churn
        hard_cap = 1000   # do not scan forever
        scanned = 0

        try:
            while scanned < hard_cap and len(new_bill_ids) < 200:
                params = {
                    'format': 'json',
                    'limit': page_limit,
                    'offset': offset,
                    'fromDateTime': from_dt,
                    'congress': congress
                }
                resp = self.session.get(base_url, headers=headers, params=params, timeout=25)
                logger.info(f"Discovery API status: {resp.status_code} (offset={offset})")
                if resp.status_code != 200:
                    logger.error(f"Discovery API error: {resp.status_code} - {resp.text}")
                    break

                data = resp.json()
                items = data.get('bills', []) or []
                logger.info(f"Discovery returned {len(items)} items (offset={offset})")
                if not items:
                    break

                added_this_page = 0
                for item in items:
                    try:
                        item_congress = int(item.get('congress')) if item.get('congress') is not None else None
                    except Exception:
                        item_congress = None

                    if item_congress != int(congress):
                        continue

                    bill_type = (item.get('type') or '').lower()
                    bill_number = item.get('number')
                    if not bill_type or not bill_number:
                        continue

                    our_bill_id = f"{bill_type}-{bill_number}-{congress}"
                    if our_bill_id not in existing_bills and our_bill_id not in new_bill_ids:
                        new_bill_ids.append(our_bill_id)
                        added_this_page += 1

                scanned += len(items)
                offset += page_limit

                # If nothing new appeared on this page, but results exist, continue one more page
                if added_this_page == 0 and len(items) < page_limit:
                    # Likely reached the end of the recent window
                    break

                time.sleep(0.3)
        except Exception as e:
            logger.error(f"Error during discovery: {e}")

        logger.info(f"Discovered {len(new_bill_ids)} new bills")
        return new_bill_ids

    def add_new_bills_to_database(self, bill_ids: List[str], congress: int) -> int:
        """Add new bills to the database."""
        added_count = 0
        
        for bill_id in bill_ids:
            try:
                # Fetch bill data from Congress.gov
                bill_data = self.fetch_bill_from_congressgov(bill_id)
                
                if bill_data and bill_data != "RATE_LIMIT":
                    # Add to database
                    with get_db_session() as session:
                        # Check if bill already exists (race condition protection)
                        existing = session.query(Bill).filter(Bill.bill_id == bill_id).first()
                        if not existing:
                            # Extract fields from bill_id and full API payload
                            parts = bill_id.split('-')
                            bill_number = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else None
                            bill_type_from_id = parts[0] if parts else ''
                            chamber = 'house' if bill_type_from_id.startswith('h') else 'senate'

                            bill_info = bill_data.get('bill', {}) if isinstance(bill_data, dict) else {}
                            # Truncate excessively long titles to fit DB column
                            raw_title = bill_info.get('title') or bill_data.get('title', '')
                            title = raw_title[:1000] if isinstance(raw_title, str) else raw_title
                            introduced_raw = bill_info.get('introducedDate') or bill_data.get('introducedDate')
                            introduced_date = datetime.strptime(introduced_raw, '%Y-%m-%d').date() if introduced_raw else None
                            sponsors = bill_info.get('sponsors') or bill_data.get('sponsors') or []
                            sponsor_bioguide = sponsors[0].get('bioguideId') if sponsors else None
                            # Ensure FK safety: only set sponsor if present in members
                            if sponsor_bioguide:
                                sponsor_exists = session.query(Member).filter(Member.member_id_bioguide == sponsor_bioguide).first()
                                if not sponsor_exists:
                                    sponsor_bioguide = None
                            policy_area_name = None
                            if isinstance(bill_info.get('policyArea'), dict):
                                policy_area_name = bill_info['policyArea'].get('name')

                            bill = Bill(
                                bill_id=bill_id,
                                congress=congress,
                                chamber=chamber,
                                title=title,
                                type=bill_type_from_id,
                                number=bill_number,
                                introduced_date=introduced_date,
                                sponsor_bioguide=sponsor_bioguide,
                                policy_area=policy_area_name,
                                updated_at=datetime.now()
                            )
                            session.add(bill)
                            session.commit()
                            added_count += 1
                            logger.info(f"Added new bill: {bill_id} ({title[:80]})")
                        else:
                            # Quiet duplicate message to reduce noise
                            pass
                
                # Rate limiting
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error adding bill {bill_id}: {e}")
                continue
        
        return added_count
    
    def update_bill_last_updated(self, bill_id: str):
        """Update the updated_at timestamp for a bill."""
        try:
            with get_db_session() as session:
                session.execute(text("""
                    UPDATE bills 
                    SET updated_at = NOW() 
                    WHERE bill_id = :bill_id
                """), {'bill_id': bill_id})
                session.commit()
        except Exception as e:
            logger.error(f"Failed to update updated_at for {bill_id}: {e}")
    
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
        """Update bill sponsor, cosponsors, policy area, subjects data, and core fields for stubs."""
        try:
            with get_db_session() as session:
                # First, check if this is a stub bill that needs core field backfill
                bill_info = bill_data.get('bill', {}) if isinstance(bill_data, dict) else {}
                core_fields_updated = False
                
                # Check if we have core field data to backfill
                # Truncate excessively long titles to fit DB column
                raw_title = bill_info.get('title') or bill_data.get('title', '')
                title = raw_title[:1000] if isinstance(raw_title, str) else raw_title
                introduced_raw = bill_info.get('introducedDate') or bill_data.get('introducedDate')
                introduced_date = datetime.strptime(introduced_raw, '%Y-%m-%d').date() if introduced_raw else None
                
                if title or introduced_date:
                    # Extract bill type and number from bill_id
                    parts = bill_id.split('-')
                    bill_type_from_id = parts[0] if parts else ''
                    bill_number = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else None
                    
                    # Update core fields if they're missing
                    update_fields = {}
                    if title:
                        update_fields['title'] = title
                    if bill_type_from_id:
                        update_fields['type'] = bill_type_from_id
                    if bill_number:
                        update_fields['number'] = bill_number
                    if introduced_date:
                        update_fields['introduced_date'] = introduced_date
                    
                    if update_fields:
                        set_clause = ', '.join([f"{field} = :{field}" for field in update_fields.keys()])
                        params = {'bill_id': bill_id}
                        params.update(update_fields)
                        
                        session.execute(text(f"""
                            UPDATE bills 
                            SET {set_clause}
                            WHERE bill_id = :bill_id
                        """), params)
                        core_fields_updated = True
                        logger.info(f"Backfilled core fields for {bill_id}: {', '.join(update_fields.keys())}")
                
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
                
                # Update updated_at timestamp
                session.execute(text("""
                    UPDATE bills 
                    SET updated_at = NOW() 
                    WHERE bill_id = :bill_id
                """), {'bill_id': bill_id})
                
                session.commit()
                
                # Log what was updated
                updates = []
                if core_fields_updated:
                    updates.append("core_fields")
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
    
    def enhanced_daily_update(self, congress: int = 119, max_bills: int = 100, days_back: int = 7):
        """Run enhanced daily update with better bill distribution."""
        logger.info(f"Starting enhanced daily update for Congress {congress}")
        
        # Step 1: Discover and add new bills
        new_bills_added = 0
        new_bill_ids = self.discover_new_bills(congress, days_back=days_back)
        if new_bill_ids:
            new_bills_added = self.add_new_bills_to_database(new_bill_ids, congress)
            logger.info(f"Added {new_bills_added} new bills to database")
        
        # Step 2: Get bills to update using enhanced selection
        bills_to_update = self.get_bills_to_update_enhanced(congress, max_bills, days_back)
        
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
        logger.info(f"  - New bills discovered: {len(new_bill_ids)}")
        logger.info(f"  - New bills added: {new_bills_added}")
        logger.info(f"  - Existing bills processed: {len(bills_to_update)}")
        logger.info(f"  - Existing bills updated: {updated_count}")
        logger.info(f"  - Rate limit hit: {rate_limit_hit}")
        
        return not rate_limit_hit

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced daily update with better bill distribution')
    parser.add_argument('--congress', type=int, default=119, help='Congress number (default: 119)')
    parser.add_argument('--max-bills', type=int, default=100, help='Maximum bills to process (default: 100)')
    parser.add_argument('--days-back', type=int, default=7, help='How many days back to consider for new bills (default: 7)')
    parser.add_argument('--api-key', help='Congress.gov API key')
    
    args = parser.parse_args()
    
    # Set API key if provided
    if args.api_key:
        os.environ['CONGRESSGOV_API_KEY'] = args.api_key
    
    updater = EnhancedDailySponsorsCosponsorsUpdater()
    success = updater.enhanced_daily_update(args.congress, args.max_bills, args.days_back)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
