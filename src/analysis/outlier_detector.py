"""
Outlier detection for congressional voting patterns.

This module identifies "unexpected" votes by members using both simple party-line
deviation rules and more sophisticated model-based approaches.
"""

import os
import sys
import logging
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report
import click
from tqdm import tqdm

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Rollcall, Vote, Bill, Cosponsor

logger = logging.getLogger(__name__)

class OutlierDetector:
    """Detects unexpected votes using multiple methods."""
    
    def __init__(self, congress: int, chamber: str):
        self.congress = congress
        self.chamber = chamber
        self.members = {}
        self.vote_model = None
        self.scaler = StandardScaler()
        
    def load_members(self):
        """Load member information for the specified Congress and chamber."""
        with get_db_session() as session:
            query = session.query(Member)
            
            # Filter by chamber
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
    
    def detect_party_line_deviations(self, start_date: Optional[date] = None, end_date: Optional[date] = None, threshold: float = 0.8) -> List[Dict]:
        """
        Detect votes where members break from their party line.
        
        Args:
            start_date: Start date for analysis window
            end_date: End date for analysis window
            threshold: Minimum party agreement percentage to consider a "party line" vote
        
        Returns:
            List of outlier vote records
        """
        logger.info(f"Detecting party line deviations with {threshold*100}% threshold...")
        
        outliers = []
        
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
            
            for rollcall in tqdm(rollcalls, desc="Analyzing roll calls"):
                # Get all votes for this roll call
                votes = session.query(Vote).filter(Vote.rollcall_id == rollcall.rollcall_id).all()
                
                # Group votes by party
                party_votes = {}
                for vote in votes:
                    if vote.member_id_bioguide in self.members:
                        party = self.members[vote.member_id_bioguide]['party']
                        if party not in party_votes:
                            party_votes[party] = {'Yea': 0, 'Nay': 0, 'Present': 0, 'Not Voting': 0}
                        party_votes[party][vote.vote_code] += 1
                
                # Check each party for party line votes
                for party, vote_counts in party_votes.items():
                    total_votes = sum(vote_counts.values())
                    if total_votes < 5:  # Skip small parties
                        continue
                    
                    yea_pct = vote_counts['Yea'] / total_votes
                    nay_pct = vote_counts['Nay'] / total_votes
                    
                    # Determine party position
                    if yea_pct >= threshold:
                        party_position = 'Yea'
                        expected_votes = vote_counts['Yea']
                        unexpected_votes = vote_counts['Nay']
                    elif nay_pct >= threshold:
                        party_position = 'Nay'
                        expected_votes = vote_counts['Nay']
                        unexpected_votes = vote_counts['Yea']
                    else:
                        continue  # Not a party line vote
                    
                    # Find members who broke from party line
                    for vote in votes:
                        if (vote.member_id_bioguide in self.members and 
                            self.members[vote.member_id_bioguide]['party'] == party and
                            vote.vote_code != party_position and
                            vote.vote_code in ['Yea', 'Nay']):
                            
                            outlier = {
                                'rollcall_id': rollcall.rollcall_id,
                                'member_id': vote.member_id_bioguide,
                                'member_name': self.members[vote.member_id_bioguide]['name'],
                                'party': party,
                                'vote': vote.vote_code,
                                'party_position': party_position,
                                'party_yea_pct': yea_pct,
                                'party_nay_pct': nay_pct,
                                'method': 'party_line_deviation',
                                'date': rollcall.date,
                                'question': rollcall.question,
                                'bill_id': rollcall.bill_id
                            }
                            outliers.append(outlier)
        
        logger.info(f"Found {len(outliers)} party line deviations")
        return outliers
    
    def build_vote_prediction_model(self, start_date: Optional[date] = None, end_date: Optional[date] = None):
        """
        Build a logistic regression model to predict votes based on member characteristics.
        
        Args:
            start_date: Start date for training data
            end_date: End date for training data
        """
        logger.info("Building vote prediction model...")
        
        with get_db_session() as session:
            # Get historical votes for training
            query = session.query(Rollcall).filter(
                Rollcall.congress == self.congress,
                Rollcall.chamber == self.chamber
            )
            
            if start_date:
                query = query.filter(Rollcall.date >= start_date)
            if end_date:
                query = query.filter(Rollcall.date <= end_date)
            
            rollcalls = query.all()
            
            # Prepare training data
            X = []  # Features
            y = []  # Target (Yea/Nay)
            
            for rollcall in tqdm(rollcalls, desc="Building training data"):
                votes = session.query(Vote).filter(Vote.rollcall_id == rollcall.rollcall_id).all()
                
                # Calculate roll call features
                total_votes = len(votes)
                yea_votes = sum(1 for v in votes if v.vote_code == 'Yea')
                nay_votes = sum(1 for v in votes if v.vote_code == 'Nay')
                yea_pct = yea_votes / total_votes if total_votes > 0 else 0.5
                
                # Get party composition
                party_votes = {}
                for vote in votes:
                    if vote.member_id_bioguide in self.members:
                        party = self.members[vote.member_id_bioguide]['party']
                        if party not in party_votes:
                            party_votes[party] = {'Yea': 0, 'Nay': 0}
                        if vote.vote_code in ['Yea', 'Nay']:
                            party_votes[party][vote.vote_code] += 1
                
                # Calculate bipartisan score
                bipartisan_score = 0.0
                if len(party_votes) >= 2:
                    parties = list(party_votes.keys())
                    for i, party1 in enumerate(parties):
                        for party2 in parties[i+1:]:
                            party1_yea = party_votes[party1]['Yea']
                            party1_nay = party_votes[party1]['Nay']
                            party2_yea = party_votes[party2]['Yea']
                            party2_nay = party_votes[party2]['Nay']
                            
                            if party1_yea + party1_nay > 0 and party2_yea + party2_nay > 0:
                                # Calculate agreement between parties
                                party1_yea_pct = party1_yea / (party1_yea + party1_nay)
                                party2_yea_pct = party2_yea / (party2_yea + party2_nay)
                                agreement = 1 - abs(party1_yea_pct - party2_yea_pct)
                                bipartisan_score = max(bipartisan_score, agreement)
                
                # Check if bill has bipartisan cosponsorship
                bipartisan_cosponsorship = False
                if rollcall.bill_id:
                    cosponsors = session.query(Cosponsor).filter(Cosponsor.bill_id == rollcall.bill_id).all()
                    if len(cosponsors) > 0:
                        cosponsor_parties = set()
                        for cosponsor in cosponsors:
                            if cosponsor.member_id_bioguide in self.members:
                                cosponsor_parties.add(self.members[cosponsor.member_id_bioguide]['party'])
                        bipartisan_cosponsorship = len(cosponsor_parties) > 1
                
                # Add features for each member vote
                for vote in votes:
                    if (vote.member_id_bioguide in self.members and 
                        vote.vote_code in ['Yea', 'Nay']):
                        
                        member = self.members[vote.member_id_bioguide]
                        
                        # Member features
                        features = [
                            1.0 if member['party'] == 'D' else 0.0,  # Democratic
                            1.0 if member['party'] == 'R' else 0.0,  # Republican
                            1.0 if member['party'] == 'I' else 0.0,  # Independent
                            yea_pct,  # Overall yea percentage
                            bipartisan_score,  # Bipartisan agreement score
                            1.0 if bipartisan_cosponsorship else 0.0,  # Bipartisan cosponsorship
                            1.0 if rollcall.bill_id else 0.0,  # Has associated bill
                        ]
                        
                        X.append(features)
                        y.append(1 if vote.vote_code == 'Yea' else 0)
            
            if len(X) == 0:
                logger.warning("No training data found")
                return
            
            # Train model
            X = np.array(X)
            y = np.array(y)
            
            # Scale features
            X_scaled = self.scaler.fit_transform(X)
            
            # Train logistic regression
            self.vote_model = LogisticRegression(random_state=42, max_iter=1000)
            self.vote_model.fit(X_scaled, y)
            
            logger.info(f"Trained vote prediction model on {len(X)} samples")
    
    def detect_model_based_outliers(self, start_date: Optional[date] = None, end_date: Optional[date] = None, z_threshold: float = 2.0) -> List[Dict]:
        """
        Detect outliers using the trained prediction model.
        
        Args:
            start_date: Start date for analysis window
            end_date: End date for analysis window
            z_threshold: Z-score threshold for outlier detection
        
        Returns:
            List of outlier vote records
        """
        if self.vote_model is None:
            logger.error("Must train model before detecting model-based outliers")
            return []
        
        logger.info(f"Detecting model-based outliers with z-score threshold {z_threshold}...")
        
        outliers = []
        
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
            
            for rollcall in tqdm(rollcalls, desc="Analyzing roll calls"):
                votes = session.query(Vote).filter(Vote.rollcall_id == rollcall.rollcall_id).all()
                
                # Calculate roll call features (same as in training)
                total_votes = len(votes)
                yea_votes = sum(1 for v in votes if v.vote_code == 'Yea')
                nay_votes = sum(1 for v in votes if v.vote_code == 'Nay')
                yea_pct = yea_votes / total_votes if total_votes > 0 else 0.5
                
                # Party composition
                party_votes = {}
                for vote in votes:
                    if vote.member_id_bioguide in self.members:
                        party = self.members[vote.member_id_bioguide]['party']
                        if party not in party_votes:
                            party_votes[party] = {'Yea': 0, 'Nay': 0}
                        if vote.vote_code in ['Yea', 'Nay']:
                            party_votes[party][vote.vote_code] += 1
                
                # Bipartisan score
                bipartisan_score = 0.0
                if len(party_votes) >= 2:
                    parties = list(party_votes.keys())
                    for i, party1 in enumerate(parties):
                        for party2 in parties[i+1:]:
                            party1_yea = party_votes[party1]['Yea']
                            party1_nay = party_votes[party1]['Nay']
                            party2_yea = party_votes[party2]['Yea']
                            party2_nay = party_votes[party2]['Nay']
                            
                            if party1_yea + party1_nay > 0 and party2_yea + party2_nay > 0:
                                party1_yea_pct = party1_yea / (party1_yea + party1_nay)
                                party2_yea_pct = party2_yea / (party2_yea + party2_nay)
                                agreement = 1 - abs(party1_yea_pct - party2_yea_pct)
                                bipartisan_score = max(bipartisan_score, agreement)
                
                # Bipartisan cosponsorship
                bipartisan_cosponsorship = False
                if rollcall.bill_id:
                    cosponsors = session.query(Cosponsor).filter(Cosponsor.bill_id == rollcall.bill_id).all()
                    if len(cosponsors) > 0:
                        cosponsor_parties = set()
                        for cosponsor in cosponsors:
                            if cosponsor.member_id_bioguide in self.members:
                                cosponsor_parties.add(self.members[cosponsor.member_id_bioguide]['party'])
                        bipartisan_cosponsorship = len(cosponsor_parties) > 1
                
                # Predict votes for each member
                for vote in votes:
                    if (vote.member_id_bioguide in self.members and 
                        vote.vote_code in ['Yea', 'Nay']):
                        
                        member = self.members[vote.member_id_bioguide]
                        
                        # Features
                        features = [
                            1.0 if member['party'] == 'D' else 0.0,
                            1.0 if member['party'] == 'R' else 0.0,
                            1.0 if member['party'] == 'I' else 0.0,
                            yea_pct,
                            bipartisan_score,
                            1.0 if bipartisan_cosponsorship else 0.0,
                            1.0 if rollcall.bill_id else 0.0,
                        ]
                        
                        # Scale features
                        features_scaled = self.scaler.transform([features])
                        
                        # Get prediction
                        pred_proba = self.vote_model.predict_proba(features_scaled)[0]
                        pred_yea_prob = pred_proba[1]  # Probability of voting Yea
                        
                        # Calculate z-score of prediction error
                        actual_yea = 1 if vote.vote_code == 'Yea' else 0
                        prediction_error = abs(actual_yea - pred_yea_prob)
                        
                        # Simple outlier detection based on prediction error
                        if prediction_error > 0.5:  # Predicted opposite of actual
                            outlier = {
                                'rollcall_id': rollcall.rollcall_id,
                                'member_id': vote.member_id_bioguide,
                                'member_name': member['name'],
                                'party': member['party'],
                                'vote': vote.vote_code,
                                'predicted_yea_prob': pred_yea_prob,
                                'prediction_error': prediction_error,
                                'method': 'model_based',
                                'date': rollcall.date,
                                'question': rollcall.question,
                                'bill_id': rollcall.bill_id
                            }
                            outliers.append(outlier)
        
        logger.info(f"Found {len(outliers)} model-based outliers")
        return outliers
    
    def analyze_outliers(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict:
        """
        Complete outlier analysis pipeline.
        
        Args:
            start_date: Start date for analysis window
            end_date: End date for analysis window
        
        Returns:
            Dictionary with outlier analysis results
        """
        logger.info(f"Starting outlier analysis for {self.chamber} in Congress {self.congress}")
        
        # Load members
        self.load_members()
        
        # Detect party line deviations
        party_line_outliers = self.detect_party_line_deviations(start_date, end_date)
        
        # Build and use prediction model
        self.build_vote_prediction_model(start_date, end_date)
        model_outliers = self.detect_model_based_outliers(start_date, end_date)
        
        # Combine and deduplicate outliers
        all_outliers = party_line_outliers + model_outliers
        
        # Remove duplicates based on rollcall_id and member_id
        seen = set()
        unique_outliers = []
        for outlier in all_outliers:
            key = (outlier['rollcall_id'], outlier['member_id'])
            if key not in seen:
                seen.add(key)
                unique_outliers.append(outlier)
        
        return {
            'congress': self.congress,
            'chamber': self.chamber,
            'analysis_date': datetime.now().isoformat(),
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'total_outliers': len(unique_outliers),
            'party_line_outliers': len(party_line_outliers),
            'model_outliers': len(model_outliers),
            'outliers': unique_outliers
        }

@click.command()
@click.option('--congress', type=int, required=True, help='Congress number (e.g., 119)')
@click.option('--chamber', type=click.Choice(['house', 'senate']), required=True, help='Chamber to analyze')
@click.option('--start-date', type=str, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', type=str, help='End date (YYYY-MM-DD)')
@click.option('--output', type=str, help='Output file for results')
def main(congress: int, chamber: str, start_date: Optional[str], end_date: Optional[str], output: Optional[str]):
    """Detect voting outliers in congressional data."""
    logging.basicConfig(level=logging.INFO)
    
    # Parse dates
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
    
    # Run analysis
    detector = OutlierDetector(congress, chamber)
    results = detector.analyze_outliers(start_dt, end_dt)
    
    # Output results
    if output:
        import json
        with open(output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to {output}")
    else:
        print(json.dumps(results, indent=2, default=str))

if __name__ == '__main__':
    main()


