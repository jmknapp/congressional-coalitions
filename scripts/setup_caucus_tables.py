#!/usr/bin/env python3
"""
Script to set up caucus database tables for the congressional coalitions system.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean, Text, create_engine
from sqlalchemy.orm import relationship
from datetime import datetime

# Import existing models to ensure tables exist
from scripts.setup_db import Base, Member

class Caucus(Base):
    """Caucus definitions table."""
    __tablename__ = 'caucuses'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    short_name = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    color = Column(String(7), default='#6c757d')  # Bootstrap color hex
    icon = Column(String(50), default='fas fa-users')  # Font Awesome icon
    is_active = Column(Boolean, default=True)
    created_at = Column(Date, default=datetime.now().date())
    
    # Relationship to memberships
    memberships = relationship("CaucusMembership", back_populates="caucus")

class CaucusMembership(Base):
    """Member-caucus relationship table."""
    __tablename__ = 'caucus_memberships'
    
    id = Column(Integer, primary_key=True)
    member_id_bioguide = Column(String(20), ForeignKey('members.member_id_bioguide'), nullable=False)
    caucus_id = Column(Integer, ForeignKey('caucuses.id'), nullable=False)
    start_date = Column(Date, nullable=True)  # Make start date optional
    end_date = Column(Date, nullable=True)  # NULL means current membership
    notes = Column(Text)
    created_at = Column(Date, default=datetime.now().date())
    
    # Relationships
    caucus = relationship("Caucus", back_populates="memberships")
    member = relationship("Member", foreign_keys=[member_id_bioguide])

def setup_caucus_tables():
    """Create the caucus tables."""
    print("Creating caucus tables...")
    
    # Create database engine
    database_url = os.environ.get('DATABASE_URL', 'mysql://congressional:congressional123@localhost/congressional_coalitions')
    engine = create_engine(database_url, echo=False)
    
    # Create tables
    Base.metadata.create_all(engine)
    print("✓ Caucus tables created successfully")
    
    # Insert default caucuses
    with get_db_session() as session:
        # Check if caucuses already exist
        existing_caucuses = session.query(Caucus).count()
        if existing_caucuses == 0:
            print("Inserting default caucuses...")
            
            default_caucuses = [
                {
                    'name': 'Freedom Caucus',
                    'short_name': 'Freedom Caucus',
                    'description': 'Conservative Republican caucus',
                    'color': '#dc3545',
                    'icon': 'fas fa-flag'
                },
                {
                    'name': 'Progressive Caucus',
                    'short_name': 'Progressive Caucus',
                    'description': 'Progressive Democratic caucus',
                    'color': '#0d6efd',
                    'icon': 'fas fa-star'
                },
                {
                    'name': 'Blue Dog Coalition',
                    'short_name': 'Blue Dog',
                    'description': 'Moderate Democratic caucus',
                    'color': '#0dcaf0',
                    'icon': 'fas fa-dog'
                },
                {
                    'name': 'Congressional Black Caucus',
                    'short_name': 'CBC',
                    'description': 'African American members of Congress',
                    'color': '#000000',
                    'icon': 'fas fa-users'
                },
                {
                    'name': 'True Blue Democrats',
                    'short_name': 'TB',
                    'description': 'Liberal Democratic caucus',
                    'color': '#007bff',
                    'icon': 'fas fa-heart'
                }
            ]
            
            for caucus_data in default_caucuses:
                caucus = Caucus(**caucus_data)
                session.add(caucus)
            
            session.commit()
            print("✓ Default caucuses inserted")
        else:
            print(f"✓ {existing_caucuses} caucuses already exist")

if __name__ == '__main__':
    setup_caucus_tables()
    print("\nCaucus table setup complete!")
