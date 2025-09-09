#!/usr/bin/env python3
"""
Migration script to add mugshot_image_filename and biography fields to challengers2026 table.
"""

import os
import sys
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_challengers_table():
    """Add new fields to the existing challengers2026 table."""
    # Database connection
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set. Example: mysql://user:password@localhost/database")
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Add mugshot_image_filename column
                logger.info("Adding mugshot_image_filename column...")
                conn.execute(text("""
                    ALTER TABLE challengers2026 
                    ADD COLUMN mugshot_image_filename VARCHAR(255) NULL
                """))
                logger.info("✓ Added mugshot_image_filename column")
                
                # Add biography column
                logger.info("Adding biography column...")
                conn.execute(text("""
                    ALTER TABLE challengers2026 
                    ADD COLUMN biography TEXT NULL
                """))
                logger.info("✓ Added biography column")
                
                # Commit transaction
                trans.commit()
                logger.info("✓ Migration completed successfully")
                
                # Verify the changes
                result = conn.execute(text("DESCRIBE challengers2026"))
                columns = [row[0] for row in result]
                
                if 'mugshot_image_filename' in columns and 'biography' in columns:
                    logger.info("✓ Verification successful - new columns exist")
                else:
                    logger.error("✗ Verification failed - new columns not found")
                    
            except Exception as e:
                trans.rollback()
                logger.error(f"Migration failed, rolling back: {e}")
                raise
                
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        raise

if __name__ == "__main__":
    migrate_challengers_table()
