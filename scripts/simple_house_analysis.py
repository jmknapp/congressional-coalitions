#!/usr/bin/env python3
"""
Simple House analysis that works with available data (votes and bills).
Enhanced with caching for performance.
"""

import os
import sys
import logging
import hashlib
import pickle
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from functools import lru_cache

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')
CACHE_DURATION_HOURS = 24  # Cache for 24 hours

def ensure_cache_dir():
    """Ensure cache directory exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_cache_key(prefix: str, *args) -> str:
    """Generate a cache key from arguments."""
    key_string = f"{prefix}:{':'.join(str(arg) for arg in args)}"
    return hashlib.md5(key_string.encode()).hexdigest()

def get_cache_path(cache_key: str) -> str:
    """Get the full path for a cache file."""
    return os.path.join(CACHE_DIR, f"{cache_key}.pkl")

def is_cache_valid(cache_path: str) -> bool:
    """Check if cache file is still valid."""
    if not os.path.exists(cache_path):
        return False
    
    # Check if cache is older than CACHE_DURATION_HOURS
    cache_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))
    return cache_age.total_seconds() < (CACHE_DURATION_HOURS * 3600)

def load_cache(cache_key: str):
    """Load data from cache."""
    cache_path = get_cache_path(cache_key)
    if is_cache_valid(cache_path):
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_key}: {e}")
    return None

def save_cache(cache_key: str, data):
    """Save data to cache."""
    ensure_cache_dir()
    cache_path = get_cache_path(cache_key)
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"Cached data for key: {cache_key}")
    except Exception as e:
        logger.warning(f"Failed to save cache {cache_key}: {e}")

def get_member_data_cached(congress: int, chamber: str) -> Dict:
    """Get member data with caching."""
    cache_key = get_cache_key("members", congress, chamber)
    cached_data = load_cache(cache_key)
    
    if cached_data is not None:
        logger.info(f"Using cached member data for Congress {congress}")
        return cached_data
    
    with get_db_session() as session:
        house_members = session.query(Member).filter(
            Member.district.isnot(None)
        ).all()
        
        member_data = {}
        for member in house_members:
            member_data[member.member_id_bioguide] = {
                'id': member.member_id_bioguide,
                'name': f"{member.first} {member.last}",
                'party': member.party,
                'state': member.state,
                'district': member.district
            }
        
        save_cache(cache_key, member_data)
        return member_data

def get_rollcall_data_cached(congress: int, chamber: str, start_date: str, end_date: str) -> Tuple[List, List]:
    """Get rollcall and vote data with caching."""
    cache_key = get_cache_key("rollcalls", congress, chamber, start_date, end_date)
    cached_data = load_cache(cache_key)
    
    if cached_data is not None:
        logger.info(f"Using cached rollcall data for Congress {congress}")
        return cached_data
    
    with get_db_session() as session:
        # Get House rollcalls in date range
        house_rollcalls = session.query(Rollcall).filter(
            Rollcall.congress == congress,
            Rollcall.chamber == chamber,
            Rollcall.date >= start_date,
            Rollcall.date <= end_date
        ).all()
        
        # Get votes for these rollcalls
        rollcall_ids = [rc.rollcall_id for rc in house_rollcalls]
        votes = session.query(Vote).filter(
            Vote.rollcall_id.in_(rollcall_ids)
        ).all()
        
        # Convert to serializable format
        rollcalls_data = []
        for rc in house_rollcalls:
            # Get bill title if bill_id exists
            bill_title = None
            if rc.bill_id:
                bill = session.query(Bill).filter(Bill.bill_id == rc.bill_id).first()
                if bill:
                    bill_title = bill.title
            
            rollcalls_data.append({
                'rollcall_id': rc.rollcall_id,
                'question': rc.question,
                'bill_id': rc.bill_id,
                'bill_title': bill_title,
                'date': rc.date.isoformat() if rc.date else None
            })
        
        votes_data = [
            {
                'rollcall_id': v.rollcall_id,
                'member_id_bioguide': v.member_id_bioguide,
                'vote_code': v.vote_code
            }
            for v in votes
        ]
        
        result = (rollcalls_data, votes_data)
        save_cache(cache_key, result)
        return result

def build_vote_matrix_cached(votes_data: List[Dict]) -> Dict:
    """Build vote matrix from cached vote data."""
    vote_matrix = {}
    for vote in votes_data:
        if vote['rollcall_id'] not in vote_matrix:
            vote_matrix[vote['rollcall_id']] = {}
        vote_matrix[vote['rollcall_id']][vote['member_id_bioguide']] = vote['vote_code']
    return vote_matrix

def calculate_voting_stats_cached(member_id: str, votes_data: List[Dict]) -> Dict:
    """Calculate voting statistics for a member with caching."""
    member_votes = [v for v in votes_data if v['member_id_bioguide'] == member_id]
    yea_votes = len([v for v in member_votes if v['vote_code'] == 'Yea'])
    nay_votes = len([v for v in member_votes if v['vote_code'] == 'Nay'])
    present_votes = len([v for v in member_votes if v['vote_code'] == 'Present'])
    total_votes = len(member_votes)
    
    return {
        'total_votes': total_votes,
        'yea_votes': yea_votes,
        'nay_votes': nay_votes,
        'present_votes': present_votes,
        'yea_percentage': (yea_votes / total_votes * 100) if total_votes > 0 else 0,
        'nay_percentage': (nay_votes / total_votes * 100) if total_votes > 0 else 0
    }

def calculate_party_line_voting_cached(vote_matrix: Dict, member_data: Dict) -> Dict:
    """Calculate party-line voting with caching."""
    party_line_votes = {}
    
    for rollcall_id, rollcall_votes in vote_matrix.items():
        party_votes = {'D': {'Yea': 0, 'Nay': 0}, 'R': {'Yea': 0, 'Nay': 0}}
        
        for member_id, vote_code in rollcall_votes.items():
            if member_id in member_data and vote_code in ['Yea', 'Nay']:
                party = member_data[member_id]['party']
                if party in ['D', 'R']:
                    party_votes[party][vote_code] += 1
        
        # Calculate party-line percentage
        d_total = party_votes['D']['Yea'] + party_votes['D']['Nay']
        r_total = party_votes['R']['Yea'] + party_votes['R']['Nay']
        
        if d_total > 0 and r_total > 0:
            d_yea_pct = party_votes['D']['Yea'] / d_total * 100
            r_yea_pct = party_votes['R']['Yea'] / r_total * 100
            party_line_score = abs(d_yea_pct - r_yea_pct)  # Difference between parties
            party_line_votes[rollcall_id] = party_line_score
    
    return party_line_votes

def run_simple_house_analysis(congress: int, chamber: str = 'house', window_days: int = 90) -> dict:
    """
    Run simplified analysis for House data with caching.
    
    Args:
        congress: Congress number
        chamber: Chamber (should be 'house')
        window_days: Analysis window in days
    
    Returns:
        Dictionary with analysis results
    """
    logger.info(f"Running simple House analysis for Congress {congress} with caching")
    
    # Calculate date window
    end_date = date.today()
    start_date = end_date - timedelta(days=window_days)
    
    # Load cached data
    member_data = get_member_data_cached(congress, chamber)
    rollcalls_data, votes_data = get_rollcall_data_cached(
        congress, chamber, start_date.isoformat(), end_date.isoformat()
    )
    
    # Build vote matrix
    vote_matrix = build_vote_matrix_cached(votes_data)
    
    # Calculate voting statistics (with caching)
    voting_stats = {}
    for member_id in member_data:
        voting_stats[member_id] = calculate_voting_stats_cached(member_id, votes_data)
    
    # Calculate party-line voting
    party_line_votes = calculate_party_line_voting_cached(vote_matrix, member_data)
    
    # Find most partisan votes
    most_partisan_votes = sorted(party_line_votes.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Find most bipartisan votes
    most_bipartisan_votes = sorted(party_line_votes.items(), key=lambda x: x[1])[:10]
    
    # Calculate cross-party voting for individual members
    cross_party_voters = []
    for member_id, member_info in member_data.items():
        if member_info['party'] not in ['D', 'R']:
            continue  # Skip independents for this analysis
            
        member_votes = [v for v in votes_data if v['member_id_bioguide'] == member_id]
        party_line_votes_for_member = []
        
        for vote in member_votes:
            rollcall_id = vote['rollcall_id']
            if rollcall_id in vote_matrix:
                # Calculate party consensus for this vote
                party_votes = {'D': {'Yea': 0, 'Nay': 0}, 'R': {'Yea': 0, 'Nay': 0}}
                
                for other_member_id, other_vote_code in vote_matrix[rollcall_id].items():
                    if other_member_id in member_data and other_vote_code in ['Yea', 'Nay']:
                        other_party = member_data[other_member_id]['party']
                        if other_party in ['D', 'R']:
                            party_votes[other_party][other_vote_code] += 1
                
                # Determine party consensus
                d_total = party_votes['D']['Yea'] + party_votes['D']['Nay']
                r_total = party_votes['R']['Yea'] + party_votes['R']['Nay']
                
                if d_total > 0 and r_total > 0:
                    d_yea_pct = party_votes['D']['Yea'] / d_total * 100
                    r_yea_pct = party_votes['R']['Yea'] / r_total * 100
                    
                    # Determine which way the member's party voted
                    member_party = member_info['party']
                    if member_party == 'D':
                        party_consensus = 'Yea' if d_yea_pct > 50 else 'Nay'
                    else:  # Republican
                        party_consensus = 'Yea' if r_yea_pct > 50 else 'Nay'
                    
                    # Check if member voted against party
                    if vote['vote_code'] in ['Yea', 'Nay'] and vote['vote_code'] != party_consensus:
                        party_line_votes_for_member.append(rollcall_id)
        
        # Calculate cross-party percentage
        total_votes = len([v for v in member_votes if v['vote_code'] in ['Yea', 'Nay']])
        if total_votes >= 10:  # Only include members with sufficient votes
            cross_party_percentage = (len(party_line_votes_for_member) / total_votes) * 100
            if cross_party_percentage >= 5:  # Only include if they cross party lines at least 5% of the time
                cross_party_voters.append({
                    'member_id': member_id,
                    'name': member_info['name'],
                    'party': member_info['party'],
                    'state': member_info['state'],
                    'cross_party_percentage': cross_party_percentage,
                    'total_votes': total_votes,
                    'cross_party_votes': len(party_line_votes_for_member)
                })
    
    # Sort by cross-party percentage (highest first)
    cross_party_voters.sort(key=lambda x: x['cross_party_percentage'], reverse=True)
    
    # Calculate member agreement scores (with optimization)
    member_agreement = {}
    for member1_id in member_data:
        member_agreement[member1_id] = {}
        for member2_id in member_data:
            if member1_id != member2_id:
                agreement_count = 0
                total_common_votes = 0
                
                for rollcall_id, rollcall_votes in vote_matrix.items():
                    if member1_id in rollcall_votes and member2_id in rollcall_votes:
                        vote1 = rollcall_votes[member1_id]
                        vote2 = rollcall_votes[member2_id]
                        
                        if vote1 in ['Yea', 'Nay'] and vote2 in ['Yea', 'Nay']:
                            total_common_votes += 1
                            if vote1 == vote2:
                                agreement_count += 1
                
                if total_common_votes > 0:
                    agreement_score = agreement_count / total_common_votes * 100
                    member_agreement[member1_id][member2_id] = agreement_score
    
    # Find most similar voting pairs
    voting_pairs = []
    for member1_id in member_agreement:
        for member2_id in member_agreement[member1_id]:
            if member1_id < member2_id:  # Avoid duplicates
                agreement = member_agreement[member1_id][member2_id]
                voting_pairs.append({
                    'member1': member_data[member1_id]['name'],
                    'member2': member_data[member2_id]['name'],
                    'party1': member_data[member1_id]['party'],
                    'party2': member_data[member2_id]['party'],
                    'agreement': agreement
                })
    
    most_similar_pairs = sorted(voting_pairs, key=lambda x: x['agreement'], reverse=True)[:10]
    
    # Find most different voting pairs
    most_different_pairs = sorted(voting_pairs, key=lambda x: x['agreement'])[:10]
    
    # Get recent bills (with caching)
    cache_key = get_cache_key("recent_bills", congress, chamber, start_date.isoformat())
    cached_bills = load_cache(cache_key)
    
    if cached_bills is not None:
        bill_data = cached_bills
    else:
        with get_db_session() as session:
            recent_bills = session.query(Bill).filter(
                Bill.congress == congress,
                Bill.chamber == chamber,
                Bill.introduced_date >= start_date
            ).order_by(Bill.introduced_date.desc()).limit(10).all()
            
            bill_data = []
            for bill in recent_bills:
                bill_data.append({
                    'bill_id': bill.bill_id,
                    'title': bill.title,
                    'introduced_date': bill.introduced_date.isoformat() if bill.introduced_date else None,
                    'sponsor_bioguide': bill.sponsor_bioguide
                })
            save_cache(cache_key, bill_data)
    
    # Compile results
    results = {
        'analysis_metadata': {
            'congress': congress,
            'chamber': chamber,
            'analysis_date': datetime.now().isoformat(),
            'window_days': window_days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'cache_used': True
        },
        'summary': {
            'total_members': len(member_data),
            'total_rollcalls': len(rollcalls_data),
            'total_votes': len(votes_data),
            'recent_bills': len(bill_data),
            'analysis_period': f"{start_date} to {end_date}"
        },
        'voting_analysis': {
            'most_partisan_votes': [
                {
                    'rollcall_id': rollcall_id,
                    'party_line_score': score,
                    'question': next((rc['question'] for rc in rollcalls_data if rc['rollcall_id'] == rollcall_id), 'Unknown'),
                    'bill_id': next((rc['bill_id'] for rc in rollcalls_data if rc['rollcall_id'] == rollcall_id), None),
                    'bill_title': next((rc.get('bill_title') for rc in rollcalls_data if rc['rollcall_id'] == rollcall_id), None)
                }
                for rollcall_id, score in most_partisan_votes
            ],
            'most_bipartisan_votes': [
                {
                    'rollcall_id': rollcall_id,
                    'party_line_score': score,
                    'question': next((rc['question'] for rc in rollcalls_data if rc['rollcall_id'] == rollcall_id), 'Unknown'),
                    'bill_id': next((rc['bill_id'] for rc in rollcalls_data if rc['rollcall_id'] == rollcall_id), None),
                    'bill_title': next((rc.get('bill_title') for rc in rollcalls_data if rc['rollcall_id'] == rollcall_id), None)
                }
                for rollcall_id, score in most_bipartisan_votes
            ]
        },
        'member_analysis': {
            'most_similar_voters': most_similar_pairs,
            'most_different_voters': most_different_pairs,
            'cross_party_voters': cross_party_voters[:20],  # Top 20 cross-party voters
            'voting_statistics': voting_stats
        },
        'recent_bills': bill_data
    }
    
    return results

if __name__ == "__main__":
    # Test the analysis
    results = run_simple_house_analysis(congress=119, chamber='house', window_days=90)
    
    print("=== SIMPLE HOUSE ANALYSIS RESULTS ===")
    print(f"Congress: {results['analysis_metadata']['congress']}")
    print(f"Analysis Period: {results['summary']['analysis_period']}")
    print(f"Cache Used: {results['analysis_metadata']['cache_used']}")
    print(f"Members: {results['summary']['total_members']}")
    print(f"Rollcalls: {results['summary']['total_rollcalls']}")
    print(f"Votes: {results['summary']['total_votes']}")
    
    print("\n=== MOST PARTISAN VOTES ===")
    for vote in results['voting_analysis']['most_partisan_votes'][:5]:
        print(f"{vote['rollcall_id']}: {vote['party_line_score']:.1f}% - {vote['question'][:50]}...")
    
    print("\n=== MOST SIMILAR VOTERS ===")
    for pair in results['member_analysis']['most_similar_voters'][:5]:
        print(f"{pair['member1']} ({pair['party1']}) & {pair['member2']} ({pair['party2']}): {pair['agreement']:.1f}% agreement")
