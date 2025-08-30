#!/usr/bin/env python3
import sys, requests, json, time
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.database import get_db_session
from scripts.setup_db import Bill, Cosponsor, Member

def convert_bill_id_to_congressgov_format(bill_id):
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

def fetch_bill_cosponsors_congressgov(bill_id):
    """Fetch cosponsor data for a specific bill from Congress.gov API."""
    # Convert our bill ID to Congress.gov format
    congressgov_id = convert_bill_id_to_congressgov_format(bill_id)
    if not congressgov_id:
        print(f"Could not convert bill ID {bill_id} to Congress.gov format")
        return None
    
    # Congress.gov API endpoint
    url = f"https://api.congress.gov/v3/bill/{congressgov_id}"
    
    headers = {
        'X-API-Key': 'DEMO_KEY'  # Congress.gov also has a DEMO_KEY
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"Failed to fetch {congressgov_id} (from {bill_id}): {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching {congressgov_id} (from {bill_id}): {e}")
        return None

def load_cosponsors_for_bill_congressgov(bill_id, bill_data):
    """Load cosponsor data for a specific bill from Congress.gov data."""
    try:
        # Extract sponsor and cosponsors from Congress.gov data
        sponsor = None
        cosponsors = []
        
        # Look for sponsor information
        if 'bill' in bill_data and 'sponsors' in bill_data['bill']:
            sponsors = bill_data['bill']['sponsors']
            if sponsors and len(sponsors) > 0:
                sponsor = sponsors[0]  # Primary sponsor
        
        # Look for cosponsors
        if 'bill' in bill_data and 'cosponsors' in bill_data['bill']:
            cosponsors_data = bill_data['bill']['cosponsors']
            # Handle both list and string formats
            if isinstance(cosponsors_data, list):
                cosponsors = cosponsors_data
            elif isinstance(cosponsors_data, str):
                # If it's a string, it might be a URL or count
                print(f"Cosponsors field is string: {cosponsors_data}")
                cosponsors = []
            else:
                cosponsors = []
        else:
            cosponsors = []
        
        # Save to database
        with get_db_session() as s:
            # Check if bill exists
            bill = s.query(Bill).filter(Bill.bill_id == bill_id).first()
            if not bill:
                print(f"Bill {bill_id} not found in database, skipping")
                return
            
            # Load sponsor if found
            if sponsor:
                sponsor_bioguide = sponsor.get('bioguideId')
                if sponsor_bioguide:
                    # Check if sponsor exists in members table
                    member = s.query(Member).filter(Member.member_id_bioguide == sponsor_bioguide).first()
                    if member:
                        # Update bill with sponsor
                        bill.sponsor_id = sponsor_bioguide
                        print(f"Set sponsor for {bill_id}: {sponsor_bioguide}")
            
            # Load cosponsors
            for cosponsor in cosponsors:
                cosponsor_bioguide = cosponsor.get('bioguideId')
                if cosponsor_bioguide:
                    # Check if cosponsor exists in members table
                    member = s.query(Member).filter(Member.member_id_bioguide == cosponsor_bioguide).first()
                    if member:
                        # Check if cosponsorship already exists
                        existing = s.query(Cosponsor).filter(
                            Cosponsor.bill_id == bill_id,
                            Cosponsor.member_id_bioguide == cosponsor_bioguide
                        ).first()
                        
                        if not existing:
                            s.add(Cosponsor(
                                bill_id=bill_id,
                                member_id_bioguide=cosponsor_bioguide,
                                cosponsor_date=None  # We don't have this info from Congress.gov
                            ))
                            print(f"Added cosponsor for {bill_id}: {cosponsor_bioguide}")
            
            s.commit()
            
    except Exception as e:
        print(f"Error loading cosponsors for {bill_id}: {e}")

def test_congressgov_api():
    """Test the Congress.gov API to see what data is available."""
    print("Testing Congress.gov API...")
    
    # Test with a sample bill ID in our format
    test_bill_id = "hr-1-119"  # Our format
    
    data = fetch_bill_cosponsors_congressgov(test_bill_id)
    if data:
        print(f"Sample bill data keys: {list(data.keys())}")
        
        if 'bill' in data:
            bill_data = data['bill']
            print(f"Bill data keys: {list(bill_data.keys())}")
            
            # Look for sponsor/cosponsor fields
            if 'sponsors' in bill_data:
                print(f"Sponsors: {bill_data['sponsors']}")
            if 'cosponsors' in bill_data:
                print(f"Cosponsors: {bill_data['cosponsors']}")
        
        # Print first 500 chars of response
        print(f"Sample response: {json.dumps(data, indent=2)[:500]}...")
    else:
        print("No data returned from Congress.gov API")

def load_sample_cosponsors():
    """Load cosponsor data for a small sample of bills."""
    print("Loading cosponsor data from Congress.gov API...")
    
    with get_db_session() as s:
        # Get a small sample of bills
        bills = s.query(Bill).limit(5).all()
        print(f"Processing {len(bills)} sample bills...")
        
        loaded_count = 0
        
        for i, bill in enumerate(bills):
            print(f"Processing bill {i+1}/{len(bills)}: {bill.bill_id}")
            
            # Fetch bill data from Congress.gov
            bill_data = fetch_bill_cosponsors_congressgov(bill.bill_id)
            
            if bill_data:
                load_cosponsors_for_bill_congressgov(bill.bill_id, bill_data)
                loaded_count += 1
            
            # Rate limiting
            time.sleep(2)  # Wait 2 seconds between requests
        
        print(f"Completed loading cosponsors for {loaded_count} bills")

if __name__ == "__main__":
    # Test the API first
    test_congressgov_api()
    
    # Then load sample cosponsors
    load_sample_cosponsors()
