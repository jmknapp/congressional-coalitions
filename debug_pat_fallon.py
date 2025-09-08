#!/usr/bin/env python3
"""
Debug script to analyze Pat Fallon's partyliner score calculation.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Rollcall, Vote
from scripts.ideological_labeling import calculate_partyliner_score
from collections import defaultdict

def debug_pat_fallon():
    """Debug Pat Fallon's partyliner score calculation."""
    member_id = 'F000246'  # Pat Fallon
    
    with get_db_session() as session:
        # Get member info
        member = session.query(Member).filter(Member.member_id_bioguide == member_id).first()
        if not member:
            print(f"Member {member_id} not found")
            return
        
        print(f"Debugging: {member.first} {member.last} ({member.party}-{member.state}-{member.district})")
        
        # Get all House members
        members = session.query(Member).filter(
            Member.district.isnot(None)  # House members only
        ).all()
        
        # Get all rollcalls for Congress 119, House
        rollcalls = session.query(Rollcall).filter(
            Rollcall.congress == 119,
            Rollcall.chamber == 'house'
        ).all()
        
        # Get all votes
        rollcall_ids = [rc.rollcall_id for rc in rollcalls]
        votes = session.query(Vote).filter(
            Vote.rollcall_id.in_(rollcall_ids)
        ).all()
        
        # Build vote matrix
        vote_matrix = defaultdict(dict)
        for vote in votes:
            vote_matrix[vote.rollcall_id][vote.member_id_bioguide] = vote.vote_code
        
        # Build member parties lookup
        member_parties = {member.member_id_bioguide: member.party for member in members}
        
        # Pre-calculate party positions for each rollcall
        rollcall_party_positions = {}
        for rollcall_id, rollcall_votes in vote_matrix.items():
            party_positions = {}
            for party in ['D', 'R']:
                party_yea = 0
                party_nay = 0
                
                for other_member_id, other_vote in rollcall_votes.items():
                    if other_vote in ['Yea', 'Nay'] and member_parties.get(other_member_id) == party:
                        if other_vote == 'Yea':
                            party_yea += 1
                        else:
                            party_nay += 1
                
                total_party_votes = party_yea + party_nay
                if total_party_votes > 0:
                    if party_yea > party_nay:
                        party_positions[party] = 'Yea'
                    elif party_nay > party_yea:
                        party_positions[party] = 'Nay'
                    else:
                        party_positions[party] = 'Tie'
            
            rollcall_party_positions[rollcall_id] = party_positions
        
        # Calculate partyliner score with debug
        print(f"\nCalculating partyliner score for {member_id}...")
        score = calculate_partyliner_score(
            member_id, 
            member.party, 
            vote_matrix, 
            rollcall_party_positions, 
            member_parties, 
            debug=True
        )
        
        print(f"\nFinal partyliner score: {score:.6f}")

if __name__ == '__main__':
    debug_pat_fallon()
