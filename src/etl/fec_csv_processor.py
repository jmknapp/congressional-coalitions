#!/usr/bin/env python3
"""
FEC CSV Processor for manually provided CSV files.
Processes CSV files containing FEC candidate data and stores in database.
"""

import os
import sys
import logging
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
import csv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.database import get_db_session
from scripts.setup_fec_candidates_table import FECCandidate

logger = logging.getLogger(__name__)

class FECCSVProcessor:
    """Processor for manually provided FEC candidate CSV files."""
    
    def __init__(self, csv_file_path: str):
        """
        Initialize the FEC CSV processor.
        
        Args:
            csv_file_path: Path to the CSV file containing FEC candidate data
        """
        self.csv_file_path = csv_file_path
        self.logger = logging.getLogger(__name__)
    
    def process_csv_file(self, force_update: bool = False) -> Dict:
        """
        Process the CSV file and store candidates in database.
        
        Args:
            force_update: If True, update existing records even if recently updated
            
        Returns:
            Dictionary with processing statistics
        """
        stats = {
            'total_processed': 0,
            'new_candidates': 0,
            'updated_candidates': 0,
            'errors': 0,
            'start_time': datetime.utcnow(),
            'end_time': None
        }
        
        try:
            if not os.path.exists(self.csv_file_path):
                raise FileNotFoundError(f"CSV file not found: {self.csv_file_path}")
            
            self.logger.info(f"Processing FEC CSV file: {self.csv_file_path}")
            
            # Read CSV file
            df = pd.read_csv(self.csv_file_path)
            self.logger.info(f"Loaded CSV with {len(df)} rows and {len(df.columns)} columns")
            
            # Show available columns for debugging
            self.logger.info(f"Available columns: {list(df.columns)}")
            
            # Convert to list of dictionaries
            candidates = df.to_dict('records')
            
            # Clean and standardize the data
            cleaned_candidates = []
            for candidate in candidates:
                cleaned = self._clean_candidate_data(candidate)
                if cleaned:
                    cleaned_candidates.append(cleaned)
            
            stats['total_processed'] = len(cleaned_candidates)
            self.logger.info(f"Successfully processed {len(cleaned_candidates)} candidates")
            
            # Store candidates in database
            with get_db_session() as session:
                for candidate_data in cleaned_candidates:
                    try:
                        self._store_candidate(session, candidate_data, force_update)
                        stats['new_candidates'] += 1
                    except Exception as e:
                        self.logger.error(f"Error storing candidate {candidate_data.get('candidate_id', 'unknown')}: {e}")
                        stats['errors'] += 1
                
                session.commit()
            
            stats['end_time'] = datetime.utcnow()
            duration = (stats['end_time'] - stats['start_time']).total_seconds()
            self.logger.info(f"FEC CSV processing completed in {duration:.2f} seconds")
            self.logger.info(f"Stats: {stats['new_candidates']} new, {stats['updated_candidates']} updated, {stats['errors']} errors")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error processing FEC CSV file: {e}")
            stats['end_time'] = datetime.utcnow()
            raise
    
    def _clean_candidate_data(self, candidate: Dict) -> Optional[Dict]:
        """
        Clean and standardize candidate data from CSV.
        
        Args:
            candidate: Raw candidate data from CSV
            
        Returns:
            Cleaned candidate data or None if invalid
        """
        try:
            # Helper function to safely get string values
            def safe_get_string(data, key, default=''):
                value = data.get(key, default)
                if pd.isna(value) or value is None:
                    return default
                return str(value).strip()
            
            # Helper function to safely get float values
            def safe_get_float(data, key, default=0.0):
                value = data.get(key, default)
                if pd.isna(value) or value is None or value == '':
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            # Extract and clean basic information
            # Try multiple possible column names for flexibility
            candidate_id = (safe_get_string(candidate, 'candidate_id') or 
                          safe_get_string(candidate, 'CAND_ID') or
                          safe_get_string(candidate, 'Candidate ID'))
            if not candidate_id:
                return None
            
            name = (safe_get_string(candidate, 'candidate_name') or
                   safe_get_string(candidate, 'CAND_NAME') or
                   safe_get_string(candidate, 'Candidate Name') or
                   safe_get_string(candidate, 'name'))
            if not name:
                return None
            
            # Clean party information
            party = (safe_get_string(candidate, 'party') or
                    safe_get_string(candidate, 'CAND_PTY_AFFILIATION') or
                    safe_get_string(candidate, 'Party')).upper()
            if party in ['DEM', 'DEMOCRATIC']:
                party = 'DEM'
            elif party in ['REP', 'REPUBLICAN']:
                party = 'REP'
            elif party in ['IND', 'INDEPENDENT']:
                party = 'IND'
            elif party in ['GRN', 'GREEN']:
                party = 'GRN'
            elif party in ['LIB', 'LIBERTARIAN']:
                party = 'LIB'
            
            # Clean state and district
            state = (safe_get_string(candidate, 'state') or
                    safe_get_string(candidate, 'candidate_state') or
                    safe_get_string(candidate, 'CAND_ST') or
                    safe_get_string(candidate, 'State')).upper()
            
            district = (candidate.get('district') or 
                       candidate.get('candidate_district') or 
                       candidate.get('CAND_DISTRICT') or 
                       candidate.get('District'))
            if pd.isna(district) or district == '' or district == '00':
                district = None
            else:
                try:
                    district = str(int(float(district)))
                except (ValueError, TypeError):
                    district = str(district).strip() if district else None
            
            # Clean financial data
            total_receipts = (safe_get_float(candidate, 'total_receipts') or
                            safe_get_float(candidate, 'Total Receipts') or
                            safe_get_float(candidate, 'receipts'))
            
            total_disbursements = (safe_get_float(candidate, 'total_disbursements') or
                                 safe_get_float(candidate, 'Total Disbursements') or
                                 safe_get_float(candidate, 'disbursements'))
            
            cash_on_hand = (safe_get_float(candidate, 'cash_on_hand') or
                           safe_get_float(candidate, 'Cash on Hand') or
                           safe_get_float(candidate, 'cash_on_hand_end_period'))
            
            debts_owed = (safe_get_float(candidate, 'debts_owed_by_committee') or
                         safe_get_float(candidate, 'Debts Owed by Committee') or
                         safe_get_float(candidate, 'debts_owed'))
            
            # Clean status information
            incumbent_challenge_status = (safe_get_string(candidate, 'incumbent_challenge') or
                                        safe_get_string(candidate, 'incumbent_challenge_status') or
                                        safe_get_string(candidate, 'INCUMBENT_CHALLENGER_STATUS') or
                                        safe_get_string(candidate, 'Incumbent/Challenger Status'))
            if not incumbent_challenge_status:
                incumbent_challenge_status = None
            
            candidate_status = (safe_get_string(candidate, 'candidate_status') or
                              safe_get_string(candidate, 'CAND_STATUS') or
                              safe_get_string(candidate, 'Candidate Status') or
                              'Unknown')
            
            # Determine if candidate is active
            active = candidate_status.lower() not in ['withdrawn', 'suspended', 'terminated']
            
            # Clean committee information
            principal_committee_id = (safe_get_string(candidate, 'principal_committee_id') or
                                    safe_get_string(candidate, 'PRINCIPAL_COMMITTEE_ID') or
                                    safe_get_string(candidate, 'Principal Committee ID'))
            if not principal_committee_id:
                principal_committee_id = None
            
            principal_committee_name = (safe_get_string(candidate, 'principal_committee_name') or
                                      safe_get_string(candidate, 'PRINCIPAL_COMMITTEE_NAME') or
                                      safe_get_string(candidate, 'Principal Committee Name'))
            if not principal_committee_name:
                principal_committee_name = None
            
            # Get election year
            election_year = candidate.get('election_year') or candidate.get('CAND_ELECTION_YR') or candidate.get('Election Year') or 2026
            try:
                election_year = int(election_year)
            except (ValueError, TypeError):
                election_year = 2026
            
            # Build cleaned candidate data
            cleaned_candidate = {
                'candidate_id': candidate_id,
                'name': name,
                'party': party,
                'office': 'H',  # House candidates
                'state': state,
                'district': district,
                'election_year': election_year,
                'election_season': str(election_year),
                'incumbent_challenge_status': incumbent_challenge_status,
                'total_receipts': total_receipts,
                'total_disbursements': total_disbursements,
                'cash_on_hand': cash_on_hand,
                'debts_owed': debts_owed,
                'principal_committee_id': principal_committee_id,
                'principal_committee_name': principal_committee_name,
                'active': active,
                'candidate_status': candidate_status,
                'last_fec_update': datetime.utcnow(),
                'raw_fec_data': str(candidate)  # Store raw data for debugging
            }
            
            return cleaned_candidate
            
        except Exception as e:
            self.logger.error(f"Error cleaning candidate data: {e}")
            return None
    
    def _store_candidate(self, session, candidate_data: Dict, force_update: bool = False):
        """
        Store a single candidate in the database.
        
        Args:
            session: Database session
            candidate_data: Cleaned candidate data
            force_update: If True, update existing records even if recently updated
        """
        candidate_id = candidate_data['candidate_id']
        
        # Check if candidate already exists by candidate_id
        existing = session.query(FECCandidate).filter_by(candidate_id=candidate_id).first()
        
        if existing:
            # Update existing candidate
            if force_update or not existing.last_fec_update or \
               (datetime.utcnow() - existing.last_fec_update).days > 1:
                
                for key, value in candidate_data.items():
                    if hasattr(existing, key) and key != 'id':
                        setattr(existing, key, value)
                
                existing.updated_at = datetime.utcnow()
                self.logger.debug(f"Updated candidate {candidate_id}")
            else:
                self.logger.debug(f"Skipped update for candidate {candidate_id} (recently updated)")
        else:
            # Check for potential duplicates by name, state, district, and election year
            potential_duplicates = session.query(FECCandidate).filter(
                FECCandidate.name == candidate_data['name'],
                FECCandidate.state == candidate_data['state'],
                FECCandidate.district == candidate_data['district'],
                FECCandidate.election_year == candidate_data['election_year']
            ).all()
            
            if potential_duplicates:
                # Found potential duplicate - use the one with more recent data or better status
                best_record = self._select_best_duplicate(potential_duplicates, candidate_data)
                
                if best_record:
                    # Update the best existing record
                    for key, value in candidate_data.items():
                        if hasattr(best_record, key) and key != 'id':
                            setattr(best_record, key, value)
                    
                    best_record.updated_at = datetime.utcnow()
                    self.logger.info(f"Updated duplicate candidate {candidate_id} (merged with existing {best_record.candidate_id})")
                else:
                    # Create new candidate
                    new_candidate = FECCandidate(**candidate_data)
                    session.add(new_candidate)
                    self.logger.debug(f"Added new candidate {candidate_id}")
            else:
                # No duplicates found, create new candidate
                new_candidate = FECCandidate(**candidate_data)
                session.add(new_candidate)
                self.logger.debug(f"Added new candidate {candidate_id}")
    
    def _select_best_duplicate(self, existing_records: List, new_data: Dict):
        """
        Select the best record from potential duplicates.
        
        Args:
            existing_records: List of existing FECCandidate records
            new_data: New candidate data
            
        Returns:
            Best existing record to update, or None if new record should be created
        """
        if not existing_records:
            return None
        
        # If only one existing record, use it
        if len(existing_records) == 1:
            return existing_records[0]
        
        # Prefer records with incumbent status over challenger status
        incumbent_records = [r for r in existing_records if r.incumbent_challenge_status == 'I']
        if incumbent_records:
            # If new data is also incumbent, prefer the one with more financial data
            if new_data.get('incumbent_challenge_status') == 'I':
                return max(incumbent_records, key=lambda r: r.total_receipts or 0)
            else:
                # New data is challenger, but existing has incumbent - keep existing
                return incumbent_records[0]
        
        # No incumbent records, prefer the one with more financial data
        return max(existing_records, key=lambda r: r.total_receipts or 0)


def main():
    """Test the FEC CSV processor."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process FEC candidate CSV file')
    parser.add_argument('csv_file', help='Path to the CSV file')
    parser.add_argument('--force-update', action='store_true', help='Force update existing records')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        processor = FECCSVProcessor(args.csv_file)
        stats = processor.process_csv_file(force_update=args.force_update)
        
        print(f"✓ CSV processing completed successfully!")
        print(f"  Total processed: {stats['total_processed']}")
        print(f"  New candidates: {stats['new_candidates']}")
        print(f"  Updated candidates: {stats['updated_candidates']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Duration: {(stats['end_time'] - stats['start_time']).total_seconds():.2f} seconds")
        
    except Exception as e:
        print(f"✗ Error processing CSV file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
