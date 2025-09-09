#!/usr/bin/env python3
"""
Setup script for the fec_candidates table.
Creates the table for storing FEC candidate data from the API.
"""

import os
import sys
from sqlalchemy import create_engine, text, Column, Integer, String, DateTime, Text, Float, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class FECCandidate(Base):
    __tablename__ = 'fec_candidates'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # FEC candidate ID (unique identifier from FEC)
    candidate_id = Column(String(20), nullable=False, unique=True, index=True)
    
    # Basic candidate information
    name = Column(String(255), nullable=False)
    party = Column(String(50))
    office = Column(String(10), nullable=False)  # H for House, S for Senate, P for President
    state = Column(String(2))
    district = Column(String(10))  # District number for House candidates
    
    # Election information
    election_year = Column(Integer, nullable=False)
    election_season = Column(String(20))  # primary, general, special, etc.
    incumbent_challenge_status = Column(String(50))  # I, C, O, etc.
    
    # Financial information (from latest filing)
    total_receipts = Column(Float, default=0.0)
    total_disbursements = Column(Float, default=0.0)
    cash_on_hand = Column(Float, default=0.0)
    debts_owed = Column(Float, default=0.0)
    
    # Committee information
    principal_committee_id = Column(String(20))
    principal_committee_name = Column(String(255))
    
    # Status and flags
    active = Column(Boolean, default=True)
    candidate_status = Column(String(50))  # active, withdrawn, etc.
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_fec_update = Column(DateTime)  # When FEC last updated this record
    
    # Raw JSON data from FEC API (for debugging/audit)
    raw_fec_data = Column(Text)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_fec_candidates_office_year', 'office', 'election_year'),
        Index('idx_fec_candidates_state_district', 'state', 'district'),
        Index('idx_fec_candidates_party', 'party'),
        Index('idx_fec_candidates_active', 'active'),
    )

def setup_fec_candidates_table():
    """Create the fec_candidates table."""
    # Database connection
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set. Example: mysql://user:password@localhost/database")
    engine = create_engine(database_url)
    
    try:
        # Create the table
        Base.metadata.create_all(engine)
        logger.info("✓ Created fec_candidates table successfully")
        
        # Test the connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM fec_candidates"))
            count = result.scalar()
            logger.info(f"✓ Table fec_candidates is ready with {count} records")
            
    except Exception as e:
        logger.error(f"Error creating fec_candidates table: {e}")
        raise

if __name__ == "__main__":
    setup_fec_candidates_table()
