#!/usr/bin/env python3
"""
Load House roll call votes for a Congress from Congress.gov API.

- Reads CONGRESS_GOV_API_KEY from env
- Upserts Rollcall and Vote rows
- Normalizes vote codes: Yea, Nay, Present
- Links bill_id when present (e.g., hr-123-119)
- Uses sourceDataURL (Clerk XML) to fetch per-member positions
- Falls back to parsing Clerk plaintext (some early rolls are text-only)
- Safe fallbacks for missing fields (e.g., date defaults to today)
- Ensures Member rows exist for all bioguide IDs (to satisfy FK)
"""

import os
import sys
import time
import datetime
import argparse
import requests
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional, Dict

# Make project src importable
sys.path.insert(0, 'src')
from src.utils.database import get_db_session  # type: ignore
from scripts.setup_db import Rollcall, Vote, Member  # type: ignore


API_KEY = os.environ.get('CONGRESS_GOV_API_KEY', '')
BASE = 'https://api.congress.gov/v3'
HEADERS = {'Accept': 'application/json'}


def normalize_vote_code(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    c = code.strip().lower()
    if c in ('yea', 'aye', 'yes', 'y'):
        return 'Yea'
    if c in ('nay', 'no', 'n'):
        return 'Nay'
    if c in ('present', 'present - announced'):
        return 'Present'
    return None


def parse_date(date_str: Optional[str]) -> datetime.date:
    if not date_str:
        return datetime.date.today()
    date_str = date_str.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y'):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except Exception:
            continue
    return datetime.date.today()


def safe_int(value, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def build_name_to_bioguide_map() -> Dict[str, str]:
    """
    Build a simple 'first last' -> bioguide map from Members table.
    """
    name_to_bio: Dict[str, str] = {}
    with get_db_session() as s:
        db_members = s.query(Member).all()
        for m in db_members:
            first = (m.first or '').strip()
            last = (m.last or '').strip()
            if first and last:
                key = f'{first} {last}'.lower()
                name_to_bio[key] = m.member_id_bioguide
    return name_to_bio


def ensure_member(session_db, bioguide: str):
    """
    Create a placeholder Member row if missing (to satisfy FK on votes).
    """
    exists = session_db.query(Member).filter(Member.member_id_bioguide == bioguide).first()
    if exists:
        return
    session_db.add(Member(
        member_id_bioguide=bioguide,
        icpsr=None, lis_id=None,
        first='',
        last='',
        party=None,
        state='',
        district=None,
        start_date=None,
        end_date=None
    ))
    session_db.flush()


def extract_clerk_members(source_url: str) -> List[Tuple[str, str]]:
    """
    Fetch Clerk XML at sourceDataURL and return list of (bioguide_id, normalized_vote_code).
    Robust to namespaces/attribute casings. Falls back to parsing plaintext
    when XML recorded-vote nodes are not present (e.g., QUORUM calls).
    """
    try:
        xr = requests.get(source_url, timeout=30)
        if xr.status_code != 200:
            return []

        body = xr.content

        # Try XML first
        try:
            root = ET.fromstring(body)

            def tn(e): return e.tag.split('}')[-1].lower()
            def text_of(e, name):
                n = e.find(name)
                if n is not None and n.text:
                    return n.text.strip()
                for c in e:
                    if tn(c) == name.lower() and c.text:
                        return c.text.strip()
                return ''

            members_xml: List[Tuple[str, str]] = []
            votes = root.findall('.//recorded-vote') + root.findall('.//recorded_vote')
            if not votes:
                for node in root.iter():
                    if tn(node) in ('recorded-vote', 'recorded_vote'):
                        votes.append(node)
            for rv in votes:
                leg = rv.find('legislator')
                bid = ''
                if leg is not None:
                    # Include 'name-id' (observed on Clerk pages) and other casings
                    for attr in ('bioguide_id', 'bioguideId', 'bioguideID', 'name-id', 'name_id'):
                        val = leg.get(attr)
                        if val:
                            bid = val.strip()
                            break
                vraw = text_of(rv, 'vote') or ''
                v = normalize_vote_code(vraw)
                if bid and v:
                    members_xml.append((bid, v))
            if members_xml:
                return members_xml
        except Exception:
            pass  # not XML; try plaintext

        # Fallback: plaintext parsing (e.g., quorum call lists)
        text = xr.text
        name_to_bio = build_name_to_bioguide_map()
        members_txt: List[Tuple[str, str]] = []

        import re
        norm = text.replace('“', '"').replace('”', '"').replace('’', "'")

        # Pattern: "BeattyPresent", "GaetzNot Voting"
        for match in re.finditer(r'([A-Za-z.\'\- ]+?)(Present|Nay|Yea|Not Voting)\b', norm):
            raw_name = match.group(1).strip().replace('  ', ' ')
            raw_vote = match.group(2)
            vote_code = normalize_vote_code(raw_vote)
            if not vote_code:
                continue
            parts = [p for p in raw_name.split(' ') if p]
            if len(parts) >= 2:
                first = parts[0].rstrip(',').strip()
                last = parts[-1].rstrip(',').strip()
                key = f'{first} {last}'.lower()
                bid = name_to_bio.get(key)
                if bid:
                    members_txt.append((bid, vote_code))

        # Pattern: "Green, Al (TX)Present"
        for match in re.finditer(r'([A-Za-z.\'\- ]+?, [A-Za-z.\'\-() ]+?)(Present|Nay|Yea|Not Voting)\b', norm):
            raw = match.group(1)
            raw_vote = match.group(2)
            vote_code = normalize_vote_code(raw_vote)
            if not vote_code:
                continue
            name_part = raw.split('(')[0].strip()
            if ',' in name_part:
                last, first = [p.strip() for p in name_part.split(',', 1)]
                key = f'{first} {last}'.lower()
                bid = name_to_bio.get(key)
                if bid:
                    members_txt.append((bid, vote_code))

        return members_txt
    except Exception:
        return []


def upsert_vote(congress: int, session: int, rc_number: int) -> Tuple[int, int]:
    """
    Insert/Update one roll call vote and its member votes.
    Returns (inserted_rollcalls, inserted_votes)
    """
    url = f'{BASE}/house-vote/{congress}/{session}/{rc_number}?api_key={API_KEY}&format=json'
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return (0, 0)
    r.raise_for_status()

    payload = r.json() or {}
    j = payload.get('houseRollCallVote') or payload.get('houseVote') or payload.get('vote') or payload

    roll_number = safe_int(
        j.get('rollCallNumber') or j.get('rollNumber') or j.get('rollnumber') or rc_number,
        rc_number
    )
    rollcall_id = f'rc-{roll_number}-{congress}'

    # Question (Congress.gov uses voteQuestion)
    question = (j.get('voteQuestion') or j.get('questionText') or j.get('voteQuestionText') or j.get('question') or '').strip()

    # Date: use startDate (ISO) -> date portion
    start = j.get('startDate') or j.get('date')
    date_portion = (start or '').split('T', 1)[0] if start else None
    rc_date = parse_date(date_portion)

    # Bill
    bill_id = None
    bill = j.get('bill') or {}
    btype = (bill.get('type') or '').strip().lower()
    bnum = bill.get('number')
    if btype and (str(bnum or '').isdigit()):
        bill_id = f'{btype}-{int(bnum)}-{congress}'

    # Members: use Clerk XML source for per-member positions; if absent, build from year+roll
    members: List[Tuple[str, str]] = []
    source_url = j.get('sourceDataURL')
    if not source_url and start:
        year = (start or '')[:4]
        if year.isdigit():
            source_url = f'https://clerk.house.gov/evs/{year}/roll{roll_number:03d}.xml'
    if source_url:
        members = extract_clerk_members(source_url)

    inserted_rc = 0
    inserted_votes = 0

    with get_db_session() as session_db:
        # Skip inserting zero-vote rollcalls to avoid clutter (e.g., quorum plain-text)
        if not members:
            return (0, 0)

        existing = session_db.query(Rollcall).filter(Rollcall.rollcall_id == rollcall_id).first()
        if not existing:
            session_db.add(Rollcall(
                rollcall_id=rollcall_id,
                congress=congress,
                chamber='house',
                session=session,
                rc_number=roll_number,
                question=question,
                bill_id=bill_id,
                date=rc_date
            ))
            session_db.flush()
            inserted_rc = 1

        for bioguide, vote_code in members:
            ensure_member(session_db, bioguide)
            exists = session_db.query(Vote).filter(
                Vote.rollcall_id == rollcall_id,
                Vote.member_id_bioguide == bioguide
            ).first()
            if not exists:
                session_db.add(Vote(
                    rollcall_id=rollcall_id,
                    member_id_bioguide=bioguide,
                    vote_code=vote_code
                ))
                inserted_votes += 1

        session_db.commit()

    return (inserted_rc, inserted_votes)


def ingest_congress(congress: int, max_roll: int = 1600, sleep_sec: float = 0.15) -> None:
    """
    Brute-force sessions 1 and 2, roll numbers 1..max_roll.
    Idempotent; runs safely multiple times.
    """
    total_rc = 0
    total_votes = 0
    for session_num in (1, 2):
        misses = 0
        for rc_number in range(1, max_roll + 1):
            try:
                rc, vv = upsert_vote(congress, session_num, rc_number)
                if rc or vv:
                    total_rc += rc
                    total_votes += vv
                    misses = 0
                else:
                    misses += 1
                    if misses >= 50 and rc_number > 200:
                        break
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2.0)
                    continue
                continue
            except Exception:
                continue
            time.sleep(sleep_sec)
    print(f'house inserted rollcalls: {total_rc}, votes: {total_votes}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--congress', type=int, required=True, help='Congress number (e.g., 119)')
    ap.add_argument('--max-roll', type=int, default=1600, help='Max roll number to probe per session')
    args = ap.parse_args()

    if not API_KEY:
        print('Missing CONGRESS_GOV_API_KEY in environment')
        sys.exit(1)

    ingest_congress(args.congress, max_roll=args.max_roll)


if __name__ == '__main__':
    main()
