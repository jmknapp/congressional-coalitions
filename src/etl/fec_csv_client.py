#!/usr/bin/env python3
"""
FEC CSV Client for downloading candidate data from CSV exports.
Handles CSV downloads, parsing, and data extraction from FEC website.
"""

import os
import sys
import logging
import requests
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
import io
import time

logger = logging.getLogger(__name__)

class FECCSVClient:
    """Client for downloading and parsing FEC candidate CSV data."""
    
    BASE_URL = "https://www.fec.gov/files/bulk-downloads"
    USER_AGENT = "Congressional-Coalitions/1.0 (https://github.com/your-repo)"
    
    def __init__(self):
        """Initialize the FEC CSV client."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'application/zip,application/octet-stream,*/*'
        })
        # Allow redirects
        self.session.max_redirects = 5
    
    def download_house_candidates_csv(self, election_year: int = 2026) -> List[Dict]:
        """
        Download House candidates CSV data from FEC bulk data files.
        
        Args:
            election_year: Election year to download
            
        Returns:
            List of candidate data dictionaries
        """
        try:
            # For 2026, we'll use the 2024 data as the most recent available
            # FEC typically releases data for the current cycle
            data_year = 2024 if election_year == 2026 else election_year
            
            # Construct the CSV download URL for candidate master file
            csv_url = f"{self.BASE_URL}/{data_year}/cn{data_year}.zip"
            
            logger.info(f"Downloading FEC House candidates CSV for {election_year} (using {data_year} data)...")
            logger.info(f"URL: {csv_url}")
            
            # Download the ZIP file
            response = self.session.get(csv_url, timeout=120)
            response.raise_for_status()
            
            # Extract and parse the CSV from ZIP
            import zipfile
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                # Find the CSV file in the ZIP
                csv_files = [f for f in zip_file.namelist() if f.endswith('.csv')]
                if not csv_files:
                    raise ValueError("No CSV files found in ZIP archive")
                
                csv_filename = csv_files[0]
                logger.info(f"Extracting CSV file: {csv_filename}")
                
                # Read the CSV content
                with zip_file.open(csv_filename) as csv_file:
                    csv_content = csv_file.read().decode('utf-8')
            
            logger.info(f"Downloaded {len(csv_content)} characters of CSV data")
            
            # Parse CSV using pandas
            df = pd.read_csv(io.StringIO(csv_content))
            logger.info(f"Parsed CSV with {len(df)} rows and {len(df.columns)} columns")
            
            # Filter for House candidates only
            if 'CAND_OFFICE' in df.columns:
                house_candidates = df[df['CAND_OFFICE'] == 'H']
                logger.info(f"Filtered to {len(house_candidates)} House candidates")
            else:
                house_candidates = df
                logger.warning("CAND_OFFICE column not found, using all candidates")
            
            # Convert to list of dictionaries
            candidates = house_candidates.to_dict('records')
            
            # Clean and standardize the data
            cleaned_candidates = []
            for candidate in candidates:
                cleaned = self._clean_candidate_data(candidate)
                if cleaned:
                    cleaned_candidates.append(cleaned)
            
            logger.info(f"Successfully processed {len(cleaned_candidates)} candidates")
            return cleaned_candidates
            
        except Exception as e:
            logger.error(f"Error downloading FEC CSV data: {e}")
            raise
    
    def _clean_candidate_data(self, candidate: Dict) -> Optional[Dict]:
        """
        Clean and standardize candidate data from CSV.
        
        Args:
            candidate: Raw candidate data from CSV
            
        Returns:
            Cleaned candidate data or None if invalid
        """
        try:
            # Extract and clean basic information using FEC bulk data column names
            candidate_id = str(candidate.get('CAND_ID', '')).strip()
            if not candidate_id:
                return None
            
            name = str(candidate.get('CAND_NAME', '')).strip()
            if not name:
                return None
            
            # Clean party information
            party = str(candidate.get('CAND_PTY_AFFILIATION', '')).strip().upper()
            if party in ['DEM', 'DEMOCRATIC']:
                party = 'DEM'
            elif party in ['REP', 'REPUBLICAN']:
                party = 'REP'
            elif party in ['IND', 'INDEPENDENT']:
                party = 'IND'
            elif party in ['GRN', 'GREEN']:
                party = 'GRN'
            elif party in ['LIB', 'LIBERTARIAN']:
                party = 'LIB'
            
            # Clean state and district
            state = str(candidate.get('CAND_ST', '')).strip().upper()
            district = candidate.get('CAND_DISTRICT', '')
            if pd.isna(district) or district == '' or district == '00':
                district = None
            else:
                try:
                    district = str(int(float(district)))  # Handle various number formats
                except (ValueError, TypeError):
                    district = str(district).strip() if district else None
            
            # Clean financial data
            def safe_float(value, default=0.0):
                if pd.isna(value) or value == '' or value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # Clean status information
            incumbent_challenge_status = str(candidate.get('INCUMBENT_CHALLENGER_STATUS', '')).strip()
            if not incumbent_challenge_status or incumbent_challenge_status == 'nan':
                incumbent_challenge_status = None
            
            candidate_status = str(candidate.get('CAND_STATUS', '')).strip()
            if not candidate_status or candidate_status == 'nan':
                candidate_status = 'Unknown'
            
            # Determine if candidate is active
            active = candidate_status.lower() not in ['withdrawn', 'suspended', 'terminated']
            
            # Clean committee information
            principal_committee_id = str(candidate.get('PRINCIPAL_COMMITTEE_ID', '')).strip()
            if not principal_committee_id or principal_committee_id == 'nan':
                principal_committee_id = None
            
            principal_committee_name = str(candidate.get('PRINCIPAL_COMMITTEE_NAME', '')).strip()
            if not principal_committee_name or principal_committee_name == 'nan':
                principal_committee_name = None
            
            # Build cleaned candidate data
            cleaned_candidate = {
                'candidate_id': candidate_id,
                'name': name,
                'party': party,
                'office': 'H',  # House candidates
                'state': state,
                'district': district,
                'election_year': int(candidate.get('CAND_ELECTION_YR', 2026)),
                'election_season': str(candidate.get('CAND_ELECTION_YR', '')).strip() or None,
                'incumbent_challenge_status': incumbent_challenge_status,
                'total_receipts': safe_float(candidate.get('total_receipts')),
                'total_disbursements': safe_float(candidate.get('total_disbursements')),
                'cash_on_hand': safe_float(candidate.get('cash_on_hand')),
                'debts_owed': safe_float(candidate.get('debts_owed_by_committee')),
                'principal_committee_id': principal_committee_id,
                'principal_committee_name': principal_committee_name,
                'active': active,
                'candidate_status': candidate_status,
                'last_fec_update': datetime.utcnow(),
                'raw_fec_data': str(candidate)  # Store raw data for debugging
            }
            
            return cleaned_candidate
            
        except Exception as e:
            logger.error(f"Error cleaning candidate data: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test the CSV download connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try to download the 2024 candidate master file
            test_url = f"{self.BASE_URL}/2024/cn2024.zip"
            response = self.session.get(test_url, timeout=30)
            response.raise_for_status()
            
            # Check if we got a ZIP file
            if len(response.content) > 1000:  # Should have at least some ZIP content
                return True
            return False
            
        except Exception as e:
            logger.error(f"FEC CSV connection test failed: {e}")
            return False


def main():
    """Test the FEC CSV client."""
    import sys
    import os
    
    # Add project root to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    # Test the client
    try:
        client = FECCSVClient()
        
        if client.test_connection():
            print("✓ FEC CSV connection successful")
            
            # Test downloading data
            print("Downloading sample House candidates for 2026...")
            candidates = client.download_house_candidates_csv(2026)
            
            if candidates:
                print(f"✓ Retrieved {len(candidates)} candidates")
                print("\nSample candidate:")
                sample = candidates[0]
                print(f"  Name: {sample.get('name', 'N/A')}")
                print(f"  Party: {sample.get('party', 'N/A')}")
                print(f"  State: {sample.get('state', 'N/A')}")
                print(f"  District: {sample.get('district', 'N/A')}")
                print(f"  Receipts: ${sample.get('total_receipts', 0):,.2f}")
                print(f"  Cash on Hand: ${sample.get('cash_on_hand', 0):,.2f}")
            else:
                print("No candidates found")
        else:
            print("✗ FEC CSV connection failed")
            
    except Exception as e:
        print(f"Error testing FEC CSV client: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
