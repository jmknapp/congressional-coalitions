#!/usr/bin/env python3
"""
Script to update the caucus_memberships table schema to allow NULL start_date values.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from sqlalchemy import text

def update_caucus_schema():
    """Update the caucus_memberships table to allow NULL start_date values."""
    print("Updating caucus_memberships table schema...")
    
    try:
        with get_db_session() as session:
            # Check current table structure
            result = session.execute(text("DESCRIBE caucus_memberships"))
            columns = result.fetchall()
            
            print("Current table structure:")
            for col in columns:
                print(f"  {col[0]}: {col[1]} {col[2]} {col[3]} {col[4]} {col[5]}")
            
            # Check if start_date is already nullable
            start_date_col = next((col for col in columns if col[0] == 'start_date'), None)
            if start_date_col and start_date_col[2] == 'YES':  # IS_NULLABLE = YES
                print("✓ start_date is already nullable")
                return
            
            # Update the start_date column to allow NULL
            print("Modifying start_date column to allow NULL...")
            session.execute(text("ALTER TABLE caucus_memberships MODIFY COLUMN start_date DATE NULL"))
            session.commit()
            
            print("✓ start_date column updated successfully")
            
            # Verify the change
            result = session.execute(text("DESCRIBE caucus_memberships"))
            columns = result.fetchall()
            
            print("\nUpdated table structure:")
            for col in columns:
                print(f"  {col[0]}: {col[1]} {col[2]} {col[3]} {col[4]} {col[5]}")
            
    except Exception as e:
        print(f"❌ Error updating schema: {e}")
        raise

if __name__ == '__main__':
    update_caucus_schema()
    print("\nSchema update complete!")
