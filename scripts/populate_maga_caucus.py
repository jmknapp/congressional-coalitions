#!/usr/bin/env python3
"""
Script to populate the MAGA Republicans caucus with members who have >95% party-line voting.
This creates an initial population that can then be manually adjusted through the web interface.
"""

import os
import sys
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_caucus_tables import Caucus, CaucusMembership
from scripts.setup_db import Member

def populate_maga_caucus():
    """Populate the MAGA Republicans caucus with algorithmic detection."""
    print("Populating MAGA Republicans caucus...")
    
    try:
        with get_db_session() as session:
            # Get the MAGA Republicans caucus
            maga_caucus = session.query(Caucus).filter(Caucus.short_name == 'MAGA').first()
            if not maga_caucus:
                print("❌ MAGA Republicans caucus not found. Please run setup_caucus_tables.py first.")
                return
            
            print(f"✓ Found MAGA caucus: {maga_caucus.name}")
            
            # Check if caucus already has members
            existing_count = session.query(CaucusMembership).filter(
                CaucusMembership.caucus_id == maga_caucus.id,
                CaucusMembership.end_date.is_(None)
            ).count()
            
            if existing_count > 0:
                print(f"⚠️  MAGA caucus already has {existing_count} members.")
                response = input("Do you want to replace them? (y/N): ")
                if response.lower() != 'y':
                    print("Aborted. Keeping existing members.")
                    return
                
                # End existing memberships
                session.query(CaucusMembership).filter(
                    CaucusMembership.caucus_id == maga_caucus.id,
                    CaucusMembership.end_date.is_(None)
                ).update({'end_date': datetime.now().date()})
                print(f"✓ Ended {existing_count} existing memberships")
            
            # Load ideological profiles
            ideological_file = 'cache/ideological_profiles_119_house.json'
            if not os.path.exists(ideological_file):
                print(f"❌ Ideological profiles file not found: {ideological_file}")
                print("Please run the ideological analysis first.")
                return
            
            with open(ideological_file, 'r') as f:
                ideological_data = json.load(f)
            
            # Find MAGA Republican members
            maga_member_ids = set()
            for member_id, profile in ideological_data.get('profiles', {}).items():
                if 'MAGA Republican' in profile.get('labels', []):
                    maga_member_ids.add(member_id)
            
            print(f"✓ Found {len(maga_member_ids)} MAGA Republican members from ideological profiles")
            
            # Create memberships for MAGA Republicans
            members_added = 0
            for member_id in maga_member_ids:
                # Check if member exists in the database
                member = session.query(Member).filter(Member.member_id_bioguide == member_id).first()
                if member:
                    # Create membership
                    membership = CaucusMembership(
                        member_id_bioguide=member_id,
                        caucus_id=maga_caucus.id,
                        start_date=None,  # Unknown when they became "MAGA"
                        notes="Automatically populated from ideological analysis (≥98.0% partyliner score)"
                    )
                    session.add(membership)
                    members_added += 1
                    print(f"  + {member.first} {member.last} ({member.party}-{member.state}{member.district or ''})")
                else:
                    print(f"  ⚠️  Member {member_id} not found in database")
            
            session.commit()
            print(f"\n✓ Successfully added {members_added} members to MAGA Republicans caucus")
            print(f"✓ Total MAGA members: {members_added}")
            
            # Show summary
            print(f"\nMAGA Republicans caucus is now populated and ready for manual adjustment.")
            print(f"Use the web interface at /caucus-management to review and modify the list.")
            
    except Exception as e:
        print(f"❌ Error populating MAGA caucus: {e}")
        raise

if __name__ == '__main__':
    populate_maga_caucus()
    print("\nMAGA caucus population complete!")
