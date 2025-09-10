#!/usr/bin/env python3
"""
Setup script for the challengers2026 table.
Creates the table for tracking 2026 Democratic challengers.
"""

import os
import sys
from sqlalchemy import create_engine, text, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class Challenger2026(Base):
    __tablename__ = 'challengers2026'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    challenger_name = Column(String(200), nullable=False)
    fecname = Column(String(200), nullable=True)  # Exact FEC name format for matching
    challenger_party = Column(String(10), nullable=False, default='D')
    challenger_state = Column(String(2), nullable=False)
    challenger_district = Column(Integer, nullable=False)
    campaign_homepage_url = Column(Text)
    actblue_donation_link = Column(Text)
    mugshot_image_filename = Column(String(255))
    biography = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def setup_challengers_table():
    """Create the challengers2026 table."""
    # Database connection
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set. Example: mysql://user:password@localhost/database")
    engine = create_engine(database_url)
    
    try:
        # Create the table
        Base.metadata.create_all(engine)
        logger.info("✓ Created challengers2026 table successfully")
        
        # Test the connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM challengers2026"))
            count = result.scalar()
            logger.info(f"✓ Table challengers2026 is ready with {count} records")
            
    except Exception as e:
        logger.error(f"Error creating challengers2026 table: {e}")
        raise

if __name__ == "__main__":
    setup_challengers_table()
