#!/usr/bin/env python3
"""
Script to remove sample bills from the database.
"""

import sys
import os
# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.utils.database import get_db_session
from scripts.setup_db import Bill, Cosponsor

def remove_sample_bills():
    """Remove specific sample bills from the database."""
    with get_db_session() as session:
        # Target specific sample bills
        sample_bill_ids = ['hr-123-118', 'hr-456-118']
        sample_bills = session.query(Bill).filter(
            Bill.bill_id.in_(sample_bill_ids)
        ).all()
        
        print(f"Found {len(sample_bills)} sample bills:")
        for bill in sample_bills:
            print(f"  - {bill.bill_id}: {bill.title}")
        
        if not sample_bills:
            print("No sample bills found.")
            return
        
        # Remove associated cosponsors first
        for bill in sample_bills:
            cosponsors = session.query(Cosponsor).filter(
                Cosponsor.bill_id == bill.bill_id
            ).all()
            if cosponsors:
                print(f"Removing {len(cosponsors)} cosponsors for {bill.bill_id}")
                for cosponsor in cosponsors:
                    session.delete(cosponsor)
        
        # Remove the bills
        for bill in sample_bills:
            print(f"Removing bill: {bill.bill_id}")
            session.delete(bill)
        
        session.commit()
        print(f"Successfully removed {len(sample_bills)} sample bills and their cosponsors.")

if __name__ == "__main__":
    remove_sample_bills()
