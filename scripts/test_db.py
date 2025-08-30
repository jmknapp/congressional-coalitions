#!/usr/bin/env python3
"""
Test script to verify database connection and create sample data.
"""

import os
import sys
import logging
from datetime import datetime, date
from sqlalchemy import text

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_db_session
from scripts.setup_db import Member, Bill, Rollcall, Vote, Cosponsor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connection():
    """Test database connection."""
    try:
        with get_db_session() as session:
            # Test basic query
            result = session.execute(text("SELECT COUNT(*) FROM members"))
            count = result.scalar()
            logger.info(f"Database connection successful. Members table has {count} records.")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

def create_sample_data():
    """Create some sample data for testing."""
    try:
        with get_db_session() as session:
            # Create sample members
            members = [
                Member(
                    member_id_bioguide="S001",
                    first="John",
                    last="Smith",
                    party="D",
                    state="CA",
                    district=1,
                    start_date=date(2023, 1, 3)
                ),
                Member(
                    member_id_bioguide="S002", 
                    first="Jane",
                    last="Doe",
                    party="R",
                    state="TX",
                    district=2,
                    start_date=date(2023, 1, 3)
                ),
                Member(
                    member_id_bioguide="S003",
                    first="Bob",
                    last="Johnson",
                    party="D",
                    state="NY",
                    district=3,
                    start_date=date(2023, 1, 3)
                )
            ]
            
            for member in members:
                session.add(member)
            
            # Commit members first to avoid foreign key issues
            session.commit()
            
            # Create sample bills
            bills = [
                Bill(
                    bill_id="hr-123-118",
                    congress=118,
                    chamber="house",
                    number=123,
                    type="hr",
                    title="Sample Bill 1",
                    introduced_date=date(2023, 1, 15),
                    sponsor_bioguide="S001"
                ),
                Bill(
                    bill_id="hr-456-118",
                    congress=118,
                    chamber="house", 
                    number=456,
                    type="hr",
                    title="Sample Bill 2",
                    introduced_date=date(2023, 2, 20),
                    sponsor_bioguide="S002"
                )
            ]
            
            for bill in bills:
                session.add(bill)
            
            # Create sample rollcalls
            rollcalls = [
                Rollcall(
                    rollcall_id="118-1-001",
                    congress=118,
                    chamber="house",
                    session=1,
                    rc_number=1,
                    date=date(2023, 1, 25),
                    question="On Passage of H.R. 123",
                    bill_id="hr-123-118"
                ),
                Rollcall(
                    rollcall_id="118-1-002",
                    congress=118,
                    chamber="house",
                    session=1,
                    rc_number=2,
                    date=date(2023, 2, 28),
                    question="On Passage of H.R. 456",
                    bill_id="hr-456-118"
                )
            ]
            
            for rollcall in rollcalls:
                session.add(rollcall)
            
            # Commit bills and rollcalls
            session.commit()
            
            # Create sample votes
            votes = [
                Vote(rollcall_id="118-1-001", member_id_bioguide="S001", vote_code="Yea"),
                Vote(rollcall_id="118-1-001", member_id_bioguide="S002", vote_code="Nay"),
                Vote(rollcall_id="118-1-001", member_id_bioguide="S003", vote_code="Yea"),
                Vote(rollcall_id="118-1-002", member_id_bioguide="S001", vote_code="Nay"),
                Vote(rollcall_id="118-1-002", member_id_bioguide="S002", vote_code="Yea"),
                Vote(rollcall_id="118-1-002", member_id_bioguide="S003", vote_code="Nay")
            ]
            
            for vote in votes:
                session.add(vote)
            
            # Create sample cosponsors
            cosponsors = [
                Cosponsor(bill_id="hr-123-118", member_id_bioguide="S003", date=date(2023, 1, 16)),
                Cosponsor(bill_id="hr-456-118", member_id_bioguide="S001", date=date(2023, 2, 21))
            ]
            
            for cosponsor in cosponsors:
                session.add(cosponsor)
            
            session.commit()
            logger.info("Sample data created successfully!")
            
            # Show counts
            member_count = session.query(Member).count()
            bill_count = session.query(Bill).count()
            rollcall_count = session.query(Rollcall).count()
            vote_count = session.query(Vote).count()
            cosponsor_count = session.query(Cosponsor).count()
            
            logger.info(f"Database now contains:")
            logger.info(f"  - {member_count} members")
            logger.info(f"  - {bill_count} bills") 
            logger.info(f"  - {rollcall_count} rollcalls")
            logger.info(f"  - {vote_count} votes")
            logger.info(f"  - {cosponsor_count} cosponsors")
            
    except Exception as e:
        logger.error(f"Failed to create sample data: {e}")
        raise

def main():
    """Main test function."""
    logger.info("Testing database connection...")
    if test_database_connection():
        logger.info("Creating sample data...")
        create_sample_data()
        logger.info("Test completed successfully!")
    else:
        logger.error("Database test failed!")

if __name__ == '__main__':
    main()
