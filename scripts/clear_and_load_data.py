#!/usr/bin/env python3
"""
Script to clear existing data and load complete 119th Congress dataset.
"""

import os
import sys
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote, Cosponsor, BillSubject, Amendment
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_all_data():
    """Clear all existing data from the database."""
    logger.info("Clearing all existing data...")
    
    try:
        with get_db_session() as session:
            # Delete in reverse order of dependencies
            session.execute(text("DELETE FROM votes"))
            session.execute(text("DELETE FROM cosponsors"))
            session.execute(text("DELETE FROM bill_subjects"))
            session.execute(text("DELETE FROM amendments"))
            session.execute(text("DELETE FROM rollcalls"))
            session.execute(text("DELETE FROM bills"))
            session.execute(text("DELETE FROM members"))
            
            session.commit()
            logger.info("All existing data cleared successfully")
            
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        session.rollback()
        raise

def load_complete_data():
    """Load complete 119th Congress data."""
    logger.info("Loading complete 119th Congress data...")
    
    # Import the comprehensive data loading functions
    from scripts.load_complete_119th_congress import CompleteCongressLoader
    
    loader = CompleteCongressLoader()
    
    try:
        # Load all data
        loader.load_complete_data()
        
        logger.info("Complete 119th Congress data loaded successfully")
        
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise

def main():
    """Main function to clear and reload data."""
    logger.info("Starting complete data reload for 119th Congress...")
    
    try:
        # Clear existing data
        clear_all_data()
        
        # Load complete data
        load_complete_data()
        
        logger.info("Data reload completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to reload data: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
