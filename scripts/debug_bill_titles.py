#!/usr/bin/env python3
"""
Debug script to check bill titles and API responses.
"""

import sys
import os
import requests
import json

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Bill, Rollcall

def check_bill_data():
    """Check what bill data we have in the database."""
    print("=== BILL DATA IN DATABASE ===")
    
    with get_db_session() as session:
        # Get recent roll calls (with or without bills)
        recent_rollcalls = session.query(Rollcall).filter(
            Rollcall.rc_number >= 235,
            Rollcall.rc_number <= 239
        ).all()
        
        print(f"Found {len(recent_rollcalls)} recent roll calls")
        
        for rc in recent_rollcalls:
            print(f"\nRoll Call {rc.rc_number}:")
            print(f"  Bill ID: {rc.bill_id}")
            print(f"  Question: {rc.question}")
            
            if rc.bill_id:
                bill = session.query(Bill).filter(Bill.bill_id == rc.bill_id).first()
                if bill:
                    print(f"  Bill Title: {bill.title}")
                    print(f"  Bill Type: {bill.bill_type}")
                    print(f"  Bill Number: {bill.bill_number}")
                    print(f"  Short Title: {bill.short_title}")
                else:
                    print(f"  ERROR: Bill {rc.bill_id} not found in database!")

def test_api_response():
    """Test what the Congress.gov API returns for a specific bill."""
    print("\n=== API RESPONSE TEST ===")
    
    api_key = os.environ.get('CONGRESSGOV_API_KEY', '')
    if not api_key:
        print("No API key found")
        return
    
    # Test with H.R. 4553 (from roll call 238)
    bill_id = "hr-4553-119"
    url = f"https://api.congress.gov/v3/bill/119/hr/4553"
    params = {
        'api_key': api_key,
        'format': 'json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        print(f"API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            bill_data = data.get('bill', {})
            print(f"Bill ID: {bill_data.get('billId')}")
            print(f"Title: {bill_data.get('title')}")
            print(f"Short Title: {bill_data.get('shortTitle')}")
            print(f"Type: {bill_data.get('type')}")
            print(f"Number: {bill_data.get('number')}")
        else:
            print(f"API Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_bill_data()
    test_api_response()
