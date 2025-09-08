#!/usr/bin/env python3
"""
Script to check for inconsistencies between ideological analysis and caucus memberships.
This will identify members who are in caucuses that don't match their voting behavior.
"""

import os
import sys
import json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_caucus_tables import Caucus, CaucusMembership
from scripts.setup_db import Member

def check_caucus_consistency():
    """Check for inconsistencies between ideological profiles and caucus memberships."""
    print("🔍 Checking caucus membership consistency...")
    
    # Load ideological profiles
    ideological_file = 'cache/ideological_profiles_119_house.json'
    if not os.path.exists(ideological_file):
        print(f"❌ Ideological profiles file not found: {ideological_file}")
        print("Please run the ideological analysis first.")
        return
    
    with open(ideological_file, 'r') as f:
        ideological_data = json.load(f)
    
    profiles = ideological_data.get('profiles', {})
    
    try:
        with get_db_session() as session:
            # Get all caucuses
            caucuses = session.query(Caucus).all()
            caucus_map = {caucus.short_name: caucus for caucus in caucuses}
            
            inconsistencies = []
            
            # Only check ideologically-based caucuses, not official congressional caucuses
            ideologically_based_caucuses = ['MAGA', 'TB']  # MAGA Republicans, True Blue Democrats
            
            # Check each caucus
            for caucus_short_name, caucus in caucus_map.items():
                # Skip official congressional caucuses - they have real members, not ideological criteria
                if caucus_short_name not in ideologically_based_caucuses:
                    print(f"\n📋 Skipping {caucus.name} ({caucus_short_name}) - Official congressional caucus")
                    continue
                    
                print(f"\n📋 Checking {caucus.name} ({caucus_short_name})...")
                
                # Get active members of this caucus
                memberships = session.query(CaucusMembership).filter(
                    CaucusMembership.caucus_id == caucus.id,
                    CaucusMembership.end_date.is_(None)
                ).all()
                
                print(f"   Found {len(memberships)} active members")
                
                for membership in memberships:
                    member_id = membership.member_id_bioguide
                    profile = profiles.get(member_id)
                    
                    if not profile:
                        print(f"   ⚠️  {member_id}: No ideological profile found")
                        continue
                    
                    # Get member info from database to fill in missing profile data
                    member = session.query(Member).filter(Member.member_id_bioguide == member_id).first()
                    if member:
                        # Fill in missing profile data from database
                        if not profile.get('name'):
                            profile['name'] = f"{member.first} {member.last}"
                        if not profile.get('party'):
                            profile['party'] = member.party
                        if not profile.get('state'):
                            profile['state'] = member.state
                        if not profile.get('district'):
                            profile['district'] = member.district
                    
                    # Check for inconsistencies based on caucus type
                    inconsistency = check_member_consistency(member_id, profile, caucus_short_name)
                    if inconsistency:
                        inconsistencies.append(inconsistency)
                        print(f"   ❌ {profile.get('name', member_id)}: {inconsistency['issue']}")
                        print(f"      Partyliner: {profile.get('partyliner_score', 'N/A'):.3f}, "
                              f"Party Line: {profile.get('party_line_percentage', 'N/A'):.1f}%, "
                              f"Labels: {profile.get('labels', [])}")
            
            # Summary
            print(f"\n📊 CONSISTENCY CHECK SUMMARY")
            print(f"   Total inconsistencies found: {len(inconsistencies)}")
            
            if inconsistencies:
                print(f"\n❌ INCONSISTENCIES FOUND:")
                for inc in inconsistencies:
                    print(f"   • {inc['member_name']} ({inc['member_id']})")
                    print(f"     Caucus: {inc['caucus_name']}")
                    print(f"     Issue: {inc['issue']}")
                    print(f"     Partyliner Score: {inc['partyliner_score']:.3f}")
                    print(f"     Expected: {inc['expected_behavior']}")
                    print()
                
                # Generate cleanup script
                generate_cleanup_script(inconsistencies)
            else:
                print("✅ No inconsistencies found! All caucus memberships align with voting behavior.")
                
    except Exception as e:
        print(f"❌ Error checking consistency: {e}")
        raise

def check_member_consistency(member_id: str, profile: dict, caucus_short_name: str) -> dict:
    """Check if a member's caucus membership is consistent with their voting behavior."""
    partyliner_score = profile.get('partyliner_score', 0.5)
    party_line_pct = profile.get('party_line_percentage', 0)
    cross_party_pct = profile.get('cross_party_percentage', 0)
    labels = profile.get('labels', [])
    party = profile.get('party', '')
    name = profile.get('name', member_id)
    
    # Define expected behavior for each caucus
    caucus_expectations = {
        'MAGA': {
            'min_partyliner': 0.98,
            'min_party_line': 95.0,
            'max_cross_party': 5.0,
            'expected_labels': ['MAGA Republican'],
            'party': 'R'
        },
        'TB': {  # True Blue Democrats
            'min_partyliner': 0.995,
            'min_party_line': 95.0,
            'max_cross_party': 5.0,
            'expected_labels': ['True Blue Democrat'],
            'party': 'D'
        },
        'Freedom Caucus': {
            'min_partyliner': 0.90,
            'min_party_line': 80.0,
            'max_cross_party': 20.0,
            'expected_labels': ['MAGA Republican', 'Mainstream Republican'],
            'party': 'R'
        },
        'Progressive Caucus': {
            'min_partyliner': 0.85,
            'min_party_line': 75.0,
            'max_cross_party': 25.0,
            'expected_labels': ['Mainstream Democrat', 'Progressive Democrat'],
            'party': 'D'
        },
        'Blue Dog': {
            'max_partyliner': 0.85,
            'max_party_line': 80.0,
            'min_cross_party': 15.0,
            'expected_labels': ['Cross-Party Democrat', 'Moderate Democrat', 'Blue Dog Democrat'],
            'party': 'D'
        }
    }
    
    expectations = caucus_expectations.get(caucus_short_name)
    if not expectations:
        return None  # No expectations defined for this caucus
    
    # Check party match
    if party != expectations.get('party'):
        return {
            'member_id': member_id,
            'member_name': name,
            'caucus_name': caucus_short_name,
            'issue': f"Wrong party: {party} (expected {expectations['party']})",
            'partyliner_score': partyliner_score,
            'expected_behavior': f"Should be {expectations['party']} party"
        }
    
    # Check partyliner score
    if 'min_partyliner' in expectations and partyliner_score < expectations['min_partyliner']:
        return {
            'member_id': member_id,
            'member_name': name,
            'caucus_name': caucus_short_name,
            'issue': f"Partyliner score too low: {partyliner_score:.3f} (expected ≥{expectations['min_partyliner']})",
            'partyliner_score': partyliner_score,
            'expected_behavior': f"Should have ≥{expectations['min_partyliner']} partyliner score"
        }
    
    if 'max_partyliner' in expectations and partyliner_score > expectations['max_partyliner']:
        return {
            'member_id': member_id,
            'member_name': name,
            'caucus_name': caucus_short_name,
            'issue': f"Partyliner score too high: {partyliner_score:.3f} (expected ≤{expectations['max_partyliner']})",
            'partyliner_score': partyliner_score,
            'expected_behavior': f"Should have ≤{expectations['max_partyliner']} partyliner score"
        }
    
    # Check party line percentage
    if 'min_party_line' in expectations and party_line_pct < expectations['min_party_line']:
        return {
            'member_id': member_id,
            'member_name': name,
            'caucus_name': caucus_short_name,
            'issue': f"Party line voting too low: {party_line_pct:.1f}% (expected ≥{expectations['min_party_line']}%)",
            'partyliner_score': partyliner_score,
            'expected_behavior': f"Should have ≥{expectations['min_party_line']}% party line voting"
        }
    
    if 'max_party_line' in expectations and party_line_pct > expectations['max_party_line']:
        return {
            'member_id': member_id,
            'member_name': name,
            'caucus_name': caucus_short_name,
            'issue': f"Party line voting too high: {party_line_pct:.1f}% (expected ≤{expectations['max_party_line']}%)",
            'partyliner_score': partyliner_score,
            'expected_behavior': f"Should have ≤{expectations['max_party_line']}% party line voting"
        }
    
    # Check cross-party percentage
    if 'min_cross_party' in expectations and cross_party_pct < expectations['min_cross_party']:
        return {
            'member_id': member_id,
            'member_name': name,
            'caucus_name': caucus_short_name,
            'issue': f"Cross-party voting too low: {cross_party_pct:.1f}% (expected ≥{expectations['min_cross_party']}%)",
            'partyliner_score': partyliner_score,
            'expected_behavior': f"Should have ≥{expectations['min_cross_party']}% cross-party voting"
        }
    
    if 'max_cross_party' in expectations and cross_party_pct > expectations['max_cross_party']:
        return {
            'member_id': member_id,
            'member_name': name,
            'caucus_name': caucus_short_name,
            'issue': f"Cross-party voting too high: {cross_party_pct:.1f}% (expected ≤{expectations['max_cross_party']}%)",
            'partyliner_score': partyliner_score,
            'expected_behavior': f"Should have ≤{expectations['max_cross_party']}% cross-party voting"
        }
    
    return None  # No inconsistency found

def generate_cleanup_script(inconsistencies):
    """Generate a cleanup script to fix the inconsistencies."""
    script_content = '''#!/usr/bin/env python3
"""
Auto-generated script to fix caucus membership inconsistencies.
Review this script before running it.
"""

import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_caucus_tables import Caucus, CaucusMembership

def fix_inconsistencies():
    """Fix caucus membership inconsistencies."""
    print("🔧 Fixing caucus membership inconsistencies...")
    
    with get_db_session() as session:
'''
    
    # Group inconsistencies by action
    removals = []
    for inc in inconsistencies:
        if 'too low' in inc['issue'] or 'too high' in inc['issue'] or 'Wrong party' in inc['issue']:
            removals.append(inc)
    
    if removals:
        script_content += f'''
        # Remove inconsistent members
        removals = {removals}
        
        for removal in removals:
            member_id = removal['member_id']
            caucus_name = removal['caucus_name']
            
            # Get caucus
            caucus = session.query(Caucus).filter(Caucus.short_name == caucus_name).first()
            if not caucus:
                print(f"⚠️  Caucus {{caucus_name}} not found")
                continue
            
            # End the membership
            membership = session.query(CaucusMembership).filter(
                CaucusMembership.caucus_id == caucus.id,
                CaucusMembership.member_id_bioguide == member_id,
                CaucusMembership.end_date.is_(None)
            ).first()
            
            if membership:
                membership.end_date = datetime.now().date()
                membership.notes = f"Removed due to inconsistency: {{removal['issue']}}"
                print(f"✓ Removed {{removal['member_name']}} from {{caucus_name}}")
            else:
                print(f"⚠️  No active membership found for {{removal['member_name']}} in {{caucus_name}}")
        
        session.commit()
        print(f"✓ Fixed {{len(removals)}} inconsistencies")
'''
    
    script_content += '''
if __name__ == '__main__':
    fix_inconsistencies()
'''
    
    # Write the cleanup script
    cleanup_file = 'scripts/fix_caucus_inconsistencies.py'
    with open(cleanup_file, 'w') as f:
        f.write(script_content)
    
    print(f"\n📝 Generated cleanup script: {cleanup_file}")
    print("   Review the script before running it to fix the inconsistencies.")

if __name__ == '__main__':
    check_caucus_consistency()
