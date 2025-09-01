#!/usr/bin/env python3
"""
Ideological labeling for congressional members.
Demonstrates multiple approaches to assign ideological labels.

IMPORTANT: This script identifies voting behavior patterns, NOT official caucus memberships.
Labels like "Blue Dog" and "Freedom Caucus" are NOT official affiliations, but rather
classifications based on how members vote relative to their party.

For official caucus memberships, you would need to:
1. Scrape official caucus websites
2. Use external APIs that track caucus membership
3. Manually maintain membership lists
4. Use academic datasets like DW-NOMINATE scores

What this script actually measures:
- Party line voting percentage
- Cross-party voting frequency  
- Overall ideological positioning based on voting patterns
- Bill sponsorship issue areas
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from collections import defaultdict

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote

logger = logging.getLogger(__name__)

def calculate_voting_ideology_scores_fast(congress: int, chamber: str) -> Dict[str, Dict]:
    """
    Calculate ideological scores based on voting patterns - FAST VERSION.
    Returns a dictionary mapping member_id to ideological metrics.
    """
    with get_db_session() as session:
        # Get all House members
        members = session.query(Member).filter(
            Member.district.isnot(None)  # House members only
        ).all()
        
        # Get all rollcalls for the congress/chamber
        rollcalls = session.query(Rollcall).filter(
            Rollcall.congress == congress,
            Rollcall.chamber == chamber
        ).all()
        
        # Get all votes
        rollcall_ids = [rc.rollcall_id for rc in rollcalls]
        votes = session.query(Vote).filter(
            Vote.rollcall_id.in_(rollcall_ids)
        ).all()
        
        # Build vote matrix more efficiently
        vote_matrix = defaultdict(dict)
        for vote in votes:
            vote_matrix[vote.rollcall_id][vote.member_id_bioguide] = vote.vote_code
        
        # Pre-calculate party positions for each rollcall
        rollcall_party_positions = {}
        for rollcall_id, rollcall_votes in vote_matrix.items():
            party_votes = {'D': {'Yea': 0, 'Nay': 0}, 'R': {'Yea': 0, 'Nay': 0}}
            
            for member_id, vote_code in rollcall_votes.items():
                if vote_code in ['Yea', 'Nay']:
                    member = session.query(Member).filter(
                        Member.member_id_bioguide == member_id
                    ).first()
                    if member and member.party in ['D', 'R']:
                        party_votes[member.party][vote_code] += 1
            
            # Determine party position for each rollcall
            rollcall_party_positions[rollcall_id] = {}
            for party in ['D', 'R']:
                if party_votes[party]['Yea'] > party_votes[party]['Nay']:
                    rollcall_party_positions[rollcall_id][party] = 'Yea'
                elif party_votes[party]['Nay'] > party_votes[party]['Yea']:
                    rollcall_party_positions[rollcall_id][party] = 'Nay'
                else:
                    rollcall_party_positions[rollcall_id][party] = 'Tie'
        
        # Calculate ideological scores for each member
        member_scores = {}
        
        for member in members:
            member_id = member.member_id_bioguide
            party = member.party
            
            if party not in ['D', 'R']:
                continue  # Skip independents for now
            
            # Get all votes for this member
            party_line_votes = 0
            total_votes = 0
            cross_party_votes = 0
            
            for rollcall_id, rollcall_votes in vote_matrix.items():
                if member_id in rollcall_votes:
                    vote = rollcall_votes[member_id]
                    if vote in ['Yea', 'Nay']:
                        total_votes += 1
                        
                        # Check party line voting
                        if rollcall_id in rollcall_party_positions and party in rollcall_party_positions[rollcall_id]:
                            party_position = rollcall_party_positions[rollcall_id][party]
                            if vote == party_position:
                                party_line_votes += 1
                        
                        # Check cross-party voting (only when voting AGAINST party position)
                        opposite_party = 'R' if party == 'D' else 'D'
                        if opposite_party in rollcall_party_positions.get(rollcall_id, {}):
                            opposite_position = rollcall_party_positions[rollcall_id][opposite_party]
                            party_position = rollcall_party_positions[rollcall_id][party]
                            # Only count as cross-party if voting with opposite party AND against own party
                            if vote == opposite_position and vote != party_position:
                                cross_party_votes += 1
            
            # Calculate scores
            party_line_percentage = (party_line_votes / total_votes * 100) if total_votes > 0 else 0
            cross_party_percentage = (cross_party_votes / total_votes * 100) if total_votes > 0 else 0
            
            member_scores[member_id] = {
                'name': f"{member.first} {member.last}",
                'party': party,
                'state': member.state,
                'district': member.district,
                'total_votes': total_votes,
                'party_line_percentage': party_line_percentage,
                'cross_party_percentage': cross_party_percentage,
                'ideological_score': party_line_percentage - cross_party_percentage
            }
    
    return member_scores

def assign_ideological_labels(member_scores: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Assign ideological labels based on voting patterns.
    """
    labeled_members = {}
    
    for member_id, scores in member_scores.items():
        party = scores['party']
        party_line_pct = scores['party_line_percentage']
        cross_party_pct = scores['cross_party_percentage']
        ideological_score = scores['ideological_score']
        
        # Initialize labels
        labels = []
        
        # Party-specific labels based on voting patterns
        # NOTE: These are NOT official caucus memberships, just voting behavior classifications
        
        if party == 'D':
            if party_line_pct < 70:  # Low party loyalty
                if cross_party_pct > 20:  # High cross-party voting
                    labels.append('Cross-Party Democrat')  # More accurate than "Blue Dog"
                else:
                    labels.append('Moderate Democrat')
            elif party_line_pct > 95:  # Very high party loyalty
                labels.append('True Blue Democrat')  # More politically relevant than "Party-Loyal Democrat"
            else:
                labels.append('Mainstream Democrat')
                
        elif party == 'R':
            if party_line_pct < 70:  # Low party loyalty
                if cross_party_pct > 20:  # High cross-party voting
                    labels.append('Cross-Party Republican')
                else:
                    labels.append('Independent Republican')
            elif party_line_pct > 95:  # Very high party loyalty
                labels.append('MAGA Republican')  # More politically relevant than "Hardline Republican"
            else:
                labels.append('Mainstream Republican')
        
        # Add ideological labels based on overall score
        if ideological_score > 80:
            labels.append('Party Loyalist')
        elif ideological_score < 20:
            labels.append('Bipartisan')
        elif ideological_score < 50:
            labels.append('Moderate')
        
        # Store results
        labeled_members[member_id] = {
            **scores,
            'labels': labels,
            'primary_label': labels[0] if labels else 'Unclassified'
        }
    
    return labeled_members

def analyze_bill_sponsorship_patterns(congress: int, chamber: str) -> Dict[str, List[str]]:
    """
    Analyze bill sponsorship patterns to identify issue areas.
    """
    with get_db_session() as session:
        # Get bills sponsored by each member
        bills = session.query(Bill).filter(
            Bill.congress == congress,
            Bill.chamber == chamber
        ).all()
        
        member_bills = defaultdict(list)
        for bill in bills:
            if bill.sponsor_bioguide:
                member_bills[bill.sponsor_bioguide].append(bill.title)
        
        # Simple keyword analysis for issue areas
        issue_keywords = {
            'Healthcare': ['health', 'medical', 'medicare', 'medicaid', 'insurance'],
            'Environment': ['environment', 'climate', 'energy', 'renewable', 'pollution'],
            'Immigration': ['immigration', 'border', 'visa', 'citizenship'],
            'Guns': ['gun', 'firearm', 'weapon', 'ammunition'],
            'Taxes': ['tax', 'revenue', 'deduction', 'credit'],
            'Defense': ['defense', 'military', 'veteran', 'armed forces'],
            'Education': ['education', 'school', 'student', 'college'],
            'Infrastructure': ['infrastructure', 'transportation', 'highway', 'bridge']
        }
        
        member_issues = {}
        for member_id, bill_titles in member_bills.items():
            issue_counts = defaultdict(int)
            for title in bill_titles:
                title_lower = title.lower()
                for issue, keywords in issue_keywords.items():
                    if any(keyword in title_lower for keyword in keywords):
                        issue_counts[issue] += 1
            
            # Get top 3 issues
            top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            member_issues[member_id] = [issue for issue, count in top_issues if count > 0]
        
        return member_issues

def get_official_caucus_memberships():
    """
    Placeholder function for official caucus membership data.
    
    In a real implementation, this would:
    1. Scrape official caucus websites
    2. Use external APIs (e.g., ProPublica, Congress.gov)
    3. Maintain updated membership lists
    4. Include membership dates and leadership positions
    
    Returns:
        Dict mapping caucus names to lists of member IDs
    """
    # This is example data - in reality you'd need to maintain current lists
    example_caucuses = {
        'Freedom Caucus': [
            # These would be real member IDs from official sources
            # 'M001234',  # Example: Marjorie Taylor Greene
            # 'M001235',  # Example: Jim Jordan
        ],
        'Blue Dog Coalition': [
            # Democratic caucus for fiscal conservatism
            # 'M001236',  # Example: Jared Golden
        ],
        'Progressive Caucus': [
            # Democratic caucus for progressive policies
            # 'M001237',  # Example: Pramila Jayapal
        ],
        'Problem Solvers Caucus': [
            # Bipartisan caucus for compromise
            # 'M001238',  # Example: Josh Gottheimer
        ]
    }
    
    return example_caucuses

def assign_official_caucus_labels(member_ids: List[str], caucus_data: Dict) -> Dict[str, List[str]]:
    """
    Assign official caucus membership labels.
    
    This would be used alongside the voting behavior analysis to show
    both official affiliations AND voting patterns.
    """
    caucus_labels = {}
    
    for member_id in member_ids:
        member_caucuses = []
        for caucus_name, caucus_members in caucus_data.items():
            if member_id in caucus_members:
                member_caucuses.append(caucus_name)
        
        caucus_labels[member_id] = member_caucuses
    
    return caucus_labels

def main():
    """Main function to demonstrate ideological labeling."""
    congress = 119
    chamber = 'house'
    
    print("=== IDEOLOGICAL LABELING ANALYSIS ===")
    print(f"Congress: {congress}, Chamber: {chamber}")
    print()
    print("NOTE: This analysis shows VOTING BEHAVIOR patterns, NOT official caucus memberships.")
    print("Labels are based on how members vote relative to their party, not actual affiliations.")
    print()
    
    # Calculate voting-based ideological scores (FAST VERSION)
    print("Calculating voting ideology scores...")
    member_scores = calculate_voting_ideology_scores_fast(congress, chamber)
    
    # Assign labels
    print("Assigning ideological labels...")
    labeled_members = assign_ideological_labels(member_scores)
    
    # Analyze bill sponsorship patterns
    print("Analyzing bill sponsorship patterns...")
    member_issues = analyze_bill_sponsorship_patterns(congress, chamber)
    
    # Show official caucus membership info (placeholder)
    print("Getting official caucus memberships...")
    caucus_data = get_official_caucus_memberships()
    print(f"Available caucuses: {list(caucus_data.keys())}")
    print("(Note: This is placeholder data - real implementation would use current membership lists)")
    print()
    
    # Display results
    print("\n=== SAMPLE RESULTS ===")
    
    # Show some examples from each party
    democrats = [(mid, data) for mid, data in labeled_members.items() if data['party'] == 'D'][:5]
    republicans = [(mid, data) for mid, data in labeled_members.items() if data['party'] == 'R'][:5]
    
    print("\n--- DEMOCRATS ---")
    for member_id, data in democrats:
        issues = member_issues.get(member_id, [])
        print(f"{data['name']} ({data['state']}-{data['district']})")
        print(f"  Labels: {', '.join(data['labels'])}")
        print(f"  Party Line: {data['party_line_percentage']:.1f}%")
        print(f"  Cross-Party: {data['cross_party_percentage']:.1f}%")
        print(f"  Top Issues: {', '.join(issues) if issues else 'None'}")
        print()
    
    print("\n--- REPUBLICANS ---")
    for member_id, data in republicans:
        issues = member_issues.get(member_id, [])
        print(f"{data['name']} ({data['state']}-{data['district']})")
        print(f"  Labels: {', '.join(data['labels'])}")
        print(f"  Party Line: {data['party_line_percentage']:.1f}%")
        print(f"  Cross-Party: {data['cross_party_percentage']:.1f}%")
        print(f"  Top Issues: {', '.join(issues) if issues else 'None'}")
        print()
    
    # Summary statistics
    print("\n=== SUMMARY STATISTICS ===")
    label_counts = defaultdict(int)
    for data in labeled_members.values():
        for label in data['labels']:
            label_counts[label] += 1
    
    print("Label distribution:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count} members")
    
    print("\n=== LABEL DEFINITIONS ===")
    print("These labels are based on VOTING BEHAVIOR, not official caucus memberships:")
    print()
    print("DEMOCRATS:")
    print("  True Blue Democrat: Votes with party >95% of the time")
    print("  Mainstream Democrat: Votes with party 70-95% of the time")
    print("  Moderate Democrat: Votes with party <70% of the time")
    print("  Cross-Party Democrat: Votes with opposite party >20% of the time")
    print()
    print("REPUBLICANS:")
    print("  MAGA Republican: Votes with party >95% of the time")
    print("  Mainstream Republican: Votes with party 70-95% of the time")
    print("  Independent Republican: Votes with party <70% of the time")
    print("  Cross-Party Republican: Votes with opposite party >20% of the time")
    print()
    print("GENERAL:")
    print("  Bipartisan: Overall ideological score <20 (high cross-party voting)")
    print("  Moderate: Overall ideological score 20-50")
    print("  Party Loyalist: Overall ideological score >80")
    print()
    print("NOTE: For official caucus memberships (Freedom Caucus, Blue Dog Coalition, etc.),")
    print("you would need to maintain current membership lists from official sources.")

if __name__ == "__main__":
    main()
