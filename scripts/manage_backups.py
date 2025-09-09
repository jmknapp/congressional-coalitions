#!/usr/bin/env python3
"""
Backup Management Script for Congressional Coalitions
Provides utilities for managing database backups
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def list_backups(backup_dir, show_details=False):
    """List all available backups with details."""
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        print(f"Backup directory does not exist: {backup_dir}")
        return
    
    backup_files = list(backup_path.glob("congressional_coalitions_backup_*.sql*"))
    backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not backup_files:
        print("No backup files found.")
        return
    
    print(f"\nFound {len(backup_files)} backup(s) in {backup_dir}:")
    print("-" * 80)
    
    for i, backup in enumerate(backup_files, 1):
        stat = backup.stat()
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime)
        age = datetime.now() - mtime
        
        # Format size
        if size > 1024 * 1024 * 1024:  # GB
            size_str = f"{size / (1024**3):.2f} GB"
        elif size > 1024 * 1024:  # MB
            size_str = f"{size / (1024**2):.2f} MB"
        else:  # KB
            size_str = f"{size / 1024:.2f} KB"
        
        # Format age
        if age.days > 0:
            age_str = f"{age.days} day(s) ago"
        elif age.seconds > 3600:
            age_str = f"{age.seconds // 3600} hour(s) ago"
        else:
            age_str = f"{age.seconds // 60} minute(s) ago"
        
        print(f"{i:2d}. {backup.name}")
        print(f"    Size: {size_str}")
        print(f"    Created: {mtime.strftime('%Y-%m-%d %H:%M:%S')} ({age_str})")
        
        if show_details:
            print(f"    Path: {backup}")
        print()

def cleanup_old_backups(backup_dir, days_to_keep=30, dry_run=False):
    """Remove backups older than specified days."""
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        print(f"Backup directory does not exist: {backup_dir}")
        return
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    backup_files = list(backup_path.glob("congressional_coalitions_backup_*.sql*"))
    
    old_backups = []
    for backup in backup_files:
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        if mtime < cutoff_date:
            old_backups.append(backup)
    
    if not old_backups:
        print(f"No backups older than {days_to_keep} days found.")
        return
    
    print(f"Found {len(old_backups)} backup(s) older than {days_to_keep} days:")
    for backup in old_backups:
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        age = datetime.now() - mtime
        print(f"  - {backup.name} ({age.days} days old)")
    
    if dry_run:
        print("\n[DRY RUN] No files were deleted.")
        return
    
    # Confirm deletion
    response = input(f"\nDelete these {len(old_backups)} backup(s)? (y/N): ")
    if response.lower() in ['y', 'yes']:
        deleted_count = 0
        for backup in old_backups:
            try:
                backup.unlink()
                deleted_count += 1
                print(f"Deleted: {backup.name}")
            except Exception as e:
                print(f"Error deleting {backup.name}: {e}")
        
        print(f"\nDeleted {deleted_count} backup(s).")
    else:
        print("Deletion cancelled.")

def backup_stats(backup_dir):
    """Show backup statistics."""
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        print(f"Backup directory does not exist: {backup_dir}")
        return
    
    backup_files = list(backup_path.glob("congressional_coalitions_backup_*.sql*"))
    
    if not backup_files:
        print("No backup files found.")
        return
    
    total_size = sum(f.stat().st_size for f in backup_files)
    oldest_backup = min(backup_files, key=lambda x: x.stat().st_mtime)
    newest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
    
    # Format total size
    if total_size > 1024 * 1024 * 1024:  # GB
        total_size_str = f"{total_size / (1024**3):.2f} GB"
    elif total_size > 1024 * 1024:  # MB
        total_size_str = f"{total_size / (1024**2):.2f} MB"
    else:  # KB
        total_size_str = f"{total_size / 1024:.2f} KB"
    
    print(f"\nBackup Statistics:")
    print(f"Total backups: {len(backup_files)}")
    print(f"Total size: {total_size_str}")
    print(f"Oldest backup: {oldest_backup.name}")
    print(f"Newest backup: {newest_backup.name}")
    
    # Show backup frequency
    if len(backup_files) > 1:
        oldest_time = datetime.fromtimestamp(oldest_backup.stat().st_mtime)
        newest_time = datetime.fromtimestamp(newest_backup.stat().st_mtime)
        time_span = newest_time - oldest_time
        avg_frequency = time_span.total_seconds() / (len(backup_files) - 1)
        
        if avg_frequency > 86400:  # More than a day
            avg_days = avg_frequency / 86400
            print(f"Average frequency: {avg_days:.1f} days between backups")
        else:
            avg_hours = avg_frequency / 3600
            print(f"Average frequency: {avg_hours:.1f} hours between backups")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Manage Congressional Coalitions database backups')
    parser.add_argument('--backup-dir', '-d', default='/home/jmknapp/congressional-coalitions/backups',
                       help='Backup directory path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List available backups')
    list_parser.add_argument('--details', action='store_true', help='Show detailed information')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Remove old backups')
    cleanup_parser.add_argument('--days', type=int, default=30, help='Keep backups newer than N days (default: 30)')
    cleanup_parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show backup statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'list':
        list_backups(args.backup_dir, args.details)
    elif args.command == 'cleanup':
        cleanup_old_backups(args.backup_dir, args.days, args.dry_run)
    elif args.command == 'stats':
        backup_stats(args.backup_dir)

if __name__ == "__main__":
    main()

