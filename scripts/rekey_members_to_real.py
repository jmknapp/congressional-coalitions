#!/usr/bin/env python3
import os
import sys
import click
import logging
from collections import defaultdict

# Ensure project root is on sys.path so 'src' is importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from src.utils.database import get_db_session
from scripts.setup_db import Member, Vote, Bill, Cosponsor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--apply', is_flag=True, help='Apply changes. Without this flag, runs as dry-run.')
@click.option('--force', is_flag=True, help='Force rekey of all House/Senate members by seat mapping (state+district; state+party).')
def main(apply: bool, force: bool):
    """Re-key members to real bioguide IDs and optionally prune unreferenced synthetic rows.
    Default mode only rekeys rows detected as synthetic; --force rekeys all by seat mapping.
    """
    with get_db_session() as session:
        # Build real member indexes
        real_house = {}
        real_senate = defaultdict(list)
        for m in session.query(Member).all():
            if m.district is not None:
                real_house[(m.state, m.district)] = m.member_id_bioguide
            else:
                real_senate[m.state].append((m.party, m.member_id_bioguide))
        logger.info("Indexed real members: House keys=%d, Senate states=%d", len(real_house), len(real_senate))

        if not real_house:
            logger.error("No House (state+district) keys found. Ensure real rosters are loaded.")
            return

        updates = []
        members = session.query(Member).all()
        for s in members:
            target_id = None
            if s.district is not None:
                # House mapping by seat
                key = (s.state, s.district)
                target_id = real_house.get(key)
                meta = key
            else:
                # Senate mapping by state + party if available
                seats = real_senate.get(s.state) or []
                meta = s.state
                if seats:
                    if s.party in ('D', 'R', 'I'):
                        for p, rid in seats:
                            if p == s.party:
                                target_id = rid
                                break
                    if not target_id:
                        # fallback to first
                        target_id = seats[0][1]
            if not target_id:
                continue
            if target_id == s.member_id_bioguide:
                # already correct
                continue
            if force:
                updates.append((s.member_id_bioguide, target_id, 'house' if s.district is not None else 'senate', meta))
            else:
                # only rekey rows that look synthetic (missing name or party outside D/R/I)
                looks_synthetic = (not s.first or not s.last or s.party not in ('D', 'R', 'I'))
                if looks_synthetic:
                    updates.append((s.member_id_bioguide, target_id, 'house' if s.district is not None else 'senate', meta))

        if not updates:
            logger.info("No members to rekey (try --force if needed).")
            return

        # Dry run report
        logger.info("Proposed updates: %d", len(updates))
        for i, (old_id, new_id, chamber, key) in enumerate(updates[:10], 1):
            logger.info("%d) %s -> %s (%s %s)", i, old_id, new_id, chamber, key)
        if len(updates) > 10:
            logger.info("... and %d more", len(updates) - 10)

        if not apply:
            logger.info("Dry-run only. Re-run with --apply%s to perform updates.", " --force" if force else "")
            return

        # Apply transactional updates: votes, bills, cosponsors, then prune unreferenced members
        old_to_new = {old_id: new_id for old_id, new_id, _, _ in updates}

        # Update Votes
        vote_updates = 0
        for old_id, new_id in old_to_new.items():
            vote_updates += session.query(Vote).filter(Vote.member_id_bioguide == old_id).update({Vote.member_id_bioguide: new_id})
        logger.info("Updated %d vote rows", vote_updates)

        # Update Bills (sponsor)
        bill_updates = 0
        for old_id, new_id in old_to_new.items():
            bill_updates += session.query(Bill).filter(Bill.sponsor_bioguide == old_id).update({Bill.sponsor_bioguide: new_id})
        logger.info("Updated %d bill rows (sponsor_bioguide)", bill_updates)

        # Update Cosponsors
        cos_updates = 0
        for old_id, new_id in old_to_new.items():
            cos_updates += session.query(Cosponsor).filter(Cosponsor.member_id_bioguide == old_id).update({Cosponsor.member_id_bioguide: new_id})
        logger.info("Updated %d cosponsor rows", cos_updates)

        session.commit()

        # Prune unreferenced old IDs
        pruned = 0
        for old_id in list(old_to_new.keys()):
            v_count = session.query(Vote).filter(Vote.member_id_bioguide == old_id).count()
            b_count = session.query(Bill).filter(Bill.sponsor_bioguide == old_id).count()
            c_count = session.query(Cosponsor).filter(Cosponsor.member_id_bioguide == old_id).count()
            if v_count == 0 and b_count == 0 and c_count == 0:
                m = session.query(Member).filter(Member.member_id_bioguide == old_id).first()
                if m:
                    session.delete(m)
                    pruned += 1
        session.commit()
        logger.info("Pruned %d unreferenced old member rows", pruned)
        logger.info("Rekey complete.")

if __name__ == '__main__':
    main()
