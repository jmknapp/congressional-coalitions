#!/usr/bin/env python3
"""
Migration script to add contact information fields to the members table.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.database import get_db_session
from sqlalchemy import text

def add_contact_info_columns():
    """Add contact information columns to the members table."""
    print("Adding contact information columns to members table...")
    
    # SQL statements to add new columns
    migration_sql = [
        "ALTER TABLE members ADD COLUMN email VARCHAR(200) DEFAULT NULL",
        "ALTER TABLE members ADD COLUMN phone VARCHAR(20) DEFAULT NULL", 
        "ALTER TABLE members ADD COLUMN website VARCHAR(500) DEFAULT NULL",
        "ALTER TABLE members ADD COLUMN dc_office VARCHAR(500) DEFAULT NULL"
    ]
    
    try:
        with get_db_session() as session:
            for sql in migration_sql:
                try:
                    session.execute(text(sql))
                    print(f"✓ Executed: {sql}")
                except Exception as e:
                    if "Duplicate column name" in str(e) or "already exists" in str(e):
                        print(f"⚠ Column already exists: {sql}")
                    else:
                        print(f"❌ Error executing {sql}: {e}")
                        raise
            
            session.commit()
            print("✓ Contact information columns added successfully")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise

if __name__ == '__main__':
    add_contact_info_columns()
    print("\nMigration complete!")
