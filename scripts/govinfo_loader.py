#!/usr/bin/env python3
"""
Wrapper script for GovInfo BILLSTATUS loader.
"""

import os
import sys
import click
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from etl.govinfo_loader import GovInfoLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--congress', required=True, type=int, help='Congress number (e.g., 119)')
@click.option('--chamber', default='both', type=click.Choice(['house', 'senate', 'both']), 
              help='Chamber to load (house, senate, or both)')
@click.option('--limit', type=int, help='Limit number of bills to load (for testing)')
@click.option('--api-key', envvar='GOVINFO_API_KEY', help='GovInfo API key (optional)')
def main(congress, chamber, limit, api_key):
    """Load bill data from GovInfo BILLSTATUS."""
    
    logger.info(f"Loading bills for Congress {congress}, chamber: {chamber}")
    
    loader = GovInfoLoader(api_key=api_key)
    
    # Get list of bills
    bills = loader.get_congress_bills(congress, chamber)
    
    if limit:
        bills = bills[:limit]
        logger.info(f"Limited to {limit} bills for testing")
    
    logger.info(f"Found {len(bills)} bills to load")
    
    # Load bills
    loaded_count = 0
    for bill_id in bills:
        try:
            success = loader.load_bill(bill_id)
            if success:
                loaded_count += 1
                logger.info(f"Loaded bill {bill_id} ({loaded_count}/{len(bills)})")
            else:
                logger.warning(f"Failed to load bill {bill_id}")
        except Exception as e:
            logger.error(f"Error loading bill {bill_id}: {e}")
    
    logger.info(f"Successfully loaded {loaded_count} out of {len(bills)} bills")

if __name__ == '__main__':
    main()
