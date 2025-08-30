"""
GovInfo BILLSTATUS loader for congressional bill data.

This module handles the ingestion of bill data from GovInfo's BILLSTATUS bulk feed,
including sponsors, cosponsors, actions, and CRS subject terms.
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
import re
import io
import zipfile

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Bill, BillSubject, Cosponsor, Action, Amendment, Member

logger = logging.getLogger(__name__)

class GovInfoLoader:
    """Loader for GovInfo BILLSTATUS data."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('GOVINFO_API_KEY')
        self.base_url = "https://www.govinfo.gov/bulkdata/BILLSTATUS"
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({'X-API-KEY': self.api_key})

    def _list_bill_ids_from_zip(self, congress: int, bill_type: str) -> List[str]:
        """Preferred: download ZIP index and list XML entries to derive bill_ids."""
        zip_url = f"{self.base_url}/{congress}/{bill_type}/BILLSTATUS-{congress}-{bill_type}.zip"
        try:
            resp = self.session.get(zip_url, stream=True)
            resp.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                bill_ids: List[str] = []
                for name in zf.namelist():
                    # Expected like BILLSTATUS-119hr1234.xml or BILLSTATUS-119hjres12.xml
                    base = name.split('/')[-1]
                    if not base.lower().endswith('.xml'):
                        continue
                    lower = base.lower()
                    # Find the digits after bill_type
                    import re
                    m = re.search(rf'billstatus-{congress}{bill_type}(\d+)\.xml', lower)
                    if m:
                        num = int(m.group(1))
                        bill_ids.append(f"{bill_type}-{num}-{congress}")
                return bill_ids
        except Exception as e:
            logger.warning(f"Failed to read ZIP for {bill_type} in Congress {congress}: {e}")
            return []

    def _list_bill_ids_from_directory(self, congress: int, bill_type: str) -> List[str]:
        """Fallback: parse directory listing HTML to extract per-bill XML filenames.
        Returns bill_ids in format '{bill_type}-{number}-{congress}'."""
        url = f"{self.base_url}/{congress}/{bill_type}/"
        try:
            resp = self.session.get(url)
            resp.raise_for_status()
            import re
            bill_ids: List[str] = []
            # Match both with and without dash between congress and type
            for pat in [
                rf'href=\"BILLSTATUS-{congress}-{bill_type}(\d+)\.xml\"',
                rf'BILLSTATUS-{congress}{bill_type}(\d+)\.xml',
            ]:
                for digits in re.findall(pat, resp.text, flags=re.IGNORECASE):
                    try:
                        num = int(digits)
                        bid = f"{bill_type}-{num}-{congress}"
                        if bid not in bill_ids:
                            bill_ids.append(bid)
                    except Exception:
                        continue
            return bill_ids
        except Exception as e:
            logger.warning(f"Failed to list directory for {bill_type} in Congress {congress}: {e}")
            return []
    
    def get_congress_bills(self, congress: int, chamber: str = 'both') -> List[str]:
        """
        Get list of bill IDs for a specific Congress and chamber.
        """
        bills: List[str] = []
        
        house_types = ['hr', 'hjres', 'hconres', 'hres']
        senate_types = ['s', 'sjres', 'sconres', 'sres']
        target_types: List[str] = []
        if chamber in ['house', 'both']:
            target_types.extend(house_types)
        if chamber in ['senate', 'both']:
            target_types.extend(senate_types)
        
        for bill_type in target_types:
            # 1) Try ZIP bulk listing
            found = self._list_bill_ids_from_zip(congress, bill_type)
            if found:
                logger.info(f"Found {len(found)} {bill_type.upper()} bills in Congress {congress} via ZIP index")
                bills.extend(found)
                continue
            # 2) Try directory listing
            found = self._list_bill_ids_from_directory(congress, bill_type)
            if found:
                logger.info(f"Found {len(found)} {bill_type.upper()} bills in Congress {congress} via directory listing")
                bills.extend(found)
                continue
            # 3) Legacy index XML (often 404)
            url = f"{self.base_url}/{congress}/{bill_type}/BILLSTATUS-{congress}-{bill_type}.xml"
            try:
                response = self.session.get(url)
                response.raise_for_status()
                root = ET.fromstring(response.content)
                for bill in root.findall('.//bill'):
                    bill_id = bill.get('billId')
                    if bill_id:
                        bills.append(bill_id)
                logger.info(f"Found {len(bills)} {bill_type.upper()} bills in Congress {congress} via index XML")
            except Exception as e:
                logger.warning(f"Failed to fetch {bill_type} index XML: {e}")
        
        return bills
    
    def parse_bill_xml(self, xml_content: str) -> Dict:
        """
        Parse a single bill's XML content into structured data.
        
        Args:
            xml_content: XML string for a single bill
        
        Returns:
            Dictionary with parsed bill data
        """
        try:
            root = ET.fromstring(xml_content)
            bill_data = {}
            
            # Basic bill info
            bill = root.find('.//bill')
            if bill is not None:
                bill_data['bill_id'] = bill.get('billId', '')
                bill_data['congress'] = int(bill.get('congress', 0))
                bill_data['type'] = bill.get('type', '')
                bill_data['number'] = int(bill.get('number', 0))
                bill_data['chamber'] = bill.get('originChamber', '')
            
            # Title and summary
            title_elem = root.find('.//title')
            if title_elem is not None:
                bill_data['title'] = title_elem.text
            
            summary_elem = root.find('.//summary')
            if summary_elem is not None:
                bill_data['summary_short'] = summary_elem.text
            
            # Sponsor
            sponsor_elem = root.find('.//sponsor')
            if sponsor_elem is not None:
                bill_data['sponsor_bioguide'] = sponsor_elem.get('bioguideId')
            
            # Introduced date
            intro_elem = root.find('.//introducedDate')
            if intro_elem is not None and intro_elem.text:
                try:
                    bill_data['introduced_date'] = datetime.strptime(intro_elem.text, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            # Policy area
            policy_elem = root.find('.//policyArea')
            if policy_elem is not None:
                bill_data['policy_area'] = policy_elem.get('name')
            
            # Subjects
            subjects = []
            for subject_elem in root.findall('.//legislativeSubject'):
                subject_name = subject_elem.get('name')
                if subject_name:
                    subjects.append(subject_name)
            bill_data['subjects'] = subjects
            
            # Cosponsors
            cosponsors = []
            for cosponsor_elem in root.findall('.//cosponsor'):
                cosponsor_data = {
                    'bioguide_id': cosponsor_elem.get('bioguideId'),
                    'date': None,
                    'is_original': cosponsor_elem.get('isOriginalCosponsor', 'false').lower() == 'true'
                }
                
                date_elem = cosponsor_elem.find('.//cosponsorDate')
                if date_elem is not None and date_elem.text:
                    try:
                        cosponsor_data['date'] = datetime.strptime(date_elem.text, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                cosponsors.append(cosponsor_data)
            bill_data['cosponsors'] = cosponsors
            
            # Actions
            actions = []
            for action_elem in root.findall('.//item'):
                action_data = {
                    'action_code': action_elem.get('actionCode', ''),
                    'text': action_elem.text if action_elem.text else '',
                    'action_date': None,
                    'committee_code': None
                }
                
                date_elem = action_elem.find('.//actionDate')
                if date_elem is not None and date_elem.text:
                    try:
                        action_data['action_date'] = datetime.strptime(date_elem.text, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                # Extract committee info if present
                if 'committee' in action_data['text'].lower():
                    # Simple heuristic to extract committee code
                    words = action_data['text'].split()
                    for i, word in enumerate(words):
                        if word.upper() in ['HSJU', 'HSAS', 'HSBU', 'HSED', 'HSFA', 'HSGO', 'HSIF', 'HSII', 'HSJU', 'HSRU', 'HSSO', 'HSSY']:
                            action_data['committee_code'] = word.upper()
                            break
                
                actions.append(action_data)
            bill_data['actions'] = actions
            
            # Amendments
            amendments = []
            for amend_elem in root.findall('.//amendment'):
                amend_data = {
                    'amendment_id': amend_elem.get('amendmentId', ''),
                    'type': amend_elem.get('type', ''),
                    'purpose': '',
                    'sponsor_bioguide': None,
                    'introduced_date': None
                }
                
                purpose_elem = amend_elem.find('.//purpose')
                if purpose_elem is not None:
                    amend_data['purpose'] = purpose_elem.text or ''
                
                sponsor_elem = amend_elem.find('.//sponsor')
                if sponsor_elem is not None:
                    amend_data['sponsor_bioguide'] = sponsor_elem.get('bioguideId')
                
                intro_elem = amend_elem.find('.//introducedDate')
                if intro_elem is not None and intro_elem.text:
                    try:
                        amend_data['introduced_date'] = datetime.strptime(intro_elem.text, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                amendments.append(amend_data)
            bill_data['amendments'] = amendments
            
            return bill_data
            
        except Exception as e:
            logger.error(f"Failed to parse bill XML: {e}")
            return {}
    
    def load_bill(self, bill_id: str) -> bool:
        """
        Load a single bill into the database.
        
        Args:
            bill_id: Bill ID (supports 'hr123-119' and 'hr-123-119')
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Normalize bill_id into components
            # Accept either two-part (hr123-119) or three-part (hr-123-119)
            bill_type: Optional[str] = None
            bill_number: Optional[int] = None
            congress: Optional[int] = None

            parts = bill_id.split('-')
            if len(parts) == 2:
                left, cong = parts
                congress = int(cong)
                # Extract alpha prefix and numeric suffix (e.g., hr123)
                import re
                m = re.match(r"^([a-z]+)(\d+)$", left.lower())
                if not m:
                    logger.error(f"Invalid bill ID format: {bill_id}")
                    return False
                bill_type = m.group(1)
                bill_number = int(m.group(2))
            elif len(parts) == 3:
                bill_type = parts[0].lower()
                bill_number = int(parts[1])
                congress = int(parts[2])
            else:
                logger.error(f"Invalid bill ID format: {bill_id}")
                return False

            # Determine chamber
            if bill_type in ['hr', 'hjres', 'hconres', 'hres']:
                chamber = 'house'
            elif bill_type in ['s', 'sjres', 'sconres', 'sres']:
                chamber = 'senate'
            else:
                logger.error(f"Unsupported bill type: {bill_type}")
                return False

            # Use a normalized bill id consistently for DB rows
            normalized_bill_id = f"{bill_type}-{bill_number}-{congress}"

            # Fetch bill XML via GovInfo per-bill path
            # Format: .../BILLSTATUS/<congress>/<bill_type>/BILLSTATUS-<congress><bill_type><number>.xml
            xml_name = f"BILLSTATUS-{congress}{bill_type}{bill_number}.xml"
            url = f"{self.base_url}/{congress}/{bill_type}/{xml_name}"
            response = self.session.get(url)
            response.raise_for_status()

            # Parse bill data
            bill_data = self.parse_bill_xml(response.text)
            if not bill_data:
                return False

            # Store in database
            with get_db_session() as session:
                # Check if bill already exists
                existing_bill = session.query(Bill).filter(Bill.bill_id == normalized_bill_id).first()
                if existing_bill:
                    logger.debug(f"Bill {normalized_bill_id} already exists, skipping")
                    return True
                
                # Create bill record
                bill = Bill(
                    bill_id=normalized_bill_id,
                    congress=bill_data.get('congress') or congress,
                    chamber=chamber,
                    number=bill_data.get('number') or bill_number,
                    type=bill_data.get('type') or bill_type.upper(),
                    title=bill_data.get('title'),
                    introduced_date=bill_data.get('introduced_date'),
                    sponsor_bioguide=bill_data.get('sponsor_bioguide'),
                    policy_area=bill_data.get('policy_area'),
                    summary_short=bill_data.get('summary_short')
                )
                session.add(bill)
                # Ensure bill row is persisted before inserting child rows to satisfy FK constraints
                session.flush()

                # Add subjects
                for subject in bill_data.get('subjects', []):
                    bill_subject = BillSubject(
                        bill_id=normalized_bill_id,
                        subject_term=subject
                    )
                    session.add(bill_subject)

                # Add cosponsors
                for cosponsor_data in bill_data.get('cosponsors', []):
                    cosponsor = Cosponsor(
                        bill_id=normalized_bill_id,
                        member_id_bioguide=cosponsor_data['bioguide_id'],
                        date=cosponsor_data['date'],
                        is_original=cosponsor_data['is_original']
                    )
                    session.add(cosponsor)

                # Add actions (skip any without action_date to satisfy NOT NULL)
                for action_data in bill_data.get('actions', []):
                    if not action_data.get('action_date'):
                        continue
                    action = Action(
                        bill_id=normalized_bill_id,
                        action_date=action_data['action_date'],
                        action_code=(action_data.get('action_code') or 'UNKNOWN'),
                        text=(action_data.get('text') or None),
                        committee_code=(action_data.get('committee_code') or None)
                    )
                    session.add(action)

                # Add amendments
                for amend_data in bill_data.get('amendments', []):
                    amend_id = (amend_data.get('amendment_id') or '').strip()
                    if not amend_id:
                        # Skip amendments without a valid identifier
                        continue
                    amendment = Amendment(
                        amendment_id=amend_id,
                        bill_id=normalized_bill_id,
                        sponsor_bioguide=amend_data.get('sponsor_bioguide'),
                        type=amend_data.get('type'),
                        purpose=amend_data.get('purpose'),
                        introduced_date=amend_data.get('introduced_date')
                    )
                    session.add(amendment)

                session.commit()
                logger.info(f"Loaded bill {normalized_bill_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to load bill {bill_id}: {e}")
            return False
    
    def load_congress(self, congress: int, chamber: str = 'both', limit: Optional[int] = None):
        """
        Load all bills for a specific Congress.
        
        Args:
            congress: Congress number
            chamber: 'house', 'senate', or 'both'
            limit: Maximum number of bills to load (for testing)
        """
        logger.info(f"Loading bills for Congress {congress}, chamber: {chamber}")
        
        # Get list of bills
        bill_ids = self.get_congress_bills(congress, chamber)
        if limit:
            bill_ids = bill_ids[:limit]
        
        logger.info(f"Found {len(bill_ids)} bills to load")
        
        # Load bills with progress bar
        successful = 0
        failed = 0
        
        for bill_id in tqdm(bill_ids, desc=f"Loading Congress {congress} bills"):
            if self.load_bill(bill_id):
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Congress {congress} loading complete: {successful} successful, {failed} failed")

@click.command()
@click.option('--congress', type=int, required=True, help='Congress number (e.g., 119)')
@click.option('--chamber', type=click.Choice(['house', 'senate', 'both']), default='both', help='Chamber to load')
@click.option('--limit', type=int, help='Maximum number of bills to load (for testing)')
@click.option('--api-key', envvar='GOVINFO_API_KEY', help='GovInfo API key')
def main(congress: int, chamber: str, limit: Optional[int], api_key: Optional[str]):
    """Load bill data from GovInfo BILLSTATUS feed."""
    logging.basicConfig(level=logging.INFO)
    
    loader = GovInfoLoader(api_key=api_key)
    loader.load_congress(congress, chamber, limit)

if __name__ == '__main__':
    main()


