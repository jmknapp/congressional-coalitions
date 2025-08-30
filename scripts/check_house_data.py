#!/usr/bin/env python3
"""
Check what House data exists in the database.
"""

import os
import sys

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote, Cosponsor

def check_house_data():
    """Check what House data exists in the database."""
    
    with get_db_session() as session:
        print("=== HOUSE DATA INVENTORY ===\n")
        
        # Check House members
        house_members = session.query(Member).filter(Member.district.isnot(None)).all()
        print(f"House Members: {len(house_members)}")
        
        if house_members:
            print("Sample House members:")
            for i, member in enumerate(house_members[:5]):
                print(f"  {member.first} {member.last} ({member.party}-{member.state}-{member.district})")
        
        # Check House bills
        house_bills = session.query(Bill).filter(Bill.chamber == 'house').all()
        print(f"\nHouse Bills: {len(house_bills)}")
        
        if house_bills:
            print("Sample House bills:")
            for i, bill in enumerate(house_bills[:5]):
                print(f"  {bill.bill_id}: {bill.title[:50]}...")
        
        # Check House rollcalls
        house_rollcalls = session.query(Rollcall).filter(Rollcall.chamber == 'house').all()
        print(f"\nHouse Rollcalls: {len(house_rollcalls)}")
        
        if house_rollcalls:
            print("Sample House rollcalls:")
            for i, rollcall in enumerate(house_rollcalls[:5]):
                print(f"  {rollcall.rollcall_id}: {rollcall.question[:50]}...")
        
        # Check House votes
        house_votes = session.query(Vote).join(Rollcall).filter(Rollcall.chamber == 'house').all()
        print(f"\nHouse Votes: {len(house_votes)}")
        
        if house_votes:
            print("Sample House votes:")
            for i, vote in enumerate(house_votes[:5]):
                member = session.query(Member).filter(Member.member_id_bioguide == vote.member_id_bioguide).first()
                member_name = f"{member.first} {member.last}" if member else "Unknown"
                print(f"  {vote.rollcall_id}: {member_name} voted {vote.vote_code}")
        
        # Check House cosponsors
        house_cosponsors = session.query(Cosponsor).join(Bill).filter(Bill.chamber == 'house').all()
        print(f"\nHouse Cosponsors: {len(house_cosponsors)}")
        
        if house_cosponsors:
            print("Sample House cosponsors:")
            for i, cosponsor in enumerate(house_cosponsors[:5]):
                member = session.query(Member).filter(Member.member_id_bioguide == cosponsor.member_id_bioguide).first()
                member_name = f"{member.first} {member.last}" if member else "Unknown"
                print(f"  {cosponsor.bill_id}: {member_name}")
        
        # Check date ranges
        if house_rollcalls:
            dates = [rc.date for rc in house_rollcalls if rc.date]
            if dates:
                min_date = min(dates)
                max_date = max(dates)
                print(f"\nHouse Rollcall Date Range: {min_date} to {max_date}")
        
        if house_bills:
            dates = [bill.introduced_date for bill in house_bills if bill.introduced_date]
            if dates:
                min_date = min(dates)
                max_date = max(dates)
                print(f"House Bill Date Range: {min_date} to {max_date}")

if __name__ == "__main__":
    check_house_data()
