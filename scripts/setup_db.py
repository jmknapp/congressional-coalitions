#!/usr/bin/env python3
"""
Database setup script for Congressional Coalition Tracker
Creates all necessary tables and indexes for the analysis pipeline.
"""

import os
import sys
import click
from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Date, DateTime, Boolean, Enum, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class Member(Base):
    __tablename__ = 'members'
    
    member_id_bioguide = Column(String(20), primary_key=True)
    icpsr = Column(Integer)
    lis_id = Column(String(20))
    first = Column(String(100))
    last = Column(String(100))
    party = Column(String(10))
    state = Column(String(2))
    district = Column(Integer)  # NULL for senators
    start_date = Column(Date)
    end_date = Column(Date)
    # Contact information
    email = Column(String(200))
    phone = Column(String(20))
    website = Column(String(500))
    dc_office = Column(String(500))
    actblue_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Bill(Base):
    __tablename__ = 'bills'
    
    bill_id = Column(String(50), primary_key=True)
    congress = Column(Integer, nullable=False)
    chamber = Column(String(10), nullable=False)  # 'house', 'senate', 'both'
    number = Column(Integer, nullable=False)
    type = Column(String(10), nullable=False)  # 'hr', 's', 'hjres', 'sjres', etc.
    title = Column(String(1000))
    introduced_date = Column(Date)
    sponsor_bioguide = Column(String(20), ForeignKey('members.member_id_bioguide'))
    policy_area = Column(String(200))
    summary_short = Column(String(2000))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BillSubject(Base):
    __tablename__ = 'bill_subjects'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(String(50), ForeignKey('bills.bill_id'), nullable=False)
    subject_term = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Cosponsor(Base):
    __tablename__ = 'cosponsors'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(String(50), ForeignKey('bills.bill_id'), nullable=False)
    member_id_bioguide = Column(String(20), ForeignKey('members.member_id_bioguide'), nullable=False)
    date = Column(Date, nullable=False)
    is_original = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Action(Base):
    __tablename__ = 'actions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_id = Column(String(50), ForeignKey('bills.bill_id'), nullable=False)
    action_date = Column(Date, nullable=False)
    action_code = Column(String(50), nullable=False)
    text = Column(String(1000))
    committee_code = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

class Amendment(Base):
    __tablename__ = 'amendments'
    
    amendment_id = Column(String(50), primary_key=True)
    bill_id = Column(String(50), ForeignKey('bills.bill_id'), nullable=False)
    sponsor_bioguide = Column(String(20), ForeignKey('members.member_id_bioguide'))
    type = Column(String(20))  # 'amendment', 'substitute', etc.
    purpose = Column(String(500))
    introduced_date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)

class Rollcall(Base):
    __tablename__ = 'rollcalls'
    
    rollcall_id = Column(String(50), primary_key=True)
    congress = Column(Integer, nullable=False)
    chamber = Column(String(10), nullable=False)  # 'house', 'senate'
    session = Column(Integer, nullable=False)
    rc_number = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    question = Column(String(500))
    bill_id = Column(String(50), ForeignKey('bills.bill_id'))
    created_at = Column(DateTime, default=datetime.utcnow)

class Vote(Base):
    __tablename__ = 'votes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rollcall_id = Column(String(50), ForeignKey('rollcalls.rollcall_id'), nullable=False)
    member_id_bioguide = Column(String(20), ForeignKey('members.member_id_bioguide'), nullable=False)
    vote_code = Column(Enum('Yea', 'Nay', 'Present', 'Not Voting', name='vote_code_enum'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create indexes for performance
def create_indexes(engine):
    """Create performance indexes on key columns"""
    with engine.connect() as conn:
        # Bills indexes
        try:
            conn.execute(text("CREATE INDEX idx_bills_congress_chamber ON bills(congress, chamber)"))
        except:
            pass
        try:
            conn.execute(text("CREATE INDEX idx_bills_sponsor ON bills(sponsor_bioguide)"))
        except:
            pass
        try:
            conn.execute(text("CREATE INDEX idx_bills_introduced ON bills(introduced_date)"))
        except:
            pass
        
        # Cosponsors indexes
        try:
            conn.execute(text("CREATE INDEX idx_cosponsors_bill ON cosponsors(bill_id)"))
        except:
            pass
        try:
            conn.execute(text("CREATE INDEX idx_cosponsors_member ON cosponsors(member_id_bioguide)"))
        except:
            pass
        
        # Votes indexes
        try:
            conn.execute(text("CREATE INDEX idx_votes_rollcall ON votes(rollcall_id)"))
        except:
            pass
        try:
            conn.execute(text("CREATE INDEX idx_votes_member ON votes(member_id_bioguide)"))
        except:
            pass
        
        # Rollcalls indexes
        try:
            conn.execute(text("CREATE INDEX idx_rollcalls_congress_chamber ON rollcalls(congress, chamber)"))
        except:
            pass
        try:
            conn.execute(text("CREATE INDEX idx_rollcalls_date ON rollcalls(date)"))
        except:
            pass
        try:
            conn.execute(text("CREATE INDEX idx_rollcalls_bill ON rollcalls(bill_id)"))
        except:
            pass
        
        # Members indexes
        try:
            conn.execute(text("CREATE INDEX idx_members_party_state ON members(party, state)"))
        except:
            pass
        
        conn.commit()

@click.command()
@click.option('--database-url', envvar='DATABASE_URL', 
              default='mysql://localhost/congressional_coalitions',
              help='Database connection URL')
@click.option('--drop-existing', is_flag=True, 
              help='Drop existing tables before creating new ones')
def setup_database(database_url, drop_existing):
    """Set up the database schema for congressional coalition tracking"""
    
    logger.info(f"Connecting to database: {database_url}")
    engine = create_engine(database_url, echo=False)
    
    if drop_existing:
        logger.info("Dropping existing tables...")
        Base.metadata.drop_all(engine)
    
    logger.info("Creating tables...")
    Base.metadata.create_all(engine)
    
    logger.info("Creating indexes...")
    create_indexes(engine)
    
    logger.info("Database setup complete!")
    
    # Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM members"))
            count = result.scalar()
            logger.info(f"Database is ready. Members table has {count} records.")
    except Exception as e:
        logger.error(f"Database test failed: {e}")

if __name__ == '__main__':
    setup_database()


