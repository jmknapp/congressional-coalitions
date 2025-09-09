#!/usr/bin/env python3
"""
Setup script for the FEC Data Service.
Creates database tables, installs dependencies, and configures the service.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_command(command, description):
    """Run a shell command and log the result."""
    logger.info(f"Running: {description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        logger.info(f"✓ {description} completed successfully")
        if result.stdout:
            logger.debug(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ {description} failed: {e}")
        if e.stderr:
            logger.error(f"Error: {e.stderr}")
        return False

def check_python_dependencies():
    """Check if required Python packages are installed."""
    logger.info("Checking Python dependencies...")
    
    required_packages = [
        'requests',
        'schedule',
        'sqlalchemy',
        'mysqlclient'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            logger.warning(f"✗ {package} is missing")
    
    if missing_packages:
        logger.info(f"Installing missing packages: {', '.join(missing_packages)}")
        return run_command(
            f"pip install {' '.join(missing_packages)}",
            "Installing missing Python packages"
        )
    
    return True

def setup_database_tables():
    """Create the FEC candidates database table."""
    logger.info("Setting up database tables...")
    
    try:
        from scripts.setup_fec_candidates_table import setup_fec_candidates_table
        setup_fec_candidates_table()
        return True
    except Exception as e:
        logger.error(f"Failed to setup database tables: {e}")
        return False

def create_directories():
    """Create necessary directories."""
    logger.info("Creating necessary directories...")
    
    directories = [
        'logs',
        'cache',
        'data'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"✓ Created directory: {directory}")
    
    return True

def check_fec_api_key():
    """Check if FEC API key is configured."""
    logger.info("Checking FEC API key configuration...")
    
    api_key = os.getenv('FEC_API_KEY')
    if not api_key:
        logger.warning("✗ FEC_API_KEY environment variable is not set")
        logger.info("To get an API key:")
        logger.info("1. Visit https://api.data.gov/signup/")
        logger.info("2. Register for an account")
        logger.info("3. Set the FEC_API_KEY environment variable")
        logger.info("4. Or add it to your .env file")
        return False
    else:
        logger.info("✓ FEC_API_KEY is configured")
        return True

def test_fec_connection():
    """Test connection to FEC API."""
    logger.info("Testing FEC API connection...")
    
    try:
        from src.etl.fec_client import FECClient
        client = FECClient()
        
        if client.test_connection():
            logger.info("✓ FEC API connection successful")
            return True
        else:
            logger.error("✗ FEC API connection failed")
            return False
    except Exception as e:
        logger.error(f"✗ FEC API connection test failed: {e}")
        return False

def test_database_connection():
    """Test database connection."""
    logger.info("Testing database connection...")
    
    try:
        from src.utils.database import get_db_session
        with get_db_session() as session:
            session.execute("SELECT 1")
        logger.info("✓ Database connection successful")
        return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False

def run_initial_download():
    """Run an initial download of FEC data."""
    logger.info("Running initial FEC data download...")
    
    try:
        from src.etl.fec_service import FECDataService
        service = FECDataService()
        
        # Download a small sample first
        logger.info("Downloading sample data...")
        stats = service.download_and_store_candidates(
            office='H',
            election_year=2026,
            force_update=True
        )
        
        logger.info(f"✓ Initial download completed: {stats}")
        return True
    except Exception as e:
        logger.error(f"✗ Initial download failed: {e}")
        return False

def setup_systemd_service():
    """Setup systemd service for the FEC scheduler."""
    logger.info("Setting up systemd service...")
    
    service_file = Path("fec-scheduler.service")
    if not service_file.exists():
        logger.error("✗ fec-scheduler.service file not found")
        return False
    
    # Copy service file to systemd directory
    commands = [
        "sudo cp fec-scheduler.service /etc/systemd/system/",
        "sudo systemctl daemon-reload",
        "sudo systemctl enable fec-scheduler.service"
    ]
    
    for command in commands:
        if not run_command(command, f"Running: {command}"):
            return False
    
    logger.info("✓ Systemd service setup completed")
    logger.info("To start the service: sudo systemctl start fec-scheduler")
    logger.info("To check status: sudo systemctl status fec-scheduler")
    logger.info("To view logs: sudo journalctl -u fec-scheduler -f")
    
    return True

def main():
    """Main setup function."""
    logger.info("Starting FEC Data Service setup...")
    
    steps = [
        ("Creating directories", create_directories),
        ("Checking Python dependencies", check_python_dependencies),
        ("Testing database connection", test_database_connection),
        ("Setting up database tables", setup_database_tables),
        ("Checking FEC API key", check_fec_api_key),
        ("Testing FEC API connection", test_fec_connection),
        ("Running initial download", run_initial_download),
    ]
    
    failed_steps = []
    
    for step_name, step_function in steps:
        logger.info(f"\n--- {step_name} ---")
        if not step_function():
            failed_steps.append(step_name)
            logger.error(f"Setup failed at: {step_name}")
            break
    
    if failed_steps:
        logger.error(f"\nSetup failed at: {', '.join(failed_steps)}")
        logger.error("Please fix the issues above and run the setup again.")
        return False
    
    logger.info("\n✓ FEC Data Service setup completed successfully!")
    logger.info("\nNext steps:")
    logger.info("1. Set your FEC_API_KEY environment variable")
    logger.info("2. Optionally setup the systemd service: python setup_fec_service.py --systemd")
    logger.info("3. Test the service: python src/etl/fec_scheduler.py --test")
    logger.info("4. Run manual download: python src/etl/fec_scheduler.py --manual")
    logger.info("5. Start daemon: python src/etl/fec_scheduler.py --daemon")
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup FEC Data Service')
    parser.add_argument('--systemd', action='store_true', help='Setup systemd service')
    parser.add_argument('--test-only', action='store_true', help='Only run tests, skip setup')
    
    args = parser.parse_args()
    
    if args.test_only:
        logger.info("Running tests only...")
        test_database_connection()
        test_fec_connection()
    elif args.systemd:
        logger.info("Setting up systemd service...")
        setup_systemd_service()
    else:
        main()
