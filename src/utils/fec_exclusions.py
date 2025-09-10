#!/usr/bin/env python3
"""
Utility functions for managing FEC candidate exclusions.
Handles loading and checking the exclusion list for dropped out candidates.
"""

import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class FECExclusionManager:
    """Manages the FEC candidate exclusion list."""
    
    def __init__(self, exclusions_file_path: Optional[str] = None):
        """
        Initialize the exclusion manager.
        
        Args:
            exclusions_file_path: Path to the exclusions JSON file. If not provided, uses default path.
        """
        if exclusions_file_path is None:
            # Default path relative to project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            exclusions_file_path = os.path.join(project_root, 'data', 'fec_exclusions.json')
        
        self.exclusions_file_path = exclusions_file_path
        self._exclusions_cache = None
        self._cache_timestamp = None
    
    def load_exclusions(self) -> Dict:
        """
        Load the exclusions list from the JSON file.
        
        Returns:
            Dictionary containing the exclusions data
        """
        try:
            if not os.path.exists(self.exclusions_file_path):
                logger.warning(f"Exclusions file not found: {self.exclusions_file_path}")
                return {"excluded_candidates": [], "last_updated": None, "description": ""}
            
            with open(self.exclusions_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Ensure required structure
            if 'excluded_candidates' not in data:
                data['excluded_candidates'] = []
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading exclusions file: {e}")
            return {"excluded_candidates": [], "last_updated": None, "description": ""}
    
    def is_candidate_excluded(self, state: str, district: str, fec_name: str) -> bool:
        """
        Check if a candidate is in the exclusion list.
        
        Args:
            state: Candidate's state (e.g., "CA")
            district: Candidate's district (e.g., "12")
            fec_name: Candidate's FEC name (e.g., "SMITH, JOHN MR.")
            
        Returns:
            True if candidate is excluded, False otherwise
        """
        exclusions = self.load_exclusions()
        
        for excluded in exclusions.get('excluded_candidates', []):
            # Check for exact match on all three fields
            if (excluded.get('state', '').upper() == state.upper() and
                str(excluded.get('district', '')) == str(district) and
                excluded.get('fec_name', '').upper() == fec_name.upper()):
                return True
        
        return False
    
    def add_exclusion(self, state: str, district: str, fec_name: str, reason: str = "Manually excluded") -> bool:
        """
        Add a candidate to the exclusion list.
        
        Args:
            state: Candidate's state
            district: Candidate's district
            fec_name: Candidate's FEC name
            reason: Reason for exclusion
            
        Returns:
            True if successfully added, False otherwise
        """
        try:
            exclusions = self.load_exclusions()
            
            # Check if already excluded
            if self.is_candidate_excluded(state, district, fec_name):
                logger.info(f"Candidate {fec_name} ({state}-{district}) is already excluded")
                return True
            
            # Add new exclusion
            new_exclusion = {
                "state": state.upper(),
                "district": str(district),
                "fec_name": fec_name.upper(),
                "reason": reason,
                "excluded_date": datetime.now().strftime("%Y-%m-%d")
            }
            
            exclusions['excluded_candidates'].append(new_exclusion)
            exclusions['last_updated'] = datetime.now().isoformat() + 'Z'
            
            # Save back to file
            self._save_exclusions(exclusions)
            
            logger.info(f"Added exclusion for {fec_name} ({state}-{district})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding exclusion: {e}")
            return False
    
    def remove_exclusion(self, state: str, district: str, fec_name: str) -> bool:
        """
        Remove a candidate from the exclusion list.
        
        Args:
            state: Candidate's state
            district: Candidate's district
            fec_name: Candidate's FEC name
            
        Returns:
            True if successfully removed, False otherwise
        """
        try:
            exclusions = self.load_exclusions()
            
            # Find and remove the exclusion
            original_count = len(exclusions.get('excluded_candidates', []))
            exclusions['excluded_candidates'] = [
                exc for exc in exclusions.get('excluded_candidates', [])
                if not (exc.get('state', '').upper() == state.upper() and
                       str(exc.get('district', '')) == str(district) and
                       exc.get('fec_name', '').upper() == fec_name.upper())
            ]
            
            if len(exclusions['excluded_candidates']) < original_count:
                exclusions['last_updated'] = datetime.now().isoformat() + 'Z'
                self._save_exclusions(exclusions)
                logger.info(f"Removed exclusion for {fec_name} ({state}-{district})")
                return True
            else:
                logger.info(f"No exclusion found for {fec_name} ({state}-{district})")
                return False
                
        except Exception as e:
            logger.error(f"Error removing exclusion: {e}")
            return False
    
    def _save_exclusions(self, exclusions: Dict) -> None:
        """Save exclusions to the JSON file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.exclusions_file_path), exist_ok=True)
        
        with open(self.exclusions_file_path, 'w', encoding='utf-8') as f:
            json.dump(exclusions, f, indent=2, ensure_ascii=False)
    
    def get_exclusions_list(self) -> List[Dict]:
        """
        Get the list of excluded candidates.
        
        Returns:
            List of exclusion dictionaries
        """
        exclusions = self.load_exclusions()
        return exclusions.get('excluded_candidates', [])


def is_candidate_excluded(state: str, district: str, fec_name: str) -> bool:
    """
    Convenience function to check if a candidate is excluded.
    
    Args:
        state: Candidate's state
        district: Candidate's district  
        fec_name: Candidate's FEC name
        
    Returns:
        True if candidate is excluded, False otherwise
    """
    manager = FECExclusionManager()
    return manager.is_candidate_excluded(state, district, fec_name)


def main():
    """Test the exclusion manager."""
    manager = FECExclusionManager()
    
    print("Testing FEC Exclusion Manager...")
    
    # Test loading exclusions
    exclusions = manager.load_exclusions()
    print(f"Loaded {len(exclusions.get('excluded_candidates', []))} exclusions")
    
    # Test adding an exclusion
    test_state = "CA"
    test_district = "12"
    test_name = "TEST, CANDIDATE MR."
    
    print(f"\nAdding test exclusion for {test_name} ({test_state}-{test_district})")
    success = manager.add_exclusion(test_state, test_district, test_name, "Test exclusion")
    print(f"Add result: {success}")
    
    # Test checking exclusion
    is_excluded = manager.is_candidate_excluded(test_state, test_district, test_name)
    print(f"Is excluded: {is_excluded}")
    
    # Test removing exclusion
    print(f"\nRemoving test exclusion for {test_name} ({test_state}-{test_district})")
    success = manager.remove_exclusion(test_state, test_district, test_name)
    print(f"Remove result: {success}")
    
    # Test checking again
    is_excluded = manager.is_candidate_excluded(test_state, test_district, test_name)
    print(f"Is excluded after removal: {is_excluded}")


if __name__ == "__main__":
    main()
