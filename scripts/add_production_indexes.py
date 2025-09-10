#!/usr/bin/env python3
"""
Add production database indexes for performance optimization.
Run this script after initial database setup.
"""

import os
import sys
from sqlalchemy import create_engine, text
from src.utils.database import get_db_session

def add_production_indexes():
    """Add database indexes for common queries."""
    
    indexes = [
        # Bills table indexes
        "CREATE INDEX IF NOT EXISTS idx_bills_congress_chamber ON bills(congress, chamber);",
        "CREATE INDEX IF NOT EXISTS idx_bills_introduced_date ON bills(introduced_date);",
        "CREATE INDEX IF NOT EXISTS idx_bills_congress_chamber_date ON bills(congress, chamber, introduced_date);",
        "CREATE INDEX IF NOT EXISTS idx_bills_sponsor_id ON bills(sponsor_id);",
        "CREATE INDEX IF NOT EXISTS idx_bills_subject ON bills(subject);",
        
        # Rollcalls table indexes
        "CREATE INDEX IF NOT EXISTS idx_rollcalls_congress_chamber ON rollcalls(congress, chamber);",
        "CREATE INDEX IF NOT EXISTS idx_rollcalls_vote_date ON rollcalls(vote_date);",
        "CREATE INDEX IF NOT EXISTS idx_rollcalls_bill_id ON rollcalls(bill_id);",
        "CREATE INDEX IF NOT EXISTS idx_rollcalls_congress_chamber_date ON rollcalls(congress, chamber, vote_date);",
        
        # Votes table indexes
        "CREATE INDEX IF NOT EXISTS idx_votes_rollcall_id ON votes(rollcall_id);",
        "CREATE INDEX IF NOT EXISTS idx_votes_member_id ON votes(member_id);",
        "CREATE INDEX IF NOT EXISTS idx_votes_rollcall_member ON votes(rollcall_id, member_id);",
        "CREATE INDEX IF NOT EXISTS idx_votes_vote_cast ON votes(vote_cast);",
        
        # Members table indexes
        "CREATE INDEX IF NOT EXISTS idx_members_bioguide ON members(member_id_bioguide);",
        "CREATE INDEX IF NOT EXISTS idx_members_state_district ON members(state, district);",
        "CREATE INDEX IF NOT EXISTS idx_members_party ON members(party);",
        "CREATE INDEX IF NOT EXISTS idx_members_chamber ON members(chamber);",
        
        # Cosponsors table indexes
        "CREATE INDEX IF NOT EXISTS idx_cosponsors_bill_id ON cosponsors(bill_id);",
        "CREATE INDEX IF NOT EXISTS idx_cosponsors_member_id ON cosponsors(member_id);",
        "CREATE INDEX IF NOT EXISTS idx_cosponsors_bill_member ON cosponsors(bill_id, member_id);",
        
        # FEC candidates table indexes
        "CREATE INDEX IF NOT EXISTS idx_fec_candidates_state_district ON fec_candidates(candidate_state, candidate_district);",
        "CREATE INDEX IF NOT EXISTS idx_fec_candidates_office ON fec_candidates(candidate_office);",
        "CREATE INDEX IF NOT EXISTS idx_fec_candidates_election_year ON fec_candidates(election_year);",
        
        # Challengers table indexes
        "CREATE INDEX IF NOT EXISTS idx_challengers_state_district ON challengers(challenger_state, challenger_district);",
        "CREATE INDEX IF NOT EXISTS idx_challengers_incumbent_id ON challengers(incumbent_id);",
    ]
    
    try:
        with get_db_session() as session:
            print("Adding production database indexes...")
            
            for i, index_sql in enumerate(indexes, 1):
                try:
                    session.execute(text(index_sql))
                    print(f"✓ Index {i}/{len(indexes)} created successfully")
                except Exception as e:
                    print(f"⚠ Index {i}/{len(indexes)} failed: {e}")
            
            session.commit()
            print(f"\n✓ Production indexes setup complete!")
            print("Database performance should be significantly improved.")
            
    except Exception as e:
        print(f"✗ Error adding indexes: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = add_production_indexes()
    sys.exit(0 if success else 1)
