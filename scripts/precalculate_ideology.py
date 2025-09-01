#!/usr/bin/env python3
"""
Pre-calculate ideological profiles for all members and store them efficiently.
This script should be run periodically to update ideological data.
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote
from scripts.ideological_labeling import calculate_voting_ideology_scores_fast, assign_ideological_labels

logger = logging.getLogger(__name__)

def precalculate_all_ideological_profiles(congress: int = 119, chamber: str = 'house'):
    """
    Pre-calculate ideological profiles for all members and store them.
    """
    print(f"=== PRECALCULATING IDEOLOGICAL PROFILES ===")
    print(f"Congress: {congress}, Chamber: {chamber}")
    print()
    
    # Calculate all member scores at once (much more efficient)
    print("Calculating voting ideology scores for all members...")
    member_scores = calculate_voting_ideology_scores_fast(congress, chamber)
    
    print("Assigning ideological labels...")
    labeled_members = assign_ideological_labels(member_scores)
    
    # Store results in a cache file
    cache_file = f"cache/ideological_profiles_{congress}_{chamber}.json"
    os.makedirs("cache", exist_ok=True)
    
    # Prepare data for storage
    cache_data = {
        'metadata': {
            'congress': congress,
            'chamber': chamber,
            'calculated_at': datetime.now().isoformat(),
            'total_members': len(labeled_members)
        },
        'profiles': {}
    }
    
    for member_id, profile in labeled_members.items():
        cache_data['profiles'][member_id] = {
            'labels': profile['labels'],
            'primary_label': profile['primary_label'],
            'party_line_percentage': round(profile['party_line_percentage'], 1),
            'cross_party_percentage': round(profile['cross_party_percentage'], 1),
            'ideological_score': round(profile['ideological_score'], 1),
            'total_votes': profile['total_votes'],
            'note': 'Based on voting patterns, not official caucus memberships'
        }
    
    # Save to cache file
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
    
    print(f"Saved {len(labeled_members)} ideological profiles to {cache_file}")
    
    # Show summary
    print("\n=== SUMMARY ===")
    label_counts = defaultdict(int)
    for profile in labeled_members.values():
        for label in profile['labels']:
            label_counts[label] += 1
    
    print("Label distribution:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count} members")
    
    return cache_file

def load_ideological_profiles(congress: int = 119, chamber: str = 'house') -> Dict:
    """
    Load pre-calculated ideological profiles from cache.
    """
    cache_file = f"cache/ideological_profiles_{congress}_{chamber}.json"
    
    if not os.path.exists(cache_file):
        print(f"Cache file not found: {cache_file}")
        print("Run precalculate_all_ideological_profiles() first")
        return {}
    
    with open(cache_file, 'r') as f:
        data = json.load(f)
    
    return data

def get_member_ideology_fast(member_id: str, congress: int = 119, chamber: str = 'house') -> Dict:
    """
    Get ideological profile for a single member from cache (fast).
    """
    cache_data = load_ideological_profiles(congress, chamber)
    
    if not cache_data or 'profiles' not in cache_data:
        return {
            'labels': ['Cache Not Available'],
            'primary_label': 'Cache Not Available',
            'note': 'Ideological profiles not pre-calculated. Run precalculate_all_ideological_profiles() first.'
        }
    
    profile = cache_data['profiles'].get(member_id)
    if not profile:
        return {
            'labels': ['Member Not Found'],
            'primary_label': 'Member Not Found',
            'note': 'Member not found in ideological analysis cache.'
        }
    
    return profile

if __name__ == "__main__":
    # Pre-calculate all profiles
    cache_file = precalculate_all_ideological_profiles()
    print(f"\nCache file created: {cache_file}")
    
    # Test loading a few profiles
    print("\n=== TESTING CACHE ===")
    cache_data = load_ideological_profiles()
    if cache_data and 'profiles' in cache_data:
        sample_members = list(cache_data['profiles'].keys())[:3]
        for member_id in sample_members:
            profile = get_member_ideology_fast(member_id)
            print(f"Member {member_id}: {profile['primary_label']}")
    
    print("\n=== NEW LABELS ===")
    print("MAGA Republican: High party loyalty Republicans (>95% party line voting)")
    print("True Blue Democrat: High party loyalty Democrats (>95% party line voting)")
    print("Mainstream: Moderate party loyalty (70-95% party line voting)")
    print("Cross-Party: High cross-party voting (>20% with opposite party)")
    
    print("\n=== USAGE ===")
    print("In your Flask app, replace the slow calculate_member_ideology() function")
    print("with get_member_ideology_fast() for instant results.")
