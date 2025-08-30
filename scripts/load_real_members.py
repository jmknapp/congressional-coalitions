#!/usr/bin/env python3
import os
import sys
import click
import logging

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from etl.member_loader import MemberLoader
from src.utils.database import get_db_session
from scripts.setup_db import Member

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--clear', is_flag=True, help='Clear existing Members table before load')
def main(clear):
    if clear:
        with get_db_session() as session:
            logger.info("Clearing Members table...")
            session.query(Member).delete()
            session.commit()
            logger.info("Members table cleared")

    loader = MemberLoader()
    inserted_house = loader.load_house()
    inserted_senate = loader.load_senate()
    logger.info("Done. Inserted House=%d, Senate=%d", inserted_house, inserted_senate)

if __name__ == '__main__':
    main()


