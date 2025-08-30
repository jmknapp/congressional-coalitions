#!/usr/bin/env python3
import os
import sys
import click
import logging

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from etl.rcv_loader import RCVLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--congress', required=True, type=int, help='Congress number (e.g., 119)')
@click.option('--chamber', default='both', type=click.Choice(['house', 'senate', 'both']),
              help='Chamber to load (house, senate, or both)')
def main(congress, chamber):
    loader = RCVLoader()
    if chamber in ('house', 'both'):
        logger.info("Loading House roll calls for Congress %d", congress)
        loader.load_congress(congress, 'house')
    if chamber in ('senate', 'both'):
        logger.info("Loading Senate roll calls for Congress %d", congress)
        loader.load_congress(congress, 'senate')
    logger.info("Done.")

if __name__ == '__main__':
    main()


