#!/usr/bin/env python3
"""
FEC Data Service for downloading and managing candidate data.
Handles daily downloads, database operations, and data synchronization.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.database import get_db_session
from src.etl.fec_csv_processor import FECCSVProcessor
from scripts.setup_fec_candidates_table import FECCandidate

logger = logging.getLogger(__name__)

class FECDataService:
    """Service for managing FEC candidate data downloads and storage."""
    
    def __init__(self, csv_file_path: Optional[str] = None):
        """
        Initialize the FEC data service.
        
        Args:
            csv_file_path: Path to the CSV file. If not provided, will use the latest CSV file in data/fec directory.
        """
        self.logger = logging.getLogger(__name__)
        
        if csv_file_path is None:
            # Find the latest CSV file in data/fec directory
            csv_file_path = self._find_latest_csv_file()
        
        self.csv_file_path = csv_file_path
    
    def _find_latest_csv_file(self) -> str:
        """
        Find the latest CSV file in the data/fec directory.
        
        Returns:
            Path to the latest CSV file
            
        Raises:
            FileNotFoundError: If no CSV files are found in the directory
        """
        fec_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'fec')
        
        if not os.path.exists(fec_dir):
            raise FileNotFoundError(f"FEC data directory not found: {fec_dir}")
        
        # Find all CSV files in the directory
        csv_files = []
        for filename in os.listdir(fec_dir):
            if filename.lower().endswith('.csv'):
                file_path = os.path.join(fec_dir, filename)
                # Get file modification time
                mtime = os.path.getmtime(file_path)
                csv_files.append((file_path, mtime))
        
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {fec_dir}")
        
        # Sort by modification time (newest first) and return the latest
        csv_files.sort(key=lambda x: x[1], reverse=True)
        latest_file = csv_files[0][0]
        
        self.logger.info(f"Using latest CSV file: {latest_file}")
        return latest_file
    
    def download_and_store_candidates(self, 
                                    office: str = 'H', 
                                    election_year: int = 2026,
                                    state: Optional[str] = None,
                                    force_update: bool = False) -> Dict:
        """
        Process FEC candidate CSV file and store in database.
        
        Args:
            office: Office type ('H' for House, 'S' for Senate, 'P' for President)
            election_year: Election year
            state: Optional state filter (applied after processing)
            force_update: If True, update existing records even if recently updated
            
        Returns:
            Dictionary with processing statistics
        """
        stats = {
            'total_downloaded': 0,
            'new_candidates': 0,
            'updated_candidates': 0,
            'errors': 0,
            'start_time': datetime.utcnow(),
            'end_time': None
        }
        
        try:
            self.logger.info(f"Starting FEC candidate CSV processing for {office} {election_year}")
            
            # Check if CSV file exists
            if not os.path.exists(self.csv_file_path):
                raise FileNotFoundError(f"FEC CSV file not found: {self.csv_file_path}")
            
            # Process CSV file
            processor = FECCSVProcessor(self.csv_file_path)
            csv_stats = processor.process_csv_file(force_update=force_update)
            
            # Update our stats with CSV processing results
            stats.update(csv_stats)
            stats['total_downloaded'] = csv_stats['total_processed']
            
            self.logger.info(f"Processed {csv_stats['total_processed']} candidates from FEC CSV")
            
            # CSV processor already handled database storage
            stats['end_time'] = datetime.utcnow()
            duration = (stats['end_time'] - stats['start_time']).total_seconds()
            
            self.logger.info(f"FEC CSV processing completed in {duration:.2f} seconds")
            self.logger.info(f"Stats: {stats['new_candidates']} new, {stats['updated_candidates']} updated, {stats['errors']} errors")
            
            return stats
            
        except Exception as e:
            self.logger.error(f"FEC download failed: {e}")
            stats['end_time'] = datetime.utcnow()
            stats['error'] = str(e)
            raise
    
    def _store_candidate(self, session, candidate_data: Dict, force_update: bool = False) -> str:
        """
        Store a single candidate in the database.
        
        Args:
            session: Database session
            candidate_data: Candidate data from FEC API
            force_update: If True, update even if recently updated
            
        Returns:
            'new', 'updated', or 'skipped'
        """
        candidate_id = candidate_data.get('candidate_id')
        if not candidate_id:
            raise ValueError("Candidate data missing candidate_id")
        
        # Check if candidate already exists
        existing = session.query(FECCandidate).filter(
            FECCandidate.candidate_id == candidate_id
        ).first()
        
        # Parse district (handle both string and numeric formats)
        district = candidate_data.get('district')
        if district and district != '00':
            try:
                district = str(int(district))  # Convert to string, remove leading zeros
            except (ValueError, TypeError):
                district = str(district) if district else None
        else:
            district = None
        
        # Helper function to safely get string values
        def safe_get_string(data, key, default=''):
            value = data.get(key, default)
            return str(value).strip() if value is not None else default
        
        # Prepare candidate data
        candidate_dict = {
            'candidate_id': candidate_id,
            'name': safe_get_string(candidate_data, 'name'),
            'party': safe_get_string(candidate_data, 'party'),
            'office': safe_get_string(candidate_data, 'office'),
            'state': safe_get_string(candidate_data, 'state'),
            'district': district,
            'election_year': candidate_data.get('election_years', [2026])[0] if candidate_data.get('election_years') else 2026,
            'election_season': safe_get_string(candidate_data, 'election_season'),
            'incumbent_challenge_status': safe_get_string(candidate_data, 'incumbent_challenge_status'),
            'total_receipts': float(candidate_data.get('total_receipts', 0) or 0),
            'total_disbursements': float(candidate_data.get('total_disbursements', 0) or 0),
            'cash_on_hand': float(candidate_data.get('cash_on_hand', 0) or 0),
            'debts_owed': float(candidate_data.get('debts_owed', 0) or 0),
            'principal_committee_id': safe_get_string(candidate_data, 'principal_committee_id'),
            'principal_committee_name': safe_get_string(candidate_data, 'principal_committee_name'),
            'active': safe_get_string(candidate_data, 'candidate_status').lower() != 'withdrawn',
            'candidate_status': safe_get_string(candidate_data, 'candidate_status'),
            'last_fec_update': datetime.utcnow(),
            'raw_fec_data': json.dumps(candidate_data, default=str)
        }
        
        if existing:
            # Check if we should update (skip if recently updated and not forcing)
            if not force_update and existing.last_fec_update:
                time_since_update = datetime.utcnow() - existing.last_fec_update
                if time_since_update < timedelta(hours=24):
                    return 'skipped'
            
            # Update existing record
            for key, value in candidate_dict.items():
                if key not in ['id', 'created_at']:  # Don't update these fields
                    setattr(existing, key, value)
            
            existing.updated_at = datetime.utcnow()
            return 'updated'
        else:
            # Create new record
            candidate_dict['created_at'] = datetime.utcnow()
            candidate_dict['updated_at'] = datetime.utcnow()
            
            new_candidate = FECCandidate(**candidate_dict)
            session.add(new_candidate)
            return 'new'
    
    def get_candidates_from_db(self, 
                             office: str = 'H',
                             election_year: int = 2026,
                             state: Optional[str] = None,
                             district: Optional[str] = None,
                             party: Optional[str] = None,
                             active_only: bool = True) -> List[Dict]:
        """
        Get candidates from the database.
        
        Args:
            office: Office type filter
            election_year: Election year filter
            state: State filter
            district: District filter
            party: Party filter
            active_only: Only return active candidates
            
        Returns:
            List of candidate dictionaries
        """
        with get_db_session() as session:
            query = session.query(FECCandidate).filter(
                FECCandidate.office == office,
                FECCandidate.election_year == election_year
            )
            
            if state:
                query = query.filter(FECCandidate.state == state)
            if district:
                query = query.filter(FECCandidate.district == district)
            if party:
                query = query.filter(FECCandidate.party == party)
            if active_only:
                query = query.filter(FECCandidate.active == True)
            
            candidates = query.order_by(FECCandidate.state, FECCandidate.district, FECCandidate.name).all()
            
            return [self._candidate_to_dict(candidate) for candidate in candidates]
    
    def _candidate_to_dict(self, candidate: FECCandidate) -> Dict:
        """Convert FECCandidate model to dictionary."""
        return {
            'id': candidate.id,
            'candidate_id': candidate.candidate_id,
            'name': candidate.name,
            'party': candidate.party,
            'office': candidate.office,
            'state': candidate.state,
            'district': candidate.district,
            'election_year': candidate.election_year,
            'election_season': candidate.election_season,
            'incumbent_challenge_status': candidate.incumbent_challenge_status,
            'total_receipts': candidate.total_receipts,
            'total_disbursements': candidate.total_disbursements,
            'cash_on_hand': candidate.cash_on_hand,
            'debts_owed': candidate.debts_owed,
            'principal_committee_id': candidate.principal_committee_id,
            'principal_committee_name': candidate.principal_committee_name,
            'active': candidate.active,
            'candidate_status': candidate.candidate_status,
            'created_at': candidate.created_at.isoformat() if candidate.created_at else None,
            'updated_at': candidate.updated_at.isoformat() if candidate.updated_at else None,
            'last_fec_update': candidate.last_fec_update.isoformat() if candidate.last_fec_update else None
        }
    
    def get_download_stats(self) -> Dict:
        """Get statistics about the FEC candidate database."""
        with get_db_session() as session:
            total_candidates = session.query(FECCandidate).count()
            active_candidates = session.query(FECCandidate).filter(FECCandidate.active == True).count()
            house_2026 = session.query(FECCandidate).filter(
                FECCandidate.office == 'H',
                FECCandidate.election_year == 2026
            ).count()
            
            # Get last update time
            last_update = session.query(FECCandidate.last_fec_update).order_by(
                FECCandidate.last_fec_update.desc()
            ).first()
            
            return {
                'total_candidates': total_candidates,
                'active_candidates': active_candidates,
                'house_2026_candidates': house_2026,
                'last_update': last_update[0].isoformat() if last_update and last_update[0] else None
            }
    
    def cleanup_old_data(self, days_old: int = 30) -> int:
        """
        Remove candidates that haven't been updated in the specified number of days.
        
        Args:
            days_old: Remove candidates older than this many days
            
        Returns:
            Number of candidates removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        with get_db_session() as session:
            old_candidates = session.query(FECCandidate).filter(
                FECCandidate.last_fec_update < cutoff_date
            ).all()
            
            count = len(old_candidates)
            for candidate in old_candidates:
                session.delete(candidate)
            
            session.commit()
            
            if count > 0:
                self.logger.info(f"Cleaned up {count} old candidate records")
            
            return count


def main():
    """Test the FEC data service."""
    import sys
    import os
    
    # Add project root to path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    # Test the service
    try:
        service = FECDataService()
        
        print("Testing FEC Data Service...")
        
        # Test download (limit to a few candidates for testing)
        print("Downloading sample House candidates for 2026...")
        stats = service.download_and_store_candidates(office='H', election_year=2026)
        
        print(f"✓ Download completed: {stats}")
        
        # Test database retrieval
        print("Retrieving candidates from database...")
        candidates = service.get_candidates_from_db(office='H', election_year=2026)
        print(f"✓ Retrieved {len(candidates)} candidates from database")
        
        if candidates:
            print("\nSample candidate from database:")
            sample = candidates[0]
            print(f"  Name: {sample.get('name', 'N/A')}")
            print(f"  Party: {sample.get('party', 'N/A')}")
            print(f"  State: {sample.get('state', 'N/A')}")
            print(f"  District: {sample.get('district', 'N/A')}")
            print(f"  Receipts: ${sample.get('total_receipts', 0):,.2f}")
        
        # Test stats
        print("\nDatabase statistics:")
        stats = service.get_download_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
            
    except Exception as e:
        print(f"Error testing FEC data service: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
