#!/usr/bin/env python3
"""
GovInfo RCV (Roll Call Votes) loader for congressional roll call data.

Downloads bulk ZIPs per chamber for a Congress and inserts rows into Rollcall and Vote.
Resilient to missing fields; skips unparseable records.
"""
import os
import io
import sys
import csv
import json
import logging
import zipfile
from datetime import datetime, date
from typing import Optional, List, Dict

import requests

# Add project root src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils.database import get_db_session
from scripts.setup_db import Rollcall, Vote

logger = logging.getLogger(__name__)


class RCVLoader:
    base_url = "https://www.govinfo.gov/bulkdata/RCV"

    def __init__(self):
        self.session = requests.Session()

    def _zip_url(self, congress: int, chamber: str) -> str:
        chamber = chamber.lower()
        if chamber not in ("house", "senate"):
            raise ValueError("chamber must be 'house' or 'senate'")
        return f"{self.base_url}/{congress}/{chamber}/RCV-{congress}-{chamber}.zip"

    def _dir_url(self, congress: int, chamber: str) -> str:
        chamber = chamber.lower()
        return f"{self.base_url}/{congress}/{chamber}/"

    def _list_from_directory(self, congress: int, chamber: str) -> List[str]:
        """Fallback: scrape directory listing for JSON files."""
        url = self._dir_url(congress, chamber)
        try:
            resp = self.session.get(url)
            resp.raise_for_status()
            import re
            names = re.findall(r'href=\"(RCV-\d+-[^\"]+?\.json)\"', resp.text, flags=re.IGNORECASE)
            return [url + n for n in names]
        except Exception as e:
            logger.warning("Failed to list RCV directory %s: %s", url, e)
            return []

    def _normalize_rollcall_id(self, rc_number: int, congress: int) -> str:
        return f"rc-{rc_number}-{congress}"

    def _normalize_bill_id(self, bill_type: Optional[str], number: Optional[str], congress: int) -> Optional[str]:
        if not bill_type or not number:
            return None
        btype = bill_type.lower()
        num = str(number).strip()
        # Map common names to our types
        mapping = {
            'hr': 'hr', 's': 's',
            'hjres': 'hjres', 'sjres': 'sjres',
            'hconres': 'hconres', 'sconres': 'sconres',
            'hres': 'hres', 'sres': 'sres',
        }
        btype = mapping.get(btype, btype)
        if not num.isdigit():
            # Sometimes formatted like 'H.R. 123'; try to strip punctuation
            num = ''.join(ch for ch in num if ch.isdigit())
        if not num:
            return None
        return f"{btype}-{int(num)}-{congress}"

    def load_congress(self, congress: int, chamber: str) -> None:
        url = self._zip_url(congress, chamber)
        logger.info("Downloading RCV ZIP: %s", url)
        resp = self.session.get(url, stream=True)
        if resp.status_code == 200 and 'zip' in (resp.headers.get('Content-Type') or '').lower():
            try:
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    files = [n for n in zf.namelist() if n.lower().endswith(('.json', '.xml', '.csv'))]
                    logger.info("Found %d RCV files in ZIP", len(files))
                    self._ingest_files(congress, chamber, zip_reader=zf)
                    return
            except zipfile.BadZipFile:
                logger.warning("Bad ZIP content; will try directory listing fallback")
        else:
            logger.info("ZIP not available (status=%s, content-type=%s); trying directory listing",
                        resp.status_code, resp.headers.get('Content-Type'))

        # Fallback: directory listing
        file_urls = self._list_from_directory(congress, chamber)
        logger.info("Found %d RCV JSON files via directory listing", len(file_urls))
        self._ingest_files(congress, chamber, url_list=file_urls)

    def _ingest_files(self, congress: int, chamber: str, zip_reader: Optional[zipfile.ZipFile] = None, url_list: Optional[List[str]] = None) -> None:
        loaded = 0
        skipped = 0
        with get_db_session() as session:
            if zip_reader is not None:
                for name in zip_reader.namelist():
                    if not name.lower().endswith('.json'):
                        continue
                    try:
                        data = zip_reader.read(name)
                        rc = self._parse_vote_file(data, name)
                        if not rc:
                            skipped += 1
                            continue
                        self._upsert_rollcall_and_votes(session, rc)
                        loaded += 1
                    except Exception as e:
                        logger.warning("Skipped %s: %s", name, e)
                        skipped += 1
            elif url_list:
                for file_url in url_list:
                    try:
                        r = self.session.get(file_url)
                        r.raise_for_status()
                        rc = self._parse_vote_file(r.content, file_url)
                        if not rc:
                            skipped += 1
                            continue
                        self._upsert_rollcall_and_votes(session, rc)
                        loaded += 1
                    except Exception as e:
                        logger.warning("Skipped %s: %s", file_url, e)
                        skipped += 1
            session.commit()
        logger.info("RCV load complete: loaded=%d skipped=%d", loaded, skipped)

    def _upsert_rollcall_and_votes(self, session, rc: Dict) -> None:
        existing = session.query(Rollcall).filter(Rollcall.rollcall_id == rc['rollcall_id']).first()
        if not existing:
            session.add(Rollcall(
                rollcall_id=rc['rollcall_id'],
                congress=rc['congress'],
                chamber=rc['chamber'].lower(),
                session=rc.get('session'),
                rc_number=rc['rc_number'],
                question=rc.get('question'),
                bill_id=rc.get('bill_id'),
                date=rc.get('date')
            ))
            session.flush()
        for v in rc.get('votes', []):
            if not v.get('member_id_bioguide') or not v.get('vote_code'):
                continue
            exists = session.query(Vote).filter(
                Vote.rollcall_id == rc['rollcall_id'],
                Vote.member_id_bioguide == v['member_id_bioguide']
            ).first()
            if not exists:
                session.add(Vote(
                    rollcall_id=rc['rollcall_id'],
                    member_id_bioguide=v['member_id_bioguide'],
                    vote_code=v['vote_code']
                ))

    def _parse_vote_file(self, blob: bytes, name: str) -> Optional[Dict]:
        lower = name.lower()
        try:
            if lower.endswith('.json'):
                j = json.loads(blob.decode('utf-8', errors='ignore'))
                return self._parse_vote_json(j)
            # Future: add XML parser if present; many RCV bundles include JSON
            return None
        except Exception as e:
            logger.debug("Parse error for %s: %s", name, e)
            return None

    def _parse_vote_json(self, j: Dict) -> Optional[Dict]:
        # Try common structures used in GovInfo RCV JSON
        meta = j.get('metadata') or j.get('vote_metadata') or {}
        congress = int(meta.get('congress') or j.get('congress') or 0)
        chamber = (meta.get('chamber') or j.get('chamber') or '').lower()
        rc_number = int(meta.get('rollcall') or j.get('rollcall') or meta.get('rollcall_number') or 0)
        if not congress or not chamber or not rc_number:
            return None
        rollcall_id = self._normalize_rollcall_id(rc_number, congress)

        # Date
        date_str = meta.get('vote_date') or meta.get('date') or j.get('date')
        rc_date: Optional[date] = None
        if date_str:
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
                try:
                    rc_date = datetime.strptime(date_str[:19], fmt).date()
                    break
                except Exception:
                    continue
        
        # Question
        question = meta.get('vote_question_text') or meta.get('question') or j.get('question')

        # Bill link
        bill_type = meta.get('legis_num') or meta.get('bill_type') or ''
        bill_number = meta.get('bill_number') or ''
        bill_id = self._normalize_bill_id(str(bill_type).lower().replace('.', '').strip(), str(bill_number).strip(), congress)

        # Votes
        votes: List[Dict] = []
        # House: often under 'vote_data'/'recorded_votes'; Senate may differ
        vote_blocks = []
        for key in ('vote_data', 'votes', 'recorded_votes'):
            vb = j.get(key)
            if isinstance(vb, list):
                vote_blocks = vb
                break
            if isinstance(vb, dict):
                if isinstance(vb.get('recorded_vote'), list):
                    vote_blocks = vb['recorded_vote']
                    break
        if not vote_blocks and isinstance(j.get('members'), list):
            vote_blocks = j['members']

        def norm_vote_code(code: str) -> Optional[str]:
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

        for item in vote_blocks:
            bioguide = item.get('bioguide_id') or item.get('bioguideId') or item.get('id')
            code = item.get('vote') or item.get('value') or item.get('vote_cast')
            code = norm_vote_code(code)
            if bioguide and code:
                votes.append({'member_id_bioguide': bioguide, 'vote_code': code})

        return {
            'rollcall_id': rollcall_id,
            'congress': congress,
            'chamber': chamber,
            'session': meta.get('session'),
            'rc_number': rc_number,
            'question': question,
            'bill_id': bill_id,
            'date': rc_date,
            'votes': votes,
        }
