#!/usr/bin/env python3
"""
Restore Blue Dog Coalition members that were incorrectly removed by the cleanup script.
Blue Dog Coalition is an official congressional caucus, not an ideologically-based caucus.
"""

import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_caucus_tables import Caucus, CaucusMembership

def restore_blue_dog_members():
    """Restore Blue Dog Coalition members that were incorrectly removed."""
    print("🔄 Restoring Blue Dog Coalition members...")
    
    # List of Blue Dog members that were incorrectly removed
    # These are the members that were in the cleanup script
    blue_dog_members_to_restore = [
        {'member_id': 'B000490', 'member_name': 'Sanford Bishop'},
        {'member_id': 'C001110', 'member_name': 'J. Correa'},
        {'member_id': 'C001059', 'member_name': 'Jim Costa'},
        {'member_id': 'C001063', 'member_name': 'Henry Cuellar'},
        {'member_id': 'G000592', 'member_name': 'Jared Golden'},
        {'member_id': 'G000581', 'member_name': 'Vicente Gonzalez'},
        {'member_id': 'G000583', 'member_name': 'Josh Gottheimer'},
        {'member_id': 'G000605', 'member_name': 'Adam Gray'},
        {'member_id': 'G000600', 'member_name': 'Marie Perez'},
        {'member_id': 'T000460', 'member_name': 'Mike Thompson'}
    ]
    
    with get_db_session() as session:
        # Get Blue Dog caucus
        blue_dog_caucus = session.query(Caucus).filter(Caucus.short_name == 'Blue Dog').first()
        if not blue_dog_caucus:
            print("❌ Blue Dog Coalition caucus not found")
            return
        
        print(f"✓ Found Blue Dog caucus: {blue_dog_caucus.name}")
        
        restored_count = 0
        for member_data in blue_dog_members_to_restore:
            member_id = member_data['member_id']
            member_name = member_data['member_name']
            
            # Check if there's an ended membership that we need to restore
            ended_membership = session.query(CaucusMembership).filter(
                CaucusMembership.caucus_id == blue_dog_caucus.id,
                CaucusMembership.member_id_bioguide == member_id,
                CaucusMembership.end_date.isnot(None)  # Find ended memberships
            ).first()
            
            if ended_membership:
                # Restore the membership by removing the end_date
                ended_membership.end_date = None
                ended_membership.notes = "Restored - Blue Dog Coalition is an official caucus, not ideologically-based"
                print(f"✓ Restored {member_name} to Blue Dog Coalition")
                restored_count += 1
            else:
                # Check if there's already an active membership
                active_membership = session.query(CaucusMembership).filter(
                    CaucusMembership.caucus_id == blue_dog_caucus.id,
                    CaucusMembership.member_id_bioguide == member_id,
                    CaucusMembership.end_date.is_(None)
                ).first()
                
                if active_membership:
                    print(f"ℹ️  {member_name} already has active Blue Dog membership")
                else:
                    # Create new membership
                    new_membership = CaucusMembership(
                        member_id_bioguide=member_id,
                        caucus_id=blue_dog_caucus.id,
                        start_date=None,
                        notes="Restored - Blue Dog Coalition is an official caucus, not ideologically-based"
                    )
                    session.add(new_membership)
                    print(f"✓ Added {member_name} to Blue Dog Coalition")
                    restored_count += 1
        
        session.commit()
        print(f"\n✅ Successfully restored {restored_count} Blue Dog Coalition members")
        print("📝 Note: Blue Dog Coalition is an official congressional caucus with real members,")
        print("   not an ideologically-based caucus. Members should not be removed based on voting scores.")

if __name__ == '__main__':
    restore_blue_dog_members()
