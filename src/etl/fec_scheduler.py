#!/usr/bin/env python3
"""
FEC Data Scheduler for automated daily downloads.
Handles scheduling, logging, and error recovery for FEC data updates.
"""

import os
import sys
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import Optional
import signal
import threading

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.etl.fec_service import FECDataService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fec_scheduler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class FECScheduler:
    """Scheduler for automated FEC data downloads."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the FEC scheduler.
        
        Args:
            api_key: FEC API key. If not provided, will look for FEC_API_KEY env var.
        """
        self.service = FECDataService(api_key)
        self.running = False
        self.scheduler_thread = None
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
    
    def daily_download_job(self):
        """Job to run daily FEC candidate download."""
        logger.info("Starting daily FEC candidate download job")
        
        try:
            # Download House candidates for 2026
            stats = self.service.download_and_store_candidates(
                office='H',
                election_year=2026,
                force_update=False
            )
            
            logger.info(f"Daily download completed successfully: {stats}")
            
            # Log any errors
            if stats.get('errors', 0) > 0:
                logger.warning(f"Daily download completed with {stats['errors']} errors")
            
            return True
            
        except Exception as e:
            logger.error(f"Daily download job failed: {e}")
            return False
    
    def weekly_cleanup_job(self):
        """Job to run weekly cleanup of old data."""
        logger.info("Starting weekly cleanup job")
        
        try:
            removed_count = self.service.cleanup_old_data(days_old=30)
            logger.info(f"Weekly cleanup completed, removed {removed_count} old records")
            return True
            
        except Exception as e:
            logger.error(f"Weekly cleanup job failed: {e}")
            return False
    
    def health_check_job(self):
        """Job to run health checks and log system status."""
        logger.info("Running health check")
        
        try:
            # Test FEC API connection
            if not self.service.client.test_connection():
                logger.error("FEC API connection test failed")
                return False
            
            # Get database stats
            stats = self.service.get_download_stats()
            logger.info(f"Database stats: {stats}")
            
            # Check if data is recent (within last 2 days)
            if stats.get('last_update'):
                last_update = datetime.fromisoformat(stats['last_update'].replace('Z', '+00:00'))
                time_since_update = datetime.utcnow() - last_update.replace(tzinfo=None)
                
                if time_since_update > timedelta(days=2):
                    logger.warning(f"Data is {time_since_update.days} days old")
                else:
                    logger.info("Data is up to date")
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def setup_schedule(self):
        """Set up the scheduled jobs."""
        # Daily download at 6 AM UTC
        schedule.every().day.at("06:00").do(self.daily_download_job)
        
        # Weekly cleanup on Sundays at 2 AM UTC
        schedule.every().sunday.at("02:00").do(self.weekly_cleanup_job)
        
        # Health check every 6 hours
        schedule.every(6).hours.do(self.health_check_job)
        
        logger.info("Scheduled jobs configured:")
        logger.info("  - Daily FEC download: 06:00 UTC")
        logger.info("  - Weekly cleanup: Sunday 02:00 UTC")
        logger.info("  - Health check: Every 6 hours")
    
    def _run_scheduler(self):
        """Run the scheduler in a separate thread."""
        logger.info("FEC scheduler started")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)  # Wait before retrying
        
        logger.info("FEC scheduler stopped")
    
    def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        logger.info("Starting FEC scheduler...")
        
        # Set up the schedule
        self.setup_schedule()
        
        # Run initial health check
        self.health_check_job()
        
        # Start scheduler thread
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("FEC scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        logger.info("Stopping FEC scheduler...")
        self.running = False
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10)
        
        logger.info("FEC scheduler stopped")
    
    def run_manual_download(self, force_update: bool = False) -> dict:
        """
        Run a manual download immediately.
        
        Args:
            force_update: If True, update existing records even if recently updated
            
        Returns:
            Download statistics
        """
        logger.info(f"Running manual download (force_update={force_update})")
        
        try:
            stats = self.service.download_and_store_candidates(
                office='H',
                election_year=2026,
                force_update=force_update
            )
            
            logger.info(f"Manual download completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Manual download failed: {e}")
            raise
    
    def get_status(self) -> dict:
        """Get current scheduler status."""
        return {
            'running': self.running,
            'next_job': str(schedule.next_run()) if schedule.jobs else None,
            'database_stats': self.service.get_download_stats(),
            'api_connected': self.service.client.test_connection()
        }


def main():
    """Main function for running the scheduler."""
    import argparse
    
    parser = argparse.ArgumentParser(description='FEC Data Scheduler')
    parser.add_argument('--manual', action='store_true', help='Run manual download and exit')
    parser.add_argument('--force', action='store_true', help='Force update existing records')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (continuous)')
    parser.add_argument('--test', action='store_true', help='Test API connection and exit')
    
    args = parser.parse_args()
    
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    try:
        scheduler = FECScheduler()
        
        if args.test:
            # Test mode
            print("Testing FEC API connection...")
            if scheduler.service.client.test_connection():
                print("✓ FEC API connection successful")
            else:
                print("✗ FEC API connection failed")
                sys.exit(1)
            
            # Test database
            print("Testing database connection...")
            stats = scheduler.service.get_download_stats()
            print(f"✓ Database connected, {stats['total_candidates']} candidates")
            
        elif args.manual:
            # Manual download mode
            print("Running manual FEC download...")
            stats = scheduler.run_manual_download(force_update=args.force)
            print(f"✓ Manual download completed: {stats}")
            
        elif args.daemon:
            # Daemon mode
            print("Starting FEC scheduler daemon...")
            scheduler.start()
            
            try:
                # Keep the main thread alive
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
                scheduler.stop()
        
        else:
            # Default: run once and exit
            print("Running FEC download once...")
            stats = scheduler.run_manual_download(force_update=args.force)
            print(f"✓ Download completed: {stats}")
            
    except Exception as e:
        logger.error(f"FEC scheduler error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
