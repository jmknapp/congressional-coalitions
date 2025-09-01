#!/usr/bin/env python3
"""
Analyze a specific member's voting record to verify ideological calculations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Vote, Rollcall
from collections import defaultdict

def analyze_member_votes(bioguide_id, congress=119, chamber='house'):
    """Analyze a member's voting record to calculate cross-party voting."""
    
    with get_db_session() as session:
        # Get member info
        member = session.query(Member).filter(Member.member_id_bioguide == bioguide_id).first()
        if not member:
            print(f"Member {bioguide_id} not found")
            return
        
        print(f"Analyzing votes for: {member.first} {member.last} ({member.party})")
        print(f"Congress: {congress}, Chamber: {chamber}")
        print("-" * 60)
        
        # Get all rollcalls for this congress/chamber
        rollcalls = session.query(Rollcall).filter(
            Rollcall.congress == congress,
            Rollcall.chamber == chamber
        ).all()
        
        print(f"Total rollcalls found: {len(rollcalls)}")
        
        # Get member's votes
        member_votes = session.query(Vote).filter(
            Vote.member_id_bioguide == bioguide_id,
            Vote.rollcall_id.in_([rc.rollcall_id for rc in rollcalls])
        ).all()
        
        print(f"Member votes found: {len(member_votes)}")
        
        # Calculate party positions for each rollcall
        rollcall_party_positions = {}
        cross_party_votes = 0
        party_line_votes = 0
        total_votes = 0
        
        for rollcall in rollcalls:
            # Get all votes for this rollcall
            votes = session.query(Vote).filter(Vote.rollcall_id == rollcall.rollcall_id).all()
            
            if not votes:
                continue
            
            # Calculate party positions
            party_votes = defaultdict(lambda: defaultdict(int))
            for vote in votes:
                member_info = session.query(Member).filter(Member.member_id_bioguide == vote.member_id_bioguide).first()
                if member_info and member_info.party in ['D', 'R']:
                    party_votes[member_info.party][vote.vote_code] += 1
            
            # Determine majority position for each party
            party_positions = {}
            for party in ['D', 'R']:
                if party in party_votes:
                    yea_count = party_votes[party].get('Yea', 0)
                    nay_count = party_votes[party].get('Nay', 0)
                    if yea_count > nay_count:
                        party_positions[party] = 'Yea'
                    elif nay_count > yea_count:
                        party_positions[party] = 'Nay'
                    # If tied, no clear position
            
            rollcall_party_positions[rollcall.rollcall_id] = party_positions
            
            # Check member's vote
            member_vote = next((v for v in member_votes if v.rollcall_id == rollcall.rollcall_id), None)
            if member_vote:
                total_votes += 1
                member_party = member.party
                
                # Check if member voted with their party
                if member_party in party_positions:
                    party_position = party_positions[member_party]
                    if member_vote.vote_code == party_position:
                        party_line_votes += 1
                    else:
                        # Check if they voted with opposite party
                        opposite_party = 'R' if member_party == 'D' else 'D'
                        if opposite_party in party_positions:
                            opposite_position = party_positions[opposite_party]
                            if member_vote.vote_code == opposite_position:
                                cross_party_votes += 1
                                print(f"CROSS-PARTY VOTE: {rollcall.rollcall_id} - Member voted {member_vote.vote_code}, {member_party} majority: {party_position}, {opposite_party} majority: {opposite_position}")
        
        # Calculate percentages
        party_line_percentage = (party_line_votes / total_votes * 100) if total_votes > 0 else 0
        cross_party_percentage = (cross_party_votes / total_votes * 100) if total_votes > 0 else 0
        
        print("\n" + "=" * 60)
        print("RESULTS:")
        print(f"Total votes: {total_votes}")
        print(f"Party-line votes: {party_line_votes} ({party_line_percentage:.1f}%)")
        print(f"Cross-party votes: {cross_party_votes} ({cross_party_percentage:.1f}%)")
        print(f"Other votes: {total_votes - party_line_votes - cross_party_votes}")
        print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/analyze_member_votes.py <bioguide_id>")
        print("Example: python scripts/analyze_member_votes.py T000481")
        sys.exit(1)
    
    bioguide_id = sys.argv[1]
    analyze_member_votes(bioguide_id)
