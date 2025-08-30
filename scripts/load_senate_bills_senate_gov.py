#!/usr/bin/env python3
"""
Senate.gov bill loader for congressional bill data.

This module handles the ingestion of Senate bill data directly from Senate.gov.
"""

import os
import sys
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
import re
import click

# Add project root src to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.utils.database import get_db_session
from scripts.setup_db import Bill, Member

logger = logging.getLogger(__name__)

class SenateBillLoader:
    """Loader for Senate bill data from Senate.gov."""
    
    def __init__(self):
        self.base_url = "https://www.senate.gov/legislative/LIS"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional Coalition Tracker/1.0'
        })

    def get_senate_bill_list(self, congress: int, session: int = 1) -> List[str]:
        """Get list of Senate bills for a specific Congress and session."""
        # Try different Senate.gov endpoints for bill lists
        endpoints = [
            f"{self.base_url}/legislation/bills_{congress}_{session}.xml",
            f"{self.base_url}/legislation/bills_{congress}.xml",
            f"{self.base_url}/legislation/senate_bills_{congress}_{session}.xml",
            f"{self.base_url}/legislation/senate_bills_{congress}.xml",
            f"{self.base_url}/legislation/bills_s_{congress}_{session}.xml",
            f"{self.base_url}/legislation/bills_s_{congress}.xml",
        ]
        
        bill_ids = []
        
        for url in endpoints:
            try:
                logger.info(f"Trying to get Senate bills from: {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                root = ET.fromstring(response.content)
                
                # Look for bill elements
                for bill_elem in root.findall('.//bill'):
                    bill_id = bill_elem.get('bill_id') or bill_elem.get('id')
                    if bill_id:
                        bill_ids.append(bill_id)
                
                # Also look for bill numbers in text
                if not bill_ids:
                    text = response.text
                    # Look for patterns like "S. 123" or "S123"
                    matches = re.findall(r'S\.?\s*(\d+)', text)
                    for match in matches:
                        bill_id = f"s-{match}-{congress}"
                        if bill_id not in bill_ids:
                            bill_ids.append(bill_id)
                
                if bill_ids:
                    logger.info(f"Found {len(bill_ids)} Senate bills from {url}")
                    break
                    
            except Exception as e:
                logger.warning(f"Failed to get bills from {url}: {e}")
                continue
        
        return bill_ids

    def get_senate_bill_data(self, bill_id: str) -> Optional[Dict]:
        """Get detailed data for a specific Senate bill."""
        # Parse bill_id to get components
        # Expected format: s-123-119
        parts = bill_id.split('-')
        if len(parts) != 3:
            logger.warning(f"Invalid bill_id format: {bill_id}")
            return None
            
        bill_type, bill_number, congress = parts
        
        # Try different Senate.gov endpoints for individual bills
        endpoints = [
            f"{self.base_url}/legislation/bills/{bill_id}.xml",
            f"{self.base_url}/legislation/bills/{congress}/{bill_type}/{bill_number}.xml",
            f"{self.base_url}/legislation/bills/{congress}/{bill_type}{bill_number}.xml",
        ]
        
        for url in endpoints:
            try:
                logger.info(f"Trying to get bill data from: {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                root = ET.fromstring(response.content)
                
                # Extract bill information
                bill_data = {
                    'bill_id': bill_id,
                    'congress': int(congress),
                    'chamber': 'senate',
                    'number': int(bill_number),
                    'type': bill_type,
                    'title': None,
                    'introduced_date': None,
                    'sponsor_bioguide': None,
                }
                
                # Extract title
                title_elem = root.find('.//title') or root.find('.//bill_title') or root.find('.//short_title')
                if title_elem is not None and title_elem.text:
                    bill_data['title'] = title_elem.text.strip()
                
                # Extract sponsor
                sponsor_elem = root.find('.//sponsor') or root.find('.//sponsor_id') or root.find('.//member_id')
                if sponsor_elem is not None and sponsor_elem.text:
                    bill_data['sponsor_bioguide'] = sponsor_elem.text.strip()
                
                # Extract introduced date
                date_elem = root.find('.//introduced_date') or root.find('.//date_introduced')
                if date_elem is not None and date_elem.text:
                    try:
                        bill_data['introduced_date'] = datetime.strptime(date_elem.text.strip(), '%Y-%m-%d').date()
                    except:
                        pass
                
                logger.info(f"Successfully parsed bill data for {bill_id}")
                return bill_data
                
            except Exception as e:
                logger.warning(f"Failed to get bill data from {url}: {e}")
                continue
        
        return None

    def create_placeholder_bill(self, bill_id: str) -> Dict:
        """Create a placeholder bill when detailed data is not available."""
        parts = bill_id.split('-')
        if len(parts) != 3:
            return None
            
        bill_type, bill_number, congress = parts
        
        return {
            'bill_id': bill_id,
            'congress': int(congress),
            'chamber': 'senate',
            'number': int(bill_number),
            'type': bill_type,
            'title': f"{bill_type.upper()} {bill_number} ({congress}th Congress)",
            'introduced_date': None,
            'sponsor_bioguide': None,
        }

    def load_senate_bills(self, congress: int, session: int = 1, limit: Optional[int] = None) -> int:
        """Load Senate bills for a specific Congress and session."""
        logger.info(f"Loading Senate bills for Congress {congress}, Session {session}")
        
        # Get list of bills
        bill_ids = self.get_senate_bill_list(congress, session)
        
        if limit:
            bill_ids = bill_ids[:limit]
            logger.info(f"Limited to {limit} bills for testing")
        
        logger.info(f"Found {len(bill_ids)} Senate bills to load")
        
        loaded_count = 0
        
        with get_db_session() as session_db:
            for bill_id in bill_ids:
                try:
                    # Check if bill already exists
                    existing = session_db.query(Bill).filter(Bill.bill_id == bill_id).first()
                    if existing:
                        logger.info(f"Bill {bill_id} already exists, skipping")
                        continue
                    
                    # Get detailed bill data
                    bill_data = self.get_senate_bill_data(bill_id)
                    
                    # If detailed data not available, create placeholder
                    if not bill_data:
                        bill_data = self.create_placeholder_bill(bill_id)
                    
                    if bill_data:
                        bill = Bill(**bill_data)
                        session_db.add(bill)
                        session_db.commit()
                        loaded_count += 1
                        logger.info(f"Loaded bill {bill_id} ({loaded_count}/{len(bill_ids)})")
                    else:
                        logger.warning(f"Failed to create bill data for {bill_id}")
                        
                except Exception as e:
                    logger.error(f"Error loading bill {bill_id}: {e}")
                    session_db.rollback()
                    continue
        
        logger.info(f"Successfully loaded {loaded_count} out of {len(bill_ids)} Senate bills")
        return loaded_count

@click.command()
@click.option('--congress', required=True, type=int, help='Congress number (e.g., 119)')
@click.option('--session', default=1, type=int, help='Session number (1 or 2)')
@click.option('--limit', type=int, help='Limit number of bills to load (for testing)')
def main(congress, session, limit):
    """Load Senate bills from Senate.gov."""
    
    loader = SenateBillLoader()
    loaded_count = loader.load_senate_bills(congress, session, limit)
    
    logger.info(f"Completed loading {loaded_count} Senate bills")

if __name__ == '__main__':
    main()
