#!/usr/bin/env python3
"""
Script to clean up duplicate FEC candidate records.
Removes duplicate records, keeping the best one for each candidate.
"""

import os
import sys
import logging
from sqlalchemy import func
from collections import defaultdict

# Add project root to path
sys.path.append(os.path.dirname(__file__))

from src.utils.database import get_db_session
from scripts.setup_fec_candidates_table import FECCandidate

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_duplicates():
    """Clean up duplicate candidate records."""
    
    with get_db_session() as session:
        # Find all candidates with duplicate names in same state/district
        duplicates = session.query(
            FECCandidate.name,
            FECCandidate.state,
            FECCandidate.district,
            func.count(FECCandidate.id).label('count')
        ).filter(
            FECCandidate.election_year == 2026
        ).group_by(
            FECCandidate.name,
            FECCandidate.state,
            FECCandidate.district
        ).having(
            func.count(FECCandidate.id) > 1
        ).all()
        
        logger.info(f"Found {len(duplicates)} candidates with duplicate records")
        
        total_removed = 0
        
        for dup in duplicates:
            name, state, district = dup.name, dup.state, dup.district
            logger.info(f"Processing duplicates for {name} ({state}-{district})")
            
            # Get all records for this candidate
            records = session.query(FECCandidate).filter(
                FECCandidate.name == name,
                FECCandidate.state == state,
                FECCandidate.district == district,
                FECCandidate.election_year == 2026
            ).all()
            
            # Select the best record to keep
            best_record = select_best_record(records)
            
            # Remove the others
            for record in records:
                if record.id != best_record.id:
                    logger.info(f"  Removing duplicate: {record.candidate_id} (status: {record.incumbent_challenge_status})")
                    session.delete(record)
                    total_removed += 1
            
            logger.info(f"  Kept: {best_record.candidate_id} (status: {best_record.incumbent_challenge_status})")
        
        # Commit the changes
        session.commit()
        logger.info(f"Cleanup completed. Removed {total_removed} duplicate records.")

def select_best_record(records):
    """
    Select the best record from a list of duplicate records.
    
    Args:
        records: List of FECCandidate records
        
    Returns:
        The best record to keep
    """
    if len(records) == 1:
        return records[0]
    
    # Prefer incumbent status over challenger status
    incumbent_records = [r for r in records if r.incumbent_challenge_status == 'I']
    if incumbent_records:
        # If multiple incumbents, prefer the one with more financial data
        return max(incumbent_records, key=lambda r: r.total_receipts or 0)
    
    # No incumbents, prefer the one with more financial data
    return max(records, key=lambda r: r.total_receipts or 0)

def main():
    """Main function."""
    try:
        cleanup_duplicates()
        print("✓ Duplicate cleanup completed successfully!")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
