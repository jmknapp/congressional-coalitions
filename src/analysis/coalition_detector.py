"""
Coalition detection and analysis for congressional voting patterns.

This module implements network-based coalition detection using vote agreement,
cosponsorship patterns, and amendment sponsorship to identify congressional blocs.
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
import networkx as nx
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Set
from sklearn.metrics import adjusted_rand_score
from sklearn.cluster import DBSCAN
import community  # python-louvain
from tqdm import tqdm
import json

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Cosponsor, Rollcall, Vote, BillSubject, Amendment

logger = logging.getLogger(__name__)

class CoalitionDetector:
    """Detects and analyzes congressional coalitions using network methods."""
    
    def __init__(self, congress: int, chamber: str):
        self.congress = congress
        self.chamber = chamber
        self.members = {}
        self.vote_matrix = None
        self.cosponsor_matrix = None
        self.amendment_matrix = None
        
    def load_members(self, start_date: Optional[date] = None, end_date: Optional[date] = None):
        """Load active members for the specified Congress and chamber."""
        with get_db_session() as session:
            query = session.query(Member).filter(
                Member.start_date <= end_date if end_date else True,
                (Member.end_date >= start_date) | (Member.end_date.is_(None)) if start_date else True
            )
            
            # Filter by chamber (House has districts, Senate doesn't)
            if self.chamber == 'house':
                query = query.filter(Member.district.isnot(None))
            elif self.chamber == 'senate':
                query = query.filter(Member.district.is_(None))
            
            members = query.all()
            
            self.members = {
                member.member_id_bioguide: {
                    'id': member.member_id_bioguide,
                    'name': f"{member.first} {member.last}",
                    'party': member.party,
                    'state': member.state,
                    'district': member.district
                }
                for member in members
            }
            
            logger.info(f"Loaded {len(self.members)} {self.chamber} members")
    
    def build_vote_agreement_matrix(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> pd.DataFrame:
        """
        Build member×member vote agreement matrix.
        
        Args:
            start_date: Start date for vote window
            end_date: End date for vote window
        
        Returns:
            DataFrame with agreement rates between members
        """
        logger.info("Building vote agreement matrix...")
        
        with get_db_session() as session:
            # Get roll calls in date range
            query = session.query(Rollcall).filter(
                Rollcall.congress == self.congress,
                Rollcall.chamber == self.chamber
            )
            
            if start_date:
                query = query.filter(Rollcall.date >= start_date)
            if end_date:
                query = query.filter(Rollcall.date <= end_date)
            
            rollcalls = query.all()
            rollcall_ids = [rc.rollcall_id for rc in rollcalls]
            
            if not rollcall_ids:
                logger.warning("No roll calls found for the specified criteria")
                return pd.DataFrame()
            
            # Get all votes for these roll calls
            votes = session.query(Vote).filter(Vote.rollcall_id.in_(rollcall_ids)).all()
            
            # Create vote matrix: members × rollcalls
            vote_data = {}
            for vote in votes:
                if vote.member_id_bioguide in self.members:
                    if vote.member_id_bioguide not in vote_data:
                        vote_data[vote.member_id_bioguide] = {}
                    vote_data[vote.member_id_bioguide][vote.rollcall_id] = vote.vote_code
            
            # Convert to DataFrame
            vote_df = pd.DataFrame.from_dict(vote_data, orient='index')
            
            # Calculate agreement matrix
            agreement_matrix = pd.DataFrame(index=vote_df.index, columns=vote_df.index)
            
            for i, member1 in enumerate(vote_df.index):
                for j, member2 in enumerate(vote_df.index):
                    if i <= j:  # Only calculate upper triangle
                        # Get votes where both members voted
                        common_votes = vote_df.loc[member1].notna() & vote_df.loc[member2].notna()
                        if common_votes.sum() > 0:
                            # Calculate agreement rate
                            member1_votes = vote_df.loc[member1, common_votes]
                            member2_votes = vote_df.loc[member2, common_votes]
                            
                            # Agreement when both vote Yea or both vote Nay
                            agreement = ((member1_votes == 'Yea') & (member2_votes == 'Yea') |
                                       (member1_votes == 'Nay') & (member2_votes == 'Nay')).sum()
                            
                            agreement_rate = agreement / common_votes.sum()
                            agreement_matrix.loc[member1, member2] = agreement_rate
                            agreement_matrix.loc[member2, member1] = agreement_rate
                        else:
                            agreement_matrix.loc[member1, member2] = 0.0
                            agreement_matrix.loc[member2, member1] = 0.0
            
            self.vote_matrix = agreement_matrix
            logger.info(f"Built vote agreement matrix with {len(agreement_matrix)} members")
            return agreement_matrix
    
    def build_cosponsorship_matrix(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> pd.DataFrame:
        """
        Build member×member cosponsorship similarity matrix using Jaccard similarity.
        
        Args:
            start_date: Start date for cosponsorship window
            end_date: End date for cosponsorship window
        
        Returns:
            DataFrame with Jaccard similarity between members
        """
        logger.info("Building cosponsorship similarity matrix...")
        
        with get_db_session() as session:
            # Get bills in date range
            query = session.query(Bill).filter(
                Bill.congress == self.congress,
                Bill.chamber == self.chamber
            )
            
            if start_date:
                query = query.filter(Bill.introduced_date >= start_date)
            if end_date:
                query = query.filter(Bill.introduced_date <= end_date)
            
            bills = query.all()
            bill_ids = [bill.bill_id for bill in bills]
            
            if not bill_ids:
                logger.warning("No bills found for the specified criteria")
                return pd.DataFrame()
            
            # Get cosponsorships
            cosponsors = session.query(Cosponsor).filter(Cosponsor.bill_id.in_(bill_ids)).all()
            
            # Build member-bill matrix
            member_bills = {}
            for cosponsor in cosponsors:
                if cosponsor.member_id_bioguide in self.members:
                    if cosponsor.member_id_bioguide not in member_bills:
                        member_bills[cosponsor.member_id_bioguide] = set()
                    member_bills[cosponsor.member_id_bioguide].add(cosponsor.bill_id)
            
            # Calculate Jaccard similarity
            members = list(member_bills.keys())
            similarity_matrix = pd.DataFrame(index=members, columns=members)
            
            for i, member1 in enumerate(members):
                for j, member2 in enumerate(members):
                    if i <= j:
                        bills1 = member_bills[member1]
                        bills2 = member_bills[member2]
                        
                        intersection = len(bills1 & bills2)
                        union = len(bills1 | bills2)
                        
                        jaccard = intersection / union if union > 0 else 0.0
                        similarity_matrix.loc[member1, member2] = jaccard
                        similarity_matrix.loc[member2, member1] = jaccard
            
            self.cosponsor_matrix = similarity_matrix
            logger.info(f"Built cosponsorship similarity matrix with {len(similarity_matrix)} members")
            return similarity_matrix
    
    def build_amendment_matrix(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> pd.DataFrame:
        """
        Build member×member amendment sponsorship similarity matrix.
        
        Args:
            start_date: Start date for amendment window
            end_date: End date for amendment window
        
        Returns:
            DataFrame with amendment similarity between members
        """
        logger.info("Building amendment similarity matrix...")
        
        with get_db_session() as session:
            # Get amendments in date range
            query = session.query(Amendment).join(Bill).filter(
                Bill.congress == self.congress,
                Bill.chamber == self.chamber
            )
            
            if start_date:
                query = query.filter(Amendment.introduced_date >= start_date)
            if end_date:
                query = query.filter(Amendment.introduced_date <= end_date)
            
            amendments = query.all()
            
            if not amendments:
                logger.warning("No amendments found for the specified criteria")
                return pd.DataFrame()
            
            # Build member-amendment matrix
            member_amendments = {}
            for amendment in amendments:
                if amendment.sponsor_bioguide in self.members:
                    if amendment.sponsor_bioguide not in member_amendments:
                        member_amendments[amendment.sponsor_bioguide] = set()
                    member_amendments[amendment.sponsor_bioguide].add(amendment.amendment_id)
            
            # Calculate Jaccard similarity
            members = list(member_amendments.keys())
            similarity_matrix = pd.DataFrame(index=members, columns=members)
            
            for i, member1 in enumerate(members):
                for j, member2 in enumerate(members):
                    if i <= j:
                        amendments1 = member_amendments[member1]
                        amendments2 = member_amendments[member2]
                        
                        intersection = len(amendments1 & amendments2)
                        union = len(amendments1 | amendments2)
                        
                        jaccard = intersection / union if union > 0 else 0.0
                        similarity_matrix.loc[member1, member2] = jaccard
                        similarity_matrix.loc[member2, member1] = jaccard
            
            self.amendment_matrix = similarity_matrix
            logger.info(f"Built amendment similarity matrix with {len(similarity_matrix)} members")
            return similarity_matrix
    
    def build_multiplex_network(self, alpha: float = 0.6, beta: float = 0.3, gamma: float = 0.1) -> nx.Graph:
        """
        Build multiplex network combining vote agreement, cosponsorship, and amendment similarity.
        
        Args:
            alpha: Weight for vote agreement (default 0.6)
            beta: Weight for cosponsorship similarity (default 0.3)
            gamma: Weight for amendment similarity (default 0.1)
        
        Returns:
            NetworkX graph with weighted edges
        """
        logger.info("Building multiplex network...")
        
        if self.vote_matrix is None or self.cosponsor_matrix is None:
            raise ValueError("Must build vote and cosponsor matrices before creating multiplex network")
        
        # Get common members across vote and cosponsor matrices
        members = set(self.vote_matrix.index) & set(self.cosponsor_matrix.index)
        
        # Add amendment matrix members if available
        if self.amendment_matrix is not None and not self.amendment_matrix.empty:
            members = members & set(self.amendment_matrix.index)
        
        # Create graph
        G = nx.Graph()
        
        # Add nodes
        for member in members:
            G.add_node(member, **self.members[member])
        
        # Add weighted edges
        for i, member1 in enumerate(members):
            for j, member2 in enumerate(members):
                if i < j:  # Avoid duplicate edges
                    weight = 0.0
                    
                    # Vote agreement weight
                    if member1 in self.vote_matrix.index and member2 in self.vote_matrix.columns:
                        vote_weight = self.vote_matrix.loc[member1, member2] * alpha
                        weight += vote_weight
                    
                    # Cosponsorship weight
                    if member1 in self.cosponsor_matrix.index and member2 in self.cosponsor_matrix.columns:
                        cosponsor_weight = self.cosponsor_matrix.loc[member1, member2] * beta
                        weight += cosponsor_weight
                    
                    # Amendment weight
                    if (self.amendment_matrix is not None and not self.amendment_matrix.empty and
                        member1 in self.amendment_matrix.index and member2 in self.amendment_matrix.columns):
                        amendment_weight = self.amendment_matrix.loc[member1, member2] * gamma
                        weight += amendment_weight
                    
                    if weight > 0:
                        G.add_edge(member1, member2, weight=weight)
        
        logger.info(f"Built multiplex network with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return G
    
    def detect_coalitions(self, G: nx.Graph, method: str = 'louvain') -> Dict:
        """
        Detect coalitions using community detection algorithms.
        
        Args:
            G: NetworkX graph
            method: 'louvain' or 'dbscan'
        
        Returns:
            Dictionary with coalition information
        """
        logger.info(f"Detecting coalitions using {method} method...")
        
        if method == 'louvain':
            # Louvain community detection
            partition = community.best_partition(G)
            
            # Group members by community
            communities = {}
            for node, community_id in partition.items():
                if community_id not in communities:
                    communities[community_id] = []
                communities[community_id].append(node)
            
        elif method == 'dbscan':
            # DBSCAN clustering on edge weights
            edges = list(G.edges(data=True))
            if not edges:
                return {}
            
            # Extract edge weights as features
            weights = [edge[2]['weight'] for edge in edges]
            weights = np.array(weights).reshape(-1, 1)
            
            # Apply DBSCAN
            clustering = DBSCAN(eps=0.1, min_samples=2).fit(weights)
            
            # Group edges by cluster
            communities = {}
            for i, (u, v, _) in enumerate(edges):
                cluster_id = clustering.labels_[i]
                if cluster_id >= 0:  # Skip noise points
                    if cluster_id not in communities:
                        communities[cluster_id] = set()
                    communities[cluster_id].add(u)
                    communities[cluster_id].add(v)
            
            # Convert sets to lists
            communities = {k: list(v) for k, v in communities.items()}
        
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Analyze coalitions
        coalition_analysis = {}
        for coalition_id, members in communities.items():
            if len(members) < 2:  # Skip single-member coalitions
                continue
            
            # Get member details
            member_details = [self.members[member] for member in members]
            
            # Calculate party composition
            parties = [m['party'] for m in member_details]
            party_counts = pd.Series(parties).value_counts()
            
            # Calculate coalition characteristics
            coalition_analysis[coalition_id] = {
                'size': len(members),
                'members': members,
                'member_details': member_details,
                'party_composition': party_counts.to_dict(),
                'bipartisan': len(party_counts) > 1,
                'avg_vote_agreement': self._calculate_avg_agreement(members),
                'avg_cosponsorship': self._calculate_avg_cosponsorship(members)
            }
        
        logger.info(f"Detected {len(coalition_analysis)} coalitions")
        return coalition_analysis
    
    def _calculate_avg_agreement(self, members: List[str]) -> float:
        """Calculate average vote agreement within a coalition."""
        if self.vote_matrix is None or len(members) < 2:
            return 0.0
        
        agreements = []
        for i, member1 in enumerate(members):
            for j, member2 in enumerate(members):
                if i < j and member1 in self.vote_matrix.index and member2 in self.vote_matrix.columns:
                    agreement = self.vote_matrix.loc[member1, member2]
                    if not pd.isna(agreement):
                        agreements.append(agreement)
        
        return np.mean(agreements) if agreements else 0.0
    
    def _calculate_avg_cosponsorship(self, members: List[str]) -> float:
        """Calculate average cosponsorship similarity within a coalition."""
        if self.cosponsor_matrix is None or len(members) < 2:
            return 0.0
        
        similarities = []
        for i, member1 in enumerate(members):
            for j, member2 in enumerate(members):
                if i < j and member1 in self.cosponsor_matrix.index and member2 in self.cosponsor_matrix.columns:
                    similarity = self.cosponsor_matrix.loc[member1, member2]
                    if not pd.isna(similarity):
                        similarities.append(similarity)
        
        return np.mean(similarities) if similarities else 0.0
    
    def get_coalition_subjects(self, coalition_members: List[str], top_n: int = 5) -> List[Tuple[str, int]]:
        """
        Get top subjects for a coalition based on their cosponsored bills.
        
        Args:
            coalition_members: List of member IDs in the coalition
            top_n: Number of top subjects to return
        
        Returns:
            List of (subject, count) tuples
        """
        with get_db_session() as session:
            # Get bills cosponsored by coalition members
            cosponsored_bills = session.query(Cosponsor.bill_id).filter(
                Cosponsor.member_id_bioguide.in_(coalition_members)
            ).distinct().all()
            
            bill_ids = [bill[0] for bill in cosponsored_bills]
            
            if not bill_ids:
                return []
            
            # Get subjects for these bills
            subjects = session.query(BillSubject.subject_term).filter(
                BillSubject.bill_id.in_(bill_ids)
            ).all()
            
            # Count subject frequencies
            subject_counts = pd.Series([subject[0] for subject in subjects]).value_counts()
            
            return list(subject_counts.head(top_n).items())
    
    def analyze_coalitions(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict:
        """
        Complete coalition analysis pipeline.
        
        Args:
            start_date: Start date for analysis window
            end_date: End date for analysis window
        
        Returns:
            Dictionary with complete coalition analysis
        """
        logger.info(f"Starting coalition analysis for {self.chamber} in Congress {self.congress}")
        
        # Load members
        self.load_members(start_date, end_date)
        
        # Build matrices
        self.build_vote_agreement_matrix(start_date, end_date)
        self.build_cosponsorship_matrix(start_date, end_date)
        self.build_amendment_matrix(start_date, end_date)
        
        # Build multiplex network
        G = self.build_multiplex_network()
        
        # Detect coalitions
        coalitions = self.detect_coalitions(G)
        
        # Add subject analysis to each coalition
        for coalition_id, coalition_data in coalitions.items():
            subjects = self.get_coalition_subjects(coalition_data['members'])
            coalition_data['top_subjects'] = subjects
        
        return {
            'congress': self.congress,
            'chamber': self.chamber,
            'analysis_date': datetime.now().isoformat(),
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'total_members': len(self.members),
            'coalitions': coalitions,
            'network_stats': {
                'nodes': G.number_of_nodes(),
                'edges': G.number_of_edges(),
                'density': nx.density(G)
            }
        }


