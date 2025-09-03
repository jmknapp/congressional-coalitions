#!/usr/bin/env python3
"""
Database migration script to add last_updated column to bills table.
This enables better bill selection distribution in the daily update script.
"""

import sys
import os
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.utils.database import get_db_session
    from sqlalchemy import text
    
    print("🔧 Adding last_updated column to bills table...")
    
    with get_db_session() as session:
        # Check if column already exists
        result = session.execute(text("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'bills'
            AND COLUMN_NAME = 'last_updated'
        """))
        
        column_exists = result.fetchone().count > 0
        
        if column_exists:
            print("✅ Column 'last_updated' already exists in bills table")
        else:
            # Add the column
            session.execute(text("""
                ALTER TABLE bills 
                ADD COLUMN last_updated DATETIME DEFAULT NULL
            """))
            
            print("✅ Added 'last_updated' column to bills table")
        
        # Update existing bills to have a baseline last_updated date
        # Set it to a month ago so they get prioritized for updates
        session.execute(text("""
            UPDATE bills 
            SET last_updated = DATE_SUB(NOW(), INTERVAL 30 DAY)
            WHERE last_updated IS NULL
        """))
        
        updated_count = session.execute(text("""
            SELECT COUNT(*) as count 
            FROM bills 
            WHERE last_updated IS NOT NULL
        """)).fetchone().count
        
        print(f"✅ Set baseline last_updated for {updated_count} existing bills")
        
        session.commit()
        
    print("🎉 Database migration completed successfully!")
    print("")
    print("The bills table now has a last_updated column that will:")
    print("  - Track when each bill was last processed")
    print("  - Enable better distribution of bill updates")
    print("  - Ensure all bills eventually get updated")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
except Exception as e:
    print(f"❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()


