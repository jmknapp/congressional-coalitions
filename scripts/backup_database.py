#!/usr/bin/env python3
"""
Database Backup Script for Congressional Coalitions
Backs up MySQL database with compression and rotation
"""

import os
import sys
import subprocess
import datetime
import gzip
import shutil
import logging
from pathlib import Path

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'congressional',
    'password': 'congressional123',
    'database': 'congressional_coalitions'
}

# Backup configuration
BACKUP_CONFIG = {
    'backup_dir': '/home/jmknapp/congressional-coalitions/backups',
    'max_backups': 30,  # Keep 30 days of backups
    'compress': True,
    'include_timestamp': True
}

def setup_logging():
    """Set up logging for the backup script."""
    log_dir = Path(BACKUP_CONFIG['backup_dir']) / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'backup.log'),
            logging.StreamHandler()
        ]
    )

def create_backup_directory():
    """Create backup directory if it doesn't exist."""
    backup_dir = Path(BACKUP_CONFIG['backup_dir'])
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def generate_backup_filename():
    """Generate backup filename with timestamp."""
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = f"congressional_coalitions_backup_{timestamp}.sql"
    
    if BACKUP_CONFIG['compress']:
        return f"{base_name}.gz"
    return base_name

def run_mysqldump():
    """Run mysqldump to create database backup."""
    config = DB_CONFIG
    
    # Build mysqldump command
    cmd = [
        'mysqldump',
        f'--host={config["host"]}',
        f'--user={config["user"]}',
        f'--password={config["password"]}',
        '--single-transaction',
        '--routines',
        '--triggers',
        '--events',
        '--hex-blob',
        '--complete-insert',
        '--extended-insert',
        '--lock-tables=false',
        '--no-tablespaces',
        config['database']
    ]
    
    try:
        logging.info("Starting database backup...")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        logging.info("mysqldump completed successfully")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logging.error(f"mysqldump failed: {e}")
        logging.error(f"Error output: {e.stderr}")
        raise
    except FileNotFoundError:
        logging.error("mysqldump command not found. Make sure MySQL client tools are installed.")
        raise

def compress_backup(data, output_path):
    """Compress backup data and save to file."""
    try:
        with gzip.open(output_path, 'wt', encoding='utf-8') as f:
            f.write(data)
        logging.info(f"Backup compressed and saved to: {output_path}")
    except Exception as e:
        logging.error(f"Failed to compress backup: {e}")
        raise

def save_backup(data, output_path):
    """Save backup data to file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(data)
        logging.info(f"Backup saved to: {output_path}")
    except Exception as e:
        logging.error(f"Failed to save backup: {e}")
        raise

def cleanup_old_backups(backup_dir):
    """Remove old backups to maintain max_backups limit."""
    try:
        backup_files = list(backup_dir.glob("congressional_coalitions_backup_*.sql*"))
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        if len(backup_files) > BACKUP_CONFIG['max_backups']:
            files_to_remove = backup_files[BACKUP_CONFIG['max_backups']:]
            for file_path in files_to_remove:
                file_path.unlink()
                logging.info(f"Removed old backup: {file_path.name}")
                
    except Exception as e:
        logging.error(f"Failed to cleanup old backups: {e}")

def verify_backup(backup_path):
    """Verify backup file integrity."""
    try:
        if backup_path.suffix == '.gz':
            # Test gzip file
            with gzip.open(backup_path, 'rt') as f:
                first_line = f.readline()
                if 'MySQL dump' in first_line or '-- MySQL dump' in first_line:
                    logging.info("Backup verification successful (compressed)")
                    return True
        else:
            # Test regular SQL file
            with open(backup_path, 'r') as f:
                first_line = f.readline()
                if 'MySQL dump' in first_line or '-- MySQL dump' in first_line:
                    logging.info("Backup verification successful")
                    return True
        
        logging.warning("Backup verification failed - file may be corrupted")
        return False
        
    except Exception as e:
        logging.error(f"Backup verification failed: {e}")
        return False

def main():
    """Main backup function."""
    try:
        setup_logging()
        logging.info("Starting database backup process...")
        
        # Create backup directory
        backup_dir = create_backup_directory()
        
        # Generate backup filename
        backup_filename = generate_backup_filename()
        backup_path = backup_dir / backup_filename
        
        # Create backup
        backup_data = run_mysqldump()
        
        # Save backup (with or without compression)
        if BACKUP_CONFIG['compress']:
            compress_backup(backup_data, backup_path)
        else:
            save_backup(backup_data, backup_path)
        
        # Verify backup
        if verify_backup(backup_path):
            logging.info("Backup completed and verified successfully")
        else:
            logging.error("Backup verification failed")
            sys.exit(1)
        
        # Cleanup old backups
        cleanup_old_backups(backup_dir)
        
        # Log backup size
        backup_size = backup_path.stat().st_size
        if backup_size > 1024 * 1024:  # > 1MB
            size_mb = backup_size / (1024 * 1024)
            logging.info(f"Backup size: {size_mb:.2f} MB")
        else:
            size_kb = backup_size / 1024
            logging.info(f"Backup size: {size_kb:.2f} KB")
        
        logging.info("Database backup process completed successfully")
        
    except Exception as e:
        logging.error(f"Backup process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
