#!/usr/bin/env python3
"""
Main analysis script for congressional coalition tracking.

This script runs the complete analysis pipeline including:
- Coalition detection using vote agreement, cosponsorship, and amendment networks
- Outlier detection for unexpected votes
- Bipartisan hotspot identification
- Subject analysis for coalitions
"""

import os
import sys
import logging
import click
import json
from datetime import datetime, date, timedelta
from typing import Optional

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.analysis.coalition_detector import CoalitionDetector
from src.analysis.outlier_detector import OutlierDetector
from src.utils.database import get_db_session
from scripts.setup_db import Bill, Cosponsor, BillSubject

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_bipartisan_hotspots(congress: int, chamber: str, start_date: Optional[date] = None, end_date: Optional[date] = None) -> dict:
    """
    Identify bills with high bipartisan cosponsorship.
    
    Args:
        congress: Congress number
        chamber: Chamber to analyze
        start_date: Start date for analysis window
        end_date: End date for analysis window
    
    Returns:
        Dictionary with bipartisan hotspot analysis
    """
    logger.info(f"Analyzing bipartisan hotspots for {chamber} in Congress {congress}")
    
    with get_db_session() as session:
        # Get bills in date range
        query = session.query(Bill).filter(
            Bill.congress == congress,
            Bill.chamber == chamber
        )
        
        if start_date:
            query = query.filter(Bill.introduced_date >= start_date)
        if end_date:
            query = query.filter(Bill.introduced_date <= end_date)
        
        bills = query.all()
        
        bipartisan_bills = []
        
        for bill in bills:
            # Get cosponsors for this bill
            cosponsors = session.query(Cosponsor).filter(Cosponsor.bill_id == bill.bill_id).all()
            
            if len(cosponsors) < 5:  # Skip bills with few cosponsors
                continue
            
            # Get party composition
            from scripts.setup_db import Member
            cosponsor_parties = set()
            for cosponsor in cosponsors:
                member = session.query(Member).filter(Member.member_id_bioguide == cosponsor.member_id_bioguide).first()
                if member:
                    cosponsor_parties.add(member.party)
            
            # Calculate bipartisan score
            if len(cosponsor_parties) >= 2:
                bipartisan_score = len(cosponsor_parties) / 3.0  # Normalize by max parties (D, R, I)
                
                # Get subjects
                subjects = session.query(BillSubject.subject_term).filter(BillSubject.bill_id == bill.bill_id).all()
                subject_terms = [subject[0] for subject in subjects]
                
                bipartisan_bills.append({
                    'bill_id': bill.bill_id,
                    'title': bill.title,
                    'sponsor_bioguide': bill.sponsor_bioguide,
                    'cosponsor_count': len(cosponsors),
                    'party_count': len(cosponsor_parties),
                    'bipartisan_score': bipartisan_score,
                    'subjects': subject_terms,
                    'introduced_date': bill.introduced_date.isoformat() if bill.introduced_date else None
                })
        
        # Sort by bipartisan score
        bipartisan_bills.sort(key=lambda x: x['bipartisan_score'], reverse=True)
        
        return {
            'congress': congress,
            'chamber': chamber,
            'analysis_date': datetime.now().isoformat(),
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'total_bills_analyzed': len(bills),
            'bipartisan_bills': bipartisan_bills[:20],  # Top 20
            'top_subjects': get_top_bipartisan_subjects(bipartisan_bills)
        }

def get_top_bipartisan_subjects(bipartisan_bills: list) -> list:
    """Get top subjects for bipartisan bills."""
    subject_counts = {}
    for bill in bipartisan_bills:
        for subject in bill['subjects']:
            if subject not in subject_counts:
                subject_counts[subject] = 0
            subject_counts[subject] += 1
    
    # Sort by count
    sorted_subjects = sorted(subject_counts.items(), key=lambda x: x[1], reverse=True)
    return sorted_subjects[:10]

def run_complete_analysis(congress: int, chamber: str, window_days: int = 90, output_dir: Optional[str] = None) -> dict:
    """
    Run complete analysis pipeline.
    
    Args:
        congress: Congress number
        chamber: Chamber to analyze
        window_days: Number of days for analysis window
        output_dir: Directory to save results
    
    Returns:
        Dictionary with complete analysis results
    """
    logger.info(f"Starting complete analysis for {chamber} in Congress {congress}")
    
    # Calculate date window
    end_date = date.today()
    start_date = end_date - timedelta(days=window_days)
    
    # Run coalition analysis
    logger.info("Running coalition analysis...")
    coalition_detector = CoalitionDetector(congress, chamber)
    coalition_results = coalition_detector.analyze_coalitions(start_date, end_date)
    
    # Run outlier analysis
    logger.info("Running outlier analysis...")
    outlier_detector = OutlierDetector(congress, chamber)
    outlier_results = outlier_detector.analyze_outliers(start_date, end_date)
    
    # Run bipartisan hotspot analysis
    logger.info("Running bipartisan hotspot analysis...")
    bipartisan_results = analyze_bipartisan_hotspots(congress, chamber, start_date, end_date)
    
    # Combine results
    complete_results = {
        'analysis_metadata': {
            'congress': congress,
            'chamber': chamber,
            'analysis_date': datetime.now().isoformat(),
            'window_days': window_days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'coalition_analysis': coalition_results,
        'outlier_analysis': outlier_results,
        'bipartisan_analysis': bipartisan_results,
        'summary': {
            'total_coalitions': len(coalition_results.get('coalitions', {})),
            'total_outliers': outlier_results.get('total_outliers', 0),
            'bipartisan_bills': len(bipartisan_results.get('bipartisan_bills', [])),
            'total_members': coalition_results.get('total_members', 0)
        }
    }
    
    # Save results if output directory specified
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
        # Save complete results
        complete_file = os.path.join(output_dir, f"complete_analysis_{chamber}_{congress}_{window_days}d.json")
        with open(complete_file, 'w') as f:
            json.dump(complete_results, f, indent=2, default=str)
        logger.info(f"Complete analysis saved to {complete_file}")
        
        # Save individual components
        coalition_file = os.path.join(output_dir, f"coalitions_{chamber}_{congress}_{window_days}d.json")
        with open(coalition_file, 'w') as f:
            json.dump(coalition_results, f, indent=2, default=str)
        
        outlier_file = os.path.join(output_dir, f"outliers_{chamber}_{congress}_{window_days}d.json")
        with open(outlier_file, 'w') as f:
            json.dump(outlier_results, f, indent=2, default=str)
        
        bipartisan_file = os.path.join(output_dir, f"bipartisan_{chamber}_{congress}_{window_days}d.json")
        with open(bipartisan_file, 'w') as f:
            json.dump(bipartisan_results, f, indent=2, default=str)
    
    return complete_results

def print_summary_results(results: dict):
    """Print a summary of analysis results."""
    print("\n" + "="*80)
    print("CONGRESSIONAL COALITION ANALYSIS SUMMARY")
    print("="*80)
    
    meta = results['analysis_metadata']
    print(f"Congress: {meta['congress']}")
    print(f"Chamber: {meta['chamber'].title()}")
    print(f"Analysis Window: {meta['start_date']} to {meta['end_date']} ({meta['window_days']} days)")
    print(f"Analysis Date: {meta['analysis_date']}")
    
    summary = results['summary']
    print(f"\nKey Findings:")
    print(f"  • Total Members Analyzed: {summary['total_members']}")
    print(f"  • Coalitions Detected: {summary['total_coalitions']}")
    print(f"  • Outlier Votes Found: {summary['total_outliers']}")
    print(f"  • Bipartisan Bills: {summary['bipartisan_bills']}")
    
    # Coalition details
    coalitions = results['coalition_analysis'].get('coalitions', {})
    if coalitions:
        print(f"\nCoalition Details:")
        for coalition_id, coalition in coalitions.items():
            print(f"  • Coalition {coalition_id}: {coalition['size']} members, "
                  f"{'Bipartisan' if coalition['bipartisan'] else 'Partisan'}")
            if coalition.get('top_subjects'):
                subjects = [s[0] for s in coalition['top_subjects'][:3]]
                print(f"    Top subjects: {', '.join(subjects)}")
    
    # Top bipartisan bills
    bipartisan_bills = results['bipartisan_analysis'].get('bipartisan_bills', [])
    if bipartisan_bills:
        print(f"\nTop Bipartisan Bills:")
        for i, bill in enumerate(bipartisan_bills[:5]):
            print(f"  {i+1}. {bill['title'][:60]}... (Score: {bill['bipartisan_score']:.2f})")
    
    print("="*80)

@click.command()
@click.option('--congress', type=int, required=True, help='Congress number (e.g., 119)')
@click.option('--chamber', type=click.Choice(['house', 'senate']), required=True, help='Chamber to analyze')
@click.option('--window', type=int, default=90, help='Analysis window in days (default: 90)')
@click.option('--output-dir', type=str, help='Directory to save results')
@click.option('--print-summary', is_flag=True, help='Print summary to console')
def main(congress: int, chamber: str, window: int, output_dir: Optional[str], print_summary: bool):
    """Run complete congressional coalition analysis."""
    
    # Run analysis
    results = run_complete_analysis(congress, chamber, window, output_dir)
    
    # Print summary if requested
    if print_summary:
        print_summary_results(results)
    
    logger.info("Analysis complete!")

if __name__ == '__main__':
    main()


