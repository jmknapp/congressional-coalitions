#!/usr/bin/env python3
"""
Wrapper script for Senate vote loader.
"""

import os
import sys
import click
import logging

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from etl.senate_vote_loader import SenateVoteLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--congress', required=True, type=int, help='Congress number (e.g., 119)')
@click.option('--session', type=int, help='Session number (1 or 2)')
@click.option('--limit', type=int, help='Limit number of votes to load (for testing)')
def main(congress, session, limit):
    """Load Senate vote data."""
    
    logger.info(f"Loading Senate votes for Congress {congress}")
    if session:
        logger.info(f"Session: {session}")
    
    loader = SenateVoteLoader()
    
    # Load votes
    loaded_count = loader.load_congress_votes(congress, session=session, limit=limit)
    
    logger.info(f"Successfully loaded {loaded_count} Senate votes")

if __name__ == '__main__':
    main()
