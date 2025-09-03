#!/usr/bin/env python3
"""
Backfill missing policy areas and subjects for existing bills using Congress.gov API.
"""

import os
import sys
import time
import logging
import argparse
from typing import Dict, Optional, List
import requests
from sqlalchemy import text

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.database import get_db_session
# Add scripts to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__)))
from setup_db import Bill, BillSubject

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MetadataBackfiller:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': api_key})
        
    def fetch_bill_metadata(self, bill_id: str) -> Optional[Dict]:
        """Fetch bill metadata from Congress.gov API."""
        # Convert bill_id format: hr-1234-119 -> 119/hr/1234
        try:
            parts = bill_id.split('-')
            if len(parts) >= 3:
                bill_type = parts[0]
                bill_number = parts[1]
                congress = parts[2]
                congressgov_id = f"{congress}/{bill_type}/{bill_number}"
            else:
                logger.warning(f"Invalid bill_id format: {bill_id}")
                return None
        except Exception as e:
            logger.error(f"Error parsing bill_id {bill_id}: {e}")
            return None
        
        # Fetch main bill data
        bill_url = f"https://api.congress.gov/v3/bill/{congressgov_id}"
        try:
            response = self.session.get(bill_url, timeout=30)
            if response.status_code == 200:
                bill_data = response.json()
                
                # Extract policy area
                policy_area = None
                if 'policyArea' in bill_data.get('bill', {}):
                    policy_area = bill_data['bill']['policyArea'].get('name')
                
                # Fetch subjects
                subjects = self.fetch_bill_subjects(congressgov_id)
                
                return {
                    'policy_area': policy_area,
                    'subjects': subjects
                }
            elif response.status_code == 429:
                logger.warning(f"Rate limit hit for {bill_id}, sleeping...")
                time.sleep(10)
                return "RATE_LIMIT"
            else:
                logger.warning(f"Failed to fetch {bill_id}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching bill {bill_id}: {e}")
            return None
    
    def fetch_bill_subjects(self, congressgov_id: str) -> List[str]:
        """Fetch bill subjects from Congress.gov API."""
        subjects = []
        subjects_url = f"https://api.congress.gov/v3/bill/{congressgov_id}/subjects"
        
        try:
            response = self.session.get(subjects_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'subjects' in data and 'legislativeSubjects' in data['subjects']:
                    for subject in data['subjects']['legislativeSubjects']:
                        if 'name' in subject:
                            subjects.append(subject['name'])
                logger.info(f"Found {len(subjects)} subjects for {congressgov_id}")
            else:
                logger.warning(f"Failed to fetch subjects for {congressgov_id}: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching subjects for {congressgov_id}: {e}")
        
        return subjects
    
    def update_bill_metadata(self, bill_id: str, policy_area: Optional[str], subjects: List[str]) -> bool:
        """Update bill metadata in database."""
        try:
            with get_db_session() as session:
                # Update policy area
                if policy_area:
                    session.execute(text("""
                        UPDATE bills 
                        SET policy_area = :policy_area 
                        WHERE bill_id = :bill_id
                    """), {
                        'policy_area': policy_area,
                        'bill_id': bill_id
                    })
                    logger.debug(f"Updated policy area for {bill_id}: {policy_area}")
                
                # Delete existing subjects
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
                
                session.commit()
                logger.debug(f"Updated {len(subjects)} subjects for {bill_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating metadata for {bill_id}: {e}")
            return False
    
    def backfill_metadata(self, congress: int = 119, limit: Optional[int] = None, skip_existing: bool = True):
        """Backfill metadata for bills missing policy areas."""
        with get_db_session() as session:
            # Get bills missing policy area
            query = """
                SELECT bill_id 
                FROM bills 
                WHERE congress = :congress 
                AND (policy_area IS NULL OR policy_area = '')
                ORDER BY bill_id
            """
            if limit:
                query += f" LIMIT {limit}"
            
            result = session.execute(text(query), {'congress': congress})
            bill_ids = [row[0] for row in result.fetchall()]
        
        logger.info(f"Found {len(bill_ids)} bills missing policy area metadata")
        
        processed = 0
        updated = 0
        for bill_id in bill_ids:
            try:
                logger.info(f"Processing {bill_id} ({processed + 1}/{len(bill_ids)})")
                
                metadata = self.fetch_bill_metadata(bill_id)
                if metadata == "RATE_LIMIT":
                    logger.warning("Rate limit hit, sleeping for 30 seconds...")
                    time.sleep(30)
                    metadata = self.fetch_bill_metadata(bill_id)
                
                if metadata and isinstance(metadata, dict):
                    policy_area = metadata.get('policy_area')
                    subjects = metadata.get('subjects', [])
                    
                    if policy_area or subjects:
                        success = self.update_bill_metadata(bill_id, policy_area, subjects)
                        if success:
                            updated += 1
                            logger.info(f"✅ Updated {bill_id}: {policy_area}, {len(subjects)} subjects")
                        else:
                            logger.error(f"❌ Failed to update {bill_id}")
                    else:
                        logger.info(f"⚠️  No metadata found for {bill_id}")
                else:
                    logger.warning(f"⚠️  No response for {bill_id}")
                
                processed += 1
                
                # Rate limiting
                time.sleep(0.5)  # Be gentle with the API
                
            except Exception as e:
                logger.error(f"Error processing {bill_id}: {e}")
                processed += 1
                continue
        
        logger.info(f"Completed: {processed} processed, {updated} updated with metadata")

def main():
    parser = argparse.ArgumentParser(description='Backfill bill metadata from Congress.gov API')
    parser.add_argument('--congress', type=int, default=119, help='Congress number (default: 119)')
    parser.add_argument('--limit', type=int, help='Limit number of bills to process (for testing)')
    parser.add_argument('--api-key', required=True, help='Congress.gov API key')
    
    args = parser.parse_args()
    
    logger.info(f"Starting metadata backfill for Congress {args.congress}")
    
    backfiller = MetadataBackfiller(args.api_key)
    backfiller.backfill_metadata(args.congress, args.limit)
    
    logger.info("Metadata backfill completed!")

if __name__ == '__main__':
    main()
