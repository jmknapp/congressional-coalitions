#!/usr/bin/env python3
"""
Database Restore Script for Congressional Coalitions
Restores MySQL database from backup files
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
import argparse

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'congressional',
    'password': 'congressional123',
    'database': 'congressional_coalitions'
}

def setup_logging():
    """Set up logging for the restore script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

def list_available_backups(backup_dir):
    """List available backup files."""
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        logging.error(f"Backup directory does not exist: {backup_dir}")
        return []
    
    backup_files = list(backup_path.glob("congressional_coalitions_backup_*.sql*"))
    backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    return backup_files

def restore_from_file(backup_file, drop_database=False):
    """Restore database from backup file."""
    config = DB_CONFIG
    
    try:
        # Drop database if requested
        if drop_database:
            logging.info("Dropping existing database...")
            drop_cmd = [
                'mysql',
                f'--host={config["host"]}',
                f'--user={config["user"]}',
                f'--password={config["password"]}',
                '-e', f'DROP DATABASE IF EXISTS {config["database"]};'
            ]
            subprocess.run(drop_cmd, check=True)
            
            # Recreate database
            create_cmd = [
                'mysql',
                f'--host={config["host"]}',
                f'--user={config["user"]}',
                f'--password={config["password"]}',
                '-e', f'CREATE DATABASE {config["database"]};'
            ]
            subprocess.run(create_cmd, check=True)
            logging.info("Database recreated successfully")
        
        # Restore from backup
        logging.info(f"Restoring from backup: {backup_file}")
        
        if backup_file.suffix == '.gz':
            # Compressed backup
            restore_cmd = [
                'gunzip', '-c', str(backup_file)
            ]
            mysql_cmd = [
                'mysql',
                f'--host={config["host"]}',
                f'--user={config["user"]}',
                f'--password={config["password"]}',
                config['database']
            ]
            
            # Pipe gunzip output to mysql
            gunzip_process = subprocess.Popen(restore_cmd, stdout=subprocess.PIPE)
            mysql_process = subprocess.Popen(mysql_cmd, stdin=gunzip_process.stdout)
            gunzip_process.stdout.close()
            mysql_process.wait()
            
        else:
            # Uncompressed backup
            restore_cmd = [
                'mysql',
                f'--host={config["host"]}',
                f'--user={config["user"]}',
                f'--password={config["password"]}',
                config['database']
            ]
            
            with open(backup_file, 'r') as f:
                subprocess.run(restore_cmd, stdin=f, check=True)
        
        logging.info("Database restore completed successfully")
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Restore failed: {e}")
        raise
    except FileNotFoundError:
        logging.error("MySQL client tools not found. Make sure MySQL client is installed.")
        raise

def main():
    """Main restore function."""
    parser = argparse.ArgumentParser(description='Restore Congressional Coalitions database from backup')
    parser.add_argument('--backup-file', '-f', help='Path to backup file to restore')
    parser.add_argument('--backup-dir', '-d', default='/home/jmknapp/congressional-coalitions/backups',
                       help='Directory containing backup files')
    parser.add_argument('--list', '-l', action='store_true', help='List available backups')
    parser.add_argument('--drop-db', action='store_true', help='Drop existing database before restore')
    
    args = parser.parse_args()
    
    setup_logging()
    
    if args.list:
        # List available backups
        backups = list_available_backups(args.backup_dir)
        if backups:
            print("\nAvailable backups:")
            for i, backup in enumerate(backups, 1):
                size = backup.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.2f} MB"
                else:
                    size_str = f"{size / 1024:.2f} KB"
                print(f"{i}. {backup.name} ({size_str})")
        else:
            print("No backup files found.")
        return
    
    if not args.backup_file:
        print("Error: --backup-file is required for restore operation")
        print("Use --list to see available backups")
        sys.exit(1)
    
    backup_file = Path(args.backup_file)
    if not backup_file.exists():
        logging.error(f"Backup file does not exist: {backup_file}")
        sys.exit(1)
    
    try:
        logging.info("Starting database restore process...")
        restore_from_file(backup_file, args.drop_db)
        logging.info("Database restore process completed successfully")
        
    except Exception as e:
        logging.error(f"Restore process failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

