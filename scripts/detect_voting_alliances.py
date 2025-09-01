#!/usr/bin/env python3
"""
Detect informal voting alliances like "The Squad" using clustering analysis.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Vote, Rollcall
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import pandas as pd
from collections import defaultdict

def get_voting_matrix(congress=119, chamber='house'):
    """Create a voting matrix where rows are members and columns are rollcalls."""
    
    with get_db_session() as session:
        # Get all rollcalls
        rollcalls = session.query(Rollcall).filter(
            Rollcall.congress == congress,
            Rollcall.chamber == chamber
        ).order_by(Rollcall.rollcall_id).all()
        
        # Get all House members
        members = session.query(Member).filter(
            Member.district.isnot(None),  # House members only
            Member.party.in_(['D', 'R'])  # Only D and R for now
        ).order_by(Member.member_id_bioguide).all()
        
        print(f"Found {len(rollcalls)} rollcalls and {len(members)} members")
        
        # Extract member data while session is active
        member_data = []
        for member in members:
            member_data.append({
                'id': member.member_id_bioguide,
                'first': member.first,
                'last': member.last,
                'party': member.party,
                'state': member.state,
                'district': member.district
            })
        
        # Extract rollcall data while session is active
        rollcall_data = []
        for rollcall in rollcalls:
            rollcall_data.append({
                'id': rollcall.rollcall_id,
                'question': rollcall.question,
                'date': rollcall.date
            })
        
        # Create voting matrix
        voting_matrix = np.zeros((len(members), len(rollcalls)))
        member_ids = [m['id'] for m in member_data]
        rollcall_ids = [rc['id'] for rc in rollcall_data]
        
        # Get all votes
        votes = session.query(Vote).filter(
            Vote.rollcall_id.in_(rollcall_ids)
        ).all()
        
        # Fill the matrix
        for vote in votes:
            if vote.member_id_bioguide in member_ids and vote.rollcall_id in rollcall_ids:
                member_idx = member_ids.index(vote.member_id_bioguide)
                rollcall_idx = rollcall_ids.index(vote.rollcall_id)
                
                # Convert vote codes to numbers
                if vote.vote_code == 'Yea':
                    voting_matrix[member_idx, rollcall_idx] = 1
                elif vote.vote_code == 'Nay':
                    voting_matrix[member_idx, rollcall_idx] = -1
                # Present, Not Voting, etc. remain 0
        
        return voting_matrix, member_data, rollcall_data, member_ids, rollcall_ids

def detect_squad_clusters(voting_matrix, members, method='dbscan'):
    """Detect clusters that might represent 'The Squad' and other groups."""
    
    if method == 'dbscan':
        # DBSCAN for density-based clustering
        clustering = DBSCAN(eps=0.3, min_samples=3, metric='cosine')
        labels = clustering.fit_predict(voting_matrix)
    elif method == 'kmeans':
        # K-means for a specific number of clusters
        clustering = KMeans(n_clusters=8, random_state=42)
        labels = clustering.fit_predict(voting_matrix)
    
    # Group members by cluster
    clusters = defaultdict(list)
    for i, label in enumerate(labels):
        clusters[label].append(members[i])
    
    return clusters, labels

def analyze_cluster_voting_patterns(clusters, voting_matrix, members, rollcall_data, member_ids, rollcall_ids):
    """Analyze the voting patterns within each cluster."""
    
    results = {}
    
    for cluster_id, cluster_members in clusters.items():
        if cluster_id == -1:  # Noise points in DBSCAN
            continue
            
        print(f"\n=== CLUSTER {cluster_id} ({len(cluster_members)} members) ===")
        
        # Get member indices for this cluster
        cluster_indices = [member_ids.index(m['id']) for m in cluster_members]
        
        # Calculate cluster voting patterns
        cluster_votes = voting_matrix[cluster_indices, :]
        cluster_consensus = np.mean(cluster_votes, axis=0)
        
        # Find rollcalls where cluster was most unified
        unity_scores = np.abs(cluster_consensus)
        most_unified_indices = np.argsort(unity_scores)[-10:]  # Top 10 most unified
        
        print("Members:")
        for member in cluster_members:
            print(f"  - {member['first']} {member['last']} ({member['party']}) - {member['state']}-{member['district']}")
        
        print(f"\nCluster size: {len(cluster_members)}")
        print(f"Average unity score: {np.mean(unity_scores):.3f}")
        
        # Check party composition
        democrats = [m for m in cluster_members if m['party'] == 'D']
        republicans = [m for m in cluster_members if m['party'] == 'R']
        print(f"Party breakdown: {len(democrats)} Democrats, {len(republicans)} Republicans")
        
        # Look for potential "Squad" characteristics
        if len(democrats) >= 3 and len(republicans) == 0:
            print("🎯 POTENTIAL PROGRESSIVE DEMOCRAT GROUP (like 'The Squad')")
        elif len(democrats) == 0 and len(republicans) >= 3:
            print("🎯 POTENTIAL CONSERVATIVE REPUBLICAN GROUP")
        elif len(democrats) > 0 and len(republicans) > 0:
            print("🎯 MIXED-PARTY COALITION")
        
        results[cluster_id] = {
            'members': cluster_members,
            'size': len(cluster_members),
            'unity_score': np.mean(unity_scores),
            'democrats': len(democrats),
            'republicans': len(republicans),
            'most_unified_rollcalls': [(rollcall_data[i]['id'], unity_scores[i]) for i in most_unified_indices]
        }
    
    return results

def find_squad_candidates(results):
    """Identify the most likely 'Squad' candidates based on cluster analysis."""
    
    print("\n" + "="*60)
    print("🎯 SQUAD CANDIDATE ANALYSIS")
    print("="*60)
    
    # Look for clusters that match Squad characteristics
    squad_candidates = []
    
    for cluster_id, data in results.items():
        # Criteria for potential Squad:
        # - All Democrats
        # - Small to medium size (3-10 members)
        # - High unity score
        # - No Republicans
        
        if (data['democrats'] >= 3 and 
            data['republicans'] == 0 and 
            data['size'] <= 10 and
            data['unity_score'] > 0.7):
            
            squad_candidates.append((cluster_id, data))
    
    # Sort by unity score
    squad_candidates.sort(key=lambda x: x[1]['unity_score'], reverse=True)
    
    for cluster_id, data in squad_candidates:
        print(f"\n🔥 TOP SQUAD CANDIDATE - Cluster {cluster_id}")
        print(f"Unity Score: {data['unity_score']:.3f}")
        print(f"Size: {data['size']} members")
        print("Members:")
        for member in data['members']:
            print(f"  - {member['first']} {member['last']} ({member['state']}-{member['district']})")
    
    return squad_candidates

def main():
    """Main analysis function."""
    
    print("🔍 DETECTING VOTING ALLIANCES LIKE 'THE SQUAD'")
    print("=" * 60)
    
    # Get voting data
    voting_matrix, members, rollcall_data, member_ids, rollcall_ids = get_voting_matrix()
    
    if voting_matrix.size == 0:
        print("No voting data found!")
        return
    
    print(f"Voting matrix shape: {voting_matrix.shape}")
    
    # Detect clusters using DBSCAN
    print("\n🔍 Detecting clusters using DBSCAN...")
    clusters, labels = detect_squad_clusters(voting_matrix, members, method='dbscan')
    
    # Analyze cluster patterns
    results = analyze_cluster_voting_patterns(clusters, voting_matrix, members, rollcall_data, member_ids, rollcall_ids)
    
    # Find Squad candidates
    squad_candidates = find_squad_candidates(results)
    
    print(f"\n✅ Analysis complete! Found {len(squad_candidates)} potential Squad-like groups.")

if __name__ == "__main__":
    main()
