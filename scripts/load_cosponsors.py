#!/usr/bin/env python3
import sys, requests, json, time
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.utils.database import get_db_session
from scripts.setup_db import Bill, Cosponsor, Member

def convert_bill_id_to_govinfo_format(bill_id):
    """Convert our bill ID format to GovInfo format."""
    # Our format: "hr-1-119" -> GovInfo format: "BILLSTATUS-119hr1"
    try:
        parts = bill_id.split('-')
        if len(parts) >= 3:
            bill_type = parts[0]  # hr, s, hjres, etc.
            bill_number = parts[1]  # 1, 2, etc.
            congress = parts[2]  # 119, 118, etc.
            
            # Convert to GovInfo format
            govinfo_id = f"BILLSTATUS-{congress}{bill_type}{bill_number}"
            return govinfo_id
    except:
        pass
    return None

def fetch_bill_cosponsors(bill_id):
    """Fetch cosponsor data for a specific bill from GovInfo."""
    # Convert our bill ID to GovInfo format
    govinfo_id = convert_bill_id_to_govinfo_format(bill_id)
    if not govinfo_id:
        print(f"Could not convert bill ID {bill_id} to GovInfo format")
        return None
    
    # GovInfo BILLSTATUS endpoint
    url = f"https://api.govinfo.gov/packages/{govinfo_id}/summary"
    
    headers = {
        'X-Api-Key': 'DEMO_KEY'  # Use DEMO_KEY for testing, or get a real key from https://api.govinfo.gov/
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            if response.status_code == 429:
                print(f"Rate limit exceeded for {govinfo_id} (from {bill_id})")
                return "429"  # Special return value for rate limit
            else:
                print(f"Failed to fetch {govinfo_id} (from {bill_id}): {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching {govinfo_id} (from {bill_id}): {e}")
        return None

def load_cosponsors_for_bill(bill_id, bill_data):
    """Load cosponsor data for a specific bill."""
    try:
        # Extract sponsor and cosponsors from bill data
        sponsor = None
        cosponsors = []
        
        # Look for sponsor information
        if 'sponsors' in bill_data:
            sponsors = bill_data['sponsors']
            if sponsors and len(sponsors) > 0:
                sponsor = sponsors[0]  # Primary sponsor
        
        # Look for cosponsors
        if 'cosponsors' in bill_data:
            cosponsors = bill_data['cosponsors']
        
        # If no explicit cosponsors field, check other fields
        if not cosponsors and 'cosponsor' in bill_data:
            cosponsors = [bill_data['cosponsor']]
        
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
                                cosponsor_date=None  # We don't have this info from summary
                            ))
                            print(f"Added cosponsor for {bill_id}: {cosponsor_bioguide}")
            
            s.commit()
            
    except Exception as e:
        print(f"Error loading cosponsors for {bill_id}: {e}")

def load_all_cosponsors():
    """Load cosponsor data for all bills in the database."""
    print("Loading cosponsor data from GovInfo...")
    
    with get_db_session() as s:
        # Get all bills
        bills = s.query(Bill).all()
        print(f"Found {len(bills)} bills to process")
        
        # For testing, only process first 10 bills
        test_bills = bills[:10]
        print(f"Processing first {len(test_bills)} bills for testing...")
        
        loaded_count = 0
        rate_limit_count = 0
        
        for i, bill in enumerate(test_bills):
            print(f"Processing bill {i+1}/{len(test_bills)}: {bill.bill_id}")
            
            # Fetch bill data from GovInfo
            bill_data = fetch_bill_cosponsors(bill.bill_id)
            
            if bill_data:
                load_cosponsors_for_bill(bill.bill_id, bill_data)
                loaded_count += 1
            elif "429" in str(bill_data):  # Rate limit error
                rate_limit_count += 1
                print(f"Rate limit hit, stopping processing")
                break
            
            # Rate limiting - GovInfo DEMO_KEY has very strict limits
            time.sleep(5)  # Wait 5 seconds between requests
        
        print(f"Completed loading cosponsors for {loaded_count} bills")
        if rate_limit_count > 0:
            print(f"Hit rate limits after {rate_limit_count} requests")
            print("To process all bills, you need a real GovInfo API key")

def test_govinfo_api():
    """Test the GovInfo API to see what data is available."""
    print("Testing GovInfo API...")
    
    # Test with a sample bill ID in our format
    test_bill_id = "hr-1-119"  # Our format
    
    data = fetch_bill_cosponsors(test_bill_id)
    if data:
        print(f"Sample bill data keys: {list(data.keys())}")
        
        # Look for sponsor/cosponsor fields
        if 'sponsors' in data:
            print(f"Sponsors: {data['sponsors']}")
        if 'cosponsors' in data:
            print(f"Cosponsors: {data['cosponsors']}")
        
        # Print first 500 chars of response
        print(f"Sample response: {json.dumps(data, indent=2)[:500]}...")
    else:
        print("No data returned from GovInfo API")

if __name__ == "__main__":
    # Test the API first
    test_govinfo_api()
    
    # Then load all cosponsors
    load_all_cosponsors()
