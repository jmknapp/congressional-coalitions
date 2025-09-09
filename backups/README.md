# Database Backup System

This directory contains database backups for the Congressional Coalitions application.

## Backup Files

Backup files are named with the format:
```
congressional_coalitions_backup_YYYYMMDD_HHMMSS.sql.gz
```

Example: `congressional_coalitions_backup_20250908_201711.sql.gz`

## Backup Scripts

### Manual Backup
```bash
# Simple shell script
./scripts/backup_database.sh

# Python script with more features
python3 scripts/backup_database.py
```

### Automated Backups
```bash
# Set up daily backups at 2 AM
./scripts/setup_backup_cron.sh
```

### Restore Database
```bash
# List available backups
python3 scripts/restore_database.py --list

# Restore from specific backup
python3 scripts/restore_database.py --backup-file backups/congressional_coalitions_backup_20250908_201711.sql.gz

# Restore with database recreation
python3 scripts/restore_database.py --backup-file backups/congressional_coalitions_backup_20250908_201711.sql.gz --drop-db
```

### Backup Management
```bash
# List all backups
python3 scripts/manage_backups.py list

# Show backup statistics
python3 scripts/manage_backups.py stats

# Clean up old backups (keep last 30 days)
python3 scripts/manage_backups.py cleanup

# Dry run cleanup (see what would be deleted)
python3 scripts/manage_backups.py cleanup --dry-run
```

## Backup Configuration

- **Database**: `congressional_coalitions`
- **Host**: `localhost`
- **User**: `congressional`
- **Backup Directory**: `/home/jmknapp/congressional-coalitions/backups`
- **Retention**: 30 days (configurable)
- **Compression**: gzip (reduces size by ~70%)

## Backup Contents

Each backup includes:
- All tables and data
- Database structure (CREATE TABLE statements)
- Stored procedures and functions
- Triggers
- Events
- Complete INSERT statements for data recovery

## Security Notes

- Backup files contain sensitive data
- Ensure proper file permissions on backup directory
- Consider encrypting backups for production use
- Store backups in secure location separate from application

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure MySQL user has necessary privileges
2. **Disk Space**: Monitor backup directory size
3. **Cron Jobs**: Check cron logs if automated backups fail

### Logs

- Backup logs: `backups/logs/backup.log`
- Cron logs: `backups/logs/cron_backup.log`

## Recovery Testing

It's recommended to periodically test backup restoration:

```bash
# Test restore to a temporary database
mysql -u root -p -e "CREATE DATABASE test_restore;"
gunzip -c backups/congressional_coalitions_backup_YYYYMMDD_HHMMSS.sql.gz | mysql -u root -p test_restore
```

