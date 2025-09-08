#!/usr/bin/env python3
"""
Script to populate the Congressional Hispanic Caucus (CHC) with current members.

The Congressional Hispanic Caucus (CHC) is a bipartisan organization of Hispanic 
members of Congress dedicated to advancing issues affecting Hispanics and Latinos.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_caucus_tables import Caucus, CaucusMembership
from datetime import date

def populate_hispanic_caucus():
    """Add the Congressional Hispanic Caucus to the database."""
    
    # Note: CHC membership will be populated manually through the web interface
    # This script just creates the caucus structure
    chc_members = []
    
    try:
        with get_db_session() as session:
            # Check if CHC already exists
            existing_chc = session.query(Caucus).filter(
                Caucus.short_name == 'CHC'
            ).first()
            
            if existing_chc:
                print(f"Congressional Hispanic Caucus already exists with ID {existing_chc.id}")
                caucus_id = existing_chc.id
            else:
                # Create the CHC caucus
                chc = Caucus(
                    name="Congressional Hispanic Caucus",
                    short_name="CHC",
                    description="A bipartisan organization of Hispanic members of Congress dedicated to advancing issues affecting Hispanics and Latinos.",
                    is_active=True,
                    color="#2e7d32",  # Green color
                    icon="fas fa-flag"
                )
                session.add(chc)
                session.commit()
                caucus_id = chc.id
                print(f"Created Congressional Hispanic Caucus with ID {caucus_id}")
            
            # Add members to the caucus
            added_count = 0
            skipped_count = 0
            
            for member_id in chc_members:
                # Check if member exists in database
                from scripts.setup_db import Member
                member = session.query(Member).filter(
                    Member.member_id_bioguide == member_id
                ).first()
                
                if not member:
                    print(f"Warning: Member {member_id} not found in database")
                    skipped_count += 1
                    continue
                
                # Check if membership already exists
                existing_membership = session.query(CaucusMembership).filter(
                    CaucusMembership.member_id_bioguide == member_id,
                    CaucusMembership.caucus_id == caucus_id,
                    CaucusMembership.end_date.is_(None)  # Active membership
                ).first()
                
                if existing_membership:
                    print(f"Member {member.first} {member.last} ({member_id}) already in CHC")
                    skipped_count += 1
                    continue
                
                # Create membership
                membership = CaucusMembership(
                    member_id_bioguide=member_id,
                    caucus_id=caucus_id,
                    start_date=date(2025, 1, 3),  # Start of 119th Congress
                    notes="119th Congress membership"
                )
                session.add(membership)
                added_count += 1
                print(f"Added {member.first} {member.last} ({member_id}) to CHC")
            
            session.commit()
            print(f"\nSummary:")
            print(f"  Added: {added_count} members")
            print(f"  Skipped: {skipped_count} members")
            print(f"  Total CHC members: {added_count}")
            print(f"\n📝 Note: CHC membership can be populated manually through the web interface at /caucus/{caucus_id}")
            print(f"   Or by running a web scraping script to get current members from https://hispaniccaucus.house.gov/")
            
    except Exception as e:
        print(f"Error populating Hispanic Caucus: {e}")
        raise

if __name__ == "__main__":
    populate_hispanic_caucus()
