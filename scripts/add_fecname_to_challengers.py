#!/usr/bin/env python3
"""
Migration script to add fecname field to challengers2026 table.
This field will store the exact FEC name format for reliable matching.
"""

import os
import sys
from sqlalchemy import create_engine, text
from datetime import datetime
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_fecname_field():
    """Add fecname field to challengers2026 table."""
    # Database connection
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set. Example: mysql://user:password@localhost/database")
    
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Check if fecname column already exists
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'challengers2026' 
                AND COLUMN_NAME = 'fecname'
            """))
            
            if result.scalar() > 0:
                logger.info("✓ fecname column already exists in challengers2026 table")
                return
            
            # Add the fecname column
            logger.info("Adding fecname column to challengers2026 table...")
            conn.execute(text("""
                ALTER TABLE challengers2026 
                ADD COLUMN fecname VARCHAR(200) NULL 
                AFTER challenger_name
            """))
            
            # Add index on fecname for faster lookups
            logger.info("Adding index on fecname column...")
            conn.execute(text("""
                CREATE INDEX idx_challengers2026_fecname 
                ON challengers2026(fecname)
            """))
            
            conn.commit()
            logger.info("✓ Successfully added fecname field to challengers2026 table")
            
            # Show current table structure
            result = conn.execute(text("DESCRIBE challengers2026"))
            columns = result.fetchall()
            logger.info("Current table structure:")
            for column in columns:
                logger.info(f"  {column[0]} - {column[1]} - {column[2]}")
            
    except Exception as e:
        logger.error(f"Error adding fecname field: {e}")
        raise

def populate_existing_fecnames():
    """Populate fecname field for existing challengers based on their current names."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set")
    
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Get all challengers that don't have fecname set
            result = conn.execute(text("""
                SELECT id, challenger_name 
                FROM challengers2026 
                WHERE fecname IS NULL OR fecname = ''
            """))
            
            challengers = result.fetchall()
            logger.info(f"Found {len(challengers)} challengers without fecname")
            
            if not challengers:
                logger.info("✓ All challengers already have fecname populated")
                return
            
            # For now, set fecname to the current challenger_name
            # This can be updated later when FEC data is loaded
            updated_count = 0
            for challenger_id, current_name in challengers:
                # Convert current name back to FEC format as a starting point
                # This is a simple conversion - can be improved later
                fec_name = convert_to_fec_format(current_name)
                
                conn.execute(text("""
                    UPDATE challengers2026 
                    SET fecname = :fecname 
                    WHERE id = :id
                """), {"fecname": fec_name, "id": challenger_id})
                updated_count += 1
            
            conn.commit()
            logger.info(f"✓ Populated fecname for {updated_count} existing challengers")
            
    except Exception as e:
        logger.error(f"Error populating fecnames: {e}")
        raise

def convert_to_fec_format(name):
    """
    Convert a formatted name back to FEC format.
    This is a simple implementation - can be enhanced later.
    """
    if not name:
        return name
    
    # Handle common title patterns
    title_mapping = {
        'Mr.': 'MR.',
        'Ms.': 'MS.',
        'Mrs.': 'MRS.',
        'Dr.': 'DR.',
        'Rev.': 'REV.',
        'Prof.': 'PROF.',
        'Sen.': 'SEN.',
        'Rep.': 'REP.',
        'Gov.': 'GOV.',
        'Mayor': 'MAYOR',
        'Judge': 'JUDGE',
        'Capt.': 'CAPT.',
        'Col.': 'COL.',
        'Lt.': 'LT.',
        'Sgt.': 'SGT.',
        'Maj.': 'MAJ.',
        'Gen.': 'GEN.',
        'Adm.': 'ADM.',
        'Hon.': 'HON.'
    }
    
    parts = name.split()
    if len(parts) < 2:
        return name
    
    # Check if first part is a title
    title = None
    if parts[0] in title_mapping:
        title = title_mapping[parts[0]]
        name_parts = parts[1:]
    else:
        name_parts = parts
    
    if len(name_parts) < 2:
        return name
    
    # Assume last part is last name, rest is first name
    last_name = name_parts[-1]
    first_name = ' '.join(name_parts[:-1])
    
    # Construct FEC format
    if title:
        return f"{last_name.upper()}, {first_name.upper()} {title}"
    else:
        return f"{last_name.upper()}, {first_name.upper()}"

def main():
    """Main migration function."""
    logger.info("🔧 MIGRATION: Adding fecname field to challengers2026 table")
    logger.info("=" * 60)
    
    try:
        # Step 1: Add the fecname column
        add_fecname_field()
        
        # Step 2: Populate existing records
        populate_existing_fecnames()
        
        logger.info("✅ Migration completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Update the Challenger2026 model to include fecname field")
        logger.info("2. Update FEC population logic to use fecname as the key")
        logger.info("3. Update API endpoints to handle fecname field")
        logger.info("4. Update frontend to display and manage fecname field")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    main()
