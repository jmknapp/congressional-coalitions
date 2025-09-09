#!/usr/bin/env python3
"""
FEC API client for downloading candidate data.
Handles authentication, rate limiting, and data retrieval from the FEC API.
"""

import os
import time
import logging
import requests
from typing import Dict, List, Optional, Generator
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class FECClient:
    """Client for interacting with the FEC API."""
    
    BASE_URL = "https://api.open.fec.gov/v1"
    RATE_LIMIT_DELAY = 1.0  # 1 second between requests to stay under 1000/hour limit
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize FEC client.
        
        Args:
            api_key: FEC API key. If not provided, will look for FEC_API_KEY env var.
        """
        self.api_key = api_key or os.getenv('FEC_API_KEY')
        if not self.api_key:
            raise ValueError("FEC API key is required. Set FEC_API_KEY environment variable or pass api_key parameter.")
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Congressional-Coalitions/1.0 (https://github.com/your-repo)',
            'Accept': 'application/json'
        })
        
        # Track last request time for rate limiting
        self._last_request_time = 0
    
    def _rate_limit(self):
        """Ensure we don't exceed rate limits."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - time_since_last)
        self._last_request_time = time.time()
    
    def _handle_rate_limit(self, retry_count: int = 0):
        """Handle rate limiting with exponential backoff."""
        if retry_count > 0:
            wait_time = min(60, 2 ** retry_count)  # Exponential backoff, max 60 seconds
            logger.warning(f"Rate limited. Waiting {wait_time} seconds before retry {retry_count}...")
            time.sleep(wait_time)
    
    def _make_request(self, endpoint: str, params: Dict, max_retries: int = 3) -> Dict:
        """
        Make a request to the FEC API with rate limiting and error handling.
        
        Args:
            endpoint: API endpoint (e.g., '/candidates')
            params: Query parameters
            max_retries: Maximum number of retries for rate limit errors
            
        Returns:
            JSON response data
            
        Raises:
            requests.RequestException: If the request fails
        """
        self._rate_limit()
        
        # Add API key to params
        params['api_key'] = self.api_key
        
        url = f"{self.BASE_URL}{endpoint}"
        
        for retry_count in range(max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=30)
                
                # Handle specific HTTP status codes
                if response.status_code == 422:
                    # 422 Unprocessable Entity - often means no data available
                    raise requests.RequestException(f"422 Client Error: Unprocessable Entity for url: {url}")
                elif response.status_code == 404:
                    # 404 Not Found - resource doesn't exist
                    raise requests.RequestException(f"404 Client Error: Not Found for url: {url}")
                elif response.status_code == 429:
                    # 429 Too Many Requests - rate limited
                    if retry_count < max_retries:
                        self._handle_rate_limit(retry_count)
                        continue  # Retry the request
                    else:
                        raise requests.RequestException(f"429 Client Error: Too Many Requests for url: {url}")
                
                response.raise_for_status()
                
                data = response.json()
                
                # Check for API errors
                if 'error' in data:
                    raise requests.RequestException(f"FEC API error: {data['error']}")
                
                return data
                
            except requests.RequestException as e:
                # Only log as error if it's not a 422 or 404 (which are expected for some candidates)
                if "422" in str(e) or "404" in str(e):
                    logger.debug(f"FEC API request returned no data: {e}")
                elif "429" in str(e) and retry_count < max_retries:
                    # Rate limit error, will retry
                    continue
                else:
                    logger.error(f"FEC API request failed: {e}")
                raise
    
    def get_candidates(self, 
                      office: str = 'H', 
                      election_year: int = 2026,
                      state: Optional[str] = None,
                      district: Optional[str] = None,
                      party: Optional[str] = None,
                      per_page: int = 100) -> Generator[Dict, None, None]:
        """
        Get candidates from the FEC API.
        
        Args:
            office: Office type ('H' for House, 'S' for Senate, 'P' for President)
            election_year: Election year
            state: State abbreviation (optional)
            district: District number (optional)
            party: Party abbreviation (optional)
            per_page: Number of results per page (max 100)
            
        Yields:
            Candidate data dictionaries
        """
        params = {
            'office': office,
            'cycle': election_year,
            'per_page': min(per_page, 100),  # FEC API max is 100
            'sort': 'name',
            'sort_hide_null': 'false'
        }
        
        if state:
            params['state'] = state
        if district:
            params['district'] = district
        if party:
            params['party'] = party
        
        page = 1
        total_pages = None
        
        while True:
            params['page'] = page
            
            try:
                data = self._make_request('/candidates', params)
                
                # Set total pages on first request
                if total_pages is None:
                    total_pages = data.get('pagination', {}).get('pages', 1)
                    logger.info(f"Fetching {data.get('pagination', {}).get('count', 0)} candidates across {total_pages} pages")
                
                # Yield each candidate
                for candidate in data.get('results', []):
                    yield candidate
                
                # Check if we've reached the last page
                if page >= total_pages:
                    break
                    
                page += 1
                
            except requests.RequestException as e:
                logger.error(f"Failed to fetch page {page}: {e}")
                break
    
    def get_candidate_financials(self, candidate_id: str) -> Optional[Dict]:
        """
        Get financial summary for a specific candidate.
        
        Args:
            candidate_id: FEC candidate ID
            
        Returns:
            Financial data dictionary or None if not found
        """
        try:
            data = self._make_request('/candidates/totals', {
                'candidate_id': candidate_id,
                'per_page': 1,
                'sort': '-cycle'
            })
            
            results = data.get('results', [])
            if results:
                return results[0]  # Return most recent financial data
            return None
            
        except requests.RequestException as e:
            # Handle 422 errors gracefully - some candidates may not have financial data
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 422:
                    logger.debug(f"No financial data available for candidate {candidate_id}")
                    return None
                elif e.response.status_code == 404:
                    logger.debug(f"Candidate {candidate_id} not found in financial data")
                    return None
            
            logger.warning(f"Failed to fetch financials for candidate {candidate_id}: {e}")
            return None
    
    def get_house_candidates_2026(self, state: Optional[str] = None, include_financials: bool = True) -> List[Dict]:
        """
        Get all House candidates for 2026 election.
        
        Args:
            state: Optional state filter
            include_financials: Whether to fetch financial data (slower but more complete)
            
        Returns:
            List of candidate data dictionaries
        """
        candidates = []
        financial_data_count = 0
        missing_financial_data_count = 0
        
        try:
            for i, candidate in enumerate(self.get_candidates(office='H', election_year=2026, state=state), 1):
                # Show progress every 100 candidates
                if i % 100 == 0:
                    logger.info(f"Processing candidate {i}...")
                
                if include_financials:
                    # Get financial data for each candidate
                    financials = self.get_candidate_financials(candidate.get('candidate_id'))
                    
                    # Merge financial data into candidate record
                    if financials:
                        candidate.update({
                            'total_receipts': financials.get('receipts', 0),
                            'total_disbursements': financials.get('disbursements', 0),
                            'cash_on_hand': financials.get('cash_on_hand', 0),
                            'debts_owed': financials.get('debts_owed_by_committee', 0)
                        })
                        financial_data_count += 1
                    else:
                        # Set default values for candidates without financial data
                        candidate.update({
                            'total_receipts': 0,
                            'total_disbursements': 0,
                            'cash_on_hand': 0,
                            'debts_owed': 0
                        })
                        missing_financial_data_count += 1
                else:
                    # Set default values when not fetching financials
                    candidate.update({
                        'total_receipts': 0,
                        'total_disbursements': 0,
                        'cash_on_hand': 0,
                        'debts_owed': 0
                    })
                
                candidates.append(candidate)
                
        except Exception as e:
            logger.error(f"Error fetching House candidates for 2026: {e}")
            raise
        
        logger.info(f"Retrieved {len(candidates)} House candidates for 2026")
        if include_financials:
            logger.info(f"Financial data available for {financial_data_count} candidates")
            if missing_financial_data_count > 0:
                logger.info(f"Financial data missing for {missing_financial_data_count} candidates (this is normal)")
        
        return candidates
    
    def test_connection(self) -> bool:
        """
        Test the API connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Make a simple request to test the connection
            data = self._make_request('/candidates', {
                'office': 'H',
                'cycle': 2026,
                'per_page': 1
            })
            return True
        except Exception as e:
            logger.error(f"FEC API connection test failed: {e}")
            return False


def main():
    """Test the FEC client."""
    import sys
    import os
    
    # Add project root to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    # Test the client
    try:
        client = FECClient()
        
        if client.test_connection():
            print("✓ FEC API connection successful")
            
            # Test fetching a few candidates
            print("Fetching sample House candidates for 2026...")
            candidates = client.get_house_candidates_2026()
            
            if candidates:
                print(f"✓ Retrieved {len(candidates)} candidates")
                print("\nSample candidate:")
                sample = candidates[0]
                print(f"  Name: {sample.get('name', 'N/A')}")
                print(f"  Party: {sample.get('party', 'N/A')}")
                print(f"  State: {sample.get('state', 'N/A')}")
                print(f"  District: {sample.get('district', 'N/A')}")
                print(f"  Receipts: ${sample.get('total_receipts', 0):,.2f}")
            else:
                print("No candidates found")
        else:
            print("✗ FEC API connection failed")
            
    except Exception as e:
        print(f"Error testing FEC client: {e}")


if __name__ == "__main__":
    main()
