#!/usr/bin/env python3
"""
Cron script to update analysis cache.
This script runs the coalition analysis and stores results in cache for quick retrieval.

Usage:
    python3 scripts/cron_update_analysis.py [--congress CONGRESS] [--chamber CHAMBER]

Example:
    python3 scripts/cron_update_analysis.py --congress 119 --chamber house
"""

import sys
import os
import logging
import argparse
import requests
import time
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/analysis_cron.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)



def update_analysis_cache(congress=119, chamber='house', port=5000, host='localhost'):
    """Run analysis by calling the Flask app API endpoint."""
    try:
        logger.info(f"Starting analysis update for Congress {congress}, {chamber}")
        start_time = datetime.now()
        
        # Clear any existing cache first to force fresh analysis
        logger.info("Clearing existing cache to force fresh analysis...")
        clear_url = f"http://{host}:{port}/api/cache/clear"
        try:
            clear_response = requests.get(clear_url, timeout=30)
            if clear_response.status_code == 200:
                logger.info("Cache cleared successfully")
            else:
                logger.warning(f"Failed to clear cache: {clear_response.status_code}")
        except Exception as e:
            logger.warning(f"Could not clear cache: {str(e)}")
        
        # Make request to analysis endpoint to trigger fresh analysis
        url = f"http://{host}:{port}/api/analysis/{congress}/{chamber}"
        logger.info(f"Requesting analysis from: {url}")
        
        response = requests.get(url, timeout=300)  # 5 minute timeout for analysis
        
        if response.status_code == 200:
            results = response.json()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Analysis completed successfully in {duration:.1f} seconds")
            logger.info(f"Analysis was {'cached' if results.get('cached', False) else 'freshly generated'}")
            
            # Log summary statistics
            if 'summary' in results:
                summary = results['summary']
                logger.info(f"Analysis summary: {summary.get('total_members', 'N/A')} members, "
                           f"{summary.get('total_rollcalls', 'N/A')} rollcalls, "
                           f"{summary.get('total_votes', 'N/A')} votes")
            
            if 'member_analysis' in results and 'cross_party_voters' in results['member_analysis']:
                cross_party_count = len(results['member_analysis']['cross_party_voters'])
                logger.info(f"Found {cross_party_count} cross-party voters")
            
            return True
        else:
            logger.error(f"Analysis request failed with status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error("Analysis request timed out after 5 minutes")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to Flask app at {host}:{port}. Is the server running?")
        return False
    except Exception as e:
        logger.error(f"Failed to update analysis cache: {str(e)}")
        logger.exception("Full traceback:")
        return False

def main():
    """Main function for command line execution."""
    parser = argparse.ArgumentParser(description='Update analysis cache via cron job')
    parser.add_argument('--congress', type=int, default=119, 
                       help='Congress number (default: 119)')
    parser.add_argument('--chamber', type=str, default='house',
                       choices=['house', 'senate'],
                       help='Chamber to analyze (default: house)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Flask app port (default: 5000)')
    parser.add_argument('--host', type=str, default='localhost',
                       help='Flask app host (default: localhost)')
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("CONGRESSIONAL COALITION ANALYSIS CRON JOB")
    logger.info("="*60)
    logger.info(f"Congress: {args.congress}")
    logger.info(f"Chamber: {args.chamber}")
    logger.info(f"Flask app: {args.host}:{args.port}")
    logger.info(f"Started at: {datetime.now()}")
    
    success = update_analysis_cache(
        congress=args.congress,
        chamber=args.chamber,
        port=args.port,
        host=args.host
    )
    
    if success:
        logger.info("✓ Analysis cache updated successfully")
        sys.exit(0)
    else:
        logger.error("✗ Failed to update analysis cache")
        sys.exit(1)

if __name__ == "__main__":
    main()
