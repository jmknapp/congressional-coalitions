#!/usr/bin/env python3
"""
Wrapper script for House vote loader.
"""

import os
import sys
import click
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from etl.house_vote_loader import HouseVoteLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--congress', required=True, type=int, help='Congress number (e.g., 119)')
@click.option('--limit', type=int, help='Limit number of votes to load (for testing)')
def main(congress, limit):
    """Load House vote data."""
    
    logger.info(f"Loading House votes for Congress {congress}")
    
    loader = HouseVoteLoader()
    
    # Load votes
    loader.load_congress_votes(congress, limit=limit)
    
    logger.info(f"House vote loading complete")

if __name__ == '__main__':
    main()
