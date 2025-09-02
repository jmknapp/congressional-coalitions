#!/usr/bin/env python3
"""
Populate True Blue Democrats caucus from ideological profiles.
"""

import json
import sys
import os
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_caucus_tables import Caucus, CaucusMembership
from scripts.setup_db import Member

def populate_true_blue_caucus():
    print("Populating True Blue Democrats caucus...")
    
    try:
        with get_db_session() as session:
            # Find the True Blue Democrats caucus
            tb_caucus = session.query(Caucus).filter(Caucus.short_name == 'TB').first()
            if not tb_caucus:
                print("❌ True Blue Democrats caucus not found. Run setup_caucus_tables.py first.")
                return
            
            print(f"✓ Found True Blue caucus: {tb_caucus.name}")
            
            # Load ideological profiles
            ideological_file = 'cache/ideological_profiles_119_house.json'
            if not os.path.exists(ideological_file):
                print(f"❌ Ideological profiles file not found: {ideological_file}")
                return
            
            with open(ideological_file, 'r') as f:
                ideological_data = json.load(f)
            
            # Find True Blue Democrat members
            tb_member_ids = set()
            for member_id, profile in ideological_data.get('profiles', {}).items():
                if 'True Blue Democrat' in profile.get('labels', []):
                    tb_member_ids.add(member_id)
            
            if not tb_member_ids:
                print("❌ No True Blue Democrat members found in ideological profiles.")
                return
            
            print(f"✓ Found {len(tb_member_ids)} True Blue Democrat members")
            
            # Create caucus memberships
            added_count = 0
            for member_id in tb_member_ids:
                member = session.query(Member).filter(
                    Member.member_id_bioguide == member_id
                ).first()
                
                if member:
                    # Check if membership already exists
                    existing = session.query(CaucusMembership).filter(
                        CaucusMembership.caucus_id == tb_caucus.id,
                        CaucusMembership.member_id_bioguide == member_id,
                        CaucusMembership.end_date.is_(None)
                    ).first()
                    
                    if not existing:
                        membership = CaucusMembership(
                            member_id_bioguide=member_id,
                            caucus_id=tb_caucus.id,
                            start_date=None,
                            notes="Auto-populated from ideological analysis"
                        )
                        session.add(membership)
                        added_count += 1
                        print(f"  + {member.first} {member.last} ({member.party}-{member.state}-{member.district})")
            
            session.commit()
            print(f"\n✓ Successfully added {added_count} members to True Blue Democrats caucus")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == '__main__':
    populate_true_blue_caucus()
    print("\nTrue Blue caucus population complete!")
